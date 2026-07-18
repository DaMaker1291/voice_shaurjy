"""Autonomous Workflow Engine — event-driven triggers, autonomous actions, feedback loops."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parent / "jarvis_workflows.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    trigger_type TEXT NOT NULL,
    trigger_config TEXT NOT NULL DEFAULT '{}',
    actions TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active',
    priority INTEGER NOT NULL DEFAULT 5,
    last_run TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms REAL NOT NULL DEFAULT 0,
    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
    max_retries INTEGER NOT NULL DEFAULT 3,
    owner TEXT DEFAULT 'local',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    trigger_event TEXT,
    actions_executed INTEGER NOT NULL DEFAULT 0,
    actions_succeeded INTEGER NOT NULL DEFAULT 0,
    actions_failed INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0,
    error TEXT,
    result TEXT DEFAULT '{}',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    severity TEXT NOT NULL DEFAULT 'info',
    processed INTEGER NOT NULL DEFAULT 0,
    workflow_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    run_id TEXT,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_wf ON workflow_runs(workflow_id, started_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, processed, created_at);
"""

_DEFAULT_WORKFLOWS = [
    {
        "name": "System Health Monitor",
        "description": "Continuously monitor system health and alert on anomalies",
        "trigger_type": "periodic",
        "trigger_config": {"interval_seconds": 300},
        "actions": [
            {"type": "check_cpu", "threshold": 90},
            {"type": "check_memory", "threshold": 85},
            {"type": "check_disk", "threshold": 90},
            {"type": "alert_if_anomaly", "channel": "notification"},
        ],
        "priority": 8,
    },
    {
        "name": "Device Auto-Discovery",
        "description": "Scan network for new devices every hour",
        "trigger_type": "periodic",
        "trigger_config": {"interval_seconds": 3600},
        "actions": [
            {"type": "network_scan", "range": "auto"},
            {"type": "register_new_devices"},
            {"type": "notify_if_new", "message": "New device detected on network"},
        ],
        "priority": 5,
    },
    {
        "name": "Conversation Summarizer",
        "description": "Summarize daily conversations and store in memory",
        "trigger_type": "schedule",
        "trigger_config": {"cron": "0 23 * * *"},
        "actions": [
            {"type": "collect_today_conversations"},
            {"type": "summarize", "model": "groq"},
            {"type": "store_summary", "target": "graph_memory"},
        ],
        "priority": 3,
    },
    {
        "name": "Memory Consolidation",
        "description": "Consolidate and optimize graph memory periodically",
        "trigger_type": "periodic",
        "trigger_config": {"interval_seconds": 86400},
        "actions": [
            {"type": "consolidate_graph_memory"},
            {"type": "prune_stale_nodes", "max_age_days": 90},
            {"type": "update_embeddings"},
        ],
        "priority": 2,
    },
    {
        "name": "Security Audit",
        "description": "Run security audit and verify compliance chain",
        "trigger_type": "periodic",
        "trigger_config": {"interval_seconds": 3600},
        "actions": [
            {"type": "verify_audit_chain"},
            {"type": "check_permissions"},
            {"type": "scan_for_anomalies"},
            {"type": "log_security_report"},
        ],
        "priority": 9,
    },
    {
        "name": "Smart Home Automation",
        "description": "React to device state changes and automate responses",
        "trigger_type": "event",
        "trigger_config": {"event_types": ["device_state_change", "time_schedule", "presence_detection"]},
        "actions": [
            {"type": "evaluate_rules", "rules_file": "automation_rules.json"},
            {"type": "execute_device_commands"},
            {"type": "log_automation"},
        ],
        "priority": 7,
    },
    {
        "name": "Proactive Insight Generator",
        "description": "Generate proactive insights from accumulated data",
        "trigger_type": "periodic",
        "trigger_config": {"interval_seconds": 7200},
        "actions": [
            {"type": "analyze_patterns"},
            {"type": "generate_insights", "model": "groq"},
            {"type": "surface_proactive_messages"},
        ],
        "priority": 4,
    },
    {
        "name": "Learning Feedback Loop",
        "description": "Use interaction feedback to improve agent strategies",
        "trigger_type": "event",
        "trigger_config": {"event_types": ["interaction_complete", "user_feedback"]},
        "actions": [
            {"type": "analyze_interaction_outcome"},
            {"type": "update_strategy_metrics"},
            {"type": "evolve_if_needed", "threshold": 0.3},
        ],
        "priority": 6,
    },
]


