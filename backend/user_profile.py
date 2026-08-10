"""
User Profile & Preference Graph.
SQLite-backed persistent store for every learned dimension of the user:
communication style, workplace relationships, automation trust, routines, facts.
"""
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, time
from typing import Optional, Any
from dataclasses import dataclass, field, asdict

DB_DIR = Path(__file__).parent / "user_data"
DB_PATH = DB_DIR / "user_profile.db"


@dataclass
class CommunicationStyle:
    brevity: float = 0.5          # 0=verbose, 1=terse
    formality: float = 0.5        # 0=casual, 1=formal
    default_channel: str = ""     # slack, teams, email, whatsapp
    email_signoff: str = ""
    preferred_response_format: str = "text"  # text, bullet, table, code


@dataclass
class RelationshipEntry:
    entity: str
    relation: str                # manager, teammate, friend, family, client
    preferred_channel: str = ""
    communication_style_hint: str = ""
    last_interacted: str = ""


@dataclass
class AutomationTrust:
    confidence: float = 0.5       # 0=needs approval, 1=fully trusted
    auto_after: int = 10          # consecutive approvals before auto
    execution_mode: str = "confirm"  # confirm, notify, silent
    consecutive_successes: int = 0
    total_attempts: int = 0


@dataclass
class LearnedRoutine:
    trigger_hour: int
    trigger_minute: int
    trigger_days: list  # 0=Mon..6=Sun
    action_summary: str
    confidence: float = 0.0
    times_observed: int = 0
    last_triggered: str = ""


@dataclass
class UserProfileData:
    user_id: str = "local"
    communication: CommunicationStyle = field(default_factory=CommunicationStyle)
    relationships: list = field(default_factory=list)
    automation_trust: dict = field(default_factory=dict)  # action_key -> AutomationTrust
    routines: list = field(default_factory=list)
    facts: list = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    interaction_count: int = 0
    first_seen: str = ""
    last_seen: str = ""


