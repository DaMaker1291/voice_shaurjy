"""JARVIS Automation — Scheduled missions and background tasks.

JARVIS can run missions automatically on schedules:
- Every Monday at 9am: research competitors
- Every day: monitor website for changes
- Every hour: check server health
- Custom cron expressions
"""

import os
import json
import time
import sched
import logging
import threading
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

log = logging.getLogger("automation")

AUTOMATION_FILE = Path.home() / ".jarvis" / "automations.json"


class ScheduleType(Enum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


@dataclass
class Automation:
    id: str
    name: str
    description: str
    mission_objective: str
    schedule_type: str
    schedule_value: str = ""  # cron expression or time
    enabled: bool = True
    last_run: float = 0
    next_run: float = 0
    run_count: int = 0
    max_runs: int = 0  # 0 = unlimited
    created_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "mission_objective": self.mission_objective,
            "schedule_type": self.schedule_type,
            "schedule_value": self.schedule_value,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Automation":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AutomationScheduler:
    """Manages scheduled missions."""

    def __init__(self, mission_callback: Callable = None):
        self._automations: Dict[str, Automation] = {}
        self._scheduler = sched.scheduler(time.time, time.sleep)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._mission_callback = mission_callback
        self._load()

    def _load(self):
        """Load automations from disk."""
        if AUTOMATION_FILE.exists():
            try:
                data = json.loads(AUTOMATION_FILE.read_text())
                for item in data:
                    auto = Automation.from_dict(item)
                    self._automations[auto.id] = auto
                log.info(f"[AUTOMATION] Loaded {len(self._automations)} automations")
            except Exception as e:
                log.error(f"[AUTOMATION] Load failed: {e}")

    def _save(self):
        """Save automations to disk."""
        AUTOMATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [a.to_dict() for a in self._automations.values()]
        AUTOMATION_FILE.write_text(json.dumps(data, indent=2))

    def create(self, name: str, description: str, mission_objective: str,
               schedule_type: str, schedule_value: str = "",
               enabled: bool = True, max_runs: int = 0) -> Automation:
        """Create a new automation."""
        import uuid
        auto = Automation(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            mission_objective=mission_objective,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            enabled=enabled,
            max_runs=max_runs,
            created_at=time.time(),
            next_run=self._calculate_next_run(schedule_type, schedule_value),
        )
        self._automations[auto.id] = auto
        self._save()
        log.info(f"[AUTOMATION] Created: {name}")
        return auto

    def update(self, automation_id: str, **kwargs) -> Optional[Automation]:
        """Update an automation."""
        auto = self._automations.get(automation_id)
        if not auto:
            return None
        for key, value in kwargs.items():
            if hasattr(auto, key):
                setattr(auto, key, value)
        if "schedule_type" in kwargs or "schedule_value" in kwargs:
            auto.next_run = self._calculate_next_run(auto.schedule_type, auto.schedule_value)
        self._save()
        return auto

    def delete(self, automation_id: str) -> bool:
        """Delete an automation."""
        if automation_id in self._automations:
            del self._automations[automation_id]
            self._save()
            return True
        return False

    def list_all(self) -> List[dict]:
        """List all automations."""
        return [a.to_dict() for a in self._automations.values()]

    def get_due(self) -> List[Automation]:
        """Get automations that are due to run."""
        now = time.time()
        return [a for a in self._automations.values() if a.enabled and a.next_run <= now]

    def run_now(self, automation_id: str) -> dict:
        """Manually trigger an automation."""
        auto = self._automations.get(automation_id)
        if not auto:
            return {"ok": False, "error": "Automation not found"}

        if self._mission_callback:
            try:
                self._mission_callback(auto.mission_objective, auto.id)
                auto.last_run = time.time()
                auto.run_count += 1
                auto.next_run = self._calculate_next_run(auto.schedule_type, auto.schedule_value)
                self._save()
                return {"ok": True, "message": f"Triggered: {auto.name}"}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        return {"ok": False, "error": "No mission callback configured"}

    def _calculate_next_run(self, schedule_type: str, schedule_value: str) -> float:
        """Calculate next run time based on schedule."""
        now = datetime.now()

        if schedule_type == "once" and schedule_value:
            try:
                target = datetime.fromisoformat(schedule_value)
                return target.timestamp()
            except Exception:
                return 0

        elif schedule_type == "hourly":
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).timestamp()

        elif schedule_type == "daily":
            try:
                hour, minute = map(int, schedule_value.split(":"))
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target.timestamp()
            except Exception:
                return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).timestamp()

        elif schedule_type == "weekly":
            try:
                day, time_str = schedule_value.split(" ")
                day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
                target_day = day_map.get(day.lower(), 0)
                hour, minute = map(int, time_str.split(":"))
                days_ahead = (target_day - now.weekday()) % 7
                target = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(weeks=1)
                return target.timestamp()
            except Exception:
                return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).timestamp()

        return 0

    def _check_loop(self):
        """Background loop to check for due automations."""
        while self._running:
            try:
                due = self.get_due()
                for auto in due:
                    if self._mission_callback:
                        self._mission_callback(auto.mission_objective, auto.id)
                        auto.last_run = time.time()
                        auto.run_count += 1
                        auto.next_run = self._calculate_next_run(auto.schedule_type, auto.schedule_value)
                        self._save()
                time.sleep(60)  # Check every minute
            except Exception as e:
                log.error(f"[AUTOMATION] Check loop error: {e}")
                time.sleep(60)

    def start(self):
        """Start the automation scheduler."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        log.info("[AUTOMATION] Scheduler started")

    def stop(self):
        """Stop the automation scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("[AUTOMATION] Scheduler stopped")


# Global instance
_scheduler = None


def get_automation_scheduler(mission_callback: Callable = None) -> AutomationScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutomationScheduler(mission_callback)
    return _scheduler
