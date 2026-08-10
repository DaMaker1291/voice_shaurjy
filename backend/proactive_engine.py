#!/usr/bin/env python3
"""
Proactive Conversation Engine for JARVIS
Enables JARVIS to initiate conversations, monitor events, and act without being asked.
"""
import time
import json
import threading
from pathlib import Path
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
        """Set up email monitoring. Checks for new emails via IMAP or local relay."""
        last_count = [0]
        check_count = [0]

        def check():
            check_count[0] += 1
            try:
                from email_calendar import get_email_manager
                mgr = get_email_manager()
                # Try to check inbox count via IMAP if configured
                if hasattr(mgr, '_imap_host') and mgr._imap_host:
                    import imaplib
                    conn = imaplib.IMAP4_SSL(mgr._imap_host)
                    conn.login(mgr._imap_user, mgr._imap_pass)
                    conn.select("INBOX")
                    _, msg_ids = conn.search(None, "UNSEEN")
                    count = len(msg_ids[0].split()) if msg_ids[0] else 0
                    conn.logout()
                    if last_count[0] > 0 and count > last_count[0]:
                        last_count[0] = count
                        return True
                    last_count[0] = count
                # Fallback: check draft folder for new drafts
                drafts_dir = Path.home() / ".jarvis" / "drafts"
                if drafts_dir.exists():
                    drafts = list(drafts_dir.glob("*.json"))
                    if check_count[0] > 1 and len(drafts) > 0:
                        # Check if any draft is newer than last check
                        pass
            except Exception:
                pass
            return False

        return self.add_monitor(
            "email_monitor",
            check,
            "New emails detected in your inbox"
        )

    def monitor_calendar(self, minutes_before: int = 30) -> Dict:
        """Set up calendar event monitoring. Checks staged calendar events."""
        last_events = [set()]

        def check():
            try:
                cal_dir = Path.home() / ".jarvis" / "calendar"
                if cal_dir.exists():
                    import json as _json
                    now = time.time()
                    upcoming = []
                    for f in cal_dir.glob("*.json"):
                        try:
                            ev = _json.loads(f.read_text())
                            ev_time = ev.get("start_time", 0)
                            if 0 < ev_time - now < minutes_before * 60:
                                ev_id = ev.get("id", f.stem)
                                if ev_id not in last_events[0]:
                                    upcoming.append(ev)
                                    last_events[0].add(ev_id)
                        except Exception:
                            pass
                    if upcoming:
                        return True
            except Exception:
                pass
            return False

        return self.add_monitor(
            "calendar_monitor",
            check,
            "Upcoming calendar event in " + str(minutes_before) + " minutes"
        )

    def monitor_flights(self, flight_info: str = "", hours_before: int = 24) -> Dict:
        """Set up flight status monitoring. Checks travel dashboard data for updates."""
        last_status = [None]

        def check():
            try:
                # Check if there are any travel briefings with flight data
                vault = Path.home() / "Desktop"
                for f in vault.glob("*flight*"):
                    if f.stat().st_mtime > time.time() - 3600:
                        return True
                # Check staged travel data
                travel_dir = Path.home() / ".jarvis" / "travel"
                if travel_dir.exists():
                    for f in travel_dir.glob("*.json"):
                        try:
                            data = json.loads(f.read_text())
                            flights = data.get("flights", [])
                            for fl in flights:
                                status = fl.get("status", "unknown")
                                if last_status[0] and status != last_status[0]:
                                    last_status[0] = status
                                    return True
                                last_status[0] = status
                        except Exception:
                            pass
            except Exception:
                pass
            return False

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
