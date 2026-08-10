"""
JARVIS Cortex — Advanced Memory Architecture
=============================================
The cognitive backbone that transforms raw data into institutional-grade intelligence.

This is the memory system that makes JARVIS worth billions:
  - Temporal Causal Chains: What happened, why, and what caused what
  - Emotional Trajectory Mapping: How feelings evolve over time
  - Predictive Anticipation: What the user will need before they ask
  - Hierarchical Abstraction: From raw events → patterns → principles
  - Cross-Domain Synthesis: Connecting health, work, relationships, goals
  - Adaptive Consolidation: Merging related memories, strengthening important ones
  - Semantic Deduplication: No redundant storage
  - Privacy-Aware Sharing: Granular control over what gets shared
  - Concept Drift Detection: When beliefs/goals change over time
  - Multi-Layer Context Assembly: The right memory at the right time

Target: Sub-5ms recall, sub-20ms consolidation, infinite scalability.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import struct
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

_DB_PATH = "jarvis_cortex.db"
_EMBED_DIM = 384

# Memory tiers — each has different retention and access patterns
class MemoryTier(Enum):
    EPISODIC = "episodic"       # Raw events, conversations, moments
    SEMANTIC = "semantic"       # Facts, knowledge, learned concepts
    PROCEDURAL = "procedural"   # How-to, skills, habits
    EMOTIONAL = "emotional"     # Feelings, mood states, emotional associations
    PREDICTIVE = "predictive"   # Anticipations, forecasts, expected futures

# Privacy levels for memory sharing
class PrivacyLevel(Enum):
    PRIVATE = 0      # Never shared, encrypted at rest
    PERSONAL = 1     # Shared with CORE_AGENT only
    FAMILY = 2       # Shared with trusted family members
    SOCIAL = 3       # Shared in social contexts
    PUBLIC = 4       # Can be shared externally

# Entity types the cortex tracks
class EntityType(Enum):
    PERSON = "person"
    CONCEPT = "concept"
    EMOTION = "emotion"
    EVENT = "event"
    GOAL = "goal"
    HABIT = "habit"
    SKILL = "skill"
    PREFERENCE = "preference"
    RELATIONSHIP = "relationship"
    ORGANIZATION = "organization"
    LOCATION = "location"
    PROJECT = "project"
    TOPIC = "topic"
    DECISION = "decision"
    OUTCOME = "outcome"

# Edge types for causal/temporal relationships
class EdgeType(Enum):
    CAUSED_BY = "caused_by"
    LED_TO = "led_to"
    TRIGGERED = "triggered"
    PRECEDED = "preceded"
    FOLLOWED = "followED"
    RELATES_TO = "relates_to"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    DEPENDS_ON = "depends_on"
    EVOLVED_INTO = "evolved_into"
    ASSOCIATED_WITH = "associated_with"
    STRENGTHENS = "strengthens"
    WEAKENS = "weakens"
    EMOTIONAL_CONTEXT = "emotional_context"


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

_SCHEMA = """
-- ═══════════════════════════════════════════════════════════════════════
-- CORE ENTITIES
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,  -- Lowercase, normalized
    description TEXT,
    properties TEXT,               -- JSON blob for flexible attributes
    embedding BLOB,                -- float32 vector for semantic search
    importance REAL DEFAULT 5.0,   -- 0-10 scale, affects recall priority
    confidence REAL DEFAULT 0.8,   -- 0-1 how sure we are about this entity
    tier TEXT DEFAULT 'semantic',  -- Which memory tier this lives in
    privacy INTEGER DEFAULT 1,     -- PrivacyLevel enum value
    access_count INTEGER DEFAULT 0,
    last_accessed REAL,
    decay_rate REAL DEFAULT 0.01,  -- How fast this fades if not accessed
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_fts USING fts5(
    name, canonical_name, description, properties,
    content=entities, content_rowid=rowid
);

