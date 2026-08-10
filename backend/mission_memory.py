"""JARVIS Mission Memory — Long-Term Memory of Workflows.

Remembers successful/failed workflows, people, files, projects,
and user preferences. Avoids repeating mistakes. Builds on past
experience to plan faster.

ARCHITECTURE:

    COMPLETED MISSIONS → MEMORY INDEX → FUTURE MISSIONS
         │                    │               │
         ├── What worked      ├── People      ├── Similar plans
         ├── What failed      ├── Files       ├── Preferred tools
         ├── Patterns         ├── Projects    ├── Learned shortcuts
         └── Preferences      └── Workflows   └── Avoided mistakes
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

log = logging.getLogger("memory")


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    category: str  # "workflow", "person", "file", "project", "preference", "mistake"
    key: str  # searchable key
    content: Dict[str, Any] = field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0
    created_at: float = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "key": self.key,
            "content": self.content,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "tags": self.tags,
        }


class MissionMemory:
    """Long-term memory system for JARVIS missions.

    Stores and retrieves:
    - Successful workflows (what worked)
    - Failed attempts (what to avoid)
    - User preferences (how they like things)
    - People (contacts, roles)
    - Files (locations, purposes)
    - Projects (context, history)
    """

    def __init__(self, memory_dir: str = None):
        self._memory_dir = memory_dir or os.path.join(
            os.path.expanduser("~"), ".jarvis", "memory"
        )
        os.makedirs(self._memory_dir, exist_ok=True)

        self._entries: Dict[str, MemoryEntry] = {}
        self._index: Dict[str, List[str]] = {}  # category -> [entry_ids]
        self._tag_index: Dict[str, List[str]] = {}  # tag -> [entry_ids]

        self._load()

    def _load(self):
        """Load memory from disk."""
        memory_file = os.path.join(self._memory_dir, "memory.json")
        if os.path.exists(memory_file):
            try:
                with open(memory_file) as f:
                    data = json.load(f)
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry(**entry_data)
                    self._entries[entry.id] = entry
                log.info(f"[MEMORY] Loaded {len(self._entries)} entries")
            except Exception as e:
                log.warning(f"[MEMORY] Failed to load: {e}")
        self._rebuild_index()

    def _save(self):
        """Save memory to disk."""
        memory_file = os.path.join(self._memory_dir, "memory.json")
        with open(memory_file, "w") as f:
            json.dump(
                {"entries": [e.to_dict() for e in self._entries.values()]},
                f, indent=2
            )

    def _rebuild_index(self):
        """Rebuild search indices."""
        self._index.clear()
        self._tag_index.clear()
        for entry in self._entries.values():
            if entry.category not in self._index:
                self._index[entry.category] = []
            self._index[entry.category].append(entry.id)
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = []
                self._tag_index[tag].append(entry.id)

    def remember_workflow(self, goal: str, steps: List[Dict[str, Any]],
                         success: bool, context: Dict[str, Any] = None):
        """Remember a workflow (successful or failed)."""
        entry_id = f"workflow_{hash(goal)}_{int(time.time())}"
        entry = MemoryEntry(
            id=entry_id,
            category="workflow",
            key=goal.lower(),
            content={
                "goal": goal,
                "steps": steps,
                "context": context or {},
            },
            success_count=1 if success else 0,
            failure_count=0 if success else 1,
            last_used=time.time(),
            created_at=time.time(),
            tags=self._extract_tags(goal),
        )

        # Check if similar workflow exists
        existing = self._find_similar_workflow(goal)
        if existing:
            # Update existing entry
            if success:
                existing.success_count += 1
            else:
                existing.failure_count += 1
            existing.last_used = time.time()
            log.info(f"[MEMORY] Updated workflow: {existing.key} "
                    f"(success={existing.success_count}, fail={existing.failure_count})")
        else:
            self._entries[entry_id] = entry
            log.info(f"[MEMORY] New workflow: {goal[:50]}...")

        self._rebuild_index()
        self._save()

    def remember_person(self, name: str, email: str = "",
                       role: str = "", context: str = ""):
        """Remember a person."""
        entry_id = f"person_{hash(name.lower())}"
        existing = self._entries.get(entry_id)
        if existing:
            existing.content.update({
                "email": email or existing.content.get("email", ""),
                "role": role or existing.content.get("role", ""),
                "context": context or existing.content.get("context", ""),
            })
            existing.last_used = time.time()
        else:
            entry = MemoryEntry(
                id=entry_id,
                category="person",
                key=name.lower(),
                content={"name": name, "email": email, "role": role, "context": context},
                last_used=time.time(),
                created_at=time.time(),
                tags=[name.lower(), email.lower()] if email else [name.lower()],
            )
            self._entries[entry_id] = entry

        self._rebuild_index()
        self._save()

    def remember_file(self, path: str, purpose: str = "",
                     project: str = ""):
        """Remember a file and its purpose."""
        filename = os.path.basename(path)
        entry_id = f"file_{hash(path.lower())}"
        existing = self._entries.get(entry_id)
        if existing:
            existing.content.update({
                "purpose": purpose or existing.content.get("purpose", ""),
                "project": project or existing.content.get("project", ""),
            })
            existing.last_used = time.time()
        else:
            entry = MemoryEntry(
                id=entry_id,
                category="file",
                key=filename.lower(),
                content={"path": path, "purpose": purpose, "project": project},
                last_used=time.time(),
                created_at=time.time(),
                tags=[filename.lower(), project.lower()] if project else [filename.lower()],
            )
            self._entries[entry_id] = entry

        self._rebuild_index()
        self._save()

    def remember_preference(self, key: str, value: Any,
                           context: str = ""):
        """Remember a user preference."""
        entry_id = f"pref_{hash(key.lower())}"
        existing = self._entries.get(entry_id)
        if existing:
            existing.content["value"] = value
            existing.content["context"] = context
            existing.last_used = time.time()
        else:
            entry = MemoryEntry(
                id=entry_id,
                category="preference",
                key=key.lower(),
                content={"key": key, "value": value, "context": context},
                last_used=time.time(),
                created_at=time.time(),
                tags=[key.lower()],
            )
            self._entries[entry_id] = entry

        self._rebuild_index()
        self._save()

    def remember_mistake(self, action: str, error: str,
                        avoidance: str):
        """Remember a mistake to avoid repeating it."""
        entry_id = f"mistake_{hash(action.lower())}_{int(time.time())}"
        entry = MemoryEntry(
            id=entry_id,
            category="mistake",
            key=action.lower(),
            content={
                "action": action,
                "error": error,
                "avoidance": avoidance,
            },
            failure_count=1,
            last_used=time.time(),
            created_at=time.time(),
            tags=self._extract_tags(action + " " + avoidance),
        )
        self._entries[entry_id] = entry
        self._rebuild_index()
        self._save()
        log.info(f"[MEMORY] Recorded mistake: {action[:50]}...")

    def recall(self, query: str, category: str = None,
              limit: int = 5) -> List[MemoryEntry]:
        """Recall memories matching a query."""
        query_lower = query.lower()
        candidates = []

        for entry in self._entries.values():
            if category and entry.category != category:
                continue

            # Score by relevance
            score = 0
            if query_lower in entry.key:
                score += 10
            for tag in entry.tags:
                if query_lower in tag:
                    score += 5
            # Boost recent entries
            if time.time() - entry.last_used < 86400:  # 24h
                score += 3
            # Boost successful entries
            if entry.success_count > entry.failure_count:
                score += 2
            # Penalize failed entries
            if entry.failure_count > entry.success_count:
                score -= 2

            if score > 0:
                candidates.append((score, entry))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in candidates[:limit]]

    def _find_similar_workflow(self, goal: str) -> Optional[MemoryEntry]:
        """Find a similar workflow in memory."""
        goal_lower = goal.lower()
        for entry in self._entries.values():
            if entry.category == "workflow":
                if goal_lower in entry.key or entry.key in goal_lower:
                    return entry
        return None

    def _extract_tags(self, text: str) -> List[str]:
        """Extract meaningful tags from text."""
        words = text.lower().split()
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on",
                    "at", "to", "for", "of", "with", "by", "from", "and", "or",
                    "but", "not", "it", "this", "that", "my", "your", "his",
                    "her", "its", "our", "their", "be", "been", "being", "have",
                    "has", "had", "do", "does", "did", "will", "would", "could",
                    "should", "may", "might", "can", "shall", "just"}
        tags = [w for w in words if len(w) > 2 and w not in stopwords]
        return list(set(tags))[:10]

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        category_counts = {}
        for entry in self._entries.values():
            category_counts[entry.category] = category_counts.get(entry.category, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_category": category_counts,
            "total_success": sum(e.success_count for e in self._entries.values()),
            "total_failures": sum(e.failure_count for e in self._entries.values()),
        }

    def get_context_string(self) -> str:
        """Get a context string for the planner."""
        lines = ["MEMORY:"]

        # Recent successful workflows
        workflows = [e for e in self._entries.values()
                    if e.category == "workflow" and e.success_count > 0]
        workflows.sort(key=lambda e: e.last_used, reverse=True)
        if workflows:
            lines.append("\nSuccessful past workflows:")
            for w in workflows[:3]:
                lines.append(f"  ✓ {w.content.get('goal', w.key)[:60]}")

        # Mistakes to avoid
        mistakes = [e for e in self._entries.values()
                   if e.category == "mistake"]
        if mistakes:
            lines.append("\nMistakes to avoid:")
            for m in mistakes[:3]:
                lines.append(f"  ✗ {m.content.get('avoidance', m.key)[:60]}")

        # User preferences
        prefs = [e for e in self._entries.values()
                if e.category == "preference"]
        if prefs:
            lines.append("\nUser preferences:")
            for p in prefs[:5]:
                lines.append(f"  • {p.key}: {p.content.get('value', '')}")

        return "\n".join(lines)


# ── Singleton ──
_memory: Optional[MissionMemory] = None


def get_mission_memory(memory_dir: str = None) -> MissionMemory:
    global _memory
    if _memory is None:
        _memory = MissionMemory(memory_dir)
    return _memory
