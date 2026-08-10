"""
JARVIS Device Manager
======================
SQLite-backed device registry with state tracking, command dispatch,
and telemetry persistence. This is the single source of truth for
every device on the sovereign network.

Zero-cloud. All state is stored locally in SQLite WAL mode
for concurrent read/write access without blocking.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", ".jarvis_devices.db")
_lock = threading.Lock()


# ── Database Setup ──────────────────────────────────────────


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode for concurrent access."""
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the device registry database schema."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            device_type TEXT NOT NULL DEFAULT 'UNKNOWN',
            ip TEXT DEFAULT '',
            mac TEXT DEFAULT '',
            protocol TEXT DEFAULT 'unknown',
            manufacturer TEXT DEFAULT '',
            model TEXT DEFAULT '',
            firmware TEXT DEFAULT '',
            room TEXT DEFAULT 'unknown',
            state TEXT DEFAULT '{}',
            actions TEXT DEFAULT '{}',
            capabilities TEXT DEFAULT '[]',
            is_online INTEGER DEFAULT 0,
            signal_strength INTEGER DEFAULT -1,
            fingerprint TEXT DEFAULT '',
            first_seen REAL DEFAULT 0,
            last_seen REAL DEFAULT 0,
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS command_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            action TEXT NOT NULL,
            params TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            result TEXT DEFAULT '{}',
            latency_ms REAL DEFAULT 0,
            error TEXT DEFAULT '',
            initiated_by TEXT DEFAULT 'user',
            timestamp REAL DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        );

        CREATE TABLE IF NOT EXISTS state_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT '{}',
            timestamp REAL DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        );

        CREATE TABLE IF NOT EXISTS device_scenes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '🎬',
            device_states TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_cmd_device ON command_log(device_id);
        CREATE INDEX IF NOT EXISTS idx_cmd_time ON command_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_state_device ON state_history(device_id);
        CREATE INDEX IF NOT EXISTS idx_state_time ON state_history(timestamp);
    """)
    conn.commit()
    conn.close()


# Initialize on import
init_db()


# ── Device CRUD ─────────────────────────────────────────────


@contextmanager
def _transaction():
    """Context manager for atomic database transactions."""
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_device(device_data: dict) -> dict:
    """
    Insert or update a device in the registry.
    Returns the full device record.
    """
    now = time.time()
    now_str = datetime.now(timezone.utc).isoformat()

    device_id = device_data.get("id", str(uuid.uuid4())[:12])
    name = device_data.get("name", device_data.get("hostname", ""))
    device_type = device_data.get("device_type", "UNKNOWN").upper()
    ip = device_data.get("ip", device_data.get("network_address", ""))
    mac = device_data.get("mac", device_data.get("mac_address", ""))
    protocol = device_data.get("protocol", "unknown")
    manufacturer = device_data.get("manufacturer", "")
    model = device_data.get("model", "")
    firmware = device_data.get("firmware", device_data.get("firmware_version", ""))
    room = device_data.get("room", "unknown")
    state = json.dumps(device_data.get("state", {}))
    actions = json.dumps(device_data.get("normalized_actions", device_data.get("actions", {})))
    capabilities = json.dumps(device_data.get("capabilities", []))
    is_online = 1 if device_data.get("is_online", device_data.get("status") == "online") else 0
    signal = device_data.get("signal_strength", -1) or -1
    fingerprint = device_data.get("fingerprint", "")

    with _transaction() as conn:
        existing = conn.execute("SELECT id FROM devices WHERE id = ?", (device_id,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE devices SET
                    name = CASE WHEN ? != '' THEN ? ELSE name END,
                    device_type = CASE WHEN ? != 'UNKNOWN' THEN ? ELSE device_type END,
                    ip = CASE WHEN ? != '' THEN ? ELSE ip END,
                    mac = CASE WHEN ? != '' THEN ? ELSE mac END,
                    protocol = CASE WHEN ? != 'unknown' THEN ? ELSE protocol END,
                    manufacturer = CASE WHEN ? != '' THEN ? ELSE manufacturer END,
                    model = CASE WHEN ? != '' THEN ? ELSE model END,
                    firmware = CASE WHEN ? != '' THEN ? ELSE firmware END,
                    room = CASE WHEN ? != 'unknown' THEN ? ELSE room END,
                    state = ?,
                    actions = ?,
                    is_online = ?,
                    signal_strength = ?,
                    fingerprint = CASE WHEN ? != '' THEN ? ELSE fingerprint END,
                    last_seen = ?,
                    updated_at = ?
                WHERE id = ?
            """, (name, name, device_type, device_type, ip, ip, mac, mac,
                  protocol, protocol, manufacturer, manufacturer, model, model,
                  firmware, firmware, room, room, state, actions, is_online, signal,
                  fingerprint, fingerprint, now, now_str, device_id))
        else:
            conn.execute("""
                INSERT INTO devices (id, name, device_type, ip, mac, protocol,
                    manufacturer, model, firmware, room, state, actions, capabilities,
                    is_online, signal_strength, fingerprint, first_seen, last_seen,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (device_id, name, device_type, ip, mac, protocol,
                  manufacturer, model, firmware, room, state, actions, capabilities,
                  is_online, signal, fingerprint, now, now, now_str, now_str))

    return get_device(device_id)


def get_device(device_id: str) -> Optional[dict]:
    """Get a single device by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    conn.close()
    if row:
        return _row_to_dict(row)
    return None


def get_all_devices() -> List[dict]:
    """Get all devices in the registry."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_online_devices() -> List[dict]:
    """Get all currently online devices."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM devices WHERE is_online = 1 ORDER BY name").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_devices_by_type(device_type: str) -> List[dict]:
    """Get all devices of a given type."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM devices WHERE device_type = ? ORDER BY name",
        (device_type.upper(),)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_devices_by_room(room: str) -> List[dict]:
    """Get all devices in a given room."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM devices WHERE room = ? ORDER BY name",
        (room,)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_devices_by_protocol(protocol: str) -> List[dict]:
    """Get all devices using a given protocol."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM devices WHERE protocol = ? ORDER BY name",
        (protocol.lower(),)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def delete_device(device_id: str) -> bool:
    """Delete a device from the registry."""
    with _transaction() as conn:
        cursor = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return cursor.rowcount > 0


def update_device_state(device_id: str, state: dict) -> bool:
    """Update a device's state and record it in history."""
    now = time.time()
    with _transaction() as conn:
        # Update current state
        cursor = conn.execute(
            "UPDATE devices SET state = ?, last_seen = ?, is_online = 1, updated_at = ? WHERE id = ?",
            (json.dumps(state), now, datetime.now(timezone.utc).isoformat(), device_id)
        )
        if cursor.rowcount == 0:
            return False

        # Record in state history
        conn.execute(
            "INSERT INTO state_history (device_id, state, timestamp) VALUES (?, ?, ?)",
            (device_id, json.dumps(state), now)
        )
    return True


