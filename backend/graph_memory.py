"""
Hybrid Graph Memory Engine for JARVIS.
Production-grade SQLite-based memory system with FTS5 full-text search,
graph traversal, and automatic user profiling.

Target: sub-10ms query latency on all graph operations.
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
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).resolve().parent / "jarvis_memory.db"
_EMBED_DIM = 384
_NODE_TYPES = frozenset(
    {
        "USER",
        "USER_HABIT",
        "RELATIONSHIP",
        "REVISION",
        "CONCEPT",
        "EMOTION",
        "EVENT",
        "PREFERENCE",
        "GOAL",
        "TOPIC",
        "SKILL",
    }
)
_PREDICATES = frozenset(
    {
        # Core relationships
        "PREFERS",
        "STUDIES",
        "REPORTS_TO",
        "FEELS",
        "REMEMBERS",
        "LEARNED",
        "STRENGTHENS",
        "WEAKENS",
        "TRIGGERS",
        "RELATES_TO",
        "FOLLOWS",
        "BLOCKS",
        "DEPENDS_ON",
        # Social relationships
        "COLLABORATES_WITH",
        "MANAGES",
        "MENTORS",
        "WORKS_WITH",
        "FRIENDS_WITH",
        "PARTNER_OF",
        "PARENT_OF",
        "SIBLING_OF",
        "CHILD_OF",
        "FAMILY_OF",
        # Work relationships
        "ASSIGNED_TO",
        "OWNS",
        "CREATED",
        "USES",
        "ACTIVE_TOOL",
        "WORKING_ON",
        "CONTRIBUTES_TO",
        "LEADS",
        "SUPPORTS",
        "REVIEWED_BY",
        # Communication
        "CONTACTS_VIA",
        "MESSAGES_ON",
        "EMAILS_VIA",
        "CALLS_VIA",
        # Temporal
        "CHEDULED_WITH",
        "MEETS_WITH",
        "FOLLOWED_BY",
        "PRECEDED_BY",
    }
)


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA = """
-- Graph nodes
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    properties TEXT,
    embedding BLOB,
    created_at REAL,
    updated_at REAL,
    access_count INTEGER DEFAULT 0,
    importance REAL DEFAULT 5.0
);

-- Graph edges
CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    created_at REAL,
    metadata TEXT,
    PRIMARY KEY (source_id, target_id, predicate),
    FOREIGN KEY(source_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- FTS5 full-text search on nodes
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    name, properties, content=nodes, content_rowid=rowid
);

-- Conversation history for context
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    role TEXT,
    content TEXT,
    mode TEXT,
    extracted_entities TEXT,
    session_id TEXT
);

-- Learning worktree (knowledge branches)
CREATE TABLE IF NOT EXISTS worktree (
    id TEXT PRIMARY KEY,
    root_concept_id TEXT,
    branch_name TEXT,
    depth INTEGER DEFAULT 0,
    parent_id TEXT,
    mastery_level REAL DEFAULT 0.0,
    last_practiced REAL,
    practice_count INTEGER DEFAULT 0,
    next_review REAL,
    ease_factor REAL DEFAULT 2.5,
    interval_days REAL DEFAULT 1.0,
    FOREIGN KEY(root_concept_id) REFERENCES nodes(id),
    FOREIGN KEY(parent_id) REFERENCES worktree(id)
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_predicate ON edges(predicate);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_worktree_parent ON worktree(parent_id);
CREATE INDEX IF NOT EXISTS idx_worktree_root ON worktree(root_concept_id);
"""

_FTS_SYNC_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, name, properties) VALUES (NEW.rowid, NEW.name, NEW.properties);
END;
"""

_FTS_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, name, properties) VALUES('delete', OLD.rowid, OLD.name, OLD.properties);
END;
"""

_FTS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, name, properties) VALUES('delete', OLD.rowid, OLD.name, OLD.properties);
    INSERT INTO nodes_fts(rowid, name, properties) VALUES (NEW.rowid, NEW.name, NEW.properties);
END;
"""

_USER_NODE_TYPE = "USER"
_DEFAULT_USER_NODE_ID = "user_primary"


# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------

_HABIT_PATTERNS = [
    re.compile(r"I\s+(always|usually|often|sometimes|constantly|keep)\s+(.+)", re.I),
    re.compile(r"I(?:'m| am)\s+(?:always|usually|often)\s+(.+)", re.I),
    re.compile(r"every\s+day\s+I\s+(.+)", re.I),
    re.compile(r"(?:bad|good|old)\s+habit[:\s]+(.+)", re.I),
]

_RELATIONSHIP_PATTERNS = [
    re.compile(r"(?:my|the)\s+(manager|boss|teacher|professor|mentor|advisor)", re.I),
    re.compile(r"(?:my|the)\s+(mom|mother|dad|father|brother|sister|sibling|partner|wife|husband|girlfriend|boyfriend)", re.I),
    re.compile(r"(?:my|the)\s+friend\s+(\w+)", re.I),
    re.compile(r"(?:my|the)\s+coworker\s+(\w+)", re.I),
    re.compile(r"(?:my|the)\s+roommate\s+(\w+)", re.I),
]

_PREFERENCE_PATTERNS = [
    re.compile(r"I\s+(?:prefer|like|love|enjoy|adore)\s+(.+)", re.I),
    re.compile(r"I\s+(?:hate|dislike|can(?:'t|t) stand|don't like)\s+(.+)", re.I),
    re.compile(r"(?:favorite|fav(?:ourite)?)\s+(.+)", re.I),
]

