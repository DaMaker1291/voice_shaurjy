"""
Deep Context Ingestion Engine — Cross-platform Outlook, Calendar, Email, Contacts.

Runs background scans of native communication channels on the host machine.
On Windows: uses win32com (Outlook MAPI)
On macOS: uses AppleScript (Calendar.app, Mail.app)
On Linux: uses CalDAV/IMAP or local ICS files
On HF Space: returns empty (relay pushes context instead)

All data stays LOCAL — never sent to cloud.
"""

import os
import json
import time
import threading
import subprocess
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

_platform = os.name  # 'nt' (Windows) or 'posix' (macOS/Linux)

# ── Singleton ──────────────────────────────────────────────────────
_instance: Optional["ContextRelay"] = None
_lock = threading.Lock()


def get_context_relay() -> "ContextRelay":
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ContextRelay()
    return _instance


class ContextRelay:
    """Cross-platform deep context ingestion engine."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_sync: Dict[str, float] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._initialized = False
        self._platform = self._detect_platform()
        self._calendar_source = None
        self._email_source = None
        self._contacts_source = None
        self._init_platform()

    def _detect_platform(self) -> str:
        system = subprocess.run(["uname", "-s"], capture_output=True, text=True).stdout.strip() if _platform == "posix" else ""
        if _platform == "nt":
            return "windows"
        elif "darwin" in system.lower():
            return "macos"
        else:
            return "linux"

    def _init_platform(self):
        """Initialize platform-specific hooks."""
        try:
            if self._platform == "windows":
                self._init_windows()
            elif self._platform == "macos":
                self._init_macos()
            else:
                self._init_linux()
            self._initialized = True
        except Exception as e:
            print(f"[CONTEXT RELAY] Platform init failed: {e}")
            self._initialized = False

    def _init_windows(self):
        """Windows: detect Outlook COM without launching it."""
        try:
            import win32com.client
            self._calendar_source = "outlook_com"
            self._email_source = "outlook_com"
            self._contacts_source = "outlook_com"
        except ImportError:
            print("[CONTEXT RELAY] win32com not available — Windows context disabled")
            self._calendar_source = None
            self._email_source = None

    def _init_macos(self):
        """macOS: Use AppleScript for Calendar and Mail."""
        self._calendar_source = "applescript_calendar"
        self._email_source = "applescript_mail"
        # Verify AppleScript works
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "Calendar" to return name'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                print("[CONTEXT RELAY] Calendar.app not available")
                self._calendar_source = None
        except Exception:
            self._calendar_source = None
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "Mail" to return name'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                print("[CONTEXT RELAY] Mail.app not available")
                self._email_source = None
        except Exception:
            self._email_source = None

    def _init_linux(self):
        """Linux: Look for ICS files, CalDAV configs, or IMAP settings."""
        # Check for common calendar files
        home = Path.home()
        ics_locations = [
            home / ".local/share/evolution/calendar",
            home / ".config/evolution/calendar",
            home / ".kde/share/apps/korganizer",
            home / ".thunderbird",
        ]
        for loc in ics_locations:
            if loc.exists():
                self._calendar_source = "local_ics"
                break
        # Check for mail configs
        mail_locations = [
            home / ".thunderbird",
            home / ".config/thunderbird",
            home / ".claws-mail",
        ]
        for loc in mail_locations:
            if loc.exists():
                self._email_source = "local_mail"
                break

    # ── Calendar Ingestion ──────────────────────────────────────────

    def ingest_calendar(self, lookahead_days: int = 2) -> List[Dict[str, Any]]:
        """Get upcoming calendar events."""
        cache_key = f"calendar_{lookahead_days}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        events = []
        try:
            if self._platform == "windows" and self._calendar_source == "outlook_com":
                events = self._ingest_windows_calendar(lookahead_days)
            elif self._platform == "macos" and self._calendar_source == "applescript_calendar":
                events = self._ingest_macos_calendar(lookahead_days)
            elif self._calendar_source == "local_ics":
                events = self._ingest_local_calendar(lookahead_days)
        except Exception as e:
            print(f"[CONTEXT RELAY] Calendar ingestion error: {e}")

        self._set_cache(cache_key, events)
        return events

    def _get_running_outlook(self):
        """Get a running Outlook instance without launching it."""
        try:
            import win32com.client
            outlook = win32com.client.GetActiveObject("Outlook.Application")
            return outlook.GetNamespace("MAPI")
        except Exception:
            return None

    def _ingest_windows_calendar(self, days: int) -> List[Dict[str, Any]]:
        """Windows Outlook calendar via COM (only if Outlook is running)."""
        ns = self._get_running_outlook()
        if ns is None:
            return []
        calendar = ns.GetDefaultFolder(9)
        items = calendar.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        start = datetime.now().strftime("%Y-%m-%d %H:%M %p")
        end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M %p")
        items = items.Restrict(f"[Start] >= '{start}' AND [End] <= '{end}'")
        events = []
        for item in items:
            events.append({
                "subject": item.Subject,
                "start": str(item.Start),
                "end": str(item.End),
                "duration_min": item.Duration,
                "location": item.Location or "",
                "importance": item.Importance,
                "is_recurring": bool(item.IsRecurring),
                "organizer": getattr(item, "Organizer", ""),
                "attendees": [a.Name for a in item.Recipients] if hasattr(item, "Recipients") else [],
                "source": "outlook",
            })
        return events

    def _ingest_macos_calendar(self, days: int) -> List[Dict[str, Any]]:
        """macOS Calendar via AppleScript."""
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        script = f'''
        tell application "Calendar"
            set output to ""
            repeat with cal in calendars
                set evts to (current events of cal whose start date >= date "{start_date}" and start date <= date "{end_date}")
                repeat with evt in evts
                    set output to output & summary of evt & "|" & start date of evt & "|" & duration of evt & "|" & location of evt & "\\n"
                end repeat
            end repeat
            return output
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        events = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|", 3)
            events.append({
                "subject": parts[0].strip() if len(parts) > 0 else "",
                "start": parts[1].strip() if len(parts) > 1 else "",
                "duration_min": int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 30,
                "location": parts[3].strip() if len(parts) > 3 else "",
                "source": "apple_calendar",
            })
        return events

    def _ingest_local_calendar(self, days: int) -> List[Dict[str, Any]]:
        """Parse local ICS files."""
        events = []
        ics_dir = Path.home() / ".local/share/evolution/calendar"
        if not ics_dir.exists():
            return events
        for ics_file in ics_dir.rglob("*.ics"):
            try:
                content = ics_file.read_text(errors="ignore")
                for block in content.split("BEGIN:VEVENT"):
                    if "END:VEVENT" not in block:
                        continue
                    summary = ""
                    dtstart = ""
                    dtend = ""
                    location = ""
                    for line in block.split("\n"):
                        if line.startswith("SUMMARY:"):
                            summary = line[8:].strip()
                        elif line.startswith("DTSTART"):
                            dtstart = line.split(":", 1)[-1].strip() if ":" in line else ""
                        elif line.startswith("DTEND"):
                            dtend = line.split(":", 1)[-1].strip() if ":" in line else ""
                        elif line.startswith("LOCATION:"):
                            location = line[9:].strip()
                    if summary:
                        events.append({
                            "subject": summary,
                            "start": dtstart,
                            "end": dtend,
                            "duration_min": 30,
                            "location": location,
                            "source": "local_ics",
                        })
            except Exception:
                continue
        return events[:20]  # Limit

    # ── Email Ingestion ─────────────────────────────────────────────

    def ingest_emails(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent emails."""
        cache_key = f"emails_{limit}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        emails = []
        try:
            if self._platform == "windows" and self._email_source == "outlook_com":
                emails = self._ingest_windows_emails(limit)
            elif self._platform == "macos" and self._email_source == "applescript_mail":
                emails = self._ingest_macos_emails(limit)
        except Exception as e:
            print(f"[CONTEXT RELAY] Email ingestion error: {e}")

        self._set_cache(cache_key, emails)
        return emails

    def _ingest_windows_emails(self, limit: int) -> List[Dict[str, Any]]:
        """Windows Outlook inbox via COM (only if Outlook is running)."""
        ns = self._get_running_outlook()
        if ns is None:
            return []
        inbox = ns.GetDefaultFolder(6)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        emails = []
        for i in range(1, min(limit + 1, items.Count + 1)):
            try:
                msg = items[i]
                emails.append({
                    "sender": msg.SenderName,
                    "sender_email": msg.SenderEmailAddress,
                    "subject": msg.Subject,
                    "received_at": str(msg.ReceivedTime),
                    "snippet": msg.Body[:200].strip() if msg.Body else "",
                    "is_read": msg.IsRead,
                    "importance": msg.Importance,
                    "has_attachments": bool(msg.Attachments.Count) if hasattr(msg, "Attachments") else False,
                    "source": "outlook",
                })
            except Exception:
                continue
        return emails

    def _ingest_macos_emails(self, limit: int) -> List[Dict[str, Any]]:
        """macOS Mail via AppleScript."""
        script = f'''
        tell application "Mail"
            set output to ""
            set msgs to messages of inbox 1
            repeat with i from 1 to {min(limit, 20)}
                try
                    set m to item i of msgs
                    set output to output & sender of m & "|" & subject of m & "|" & date received of m & "|" & (do shell script "echo " & (content of m) & " | head -c 200") & "\\n"
                end try
            end repeat
            return output
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        emails = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|", 3)
            emails.append({
                "sender": parts[0].strip() if len(parts) > 0 else "",
                "subject": parts[1].strip() if len(parts) > 1 else "",
                "received_at": parts[2].strip() if len(parts) > 2 else "",
                "snippet": parts[3].strip() if len(parts) > 3 else "",
                "source": "apple_mail",
            })
        return emails

    # ── Contacts / People Ingestion ─────────────────────────────────

    def ingest_contacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent/frequent contacts."""
        cache_key = f"contacts_{limit}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        contacts = []
        try:
            if self._platform == "windows" and self._calendar_source == "outlook_com":
                contacts = self._ingest_windows_contacts(limit)
            elif self._platform == "macos":
                contacts = self._ingest_macos_contacts(limit)
        except Exception as e:
            print(f"[CONTEXT RELAY] Contacts ingestion error: {e}")

        self._set_cache(cache_key, contacts)
        return contacts

    def _ingest_windows_contacts(self, limit: int) -> List[Dict[str, Any]]:
        """Windows Outlook contacts via COM (only if Outlook is running)."""
        ns = self._get_running_outlook()
        if ns is None:
            return []
        contacts_folder = ns.GetDefaultFolder(10)  # olFolderContacts
        items = contacts_folder.Items
        contacts = []
        for i in range(1, min(limit + 1, items.Count + 1)):
            try:
                item = items[i]
                contacts.append({
                    "name": getattr(item, "FullName", ""),
                    "email": getattr(item, "Email1Address", ""),
                    "company": getattr(item, "CompanyName", ""),
                    "phone": getattr(item, "BusinessTelephoneNumber", ""),
                    "source": "outlook",
                })
            except Exception:
                continue
        return contacts

    def _ingest_macos_contacts(self, limit: int) -> List[Dict[str, Any]]:
        """macOS Contacts via AppleScript."""
        script = f'''
        tell application "Contacts"
            set output to ""
            set ppl to people
            repeat with i from 1 to {min(limit, 20)}
                try
                    set p to item i of ppl
                    set output to output & name of p & "|" & (value of first email of p) & "|" & (value of first phone of p) & "\\n"
                end try
            end repeat
            return output
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        contacts = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|", 2)
            contacts.append({
                "name": parts[0].strip() if len(parts) > 0 else "",
                "email": parts[1].strip() if len(parts) > 1 else "",
                "phone": parts[2].strip() if len(parts) > 2 else "",
                "source": "apple_contacts",
            })
        return contacts

    # ── Full Context Snapshot ───────────────────────────────────────

    def get_full_context(self, user_id: str = "local") -> Dict[str, Any]:
        """Build complete context snapshot for hyper-personalized responses."""
        now = datetime.now()
        calendar_events = self.ingest_calendar(lookahead_days=2)
        recent_emails = self.ingest_emails(limit=10)
        contacts = self.ingest_contacts(limit=20)

        # Build relationship graph nodes from contacts + emails
        graph_nodes = []
        for c in contacts:
            graph_nodes.append({
                "id": hashlib.md5(c.get("email", c.get("name", "")).encode()).hexdigest()[:8],
                "type": "person",
                "name": c.get("name", ""),
                "email": c.get("email", ""),
                "company": c.get("company", ""),
            })
        for e in recent_emails:
            sender = e.get("sender", "")
            if sender and not any(n.get("name") == sender for n in graph_nodes):
                graph_nodes.append({
                    "id": hashlib.md5(sender.encode()).hexdigest()[:8],
                    "type": "person",
                    "name": sender,
                    "email": e.get("sender_email", ""),
                })

        # Detect patterns
        patterns = self._detect_patterns(calendar_events, recent_emails)

        # Compute urgency signals
        urgency = self._compute_urgency(calendar_events, recent_emails)

        return {
            "timestamp": now.isoformat(),
            "platform": self._platform,
            "initialized": self._initialized,
            "calendar": {
                "events": calendar_events,
                "count": len(calendar_events),
                "next_event": calendar_events[0] if calendar_events else None,
            },
            "emails": {
                "recent": recent_emails,
                "count": len(recent_emails),
                "unread_count": sum(1 for e in recent_emails if not e.get("is_read", True)),
            },
            "contacts": {
                "people": contacts,
                "count": len(contacts),
            },
            "graph_nodes": graph_nodes,
            "patterns": patterns,
            "urgency": urgency,
            "summary": self._build_summary(calendar_events, recent_emails, contacts, patterns, urgency),
        }

    def _detect_patterns(self, events: List[Dict], emails: List[Dict]) -> Dict[str, Any]:
        """Detect behavioral patterns from calendar and email data."""
        patterns = {
            "meeting_heavy_day": False,
            "frequent_communicators": [],
            "upcoming_deadlines": [],
            "work_hours_active": False,
        }

        # Count meetings per day
        if events:
            today_events = [e for e in events if datetime.now().strftime("%Y-%m-%d") in str(e.get("start", ""))]
            patterns["meeting_heavy_day"] = len(today_events) >= 5

            # Find upcoming deadlines (events with "deadline" or "due" in subject)
            for e in events:
                subj = e.get("subject", "").lower()
                if any(kw in subj for kw in ["deadline", "due", "review", "submission", "presentation"]):
                    patterns["upcoming_deadlines"].append({
                        "subject": e["subject"],
                        "start": e.get("start", ""),
                    })

        # Frequent communicators
        if emails:
            sender_counts = {}
            for e in emails:
                sender = e.get("sender", "")
                if sender:
                    sender_counts[sender] = sender_counts.get(sender, 0) + 1
            patterns["frequent_communicators"] = sorted(
                [{"name": k, "count": v} for k, v in sender_counts.items()],
                key=lambda x: -x["count"]
            )[:5]

        # Work hours detection
        hour = datetime.now().hour
        patterns["work_hours_active"] = 9 <= hour <= 17

        return patterns

    def _compute_urgency(self, events: List[Dict], emails: List[Dict]) -> Dict[str, Any]:
        """Compute urgency signals."""
        now = datetime.now()
        urgency = {
            "level": "low",
            "signals": [],
        }

        # Check for imminent meetings (within 30 min)
        for e in events:
            try:
                start_str = str(e.get("start", ""))
                if start_str:
                    # Try parsing common formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %I:%M %p"]:
                        try:
                            start_dt = datetime.strptime(start_str, fmt)
                            mins_until = (start_dt - now).total_seconds() / 60
                            if 0 < mins_until <= 30:
                                urgency["level"] = "high"
                                urgency["signals"].append(f"Meeting '{e['subject']}' in {int(mins_until)} min")
                            elif 30 < mins_until <= 60:
                                urgency["level"] = max(urgency["level"], "medium")
                                urgency["signals"].append(f"Meeting '{e['subject']}' in {int(mins_until)} min")
                            break
                        except ValueError:
                            continue
            except Exception:
                continue

        # Check for unread emails from important people
        unread = [e for e in emails if not e.get("is_read", True)]
        if len(unread) >= 5:
            urgency["level"] = max(urgency["level"], "medium")
            urgency["signals"].append(f"{len(unread)} unread emails")

        return urgency

    def _build_summary(self, events, emails, contacts, patterns, urgency) -> str:
        """Build a human-readable context summary."""
        parts = []
        if events:
            parts.append(f"{len(events)} upcoming events")
            if patterns.get("meeting_heavy_day"):
                parts.append("HEAVY meeting day")
        if emails:
            unread = sum(1 for e in emails if not e.get("is_read", True))
            if unread:
                parts.append(f"{unread} unread emails")
        if contacts:
            parts.append(f"{len(contacts)} contacts loaded")
        if patterns.get("upcoming_deadlines"):
            parts.append(f"{len(patterns['upcoming_deadlines'])} deadlines approaching")
        if urgency["level"] != "low":
            parts.append(f"Urgency: {urgency['level'].upper()}")
        return " | ".join(parts) if parts else "No context data available"

    # ── Cache Helpers ───────────────────────────────────────────────

    def _get_cache(self, key: str) -> Optional[Any]:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = (time.time(), data)

    # ── Background Sync ─────────────────────────────────────────────

    def start_background_sync(self, interval: int = 300):
        """Start background context ingestion thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, args=(interval,), daemon=True)
        self._thread.start()
        print(f"[CONTEXT RELAY] Background sync started (every {interval}s)")

    def stop_background_sync(self):
        self._running = False

    def _sync_loop(self, interval: int):
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        while self._running:
            try:
                self.get_full_context()
            except Exception as e:
                print(f"[CONTEXT RELAY] Sync error: {e}")
            time.sleep(interval)
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except ImportError:
            pass

    # ── Inject Context for Relay ────────────────────────────────────

    def inject_relay_context(self, context_data: Dict[str, Any]):
        """Receive context pushed from relay agent on user's machine."""
        # Merge relay-provided context (Outlook/Calendar from user's real machine)
        if "calendar" in context_data:
            self._cache["calendar_2"] = (time.time(), context_data["calendar"])
        if "emails" in context_data:
            self._cache["emails_10"] = (time.time(), context_data["emails"])
        if "contacts" in context_data:
            self._cache["contacts_20"] = (time.time(), context_data["contacts"])

    def get_state(self) -> Dict[str, Any]:
        """Return current relay state for frontend."""
        return {
            "initialized": self._initialized,
            "platform": self._platform,
            "calendar_source": self._calendar_source,
            "email_source": self._email_source,
            "contacts_source": self._contacts_source,
            "background_sync": self._running,
            "cache_keys": list(self._cache.keys()),
            "last_sync": {k: datetime.fromtimestamp(ts).isoformat() for k, (ts, _) in self._cache.items()},
        }
