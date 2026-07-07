#!/usr/bin/env python3
"""
Proactive Conversation Engine for JARVIS
Enables JARVIS to initiate conversations, monitor events, and act without being asked.
"""
import time
import json
import threading
from typing import Dict, Any, List, Optional, Callable

class ProactiveEngine:
    """
    Enables JARVIS to:
    - Monitor email/calendar for new events
    - Send reminders
    - Auto-act on triggers
    - Start conversations proactively
    - Track ongoing tasks and update user
    """

    def __init__(self):
        self.monitors = {}
        self.reminders = []
        self.conversation_queue = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        """Start the proactive monitoring engine."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the proactive monitoring engine."""
        self._running = False

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_reminders()
                self._check_monitors()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"[ProactiveEngine] Monitor error: {e}")
                time.sleep(5)

    def _check_reminders(self):
        """Check and fire pending reminders."""
        now = time.time()
        fired = []
        with self._lock:
            for i, reminder in enumerate(self.reminders):
                if reminder["time"] <= now:
                    fired.append(i)
                    self.conversation_queue.append({
                        "type": "reminder",
                        "message": reminder["message"],
                        "created_at": now,
                    })
            # Remove fired reminders (reverse order)
            for i in sorted(fired, reverse=True):
                self.reminders.pop(i)

    def _check_monitors(self):
        """Check all active monitors."""
        for monitor_id, monitor in list(self.monitors.items()):
            if not monitor.get("active", False):
                continue
            try:
                should_fire = monitor["check_fn"]()
                if should_fire:
                    self.conversation_queue.append({
                        "type": "monitor",
                        "monitor_id": monitor_id,
                        "message": monitor.get("message", "Monitor triggered"),
                        "created_at": time.time(),
                    })
            except Exception as e:
                print(f"[ProactiveEngine] Monitor {monitor_id} error: {e}")

    def add_reminder(self, message: str, delay_seconds: float) -> Dict:
        """Add a timed reminder."""
        with self._lock:
            reminder = {
                "message": message,
                "time": time.time() + delay_seconds,
                "created_at": time.time(),
            }
            self.reminders.append(reminder)
            return {"status": "scheduled", "fires_at": reminder["time"]}

    def add_monitor(self, monitor_id: str, check_fn: Callable, message: str) -> Dict:
        """Add a monitoring trigger."""
        with self._lock:
            self.monitors[monitor_id] = {
                "check_fn": check_fn,
                "message": message,
                "active": True,
                "created_at": time.time(),
            }
            return {"status": "monitoring", "monitor_id": monitor_id}

    def remove_monitor(self, monitor_id: str) -> Dict:
        """Remove a monitor."""
        with self._lock:
            if monitor_id in self.monitors:
                del self.monitors[monitor_id]
                return {"status": "removed"}
            return {"status": "not_found"}

    def get_pending_messages(self) -> List[Dict]:
        """Get all pending proactive messages."""
        with self._lock:
            messages = self.conversation_queue.copy()
            self.conversation_queue.clear()
            return messages

    def queue_message(self, message: str, msg_type: str = "proactive"):
        """Manually queue a proactive message."""
        with self._lock:
            self.conversation_queue.append({
                "type": msg_type,
                "message": message,
                "created_at": time.time(),
            })

    def get_status(self) -> Dict:
        """Get engine status."""
        return {
            "running": self._running,
            "monitors": len(self.monitors),
            "reminders": len(self.reminders),
            "pending_messages": len(self.conversation_queue),
        }

    # ── Common Monitor Presets ────────────────────────────────────────

    def monitor_email(self, interval_minutes: int = 5) -> Dict:
        """Set up email monitoring."""
        last_count = [0]

        def check():
            # This would check email count via the relay
            # Return True if new emails detected
            return False  # Placeholder

        return self.add_monitor(
            "email_monitor",
            check,
            "New emails detected in your inbox"
        )

    def monitor_calendar(self, minutes_before: int = 30) -> Dict:
        """Set up calendar event monitoring."""
        def check():
            return False  # Placeholder

        return self.add_monitor(
            "calendar_monitor",
            check,
            "Upcoming calendar event in 30 minutes"
        )

    def monitor_flights(self, hours_before: int = 24) -> Dict:
        """Set up flight status monitoring."""
        def check():
            return False  # Placeholder

        return self.add_monitor(
            "flight_monitor",
            check,
            "Your flight status has changed"
        )

    def schedule_morning_brief(self, hour: int = 7, minute: int = 0) -> Dict:
        """Schedule a daily morning briefing."""
        import datetime
        now = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        delay = (target - now).total_seconds()
        return self.add_reminder("Time for your morning briefing! I'll scan your email, calendar, and news.", delay)


# Singleton
_proactive = None

def get_proactive_engine() -> ProactiveEngine:
    global _proactive
    if _proactive is None:
        _proactive = ProactiveEngine()
    return _proactive