_EMOTION_PATTERNS = [
    re.compile(r"I\s+(?:feel(?:ing)?|am)\s+(stressed|anxious|happy|sad|angry|frustrated|excited|nervous|overwhelmed|calm|tired|exhausted|motivated|inspired|bored|confused|grateful|lonely|proud|worried)", re.I),
    re.compile(r"(?:makes?|makes me)\s+(me\s+)?(happy|sad|angry|anxious|stressed|frustrated|excited|nervous)", re.I),
]

_GOAL_PATTERNS = [
    re.compile(r"I\s+(?:want|need|aim|plan)\s+to\s+(.+)", re.I),
    re.compile(r"my\s+goal\s+is\s+(?:to\s+)?(.+)", re.I),
    re.compile(r"(?:trying|working)\s+to\s+(.+)", re.I),
    re.compile(r"I(?:'m| am)\s+(?:trying|working)\s+to\s+(.+)", re.I),
]

_LEARNING_PATTERNS = [
    re.compile(r"(?:teach|explain|help(?:\s+me)?\s+understand)\s+(?:me\s+)?(?:about\s+)?(.+)", re.I),
    re.compile(r"I(?:'m| am)\s+(?:studying|learning|reading about|practicing)\s+(.+)", re.I),
    re.compile(r"(?:how\s+do|how\s+does|what\s+is|what\s+are)\s+(.+)", re.I),
    re.compile(r"(?:can\s+you|please)\s+(?:explain|teach)\s+(.+)", re.I),
]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _now() -> float:
    """Return current UTC epoch seconds."""
    return time.time()


def _uid() -> str:
    """Return a 12-char hex UUID."""
    return uuid.uuid4().hex[:12]