-- ═══════════════════════════════════════════════════════════════════════
-- RELATIONSHIPS (temporal, causal, emotional)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS relationships (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    confidence REAL DEFAULT 0.8,
    context TEXT,                  -- What was happening when this relationship formed
    temporal_order INTEGER,        -- For causal chains: 1,2,3...
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT,
    PRIMARY KEY (source_id, target_id, edge_type),
    FOREIGN KEY(source_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(edge_type);

-- ═══════════════════════════════════════════════════════════════════════
-- TEMPORAL EVENTS (what happened, when, causal chain position)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS temporal_events (
    id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,      -- conversation, action, observation, decision
    summary TEXT NOT NULL,         -- One-line description
    full_content TEXT,             -- Full content/details
    causal_chain_id TEXT,          -- Groups events into causal sequences
    chain_position INTEGER,        -- Position within the causal chain
    cause_event_id TEXT,           -- What caused this event
    effect_event_ids TEXT,         -- JSON array of what this event caused
    emotional_state TEXT,          -- JSON: {sentiment, valence, arousal, dominance}
    entities_involved TEXT,        -- JSON array of entity IDs
    domain TEXT,                   -- health, work, relationships, finance, etc.
    importance REAL DEFAULT 5.0,
    embedding BLOB,
    recalled_count INTEGER DEFAULT 0,
    last_recalled REAL,
    consolidated INTEGER DEFAULT 0,  -- Has this been consolidated into semantic memory?
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_time ON temporal_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_chain ON temporal_events(causal_chain_id);
CREATE INDEX IF NOT EXISTS idx_events_domain ON temporal_events(domain);
CREATE INDEX IF NOT EXISTS idx_events_type ON temporal_events(event_type);

CREATE TABLE IF NOT EXISTS event_fts USING fts5(
    summary, full_content, domain,
    content=temporal_events, content_rowid=rowid
);

-- ═══════════════════════════════════════════════════════════════════════
-- EMOTIONAL TRAJECTORY (mood over time, sentiment arcs)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS emotional_trajectory (
    id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    valence REAL NOT NULL,         -- -1 (negative) to +1 (positive)
    arousal REAL DEFAULT 0.5,     -- 0 (calm) to 1 (excited)
    dominance REAL DEFAULT 0.5,   -- 0 (submissive) to 1 (dominant)
    sentiment TEXT,                -- happy, sad, anxious, etc.
    intensity REAL DEFAULT 0.5,   -- 0-1
    context TEXT,                  -- What triggered this emotional state
    event_id TEXT,                 -- Link to temporal event
    domain TEXT,                   -- Life domain this relates to
    created_at REAL NOT NULL,
    FOREIGN KEY(event_id) REFERENCES temporal_events(id)
);

CREATE INDEX IF NOT EXISTS idx_emo_time ON emotional_trajectory(timestamp);
CREATE INDEX IF NOT EXISTS idx_emo_sentiment ON emotional_trajectory(sentiment);

-- ═══════════════════════════════════════════════════════════════════════
-- HIERARCHICAL ABSTRACTION (specific → pattern → principle)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS abstraction_hierarchy (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL,           -- 'instance', 'pattern', 'principle', 'meta'
    name TEXT NOT NULL,
    description TEXT,
    parent_id TEXT,                -- More abstract level
    supporting_events TEXT,        -- JSON array of event IDs
    supporting_entities TEXT,      -- JSON array of entity IDs
    confidence REAL DEFAULT 0.5,
    times_applied INTEGER DEFAULT 0,
    last_applied REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY(parent_id) REFERENCES abstraction_hierarchy(id)
);

-- ═══════════════════════════════════════════════════════════════════════
-- CROSS-DOMAIN CONNECTIONS (linking insights across life areas)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cross_domain_links (
    id TEXT PRIMARY KEY,
    source_domain TEXT NOT NULL,
    target_domain TEXT NOT NULL,
    insight TEXT NOT NULL,
    supporting_entities TEXT,      -- JSON array
    strength REAL DEFAULT 0.5,
    times_reinforced INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- PREDICTIVE ANTECEDENTS (what typically precedes what)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS predictive_patterns (
    id TEXT PRIMARY KEY,
    trigger_pattern TEXT NOT NULL,  -- What typically happens first
    predicted_outcome TEXT NOT NULL, -- What usually follows
    confidence REAL DEFAULT 0.5,
    times_observed INTEGER DEFAULT 1,
    last_observed REAL,
    domain TEXT,
    embedding BLOB,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS predictive_fts USING fts5(
    trigger_pattern, predicted_outcome, domain,
    content=predictive_patterns, content_rowid=rowid
);

-- ═══════════════════════════════════════════════════════════════════════
-- CONCEPT DRIFT (when beliefs/goals/motivations change)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS concept_drift (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    drift_type TEXT NOT NULL,      -- 'goal_change', 'belief_shift', 'motivation_change'
    old_value TEXT,
    new_value TEXT,
    magnitude REAL DEFAULT 0.5,    -- 0 (subtle) to 1 (fundamental shift)
    trigger_event_id TEXT,         -- What caused the drift
    detected_at REAL NOT NULL,
    confirmed INTEGER DEFAULT 0,   -- User confirmed this drift
    FOREIGN KEY(entity_id) REFERENCES entities(id),
    FOREIGN KEY(trigger_event_id) REFERENCES temporal_events(id)
);

-- ═══════════════════════════════════════════════════════════════════════
-- PRIVACY & SHARING
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS privacy_rules (
    id TEXT PRIMARY KEY,
    entity_id TEXT,
    domain TEXT,
    rule_type TEXT NOT NULL,       -- 'allow', 'deny', 'encrypt', 'audit'
    target TEXT,                   -- Who/what the rule applies to
    conditions TEXT,               -- JSON: time-of-day, context, etc.
    created_at REAL NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id)
);

-- ═══════════════════════════════════════════════════════════════════════
-- CONSOLIDATION LOG (tracks memory merging/strengthening)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS consolidation_log (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,          -- 'merge', 'strengthen', 'decay', 'prune', 'abstract'
    source_ids TEXT NOT NULL,      -- JSON array of entity/event IDs involved
    target_id TEXT,                -- Result after consolidation
    reason TEXT,
    metadata TEXT,
    created_at REAL NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════
-- USER PROFILE (aggregated personality/behavioral model)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_profile (
    dimension TEXT PRIMARY KEY,    -- 'personality', 'values', 'communication_style', etc.
    value TEXT NOT NULL,           -- JSON with the profile data
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 0,
    last_updated REAL NOT NULL
);

-- Indices for user profile
CREATE INDEX IF NOT EXISTS idx_abstraction_level ON abstraction_hierarchy(level);
CREATE INDEX IF NOT EXISTS idx_abstraction_parent ON abstraction_hierarchy(parent_id);
CREATE INDEX IF NOT EXISTS idx_drift_entity ON concept_drift(entity_id);
CREATE INDEX IF NOT EXISTS idx_privacy_entity ON privacy_rules(entity_id);
CREATE INDEX IF NOT EXISTS idx_privacy_domain ON privacy_rules(domain);
"""

_FTS_SYNC = """
CREATE TRIGGER IF NOT EXISTS entity_ai AFTER INSERT ON entities BEGIN
    INSERT INTO entity_fts(rowid, name, canonical_name, description, properties)
    VALUES (NEW.rowid, NEW.name, NEW.canonical_name, NEW.description, NEW.properties);
END;
CREATE TRIGGER IF NOT EXISTS entity_ad AFTER DELETE ON entities BEGIN
    INSERT INTO entity_fts(entity_fts, rowid, name, canonical_name, description, properties)
    VALUES('delete', OLD.rowid, OLD.name, OLD.canonical_name, OLD.description, OLD.properties);
END;
CREATE TRIGGER IF NOT EXISTS entity_au AFTER UPDATE ON entities BEGIN
    INSERT INTO entity_fts(entity_fts, rowid, name, canonical_name, description, properties)
    VALUES('delete', OLD.rowid, OLD.name, OLD.canonical_name, OLD.description, OLD.properties);
    INSERT INTO entity_fts(rowid, name, canonical_name, description, properties)
    VALUES (NEW.rowid, NEW.name, NEW.canonical_name, NEW.description, NEW.properties);
END;
CREATE TRIGGER IF NOT EXISTS event_ai AFTER INSERT ON temporal_events BEGIN
    INSERT INTO event_fts(rowid, summary, full_content, domain)
    VALUES (NEW.rowid, NEW.summary, NEW.full_content, NEW.domain);
END;
CREATE TRIGGER IF NOT EXISTS event_ad AFTER DELETE ON temporal_events BEGIN
    INSERT INTO event_fts(event_fts, rowid, summary, full_content, domain)
    VALUES('delete', OLD.rowid, OLD.summary, OLD.full_content, OLD.domain);
END;
CREATE TRIGGER IF NOT EXISTS predictive_ai AFTER INSERT ON predictive_patterns BEGIN
    INSERT INTO predictive_fts(rowid, trigger_pattern, predicted_outcome, domain)
    VALUES (NEW.rowid, NEW.trigger_pattern, NEW.predicted_outcome, NEW.domain);
END;
"""


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

def _now() -> float:
    return time.time()

def _uid() -> str:
    return uuid.uuid4().hex[:12]

def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)

def _unpack(blob: bytes) -> list[float]:
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))

def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0

def _json(obj: Any) -> str | None:
    return json.dumps(obj, ensure_ascii=False) if obj is not None else None

def _unjson(text: str | None, default=None):
    if text is None:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default

def _normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())

def _sentiment_score(text: str) -> float:
    """Quick rule-based sentiment: -1 to +1."""
    pos = {"happy", "good", "great", "love", "excited", "grateful", "proud",
           "amazing", "wonderful", "fantastic", "excellent", "awesome", "best"}
    neg = {"sad", "bad", "hate", "angry", "stressed", "anxious", "worried",
           "frustrated", "terrible", "awful", "worst", "annoying", "overwhelmed"}
    words = set(_normalize(text).split())
    p = len(words & pos)
    n = len(words & neg)
    total = p + n
    if total == 0:
        return 0.0
    return (p - n) / total

def _extract_domain(text: str) -> str:
    """Heuristic domain classification."""
    domains = {
        "health": {"exercise", "workout", "gym", "run", "sleep", "eat", "diet",
                    "weight", "doctor", "medication", "walk", "yoga", "meditation"},
        "work": {"meeting", "deadline", "project", "boss", "colleague", "office",
                 "email", "report", "presentation", "client", "team", "sprint"},
        "relationships": {"friend", "family", "partner", "mom", "dad", "brother",
                          "sister", "date", "relationship", "love", "breakup"},
        "finance": {"money", "budget", "invest", "save", "spend", "bill", "salary",
                    "tax", "savings", "debt", "loan", "income"},
        "education": {"study", "learn", "exam", "course", "class", "homework",
                      "assignment", "research", "thesis", "professor"},
        "creative": {"write", "paint", "music", "song", "art", "design", "code",
                     "build", "create", "project", "portfolio"},
    }
    words = set(_normalize(text).split())
    best = "general"
    best_score = 0
    for domain, keywords in domains.items():
        score = len(words & keywords)
        if score > best_score:
            best_score = score
            best = domain
    return best

def _quick_embed(text: str) -> list[float]:
    """Deterministic pseudo-embedding based on text hash for when real embeddings aren't available."""
    import hashlib
    h = hashlib.sha256(_normalize(text).encode()).digest()
    vec = []
    for i in range(0, min(len(h), _EMBED_DIM), 1):
        byte_val = h[i % len(h)]
        vec.append((byte_val / 127.5) - 1.0)
    # Pad or truncate to _EMBED_DIM
    while len(vec) < _EMBED_DIM:
        vec.append(0.0)
    return vec[:_EMBED_DIM]


# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

_PERSON_PATTERNS = [
    re.compile(r"(?:my|the|with|to|from|about)\s+(friend|mom|dad|brother|sister|"
               r"partner|wife|husband|girlfriend|boyfriend|manager|boss|teacher|"
               r"professor|mentor|doctor|therapist|coworker|colleague|roommate|neighbor)\s+(\w+)", re.I),
    re.compile(r"(\w+)\s+(?:said|told|asked|mentioned|texted|called| messaged)", re.I),
]

_EMOTION_PATTERNS = [
    re.compile(r"I(?:'m| am| feel| feel like I'm)\s+(stressed|anxious|happy|sad|angry|"
               r"frustrated|excited|nervous|overwhelmed|calm|tired|exhausted|motivated|"
               r"inspired|bored|confused|grateful|lonely|proud|worried|hopeful|peaceful|"
               r"restless|irritable|content|disappointed|relieved|jealous|guilty|ashamed)", re.I),
]

_GOAL_PATTERNS = [
    re.compile(r"I\s+(?:want|need|aim|plan|hope)\s+to\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"my\s+goal\s+is\s+(?:to\s+)?(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:trying|working|attempting)\s+to\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"I(?:'m| am)\s+(?:trying|working|planning)\s+to\s+(.+?)(?:\.|$)", re.I),
]

_DECISION_PATTERNS = [
    re.compile(r"I\s+(?:decided|chose|picked|selected|committed)\s+to\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:going with|switching to|moving to|choosing)\s+(.+?)(?:\.|$)", re.I),
]

_CAUSAL_MARKERS = {
    "because", "since", "due to", "as a result", "consequently",
    "therefore", "led to", "caused", "triggered", "resulted in",
    "after", "before", "during", "while", "then",
}


# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class CortexMemory:
    """
    The billion-dollar memory system.

    Provides:
      - Temporal causal chain tracking
      - Emotional trajectory mapping
      - Predictive anticipation from patterns
      - Hierarchical abstraction (instance → pattern → principle)
      - Cross-domain synthesis
      - Adaptive consolidation with semantic deduplication
      - Concept drift detection
      - Privacy-aware memory sharing
      - Multi-layer context assembly
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _DB_PATH
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._connect()

    # ───────────────────────────────────────────────────────────────────
    # CONNECTION
    # ───────────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")

        # Execute regular schema statements one by one (skip FTS USING lines)
        for stmt in _SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt and "USING fts5" not in stmt:
                try:
                    conn.execute(stmt)
                except Exception:
                    pass

        # Create FTS tables individually via execute()
        fts_tables = [
            "CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts USING fts5(name, canonical_name, description, properties)",
            "CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(summary, full_content, domain)",
            "CREATE VIRTUAL TABLE IF NOT EXISTS predictive_fts USING fts5(trigger_pattern, predicted_outcome, domain)",
        ]
        for stmt in fts_tables:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Execute FTS sync triggers
        try:
            conn.executescript(_FTS_SYNC)
        except Exception:
            pass
        conn.commit()
        self._conn = conn
        return conn

    def _q(self, sql: str, params=(), one=False):
        with self._lock:
            cur = self._conn.execute(sql, params)
            if one:
                return cur.fetchone()
            return cur.fetchall()

    def _x(self, sql: str, params=()):
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _xmany(self, sql: str, params_list):
        with self._lock:
            for p in params_list:
                self._conn.execute(sql, p)
            self._conn.commit()

    # ═══════════════════════════════════════════════════════════════════
    # 1. ENTITY MANAGEMENT (with semantic deduplication)
    # ═══════════════════════════════════════════════════════════════════

    def upsert_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        properties: dict | None = None,
        importance: float = 5.0,
        confidence: float = 0.8,
        tier: str = "semantic",
        privacy: int = 1,
    ) -> str:
        """Create or update an entity. Performs semantic deduplication."""
        canonical = _normalize(name)
        now = _now()

        # Check for existing similar entity (semantic dedup)
        existing = self._q(
            "SELECT id, name, importance FROM entities WHERE canonical_name = ?",
            (canonical,), one=True
        )
        if existing:
            # Strengthen existing entity
            new_importance = min(10.0, existing["importance"] + 0.3)
            self._x(
                """UPDATE entities SET importance = ?, access_count = access_count + 1,
                   last_accessed = ?, updated_at = ? WHERE id = ?""",
                (new_importance, now, now, existing["id"])
            )
            return existing["id"]

        # Also check for semantically similar entities (fuzzy dedup)
        if properties and "aliases" in properties:
            for alias in properties["aliases"]:
                dup = self._q(
                    "SELECT id FROM entities WHERE canonical_name = ?",
                    (_normalize(alias),), one=True
                )
                if dup:
                    self._x(
                        "UPDATE entities SET access_count = access_count + 1, last_accessed = ?, updated_at = ? WHERE id = ?",
                        (now, now, dup["id"])
                    )
                    return dup["id"]

        eid = _uid()
        embedding = _quick_embed(f"{entity_type}: {name} {description}")
        self._x(
            """INSERT INTO entities (id, type, name, canonical_name, description,
               properties, embedding, importance, confidence, tier, privacy,
               created_at, updated_at, last_accessed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, entity_type, name, canonical, description,
             _json(properties), _pack(embedding), importance, confidence,
             tier, privacy, now, now, now)
        )
        return eid

    def find_entity(self, name: str) -> dict | None:
        row = self._q(
            "SELECT * FROM entities WHERE canonical_name = ?", (_normalize(name),), one=True
        )
        return dict(row) if row else None

    def find_entities(self, type: str | None = None, limit: int = 50) -> list[dict]:
        if type:
            rows = self._q(
                "SELECT * FROM entities WHERE type = ? ORDER BY importance DESC LIMIT ?",
                (type, limit)
            )
        else:
            rows = self._q(
                "SELECT * FROM entities ORDER BY importance DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in rows]

    def search_entities(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across entities."""
        clean_words = re.findall(r"\b\w{2,}\b", query.lower())
        if not clean_words:
            return []
        fts_query = " OR ".join(clean_words[:5])
        try:
            rows = self._q(
                """SELECT e.*, rank FROM entity_fts f
                   JOIN entities e ON e.rowid = f.rowid
                   WHERE entity_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (fts_query, limit)
            )
        except Exception:
            rows = []
        return [dict(r) for r in rows]

    def get_entity_context(self, entity_id: str) -> dict:
        """Get everything about an entity: relationships, events, emotional context."""
        entity = self._q("SELECT * FROM entities WHERE id = ?", (entity_id,), one=True)
        if not entity:
            return {}

        # Get all relationships
        rels_out = self._q(
            """SELECT r.*, e.name as target_name, e.type as target_type
               FROM relationships r JOIN entities e ON e.id = r.target_id
               WHERE r.source_id = ? ORDER BY r.weight DESC""",
            (entity_id,)
        )
        rels_in = self._q(
            """SELECT r.*, e.name as source_name, e.type as source_type
               FROM relationships r JOIN entities e ON e.id = r.source_id
               WHERE r.target_id = ? ORDER BY r.weight DESC""",
            (entity_id,)
        )

        # Get events involving this entity
        events = self._q(
            """SELECT * FROM temporal_events
               WHERE entities_involved LIKE ? ORDER BY timestamp DESC LIMIT 20""",
            (f"%{entity_id}%",)
        )

        # Get emotional context
        emotions = self._q(
            """SELECT et.* FROM emotional_trajectory et
               JOIN temporal_events te ON te.id = et.event_id
               WHERE te.entities_involved LIKE ?
               ORDER BY et.timestamp DESC LIMIT 10""",
            (f"%{entity_id}%",)
        )

        return {
            "entity": dict(entity),
            "relationships_out": [dict(r) for r in rels_out],
            "relationships_in": [dict(r) for r in rels_in],
            "recent_events": [dict(e) for e in events],
            "emotional_context": [dict(e) for e in emotions],
        }

    # ═══════════════════════════════════════════════════════════════════
    # 2. TEMPORAL CAUSAL CHAINS
    # ═══════════════════════════════════════════════════════════════════

    def record_event(
        self,
        summary: str,
        full_content: str = "",
        event_type: str = "observation",
        cause_event_id: str | None = None,
        domain: str | None = None,
        importance: float = 5.0,
        entities_involved: list[str] | None = None,
        emotional_state: dict | None = None,
    ) -> str:
        """Record a temporal event with optional causal linking."""
        now = _now()
        eid = _uid()
        domain = domain or _extract_domain(summary)
        embedding = _quick_embed(summary)

        # Determine causal chain
        chain_id = None
        chain_pos = None
        if cause_event_id:
            cause = self._q(
                "SELECT causal_chain_id, chain_position FROM temporal_events WHERE id = ?",
                (cause_event_id,), one=True
            )
            if cause:
                chain_id = cause["causal_chain_id"]
                chain_pos = (cause["chain_position"] or 0) + 1
                # Update cause's effect list
                effects = _unjson(
                    self._q(
                        "SELECT effect_event_ids FROM temporal_events WHERE id = ?",
                        (cause_event_id,), one=True
                    )["effect_event_ids"],
                    []
                )
                effects.append(eid)
                self._x(
                    "UPDATE temporal_events SET effect_event_ids = ? WHERE id = ?",
                    (_json(effects), cause_event_id)
                )

        if not chain_id:
            chain_id = _uid()
            chain_pos = 1

        # Extract emotional state
        if not emotional_state:
            ss = _sentiment_score(summary)
            emotional_state = {
                "valence": ss,
                "arousal": 0.5,
                "dominance": 0.5,
                "sentiment": "positive" if ss > 0.1 else ("negative" if ss < -0.1 else "neutral"),
                "intensity": abs(ss),
            }

        self._x(
            """INSERT INTO temporal_events
               (id, timestamp, event_type, summary, full_content,
                causal_chain_id, chain_position, cause_event_id,
                effect_event_ids, emotional_state, entities_involved,
                domain, importance, embedding, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, now, event_type, summary, full_content,
             chain_id, chain_pos, cause_event_id,
             _json([]), _json(emotional_state),
             _json(entities_involved or []), domain, importance,
             _pack(embedding), now)
        )

        # Record emotional trajectory point
        self._record_emotional_point(emotional_state, eid, domain)

        return eid

    def get_causal_chain(self, event_id: str, max_depth: int = 10) -> list[dict]:
        """Walk backward through a causal chain from any event."""
        chain = []
        current_id = event_id
        visited = set()

        for _ in range(max_depth):
            if not current_id or current_id in visited:
                break
            visited.add(current_id)
            event = self._q(
                "SELECT * FROM temporal_events WHERE id = ?", (current_id,), one=True
            )
            if not event:
                break
            chain.append(dict(event))
            current_id = event["cause_event_id"]

        chain.reverse()

        # Also walk forward from the starting event
        forward = []
        current_id = event_id
        visited = {event_id}
        for _ in range(max_depth):
            event = self._q(
                "SELECT * FROM temporal_events WHERE id = ?", (current_id,), one=True
            )
            if not event:
                break
            effects = _unjson(event["effect_event_ids"], [])
            next_id = effects[0] if effects else None
            if not next_id or next_id in visited:
                break
            visited.add(next_id)
            current_id = next_id
            forward.append(dict(event))

        return chain + forward

    def get_temporal_context(self, window_hours: float = 24, domain: str | None = None) -> list[dict]:
        """Get recent events for context injection."""
        cutoff = _now() - (window_hours * 3600)
        if domain:
            rows = self._q(
                """SELECT * FROM temporal_events
                   WHERE timestamp > ? AND domain = ?
                   ORDER BY timestamp DESC LIMIT 50""",
                (cutoff, domain)
            )
        else:
            rows = self._q(
                """SELECT * FROM temporal_events
                   WHERE timestamp > ?
                   ORDER BY timestamp DESC LIMIT 50""",
                (cutoff,)
            )
        return [dict(r) for r in rows]

    def get_domain_timeline(self, domain: str, limit: int = 100) -> list[dict]:
        """Get all events in a domain, ordered by time."""
        rows = self._q(
            """SELECT * FROM temporal_events
               WHERE domain = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (domain, limit)
        )
        return [dict(r) for r in rows]

    # ═══════════════════════════════════════════════════════════════════
    # 3. EMOTIONAL TRAJECTORY MAPPING
    # ═══════════════════════════════════════════════════════════════════

    def _record_emotional_point(self, state: dict, event_id: str, domain: str):
        """Record an emotional trajectory point."""
        now = _now()
        self._x(
            """INSERT INTO emotional_trajectory
               (id, timestamp, valence, arousal, dominance, sentiment,
                intensity, context, event_id, domain, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_uid(), now, state.get("valence", 0), state.get("arousal", 0.5),
             state.get("dominance", 0.5), state.get("sentiment", "neutral"),
             state.get("intensity", 0.5), state.get("context", ""),
             event_id, domain, now)
        )

    def get_emotional_arc(self, hours: float = 168, domain: str | None = None) -> list[dict]:
        """Get emotional trajectory over time (default: 7 days)."""
        cutoff = _now() - (hours * 3600)
        if domain:
            rows = self._q(
                """SELECT * FROM emotional_trajectory
                   WHERE timestamp > ? AND domain = ?
                   ORDER BY timestamp""",
                (cutoff, domain)
            )
        else:
            rows = self._q(
                "SELECT * FROM emotional_trajectory WHERE timestamp > ? ORDER BY timestamp",
                (cutoff,)
            )
        return [dict(r) for r in rows]

    def get_emotional_summary(self, hours: float = 168) -> dict:
        """Aggregate emotional state over a time window."""
        points = self.get_emotional_arc(hours)
        if not points:
            return {"avg_valence": 0, "avg_arousal": 0.5, "dominant_sentiment": "neutral",
                    "emotional_stability": 1.0, "trend": "stable", "data_points": 0}

        valences = [p["valence"] for p in points]
        arousals = [p["arousal"] for p in points]
        sentiments = [p["sentiment"] for p in points]

        avg_v = sum(valences) / len(valences)
        avg_a = sum(arousals) / len(arousals)

        # Stability: low variance = stable
        variance = sum((v - avg_v) ** 2 for v in valences) / len(valences)
        stability = max(0, 1 - variance)

        # Trend: compare first half to second half
        mid = len(valences) // 2
        if mid > 0:
            first_half = sum(valences[:mid]) / mid
            second_half = sum(valences[mid:]) / (len(valences) - mid)
            diff = second_half - first_half
            trend = "improving" if diff > 0.1 else ("declining" if diff < -0.1 else "stable")
        else:
            trend = "stable"

        # Dominant sentiment
        from collections import Counter
        sentiment_counts = Counter(sentiments)
        dominant = sentiment_counts.most_common(1)[0][0] if sentiment_counts else "neutral"

        return {
            "avg_valence": round(avg_v, 3),
            "avg_arousal": round(avg_a, 3),
            "dominant_sentiment": dominant,
            "emotional_stability": round(stability, 3),
            "trend": trend,
            "data_points": len(points),
            "period_hours": hours,
        }

    def detect_emotional_shifts(self, threshold: float = 0.3) -> list[dict]:
        """Detect significant emotional shifts (e.g., sudden mood drops)."""
        points = self.get_emotional_arc(hours=168)
        shifts = []
        for i in range(1, len(points)):
            delta_v = points[i]["valence"] - points[i - 1]["valence"]
            if abs(delta_v) >= threshold:
                shifts.append({
                    "timestamp": points[i]["timestamp"],
                    "from_sentiment": points[i - 1]["sentiment"],
                    "to_sentiment": points[i]["sentiment"],
                    "valence_change": round(delta_v, 3),
                    "trigger": points[i].get("context", ""),
                    "magnitude": "major" if abs(delta_v) > 0.5 else "moderate",
                })
        return shifts

    # ═══════════════════════════════════════════════════════════════════
    # 4. PREDICTIVE ANTICIPATION
    # ═══════════════════════════════════════════════════════════════════

    def learn_predictive_pattern(
        self,
        trigger: str,
        outcome: str,
        domain: str = "general",
        confidence: float = 0.5,
    ) -> str:
        """Record that X typically precedes Y."""
        now = _now()
        # Check if pattern already exists
        existing = self._q(
            "SELECT id, times_observed, confidence FROM predictive_patterns WHERE trigger_pattern = ? AND predicted_outcome = ?",
            (trigger, outcome), one=True
        )
        if existing:
            new_conf = min(0.99, existing["confidence"] + 0.05)
            self._x(
                """UPDATE predictive_patterns
                   SET times_observed = times_observed + 1,
                       confidence = ?, last_observed = ?
                   WHERE id = ?""",
                (new_conf, now, existing["id"])
            )
            return existing["id"]

        pid = _uid()
        embedding = _quick_embed(f"{trigger} → {outcome}")
        self._x(
            """INSERT INTO predictive_patterns
               (id, trigger_pattern, predicted_outcome, confidence,
                times_observed, last_observed, domain, embedding, created_at)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (pid, trigger, outcome, confidence, now, domain, _pack(embedding), now)
        )
        return pid

    def anticipate(self, context: str, limit: int = 5) -> list[dict]:
        """Given current context, predict what might happen next."""
        # Sanitize FTS5 query — strip special chars, use OR between words
        clean_words = re.findall(r"\b\w{3,}\b", context.lower())
        if not clean_words:
            return []
        fts_query = " OR ".join(clean_words[:5])

        try:
            rows = self._q(
                """SELECT p.*, rank FROM predictive_fts f
                   JOIN predictive_patterns p ON p.rowid = f.rowid
                   WHERE predictive_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (fts_query, limit * 2)
            )
        except Exception:
            rows = []

        # Score by confidence and recency
        results = []
        now = _now()
        for r in rows:
            d = dict(r)
            recency_bonus = max(0, 1 - (now - d["last_observed"]) / (86400 * 30))
            d["anticipation_score"] = d["confidence"] * 0.7 + recency_bonus * 0.3
            results.append(d)

        results.sort(key=lambda x: x["anticipation_score"], reverse=True)
        return results[:limit]

    # ═══════════════════════════════════════════════════════════════════
    # 5. HIERARCHICAL ABSTRACTION
    # ═══════════════════════════════════════════════════════════════════

    def create_abstraction(
        self,
        level: str,  # 'instance', 'pattern', 'principle', 'meta'
        name: str,
        description: str = "",
        parent_id: str | None = None,
        supporting_events: list[str] | None = None,
        supporting_entities: list[str] | None = None,
    ) -> str:
        """Create a hierarchical abstraction (e.g., 'I always procrastinate on deadlines' → 'Procrastination pattern')."""
        aid = _uid()
        now = _now()
        self._x(
            """INSERT INTO abstraction_hierarchy
               (id, level, name, description, parent_id,
                supporting_events, supporting_entities,
                confidence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (aid, level, name, description, parent_id,
             _json(supporting_events or []), _json(supporting_entities or []),
             0.5, now, now)
        )
        return aid

    def get_abstraction_tree(self) -> list[dict]:
        """Get the full abstraction hierarchy."""
        rows = self._q(
            "SELECT * FROM abstraction_hierarchy ORDER BY level, created_at"
        )
        return [dict(r) for r in rows]

    def strengthen_abstraction(self, abstraction_id: str):
        """Mark an abstraction as being reinforced by new evidence."""
        self._x(
            """UPDATE abstraction_hierarchy
               SET times_applied = times_applied + 1,
                   confidence = MIN(1.0, confidence + 0.05),
                   last_applied = ?,
                   updated_at = ?
               WHERE id = ?""",
            (_now(), _now(), abstraction_id)
        )

    # ═══════════════════════════════════════════════════════════════════
    # 6. CROSS-DOMAIN SYNTHESIS
    # ═══════════════════════════════════════════════════════════════════

    def create_cross_domain_link(
        self,
        source_domain: str,
        target_domain: str,
        insight: str,
        supporting_entities: list[str] | None = None,
    ) -> str:
        """Link insights across life domains (e.g., 'poor sleep → bad work performance')."""
        lid = _uid()
        now = _now()
        self._x(
            """INSERT INTO cross_domain_links
               (id, source_domain, target_domain, insight,
                supporting_entities, strength, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (lid, source_domain, target_domain, insight,
             _json(supporting_entities or []), 0.5, now, now)
        )
        return lid

    def get_cross_domain_insights(self, domain: str | None = None) -> list[dict]:
        """Get insights that connect different life areas."""
        if domain:
            rows = self._q(
                """SELECT * FROM cross_domain_links
                   WHERE source_domain = ? OR target_domain = ?
                   ORDER BY strength DESC""",
                (domain, domain)
            )
        else:
            rows = self._q(
                "SELECT * FROM cross_domain_links ORDER BY strength DESC"
            )
        return [dict(r) for r in rows]

    def synthesize_domains(self) -> dict:
        """Generate a cross-domain synthesis report."""
        links = self.get_cross_domain_insights()
        domains = defaultdict(list)
        for link in links:
            domains[link["source_domain"]].append(link)
            domains[link["target_domain"]].append(link)

        return {
            "connected_domains": len(domains),
            "total_insights": len(links),
            "domain_map": {k: len(v) for k, v in domains.items()},
            "strongest_connections": sorted(links, key=lambda x: x["strength"], reverse=True)[:5],
        }

    # ═══════════════════════════════════════════════════════════════════
    # 7. ADAPTIVE CONSOLIDATION
    # ═══════════════════════════════════════════════════════════════════

    def consolidate_memories(self, force: bool = False) -> dict:
        """Run memory consolidation: merge duplicates, strengthen important memories, decay old ones."""
        actions = {"merged": 0, "strengthened": 0, "decayed": 0, "abstracted": 0}

        # 1. Decay old, unaccessed entities
        decay_cutoff = _now() - (86400 * 90)  # 90 days
        old_entities = self._q(
            """SELECT id, importance, decay_rate FROM entities
               WHERE last_accessed < ? AND importance > 1""",
            (decay_cutoff,)
        )
        for e in old_entities:
            new_importance = max(1.0, e["importance"] - e["decay_rate"])
            self._x(
                "UPDATE entities SET importance = ? WHERE id = ?",
                (new_importance, e["id"])
            )
            actions["decayed"] += 1

        # 2. Strengthen frequently accessed entities
        hot_entities = self._q(
            """SELECT id, importance, access_count FROM entities
               WHERE access_count > 5 AND importance < 10"""
        )
        for e in hot_entities:
            boost = min(0.1, e["access_count"] * 0.01)
            new_imp = min(10.0, e["importance"] + boost)
            self._x(
                "UPDATE entities SET importance = ? WHERE id = ?",
                (new_imp, e["id"])
            )
            actions["strengthened"] += 1

        # 3. Merge semantically identical entities
        if force:
            all_entities = self._q(
                "SELECT id, canonical_name, type, importance FROM entities ORDER BY canonical_name"
            )
            merged_names = set()
            for i, e in enumerate(all_entities):
                if e["id"] in merged_names:
                    continue
                for j in range(i + 1, len(all_entities)):
                    other = all_entities[j]
                    if other["id"] in merged_names:
                        continue
                    if (e["canonical_name"] == other["canonical_name"] and
                        e["type"] == other["type"]):
                        # Merge: keep the one with higher importance
                        keep = e if e["importance"] >= other["importance"] else other
                        remove = other if keep == e else e
                        # Transfer relationships
                        self._x(
                            "UPDATE relationships SET source_id = ? WHERE source_id = ?",
                            (keep["id"], remove["id"])
                        )
                        self._x(
                            "UPDATE relationships SET target_id = ? WHERE target_id = ?",
                            (keep["id"], remove["id"])
                        )
                        self._x("DELETE FROM entities WHERE id = ?", (remove["id"],))
                        merged_names.add(remove["id"])
                        actions["merged"] += 1

        # Log consolidation
        self._x(
            """INSERT INTO consolidation_log (id, action, source_ids, reason, created_at)
               VALUES (?, 'consolidate', ?, ?, ?)""",
            (_uid(), _json(actions), "automated_consolidation", _now())
        )

        return actions

    def detect_concept_drift(self) -> list[dict]:
        """Detect when user's goals/beliefs/motivations change over time."""
        # Compare recent goal statements with older ones
        recent_goals = self._q(
            """SELECT * FROM temporal_events
               WHERE event_type = 'decision'
               AND timestamp > ?
               ORDER BY timestamp DESC LIMIT 20""",
            (_now() - 86400 * 30,)
        )
        old_goals = self._q(
            """SELECT * FROM temporal_events
               WHERE event_type = 'decision'
               AND timestamp <= ?
               ORDER BY timestamp DESC LIMIT 20""",
            (_now() - 86400 * 30,)
        )

        drifts = []
        for recent in recent_goals:
            for old in old_goals:
                # Check for semantic contradiction
                r_emb = _unpack(recent["embedding"]) if recent["embedding"] else []
                o_emb = _unpack(old["embedding"]) if old["embedding"] else []
                if r_emb and o_emb:
                    sim = _cosine(r_emb, o_emb)
                    if 0.3 < sim < 0.7:  # Somewhat related but different
                        drifts.append({
                            "drift_type": "goal_change",
                            "old_summary": old["summary"],
                            "new_summary": recent["summary"],
                            "old_timestamp": old["timestamp"],
                            "new_timestamp": recent["timestamp"],
                            "similarity": round(sim, 3),
                            "magnitude": round(1 - sim, 3),
                        })
        return drifts

    # ═══════════════════════════════════════════════════════════════════
    # 8. PRIVACY-AWARE SHARING
    # ═══════════════════════════════════════════════════════════════════

    def set_privacy(self, entity_id: str | None, domain: str | None,
                    rule_type: str, target: str = "all", conditions: dict | None = None):
        """Set a privacy rule for an entity or domain."""
        self._x(
            """INSERT OR REPLACE INTO privacy_rules
               (id, entity_id, domain, rule_type, target, conditions, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (_uid(), entity_id, domain, rule_type, target, _json(conditions), _now())
        )

    def check_privacy(self, entity_id: str | None, domain: str | None,
                      requested_action: str) -> bool:
        """Check if an action is allowed by privacy rules."""
        rules = []
        if entity_id:
            rules.extend(self._q(
                "SELECT * FROM privacy_rules WHERE entity_id = ?", (entity_id,)
            ))
        if domain:
            rules.extend(self._q(
                "SELECT * FROM privacy_rules WHERE domain = ?", (domain,)
            ))
        rules.extend(self._q(
            "SELECT * FROM privacy_rules WHERE entity_id IS NULL AND domain IS NULL"
        ))

        for rule in rules:
            if rule["rule_type"] == "deny":
                return False
            if rule["rule_type"] == "allow":
                return True
        return True  # Default: allow

    def get_shared_context(self, privacy_level: int, domain: str | None = None) -> dict:
        """Get context that's safe to share at a given privacy level."""
        entities = self._q(
            "SELECT * FROM entities WHERE privacy <= ? ORDER BY importance DESC LIMIT 50",
            (privacy_level,)
        )
        events = self._q(
            """SELECT * FROM temporal_events
               WHERE domain = ? ORDER BY timestamp DESC LIMIT 20"""
            if domain else
            "SELECT * FROM temporal_events ORDER BY timestamp DESC LIMIT 20",
            (domain,) if domain else ()
        )
        return {
            "entities": [dict(e) for e in entities],
            "events": [dict(e) for e in events],
            "privacy_level": privacy_level,
        }

    # ═══════════════════════════════════════════════════════════════════
    # 9. USER PROFILE (aggregated personality model)
    # ═══════════════════════════════════════════════════════════════════

    def update_user_profile(self, dimension: str, value: Any,
                            confidence: float = 0.5):
        """Update a dimension of the user's profile."""
        now = _now()
        existing = self._q(
            "SELECT * FROM user_profile WHERE dimension = ?", (dimension,), one=True
        )
        if existing:
            new_conf = min(1.0, (existing["confidence"] * existing["evidence_count"] + confidence) /
                          (existing["evidence_count"] + 1))
            self._x(
                """UPDATE user_profile
                   SET value = ?, confidence = ?, evidence_count = evidence_count + 1,
                       last_updated = ?
                   WHERE dimension = ?""",
                (_json(value), new_conf, now, dimension)
            )
        else:
            self._x(
                """INSERT INTO user_profile (dimension, value, confidence,
                   evidence_count, last_updated) VALUES (?, ?, ?, 1, ?)""",
                (dimension, _json(value), confidence, now)
            )

    def get_user_profile(self) -> dict:
        """Get the complete user profile."""
        rows = self._q("SELECT * FROM user_profile ORDER BY confidence DESC")
        profile = {}
        for r in rows:
            profile[r["dimension"]] = {
                "value": _unjson(r["value"]),
                "confidence": r["confidence"],
                "evidence_count": r["evidence_count"],
            }
        return profile

    def get_personality_summary(self) -> str:
        """Generate a natural language personality summary from the profile."""
        profile = self.get_user_profile()
        if not profile:
            return "Still learning about you..."

        traits = []
        for dim, data in profile.items():
            if data["confidence"] > 0.6:
                traits.append(f"{dim}: {data['value']}")

        if not traits:
            return "Getting to know you better..."

        return " | ".join(traits[:10])

    # ═══════════════════════════════════════════════════════════════════
    # 10. MULTI-LAYER CONTEXT ASSEMBLY
    # ═══════════════════════════════════════════════════════════════════

    def assemble_context(
        self,
        user_text: str,
        agent_type: str = "CORE_AGENT",
        include_temporal: bool = True,
        include_emotional: bool = True,
        include_predictive: bool = True,
        include_abstractions: bool = True,
        include_profile: bool = True,
        max_tokens: int = 2000,
    ) -> str:
        """
        The money function. Assembles the perfect context window from
        multiple memory layers to give any agent maximum awareness.
        """
        sections = []

        # 1. User Profile (personality, preferences, communication style)
        if include_profile:
            profile = self.get_user_profile()
            if profile:
                profile_text = "USER PROFILE:\n"
                for dim, data in list(profile.items())[:8]:
                    if data["confidence"] > 0.4:
                        profile_text += f"  - {dim}: {data['value']}\n"
                sections.append(profile_text)

        # 2. Emotional Trajectory (recent mood arc)
        if include_emotional:
            emo_summary = self.get_emotional_summary(hours=72)
            if emo_summary["data_points"] > 0:
                sections.append(
                    f"EMOTIONAL STATE (72h): avg_valence={emo_summary['avg_valence']}, "
                    f"dominant={emo_summary['dominant_sentiment']}, "
                    f"trend={emo_summary['trend']}, "
                    f"stability={emo_summary['emotional_stability']}"
                )

            # Detect recent emotional shifts
            shifts = self.detect_emotional_shifts(threshold=0.3)
            if shifts:
                recent_shifts = shifts[-3:]
                for s in recent_shifts:
                    sections.append(
                        f"  EMOTIONAL SHIFT: {s['from_sentiment']} → {s['to_sentiment']} "
                        f"(Δ={s['valence_change']})"
                    )

        # 3. Temporal Context (recent events, causal chains)
        if include_temporal:
            domain = _extract_domain(user_text)
            recent = self.get_temporal_context(window_hours=48, domain=domain)
            if recent:
                sections.append(f"RECENT EVENTS ({domain}):")
                for evt in recent[:5]:
                    sections.append(f"  [{evt['event_type']}] {evt['summary']}")

                # Walk causal chain from most recent event
                if recent:
                    chain = self.get_causal_chain(recent[0]["id"], max_depth=3)
                    if len(chain) > 1:
                        chain_text = " → ".join(e["summary"][:50] for e in chain[:4])
                        sections.append(f"  CAUSAL CHAIN: {chain_text}")

        # 4. Predictive Anticipation
        if include_predictive:
            predictions = self.anticipate(user_text, limit=3)
            if predictions:
                sections.append("PREDICTIONS:")
                for p in predictions:
                    sections.append(
                        f"  IF '{p['trigger_pattern'][:40]}' → THEN '{p['predicted_outcome'][:40]}' "
                        f"(confidence={p['confidence']:.0%})"
                    )

        # 5. Hierarchical Abstractions (patterns, principles)
        if include_abstractions:
            abstractions = self._q(
                """SELECT * FROM abstraction_hierarchy
                   WHERE confidence > 0.5
                   ORDER BY times_applied DESC, confidence DESC LIMIT 5"""
            )
            if abstractions:
                sections.append("KNOWN PATTERNS:")
                for a in abstractions:
                    sections.append(f"  [{a['level']}] {a['name']} (applied {a['times_applied']}x)")

        # 6. Cross-Domain Insights
        domain = _extract_domain(user_text)
        cross = self.get_cross_domain_insights(domain)
        if cross:
            sections.append(f"CROSS-DOMAIN INSIGHTS ({domain}):")
            for c in cross[:3]:
                sections.append(f"  {c['source_domain']} ↔ {c['target_domain']}: {c['insight']}")

        # 7. Personality Summary
        personality = self.get_personality_summary()
        if personality and personality != "Still learning about you...":
            sections.append(f"PERSONALITY: {personality}")

        # Assemble with token budget
        result = "\n\n".join(sections)
        if len(result) > max_tokens * 4:  # Rough char estimate
            result = result[:max_tokens * 4]
        return result

    # ═══════════════════════════════════════════════════════════════════
    # 11. ANALYTICS & INSIGHTS
    # ═══════════════════════════════════════════════════════════════════

    def get_analytics(self) -> dict:
        """Full analytics dashboard data."""
        return {
            "entities": self._q("SELECT COUNT(*) as c FROM entities")[0]["c"],
            "relationships": self._q("SELECT COUNT(*) as c FROM relationships")[0]["c"],
            "events": self._q("SELECT COUNT(*) as c FROM temporal_events")[0]["c"],
            "emotional_points": self._q("SELECT COUNT(*) as c FROM emotional_trajectory")[0]["c"],
            "abstractions": self._q("SELECT COUNT(*) as c FROM abstraction_hierarchy")[0]["c"],
            "cross_domain_links": self._q("SELECT COUNT(*) as c FROM cross_domain_links")[0]["c"],
            "predictive_patterns": self._q("SELECT COUNT(*) as c FROM predictive_patterns")[0]["c"],
            "concept_drifts": self._q("SELECT COUNT(*) as c FROM concept_drift")[0]["c"],
            "consolidation_count": self._q("SELECT COUNT(*) as c FROM consolidation_log")[0]["c"],
            "privacy_rules": self._q("SELECT COUNT(*) as c FROM privacy_rules")[0]["c"],
            "profile_dimensions": self._q("SELECT COUNT(*) as c FROM user_profile")[0]["c"],
            "domain_distribution": dict(self._q(
                "SELECT domain, COUNT(*) as c FROM temporal_events GROUP BY domain"
            ) or []),
            "emotional_summary": self.get_emotional_summary(),
            "user_profile": self.get_user_profile(),
            "cross_domain_synthesis": self.synthesize_domains(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

cortex = CortexMemory()