class UserProfile:
    def __init__(self, user_id: str = "local", db_path: Optional[Path] = None):
        self.user_id = user_id
        self._db_path = db_path or DB_PATH
        self._local = threading.Lock()
        self._profile: Optional[UserProfileData] = None
        self._init_db()
        self.load()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    input_hash TEXT,
                    action TEXT,
                    success INTEGER,
                    latency_ms REAL,
                    correction_similarity REAL,
                    mode TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    context TEXT,
                    details TEXT
                );
                CREATE TABLE IF NOT EXISTS routines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    trigger_hour INTEGER NOT NULL,
                    trigger_minute INTEGER NOT NULL,
                    trigger_days TEXT NOT NULL,
                    action_summary TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    times_observed INTEGER DEFAULT 1,
                    last_triggered TEXT,
                    UNIQUE(user_id, trigger_hour, trigger_minute, action_summary)
                );
                CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_signals(user_id);
                CREATE INDEX IF NOT EXISTS idx_routines_user ON routines(user_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def load(self):
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                "SELECT data FROM profiles WHERE user_id = ?", (self.user_id,)
            ).fetchone()
            if row:
                self._profile = self._deserialize(row[0])
            else:
                self._profile = UserProfileData(user_id=self.user_id)
                self._profile.first_seen = datetime.now().isoformat()
                self._save(conn)
        finally:
            conn.close()

    def _save(self, conn: Optional[sqlite3.Connection] = None):
        if self._profile is None:
            return
        now = datetime.now().isoformat()
        self._profile.last_seen = now
        data = self._serialize(self._profile)
        if conn:
            conn.execute(
                """INSERT OR REPLACE INTO profiles (user_id, data, created_at, updated_at)
                   VALUES (?, ?, COALESCE((SELECT created_at FROM profiles WHERE user_id=?), ?), ?)""",
                (self.user_id, data, self.user_id, now, now)
            )
            conn.commit()
        else:
            c = sqlite3.connect(str(self._db_path))
            try:
                c.execute(
                    """INSERT OR REPLACE INTO profiles (user_id, data, created_at, updated_at)
                       VALUES (?, ?, COALESCE((SELECT created_at FROM profiles WHERE user_id=?), ?), ?)""",
                    (self.user_id, data, self.user_id, now, now)
                )
                c.commit()
            finally:
                c.close()

    def save(self):
        with self._local:
            self._save()

    # ── Serialization ──────────────────────────────────────────────

    @staticmethod
    def _serialize(p: UserProfileData) -> str:
        d = asdict(p)
        d["communication"] = asdict(p.communication)
        d["automation_trust"] = {k: asdict(v) for k, v in p.automation_trust.items()}
        return json.dumps(d, default=str)

    @staticmethod
    def _deserialize(s: str) -> UserProfileData:
        d = json.loads(s)
        comm = CommunicationStyle(**d.get("communication", {}))
        trust = {}
        for k, v in d.get("automation_trust", {}).items():
            trust[k] = AutomationTrust(**v)
        p = UserProfileData(
            user_id=d.get("user_id", "local"),
            communication=comm,
            relationships=[RelationshipEntry(**r) for r in d.get("relationships", [])],
            automation_trust=trust,
            routines=[LearnedRoutine(**r) for r in d.get("routines", [])],
            facts=d.get("facts", []),
            preferences=d.get("preferences", {}),
            interaction_count=d.get("interaction_count", 0),
            first_seen=d.get("first_seen", ""),
            last_seen=d.get("last_seen", ""),
        )
        return p

    # ── Profile access ─────────────────────────────────────────────

    @property
    def profile(self) -> UserProfileData:
        if self._profile is None:
            self.load()
        return self._profile

    def get_communication_style(self) -> CommunicationStyle:
        return self.profile.communication

    def update_communication_style(self, **kwargs):
        with self._local:
            for k, v in kwargs.items():
                if hasattr(self._profile.communication, k):
                    setattr(self._profile.communication, k, v)
            self._save()

    def get_relationship(self, entity: str) -> Optional[RelationshipEntry]:
        for r in self.profile.relationships:
            if r.entity.lower() == entity.lower():
                return r
        return None

    def upsert_relationship(self, entity: str, relation: str = "", channel: str = "", style_hint: str = ""):
        with self._local:
            for r in self.profile.relationships:
                if r.entity.lower() == entity.lower():
                    if relation:
                        r.relation = relation
                    if channel:
                        r.preferred_channel = channel
                    if style_hint:
                        r.communication_style_hint = style_hint
                    r.last_interacted = datetime.now().isoformat()
                    self._save()
                    return
            self.profile.relationships.append(RelationshipEntry(
                entity=entity, relation=relation or "contact",
                preferred_channel=channel, communication_style_hint=style_hint,
                last_interacted=datetime.now().isoformat()
            ))
            self._save()

    def get_automation_trust(self, action_key: str) -> AutomationTrust:
        t = self.profile.automation_trust.get(action_key)
        if t is None:
            t = AutomationTrust()
            self.profile.automation_trust[action_key] = t
        return t

    def record_action_outcome(self, action_key: str, success: bool, user_corrected: bool = False):
        with self._local:
            trust = self.get_automation_trust(action_key)
            trust.total_attempts += 1
            if success and not user_corrected:
                trust.consecutive_successes += 1
                trust.confidence = min(1.0, trust.confidence + 0.05)
            else:
                trust.consecutive_successes = 0
                trust.confidence = max(0.0, trust.confidence - 0.1)
                if user_corrected:
                    trust.confidence = max(0.0, trust.confidence - 0.15)

            if trust.consecutive_successes >= trust.auto_after:
                trust.execution_mode = "notify"
            if trust.consecutive_successes >= trust.auto_after * 3:
                trust.execution_mode = "silent"
            if trust.consecutive_successes == 0 and trust.total_attempts > 3:
                trust.execution_mode = "confirm"
            self._save()

    def record_interaction(self, action: str = "", success: bool = True, latency_ms: float = 0.0,
                           correction_similarity: Optional[float] = None, mode: str = "auto"):
        with self._local:
            self.profile.interaction_count += 1
            now = datetime.now().isoformat()
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """INSERT INTO interactions (user_id, timestamp, action, success, latency_ms, correction_similarity, mode)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, now, action, int(success), latency_ms, correction_similarity, mode)
                )
                conn.commit()
            finally:
                conn.close()

    def record_feedback_signal(self, signal_type: str, context: str = "", details: Optional[dict] = None):
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """INSERT INTO feedback_signals (user_id, timestamp, signal_type, context, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (self.user_id, datetime.now().isoformat(), signal_type, context,
                 json.dumps(details) if details else None)
            )
            conn.commit()
        finally:
            conn.close()

    def get_routines(self) -> list:
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                """SELECT trigger_hour, trigger_minute, trigger_days, action_summary,
                          confidence, times_observed, last_triggered
                   FROM routines WHERE user_id = ? ORDER BY confidence DESC""",
                (self.user_id,)
            ).fetchall()
            return [
                LearnedRoutine(
                    trigger_hour=r[0], trigger_minute=r[1],
                    trigger_days=json.loads(r[2]), action_summary=r[3],
                    confidence=r[4], times_observed=r[5], last_triggered=r[6] or ""
                ) for r in rows
            ]
        finally:
            conn.close()

    def add_fact(self, fact: str, category: str = "general"):
        with self._local:
            entry = {"fact": fact, "category": category, "learned": datetime.now().isoformat()}
            self.profile.facts.append(entry)
            if len(self.profile.facts) > 500:
                self.profile.facts = self.profile.facts[-500:]
            self._save()

    def set_preference(self, key: str, value: Any):
        with self._local:
            self.profile.preferences[key] = value
            self._save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.profile.preferences.get(key, default)

    def learn_routine(self, hour: int, minute: int, days: list, summary: str):
        conn = sqlite3.connect(str(self._db_path))
        try:
            days_json = json.dumps(days)
            existing = conn.execute(
                "SELECT confidence, times_observed FROM routines WHERE user_id=? AND trigger_hour=? AND trigger_minute=? AND action_summary=?",
                (self.user_id, hour, minute, summary)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE routines SET confidence=?, times_observed=?, last_triggered=? WHERE user_id=? AND trigger_hour=? AND trigger_minute=? AND action_summary=?",
                    (min(1.0, existing[0] + 0.1), existing[1] + 1, datetime.now().isoformat(),
                     self.user_id, hour, minute, summary)
                )
            else:
                conn.execute(
                    "INSERT INTO routines (user_id, trigger_hour, trigger_minute, trigger_days, action_summary, confidence, times_observed, last_triggered) VALUES (?,?,?,?,?,?,?,?)",
                    (self.user_id, hour, minute, days_json, summary, 0.1, 1, datetime.now().isoformat())
                )
            conn.commit()
        finally:
            conn.close()

    def get_trust_summary(self) -> dict:
        return {
            k: {"confidence": round(v.confidence, 2), "mode": v.execution_mode,
                "successes": v.consecutive_successes, "total": v.total_attempts}
            for k, v in self.profile.automation_trust.items()
        }

    def get_relationship_summary(self) -> str:
        if not self.profile.relationships:
            return ""
        lines = []
        for r in self.profile.relationships:
            parts = [f"{r.entity} ({r.relation})"]
            if r.preferred_channel:
                parts.append(f"via {r.preferred_channel}")
            lines.append("; ".join(parts))
        return "\n".join(lines)

    def get_summary_for_prompt(self) -> str:
        c = self.profile.communication
        lines = [f"User: {self.user_id}"]
        lines.append(f"Brevity preference: {c.brevity:.0%} (0=verbose, 1=terse)")
        lines.append(f"Formality preference: {c.formality:.0%}")
        if c.default_channel:
            lines.append(f"Default channel: {c.default_channel}")
        if c.email_signoff:
            lines.append(f"Email sign-off: {c.email_signoff}")
        if c.preferred_response_format != "text":
            lines.append(f"Preferred response format: {c.preferred_response_format}")

        rel = self.get_relationship_summary()
        if rel:
            lines.append(f"Relationships:\n{rel}")

        trust = self.get_trust_summary()
        if trust:
            high_trust = [k for k, v in trust.items() if v["confidence"] > 0.7 and v["mode"] == "silent"]
            low_trust = [k for k, v in trust.items() if v["confidence"] < 0.3]
            if high_trust:
                lines.append(f"Fully trusted actions (auto-execute): {', '.join(high_trust)}")
            if low_trust:
                lines.append(f"Low-trust actions (require confirmation): {', '.join(low_trust)}")

        routines = self.get_routines()
        if routines:
            active = [r for r in routines if r.confidence > 0.3]
            if active:
                rlines = []
                for r in active[:5]:
                    days_str = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                    dnames = [days_str[d] for d in r.trigger_days if d < 7]
                    rlines.append(f"  {r.action_summary} @ {r.trigger_hour:02d}:{r.trigger_minute:02d} on {','.join(dnames)}")
                lines.append(f"Learned routines:\n" + "\n".join(rlines))

        if self.profile.facts:
            recent = self.profile.facts[-10:]
            lines.append("Recent facts learned:")
            for f in recent:
                lines.append(f"  [{f['category']}] {f['fact']}")

        if self.profile.preferences:
            lines.append("Preferences: " + json.dumps(self.profile.preferences, default=str))

        return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────
_profile_store: dict[str, UserProfile] = {}

def get_profile(user_id: str = "local") -> UserProfile:
    if user_id not in _profile_store:
        _profile_store[user_id] = UserProfile(user_id)
    return _profile_store[user_id]