def _pack_embedding(vec: list[float]) -> bytes:
    """Pack a float32 vector into bytes."""
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_embedding(blob: bytes) -> list[float]:
    """Unpack a float32 blob back to a list."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _json_dumps(obj: Any) -> str | None:
    """Safely serialize to JSON string."""
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def _json_loads(text: str | None) -> Any:
    """Safely deserialize from JSON string."""
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class HybridGraphMemory:
    """Production-grade hybrid graph memory engine backed by SQLite.

    Provides FTS5 full-text search, recursive CTE graph traversal,
    automatic entity extraction from conversation, SM-2 spaced repetition
    via a worktree, and cosine-similarity semantic recall — all targeting
    sub-10ms query latency.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or _DB_PATH)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._connect()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open (or re-open) the SQLite connection and initialise schema."""
        conn = sqlite3.connect(
            self._db_path,
            timeout=10,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-64000")  # 64 MB page cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.executescript(_SCHEMA)
        conn.execute(_FTS_SYNC_TRIGGER)
        conn.execute(_FTS_DELETE_TRIGGER)
        conn.execute(_FTS_UPDATE_TRIGGER)
        conn.commit()
        self._conn = conn
        return conn

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            return self._connect()
        return self._conn

    def close(self) -> None:
        """Close the underlying connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Core CRUD — Nodes
    # ------------------------------------------------------------------

    def add_node(
        self,
        type: str,
        name: str,
        properties: dict | None = None,
        importance: float = 5.0,
        node_id: str | None = None,
    ) -> str:
        """Create a new node and return its ID.

        Args:
            type: Node type (must be in _NODE_TYPES).
            name: Human-readable label.
            properties: Optional JSON-serialisable metadata.
            importance: 0-10 importance score (default 5).
            node_id: Optional explicit ID (auto-generated if omitted).

        Returns:
            The new node's ID string.
        """
        if type not in _NODE_TYPES:
            raise ValueError(f"Invalid node type: {type!r}. Must be one of {_NODE_TYPES}")
        nid = node_id or _uid()
        ts = _now()
        props_json = _json_dumps(properties)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO nodes (id, type, name, properties, created_at, updated_at, access_count, importance) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (nid, type, name, props_json, ts, ts, importance),
            )
            self._db.commit()
        return nid

    def get_node(self, node_id: str) -> dict | None:
        """Return node dict or None."""
        row = self._db.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return None
        self._db.execute(
            "UPDATE nodes SET access_count = access_count + 1, updated_at = ? WHERE id = ?",
            (_now(), node_id),
        )
        self._db.commit()
        return self._row_to_node(row)

    def find_nodes(
        self,
        type: str | None = None,
        name_like: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Find nodes with optional type and name filters."""
        query = "SELECT * FROM nodes WHERE 1=1"
        params: list[Any] = []
        if type:
            query += " AND type = ?"
            params.append(type)
        if name_like:
            query += " AND name LIKE ?"
            params.append(f"%{name_like}%")
        query += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        rows = self._db.execute(query, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def update_node(
        self,
        node_id: str,
        properties: dict | None = None,
        importance: float | None = None,
        name: str | None = None,
    ) -> bool:
        """Update node fields. Returns True if node existed."""
        existing = self._db.execute(
            "SELECT id FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if existing is None:
            return False
        updates: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if properties is not None:
            updates.append("properties = ?")
            params.append(_json_dumps(properties))
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        params.append(node_id)
        with self._lock:
            self._db.execute(
                f"UPDATE nodes SET {', '.join(updates)} WHERE id = ?", params
            )
            self._db.commit()
        return True

    def remove_node(self, node_id: str) -> bool:
        """Delete a node and all incident edges. Returns True if deleted."""
        with self._lock:
            cur = self._db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            self._db.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Core CRUD — Edges
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        predicate: str,
        weight: float = 1.0,
        metadata: dict | None = None,
    ) -> None:
        """Insert or update an edge between two nodes.

        If an edge with the same (source, target, predicate) already exists
        the weight is updated to the average of old and new.
        Accepts any predicate — fully dynamic, no hardcoding.
        """
        ts = _now()
        meta_json = _json_dumps(metadata)
        with self._lock:
            existing = self._db.execute(
                "SELECT weight FROM edges WHERE source_id = ? AND target_id = ? AND predicate = ?",
                (source_id, target_id, predicate),
            ).fetchone()
            if existing:
                new_weight = (existing["weight"] + weight) / 2.0
                self._db.execute(
                    "UPDATE edges SET weight = ?, metadata = COALESCE(?, metadata) WHERE source_id = ? AND target_id = ? AND predicate = ?",
                    (new_weight, meta_json, source_id, target_id, predicate),
                )
            else:
                self._db.execute(
                    "INSERT INTO edges (source_id, target_id, predicate, weight, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                    (source_id, target_id, predicate, weight, ts, meta_json),
                )
            self._db.commit()

    def get_edges(
        self,
        node_id: str,
        direction: str = "both",
        predicate: str | None = None,
    ) -> list[dict]:
        """Get edges for a node.

        Args:
            node_id: The node to query.
            direction: 'outgoing', 'incoming', or 'both'.
            predicate: Optional filter on predicate.
        """
        results: list[dict] = []
        if direction in ("outgoing", "both"):
            q = "SELECT * FROM edges WHERE source_id = ?"
            p: list[Any] = [node_id]
            if predicate:
                q += " AND predicate = ?"
                p.append(predicate)
            results.extend(self._dictify_rows(self._db.execute(q, p).fetchall()))
        if direction in ("incoming", "both"):
            q = "SELECT * FROM edges WHERE target_id = ?"
            p2: list[Any] = [node_id]
            if predicate:
                q += " AND predicate = ?"
                p2.append(predicate)
            results.extend(self._dictify_rows(self._db.execute(q, p2).fetchall()))
        return results

    # ------------------------------------------------------------------
    # Graph Traversal
    # ------------------------------------------------------------------

    def multi_hop_recall(
        self,
        start_name: str,
        max_hops: int = 3,
        node_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Recursive CTE traversal from a node name, up to max_hops edges away."""
        type_filter = ""
        params: list[Any] = [start_name, max_hops]
        if node_type:
            type_filter = "AND n.type = ?"
            params.append(node_type)
        params.append(limit)

        sql = f"""
            WITH RECURSIVE traverse(start_id, hop) AS (
                SELECT n.id, 0
                FROM nodes n
                WHERE n.name = ?

                UNION ALL

                SELECT CASE
                    WHEN e.source_id = t.start_id THEN e.target_id
                    ELSE e.source_id
                END, t.hop + 1
                FROM traverse t
                JOIN edges e ON e.source_id = t.start_id OR e.target_id = t.start_id
                WHERE t.hop < ?
            )
            SELECT DISTINCT n.*
            FROM traverse t
            JOIN nodes n ON n.id = t.start_id
            WHERE t.hop > 0 {type_filter}
            ORDER BY n.importance DESC
            LIMIT ?
        """
        rows = self._db.execute(sql, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def shortest_path(self, source_name: str, target_name: str) -> list[dict]:
        """BFS shortest path between two nodes by name.

        Returns the list of nodes on the path (including endpoints), or
        an empty list if no path exists.
        """
        sql = """
            WITH RECURSIVE bfs(node_id, path, depth) AS (
                SELECT n.id, n.id, 0
                FROM nodes n
                WHERE n.name = ?

                UNION ALL

                SELECT
                    CASE WHEN e.source_id = b.node_id THEN e.target_id ELSE e.source_id END,
                    b.path || '|' || CASE WHEN e.source_id = b.node_id THEN e.target_id ELSE e.source_id END,
                    b.depth + 1
                FROM bfs b
                JOIN edges e ON e.source_id = b.node_id OR e.target_id = b.node_id
                WHERE b.depth < 10
                  AND (
                    CASE WHEN e.source_id = b.node_id THEN e.target_id ELSE e.source_id END
                  ) NOT IN (
                    SELECT value FROM json_each('["' || REPLACE(b.path, '|', '","') || '"]')
                  )
            )
            SELECT path, depth FROM bfs b
            JOIN nodes n ON n.id = b.node_id
            WHERE n.name = ? AND b.depth > 0
            ORDER BY b.depth ASC
            LIMIT 1
        """
        row = self._db.execute(sql, (source_name, target_name)).fetchone()
        if row is None:
            return []
        node_ids = row["path"].split("|")
        result: list[dict] = []
        for nid in node_ids:
            n = self.get_node(nid)
            if n:
                result.append(n)
        return result

    def get_context_cluster(self, node_name: str, radius: int = 2) -> dict:
        """Return all nodes within *radius* hops of the named node.

        Returns ``{"center": node_dict, "nodes": [...], "edges": [...]}``.
        """
        center_row = self._db.execute(
            "SELECT * FROM nodes WHERE name = ?", (node_name,)
        ).fetchone()
        if center_row is None:
            return {"center": None, "nodes": [], "edges": []}
        center = self._row_to_node(center_row)
        visited: set[str] = {center["id"]}
        frontier = {center["id"]}
        for _ in range(radius):
            next_frontier: set[str] = set()
            for nid in frontier:
                for e in self.get_edges(nid, direction="both"):
                    sid = e["source_id"]
                    tid = e["target_id"]
                    for neighbour_id in (sid, tid):
                        if neighbour_id not in visited:
                            visited.add(neighbour_id)
                            next_frontier.add(neighbour_id)
            frontier = next_frontier

        nodes: list[dict] = []
        for nid in visited:
            n = self.get_node(nid)
            if n:
                nodes.append(n)

        edge_set: list[dict] = []
        for nid in visited:
            for e in self.get_edges(nid, direction="both"):
                key = (e["source_id"], e["target_id"], e["predicate"])
                if key not in {(x["source_id"], x["target_id"], x["predicate"]) for x in edge_set}:
                    edge_set.append(e)

        return {"center": center, "nodes": nodes, "edges": edge_set}

    def get_subgraph(self, root_name: str, max_depth: int = 3) -> dict:
        """Return a subtree rooted at the named node."""
        root_row = self._db.execute(
            "SELECT * FROM nodes WHERE name = ?", (root_name,)
        ).fetchone()
        if root_row is None:
            return {"root": None, "nodes": [], "edges": []}
        root = self._row_to_node(root_row)

        visited: set[str] = {root["id"]}
        frontier = [root["id"]]
        for _ in range(max_depth):
            next_frontier: list[str] = []
            for nid in frontier:
                for e in self.get_edges(nid, direction="outgoing"):
                    child = e["target_id"]
                    if child not in visited:
                        visited.add(child)
                        next_frontier.append(child)
            frontier = next_frontier

        nodes: list[dict] = []
        for nid in visited:
            n = self.get_node(nid)
            if n:
                nodes.append(n)

        edge_set: list[dict] = []
        for nid in visited:
            for e in self.get_edges(nid, direction="outgoing"):
                if e["target_id"] in visited:
                    edge_set.append(e)

        return {"root": root, "nodes": nodes, "edges": edge_set}

    # ------------------------------------------------------------------
    # FTS5 Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across node names and properties via FTS5.

        Uses the built-in BM25 ranking.
        """
        sql = """
            SELECT n.* FROM nodes n
            JOIN nodes_fts f ON n.rowid = f.rowid
            WHERE nodes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        rows = self._db.execute(sql, (query, limit)).fetchall()
        return [self._row_to_node(r) for r in rows]

    # ------------------------------------------------------------------
    # User Profiling (Auto-extraction)
    # ------------------------------------------------------------------

    def _ensure_user_node(self) -> str:
        """Return the primary user node ID, creating it if needed."""
        existing = self._db.execute(
            "SELECT id FROM nodes WHERE id = ? AND type = ?",
            (_DEFAULT_USER_NODE_ID, _USER_NODE_TYPE),
        ).fetchone()
        if existing:
            return existing["id"]
        return self.add_node(
            type=_USER_NODE_TYPE,
            name="Primary User",
            node_id=_DEFAULT_USER_NODE_ID,
            importance=10.0,
        )

    def extract_and_store(
        self,
        text: str,
        role: str = "user",
        session_id: str | None = None,
    ) -> list[str]:
        """Extract entities from text and store them as nodes + edges.

        Detects habits, relationships, preferences, emotions, goals,
        and learning topics using regex pattern matching.

        Returns a list of extracted entity names.
        """
        user_id = self._ensure_user_node()
        extracted: list[str] = []

        # --- Habits ---
        for pat in _HABIT_PATTERNS:
            for m in pat.finditer(text):
                habit_text = m.group(m.lastindex or 0).strip().rstrip(".")
                node_name = f"habit:{habit_text[:80]}"
                nid = self.add_node(type="USER_HABIT", name=node_name, importance=6.0)
                self.add_edge(user_id, nid, "FOLLOWS", weight=1.0)
                extracted.append(node_name)

        # --- Relationships ---
        for pat in _RELATIONSHIP_PATTERNS:
            for m in pat.finditer(text):
                rel_text = m.group(0).strip().rstrip(".")
                node_name = f"relationship:{rel_text[:80]}"
                nid = self.add_node(type="RELATIONSHIP", name=node_name, importance=7.0)
                self.add_edge(user_id, nid, "REPORTS_TO", weight=1.0)
                extracted.append(node_name)

        # --- Preferences ---
        for pat in _PREFERENCE_PATTERNS:
            for m in pat.finditer(text):
                pref_text = m.group(m.lastindex or 0).strip().rstrip(".")
                node_name = f"preference:{pref_text[:80]}"
                nid = self.add_node(type="PREFERENCE", name=node_name, importance=6.5)
                self.add_edge(user_id, nid, "PREFERS", weight=1.0)
                extracted.append(node_name)

        # --- Emotions ---
        for pat in _EMOTION_PATTERNS:
            for m in pat.finditer(text):
                emotion_text = m.group(1 if m.lastindex else 0).strip().rstrip(".")
                node_name = f"emotion:{emotion_text[:60]}"
                nid = self.add_node(type="EMOTION", name=node_name, importance=7.0)
                self.add_edge(user_id, nid, "FEELS", weight=1.0)
                extracted.append(node_name)

        # --- Goals ---
        for pat in _GOAL_PATTERNS:
            for m in pat.finditer(text):
                goal_text = m.group(m.lastindex or 0).strip().rstrip(".")
                node_name = f"goal:{goal_text[:80]}"
                nid = self.add_node(type="GOAL", name=node_name, importance=8.0)
                self.add_edge(user_id, nid, "FOLLOWS", weight=1.0)
                extracted.append(node_name)

        # --- Learning topics ---
        for pat in _LEARNING_PATTERNS:
            for m in pat.finditer(text):
                topic_text = m.group(m.lastindex or 0).strip().rstrip(".")
                node_name = f"topic:{topic_text[:80]}"
                nid = self.add_node(type="TOPIC", name=node_name, importance=7.0)
                self.add_edge(user_id, nid, "STUDIES", weight=1.0)
                extracted.append(node_name)

        # --- Log conversation entry ---
        self._log_conversation(
            role=role,
            content=text,
            extracted_entities=extracted,
            session_id=session_id,
        )

        # --- Strengthen edges for recurring mentions ---
        self.learn_pattern(text)

        return extracted

    def learn_pattern(self, text: str) -> None:
        """Detect recurring patterns and strengthen existing edges.

        For every existing node whose name substring appears in the text,
        increment the corresponding edge weight.
        """
        rows = self._db.execute("SELECT id, name FROM nodes").fetchall()
        for row in rows:
            name_lower = row["name"].lower()
            # Extract the meaningful portion (after the type prefix)
            if ":" in name_lower:
                keyword = name_lower.split(":", 1)[1]
            else:
                keyword = name_lower
            if len(keyword) < 3:
                continue
            if keyword in text.lower():
                edges = self._get_edges_for_node(row["id"])
                for e in edges:
                    with self._lock:
                        self._db.execute(
                            "UPDATE edges SET weight = MIN(weight + 0.1, 10.0) WHERE source_id = ? AND target_id = ? AND predicate = ?",
                            (e["source_id"], e["target_id"], e["predicate"]),
                        )
                        self._db.commit()

    def _get_edges_for_node(self, node_id: str) -> list[dict]:
        """Internal helper — get all edges where this node is source or target."""
        rows = self._db.execute(
            "SELECT * FROM edges WHERE source_id = ? OR target_id = ?", (node_id, node_id)
        ).fetchall()
        return self._dictify_rows(rows)

    def get_user_profile(self) -> dict:
        """Aggregate a full user profile from all stored data.

        Returns a dict with keys: habits, relationships, preferences,
        emotions, goals, skills, topics.
        """
        user_id = self._ensure_user_node()
        profile: dict[str, list[dict]] = {
            "habits": [],
            "relationships": [],
            "preferences": [],
            "emotions": [],
            "goals": [],
            "skills": [],
            "topics": [],
        }

        type_map = {
            "USER_HABIT": "habits",
            "RELATIONSHIP": "relationships",
            "PREFERENCE": "preferences",
            "EMOTION": "emotions",
            "GOAL": "goals",
            "SKILL": "skills",
            "TOPIC": "topics",
        }

        edges = self.get_edges(user_id, direction="outgoing")
        for e in edges:
            target = self.get_node(e["target_id"])
            if target is None:
                continue
            key = type_map.get(target["type"])
            if key:
                profile[key].append(
                    {
                        "id": target["id"],
                        "name": target["name"],
                        "importance": target["importance"],
                        "predicate": e["predicate"],
                        "edge_weight": e["weight"],
                    }
                )

        # Sort each category by importance descending
        for key in profile:
            profile[key].sort(key=lambda x: x["importance"], reverse=True)

        return profile

    # ------------------------------------------------------------------
    # Context Injection
    # ------------------------------------------------------------------

    def inject_context(self, agent_type: str, user_text: str) -> str:
        """Generate a context string for injection into an agent's system prompt.

        Args:
            agent_type: One of 'OS_AGENT', 'HAL_AGENT', 'WEB_AGENT', 'CORE_AGENT'.
            user_text: The current user utterance (used for semantic recall).

        Returns:
            A formatted context string.
        """
        user_id = self._ensure_user_node()
        lines: list[str] = [f"[MEMORY CONTEXT — {agent_type}]", ""]

        # General profile summary
        profile = self.get_user_profile()
        if profile["preferences"]:
            lines.append("## Preferences")
            for p in profile["preferences"][:5]:
                lines.append(f"- {p['name']}")
            lines.append("")

        if profile["emotions"]:
            recent_emotions = profile["emotions"][:3]
            lines.append("## Recent Emotions")
            for e in recent_emotions:
                lines.append(f"- {e['name']}")
            lines.append("")

        if profile["goals"]:
            lines.append("## Active Goals")
            for g in profile["goals"][:5]:
                lines.append(f"- {g['name']}")
            lines.append("")

        # Agent-type-specific recall
        if agent_type == "OS_AGENT":
            app_nodes = self.find_nodes(type="PREFERENCE", name_like="app", limit=5)
            if not app_nodes:
                app_nodes = self.find_nodes(type="PREFERENCE", name_like="tool", limit=5)
            if app_nodes:
                lines.append("## Preferred Apps / Tools")
                for a in app_nodes:
                    lines.append(f"- {a['name']}")
                lines.append("")
            work_habits = [h for h in profile["habits"] if any(k in h["name"].lower() for k in ("work", "schedule", "routine", "time"))]
            if work_habits:
                lines.append("## Work Habits")
                for h in work_habits[:5]:
                    lines.append(f"- {h['name']}")
                lines.append("")

        elif agent_type == "HAL_AGENT":
            device_nodes = self.find_nodes(type="PREFERENCE", name_like="device", limit=5)
            if not device_nodes:
                device_nodes = self.find_nodes(type="PREFERENCE", name_like="smart", limit=5)
            if device_nodes:
                lines.append("## Device Preferences")
                for d in device_nodes:
                    lines.append(f"- {d['name']}")
                lines.append("")

        elif agent_type == "WEB_AGENT":
            browse_nodes = self.find_nodes(type="PREFERENCE", name_like="website", limit=5)
            if not browse_nodes:
                browse_nodes = self.find_nodes(type="PREFERENCE", name_like="browse", limit=5)
            if browse_nodes:
                lines.append("## Browsing Preferences")
                for b in browse_nodes:
                    lines.append(f"- {b['name']}")
                lines.append("")

        elif agent_type == "CORE_AGENT":
            if profile["relationships"]:
                lines.append("## Relationships")
                for r in profile["relationships"][:5]:
                    lines.append(f"- {r['name']}")
                lines.append("")
            if profile["topics"]:
                lines.append("## Study Progress")
                for t in profile["topics"][:5]:
                    lines.append(f"- {t['name']}")
                lines.append("")

        # Multi-hop recall from user text keywords
        keywords = re.findall(r"\b\w{4,}\b", user_text.lower())
        seen: set[str] = set()
        hop_results: list[dict] = []
        for kw in keywords[:3]:
            nodes = self.find_nodes(name_like=kw, limit=3)
            for n in nodes:
                if n["id"] not in seen:
                    seen.add(n["id"])
                    hop_results.extend(self.multi_hop_recall(n["name"], max_hops=2, limit=5))
        if hop_results:
            deduped = {n["id"]: n for n in hop_results}
            lines.append("## Related Knowledge")
            for n in list(deduped.values())[:10]:
                lines.append(f"- [{n['type']}] {n['name']}")
            lines.append("")

        return "\n".join(lines) if len(lines) > 2 else ""

    # ------------------------------------------------------------------
    # Worktree (Knowledge Branching)
    # ------------------------------------------------------------------

    def create_branch(
        self,
        root_concept: str,
        branch_name: str,
        parent_id: str | None = None,
    ) -> str:
        """Create a new worktree branch rooted at a concept node.

        Returns the new branch ID.
        """
        # Ensure the root concept node exists
        existing = self._db.execute(
            "SELECT id FROM nodes WHERE name = ?", (root_concept,)
        ).fetchone()
        if existing:
            root_concept_id = existing["id"]
        else:
            root_concept_id = self.add_node(
                type="CONCEPT", name=root_concept, importance=7.0
            )

        branch_id = _uid()
        ts = _now()
        next_review = ts + 86400  # 1 day from now
        depth = 0
        if parent_id:
            parent_row = self._db.execute(
                "SELECT depth FROM worktree WHERE id = ?", (parent_id,)
            ).fetchone()
            if parent_row:
                depth = parent_row["depth"] + 1

        with self._lock:
            self._db.execute(
                "INSERT INTO worktree (id, root_concept_id, branch_name, depth, parent_id, mastery_level, last_practiced, practice_count, next_review, ease_factor, interval_days) "
                "VALUES (?, ?, ?, ?, ?, 0.0, NULL, 0, ?, 2.5, 1.0)",
                (branch_id, root_concept_id, branch_name, depth, parent_id, next_review),
            )
            self._db.commit()
        return branch_id

    def grow_branch(self, branch_id: str, child_concept: str) -> str:
        """Add a child concept to an existing branch.

        Returns the new child branch ID.
        """
        return self.create_branch(root_concept=child_concept, branch_name=child_concept, parent_id=branch_id)

    def update_mastery(self, branch_id: str, quality: int) -> None:
        """Update mastery of a branch using the SM-2 algorithm.

        Args:
            branch_id: The branch to update.
            quality: Quality of recall 0-5 (0=complete blackout, 5=perfect).
        """
        quality = max(0, min(5, quality))
        row = self._db.execute(
            "SELECT ease_factor, interval_days, practice_count FROM worktree WHERE id = ?",
            (branch_id,),
        ).fetchone()
        if row is None:
            return

        ef = row["ease_factor"]
        interval = row["interval_days"]
        pc = row["practice_count"]

        # SM-2 formula
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(1.3, new_ef)

        if quality < 3:
            new_interval = 1.0
        else:
            if pc == 0:
                new_interval = 1.0
            elif pc == 1:
                new_interval = 6.0
            else:
                new_interval = interval * new_ef

        new_mastery = min(1.0, quality / 5.0)

        with self._lock:
            self._db.execute(
                "UPDATE worktree SET ease_factor = ?, interval_days = ?, practice_count = practice_count + 1, "
                "mastery_level = ?, last_practiced = ?, next_review = ? WHERE id = ?",
                (
                    new_ef,
                    new_interval,
                    new_mastery,
                    _now(),
                    _now() + new_interval * 86400,
                    branch_id,
                ),
            )
            self._db.commit()

    def get_worktree(self, root_name: str) -> dict:
        """Return the full tree structure for a root concept.

        Returns ``{"root": branch_dict, "children": [...]}`` with nested children.
        """
        root_concept_row = self._db.execute(
            "SELECT id FROM nodes WHERE name = ?", (root_name,)
        ).fetchone()
        if root_concept_row is None:
            return {"root": None, "children": []}

        root_branch = self._db.execute(
            "SELECT * FROM worktree WHERE root_concept_id = ? AND parent_id IS NULL",
            (root_concept_row["id"],),
        ).fetchone()
        if root_branch is None:
            return {"root": None, "children": []}

        def _build_tree(branch_id: str) -> dict:
            row = self._db.execute(
                "SELECT * FROM worktree WHERE id = ?", (branch_id,)
            ).fetchone()
            if row is None:
                return {}
            children_rows = self._db.execute(
                "SELECT id FROM worktree WHERE parent_id = ?", (branch_id,)
            ).fetchall()
            return {
                **self._dictify_row(row),
                "children": [_build_tree(c["id"]) for c in children_rows],
            }

        return _build_tree(root_branch["id"])

    def get_due_reviews(self) -> list[dict]:
        """Return branches that are due for review (next_review <= now)."""
        ts = _now()
        rows = self._db.execute(
            "SELECT * FROM worktree WHERE next_review <= ? ORDER BY next_review ASC",
            (ts,),
        ).fetchall()
        return [self._dictify_row(r) for r in rows]

    def prune_branch(self, branch_id: str) -> bool:
        """Remove a branch and all its children. Returns True if deleted."""
        with self._lock:
            # Collect all descendant branch IDs
            to_delete: list[str] = [branch_id]
            queue = [branch_id]
            while queue:
                current = queue.pop(0)
                children = self._db.execute(
                    "SELECT id FROM worktree WHERE parent_id = ?", (current,)
                ).fetchall()
                for c in children:
                    to_delete.append(c["id"])
                    queue.append(c["id"])

            placeholders = ",".join("?" for _ in to_delete)
            self._db.execute(
                f"DELETE FROM worktree WHERE id IN ({placeholders})", to_delete
            )
            self._db.commit()
        return True

    # ------------------------------------------------------------------
    # Semantic Similarity
    # ------------------------------------------------------------------

    def store_embedding(self, node_id: str, embedding: list[float]) -> None:
        """Store a float32 embedding vector for a node."""
        blob = _pack_embedding(embedding)
        with self._lock:
            self._db.execute(
                "UPDATE nodes SET embedding = ? WHERE id = ?", (blob, node_id)
            )
            self._db.commit()

    def find_similar(self, node_id: str, limit: int = 5) -> list[dict]:
        """Find nodes with the most similar embedding to the given node.

        Falls back to brute-force cosine scan (fine for < 100k nodes).
        """
        source_row = self._db.execute(
            "SELECT embedding FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if source_row is None or source_row["embedding"] is None:
            return []
        source_vec = _unpack_embedding(source_row["embedding"])

        rows = self._db.execute(
            "SELECT id, embedding FROM nodes WHERE id != ? AND embedding IS NOT NULL",
            (node_id,),
        ).fetchall()

        scored: list[tuple[str, float]] = []
        for r in rows:
            vec = _unpack_embedding(r["embedding"])
            sim = _cosine_similarity(source_vec, vec)
            scored.append((r["id"], sim))

        scored.sort(key=lambda x: x[1], reverse=True)

        results: list[dict] = []
        for nid, sim in scored[:limit]:
            node = self.get_node(nid)
            if node:
                node["similarity"] = round(sim, 4)
                results.append(node)
        return results

    # ------------------------------------------------------------------
    # Local Embedding Generation (sentence-transformers)
    # ------------------------------------------------------------------

    _embed_model = None

    def _get_embed_model(self):
        if HybridGraphMemory._embed_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                HybridGraphMemory._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                return None
        return HybridGraphMemory._embed_model

    def generate_embedding(self, text: str) -> list[float] | None:
        """Generate a local embedding for text using all-MiniLM-L6-v2."""
        model = self._get_embed_model()
        if model is None:
            return None
        try:
            vec = model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception:
            return None

    def embed_node(self, node_id: str) -> bool:
        """Generate and store an embedding for a single node."""
        node = self.get_node(node_id)
        if not node:
            return False
        text = f"{node.get('name', '')} [{node.get('type', '')}]"
        if node.get("metadata"):
            for k, v in node["metadata"].items():
                if isinstance(v, str):
                    text += f" {k}: {v}"
        vec = self.generate_embedding(text)
        if vec:
            self.store_embedding(node_id, vec)
            return True
        return False

    def embed_all_pending(self, batch_size: int = 64) -> dict:
        """Embed all nodes without embeddings. Returns stats."""
        model = self._get_embed_model()
        if model is None:
            return {"error": "Embedding model not available", "embedded": 0}

        pending = self.query(
            "SELECT id, name, type, metadata FROM nodes WHERE embedding IS NULL"
        )
        if not pending:
            return {"embedded": 0, "total": 0}

        texts = []
        ids = []
        for row in pending:
            text = f"{row.get('name', '')} [{row.get('type', '')}]"
            if row.get("metadata"):
                meta = row["metadata"]
                if isinstance(meta, str):
                    try:
                        import json as _json
                        meta = _json.loads(meta)
                    except Exception:
                        meta = {}
                for k, v in meta.items():
                    if isinstance(v, str):
                        text += f" {k}: {v}"
            texts.append(text)
            ids.append(row["id"])

        embedded = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            try:
                vecs = model.encode(batch_texts, normalize_embeddings=True, batch_size=batch_size)
                with self._lock:
                    for nid, vec in zip(batch_ids, vecs):
                        blob = _pack_embedding(vec.tolist())
                        self._db.execute(
                            "UPDATE nodes SET embedding = ? WHERE id = ?",
                            (blob, nid),
                        )
                        embedded += 1
                    self._db.commit()
            except Exception:
                continue

        return {"embedded": embedded, "total": len(pending)}

    def semantic_search(self, query_text: str, limit: int = 10) -> list[dict]:
        """Find nodes most similar to a text query using local embeddings."""
        vec = self.generate_embedding(query_text)
        if vec is None:
            return []

        rows = self.query(
            "SELECT id, name, type, importance, embedding FROM nodes WHERE embedding IS NOT NULL"
        )
        scored = []
        for r in rows:
            node_vec = _unpack_embedding(r["embedding"])
            sim = _cosine_similarity(vec, node_vec)
            scored.append((r, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for node, sim in scored[:limit]:
            node["similarity"] = round(sim, 4)
            node.pop("embedding", None)
            results.append(node)
        return results

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregate statistics about the memory store."""
        node_counts = {}
        for row in self._db.execute(
            "SELECT type, COUNT(*) as cnt FROM nodes GROUP BY type"
        ).fetchall():
            node_counts[row["type"]] = row["cnt"]

        edge_counts = {}
        for row in self._db.execute(
            "SELECT predicate, COUNT(*) as cnt FROM edges GROUP BY predicate"
        ).fetchall():
            edge_counts[row["predicate"]] = row["cnt"]

        total_nodes = self._db.execute("SELECT COUNT(*) as cnt FROM nodes").fetchone()["cnt"]
        total_edges = self._db.execute("SELECT COUNT(*) as cnt FROM edges").fetchone()["cnt"]
        total_conversations = self._db.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()["cnt"]
        total_worktree = self._db.execute("SELECT COUNT(*) as cnt FROM worktree").fetchone()["cnt"]

        recent_activity = self._db.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE timestamp > ?",
            (_now() - 86400,),
        ).fetchone()["cnt"]

        avg_importance = self._db.execute(
            "SELECT AVG(importance) as avg_imp FROM nodes"
        ).fetchone()["avg_imp"]

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_conversations": total_conversations,
            "total_worktree_branches": total_worktree,
            "nodes_by_type": node_counts,
            "edges_by_predicate": edge_counts,
            "recent_activity_24h": recent_activity,
            "avg_importance": round(avg_importance or 0, 2),
        }

    # ------------------------------------------------------------------
    # Conversation logging
    # ------------------------------------------------------------------

    def _log_conversation(
        self,
        role: str,
        content: str,
        extracted_entities: list[str] | None = None,
        session_id: str | None = None,
        mode: str | None = None,
    ) -> int:
        """Append a row to the conversations table. Returns the row ID."""
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO conversations (timestamp, role, content, mode, extracted_entities, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _now(),
                    role,
                    content,
                    mode,
                    _json_dumps(extracted_entities) if extracted_entities else None,
                    session_id,
                ),
            )
            self._db.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict with parsed JSON."""
        d = dict(row)
        d["properties"] = _json_loads(d.get("properties"))
        return d

    @staticmethod
    def _dictify_row(row: sqlite3.Row) -> dict:
        """Convert a Row to a plain dict, parsing JSON fields."""
        d = dict(row)
        for key in ("properties", "metadata", "extracted_entities"):
            if key in d:
                d[key] = _json_loads(d[key])
        return d

    @staticmethod
    def _dictify_rows(rows: list[sqlite3.Row]) -> list[dict]:
        """Convert a list of Rows to a list of dicts."""
        return [HybridGraphMemory._dictify_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Public Query Helpers (for context_orchestrator and others)
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a read-only SQL query and return list of dicts."""
        try:
            rows = self._db.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_recent_conversations(self, limit: int = 10) -> list[dict]:
        """Get recent conversation history from the conversations table."""
        return self.query(
            "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )

    def get_all_nodes_for_embedding(self) -> list[dict]:
        """Get all nodes that don't yet have embeddings (for batch embedding)."""
        return self.query(
            "SELECT id, name, node_type FROM nodes WHERE embedding IS NULL LIMIT 500"
        )

    def get_graph_for_visualization(self, limit: int = 200) -> dict:
        """Get nodes and edges formatted for frontend graph visualization."""
        nodes = self.query(
            "SELECT id, name, node_type, importance FROM nodes ORDER BY importance DESC LIMIT ?",
            (limit,),
        )
        node_ids = {n["id"] for n in nodes}
        edges = self.query(
            "SELECT source, target, edge_type, weight FROM edges WHERE source IN ({}) OR target IN ({})".format(
                ",".join("?" * len(node_ids)), ",".join("?" * len(node_ids))
            ),
            tuple(node_ids) * 2,
        )
        return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

memory = HybridGraphMemory()
