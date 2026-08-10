"""
JARVIS Companion & Memory Agent (CORE_AGENT)
=============================================
Worker Agent #4 — handles memory retention, spaced-repetition education,
empathy/crisis detection, and proactive life-context orchestration.

Components:
  - MemoryEngine   : Persistent personal context store (SQLite WAL)
  - EducationEngine: Spaced repetition & active recall (SM-2 algorithm)
  - EmpathyEngine  : Emotional support & crisis detection (CBT grounding)
  - CompanionAgent : Main orchestrator routing user input to sub-engines
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "jarvis_memory.db")

MEMORY_CATEGORIES = {"pref", "event", "concern", "habit", "fact", "emotion"}

CRISIS_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(?:want(?:ing)?\s+to\s+die|suicide|kill(?:ing)?\s+myself|end\s+my\s+life"
        r"|wish\s+I\s+(?:were|was)\s+dead|no\s+reason\s+to\s+live"
        r"|better\s+off\s+(?:dead|without\s+me)|overdose"
        r"|cut(?:ting)?\s+(?:my)?self(?:self)?|self[- ]?harm"
        r"|want\s+to\s+(?:hurt|end)\s+myself)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:murder|kill(?:ing)?\s+(?:someone|him|her|them|people)"
        r"|bomb|shoot(?:ing)?\s+(?:up|people|school|public)"
        r"|arson|attack(?:ing)?\s+(?:with\s+a)\s+(?:weapon|knife|gun))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:rape|molest|abuse\s+(?:a\s+)?child|sex\s+traffick)\b",
        re.IGNORECASE,
    ),
]

CRISIS_RESOURCES: Dict[str, Dict[str, str]] = {
    "US": {
        "name": "988 Suicide & Crisis Lifeline",
        "number": "988",
        "sms": "Text HOME to 741741",
        "url": "https://988lifeline.org",
    },
    "UK": {
        "name": "Samaritans",
        "number": "116 123",
        "sms": "Text SHOUT to 85258",
        "url": "https://www.samaritans.org",
    },
    "IN": {
        "name": "iCall / Vandrevala Foundation",
        "number": "1860-2662-345",
        "sms": "",
        "url": "https://icallhelpline.org",
    },
    "CA": {
        "name": "Talk Suicide Canada",
        "number": "1-833-456-4566",
        "sms": "Text 45645",
        "url": "https://talksuicide.ca",
    },
    "AU": {
        "name": "Lifeline Australia",
        "number": "13 11 14",
        "sms": "",
        "url": "https://www.lifeline.org.au",
    },
    "DE": {
        "name": "Telefonseelsorge",
        "number": "0800 111 0 111",
        "sms": "",
        "url": "https://www.telefonseelsorge.de",
    },
    "JP": {
        "name": "TELL Lifeline",
        "number": "03-5774-0992",
        "sms": "",
        "url": "https://telljp.com",
    },
    "BR": {
        "name": "CVV (Centro de Valorização da Vida)",
        "number": "188",
        "sms": "",
        "url": "https://cvv.org.br",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryEngine — Persistent Personal Context Store
# ═══════════════════════════════════════════════════════════════════════════════


class MemoryEngine:
    """SQLite-backed persistent memory with WAL mode for concurrent reads.

    Stores user preferences, events, concerns, habits, facts, and emotions.
    Supports keyword-based recall, proactive trigger matching, and reminders.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._local = threading.local()
        self._init_db()

    # ── Connection ────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL    NOT NULL,
                category        TEXT    NOT NULL CHECK(category IN
                                    ('pref','event','concern','habit','fact','emotion')),
                content         TEXT    NOT NULL,
                importance      INTEGER NOT NULL DEFAULT 5
                                    CHECK(importance BETWEEN 1 AND 10),
                access_count    INTEGER NOT NULL DEFAULT 0,
                last_accessed   REAL    NOT NULL,
                source_text     TEXT
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at      REAL    NOT NULL,
                trigger_text    TEXT    NOT NULL,
                next_fire       REAL    NOT NULL,
                recurring_pattern TEXT  CHECK(recurring_pattern IN
                                    ('daily','weekly','monthly') OR recurring_pattern IS NULL),
                active          INTEGER NOT NULL DEFAULT 1,
                last_fired      REAL,
                fire_count      INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS proactive_triggers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_regex   TEXT    NOT NULL,
                action_type     TEXT    NOT NULL,
                action_data     TEXT    NOT NULL,
                created_from_entry_id INTEGER REFERENCES memory_entries(id)
            );

            CREATE INDEX IF NOT EXISTS idx_mem_category ON memory_entries(category);
            CREATE INDEX IF NOT EXISTS idx_mem_timestamp ON memory_entries(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_rem_next ON reminders(next_fire) WHERE active = 1;
            CREATE INDEX IF NOT EXISTS idx_pt_pattern ON proactive_triggers(pattern_regex);
        """)
        conn.commit()

    # ── Memory CRUD ───────────────────────────────────────────────────────

    def store(
        self,
        content: str,
        category: str,
        importance: int = 5,
        source: str | None = None,
    ) -> int:
        """Store a memory entry. Returns the new row id."""
        if category not in MEMORY_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of {MEMORY_CATEGORIES}")
        importance = max(1, min(10, importance))
        now = time.time()
        conn = self._conn()
        cur = conn.execute(
            """INSERT INTO memory_entries
               (timestamp, category, content, importance, access_count, last_accessed, source_text)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (now, category, content, importance, now, source),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def recall(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories by keyword relevance. Returns up to *limit* entries."""
        conn = self._conn()
        now = time.time()
        keywords = [w.lower() for w in re.split(r"\W+", query) if len(w) > 1]
        if not keywords:
            return self.get_recent(limit)

        # Build a LIKE clause for every keyword across content & source_text
        where_parts: list[str] = []
        params: list[str] = []
        for kw in keywords:
            like = f"%{kw}%"
            where_parts.append("(LOWER(content) LIKE ? OR LOWER(source_text) LIKE ?)")
            params.extend([like, like])

        where_sql = " OR ".join(where_parts)
        rows = conn.execute(
            f"""SELECT *, (importance * 1.0 / (1 + julianday('now') - julianday(timestamp, 'unixepoch')))
                AS relevance
                FROM memory_entries
                WHERE {where_sql}
                ORDER BY relevance DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

        # Bump access_count / last_accessed for retrieved rows
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"""UPDATE memory_entries
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE id IN ({placeholders})""",
                [now] + ids,
            )
            conn.commit()

        return [dict(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Return the most recent *limit* memory entries."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM memory_entries ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Reminders ─────────────────────────────────────────────────────────

    def create_reminder(
        self,
        trigger_text: str,
        recurring: str | None = None,
        fire_at: float | None = None,
    ) -> int:
        """Create a reminder. Returns the new row id."""
        if recurring is not None and recurring not in ("daily", "weekly", "monthly"):
            raise ValueError(f"Invalid recurring pattern '{recurring}'")
        now = time.time()
        next_fire = fire_at if fire_at is not None else now
        conn = self._conn()
        cur = conn.execute(
            """INSERT INTO reminders
               (created_at, trigger_text, next_fire, recurring_pattern, active, last_fired, fire_count)
               VALUES (?, ?, ?, ?, 1, NULL, 0)""",
            (now, trigger_text, next_fire, recurring),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_active_reminders(self) -> list[dict]:
        """Return all active reminders whose next_fire is in the past or now."""
        conn = self._conn()
        now = time.time()
        rows = conn.execute(
            "SELECT * FROM reminders WHERE active = 1 AND next_fire <= ? ORDER BY next_fire",
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]

    def fire_reminder(self, reminder_id: int) -> None:
        """Mark a reminder as fired and schedule next occurrence."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        ).fetchone()
        if row is None:
            return

        now = time.time()
        pattern = row["recurring_pattern"]

        if pattern == "daily":
            next_fire = now + 86400
        elif pattern == "weekly":
            next_fire = now + 604800
        elif pattern == "monthly":
            next_fire = now + 2592000  # ~30 days
        else:
            # One-shot: deactivate
            conn.execute(
                "UPDATE reminders SET active = 0, last_fired = ?, fire_count = fire_count + 1 WHERE id = ?",
                (now, reminder_id),
            )
            conn.commit()
            return

        conn.execute(
            """UPDATE reminders
               SET last_fired = ?, fire_count = fire_count + 1, next_fire = ?
               WHERE id = ?""",
            (now, next_fire, reminder_id),
        )
        conn.commit()

    # ── Proactive Triggers ────────────────────────────────────────────────

    def store_proactive_trigger(
        self,
        pattern: str,
        action: str,
        data: dict,
        entry_id: int | None = None,
    ) -> int:
        """Store a regex-based proactive trigger. Returns the new row id."""
        conn = self._conn()
        try:
            re.compile(pattern)
        except re.error:
            raise ValueError(f"Invalid regex pattern: {pattern}")
        cur = conn.execute(
            """INSERT INTO proactive_triggers
               (pattern_regex, action_type, action_data, created_from_entry_id)
               VALUES (?, ?, ?, ?)""",
            (pattern, action, json.dumps(data), entry_id),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def check_proactive_triggers(self, text: str) -> list[dict]:
        """Check if *text* matches any stored proactive trigger patterns."""
        conn = self._conn()
        rows = conn.execute("SELECT * FROM proactive_triggers").fetchall()
        matches: list[dict] = []
        for row in rows:
            try:
                if re.search(row["pattern_regex"], text, re.IGNORECASE):
                    matches.append({
                        "id": row["id"],
                        "action_type": row["action_type"],
                        "action_data": json.loads(row["action_data"]),
                        "pattern": row["pattern_regex"],
                    })
            except re.error:
                continue
        return matches

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Aggregate statistics: total entries, category counts, active reminders."""
        conn = self._conn()
        total = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
        cat_rows = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM memory_entries GROUP BY category"
        ).fetchall()
        categories = {r["category"]: r["cnt"] for r in cat_rows}
        active_reminders = conn.execute(
            "SELECT COUNT(*) FROM reminders WHERE active = 1"
        ).fetchone()[0]
        triggers = conn.execute("SELECT COUNT(*) FROM proactive_triggers").fetchone()[0]
        return {
            "total_entries": total,
            "categories": categories,
            "active_reminders": active_reminders,
            "proactive_triggers": triggers,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EducationEngine — Spaced Repetition & Active Recall (SM-2)
# ═══════════════════════════════════════════════════════════════════════════════


class EducationEngine:
    """Spaced-repetition study system using the SM-2 algorithm.

    Stores study cards, tracks sessions, and computes optimal review intervals
    based on self-reported recall quality (0-5 scale).
    """

    def __init__(self, memory: MemoryEngine) -> None:
        self._memory = memory
        self._conn = memory._conn
        self._init_tables()
        self._active_sessions: Dict[str, dict] = {}

    def _init_tables(self) -> None:
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS study_cards (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                concept         TEXT    NOT NULL,
                summary         TEXT    NOT NULL,
                quiz_question   TEXT    NOT NULL,
                answer_key      TEXT    NOT NULL,
                field_name      TEXT    NOT NULL DEFAULT 'general',
                difficulty      INTEGER NOT NULL DEFAULT 3
                                    CHECK(difficulty BETWEEN 1 AND 5),
                next_review     REAL    NOT NULL,
                interval_days   REAL    NOT NULL DEFAULT 1.0,
                ease_factor     REAL    NOT NULL DEFAULT 2.5,
                review_count    INTEGER NOT NULL DEFAULT 0,
                correct_count   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS study_sessions (
                id              TEXT    PRIMARY KEY,
                started_at      REAL    NOT NULL,
                cards_reviewed  INTEGER NOT NULL DEFAULT 0,
                correct         INTEGER NOT NULL DEFAULT 0,
                accuracy_pct    REAL    NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS retention_fields (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                field_name      TEXT    NOT NULL UNIQUE,
                cards_count     INTEGER NOT NULL DEFAULT 0,
                avg_accuracy    REAL    NOT NULL DEFAULT 0.0,
                last_studied    REAL
            );

            CREATE INDEX IF NOT EXISTS idx_card_next ON study_cards(next_review);
        """)
        conn.commit()

    # ── Card Management ───────────────────────────────────────────────────

    def add_concept(
        self,
        concept: str,
        summary: str,
        quiz_question: str,
        answer: str,
        field: str = "general",
    ) -> int:
        """Add a study card. Returns the new card id."""
        now = time.time()
        conn = self._conn()
        cur = conn.execute(
            """INSERT INTO study_cards
               (concept, summary, quiz_question, answer_key, field_name,
                difficulty, next_review, interval_days, ease_factor, review_count, correct_count)
               VALUES (?, ?, ?, ?, ?, 3, ?, 1.0, 2.5, 0, 0)""",
            (concept, summary, quiz_question, answer, field, now),
        )
        card_id = cur.lastrowid
        # Upsert retention field
        conn.execute(
            """INSERT INTO retention_fields (field_name, cards_count, avg_accuracy, last_studied)
               VALUES (?, 1, 0.0, ?)
               ON CONFLICT(field_name) DO UPDATE SET
                 cards_count = cards_count + 1,
                 last_studied = excluded.last_studied""",
            (field, now),
        )
        conn.commit()
        return card_id  # type: ignore[return-value]

    def get_due_cards(self, field: str | None = None, limit: int = 10) -> list[dict]:
        """Return study cards due for review, ordered by urgency."""
        conn = self._conn()
        now = time.time()
        if field:
            rows = conn.execute(
                """SELECT sc.*, rf.field_name
                   FROM study_cards sc
                   JOIN retention_fields rf ON rf.field_name = ?
                   WHERE sc.next_review <= ?
                   ORDER BY sc.next_review ASC
                   LIMIT ?""",
                (field, now, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT sc.*, rf.field_name
                   FROM study_cards sc
                   LEFT JOIN retention_fields rf ON rf.cards_count > 0
                   WHERE sc.next_review <= ?
                   ORDER BY sc.next_review ASC
                   LIMIT ?""",
                (now, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def review_card(self, card_id: int, quality: int) -> dict:
        """Update a card using the SM-2 algorithm.

        quality: 0–5 (0 = total blackout, 5 = perfect recall)
        Returns the updated card state.
        """
        quality = max(0, min(5, quality))
        conn = self._conn()
        card = conn.execute(
            "SELECT * FROM study_cards WHERE id = ?", (card_id,)
        ).fetchone()
        if card is None:
            raise ValueError(f"Card {card_id} not found")

        # ── SM-2 core ─────────────────────────────────────────────────────
        ease_factor = card["ease_factor"]
        interval = card["interval_days"]
        review_count = card["review_count"] + 1
        correct_count = card["correct_count"] + (1 if quality >= 3 else 0)

        # Update ease factor (min 1.3)
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(1.3, ease_factor)

        if quality < 3:
            # Failed recall → reset interval to 1 day, card re-enters short-term
            interval = 1.0
        else:
            if review_count == 1:
                interval = 1.0
            elif review_count == 2:
                interval = 6.0
            else:
                interval = round(interval * ease_factor, 1)

        now = time.time()
        next_review = now + interval * 86400

        conn.execute(
            """UPDATE study_cards
               SET interval_days = ?, ease_factor = ?, next_review = ?,
                   review_count = ?, correct_count = ?
               WHERE id = ?""",
            (interval, ease_factor, next_review, review_count, correct_count, card_id),
        )

        # Update field accuracy
        field_name = dict(card)["field_name"] if "field_name" in card.keys() else "general"
        conn.execute(
            """UPDATE retention_fields
               SET avg_accuracy = (
                     SELECT 100.0 * SUM(CASE WHEN correct_count > 0 THEN 1 ELSE 0 END) / COUNT(*)
                     FROM study_cards
                   ),
                   last_studied = ?
               WHERE field_name = ?""",
            (now, field_name),
        )
        conn.commit()

        return {
            "card_id": card_id,
            "quality": quality,
            "new_interval_days": interval,
            "new_ease_factor": round(ease_factor, 3),
            "next_review": datetime.fromtimestamp(next_review).isoformat(),
            "review_count": review_count,
            "correct_count": correct_count,
        }

    # ── Session Management ────────────────────────────────────────────────

    def start_session(self) -> str:
        """Start a study session. Returns session_id."""
        session_id = f"ses_{uuid.uuid4().hex[:12]}"
        now = time.time()
        conn = self._conn()
        conn.execute(
            """INSERT INTO study_sessions (id, started_at, cards_reviewed, correct, accuracy_pct)
               VALUES (?, ?, 0, 0, 0.0)""",
            (session_id, now),
        )
        conn.commit()
        self._active_sessions[session_id] = {
            "started_at": now,
            "cards_reviewed": 0,
            "correct": 0,
        }
        return session_id

    def end_session(self, session_id: str) -> dict:
        """End a study session and return final stats."""
        session = self._active_sessions.pop(session_id, None)
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM study_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return {"error": "Session not found"}
        accuracy = (row["correct"] / row["cards_reviewed"] * 100) if row["cards_reviewed"] > 0 else 0.0
        conn.execute(
            "UPDATE study_sessions SET accuracy_pct = ? WHERE id = ?",
            (accuracy, session_id),
        )
        conn.commit()
        return {
            "session_id": session_id,
            "cards_reviewed": row["cards_reviewed"],
            "correct": row["correct"],
            "accuracy_pct": round(accuracy, 1),
            "duration_s": round(time.time() - row["started_at"], 1),
        }

    def _record_review(self, session_id: str, correct: bool) -> None:
        """Internal: increment session counters after a review."""
        conn = self._conn()
        conn.execute(
            """UPDATE study_sessions
               SET cards_reviewed = cards_reviewed + 1,
                   correct = correct + ?
               WHERE id = ?""",
            (1 if correct else 0, session_id),
        )
        conn.commit()

    # ── Quiz Generation ───────────────────────────────────────────────────

    def generate_quiz(self, topic: str, num_questions: int = 5) -> list[dict]:
        """Generate a quiz from stored concepts matching *topic* keyword."""
        conn = self._conn()
        like = f"%{topic.lower()}%"
        rows = conn.execute(
            """SELECT id, concept, summary, quiz_question, answer_key, difficulty
               FROM study_cards
               WHERE LOWER(concept) LIKE ? OR LOWER(summary) LIKE ?
               ORDER BY RANDOM()
               LIMIT ?""",
            (like, like, num_questions),
        ).fetchall()
        return [
            {
                "card_id": r["id"],
                "concept": r["concept"],
                "question": r["quiz_question"],
                "difficulty": r["difficulty"],
            }
            for r in rows
        ]

    # ── Retention Stats ───────────────────────────────────────────────────

    def get_retention_stats(self) -> dict:
        """Per-field accuracy, total cards due, and study streak."""
        conn = self._conn()
        now = time.time()

        fields = conn.execute("SELECT * FROM retention_fields").fetchall()
        field_stats = [dict(f) for f in fields]

        total_due = conn.execute(
            "SELECT COUNT(*) FROM study_cards WHERE next_review <= ?", (now,)
        ).fetchone()[0]

        total_cards = conn.execute("SELECT COUNT(*) FROM study_cards").fetchone()[0]

        # Streak: consecutive days with at least one review
        streak = 0
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for _ in range(365):
            day_start = day.timestamp()
            day_end = day_start + 86400
            count = conn.execute(
                """SELECT COUNT(*) FROM study_sessions
                   WHERE started_at >= ? AND started_at < ? AND cards_reviewed > 0""",
                (day_start, day_end),
            ).fetchone()[0]
            if count == 0:
                break
            streak += 1
            day -= timedelta(days=1)

        sessions = conn.execute(
            "SELECT * FROM study_sessions ORDER BY started_at DESC LIMIT 10"
        ).fetchall()

        return {
            "fields": field_stats,
            "total_cards": total_cards,
            "cards_due": total_due,
            "streak_days": streak,
            "recent_sessions": [dict(s) for s in sessions],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EmpathyEngine — Emotional Support & Crisis Detection
# ═══════════════════════════════════════════════════════════════════════════════


class EmpathyEngine:
    """Emotional intelligence layer: sentiment analysis, crisis detection,
    CBT-based grounding responses, and empathetic active-listening replies.
    """

    # Sentiment lexicons (word → score)
    _POSITIVE_WORDS: set[str] = {
        "happy", "great", "awesome", "love", "excited", "wonderful", "amazing",
        "good", "fantastic", "grateful", "thankful", "proud", "accomplished",
        "confident", "hopeful", "peaceful", "calm", "relaxed", "content",
        "thrilled", "blessed", "joy", "delighted", "cheerful", "optimistic",
        "productive", "motivated", "energetic", "enthusiastic", "inspired",
    }
    _NEGATIVE_WORDS: set[str] = {
        "sad", "angry", "frustrated", "stressed", "anxious", "worried",
        "depressed", "lonely", "overwhelmed", "exhausted", "tired", "upset",
        "hurt", "scared", "afraid", "nervous", "disappointed", "confused",
        "hopeless", "helpless", "miserable", "terrible", "awful", "bad",
        "annoyed", "irritated", "anxious", "panic", "fear", "dread",
        "exhausted", "burnt", "drained", "worthless", "empty", "numb",
    }
    _INTENSIFIERS: set[str] = {
        "very", "extremely", "really", "so", "incredibly", "absolutely",
        "totally", "completely", "utterly", "deeply", "severely",
    }

    def __init__(self, memory: MemoryEngine) -> None:
        self._memory = memory

    def analyze_sentiment(self, text: str) -> dict:
        """Rule-based sentiment analysis returning sentiment label, intensity, and keywords."""
        words = re.findall(r"\b\w+\b", text.lower())
        pos_count = 0
        neg_count = 0
        keywords: list[str] = []
        intensifier_bonus = 1.0

        for w in words:
            if w in self._INTENSIFIERS:
                intensifier_bonus = 1.5
                continue
            if w in self._POSITIVE_WORDS:
                pos_count += 1
                keywords.append(w)
            elif w in self._NEGATIVE_WORDS:
                neg_count += 1
                keywords.append(w)

        total = pos_count + neg_count
        if total == 0:
            return {"sentiment": "neutral", "intensity": 0.0, "keywords": []}

        raw = (pos_count - neg_count) / total
        intensity = min(1.0, (total / max(len(words), 1)) * intensifier_bonus)

        if raw > 0.15:
            sentiment = "positive"
        elif raw < -0.15:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {"sentiment": sentiment, "intensity": round(intensity, 3), "keywords": keywords}

    def detect_crisis(self, text: str) -> dict:
        """Scan for crisis-level language. Returns severity and helpline info."""
        for pattern in CRISIS_PATTERNS:
            match = pattern.search(text)
            if match:
                # Heuristic severity: count of distinct crisis phrases
                severity = "high" if len(re.findall(r"\b(?:want|kill|die|suicide|end|hurt|self)\b", text.lower())) >= 3 else "medium"
                resources = self.get_crisis_resources()
                return {
                    "is_crisis": True,
                    "severity": severity,
                    "matched_phrase": match.group(),
                    "helpline": resources["number"],
                    "message": (
                        f"I'm really concerned about what you've shared. "
                        f"Your life matters and there are people trained to help right now. "
                        f"Please reach out to {resources['name']} at {resources['number']}. "
                        f"{resources.get('sms', '')}"
                    ),
                }
        return {"is_crisis": False, "severity": "none", "helpline": None, "message": None}

    def generate_grounding_response(self, text: str, history: list | None = None) -> str:
        """Generate a CBT-based grounding response for acute distress."""
        distress_words = {
            "anxious", "panic", "overwhelmed", "stressed", "fear", "scared",
            "nervous", "dread", "racing", "spiraling", "drowning", "trapped",
        }
        words = set(re.findall(r"\b\w+\b", text.lower()))
        triggers = distress_words & words

        if triggers:
            return (
                "I hear you, and what you're feeling is valid. Let's ground ourselves "
                "together. Try this: **5-4-3-2-1 technique**\n\n"
                "1. Name **5** things you can see right now\n"
                "2. Name **4** things you can touch or feel\n"
                "3. Name **3** things you can hear\n"
                "4. Name **2** things you can smell\n"
                "5. Name **1** thing you can taste\n\n"
                "Take slow breaths — in for 4 counts, hold for 4, out for 4. "
                "You're safe in this moment. I'm here with you."
            )

        if "angry" in words or "frustrated" in words:
            return (
                "That sounds really frustrating. When emotions run high, "
                "try this: pause, place both feet on the floor, and take 3 slow breaths. "
                "Name what you're feeling out loud — 'I feel angry because ___'. "
                "Labeling the emotion gives your prefrontal cortex a chance to catch up "
                "with your amygdala. You've got this."
            )

        if "sad" in words or "depressed" in words or "lonely" in words:
            return (
                "I'm sorry you're going through this. It's okay to feel this way — "
                "sadness is your mind processing something important. "
                "One small step: can you do one kind thing for yourself right now? "
                "A glass of water, a short walk, texting someone you trust? "
                "You don't have to fix everything at once."
            )

        return (
            "I'm here with you. Whatever you're going through, take it one moment at a time. "
            "If things feel heavy, remember: feelings are temporary visitors, not permanent residents. "
            "Would you like to talk about what's on your mind?"
        )

    def generate_empathetic_reply(self, text: str, history: list | None = None) -> str:
        """Active-listening response that validates feelings and asks a follow-up."""
        sentiment = self.analyze_sentiment(text)

        # Check for personal disclosure patterns
        name_match = re.search(r"(?:my name is|i'm|i am)\s+(\w+)", text.lower())
        name = name_match.group(1).capitalize() if name_match else None

        if sentiment["sentiment"] == "negative":
            intensity = sentiment["intensity"]
            if intensity > 0.6:
                opening = (
                    f"Thank you for trusting me with that. It sounds like you're going "
                    f"through something really tough right now."
                )
            else:
                opening = "I appreciate you sharing that with me."
        elif sentiment["sentiment"] == "positive":
            opening = "That's great to hear! I'm glad something positive is happening."
        else:
            opening = "Thanks for telling me about that."

        # Context-aware follow-up
        event_words = {"happened", "today", "morning", "yesterday", "just", "now", "week"}
        words = set(re.findall(r"\b\w+\b", text.lower()))

        if words & event_words:
            followup = "Would you like to tell me more about what happened?"
        elif sentiment["sentiment"] == "negative":
            followup = "What do you think triggered this feeling?"
        else:
            followup = "Is there anything specific you'd like to do about this?"

        greeting = f"Hey {name}, " if name else ""
        return f"{greeting}{opening} {followup}"

    @staticmethod
    def get_crisis_resources(country: str = "US") -> dict:
        """Return crisis helpline info for the given country code."""
        return CRISIS_RESOURCES.get(country.upper(), CRISIS_RESOURCES["US"])


# ═══════════════════════════════════════════════════════════════════════════════
# CompanionAgent — Main Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════


class CompanionAgent:
    """CORE_AGENT orchestrator — routes user input through crisis detection,
    proactive triggers, sentiment analysis, and domain-specific handlers.

    Returns a structured JSON-compatible response dict.
    """

    # Response modes
    MODE_SUPPORTIVE = "SUPPORTIVE"
    MODE_EDUCATIONAL = "EDUCATIONAL"
    MODE_LOGISTICAL = "LOGISTICAL"
    MODE_CONVERSATIONAL = "CONVERSATIONAL"

    # Keyword sets for mode classification
    _EDUCATION_KEYWORDS = {
        "study", "learn", "quiz", "flashcard", "review", "concept", "explain",
        "teach", "remember", "revision", "exam", "test", "practice", "spaced",
        "recall", "mnemonic", "flashcard", "note", "notes", "summary",
    }
    _LOGISTICAL_KEYWORDS = {
        "remind", "reminder", "schedule", "alarm", "set", "create",
        "list", "add", "track", "todo", "task", "calendar", "event",
        "delete", "remove", "update", "change", "activate",
    }

    def __init__(self, memory: MemoryEngine | None = None) -> None:
        self.memory = memory or MemoryEngine()
        self.education = EducationEngine(self.memory)
        self.empathy = EmpathyEngine(self.memory)
        self._graph = None
        self._cortex = None
        self._orchestrator = None
        self._init_memory_systems()

    def _init_memory_systems(self):
        """Initialize all memory subsystems."""
        try:
            from graph_memory import memory as graph_mem
            self._graph = graph_mem
        except ImportError:
            pass
        try:
            from advanced_cortex import cortex
            self._cortex = cortex
        except ImportError:
            pass
        try:
            from context_orchestrator import orchestrator
            self._orchestrator = orchestrator
        except ImportError:
            pass

    def process(self, text: str, context: dict | None = None) -> dict:
        """Main entry point. Routes input through the companion pipeline.

        Pipeline stages:
          1. Crisis detection → immediate safety response
          2. Proactive triggers → fire any matching reminders
          3. Sentiment analysis → determine mode
          4. Route to handler
          5. Store interaction memory
          6. Return structured response
        """
        context = context or {}
        response: dict[str, Any] = {
            "mode": self.MODE_CONVERSATIONAL,
            "empathy_note": None,
            "revision_data": None,
            "reminders": [],
            "memory_stored": False,
            "proactive_triggers_fired": [],
            "crisis_detected": False,
            "crisis_resources": None,
            "reply": "",
            "confidence": 0.0,
        }

        # ── Stage 1: Crisis detection ─────────────────────────────────────
        crisis = self.empathy.detect_crisis(text)
        if crisis["is_crisis"]:
            response["crisis_detected"] = True
            response["mode"] = self.MODE_SUPPORTIVE
            response["reply"] = crisis["message"]
            response["crisis_resources"] = self.empathy.get_crisis_resources(
                context.get("country", "US")
            )
            response["empathy_note"] = "Crisis detected — safety response prioritized."
            response["confidence"] = 0.99
            self._store_interaction(text, response)
            return response

        # ── Stage 2: Proactive triggers ───────────────────────────────────
        triggers = self.memory.check_proactive_triggers(text)
        fired_triggers: list[str] = []
        for trig in triggers:
            action_type = trig["action_type"]
            action_data = trig["action_data"]
            fired_triggers.append(f"{action_type}:{trig['pattern']}")
            if action_type == "reminder":
                response["reminders"].append(
                    action_data.get("message", "Proactive reminder fired.")
                )
            elif action_type == "fact":
                response["reminders"].append(
                    action_data.get("fact", "")
                )
        response["proactive_triggers_fired"] = fired_triggers

        # Also check active reminders
        active_reminders = self.memory.get_active_reminders()
        for rem in active_reminders[:3]:
            response["reminders"].append(rem["trigger_text"])
            self.memory.fire_reminder(rem["id"])

        # ── Stage 3: Mode classification ──────────────────────────────────
        words = set(re.findall(r"\b\w+\b", text.lower()))
        sentiment = self.empathy.analyze_sentiment(text)

        if words & self._EDUCATION_KEYWORDS:
            mode = self.MODE_EDUCATIONAL
            confidence = 0.88
        elif words & self._LOGISTICAL_KEYWORDS:
            mode = self.MODE_LOGISTICAL
            confidence = 0.85
        elif sentiment["sentiment"] == "negative" and sentiment["intensity"] > 0.3:
            mode = self.MODE_SUPPORTIVE
            confidence = 0.82
        elif sentiment["sentiment"] == "positive" and sentiment["intensity"] > 0.5:
            mode = self.MODE_CONVERSATIONAL
            confidence = 0.80
        else:
            mode = self.MODE_CONVERSATIONAL
            confidence = 0.70

        response["mode"] = mode
        response["confidence"] = confidence

        # ── Stage 4: Route to handler ─────────────────────────────────────
        if mode == self.MODE_EDUCATIONAL:
            reply, revision = self._handle_educational(text, context)
            response["reply"] = reply
            response["revision_data"] = revision

        elif mode == self.MODE_LOGISTICAL:
            reply, reminders = self._handle_logistical(text, context)
            response["reply"] = reply
            response["reminders"].extend(reminders)

        elif mode == self.MODE_SUPPORTIVE:
            history = context.get("history", [])
            reply = self.empathy.generate_empathetic_reply(text, history)
            grounding = self.empathy.generate_grounding_response(text, history)
            response["reply"] = reply
            response["empathy_note"] = grounding

        else:
            reply = self._handle_conversational(text, context)
            response["reply"] = reply

        # ── Stage 5: Store interaction memory ─────────────────────────────
        self._store_interaction(text, response)

        return response

    # ── Handlers ──────────────────────────────────────────────────────────

    def _handle_educational(self, text: str, context: dict) -> tuple[str, dict | None]:
        """Handle study/quiz-related requests."""
        # Check if user wants a quiz
        if any(w in text.lower() for w in ("quiz", "test me", "question", "flashcard")):
            topic = self._extract_topic(text)
            quiz = self.education.generate_quiz(topic)
            if quiz:
                questions_text = "\n".join(
                    f"**Q{i+1}.** {q['question']} (Difficulty: {q['difficulty']}/5)"
                    for i, q in enumerate(quiz)
                )
                return (
                    f"Here's a quiz on **{topic}** — {len(quiz)} questions:\n\n{questions_text}\n\n"
                    "Reply with the card ID and your confidence (0-5) after each one.",
                    {
                        "concept": topic,
                        "summary": "",
                        "quiz": questions_text,
                        "answer": "",
                    },
                )
            return (
                f"No study cards found for '{topic}' yet. Want me to add some concepts first?",
                None,
            )

        # Check if user wants to add a concept
        if any(w in text.lower() for w in ("add concept", "new concept", "create card", "save")):
            parsed = self._parse_concept_input(text)
            if parsed:
                card_id = self.education.add_concept(**parsed)
                return (
                    f"Got it — card #{card_id} created for **{parsed['concept']}**. "
                    f"I'll quiz you on this when it's due for review.",
                    parsed,
                )
            return (
                "To add a concept, tell me:\n"
                "- Concept name\n"
                "- Summary\n"
                "- A quiz question\n"
                "- The answer\n\n"
                'Example: "Add concept: photosynthesis. Summary: process plants use. '
                'Q: What is photosynthesis? A: Process converting light to energy."',
                None,
            )

        # Check if user is reviewing a card
        review_match = re.search(r"(?:card|#)\s*(\d+).*?(?:quality|confidence|q[=:]?\s*)(\d)", text.lower())
        if review_match:
            card_id = int(review_match.group(1))
            quality = int(review_match.group(2))
            try:
                result = self.education.review_card(card_id, quality)
                return (
                    f"Card #{card_id} reviewed! Next review: {result['next_review']}. "
                    f"Interval: {result['new_interval_days']} days. "
                    f"Ease factor: {result['new_ease_factor']}.",
                    result,
                )
            except ValueError as e:
                return str(e), None

        # Default: show due cards
        due = self.education.get_due_cards(limit=5)
        if due:
            cards_text = "\n".join(
                f"  #{c['id']}: **{c['concept']}** — {c['quiz_question']}"
                for c in due
            )
            return (
                f"You have {len(due)} card(s) due for review:\n{cards_text}\n\n"
                "Reply with 'card <id> quality <0-5>' to review.",
                None,
            )

        # Check retention stats
        if any(w in text.lower() for w in ("stats", "progress", "streak", "retention")):
            stats = self.education.get_retention_stats()
            fields_info = "\n".join(
                f"  - {f['field_name']}: {f['cards_count']} cards, avg accuracy {f['avg_accuracy']:.1f}%"
                for f in stats["fields"]
            ) or "  No fields yet."
            return (
                f"📊 **Retention Stats**\n"
                f"Total cards: {stats['total_cards']} | Due: {stats['cards_due']}\n"
                f"Study streak: {stats['streak_days']} days\n"
                f"Fields:\n{fields_info}",
                stats,
            )

        return (
            "I can help you study! You can:\n"
            "- Add a concept: 'add concept: ...'\n"
            "- Take a quiz: 'quiz on <topic>'\n"
            "- Review due cards: 'show due cards'\n"
            "- Check progress: 'stats'\n\n"
            "What would you like to do?",
            None,
        )

    def _handle_logistical(self, text: str, context: dict) -> tuple[str, list[str]]:
        """Handle reminder/logistics-related requests."""
        reminders_added: list[str] = []

        # Create reminder
        remind_match = re.search(
            r"(?:remind|reminder|set)\s+(?:me\s+)?(?:to\s+)?(.+?)(?:\s+(?:daily|weekly|monthly))?\s*$",
            text,
            re.IGNORECASE,
        )
        if remind_match:
            trigger = remind_match.group(1).strip()
            recurring = None
            recur_match = re.search(r"(daily|weekly|monthly)", text.lower())
            if recur_match:
                recurring = recur_match.group(1)
            reminder_id = self.memory.create_reminder(trigger, recurring)
            recurrence_text = f" ({recurring})" if recurring else ""
            reminders_added.append(f"Reminder #{reminder_id}: {trigger}{recurrence_text}")
            return (
                f"Done! Reminder created{recurrence_text}: **{trigger}**. "
                f"I'll notify you when it's time.",
                reminders_added,
            )

        # List active reminders
        if any(w in text.lower() for w in ("list reminders", "show reminders", "my reminders")):
            active = self.memory.get_active_reminders()
            if active:
                lines = "\n".join(
                    f"  #{r['id']}: {r['trigger_text']} "
                    f"({'every ' + r['recurring_pattern'] if r['recurring_pattern'] else 'once'})"
                    for r in active
                )
                return f"Active reminders:\n{lines}", reminders_added
            return "No active reminders.", reminders_added

        # Default logistical response
        return (
            "I can set reminders for you. Try:\n"
            "- 'Remind me to call mom tomorrow'\n"
            "- 'Set daily reminder to exercise'\n"
            "- 'Show my reminders'\n\n"
            "What do you need?",
            reminders_added,
        )

    def _handle_conversational(self, text: str, context: dict) -> str:
        """Handle general conversation with memory-augmented context."""
        # Recall relevant memories
        memories = self.memory.recall(text, limit=3)
        memory_context = ""
        if memories:
            snippets = " | ".join(m["content"][:80] for m in memories[:2])
            memory_context = f"\n[Context: {snippets}]\n"

        sentiment = self.empathy.analyze_sentiment(text)
        empathy = self.empathy.generate_empathetic_reply(text, context.get("history"))

        if memory_context:
            return f"{empathy}\n\nBased on what I remember: {memory_context.strip()}"

        return empathy

    # ── Helpers ───────────────────────────────────────────────────────────

    def _store_interaction(self, text: str, response: dict) -> None:
        """Persist the interaction as a memory entry + graph memory entities."""
        try:
            importance = 6 if response.get("crisis_detected") else 4
            category = "concern" if response.get("crisis_detected") else "fact"
            mode = response.get("mode", "CONVERSATIONAL")

            if mode == "SUPPORTIVE":
                category = "emotion"
                importance = 7
            elif mode == "EDUCATIONAL":
                category = "fact"
                importance = 5
            elif mode == "LOGISTICAL":
                category = "event"
                importance = 5

            content = json.dumps({
                "user_input": text[:500],
                "mode": mode,
                "reply_preview": response.get("reply", "")[:200],
                "crisis": response.get("crisis_detected", False),
            })

            self.memory.store(content, category, importance, source=text[:500])
            response["memory_stored"] = True

            # Graph memory: extract and store entities
            if self._graph:
                try:
                    self._graph.extract_and_store(text, role="user")
                except Exception:
                    pass

            # Cortex: record temporal event
            if self._cortex:
                try:
                    event_id = self._cortex.record_event(
                        summary=text[:200],
                        full_content=text,
                        event_type="conversation",
                        importance=importance,
                    )
                    # Auto-learn emotional state from user text
                    if mode == "SUPPORTIVE":
                        self._cortex.update_user_profile(
                            "current_emotional_state",
                            response.get("reply", "")[:100],
                            confidence=0.6,
                        )
                except Exception:
                    pass

            # Orchestrator: learn from interaction
            if self._orchestrator:
                try:
                    self._orchestrator.learn_from_interaction(
                        text, response.get("reply", "")
                    )
                except Exception:
                    pass

        except Exception:
            response["memory_stored"] = False

    @staticmethod
    def _extract_topic(text: str) -> str:
        """Extract a topic from text for quiz generation."""
        # Remove common prefixes
        cleaned = re.sub(
            r"(?:quiz|test|revision|review|study|on|about|of|for)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        # Remove trailing punctuation
        cleaned = re.sub(r"[.!?;:,]+$", "", cleaned).strip()
        return cleaned if cleaned else "general"

    @staticmethod
    def _parse_concept_input(text: str) -> dict | None:
        """Try to parse a structured concept input."""
        concept_match = re.search(r"concept[:\s]+(.+?)(?:\.|summary|$)", text, re.IGNORECASE)
        summary_match = re.search(r"summary[:\s]+(.+?)(?:\.|q(?:uestion)?[:\s]|$)", text, re.IGNORECASE)
        question_match = re.search(r"q(?:uestion)?[:\s]+(.+?)(?:\.|a(?:nswer)?[:\s]|$)", text, re.IGNORECASE)
        answer_match = re.search(r"a(?:nswer)?[:\s]+(.+?)$", text, re.IGNORECASE)

        if not concept_match:
            return None

        return {
            "concept": concept_match.group(1).strip(),
            "summary": summary_match.group(1).strip() if summary_match else "",
            "quiz_question": question_match.group(1).strip() if question_match else "",
            "answer": answer_match.group(1).strip() if answer_match else "",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Module-Level Singleton
# ═══════════════════════════════════════════════════════════════════════════════

_companion_lock = threading.Lock()
_companion_instance: CompanionAgent | None = None


def _get_companion() -> CompanionAgent:
    global _companion_instance
    if _companion_instance is None:
        with _companion_lock:
            if _companion_instance is None:
                _companion_instance = CompanionAgent()
    return _companion_instance


companion: CompanionAgent = _get_companion()
