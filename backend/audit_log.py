"""Append-only SQLite audit logging for JARVIS operations.

Provides tamper-evident, append-only event storage with concurrent read
support via WAL mode. All audit_events rows are immutable — no UPDATE or
DELETE operations are permitted on that table.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any


class AuditLog:
    """Append-only SQLite audit logger for JARVIS operations.

    Thread-safe: all database access serialises through a per-instance lock.
    The ``audit_events`` table is append-only — no UPDATE/DELETE is executed
    against it at any point, preserving a tamper-evident history.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or os.environ.get(
            "JARVIS_AUDIT_DB", "./jarvis_audit.db"
        )
        self._lock = threading.Lock()
        self._local = threading.local()
        self._init_db()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Return a per-thread connection, enabling WAL mode on first use."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    @contextmanager
    def _cursor(self):
        """Yield a cursor inside a transaction, committing on success."""
        conn = self._get_conn()
        with self._lock:
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables and indexes if they do not already exist."""
        with self._cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   REAL    NOT NULL,
                    event_type  TEXT    NOT NULL,
                    agent_id    TEXT,
                    agent_type  TEXT,
                    action      TEXT    NOT NULL,
                    target      TEXT,
                    details     TEXT,
                    status      TEXT    DEFAULT 'pending',
                    error       TEXT,
                    latency_ms  INTEGER,
                    user_id     TEXT    DEFAULT 'local',
                    session_id  TEXT,
                    metadata    TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_sessions (
                    id            TEXT PRIMARY KEY,
                    started_at    REAL    NOT NULL,
                    ended_at      REAL,
                    user_id       TEXT,
                    total_events  INTEGER DEFAULT 0,
                    summary       TEXT
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp "
                "ON audit_events(timestamp)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type "
                "ON audit_events(event_type)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_agent "
                "ON audit_events(agent_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_status "
                "ON audit_events(status)"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        if d.get("details") is not None:
            try:
                d["details"] = json.loads(d["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        if d.get("metadata") is not None:
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    @staticmethod
    def _now() -> float:
        return time.time()

    # ------------------------------------------------------------------
    # Core logging methods
    # ------------------------------------------------------------------

    def log_event(
        self,
        event_type: str,
        action: str,
        target: str | None = None,
        details: dict | None = None,
        agent_id: str | None = None,
        agent_type: str | None = None,
        status: str = "completed",
        error: str | None = None,
        latency_ms: int | None = None,
        user_id: str = "local",
        session_id: str | None = None,
    ) -> int:
        """Insert an audit event and return its row id.

        Parameters
        ----------
        event_type:
            Category of the event, e.g. ``"agent"``, ``"device"``,
            ``"security"``, ``"system"``.
        action:
            Human-readable description of what happened.
        target:
            Optional target resource (device id, file path, URL, …).
        details:
            Arbitrary JSON-serialisable payload.
        agent_id / agent_type:
            Identity of the JARVIS agent responsible.
        status:
            One of ``"pending"``, ``"completed"``, ``"failed"``.
        error:
            Error message when ``status == "failed"``.
        latency_ms:
            Wall-clock duration of the operation in milliseconds.
        user_id:
            Owning user; defaults to ``"local"``.
        session_id:
            Optionally groups events into a logical session.
        """
        details_json = json.dumps(details) if details is not None else None
        ts = self._now()

        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_events (
                    timestamp, event_type, agent_id, agent_type,
                    action, target, details, status, error,
                    latency_ms, user_id, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_type,
                    agent_id,
                    agent_type,
                    action,
                    target,
                    details_json,
                    status,
                    error,
                    latency_ms,
                    user_id,
                    session_id,
                ),
            )
            event_id: int = cur.lastrowid  # type: ignore[assignment]

        if session_id is not None:
            self._bump_session_event_count(session_id)

        return event_id

    def _bump_session_event_count(self, session_id: str) -> None:
        """Increment the total_events counter for a session."""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE audit_sessions
                SET total_events = total_events + 1
                WHERE id = ?
                """,
                (session_id,),
            )

    # ------------------------------------------------------------------
    # Convenience logging wrappers
    # ------------------------------------------------------------------

    def log_agent_start(
        self,
        agent_id: str,
        agent_type: str,
        action: str,
        user_id: str = "local",
    ) -> int:
        """Log that an agent has begun executing an action.

        Returns the event id so callers can later update the result via
        :meth:`log_agent_complete` or :meth:`log_agent_error`.
        """
        return self.log_event(
            event_type="agent",
            action=action,
            agent_id=agent_id,
            agent_type=agent_type,
            status="pending",
            user_id=user_id,
        )

    def log_agent_complete(
        self,
        event_id: int,
        status: str = "completed",
        result: dict | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Update a previously-created agent event with its final status.

        This is the only mutation allowed on ``audit_events`` and it only
        touches ``status``, ``details``, and ``latency_ms``.
        """
        details_json = json.dumps(result) if result is not None else None
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE audit_events
                SET status = ?, details = COALESCE(?, details),
                    latency_ms = COALESCE(?, latency_ms)
                WHERE id = ?
                """,
                (status, details_json, latency_ms, event_id),
            )

    def log_agent_error(
        self,
        event_id: int,
        error: str,
        stack_trace: str | None = None,
    ) -> None:
        """Record a failure against a previously-created agent event."""
        details = {"stack_trace": stack_trace} if stack_trace else None
        details_json = json.dumps(details) if details else None
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE audit_events
                SET status = 'failed', error = ?,
                    details = COALESCE(?, details)
                WHERE id = ?
                """,
                (error, details_json, event_id),
            )

    def log_device_control(
        self,
        device_id: str,
        protocol: str,
        command: dict,
        result: dict,
        latency_ms: int,
    ) -> int:
        """Log a device-control round-trip (command sent → result received)."""
        return self.log_event(
            event_type="device",
            action=f"control:{protocol}",
            target=device_id,
            details={"command": command, "result": result, "protocol": protocol},
            status="completed",
            latency_ms=latency_ms,
        )

    def log_nl_command(
        self,
        text: str,
        parsed: dict,
        executed: bool,
        device: str | None = None,
    ) -> int:
        """Log a natural-language command and its parsed representation."""
        return self.log_event(
            event_type="nl_command",
            action="parse_and_execute",
            target=device,
            details={"text": text, "parsed": parsed, "executed": executed},
            status="completed" if executed else "failed",
        )

    def log_security_event(
        self,
        event_type: str,
        details: dict,
        severity: str = "info",
    ) -> int:
        """Record a security-relevant occurrence.

        Parameters
        ----------
        event_type:
            E.g. ``"unauthorized_access"``, ``"key_rotated"``,
            ``"rate_limit_hit"``.
        details:
            Arbitrary payload describing the event.
        severity:
            ``"info"``, ``"warning"``, or ``"critical"``.
        """
        return self.log_event(
            event_type="security",
            action=event_type,
            details={**details, "severity": severity},
            status="completed",
        )

    def log_system_event(
        self,
        event_type: str,
        details: dict,
    ) -> int:
        """Record a general system-level occurrence."""
        return self.log_event(
            event_type="system",
            action=event_type,
            details=details,
            status="completed",
        )

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        since: float | None = None,
        until: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return a filtered, paginated list of audit events.

        All filter parameters are optional; ``None`` means "no filter".
        """
        clauses: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        with self._cursor() as cur:
            cur.execute(
                f"SELECT * FROM audit_events{where} "
                "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]  # type: ignore[misc]

    def get_event(self, event_id: int) -> dict[str, Any] | None:
        """Return a single event by id, or ``None`` if not found."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_events WHERE id = ?", (event_id,)
            )
            return self._row_to_dict(cur.fetchone())

    def get_events_by_agent(
        self, agent_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Return the most recent events for a given agent."""
        return self.get_events(limit=limit, agent_id=agent_id)

    def get_events_by_session(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        """Return every event belonging to a session, oldest first."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_events WHERE session_id = ? "
                "ORDER BY timestamp ASC",
                (session_id,),
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]  # type: ignore[misc]

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics across the entire audit log."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM audit_events")
            total = cur.fetchone()["total"]  # type: ignore[index]

            cur.execute(
                "SELECT event_type, COUNT(*) AS cnt "
                "FROM audit_events GROUP BY event_type"
            )
            by_type = {r["event_type"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(
                "SELECT status, COUNT(*) AS cnt "
                "FROM audit_events GROUP BY status"
            )
            by_status = {r["status"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(
                "SELECT AVG(latency_ms) AS avg_latency "
                "FROM audit_events WHERE latency_ms IS NOT NULL"
            )
            avg_row = cur.fetchone()
            avg_latency: float | None = (
                round(avg_row["avg_latency"], 2) if avg_row and avg_row["avg_latency"] else None
            )

            failed = by_status.get("failed", 0)
            error_rate = round(failed / total, 4) if total else 0.0

        return {
            "total_events": total,
            "events_by_type": by_type,
            "events_by_status": by_status,
            "avg_latency_ms": avg_latency,
            "error_rate": error_rate,
        }

    def get_timeline(self, hours: int = 24) -> list[dict[str, Any]]:
        """Return events grouped by hour for the last *hours* hours.

        Each element contains ``hour`` (ISO-8601 string) and ``count``.
        """
        cutoff = self._now() - hours * 3600
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT
                    strftime('%Y-%m-%dT%H:00:00', timestamp, 'unixepoch') AS hour,
                    COUNT(*) AS count
                FROM audit_events
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour ASC
                """,
                (cutoff,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_recent_errors(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent failed events."""
        return self.get_events(limit=limit, status="failed")

    def search_events(
        self, query: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Full-text search across ``action`` and ``details`` columns.

        Uses SQLite ``LIKE`` for portability; a FTS5 virtual table could
        replace this for large datasets.
        """
        pattern = f"%{query}%"
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM audit_events
                WHERE action LIKE ? OR details LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_session(self, user_id: str = "local") -> str:
        """Create a new audit session and return its UUID."""
        session_id = str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_sessions (id, started_at, user_id)
                VALUES (?, ?, ?)
                """,
                (session_id, self._now(), user_id),
            )
        return session_id

    def end_session(
        self, session_id: str, summary: str | None = None
    ) -> None:
        """Mark a session as ended and optionally attach a summary."""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE audit_sessions
                SET ended_at = ?, summary = ?
                WHERE id = ?
                """,
                (self._now(), summary, session_id),
            )

    # ------------------------------------------------------------------
    # Data integrity & export
    # ------------------------------------------------------------------

    def vacuum(self) -> None:
        """Reclaim unused space and optimise the database file.

        This acquires an exclusive lock and may briefly block concurrent
        writers.  Call periodically (e.g. nightly cron).
        """
        conn = self._get_conn()
        with self._lock:
            conn.execute("VACUUM")

    def export_events(
        self,
        format: str = "json",
        filepath: str | None = None,
    ) -> str:
        """Export the full audit log to a file or return as a string.

        Parameters
        ----------
        format:
            ``"json"`` or ``"csv"``.
        filepath:
            Destination path.  When ``None`` the serialised string is
            returned directly.

        Returns
        -------
        str
            The serialised data (always returned, even when *filepath* is
            set, so callers can inspect what was written).
        """
        with self._cursor() as cur:
            cur.execute("SELECT * FROM audit_events ORDER BY timestamp ASC")
            rows = [self._row_to_dict(r) for r in cur.fetchall()]  # type: ignore[misc]

        if format == "csv":
            output = StringIO()
            if rows:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            serialised = output.getvalue()
        else:
            serialised = json.dumps(rows, indent=2, default=str)

        if filepath is not None:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(serialised, encoding="utf-8")

        return serialised


# Module-level singleton ------------------------------------------------
audit = AuditLog()
