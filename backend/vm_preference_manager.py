"""
VM Preference Manager — learns what the user prefers to run in VM vs desktop.
Tracks patterns, suggests VM for repetitive/background tasks, remembers choices.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional


_PREFS_DIR = Path(os.getenv("JARVIS_DATA", os.path.expanduser("~/.jarvis"))) / "preferences"
_PREFS_FILE = _PREFS_DIR / "vm_preferences.json"


class VMPreferenceManager:
    """Learns and remembers user's VM vs desktop preferences."""

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self._data = self._load()
        self._session_choices: list[dict] = []

    def _load(self) -> dict:
        _PREFS_DIR.mkdir(parents=True, exist_ok=True)
        if _PREFS_FILE.exists():
            try:
                return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "choices": [],
            "task_patterns": {},
            "auto_rules": [],
            "stats": {"vm_count": 0, "desktop_count": 0},
        }

    def _save(self):
        _PREFS_DIR.mkdir(parents=True, exist_ok=True)
        _PREFS_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def record_choice(self, task_text: str, target: str, confirmed: bool = True):
        """Record a user choice: target is 'vm' or 'desktop'."""
        entry = {
            "task": task_text[:200],
            "target": target,
            "timestamp": time.time(),
            "confirmed": confirmed,
        }
        self._data["choices"].append(entry)
        # Keep last 200 choices
        self._data["choices"] = self._data["choices"][-200:]

        # Update stats
        if target == "vm":
            self._data["stats"]["vm_count"] += 1
        else:
            self._data["stats"]["desktop_count"] += 1

        # Update pattern tracking
        self._update_patterns(task_text, target)
        self._session_choices.append(entry)
        self._save()

    def _update_patterns(self, task_text: str, target: str):
        """Extract keywords and track which target user prefers for each."""
        lower = task_text.lower()
        keywords = set()
        # Extract meaningful words (skip stop words)
        stop = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
                "by", "from", "is", "are", "was", "were", "be", "been", "being",
                "have", "has", "had", "do", "does", "did", "will", "would",
                "could", "should", "may", "might", "can", "shall", "my", "your",
                "his", "her", "its", "our", "their", "this", "that", "these",
                "those", "i", "you", "he", "she", "it", "we", "they", "me",
                "him", "us", "them", "open", "run", "start", "launch", "make",
                "create", "do", "go", "get", "find", "search", "show", "look"}
        for word in lower.split():
            w = word.strip(".,!?;:'\"")
            if len(w) > 2 and w not in stop:
                keywords.add(w)

        for kw in keywords:
            if kw not in self._data["task_patterns"]:
                self._data["task_patterns"][kw] = {"vm": 0, "desktop": 0}
            self._data["task_patterns"][kw][target] += 1

    def suggest_target(self, task_text: str) -> Optional[str]:
        """Suggest 'vm' or 'desktop' based on learned preferences, or None if unsure."""
        lower = task_text.lower()
        words = set(w.strip(".,!?;:'\"") for w in lower.split() if len(w) > 2)
        vm_score = 0
        desktop_score = 0

        for kw in words:
            pattern = self._data["task_patterns"].get(kw)
            if pattern:
                vm_score += pattern.get("vm", 0)
                desktop_score += pattern.get("desktop", 0)

        # Need at least 3 signals to suggest
        total = vm_score + desktop_score
        if total < 3:
            return None

        ratio = vm_score / total
        if ratio > 0.7:
            return "vm"
        elif ratio < 0.3:
            return "desktop"
        return None

    def should_ask_confirmation(self, task_text: str) -> bool:
        """Determine if we need to ask user where to run this."""
        lower = task_text.lower()

        # Explicit VM request — no confirmation needed
        vm_keywords = ["in vm", "in virtual", "in the vm", "in a vm",
                       "headless", "background", "isolated", "sandbox",
                       "in virtual desktop", "on virtual desktop"]
        if any(kw in lower for kw in vm_keywords):
            return False

        # Explicit desktop request — no confirmation needed
        desktop_keywords = ["on my desktop", "on my screen", "here",
                            "on my computer", "on this machine", "locally"]
        if any(kw in lower for kw in desktop_keywords):
            return False

        # NEVER ask for simple questions, chat, greetings, searches
        never_ask = ["what", "who", "how", "when", "where", "why", "search",
                     "find", "look up", "tell me", "name", "time", "date",
                     "weather", "news", "help", "hello", "hi", "hey",
                     "status", "info", "about", "explain", "define",
                     "calculate", "math", "convert"]
        first_word = lower.split()[0] if lower.split() else ""
        if first_word in never_ask:
            return False
        # Also skip if it's clearly a question (ends with ?)
        if task_text.strip().endswith("?"):
            return False

        # Only ask for tasks that are clearly automation/computer-use
        automation_triggers = ["batch", "automate", "scrape", "download multiple",
                               "process files", "convert files", "rename files",
                               "compress", "install", "update", "scan",
                               "backup", "sync", "migrate", "deploy",
                               "run script", "execute", "build"]
        if any(kw in lower for kw in automation_triggers):
            return True

        # Default: don't ask — most tasks should just run on desktop
        return False

    def get_stats(self) -> dict:
        return {
            "total_choices": len(self._data["choices"]),
            "vm_count": self._data["stats"]["vm_count"],
            "desktop_count": self._data["stats"]["desktop_count"],
            "top_patterns": self._get_top_patterns(),
        }

    def _get_top_patterns(self) -> list[dict]:
        patterns = []
        for kw, counts in self._data["task_patterns"].items():
            total = counts["vm"] + counts["desktop"]
            if total >= 2:
                preferred = "vm" if counts["vm"] > counts["desktop"] else "desktop"
                patterns.append({"keyword": kw, "preferred": preferred, "count": total})
        return sorted(patterns, key=lambda x: x["count"], reverse=True)[:10]


# Singleton
_managers: dict[str, VMPreferenceManager] = {}


def get_vm_prefs(user_id: str = "local") -> VMPreferenceManager:
    if user_id not in _managers:
        _managers[user_id] = VMPreferenceManager(user_id)
    return _managers[user_id]
