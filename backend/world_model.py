"""JARVIS Persistent World Model — Computer Memory.

A continuously updated representation of everything JARVIS knows
about the computer. Don't make the LLM rediscover the computer
every time.

The World Model:
  - Remembers files, windows, applications, browser tabs
  - Tracks what changed since last observation
  - Resolves natural-language references to objects
  - Provides context for planning
  - Learns from mission history

ARCHITECTURE:

    PERCEPTION → WORLD MODEL → PLANNER
                    │
                    ├── Objects (files, windows, apps)
                    ├── Relationships (belongs_to, located_in)
                    ├── History (what changed, when)
                    ├── Preferences (user patterns)
                    └── Missions (past, present)
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field, asdict

log = logging.getLogger("world_model")


@dataclass
class WorldObject:
    """An object in the world model."""
    id: str
    type: str  # "file", "window", "application", "browser_tab", "process"
    name: str
    location: str = ""  # jarvis:// URI
    last_seen: float = 0
    last_modified: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    # relationships: {"belongs_to": ["mission_123"], "located_in": ["desktop"]}

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChangeRecord:
    """A recorded change in the world."""
    timestamp: float
    object_id: str
    change_type: str  # "created", "modified", "deleted", "moved", "opened", "closed"
    details: str = ""
    old_state: Dict[str, Any] = field(default_factory=dict)
    new_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class WorldModel:
    """Persistent world model — JARVIS's memory of the computer.

    Continuously updated by perception system.
    Queried by planner and executor.
    """

    def __init__(self, model_dir: str = None):
        self._model_dir = model_dir or os.path.join(
            os.path.expanduser("~"), ".jarvis", "world_model"
        )
        os.makedirs(self._model_dir, exist_ok=True)

        self._objects: Dict[str, WorldObject] = {}
        self._changes: List[ChangeRecord] = []
        self._index: Dict[str, List[str]] = {}  # type -> [object_ids]
        self._name_index: Dict[str, List[str]] = {}  # name_lower -> [object_ids]

        self._load()

    def _load(self):
        """Load world model from disk."""
        objects_file = os.path.join(self._model_dir, "objects.json")
        if os.path.exists(objects_file):
            try:
                with open(objects_file) as f:
                    data = json.load(f)
                for obj_data in data.get("objects", []):
                    obj = WorldObject(**obj_data)
                    self._objects[obj.id] = obj
                log.info(f"[WORLD] Loaded {len(self._objects)} objects")
            except Exception as e:
                log.warning(f"[WORLD] Failed to load: {e}")

        changes_file = os.path.join(self._model_dir, "changes.json")
        if os.path.exists(changes_file):
            try:
                with open(changes_file) as f:
                    data = json.load(f)
                for ch in data.get("changes", []):
                    self._changes.append(ChangeRecord(**ch))
            except Exception:
                pass

        self._rebuild_index()

    def _save(self):
        """Save world model to disk."""
        objects_file = os.path.join(self._model_dir, "objects.json")
        with open(objects_file, "w") as f:
            json.dump(
                {"objects": [o.to_dict() for o in self._objects.values()]},
                f, indent=2
            )

        # Keep last 1000 changes
        changes_file = os.path.join(self._model_dir, "changes.json")
        with open(changes_file, "w") as f:
            json.dump(
                {"changes": [c.to_dict() for c in self._changes[-1000:]]},
                f, indent=2
            )

    def _rebuild_index(self):
        """Rebuild search indices."""
        self._index.clear()
        self._name_index.clear()
        for obj in self._objects.values():
            # Type index
            if obj.type not in self._index:
                self._index[obj.type] = []
            self._index[obj.type].append(obj.id)
            # Name index
            name_lower = obj.name.lower()
            if name_lower not in self._name_index:
                self._name_index[name_lower] = []
            self._name_index[name_lower].append(obj.id)

    def update_from_perception(self, snapshot) -> List[ChangeRecord]:
        """Update the world model from a perception snapshot.

        Returns list of changes detected.
        """
        changes = []
        now = time.time()

        # Update windows
        if hasattr(snapshot, 'windows'):
            seen_window_ids = set()
            for win in snapshot.windows:
                obj_id = f"window_{win.id}"
                seen_window_ids.add(obj_id)

                existing = self._objects.get(obj_id)
                if existing:
                    # Check for changes
                    if existing.name != win.title:
                        change = ChangeRecord(
                            timestamp=now, object_id=obj_id,
                            change_type="modified",
                            details=f"Title changed: {existing.name} → {win.title}",
                            old_state={"name": existing.name},
                            new_state={"name": win.title},
                        )
                        changes.append(change)
                        existing.name = win.title
                    existing.last_seen = now
                else:
                    # New window
                    obj = WorldObject(
                        id=obj_id, type="window",
                        name=win.title,
                        location=f"jarvis://window/{win.id}",
                        last_seen=now,
                        metadata={"app": win.app_name, "pid": win.pid},
                    )
                    self._objects[obj_id] = obj
                    change = ChangeRecord(
                        timestamp=now, object_id=obj_id,
                        change_type="created",
                        details=f"New window: {win.title}",
                    )
                    changes.append(change)

            # Detect closed windows
            for obj_id, obj in list(self._objects.items()):
                if obj.type == "window" and obj_id not in seen_window_ids:
                    if now - obj.last_seen > 30:  # 30s timeout
                        change = ChangeRecord(
                            timestamp=now, object_id=obj_id,
                            change_type="deleted",
                            details=f"Window closed: {obj.name}",
                        )
                        changes.append(change)
                        del self._objects[obj_id]

        # Update browser state
        if hasattr(snapshot, 'browser') and snapshot.browser:
            browser = snapshot.browser
            for tab in browser.tabs:
                tab_id = f"tab_{hash(tab.get('url', ''))}"
                existing = self._objects.get(tab_id)
                if not existing:
                    obj = WorldObject(
                        id=tab_id, type="browser_tab",
                        name=tab.get("title", ""),
                        location=tab.get("url", ""),
                        last_seen=now,
                        metadata={"url": tab.get("url", "")},
                    )
                    self._objects[tab_id] = obj

        # Update filesystem
        if hasattr(snapshot, 'filesystem') and snapshot.filesystem:
            fs = snapshot.filesystem
            for file_list in [fs.desktop_files, fs.downloads_files, fs.recent_files]:
                for f in file_list:
                    file_id = f"file_{hash(f.get('path', ''))}"
                    existing = self._objects.get(file_id)
                    if existing:
                        existing.last_seen = now
                    else:
                        obj = WorldObject(
                            id=file_id, type="file",
                            name=f.get("name", ""),
                            location=f.get("path", ""),
                            last_seen=now,
                            last_modified=f.get("modified", 0),
                            metadata={"size": f.get("size", 0)},
                        )
                        self._objects[file_id] = obj

        # Record all changes
        self._changes.extend(changes)
        self._rebuild_index()
        self._save()

        if changes:
            log.info(f"[WORLD] {len(changes)} changes detected")

        return changes

    def query(self, object_type: str = None, name_contains: str = None,
             location_contains: str = None,
             last_seen_within: float = None) -> List[WorldObject]:
        """Query objects in the world model."""
        candidates = list(self._objects.values())

        if object_type:
            candidates = [o for o in candidates if o.type == object_type]

        if name_contains:
            name_lower = name_contains.lower()
            candidates = [o for o in candidates if name_lower in o.name.lower()]

        if location_contains:
            loc_lower = location_contains.lower()
            candidates = [o for o in candidates if loc_lower in o.location.lower()]

        if last_seen_within:
            cutoff = time.time() - last_seen_within
            candidates = [o for o in candidates if o.last_seen > cutoff]

        return candidates

    def find(self, reference: str) -> List[WorldObject]:
        """Find objects matching a natural-language reference."""
        ref_lower = reference.lower()
        candidates = []

        # Name match
        for obj in self._objects.values():
            if ref_lower in obj.name.lower():
                candidates.append(obj)

        # Type hints
        type_hints = {
            "document": "file", "docx": "file", "pdf": "file",
            "spreadsheet": "file", "xlsx": "file",
            "image": "file", "video": "file",
            "browser": "browser_tab", "chrome": "browser_tab",
            "window": "window", "app": "application",
        }
        for hint, obj_type in type_hints.items():
            if hint in ref_lower:
                type_matches = self.query(object_type=obj_type)
                candidates.extend(type_matches)

        # Deduplicate
        seen = set()
        unique = []
        for c in candidates:
            if c.id not in seen:
                seen.add(c.id)
                unique.append(c)

        # Sort by last seen (most recent first)
        unique.sort(key=lambda o: o.last_seen, reverse=True)

        return unique[:10]

    def get_recent_changes(self, limit: int = 20) -> List[ChangeRecord]:
        """Get recent changes in the world."""
        return self._changes[-limit:]

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the world model."""
        type_counts = {}
        for obj in self._objects.values():
            type_counts[obj.type] = type_counts.get(obj.type, 0) + 1

        return {
            "total_objects": len(self._objects),
            "by_type": type_counts,
            "recent_changes": len(self._changes),
            "last_update": self._changes[-1].timestamp if self._changes else 0,
        }

    def get_context_string(self) -> str:
        """Get a context string for the LLM planner."""
        lines = ["CURRENT WORLD STATE:"]

        # Active windows
        windows = self.query(object_type="window")
        if windows:
            lines.append("\nOpen windows:")
            for w in windows[:5]:
                lines.append(f"  - {w.name}")

        # Browser tabs
        tabs = self.query(object_type="browser_tab")
        if tabs:
            lines.append("\nBrowser tabs:")
            for t in tabs[:5]:
                lines.append(f"  - {t.name}: {t.location}")

        # Recent files
        files = self.query(object_type="file", last_seen_within=3600)
        if files:
            lines.append("\nRecent files:")
            for f in files[:5]:
                lines.append(f"  - {f.name}")

        return "\n".join(lines)


# ── Singleton ──
_model: Optional[WorldModel] = None


def get_world_model() -> WorldModel:
    global _model
    if _model is None:
        _model = WorldModel()
    return _model
