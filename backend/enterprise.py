"""Enterprise Layer — multi-user auth, RBAC, team workspaces, compliance dashboard."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parent / "jarvis_enterprise.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'viewer',
    team_id TEXT,
    avatar_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_admin INTEGER NOT NULL DEFAULT 0,
    last_login TEXT,
    login_count INTEGER NOT NULL DEFAULT 0,
    api_key TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner_id TEXT NOT NULL,
    member_ids TEXT NOT NULL DEFAULT '[]',
    settings TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details TEXT DEFAULT '{}',
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_team ON users(team_id, is_active);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token, expires_at);
"""

_ROLES = {
    "admin": {"permissions": ["*"], "description": "Full system access"},
    "editor": {"permissions": ["read", "write", "execute", "deploy"], "description": "Can modify and deploy"},
    "operator": {"permissions": ["read", "execute"], "description": "Can run workflows and commands"},
    "viewer": {"permissions": ["read"], "description": "Read-only access"},
}


class EnterpriseEngine:
    """Multi-user authentication, RBAC, team workspaces, and compliance dashboard."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or _DB_PATH)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_default_admin()

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

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()

    def _hash_password_fast(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 10000).hex()

    def _verify_password(self, password: str, salt: str, stored_hash: str) -> bool:
        """Verify password against stored hash, supporting both old and new iteration counts."""
        if self._hash_password_fast(password, salt) == stored_hash:
            return True
        return self._hash_password(password, salt) == stored_hash

    def _create_default_admin(self) -> None:
        with self._lock:
            existing = self._conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            if not existing:
                salt = secrets.token_hex(16)
                admin_id = str(uuid.uuid4())[:12]
                api_key = f"jarvis_{secrets.token_hex(24)}"
                self._conn.execute(
                    """INSERT INTO users (id, username, email, password_hash, salt, display_name, role, is_admin, api_key)
                    VALUES (?, 'admin', 'admin@jarvis.local', ?, ?, 'Administrator', 'admin', 1, ?)""",
                    (admin_id, self._hash_password_fast("admin", salt), salt, api_key),
                )
                self._conn.commit()

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        role: str = "viewer",
        team_id: Optional[str] = None,
    ) -> Dict:
        """Create a new user account."""
        user_id = str(uuid.uuid4())[:12]
        salt = secrets.token_hex(16)
        api_key = f"jarvis_{secrets.token_hex(24)}"
        with self._lock:
            with self._conn:
                existing = self._conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
                if existing:
                    return {"error": "username_taken"}
                self._conn.execute(
                    """INSERT INTO users (id, username, email, password_hash, salt, display_name, role, team_id, api_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, username, email, self._hash_password(password, salt), salt, display_name, role, team_id, api_key),
                )
                self.audit(user_id, "user_created", "user", user_id, {"username": username, "role": role})
                return {"id": user_id, "username": username, "role": role, "api_key": api_key}

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user and return a session token."""
        with self._lock:
            user = self._conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
            ).fetchone()
            if not user:
                return None
            if self._verify_password(password, user["salt"], user["password_hash"]):
                return None

            token = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
            session_id = str(uuid.uuid4())[:12]

            self._conn.execute(
                "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, user["id"], token, expires),
            )
            self._conn.execute(
                "UPDATE users SET last_login = datetime('now'), login_count = login_count + 1 WHERE id = ?",
                (user["id"],),
            )
            self._conn.commit()
            self.audit(user["id"], "login", "session", session_id)

            return {
                "token": token,
                "user_id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "expires_at": expires,
            }

    def validate_token(self, token: str) -> Optional[Dict]:
        """Validate a session token and return user info."""
        with self._lock:
            session = self._conn.execute(
                """SELECT s.*, u.username, u.role, u.is_admin, u.team_id
                FROM sessions s JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > datetime('now')""",
                (token,),
            ).fetchone()
            if not session:
                return None
            return {
                "user_id": session["user_id"],
                "username": session["username"],
                "role": session["role"],
                "is_admin": bool(session["is_admin"]),
                "team_id": session["team_id"],
            }

    def has_permission(self, user_id: str, permission: str) -> bool:
        """Check if a user has a specific permission."""
        with self._lock:
            user = self._conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                return False
            role_perms = _ROLES.get(user["role"], {}).get("permissions", [])
            return "*" in role_perms or permission in role_perms

    def update_user_role(self, user_id: str, new_role: str, admin_id: str) -> bool:
        """Update a user's role (admin only)."""
        if not self.has_permission(admin_id, "*"):
            return False
        with self._lock:
            with self._conn:
                self._conn.execute("UPDATE users SET role = ?, updated_at = datetime('now') WHERE id = ?", (new_role, user_id))
                self.audit(admin_id, "role_changed", "user", user_id, {"new_role": new_role})
                return True

    def create_team(self, name: str, owner_id: str, description: str = "") -> Dict:
        """Create a team workspace."""
        team_id = str(uuid.uuid4())[:12]
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO teams (id, name, description, owner_id, member_ids) VALUES (?, ?, ?, ?, ?)",
                    (team_id, name, description, owner_id, json.dumps([owner_id])),
                )
                self._conn.execute("UPDATE users SET team_id = ? WHERE id = ?", (team_id, owner_id))
                self.audit(owner_id, "team_created", "team", team_id, {"name": name})
                return {"id": team_id, "name": name, "owner_id": owner_id}

    def add_team_member(self, team_id: str, user_id: str, added_by: str) -> bool:
        with self._lock:
            with self._conn:
                team = self._conn.execute("SELECT member_ids FROM teams WHERE id = ?", (team_id,)).fetchone()
                if not team:
                    return False
                members = json.loads(team["member_ids"])
                if user_id not in members:
                    members.append(user_id)
                    self._conn.execute("UPDATE teams SET member_ids = ?, updated_at = datetime('now') WHERE id = ?", (json.dumps(members), team_id))
                    self._conn.execute("UPDATE users SET team_id = ? WHERE id = ?", (team_id, user_id))
                self.audit(added_by, "team_member_added", "team", team_id, {"user_id": user_id})
                return True

    def get_team(self, team_id: str) -> Optional[Dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
            return dict(row) if row else None

    def get_user_teams(self, user_id: str) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM teams WHERE member_ids LIKE ?", (f'%"{user_id}"%',)).fetchall()
            return [dict(r) for r in rows]

    def audit(self, user_id: str, action: str, resource_type: str = "", resource_id: str = "", details: Optional[Dict] = None, ip_address: str = "", user_agent: str = "") -> None:
        """Log an audit event."""
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, action, resource_type, resource_id, json.dumps(details or {}), ip_address, user_agent),
                )

    def get_audit_log(self, limit: int = 100, user_id: Optional[str] = None, action: Optional[str] = None) -> List[Dict]:
        with self._lock:
            query = "SELECT a.*, u.username FROM audit_log a LEFT JOIN users u ON a.user_id = u.id WHERE 1=1"
            params: list = []
            if user_id:
                query += " AND a.user_id = ?"
                params.append(user_id)
            if action:
                query += " AND a.action = ?"
                params.append(action)
            query += " ORDER BY a.created_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_compliance_dashboard(self) -> Dict:
        """Get enterprise compliance dashboard data."""
        with self._lock:
            users = self._conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active FROM users").fetchone()
            teams = self._conn.execute("SELECT COUNT(*) as total FROM teams").fetchone()
            audit_24h = self._conn.execute(
                "SELECT COUNT(*) as total FROM audit_log WHERE created_at >= datetime('now', '-1 day')"
            ).fetchone()
            audit_7d = self._conn.execute(
                "SELECT COUNT(*) as total FROM audit_log WHERE created_at >= datetime('now', '-7 days')"
            ).fetchone()
            top_actions = self._conn.execute(
                """SELECT action, COUNT(*) as count FROM audit_log
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY action ORDER BY count DESC LIMIT 10"""
            ).fetchall()
            active_sessions = self._conn.execute(
                "SELECT COUNT(*) as total FROM sessions WHERE expires_at > datetime('now')"
            ).fetchone()
            role_dist = self._conn.execute(
                "SELECT role, COUNT(*) as count FROM users WHERE is_active = 1 GROUP BY role"
            ).fetchall()

            return {
                "users": {"total": users["total"], "active": users["active"]},
                "teams": {"total": teams["total"]},
                "audit": {
                    "last_24h": audit_24h["total"],
                    "last_7d": audit_7d["total"],
                    "top_actions": [{"action": r["action"], "count": r["count"]} for r in top_actions],
                },
                "sessions": {"active": active_sessions["total"]},
                "roles": [{"role": r["role"], "count": r["count"]} for r in role_dist],
                "compliance_score": self._calculate_compliance_score(),
            }

    def _calculate_compliance_score(self) -> float:
        """Calculate an overall compliance score (0-100)."""
        score = 100.0
        with self._lock:
            failed_logins = self._conn.execute(
                "SELECT COUNT(*) as c FROM audit_log WHERE action = 'login_failed' AND created_at >= datetime('now', '-24 hours')"
            ).fetchone()
            score -= min(failed_logins["c"] * 2, 20)

            inactive_admins = self._conn.execute(
                "SELECT COUNT(*) as c FROM users WHERE is_admin = 1 AND is_active = 0"
            ).fetchone()
            score -= inactive_admins["c"] * 10

            stale_sessions = self._conn.execute(
                "SELECT COUNT(*) as c FROM sessions WHERE expires_at < datetime('now')"
            ).fetchone()
            score -= min(stale_sessions["c"] * 0.5, 10)

            return max(0, min(100, score))

    def get_all_users(self) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, username, email, display_name, role, team_id, is_active, is_admin, last_login, login_count, created_at FROM users ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]

    def deactivate_user(self, user_id: str, admin_id: str) -> bool:
        if not self.has_permission(admin_id, "*"):
            return False
        with self._lock:
            with self._conn:
                self._conn.execute("UPDATE users SET is_active = 0, updated_at = datetime('now') WHERE id = ?", (user_id,))
                self.audit(admin_id, "user_deactivated", "user", user_id)
                return True


_engine: Optional[EnterpriseEngine] = None


def get_enterprise_engine() -> EnterpriseEngine:
    global _engine
    if _engine is None:
        _engine = EnterpriseEngine()
    return _engine
