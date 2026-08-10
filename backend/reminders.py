"""Local reminders storage — JSON file based."""

import json
import os
import uuid
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")


def _load():
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE) as f:
        return json.load(f)


def _save(reminders):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, indent=2)


def create_reminder(user_id: str, title: str, description: str = "", due_date: str = "") -> dict:
    reminders = _load()
    reminder = {
        "id": uuid.uuid4().hex[:12],
        "user_id": user_id,
        "title": title,
        "description": description,
        "due_date": due_date,
        "completed": False,
        "created_at": datetime.now().isoformat(),
    }
    reminders.append(reminder)
    _save(reminders)
    return reminder


def list_reminders(user_id: str) -> list[dict]:
    return [r for r in _load() if r["user_id"] == user_id]


def update_reminder(reminder_id: str, updates: dict) -> dict | None:
    reminders = _load()
    for r in reminders:
        if r["id"] == reminder_id:
            r.update({k: v for k, v in updates.items() if v is not None})
            _save(reminders)
            return r
    return None


def delete_reminder(reminder_id: str) -> bool:
    reminders = _load()
    filtered = [r for r in reminders if r["id"] != reminder_id]
    if len(filtered) == len(reminders):
        return False
    _save(filtered)
    return True