class AutonomousEngine:
    """Event-driven autonomous workflow engine with feedback loops and self-optimization."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or _DB_PATH)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._action_handlers: Dict[str, Callable] = {}
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._connect()
        self._register_default_handlers()

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
        self._seed_workflows()
        return conn

    def _seed_workflows(self) -> None:
        with self._lock:
            with self._conn:
                for wf in _DEFAULT_WORKFLOWS:
                    existing = self._conn.execute("SELECT id FROM workflows WHERE name = ?", (wf["name"],)).fetchone()
                    if not existing:
                        wf_id = str(uuid.uuid4())[:12]
                        self._conn.execute(
                            """INSERT INTO workflows (id, name, description, trigger_type, trigger_config, actions, priority)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (wf_id, wf["name"], wf["description"], wf["trigger_type"],
                             json.dumps(wf["trigger_config"]), json.dumps(wf["actions"]), wf["priority"]),
                        )

    def _register_default_handlers(self) -> None:
        """Register built-in action handlers."""
        self._action_handlers = {
            "check_cpu": self._handle_check_cpu,
            "check_memory": self._handle_check_memory,
            "check_disk": self._handle_check_disk,
            "network_scan": self._handle_network_scan,
            "alert_if_anomaly": self._handle_alert,
            "log_automation": self._handle_log,
        }

    def register_handler(self, action_type: str, handler: Callable) -> None:
        self._action_handlers[action_type] = handler

    def create_workflow(
        self,
        name: str,
        description: str = "",
        trigger_type: str = "manual",
        trigger_config: Optional[Dict] = None,
        actions: Optional[List[Dict]] = None,
        priority: int = 5,
        cooldown_seconds: int = 300,
        max_retries: int = 3,
    ) -> Dict:
        """Create a new autonomous workflow."""
        wf_id = str(uuid.uuid4())[:12]
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO workflows (id, name, description, trigger_type, trigger_config,
                    actions, priority, cooldown_seconds, max_retries)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (wf_id, name, description, trigger_type,
                     json.dumps(trigger_config or {}), json.dumps(actions or []),
                     priority, cooldown_seconds, max_retries),
                )
                return {"id": wf_id, "name": name, "status": "active"}

    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
            return dict(row) if row else None

    def get_all_workflows(self, status: Optional[str] = None) -> List[Dict]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM workflows WHERE status = ? ORDER BY priority DESC", (status,)
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM workflows ORDER BY priority DESC").fetchall()
            return [dict(r) for r in rows]

    def update_workflow(self, workflow_id: str, **kwargs) -> bool:
        with self._lock:
            with self._conn:
                sets = []
                params: list = []
                for key, val in kwargs.items():
                    if key in ("name", "description", "trigger_type", "status", "priority", "cooldown_seconds", "max_retries"):
                        sets.append(f"{key} = ?")
                        params.append(val)
                    elif key in ("trigger_config", "actions"):
                        sets.append(f"{key} = ?")
                        params.append(json.dumps(val))
                if not sets:
                    return False
                sets.append("updated_at = datetime('now')")
                params.append(workflow_id)
                self._conn.execute(f"UPDATE workflows SET {', '.join(sets)} WHERE id = ?", params)
                return True

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
                return True

    def emit_event(self, event_type: str, source: str, payload: Optional[Dict] = None, severity: str = "info") -> int:
        """Emit an event that can trigger workflows."""
        with self._lock:
            with self._conn:
                cursor = self._conn.execute(
                    "INSERT INTO events (event_type, source, payload, severity) VALUES (?, ?, ?, ?)",
                    (event_type, source, json.dumps(payload or {}), severity),
                )
                return cursor.lastrowid or 0

    def run_workflow(self, workflow_id: str, trigger_event: Optional[Dict] = None) -> Dict:
        """Execute a workflow immediately."""
        wf = self.get_workflow(workflow_id)
        if not wf:
            return {"error": "workflow_not_found"}
        if wf["status"] != "active":
            return {"error": "workflow_inactive"}

        run_id = str(uuid.uuid4())[:12]
        actions = json.loads(wf["actions"]) if isinstance(wf["actions"], str) else wf["actions"]
        now = datetime.utcnow().isoformat()

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO workflow_runs (id, workflow_id, status, trigger_event, started_at)
                    VALUES (?, ?, 'running', ?, ?)""",
                    (run_id, workflow_id, json.dumps(trigger_event or {}), now),
                )

        start_time = time.monotonic()
        succeeded = 0
        failed = 0
        errors = []

        for action in actions:
            action_type = action.get("type", "unknown")
            handler = self._action_handlers.get(action_type)
            if handler:
                try:
                    result = handler(action, workflow_id)
                    if result.get("success", True):
                        succeeded += 1
                    else:
                        failed += 1
                        errors.append(result.get("error", "unknown"))
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
            else:
                failed += 1
                errors.append(f"no_handler:{action_type}")

        latency_ms = (time.monotonic() - start_time) * 1000
        status = "success" if failed == 0 else "partial" if succeeded > 0 else "failed"

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """UPDATE workflow_runs SET status = ?, actions_executed = ?,
                    actions_succeeded = ?, actions_failed = ?, latency_ms = ?,
                    error = ?, completed_at = datetime('now')
                    WHERE id = ?""",
                    (status, len(actions), succeeded, failed, latency_ms,
                     json.dumps(errors) if errors else None, run_id),
                )

                self._conn.execute(
                    """UPDATE workflows SET last_run = datetime('now'), run_count = run_count + 1,
                    success_count = success_count + ?, failure_count = failure_count + ?,
                    avg_latency_ms = (avg_latency_ms * (run_count) + ?) / (run_count + 1),
                    updated_at = datetime('now')
                    WHERE id = ?""",
                    (succeeded, failed, latency_ms, workflow_id),
                )

        return {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "workflow_name": wf["name"],
            "status": status,
            "actions_executed": len(actions),
            "actions_succeeded": succeeded,
            "actions_failed": failed,
            "latency_ms": round(latency_ms, 1),
            "errors": errors,
        }

    def get_workflow_runs(self, workflow_id: str, limit: int = 20) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY started_at DESC LIMIT ?",
                (workflow_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        with self._lock:
            if event_type:
                rows = self._conn.execute(
                    "SELECT * FROM events WHERE event_type = ? ORDER BY created_at DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def add_feedback(self, workflow_id: str, run_id: Optional[str], rating: int, comment: str = "") -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO feedback (workflow_id, run_id, rating, comment) VALUES (?, ?, ?, ?)",
                    (workflow_id, run_id, rating, comment),
                )

    def get_feedback_stats(self, workflow_id: str) -> Dict:
        with self._lock:
            row = self._conn.execute(
                """SELECT AVG(rating) as avg_rating, COUNT(*) as total, MIN(rating) as min_rating, MAX(rating) as max_rating
                FROM feedback WHERE workflow_id = ?""",
                (workflow_id,),
            ).fetchone()
            return {
                "avg_rating": round(row["avg_rating"], 2) if row["avg_rating"] else 0,
                "total_ratings": row["total"],
                "min_rating": row["min_rating"],
                "max_rating": row["max_rating"],
            }

    def get_engine_stats(self) -> Dict:
        """Get aggregate engine statistics."""
        with self._lock:
            wfs = self._conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active FROM workflows").fetchone()
            runs = self._conn.execute(
                """SELECT COUNT(*) as total, SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                AVG(latency_ms) as avg_latency FROM workflow_runs"""
            ).fetchone()
            events = self._conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN processed=0 THEN 1 ELSE 0 END) as pending FROM events").fetchone()
            feedback = self._conn.execute("SELECT AVG(rating) as avg_rating FROM feedback").fetchone()

            return {
                "workflows": {"total": wfs["total"], "active": wfs["active"]},
                "runs": {
                    "total": runs["total"],
                    "success": runs["success"],
                    "success_rate": round(runs["success"] / max(runs["total"], 1) * 100, 1),
                    "avg_latency_ms": round(runs["avg_latency"], 1) if runs["avg_latency"] else 0,
                },
                "events": {"total": events["total"], "pending": events["pending"]},
                "feedback": {"avg_rating": round(feedback["avg_rating"], 2) if feedback["avg_rating"] else 0},
            }

    # --- Built-in action handlers ---

    def _handle_check_cpu(self, action: Dict, workflow_id: str) -> Dict:
        import psutil
        threshold = action.get("threshold", 90)
        cpu = psutil.cpu_percent(interval=1)
        if cpu > threshold:
            return {"success": False, "error": f"CPU at {cpu}% (threshold: {threshold}%)", "value": cpu}
        return {"success": True, "value": cpu}

    def _handle_check_memory(self, action: Dict, workflow_id: str) -> Dict:
        import psutil
        threshold = action.get("threshold", 85)
        mem = psutil.virtual_memory()
        if mem.percent > threshold:
            return {"success": False, "error": f"Memory at {mem.percent}% (threshold: {threshold}%)", "value": mem.percent}
        return {"success": True, "value": mem.percent}

    def _handle_check_disk(self, action: Dict, workflow_id: str) -> Dict:
        import psutil
        threshold = action.get("threshold", 90)
        disk = psutil.disk_usage("/")
        if disk.percent > threshold:
            return {"success": False, "error": f"Disk at {disk.percent}% (threshold: {threshold}%)", "value": disk.percent}
        return {"success": True, "value": disk.percent}

    def _handle_network_scan(self, action: Dict, workflow_id: str) -> Dict:
        return {"success": True, "scanned": True}

    def _handle_alert(self, action: Dict, workflow_id: str) -> Dict:
        return {"success": True, "alerted": True}

    def _handle_log(self, action: Dict, workflow_id: str) -> Dict:
        return {"success": True, "logged": True}


_engine: Optional[AutonomousEngine] = None


def get_autonomous_engine() -> AutonomousEngine:
    global _engine
    if _engine is None:
        _engine = AutonomousEngine()
    return _engine
