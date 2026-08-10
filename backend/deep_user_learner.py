"""
JARVIS Deep User Learning System — Learns everything about the user.

Observes:
- What user says, how they say it, corrections they make
- Actions approved vs rejected, trust patterns
- Daily routines, app usage, time patterns
- Communication style evolution
- Task preferences, quality standards
- What works and what fails

Stores in SQLite for persistence across sessions.
Uses Bayesian updating for confidence scores.
"""
import os
import json
import math
import sqlite3
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict

DB_DIR = Path(__file__).parent / "user_data"
DB_PATH = DB_DIR / "deep_learning.db"


@dataclass
class ConversationMemory:
    """A single conversation turn to learn from."""
    user_input: str
    ai_response: str
    action_taken: str = ""
    success: bool = True
    user_feedback: str = ""  # positive, negative, correction, none
    context: dict = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class PreferenceDimension:
    """A single preference with confidence score."""
    name: str
    value: Any
    confidence: float = 0.5  # 0-1, Bayesian
    observations: int = 0
    last_updated: str = ""
    sources: list = field(default_factory=list)  # correction, explicit, implicit


@dataclass
class RoutinePattern:
    """A detected daily routine pattern."""
    hour: int
    minute: int
    weekday: int  # 0=Mon..6=Sun
    action_type: str
    description: str
    frequency: int = 0
    confidence: float = 0.0
    last_observed: str = ""


