"""Self-Improving Agent Engine — tracks outcomes, evolves strategies, measures improvement."""

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

_DB_PATH = Path(__file__).resolve().parent / "jarvis_learning.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'local',
    task_type TEXT NOT NULL,
    input_text TEXT,
    output_text TEXT,
    strategy_id TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0,
    user_feedback INTEGER,
    confidence REAL,
    tokens_used INTEGER DEFAULT 0,
    error_type TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parameters TEXT NOT NULL DEFAULT '{}',
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    total_latency_ms REAL NOT NULL DEFAULT 0,
    avg_confidence REAL NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learning_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS improvement_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT,
    old_value TEXT,
    new_value TEXT,
    impact_score REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_interactions_agent ON interactions(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_interactions_task ON interactions(task_type, success);
CREATE INDEX IF NOT EXISTS idx_strategies_agent ON strategies(agent_id, active);
CREATE INDEX IF NOT EXISTS idx_metrics_agent ON learning_metrics(agent_id, metric_name, created_at);
"""

_DEFAULT_STRATEGIES = {
    "os": [
        {"name": "direct_execute", "description": "Execute OS commands directly", "parameters": {"timeout": 30, "retry": 1}},
        {"name": "sandbox_first", "description": "Run in sandbox first, then promote", "parameters": {"timeout": 60, "sandbox": True}},
        {"name": "explain_then_execute", "description": "Explain what will happen, then execute", "parameters": {"timeout": 30, "explain": True}},
    ],
    "hal": [
        {"name": "parallel_fetch", "description": "Fetch multiple sources in parallel", "parameters": {"concurrency": 5, "timeout": 15}},
        {"name": "sequential_fetch", "description": "Fetch sources one by one for reliability", "parameters": {"concurrency": 1, "timeout": 30}},
        {"name": "cached_priority", "description": "Use cache, fall back to live fetch", "parameters": {"cache_ttl": 300, "timeout": 10}},
    ],
    "web": [
        {"name": "broad_search", "description": "Search multiple engines and merge", "parameters": {"engines": 3, "timeout": 20}},
        {"name": "deep_search", "description": "Deep crawl of top results", "parameters": {"depth": 3, "timeout": 60}},
        {"name": "quick_answer", "description": "Fast single-source answer", "parameters": {"engines": 1, "timeout": 5}},
    ],
    "core": [
        {"name": "full_context", "description": "Use full graph memory context", "parameters": {"max_hops": 3, "timeout": 15}},
        {"name": "minimal_context", "description": "Use only recent context for speed", "parameters": {"max_hops": 1, "timeout": 5}},
        {"name": "semantic_recall", "description": "Use cosine similarity for relevant context", "parameters": {"top_k": 10, "threshold": 0.7}},
    ],
    "device": [
        {"name": "direct_relay", "description": "Send command directly to device", "parameters": {"timeout": 10, "retry": 2}},
        {"name": "broadcast_relay", "description": "Broadcast to all connected devices", "parameters": {"timeout": 15, "all_devices": True}},
    ],
    "monitor": [
        {"name": "continuous_watch", "description": "Monitor continuously with alerts", "parameters": {"interval": 5, "alert_threshold": 0.8}},
        {"name": "polling_watch", "description": "Poll at regular intervals", "parameters": {"interval": 30, "alert_threshold": 0.9}},
    ],
}


class SelfImprovementEngine:
    """Tracks agent interactions, measures outcomes, and evolves strategies for continuous improvement."""

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
        self._seed_strategies()
        return conn

    def _seed_strategies(self) -> None:
        """Initialize default strategies for each agent if none exist."""
        with self._lock:
            with self._conn:
                for agent_id, strats in _DEFAULT_STRATEGIES.items():
                    for s in strats:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO strategies (id, agent_id, name, description, parameters) VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4())[:12], agent_id, s["name"], s["description"], json.dumps(s["parameters"])),
                        )

    def record_interaction(
        self,
        agent_id: str,
        task_type: str,
        input_text: str = "",
        output_text: str = "",
        strategy_id: Optional[str] = None,
        success: bool = True,
        latency_ms: float = 0,
        user_feedback: Optional[int] = None,
        confidence: float = 0.0,
        tokens_used: int = 0,
        error_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Record a single interaction for learning."""
        interaction_id = str(uuid.uuid4())[:16]
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO interactions
                    (id, agent_id, task_type, input_text, output_text, strategy_id,
                     success, latency_ms, user_feedback, confidence, tokens_used, error_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        interaction_id, agent_id, task_type, input_text, output_text,
                        strategy_id, 1 if success else 0, latency_ms,
                        user_feedback, confidence, tokens_used, error_type,
                        json.dumps(metadata or {}),
                    ),
                )
                if strategy_id:
                    self._update_strategy_stats(strategy_id, success, latency_ms, confidence)
                return interaction_id

    def _update_strategy_stats(self, strategy_id: str, success: bool, latency_ms: float, confidence: float) -> None:
        """Update strategy aggregate stats after an interaction."""
        self._conn.execute(
            """UPDATE strategies SET
                success_count = success_count + ?,
                failure_count = failure_count + ?,
                total_latency_ms = total_latency_ms + ?,
                avg_confidence = (avg_confidence * (success_count + failure_count) + ?) / (success_count + failure_count + 1),
                updated_at = datetime('now')
            WHERE id = ?""",
            (1 if success else 0, 0 if success else 1, latency_ms, confidence, strategy_id),
        )

    def get_best_strategy(self, agent_id: str, task_type: Optional[str] = None) -> Optional[Dict]:
        """Return the strategy with the highest success rate and lowest latency."""
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM strategies
                WHERE agent_id = ? AND active = 1
                ORDER BY
                    CASE WHEN (success_count + failure_count) = 0 THEN 0
                         ELSE CAST(success_count AS REAL) / (success_count + failure_count)
                    END DESC,
                    CASE WHEN total_latency_ms = 0 THEN 999999
                         ELSE total_latency_ms / (success_count + failure_count)
                    END ASC
                LIMIT 1""",
                (agent_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_learning_curve(self, agent_id: str, days: int = 30) -> List[Dict]:
        """Get success rate over time for charting improvement."""
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """SELECT
                    date(created_at) as day,
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(latency_ms) as avg_latency,
                    AVG(confidence) as avg_confidence,
                    AVG(CASE WHEN user_feedback IS NOT NULL THEN user_feedback END) as avg_feedback
                FROM interactions
                WHERE agent_id = ? AND created_at >= ?
                GROUP BY date(created_at)
                ORDER BY day""",
                (agent_id, since),
            ).fetchall()
            return [
                {
                    "day": r["day"],
                    "total": r["total"],
                    "successes": r["successes"],
                    "success_rate": round(r["successes"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
                    "avg_latency_ms": round(r["avg_latency"], 1) if r["avg_latency"] else 0,
                    "avg_confidence": round(r["avg_confidence"], 3) if r["avg_confidence"] else 0,
                    "avg_feedback": round(r["avg_feedback"], 2) if r["avg_feedback"] else None,
                }
                for r in rows
            ]

    def get_agent_metrics(self, agent_id: str) -> Dict:
        """Get comprehensive metrics for an agent."""
        with self._lock:
            overall = self._conn.execute(
                """SELECT
                    COUNT(*) as total_interactions,
                    SUM(success) as total_successes,
                    AVG(latency_ms) as avg_latency,
                    AVG(confidence) as avg_confidence,
                    SUM(tokens_used) as total_tokens,
                    COUNT(DISTINCT task_type) as unique_tasks,
                    MIN(created_at) as first_interaction,
                    MAX(created_at) as last_interaction
                FROM interactions WHERE agent_id = ?""",
                (agent_id,),
            ).fetchone()

            by_task = self._conn.execute(
                """SELECT task_type,
                    COUNT(*) as count,
                    SUM(success) as successes,
                    AVG(latency_ms) as avg_latency
                FROM interactions WHERE agent_id = ?
                GROUP BY task_type ORDER BY count DESC""",
                (agent_id,),
            ).fetchall()

            strategies = self._conn.execute(
                """SELECT name, success_count, failure_count, avg_confidence, version
                FROM strategies WHERE agent_id = ? AND active = 1""",
                (agent_id,),
            ).fetchall()

            improvement_rate = self._calculate_improvement_rate(agent_id)

            return {
                "agent_id": agent_id,
                "overall": {
                    "total_interactions": overall["total_interactions"],
                    "total_successes": overall["total_successes"],
                    "success_rate": round(overall["total_successes"] / overall["total_interactions"] * 100, 1) if overall["total_interactions"] > 0 else 0,
                    "avg_latency_ms": round(overall["avg_latency"], 1) if overall["avg_latency"] else 0,
                    "avg_confidence": round(overall["avg_confidence"], 3) if overall["avg_confidence"] else 0,
                    "total_tokens": overall["total_tokens"] or 0,
                    "unique_tasks": overall["unique_tasks"],
                    "first_interaction": overall["first_interaction"],
                    "last_interaction": overall["last_interaction"],
                },
                "by_task": [dict(r) for r in by_task],
                "strategies": [dict(r) for r in strategies],
                "improvement_rate": improvement_rate,
            }

    def _calculate_improvement_rate(self, agent_id: str) -> Dict:
        """Calculate whether the agent is improving over time."""
        with self._lock:
            now = datetime.utcnow()
            recent = self._conn.execute(
                """SELECT AVG(success) as success_rate, AVG(latency_ms) as latency
                FROM interactions WHERE agent_id = ? AND created_at >= ?""",
                (agent_id, (now - timedelta(days=7)).isoformat()),
            ).fetchone()
            older = self._conn.execute(
                """SELECT AVG(success) as success_rate, AVG(latency_ms) as latency
                FROM interactions WHERE agent_id = ? AND created_at < ? AND created_at >= ?""",
                (agent_id, (now - timedelta(days=7)).isoformat(), (now - timedelta(days=30)).isoformat()),
            ).fetchone()

            recent_rate = recent["success_rate"] if recent and recent["success_rate"] is not None else 0
            older_rate = older["success_rate"] if older and older["success_rate"] is not None else 0
            recent_latency = recent["latency"] if recent and recent["latency"] is not None else 0
            older_latency = older["latency"] if older and older["latency"] is not None else 0

            return {
                "recent_7d_success_rate": round(recent_rate * 100, 1),
                "older_23d_success_rate": round(older_rate * 100, 1),
                "success_rate_change": round((recent_rate - older_rate) * 100, 1),
                "recent_7d_avg_latency": round(recent_latency, 1),
                "older_23d_avg_latency": round(older_latency, 1),
                "latency_change": round(recent_latency - older_latency, 1),
                "is_improving": recent_rate >= older_rate and recent_latency <= older_latency,
            }

    def evolve_strategy(self, agent_id: str, strategy_id: str, new_parameters: Dict) -> str:
        """Create a new version of a strategy with updated parameters."""
        with self._lock:
            with self._conn:
                current = self._conn.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
                if not current:
                    raise ValueError(f"Strategy {strategy_id} not found")

                new_id = str(uuid.uuid4())[:12]
                new_version = current["version"] + 1

                self._conn.execute(
                    """INSERT INTO strategies (id, agent_id, name, description, parameters, version, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (new_id, agent_id, current["name"], f"v{new_version} evolved", json.dumps(new_parameters), new_version),
                )

                self._conn.execute("UPDATE strategies SET active = 0 WHERE id = ?", (strategy_id,))

                self._conn.execute(
                    """INSERT INTO improvement_log (agent_id, event_type, description, old_value, new_value, impact_score)
                    VALUES (?, 'strategy_evolved', ?, ?, ?, ?)""",
                    (
                        agent_id,
                        f"Evolved {current['name']} from v{current['version']} to v{new_version}",
                        current["parameters"],
                        json.dumps(new_parameters),
                        0.0,
                    ),
                )
                return new_id

    def log_improvement(self, agent_id: str, event_type: str, description: str, old_value: str = "", new_value: str = "", impact_score: float = 0.0) -> None:
        """Log a manual improvement event."""
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO improvement_log (agent_id, event_type, description, old_value, new_value, impact_score)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (agent_id, event_type, description, old_value, new_value, impact_score),
                )

    def get_improvement_timeline(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """Get chronological improvement events."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM improvement_log WHERE agent_id = ?
                ORDER BY created_at DESC LIMIT ?""",
                (agent_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_leaderboard(self) -> List[Dict]:
        """Get all agents ranked by improvement score."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT
                    agent_id,
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(confidence) as avg_conf,
                    AVG(latency_ms) as avg_lat
                FROM interactions GROUP BY agent_id
                ORDER BY CAST(SUM(success) AS REAL) / COUNT(*) DESC"""
            ).fetchall()
            return [
                {
                    "rank": i + 1,
                    "agent_id": r["agent_id"],
                    "total_interactions": r["total"],
                    "success_rate": round(r["successes"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
                    "avg_confidence": round(r["avg_conf"], 3) if r["avg_conf"] else 0,
                    "avg_latency_ms": round(r["avg_lat"], 1) if r["avg_lat"] else 0,
                }
                for i, r in enumerate(rows)
            ]


_engine: Optional[SelfImprovementEngine] = None


def get_learning_engine() -> SelfImprovementEngine:
    global _engine
    if _engine is None:
        _engine = SelfImprovementEngine()
    return _engine