# ── Command Dispatch ─────────────────────────────────────────


def log_command(
    device_id: str,
    action: str,
    params: dict = None,
    status: str = "pending",
    result: dict = None,
    latency_ms: float = 0,
    error: str = "",
    initiated_by: str = "user",
) -> int:
    """Log a command execution attempt. Returns the command log ID."""
    now = time.time()
    with _transaction() as conn:
        cursor = conn.execute("""
            INSERT INTO command_log (device_id, action, params, status, result,
                latency_ms, error, initiated_by, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, action, json.dumps(params or {}),
            status, json.dumps(result or {}),
            latency_ms, error, initiated_by, now
        ))
        return cursor.lastrowid


def update_command_status(
    log_id: int,
    status: str,
    result: dict = None,
    latency_ms: float = 0,
    error: str = "",
):
    """Update the status of a logged command."""
    with _transaction() as conn:
        conn.execute("""
            UPDATE command_log SET status = ?, result = ?, latency_ms = ?, error = ?
            WHERE id = ?
        """, (status, json.dumps(result or {}), latency_ms, error, log_id))


def get_command_history(device_id: str = None, limit: int = 50) -> List[dict]:
    """Get recent command history, optionally filtered by device."""
    conn = _get_conn()
    if device_id:
        rows = conn.execute(
            "SELECT * FROM command_log WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?",
            (device_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM command_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_command_stats() -> dict:
    """Get command execution statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM command_log").fetchone()["c"]
    success = conn.execute("SELECT COUNT(*) as c FROM command_log WHERE status = 'success'").fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) as c FROM command_log WHERE status = 'error'").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM command_log WHERE status = 'pending'").fetchone()["c"]
    avg_latency = conn.execute("SELECT AVG(latency_ms) as avg FROM command_log WHERE status = 'success'").fetchone()["avg"] or 0
    recent = conn.execute("SELECT * FROM command_log ORDER BY timestamp DESC LIMIT 10").fetchall()
    conn.close()

    return {
        "total_commands": total,
        "successful": success,
        "failed": failed,
        "pending": pending,
        "success_rate": round(success / max(total, 1) * 100, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "recent_commands": [_row_to_dict(r) for r in recent],
    }


# ── Scenes ──────────────────────────────────────────────────


def create_scene(name: str, icon: str = "🎬", device_states: list = None) -> dict:
    """Create a new scene."""
    scene_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    with _transaction() as conn:
        conn.execute("""
            INSERT INTO device_scenes (id, name, icon, device_states, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (scene_id, name, icon, json.dumps(device_states or []), now))
    return {"id": scene_id, "name": name, "icon": icon, "device_states": device_states or []}


def get_all_scenes() -> List[dict]:
    """Get all saved scenes."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM device_scenes ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def activate_scene(scene_id: str) -> Optional[dict]:
    """Activate a scene and return the list of commands to execute."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM device_scenes WHERE id = ?", (scene_id,)).fetchone()
    conn.close()
    if not row:
        return None

    scene = _row_to_dict(row)
    device_states = json.loads(scene.get("device_states", "[]"))

    # Mark as active
    with _transaction() as conn:
        conn.execute("UPDATE device_scenes SET is_active = 1 WHERE id = ?", (scene_id,))

    return {
        "scene_id": scene_id,
        "name": scene["name"],
        "commands": device_states,
    }


def delete_scene(scene_id: str) -> bool:
    """Delete a scene."""
    with _transaction() as conn:
        cursor = conn.execute("DELETE FROM device_scenes WHERE id = ?", (scene_id,))
        return cursor.rowcount > 0


# ── State History ───────────────────────────────────────────


def get_state_history(device_id: str, hours: int = 24, limit: int = 100) -> List[dict]:
    """Get state change history for a device."""
    conn = _get_conn()
    cutoff = time.time() - (hours * 3600)
    rows = conn.execute(
        "SELECT * FROM state_history WHERE device_id = ? AND timestamp > ? ORDER BY timestamp DESC LIMIT ?",
        (device_id, cutoff, limit)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ── Telemetry Dashboard ─────────────────────────────────────


def get_dashboard() -> dict:
    """Get a comprehensive dashboard of all device telemetry."""
    conn = _get_conn()

    total = conn.execute("SELECT COUNT(*) as c FROM devices").fetchone()["c"]
    online = conn.execute("SELECT COUNT(*) as c FROM devices WHERE is_online = 1").fetchone()["c"]
    offline = total - online

    type_dist = conn.execute(
        "SELECT device_type, COUNT(*) as c FROM devices GROUP BY device_type"
    ).fetchall()

    room_dist = conn.execute(
        "SELECT room, COUNT(*) as c FROM devices GROUP BY room"
    ).fetchall()

    proto_dist = conn.execute(
        "SELECT protocol, COUNT(*) as c FROM devices GROUP BY protocol"
    ).fetchall()

    recent_cmds = conn.execute(
        "SELECT * FROM command_log ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()

    total_cmds = conn.execute("SELECT COUNT(*) as c FROM command_log").fetchone()["c"]
    success_cmds = conn.execute(
        "SELECT COUNT(*) as c FROM command_log WHERE status = 'success'"
    ).fetchone()["c"]
    avg_latency = conn.execute(
        "SELECT AVG(latency_ms) as avg FROM command_log WHERE status = 'success'"
    ).fetchone()["avg"] or 0

    conn.close()

    return {
        "devices": {
            "total": total,
            "online": online,
            "offline": offline,
        },
        "by_type": {r["device_type"]: r["c"] for r in type_dist},
        "by_room": {r["room"]: r["c"] for r in room_dist},
        "by_protocol": {r["protocol"]: r["c"] for r in proto_dist},
        "commands": {
            "total": total_cmds,
            "successful": success_cmds,
            "success_rate": round(success_cmds / max(total_cmds, 1) * 100, 1),
            "avg_latency_ms": round(avg_latency, 1),
        },
        "recent_commands": [_row_to_dict(r) for r in recent_cmds],
    }


# ── Helpers ─────────────────────────────────────────────────


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a SQLite Row to a dictionary, parsing JSON fields."""
    d = dict(row)
    for key in ("state", "actions", "capabilities", "device_states", "params", "result"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
    return d


# ── Stats ───────────────────────────────────────────────────


def get_stats() -> dict:
    """Get overall device manager statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM devices").fetchone()["c"]
    online = conn.execute("SELECT COUNT(*) as c FROM devices WHERE is_online = 1").fetchone()["c"]
    total_cmds = conn.execute("SELECT COUNT(*) as c FROM command_log").fetchone()["c"]
    total_states = conn.execute("SELECT COUNT(*) as c FROM state_history").fetchone()["c"]
    total_scenes = conn.execute("SELECT COUNT(*) as c FROM device_scenes").fetchone()["c"]
    conn.close()

    return {
        "total_devices": total,
        "online_devices": online,
        "offline_devices": total - online,
        "total_commands": total_cmds,
        "total_state_records": total_states,
        "total_scenes": total_scenes,
    }