class DeepUserLearner:
    """Comprehensive user learning system."""

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self._local = threading.Lock()
        self._init_db()

    def _init_db(self):
        DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_input TEXT,
                    ai_response TEXT,
                    action_taken TEXT,
                    success INTEGER,
                    user_feedback TEXT,
                    context TEXT
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    observations INTEGER DEFAULT 0,
                    last_updated TEXT,
                    sources TEXT DEFAULT '[]',
                    PRIMARY KEY (user_id, name)
                );

                CREATE TABLE IF NOT EXISTS routines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    hour INTEGER,
                    minute INTEGER,
                    weekday INTEGER,
                    action_type TEXT,
                    description TEXT,
                    frequency INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0.0,
                    last_observed TEXT
                );

                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    original_action TEXT,
                    corrected_action TEXT,
                    similarity REAL,
                    inferred Preference TEXT,
                    context TEXT
                );

                CREATE TABLE IF NOT EXISTS app_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    app_name TEXT,
                    timestamp TEXT,
                    duration_seconds REAL,
                    context TEXT
                );

                CREATE TABLE IF NOT EXISTS task_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_type TEXT,
                    task_description TEXT,
                    success INTEGER,
                    duration_seconds REAL,
                    quality_rating REAL,
                    user_satisfaction TEXT,
                    timestamp TEXT
                );

                CREATE TABLE IF NOT EXISTS knowledge_graph (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    entity TEXT,
                    relation TEXT,
                    value TEXT,
                    confidence REAL DEFAULT 0.5,
                    source TEXT,
                    last_updated TEXT
                );
            """)
        finally:
            conn.close()

    # ── Conversation Learning ────────────────────────────────────────────

    def observe_conversation(self, user_input: str, ai_response: str,
                             action_taken: str = "", success: bool = True,
                             user_feedback: str = "none", context: dict = None):
        """Record and learn from a conversation turn."""
        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(
                    """INSERT INTO conversations
                       (user_id, timestamp, user_input, ai_response, action_taken,
                        success, user_feedback, context)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, datetime.now().isoformat(), user_input, ai_response,
                     action_taken, 1 if success else 0, user_feedback,
                     json.dumps(context or {}))
                )
                conn.commit()
            finally:
                conn.close()

        # Learn from this interaction
        self._learn_from_conversation(user_input, ai_response, action_taken,
                                       success, user_feedback, context or {})

    def _learn_from_conversation(self, user_input: str, ai_response: str,
                                  action_taken: str, success: bool,
                                  user_feedback: str, context: dict):
        """Extract learnings from a conversation."""
        input_lower = user_input.lower().strip()

        # 1. Learn communication style
        self._learn_communication_style(user_input)

        # 2. Learn task preferences
        if action_taken:
            self._update_preference("preferred_action_" + action_taken, success,
                                    "conversation", confidence_delta=0.05)

        # 3. Learn from corrections
        if user_feedback == "correction":
            self._learn_from_correction(user_input, ai_response, context)

        # 4. Learn from positive feedback
        if user_feedback == "positive":
            self._update_preference("task_quality_" + (action_taken or "general"),
                                    True, "explicit_approval", confidence_delta=0.1)

        # 5. Learn time patterns
        self._learn_time_pattern(action_taken or "conversation", user_input)

        # 6. Learn vocabulary and topics
        self._learn_vocabulary(user_input)

        # 7. Learn app preferences
        if context.get("app"):
            self._learn_app_usage(context["app"], context.get("duration", 0))

    def _learn_communication_style(self, text: str):
        """Learn user's communication style from their messages."""
        words = text.split()
        word_count = len(words)

        # Brevity preference
        if word_count <= 3:
            self._update_preference("brevity", "terse", "implicit",
                                    confidence_delta=0.03)
        elif word_count >= 20:
            self._update_preference("brevity", "verbose", "implicit",
                                    confidence_delta=0.03)

        # Formality signals
        formal_words = {"please", "kindly", "would", "could", "appreciate", "thank"}
        casual_words = {"hey", "yo", "sup", "cool", "awesome", "btw", "thx", "np", "lol"}

        formal_count = sum(1 for w in formal_words if w in text.lower())
        casual_count = sum(1 for w in casual_words if w in text.lower())

        if formal_count > casual_count:
            self._update_preference("formality", "formal", "implicit",
                                    confidence_delta=0.02)
        elif casual_count > formal_count:
            self._update_preference("formality", "casual", "implicit",
                                    confidence_delta=0.02)

        # Question vs command style
        if "?" in text:
            self._update_preference("communication_style", "question", "implicit",
                                    confidence_delta=0.02)
        elif any(w in text.lower() for w in ["do ", "make ", "create ", "open ", "run "]):
            self._update_preference("communication_style", "command", "implicit",
                                    confidence_delta=0.02)

    def _learn_from_correction(self, original: str, corrected: str, context: dict):
        """Learn from user corrections."""
        # Store correction
        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(
                    """INSERT INTO corrections
                       (user_id, timestamp, original_action, corrected_action,
                        similarity, context)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (self.user_id, datetime.now().isoformat(), original, corrected,
                     0.5, json.dumps(context))
                )
                conn.commit()
            finally:
                conn.close()

        # Infer what went wrong
        orig_lower = original.lower()
        corr_lower = corrected.lower()

        # Style corrections
        if "more formal" in corr_lower or "less casual" in corr_lower:
            self._update_preference("formality", "formal", "correction",
                                    confidence_delta=0.15)
        elif "more casual" in corr_lower or "less formal" in corr_lower:
            self._update_preference("formality", "casual", "correction",
                                    confidence_delta=0.15)

        # Brevity corrections
        if "shorter" in corr_lower or "brief" in corr_lower or "concise" in corr_lower:
            self._update_preference("brevity", "terse", "correction",
                                    confidence_delta=0.15)
        elif "more detail" in corr_lower or "longer" in corr_lower:
            self._update_preference("brevity", "verbose", "correction",
                                    confidence_delta=0.15)

    def _learn_time_pattern(self, action_type: str, context: str = ""):
        """Learn when user does certain actions."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute // 15 * 15  # Round to 15-min intervals
        weekday = now.weekday()

        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                # Check if pattern exists
                existing = conn.execute(
                    """SELECT id, frequency, confidence FROM routines
                       WHERE user_id=? AND hour=? AND minute=? AND weekday=?
                       AND action_type=?""",
                    (self.user_id, hour, minute, weekday, action_type)
                ).fetchone()

                if existing:
                    # Update frequency and confidence
                    new_freq = existing[1] + 1
                    new_conf = min(0.95, 0.1 + (new_freq * 0.05))
                    conn.execute(
                        """UPDATE routines SET frequency=?, confidence=?,
                           last_observed=? WHERE id=?""",
                        (new_freq, new_conf, datetime.now().isoformat(), existing[0])
                    )
                else:
                    # New pattern
                    conn.execute(
                        """INSERT INTO routines
                           (user_id, hour, minute, weekday, action_type,
                            description, frequency, confidence, last_observed)
                           VALUES (?, ?, ?, ?, ?, ?, 1, 0.1, ?)""",
                        (self.user_id, hour, minute, weekday, action_type,
                         context[:200], datetime.now().isoformat())
                    )
                conn.commit()
            finally:
                conn.close()

    def _learn_vocabulary(self, text: str):
        """Learn user's vocabulary and topics of interest."""
        words = text.lower().split()
        # Extract meaningful words (skip common ones)
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "can", "shall",
                      "i", "you", "he", "she", "it", "we", "they", "me", "him",
                      "her", "us", "them", "my", "your", "his", "its", "our",
                      "their", "this", "that", "these", "those", "in", "on", "at",
                      "to", "for", "of", "with", "by", "from", "as", "into",
                      "and", "or", "but", "not", "no", "so", "if", "then",
                      "please", "hey", "jarvis", "hi", "hello"}

        for word in words:
            word = word.strip(".,!?;:\"'()[]{}")
            if len(word) > 2 and word not in stopwords:
                self._update_knowledge("vocabulary", word, "frequent_use",
                                       confidence_delta=0.01)

    def _learn_app_usage(self, app_name: str, duration: float = 0):
        """Learn app usage patterns."""
        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(
                    """INSERT INTO app_usage
                       (user_id, app_name, timestamp, duration_seconds)
                       VALUES (?, ?, ?, ?)""",
                    (self.user_id, app_name, datetime.now().isoformat(), duration)
                )
                conn.commit()
            finally:
                conn.close()

        # Update app preference
        self._update_preference(f"uses_app_{app_name}", True, "observation",
                                confidence_delta=0.05)

    # ── Preference Management ────────────────────────────────────────────

    def _update_preference(self, name: str, value: Any, source: str,
                           confidence_delta: float = 0.05):
        """Update a preference using Bayesian updating."""
        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                existing = conn.execute(
                    """SELECT value, confidence, observations, sources
                       FROM preferences WHERE user_id=? AND name=?""",
                    (self.user_id, name)
                ).fetchone()

                if existing:
                    old_value, old_conf, obs_count, sources_json = existing
                    sources = json.loads(sources_json) if sources_json else []

                    # Bayesian update
                    new_conf = min(0.99, old_conf + confidence_delta * (1 - old_conf))
                    new_obs = obs_count + 1
                    if source not in sources:
                        sources.append(source)

                    conn.execute(
                        """UPDATE preferences SET value=?, confidence=?,
                           observations=?, last_updated=?, sources=?
                           WHERE user_id=? AND name=?""",
                        (str(value), new_conf, new_obs,
                         datetime.now().isoformat(), json.dumps(sources),
                         self.user_id, name)
                    )
                else:
                    conn.execute(
                        """INSERT INTO preferences
                           (user_id, name, value, confidence, observations,
                            last_updated, sources)
                           VALUES (?, ?, ?, ?, 1, ?, ?)""",
                        (self.user_id, name, str(value), confidence_delta,
                         datetime.now().isoformat(), json.dumps([source]))
                    )
                conn.commit()
            finally:
                conn.close()

    def get_preference(self, name: str) -> Optional[dict]:
        """Get a learned preference."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            row = conn.execute(
                """SELECT value, confidence, observations, sources
                   FROM preferences WHERE user_id=? AND name=?""",
                (self.user_id, name)
            ).fetchone()
            if row:
                return {
                    "value": row[0],
                    "confidence": row[1],
                    "observations": row[2],
                    "sources": json.loads(row[3]) if row[3] else []
                }
        finally:
            conn.close()
        return None

    def get_all_preferences(self) -> dict:
        """Get all learned preferences."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute(
                """SELECT name, value, confidence, observations
                   FROM preferences WHERE user_id=?
                   ORDER BY confidence DESC""",
                (self.user_id,)
            ).fetchall()
            return {
                row[0]: {"value": row[1], "confidence": row[2], "observations": row[3]}
                for row in rows
            }
        finally:
            conn.close()

    # ── Knowledge Graph ──────────────────────────────────────────────────

    def _update_knowledge(self, entity: str, value: str, relation: str,
                          source: str = "observation", confidence_delta: float = 0.05):
        """Update the knowledge graph."""
        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                existing = conn.execute(
                    """SELECT confidence FROM knowledge_graph
                       WHERE user_id=? AND entity=? AND relation=? AND value=?""",
                    (self.user_id, entity, relation, value)
                ).fetchone()

                if existing:
                    new_conf = min(0.99, existing[0] + confidence_delta)
                    conn.execute(
                        """UPDATE knowledge_graph SET confidence=?, last_updated=?
                           WHERE user_id=? AND entity=? AND relation=? AND value=?""",
                        (new_conf, datetime.now().isoformat(),
                         self.user_id, entity, relation, value)
                    )
                else:
                    conn.execute(
                        """INSERT INTO knowledge_graph
                           (user_id, entity, relation, value, confidence,
                            source, last_updated)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (self.user_id, entity, relation, value, confidence_delta,
                         source, datetime.now().isoformat())
                    )
                conn.commit()
            finally:
                conn.close()

    def query_knowledge(self, entity: str = None, relation: str = None) -> list:
        """Query the knowledge graph."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            query = "SELECT entity, relation, value, confidence FROM knowledge_graph WHERE user_id=?"
            params = [self.user_id]
            if entity:
                query += " AND entity=?"
                params.append(entity)
            if relation:
                query += " AND relation=?"
                params.append(relation)
            query += " ORDER BY confidence DESC LIMIT 50"

            rows = conn.execute(query, params).fetchall()
            return [{"entity": r[0], "relation": r[1], "value": r[2], "confidence": r[3]}
                    for r in rows]
        finally:
            conn.close()

    # ── Routine Detection ────────────────────────────────────────────────

    def get_detected_routines(self, min_confidence: float = 0.3) -> list:
        """Get detected daily routines."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute(
                """SELECT hour, minute, weekday, action_type, description,
                          frequency, confidence
                   FROM routines WHERE user_id=? AND confidence >= ?
                   ORDER BY confidence DESC""",
                (self.user_id, min_confidence)
            ).fetchall()
            return [
                {
                    "hour": r[0], "minute": r[1], "weekday": r[2],
                    "action": r[3], "description": r[4],
                    "frequency": r[5], "confidence": r[6]
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ── Task Outcome Learning ────────────────────────────────────────────

    def record_task_outcome(self, task_type: str, description: str,
                            success: bool, duration: float = 0,
                            quality: float = 0, satisfaction: str = "unknown"):
        """Record task outcome for learning."""
        with self._local:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(
                    """INSERT INTO task_outcomes
                       (user_id, task_type, task_description, success,
                        duration_seconds, quality_rating, user_satisfaction, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, task_type, description, 1 if success else 0,
                     duration, quality, satisfaction, datetime.now().isoformat())
                )
                conn.commit()
            finally:
                conn.close()

        # Learn from outcome
        if success:
            self._update_preference(f"task_success_{task_type}", True, "outcome",
                                    confidence_delta=0.05)
        else:
            self._update_preference(f"task_success_{task_type}", False, "outcome",
                                    confidence_delta=0.05)

    # ── Context Retrieval ────────────────────────────────────────────────

    def get_relevant_context(self, current_input: str) -> dict:
        """Get relevant learned context for current input."""
        context = {
            "preferences": {},
            "routines": [],
            "recent_conversations": [],
            "knowledge": [],
        }

        # Get high-confidence preferences
        prefs = self.get_all_preferences()
        context["preferences"] = {
            k: v for k, v in prefs.items()
            if v["confidence"] > 0.3
        }

        # Get routines for current time
        now = datetime.now()
        context["routines"] = [
            r for r in self.get_detected_routines(min_confidence=0.2)
            if r["hour"] == now.hour
        ]

        # Get recent conversations
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute(
                """SELECT user_input, ai_response, action_taken, success
                   FROM conversations WHERE user_id=?
                   ORDER BY timestamp DESC LIMIT 10""",
                (self.user_id,)
            ).fetchall()
            context["recent_conversations"] = [
                {"input": r[0], "response": r[1], "action": r[2], "success": r[3]}
                for r in rows
            ]
        finally:
            conn.close()

        # Get relevant knowledge
        words = current_input.lower().split()
        for word in words:
            if len(word) > 3:
                knowledge = self.query_knowledge(entity=word)
                context["knowledge"].extend(knowledge)

        return context

    # ── Learning Summary ─────────────────────────────────────────────────

    def get_learning_summary(self) -> dict:
        """Get a summary of what the system has learned."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conv_count = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE user_id=?",
                (self.user_id,)
            ).fetchone()[0]

            pref_count = conn.execute(
                "SELECT COUNT(*) FROM preferences WHERE user_id=?",
                (self.user_id,)
            ).fetchone()[0]

            routine_count = conn.execute(
                "SELECT COUNT(*) FROM routines WHERE user_id=? AND confidence > 0.3",
                (self.user_id,)
            ).fetchone()[0]

            correction_count = conn.execute(
                "SELECT COUNT(*) FROM corrections WHERE user_id=?",
                (self.user_id,)
            ).fetchone()[0]

            task_count = conn.execute(
                "SELECT COUNT(*) FROM task_outcomes WHERE user_id=?",
                (self.user_id,)
            ).fetchone()[0]

            knowledge_count = conn.execute(
                "SELECT COUNT(*) FROM knowledge_graph WHERE user_id=?",
                (self.user_id,)
            ).fetchone()[0]

            top_prefs = conn.execute(
                """SELECT name, value, confidence FROM preferences
                   WHERE user_id=? ORDER BY confidence DESC LIMIT 10""",
                (self.user_id,)
            ).fetchall()

            return {
                "conversations_learned": conv_count,
                "preferences_tracked": pref_count,
                "routines_detected": routine_count,
                "corrections_analyzed": correction_count,
                "tasks_recorded": task_count,
                "knowledge_entries": knowledge_count,
                "top_preferences": [
                    {"name": r[0], "value": r[1], "confidence": r[2]}
                    for r in top_prefs
                ]
            }
        finally:
            conn.close()


# ── Singleton ──────────────────────────────────────────────────────────

_learner_instance = None

def get_learner(user_id: str = "local") -> DeepUserLearner:
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = DeepUserLearner(user_id)
    return _learner_instance


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="[LEARNER] %(message)s")
    learner = get_learner()
    print(json.dumps(learner.get_learning_summary(), indent=2))
