"""Multi-Device Orchestration — device mesh, cross-device coordination, command relay, failover."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parent / "jarvis_devices.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    platform TEXT,
    ip_address TEXT,
    mac_address TEXT,
    capabilities TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'offline',
    health_score REAL NOT NULL DEFAULT 1.0,
    last_seen TEXT,
    last_heartbeat TEXT,
    zone TEXT DEFAULT 'default',
    tags TEXT NOT NULL DEFAULT '[]',
    relay_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS device_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    device_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS command_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    target_device_id TEXT,
    target_group_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    relay_id TEXT,
    latency_ms REAL,
    retries INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    device_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status, zone);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(type, status);
CREATE INDEX IF NOT EXISTS idx_command_log_target ON command_log(target_device_id, created_at);
CREATE INDEX IF NOT EXISTS idx_command_log_status ON command_log(status, created_at);
"""


class DeviceMesh:
    """Multi-device orchestration with mesh networking, failover, and cross-device coordination."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or _DB_PATH)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-32000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.executescript(_SCHEMA)
        conn.commit()
        self._conn = conn
        return conn

    def register_device(
        self,
        name: str,
        type: str,
        platform: str = "unknown",
        ip_address: str = "",
        mac_address: str = "",
        capabilities: Optional[List[str]] = None,
        zone: str = "default",
        tags: Optional[List[str]] = None,
        relay_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Register a new device or update existing one."""
        device_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO devices (id, name, type, platform, ip_address, mac_address,
                    capabilities, status, zone, tags, relay_id, metadata, last_seen, last_heartbeat, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        device_id, name, type, platform, ip_address, mac_address,
                        json.dumps(capabilities or []), zone, json.dumps(tags or []),
                        relay_id, json.dumps(metadata or {}), now, now, now, now,
                    ),
                )
                return {"id": device_id, "name": name, "type": type, "status": "online"}

    def update_device_status(self, device_id: str, status: str, health_score: Optional[float] = None, metadata: Optional[Dict] = None) -> bool:
        """Update device status and heartbeat."""
        with self._lock:
            with self._conn:
                now = datetime.utcnow().isoformat()
                sets = ["status = ?", "last_heartbeat = ?", "updated_at = ?"]
                params: list = [status, now, now]
                if health_score is not None:
                    sets.append("health_score = ?")
                    params.append(health_score)
                if metadata:
                    sets.append("metadata = ?")
                    params.append(json.dumps(metadata))
                if status == "online":
                    sets.append("last_seen = ?")
                    params.append(now)
                params.append(device_id)
                self._conn.execute(f"UPDATE devices SET {', '.join(sets)} WHERE id = ?", params)
                return True

    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get full device info."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
            return dict(row) if row else None

    def get_all_devices(self, status: Optional[str] = None, zone: Optional[str] = None, type: Optional[str] = None) -> List[Dict]:
        """Get all devices with optional filters."""
        with self._lock:
            query = "SELECT * FROM devices WHERE 1=1"
            params: list = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if zone:
                query += " AND zone = ?"
                params.append(zone)
            if type:
                query += " AND type = ?"
                params.append(type)
            query += " ORDER BY health_score DESC, name"
            rows = self._conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_mesh_topology(self) -> Dict:
        """Get the full device mesh topology for visualization."""
        devices = self.get_all_devices()
        zones = self.get_all_zones()

        nodes = []
        edges = []
        for d in devices:
            nodes.append({
                "id": d["id"],
                "label": d["name"],
                "type": d["type"],
                "status": d["status"],
                "health": d["health_score"],
                "zone": d["zone"],
                "capabilities": json.loads(d["capabilities"]) if isinstance(d["capabilities"], str) else d["capabilities"],
            })
            if d.get("relay_id"):
                edges.append({"from": d["relay_id"], "to": d["id"], "type": "relay"})

        for z in zones:
            device_ids = json.loads(z["device_ids"]) if isinstance(z["device_ids"], str) else z["device_ids"]
            for i in range(len(device_ids)):
                for j in range(i + 1, len(device_ids)):
                    edges.append({"from": device_ids[i], "to": device_ids[j], "type": "zone"})

        return {
            "nodes": nodes,
            "edges": edges,
            "zones": [dict(z) for z in zones],
            "stats": {
                "total_devices": len(devices),
                "online": sum(1 for d in devices if d["status"] == "online"),
                "offline": sum(1 for d in devices if d["status"] == "offline"),
                "degraded": sum(1 for d in devices if d["status"] == "degraded"),
                "avg_health": round(sum(d["health_score"] for d in devices) / max(len(devices), 1), 3),
            },
        }

    def send_command(
        self,
        command: str,
        target_device_id: Optional[str] = None,
        target_group_id: Optional[str] = None,
        retries: int = 2,
    ) -> Dict:
        """Send a command to a device or group with failover and retry."""
        command_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        start_time = time.monotonic()

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO command_log (id, command, target_device_id, target_group_id, status, retries, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                    (command_id, command, target_device_id, target_group_id, retries, now),
                )

        target_devices = []
        if target_device_id:
            d = self.get_device(target_device_id)
            if d:
                target_devices = [d]
        elif target_group_id:
            group = self.get_group(target_group_id)
            if group:
                target_devices = [self.get_device(did) for did in group.get("device_ids", []) if self.get_device(did)]

        results = []
        for device in target_devices:
            device_result = self._execute_on_device(device, command, retries)
            results.append(device_result)

        latency_ms = (time.monotonic() - start_time) * 1000
        overall_status = "success" if all(r.get("success") for r in results) else "partial" if results else "no_device"

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """UPDATE command_log SET status = ?, result = ?, latency_ms = ?, completed_at = ?
                    WHERE id = ?""",
                    (overall_status, json.dumps(results), latency_ms, datetime.utcnow().isoformat(), command_id),
                )

        return {
            "command_id": command_id,
            "status": overall_status,
            "results": results,
            "latency_ms": round(latency_ms, 1),
            "retries_used": retries,
        }

    def _execute_on_device(self, device: Dict, command: str, retries: int) -> Dict:
        """Execute a command on a specific device via relay with retry logic."""
        import urllib.request
        import urllib.error
        import json as _json

        if device["status"] != "online":
            return {"device_id": device["id"], "success": False, "error": "device_offline"}

        relay_id = device.get("relay_id")
        if not relay_id:
            return {"device_id": device["id"], "success": False, "error": "no_relay"}

        relay_url = os.environ.get("JARVIS_RELAY_URL", "http://127.0.0.1:8765")
        payload = _json.dumps({
            "type": "device_command",
            "device_id": device["id"],
            "device_name": device["name"],
            "relay_id": relay_id,
            "command": command,
            "timestamp": datetime.utcnow().isoformat(),
        }).encode("utf-8")

        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(
                    f"{relay_url}/relay/command",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result_data = _json.loads(resp.read().decode())
                    return {
                        "device_id": device["id"],
                        "device_name": device["name"],
                        "relay_id": relay_id,
                        "success": result_data.get("success", True),
                        "attempt": attempt + 1,
                        "command": command,
                        "response": result_data,
                    }
            except urllib.error.URLError as e:
                if attempt == retries:
                    return {"device_id": device["id"], "success": False, "error": f"relay_unreachable: {e.reason}", "attempts": attempt + 1}
                time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                if attempt == retries:
                    return {"device_id": device["id"], "success": False, "error": str(e), "attempts": attempt + 1}
                time.sleep(0.5 * (attempt + 1))
        return {"device_id": device["id"], "success": False, "error": "max_retries"}

    def broadcast_command(self, command: str, zone: Optional[str] = None, device_type: Optional[str] = None) -> Dict:
        """Broadcast a command to all matching devices."""
        devices = self.get_all_devices(status="online", zone=zone, type=device_type)
        results = []
        for device in devices:
            result = self._execute_on_device(device, command, retries=1)
            results.append(result)

        return {
            "broadcast": True,
            "target_count": len(devices),
            "results": results,
            "success_count": sum(1 for r in results if r.get("success")),
            "fail_count": sum(1 for r in results if not r.get("success")),
        }

    def create_group(self, name: str, description: str = "", device_ids: Optional[List[str]] = None) -> Dict:
        """Create a device group."""
        group_id = str(uuid.uuid4())[:12]
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO device_groups (id, name, description, device_ids) VALUES (?, ?, ?, ?)",
                    (group_id, name, description, json.dumps(device_ids or [])),
                )
                return {"id": group_id, "name": name, "device_ids": device_ids or []}

    def get_group(self, group_id: str) -> Optional[Dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM device_groups WHERE id = ?", (group_id,)).fetchone()
            return dict(row) if row else None

    def get_all_groups(self) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM device_groups ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def create_zone(self, name: str, description: str = "", device_ids: Optional[List[str]] = None) -> Dict:
        """Create a physical zone (room, floor, building)."""
        zone_id = str(uuid.uuid4())[:12]
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO zones (id, name, description, device_ids) VALUES (?, ?, ?, ?)",
                    (zone_id, name, description, json.dumps(device_ids or [])),
                )
                return {"id": zone_id, "name": name, "device_ids": device_ids or []}

    def get_all_zones(self) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM zones ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def get_command_history(self, limit: int = 50, device_id: Optional[str] = None) -> List[Dict]:
        """Get recent command execution history."""
        with self._lock:
            if device_id:
                rows = self._conn.execute(
                    "SELECT * FROM command_log WHERE target_device_id = ? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM command_log ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_mesh_stats(self) -> Dict:
        """Get aggregate mesh statistics."""
        with self._lock:
            devices = self._conn.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='online' THEN 1 ELSE 0 END) as online,
                    SUM(CASE WHEN status='offline' THEN 1 ELSE 0 END) as offline,
                    AVG(health_score) as avg_health
                FROM devices"""
            ).fetchone()

            commands = self._conn.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                    AVG(latency_ms) as avg_latency
                FROM command_log"""
            ).fetchone()

            return {
                "devices": {
                    "total": devices["total"],
                    "online": devices["online"],
                    "offline": devices["offline"],
                    "avg_health": round(devices["avg_health"], 3) if devices["avg_health"] else 1.0,
                },
                "commands": {
                    "total": commands["total"],
                    "success": commands["success"],
                    "success_rate": round(commands["success"] / max(commands["total"], 1) * 100, 1),
                    "avg_latency_ms": round(commands["avg_latency"], 1) if commands["avg_latency"] else 0,
                },
                "zones": len(self.get_all_zones()),
                "groups": len(self.get_all_groups()),
            }


_engine: Optional[DeviceMesh] = None


def get_device_mesh() -> DeviceMesh:
    global _engine
    if _engine is None:
        _engine = DeviceMesh()
    return _engine
