"""
Local Memory Engine — semantic memory with local embeddings for deep recall.
Uses sentence-transformers entirely offline to embed interactions, facts,
and conversations, then retrieves via cosine similarity.

Provides: episodic memory, semantic search over past interactions,
concept clustering, and automatic memory consolidation.
"""
import json
import sqlite3
import threading
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

DB_DIR = Path(__file__).parent / "user_data"
MEMORY_DB = DB_DIR / "semantic_memory.db"

# Lazy-loaded embedder
_embedder = None
_embedder_lock = threading.Lock()


def _get_embedder():
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    _embedder = SentenceTransformer("all-MiniLM-L6-v2")
                except ImportError:
                    _embedder = None
    return _embedder


def _embed(text: str) -> list[float]:
    e = _get_embedder()
    if e is None:
        return []
    return e.encode(text[:512], normalize_embeddings=True).tolist()


@dataclass
class MemoryEntry:
    id: int = 0
    user_id: str = "local"
    memory_type: str = "interaction"  # interaction, fact, preference, reflection, concept
    content: str = ""
    embedding: list = field(default_factory=list)
    timestamp: str = ""
    metadata: dict = field(default_factory=dict)
    access_count: int = 0
    importance: float = 0.5  # 0-1, auto-calculated


class SemanticMemory:
    def __init__(self, user_id: str = "local", db_path: Optional[Path] = None):
        self.user_id = user_id
        self._db_path = db_path or MEMORY_DB
        self._local = threading.Lock()
        self._init_db()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    access_count INTEGER DEFAULT 0,
                    importance REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    concept TEXT NOT NULL,
                    related_terms TEXT DEFAULT '[]',
                    significance REAL DEFAULT 0.5,
                    last_updated TEXT NOT NULL,
                    UNIQUE(user_id, concept)
                );
                CREATE TABLE IF NOT EXISTS consolidated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    importance REAL DEFAULT 0.5
                );
                CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
                CREATE INDEX IF NOT EXISTS idx_concepts_user ON concepts(user_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _calc_importance(self, content: str, memory_type: str) -> float:
        score = 0.3
        # Emotional / high-signal keywords
        high_signal = ["love", "hate", "important", "urgent", "critical", "deadline",
                       "birthday", "anniversary", "remember", "never", "always",
                       "favorite", "best", "worst", "amazing", "terrible"]
        for w in high_signal:
            if w in content.lower():
                score += 0.05
        # Longer content = potentially more significant
        if len(content) > 200:
            score += 0.1
        # Personal references
        if re.search(r'\b(my|i am|i have|i need|i want|i like|i dislike)\b', content.lower()):
            score += 0.15
        # Time references
        if re.search(r'\b(today|tomorrow|yesterday|next week|tonight)\b', content.lower()):
            score += 0.1
        # Type boost
        if memory_type == "preference":
            score += 0.2
        elif memory_type == "reflection":
            score += 0.1
        return min(1.0, score)

    def store(self, memory_type: str, content: str, metadata: Optional[dict] = None,
              user_id: Optional[str] = None):
        uid = user_id or self.user_id
        importance = self._calc_importance(content, memory_type)
        emb = _embed(content)
        emb_blob = json.dumps(emb) if emb else ""
        meta = json.dumps(metadata or {})
        now = datetime.now().isoformat()

        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """INSERT INTO memories (user_id, memory_type, content, embedding, timestamp, metadata, importance, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, memory_type, content, emb_blob, now, meta, importance, now)
            )
            conn.commit()
            # Extract and update concepts
            self._extract_concepts(content, uid, conn)
        finally:
            conn.close()

    def _extract_concepts(self, content: str, uid: str, conn: sqlite3.Connection):
        # Extract noun phrases and key terms
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        words += re.findall(r'\b[a-z]{4,}\b', content.lower())
        common = {"this", "that", "with", "from", "have", "been", "were", "they",
                  "what", "when", "where", "which", "their", "there", "would",
                  "could", "should", "about", "after", "before", "between"}
        words = [w for w in words if w.lower() not in common and len(w) > 3]
        word_freq = {}
        for w in words:
            word_freq[w.lower()] = word_freq.get(w.lower(), 0) + 1
        top = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        for term, freq in top:
            existing = conn.execute(
                "SELECT significance, related_terms FROM concepts WHERE user_id=? AND concept=?",
                (uid, term)
            ).fetchone()
            if existing:
                related = json.loads(existing[1])
                if term not in related:
                    related.append(term)
                conn.execute(
                    "UPDATE concepts SET significance=?, related_terms=?, last_updated=? WHERE user_id=? AND concept=?",
                    (min(1.0, existing[0] + 0.05 * freq), json.dumps(related),
                     datetime.now().isoformat(), uid, term)
                )
            else:
                conn.execute(
                    "INSERT INTO concepts (user_id, concept, related_terms, significance, last_updated) VALUES (?, ?, ?, ?, ?)",
                    (uid, term, json.dumps([]), 0.1 * freq, datetime.now().isoformat())
                )
        conn.commit()

    def search(self, query: str, top_k: int = 5, memory_type: Optional[str] = None,
               min_importance: float = 0.0) -> list[MemoryEntry]:
        q_emb = _embed(query)
        if not q_emb:
            return self._fallback_search(query, top_k, memory_type)

        conn = sqlite3.connect(str(self._db_path))
        try:
            params = [self.user_id]
            type_filter = ""
            if memory_type:
                type_filter = " AND memory_type = ?"
                params.append(memory_type)
            if min_importance > 0:
                type_filter += " AND importance >= ?"
                params.append(min_importance)

            rows = conn.execute(
                f"SELECT id, user_id, memory_type, content, embedding, timestamp, metadata, access_count, importance "
                f"FROM memories WHERE user_id = ?{type_filter}",
                params
            ).fetchall()

            scored = []
            for r in rows:
                emb_blob = r[4]
                if not emb_blob:
                    continue
                try:
                    emb = json.loads(emb_blob)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not emb or not q_emb:
                    continue
                # Cosine similarity
                dot = sum(a * b for a, b in zip(q_emb, emb))
                sim = max(-1.0, min(1.0, dot))
                importance = r[8] or 0.5
                scored.append((sim * 0.7 + importance * 0.3, MemoryEntry(
                    id=r[0], user_id=r[1], memory_type=r[2],
                    content=r[3], embedding=emb, timestamp=r[5],
                    metadata=json.loads(r[6]) if r[6] else {},
                    access_count=r[7] or 0, importance=importance
                )))

            scored.sort(key=lambda x: -x[0])
            # Update access counts
            for _, entry in scored[:top_k]:
                conn.execute("UPDATE memories SET access_count = access_count + 1 WHERE id = ?", (entry.id,))
            conn.commit()
            return [entry for _, entry in scored[:top_k]]
        finally:
            conn.close()

    def _fallback_search(self, query: str, top_k: int = 5,
                         memory_type: Optional[str] = None) -> list[MemoryEntry]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            params = [self.user_id]
            type_filter = ""
            if memory_type:
                type_filter = " AND memory_type = ?"
                params.append(memory_type)
            rows = conn.execute(
                f"SELECT id, user_id, memory_type, content, embedding, timestamp, metadata, access_count, importance "
                f"FROM memories WHERE user_id = ?{type_filter} ORDER BY importance DESC, access_count DESC LIMIT ?",
                params + [top_k]
            ).fetchall()
            return [MemoryEntry(
                id=r[0], user_id=r[1], memory_type=r[2], content=r[3],
                timestamp=r[5], metadata=json.loads(r[6]) if r[6] else {},
                access_count=r[7] or 0, importance=r[8] or 0.5
            ) for r in rows]
        finally:
            conn.close()

    def recall_recent(self, limit: int = 10, memory_type: Optional[str] = None) -> list[MemoryEntry]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            params = [self.user_id]
            type_filter = ""
            if memory_type:
                type_filter = " AND memory_type = ?"
                params.append(memory_type)
            rows = conn.execute(
                f"SELECT id, user_id, memory_type, content, embedding, timestamp, metadata, access_count, importance "
                f"FROM memories WHERE user_id = ?{type_filter} ORDER BY timestamp DESC LIMIT ?",
                params + [limit]
            ).fetchall()
            return [MemoryEntry(
                id=r[0], user_id=r[1], memory_type=r[2], content=r[3],
                timestamp=r[5], metadata=json.loads(r[6]) if r[6] else {},
                access_count=r[7] or 0, importance=r[8] or 0.5
            ) for r in rows]
        finally:
            conn.close()

    def recall_important(self, limit: int = 10) -> list[MemoryEntry]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                "SELECT id, user_id, memory_type, content, embedding, timestamp, metadata, access_count, importance "
                "FROM memories WHERE user_id = ? ORDER BY importance DESC LIMIT ?",
                (self.user_id, limit)
            ).fetchall()
            return [MemoryEntry(
                id=r[0], user_id=r[1], memory_type=r[2], content=r[3],
                timestamp=r[5], metadata=json.loads(r[6]) if r[6] else {},
                access_count=r[7] or 0, importance=r[8] or 0.5
            ) for r in rows]
        finally:
            conn.close()

    def get_concepts(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                "SELECT concept, related_terms, significance, last_updated "
                "FROM concepts WHERE user_id = ? ORDER BY significance DESC LIMIT ?",
                (self.user_id, limit)
            ).fetchall()
            return [
                {"concept": r[0], "related": json.loads(r[1]) if r[1] else [],
                 "significance": r[2], "last_updated": r[3]}
                for r in rows
            ]
        finally:
            conn.close()

    def consolidate(self):
        """Consolidate similar memories into summaries for long-term storage."""
        conn = sqlite3.connect(str(self._db_path))
        try:
            # Find unconsolidated memories older than 1 hour with similar content
            rows = conn.execute(
                "SELECT id, content, memory_type FROM memories WHERE user_id = ? AND importance < 0.7 ORDER BY timestamp ASC",
                (self.user_id,)
            ).fetchall()
            if len(rows) < 5:
                return

            # Group by rough content similarity (word overlap)
            groups = []
            used = set()
            for i, (id1, c1, t1) in enumerate(rows):
                if id1 in used:
                    continue
                group = [(id1, c1, t1)]
                used.add(id1)
                words1 = set(c1.lower().split())
                for j, (id2, c2, t2) in enumerate(rows):
                    if id2 in used or j == i:
                        continue
                    words2 = set(c2.lower().split())
                    if len(words1 & words2) / max(len(words1 | words2), 1) > 0.3:
                        group.append((id2, c2, t2))
                        used.add(id2)
                if len(group) >= 3:
                    groups.append(group)

            for group in groups:
                source_ids = [str(g[0]) for g in group]
                summary = self._summarize_group([g[1] for g in group])
                conn.execute(
                    "INSERT INTO consolidated (user_id, summary, source_ids, created_at, importance) VALUES (?, ?, ?, ?, ?)",
                    (self.user_id, summary, json.dumps(source_ids), datetime.now().isoformat(), 0.3)
                )
            conn.commit()
        finally:
            conn.close()

    def _summarize_group(self, contents: list[str]) -> str:
        if not contents:
            return ""
        # Simple extractive summarization: most representative sentences
        all_words = " ".join(contents).lower().split()
        from collections import Counter
        common = Counter(all_words).most_common(20)
        common_words = {w for w, _ in common if len(w) > 3}
        scored = []
        for c in contents:
            words = set(c.lower().split())
            overlap = len(words & common_words)
            scored.append((overlap, c))
        scored.sort(key=lambda x: -x[0])
        best = scored[0][1] if scored else contents[0]
        return f"[Consolidated] {best[:300]}"

    def get_memory_stats(self) -> dict:
        conn = sqlite3.connect(str(self._db_path))
        try:
            total = conn.execute("SELECT COUNT(*) FROM memories WHERE user_id=?", (self.user_id,)).fetchone()[0]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) FROM memories WHERE user_id=? GROUP BY memory_type",
                (self.user_id,)
            ).fetchall()
            concepts = conn.execute(
                "SELECT COUNT(*) FROM concepts WHERE user_id=?", (self.user_id,)
            ).fetchone()[0]
            top = conn.execute(
                "SELECT content FROM memories WHERE user_id=? ORDER BY importance DESC LIMIT 3",
                (self.user_id,)
            ).fetchall()
            return {
                "total_memories": total,
                "by_type": dict(by_type),
                "concepts_known": concepts,
                "top_memories": [r[0][:100] for r in top],
            }
        finally:
            conn.close()

    def build_relevant_context(self, query: str, max_entries: int = 5) -> str:
        results = self.search(query, top_k=max_entries, min_importance=0.2)
        if not results:
            return ""
        lines = ["[Relevant Past Memories]"]
        for r in results:
            lines.append(f"  [{r.memory_type}] {r.content[:200]}")
        return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────
_memory_store: dict[str, SemanticMemory] = {}

def get_memory(user_id: str = "local") -> SemanticMemory:
    if user_id not in _memory_store:
        _memory_store[user_id] = SemanticMemory(user_id)
    return _memory_store[user_id]