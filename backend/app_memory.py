"""JARVIS Application Memory — Learn Software Over Time.

First encounter: explore → build interaction map → cache.
Next encounter: load map → adapt → use immediately.

Instead of relearning Photoshop every time:
    Photoshop v27
    → known interaction graph
    → adapt changed controls
"""

import os, json, time, logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger("app_memory")

APP_MEMORY_PATH = Path("/opt/jarvis/app_memory.json")


@dataclass
class InteractionMap:
    """Cached interaction knowledge for an application."""
    app_name: str
    version: str = ""
    fingerprint: str = ""  # process name + version hash
    menus: dict = field(default_factory=dict)  # menu_name -> [items]
    keyboard_shortcuts: dict = field(default_factory=dict)  # action -> shortcut
    ui_elements: dict = field(default_factory=dict)  # role -> [{text, location}]
    known_workflows: dict = field(default_factory=dict)  # goal -> [steps]
    last_updated: float = 0
    encounter_count: int = 0
    reliability: float = 0.5  # how reliable is this map


class ApplicationMemory:
    """Learn and remember how to interact with applications."""

    def __init__(self):
        self.apps: dict[str, InteractionMap] = {}
        self._load()

    def _load(self):
        if APP_MEMORY_PATH.exists():
            try:
                data = json.loads(APP_MEMORY_PATH.read_text())
                for name, app_data in data.get("apps", {}).items():
                    self.apps[name] = InteractionMap(**app_data)
            except Exception:
                pass

    def save(self):
        APP_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"apps": {k: asdict(v) for k, v in self.apps.items()}}
        APP_MEMORY_PATH.write_text(json.dumps(data, indent=2))

    def get_app(self, app_name: str) -> Optional[InteractionMap]:
        """Get cached interaction map for an app."""
        return self.apps.get(app_name.lower())

    def record_encounter(self, app_name: str, interactions: list[dict] = None):
        """Record that we interacted with an app and what worked."""
        key = app_name.lower()
        if key not in self.apps:
            self.apps[key] = InteractionMap(app_name=app_name)

        app = self.apps[key]
        app.encounter_count += 1
        app.last_updated = time.time()

        if interactions:
            for ix in interactions:
                action = ix.get("action", "")
                target = ix.get("target", {})
                success = ix.get("success", False)

                if action and target:
                    role = target.get("role", "unknown")
                    text = target.get("text", "")
                    if role not in app.ui_elements:
                        app.ui_elements[role] = []
                    # Update or add element
                    found = False
                    for el in app.ui_elements[role]:
                        if el.get("text") == text:
                            el["success_count"] = el.get("success_count", 0) + (1 if success else 0)
                            el["total_count"] = el.get("total_count", 0) + 1
                            el["last_seen"] = time.time()
                            found = True
                            break
                    if not found:
                        app.ui_elements[role].append({
                            "text": text,
                            "success_count": 1 if success else 0,
                            "total_count": 1,
                            "last_seen": time.time(),
                        })

            # Update reliability
            successes = sum(1 for ix in interactions if ix.get("success"))
            total = len(interactions)
            if total > 0:
                app.reliability = (app.reliability * 0.7) + (successes / total * 0.3)

        self.save()

    def learn_shortcut(self, app_name: str, action: str, shortcut: str):
        """Learn a keyboard shortcut for an app."""
        key = app_name.lower()
        if key not in self.apps:
            self.apps[key] = InteractionMap(app_name=app_name)
        self.apps[key].keyboard_shortcuts[action] = shortcut
        self.save()

    def learn_menu(self, app_name: str, menu_name: str, items: list[str]):
        """Learn a menu structure."""
        key = app_name.lower()
        if key not in self.apps:
            self.apps[key] = InteractionMap(app_name=app_name)
        self.apps[key].menus[menu_name] = items
        self.save()

    def learn_workflow(self, app_name: str, goal: str, steps: list[dict]):
        """Learn how to accomplish a goal in an app."""
        key = app_name.lower()
        if key not in self.apps:
            self.apps[key] = InteractionMap(app_name=app_name)
        self.apps[key].known_workflows[goal] = steps
        self.save()

    def get_workflow(self, app_name: str, goal: str) -> Optional[list[dict]]:
        """Get cached workflow for a goal in an app."""
        app = self.apps.get(app_name.lower())
        if app:
            return app.known_workflows.get(goal)
        return None

    def get_reliable_elements(self, app_name: str, role: str = "") -> list[dict]:
        """Get UI elements that have proven reliable (>80% success rate)."""
        app = self.apps.get(app_name.lower())
        if not app:
            return []

        elements = []
        for el_role, els in app.ui_elements.items():
            if role and el_role != role:
                continue
            for el in els:
                total = el.get("total_count", 0)
                successes = el.get("success_count", 0)
                if total >= 2 and successes / total >= 0.8:
                    elements.append({
                        "role": el_role,
                        "text": el["text"],
                        "reliability": successes / total,
                        "uses": total,
                    })
        return elements

    def get_stats(self) -> dict:
        """Get application memory statistics."""
        total_apps = len(self.apps)
        total_encounters = sum(a.encounter_count for a in self.apps.values())
        total_workflows = sum(len(a.known_workflows) for a in self.apps.values())
        total_shortcuts = sum(len(a.keyboard_shortcuts) for a in self.apps.values())

        return {
            "apps_learned": total_apps,
            "total_encounters": total_encounters,
            "total_workflows": total_workflows,
            "total_shortcuts": total_shortcuts,
            "most_used": sorted(
                [(a.app_name, a.encounter_count) for a in self.apps.values()],
                key=lambda x: x[1], reverse=True
            )[:5],
        }


# ── Singleton ──
_memory: Optional[ApplicationMemory] = None

def get_app_memory() -> ApplicationMemory:
    global _memory
    if _memory is None:
        _memory = ApplicationMemory()
    return _memory
