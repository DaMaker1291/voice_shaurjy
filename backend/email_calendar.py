"""
Email & Calendar Staging — Draft storage, SMTP send, calendar API.

Email:
- Draft emails locally (stored in ~/.jarvis/drafts/)
- Send via SMTP (configurable in .env)
- Laser Gate approval required before sending
- Support attachments

Calendar:
- Create calendar events locally
- Open in Outlook/Google Calendar via URL
- Stage for Laser Gate approval
"""

import json
import os
import time
import logging
import smtplib
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

log = logging.getLogger("jarvis-email-calendar")

_DRAFTS_DIR = Path.home() / ".jarvis" / "drafts"
_CALENDAR_DIR = Path.home() / ".jarvis" / "calendar"


@dataclass
class EmailDraft:
    id: str
    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    attachments: List[str] = field(default_factory=list)
    status: str = "draft"  # draft, approved, sent, failed
    created_at: float = field(default_factory=time.time)
    sent_at: float = 0.0
    error: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class CalendarEvent:
    id: str
    title: str
    date: str  # ISO format
    time: str = ""
    duration_minutes: int = 60
    description: str = ""
    location: str = ""
    attendees: List[str] = field(default_factory=list)
    status: str = "draft"  # draft, approved, created
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)


class EmailManager:
    """Draft and send emails with Laser Gate approval."""

    def __init__(self):
        _DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    def _gen_id(self, to: str, subject: str) -> str:
        safe = hashlib.md5(f"{to}{subject}{time.time()}".encode()).hexdigest()[:10]
        return f"email_{safe}"

    def draft(self, to: str, subject: str, body: str,
              cc: str = "", attachments: list = None) -> EmailDraft:
        """Create an email draft (does NOT send)."""
        draft_id = self._gen_id(to, subject)
        draft = EmailDraft(
            id=draft_id, to=to, subject=subject, body=body,
            cc=cc, attachments=attachments or [],
        )
        path = _DRAFTS_DIR / f"{draft_id}.json"
        path.write_text(json.dumps(draft.to_dict(), indent=2), encoding="utf-8")
        log.info(f"[EMAIL] Draft created: {draft_id} -> {to}")
        return draft

    def get_draft(self, draft_id: str) -> Optional[EmailDraft]:
        path = _DRAFTS_DIR / f"{draft_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return EmailDraft(**data)
        return None

    def list_drafts(self) -> List[EmailDraft]:
        drafts = []
        for f in sorted(_DRAFTS_DIR.glob("email_*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                drafts.append(EmailDraft(**data))
            except Exception:
                pass
        return drafts

    def approve_draft(self, draft_id: str) -> bool:
        draft = self.get_draft(draft_id)
        if draft:
            draft.status = "approved"
            path = _DRAFTS_DIR / f"{draft_id}.json"
            path.write_text(json.dumps(draft.to_dict(), indent=2), encoding="utf-8")
            return True
        return False

    def send(self, draft_id: str) -> bool:
        """Send an approved email via SMTP. Requires .env config."""
        draft = self.get_draft(draft_id)
        if not draft:
            return False
        if draft.status not in ("approved", "draft"):
            return False

        smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")

        if not smtp_user or not smtp_pass:
            draft.status = "failed"
            draft.error = "SMTP not configured in .env"
            self._save_draft(draft)
            log.warning("[EMAIL] SMTP not configured")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = draft.to
            if draft.cc:
                msg["Cc"] = draft.cc
            msg["Subject"] = draft.subject
            msg.attach(MIMEText(draft.body, "plain"))

            for filepath in draft.attachments:
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
                    msg.attach(part)

            recipients = [draft.to]
            if draft.cc:
                recipients.extend(draft.cc.split(","))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, recipients, msg.as_string())

            draft.status = "sent"
            draft.sent_at = time.time()
            self._save_draft(draft)
            log.info(f"[EMAIL] Sent: {draft_id} -> {draft.to}")
            return True

        except Exception as e:
            draft.status = "failed"
            draft.error = str(e)
            self._save_draft(draft)
            log.error(f"[EMAIL] Send failed: {e}")
            return False

    def _save_draft(self, draft: EmailDraft):
        path = _DRAFTS_DIR / f"{draft.id}.json"
        path.write_text(json.dumps(draft.to_dict(), indent=2), encoding="utf-8")


class CalendarManager:
    """Stage and create calendar events."""

    def __init__(self):
        _CALENDAR_DIR.mkdir(parents=True, exist_ok=True)

    def _gen_id(self, title: str, date: str) -> str:
        safe = hashlib.md5(f"{title}{date}{time.time()}".encode()).hexdigest()[:10]
        return f"cal_{safe}"

    def stage(self, title: str, date: str, time_str: str = "",
              duration: int = 60, description: str = "",
              location: str = "", attendees: list = None) -> CalendarEvent:
        """Stage a calendar event (does NOT create it yet)."""
        event_id = self._gen_id(title, date)
        event = CalendarEvent(
            id=event_id, title=title, date=date, time=time_str,
            duration_minutes=duration, description=description,
            location=location, attendees=attendees or [],
        )
        path = _CALENDAR_DIR / f"{event_id}.json"
        path.write_text(json.dumps(event.to_dict(), indent=2), encoding="utf-8")
        log.info(f"[CAL] Event staged: {event_id} - {title}")
        return event

    def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        path = _CALENDAR_DIR / f"{event_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return CalendarEvent(**data)
        return None

    def list_events(self) -> List[CalendarEvent]:
        events = []
        for f in sorted(_CALENDAR_DIR.glob("cal_*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                events.append(CalendarEvent(**data))
            except Exception:
                pass
        return events

    def approve(self, event_id: str) -> bool:
        event = self.get_event(event_id)
        if event:
            event.status = "approved"
            path = _CALENDAR_DIR / f"{event_id}.json"
            path.write_text(json.dumps(event.to_dict(), indent=2), encoding="utf-8")
            return True
        return False

    def create_outlook_url(self, event: CalendarEvent) -> str:
        """Generate an Outlook calendar URL to add the event."""
        import urllib.parse
        start = event.date.replace("-", "")
        if event.time:
            start += "T" + event.time.replace(":", "") + "00"
        else:
            start += "T090000"
        end_dt = datetime.fromisoformat(f"{event.date}T{event.time or '09:00'}") + timedelta(minutes=event.duration_minutes)
        end = end_dt.strftime("%Y%m%dT%H%M%S")

        params = {
            "path": "/calendar/action/compose",
            "rru": "addevent",
            "subject": event.title,
            "startdt": start,
            "enddt": end,
            "body": event.description,
            "location": event.location,
        }
        return "https://outlook.live.com/calendar/0/deeplink/compose?" + urllib.parse.urlencode(params)

    def create_gcal_url(self, event: CalendarEvent) -> str:
        """Generate a Google Calendar URL to add the event."""
        import urllib.parse
        start = f"{event.date}T{event.time or '09:00'}:00"
        end_dt = datetime.fromisoformat(f"{event.date}T{event.time or '09:00'}") + timedelta(minutes=event.duration_minutes)
        end = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

        params = {
            "action": "TEMPLATE",
            "text": event.title,
            "dates": f"{start}/{end}",
            "details": event.description,
            "location": event.location,
        }
        return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

    def open_in_browser(self, event: CalendarEvent, provider: str = "outlook"):
        """Open the calendar event in the user's browser."""
        import webbrowser
        if provider == "google":
            url = self.create_gcal_url(event)
        else:
            url = self.create_outlook_url(event)
        webbrowser.open(url)
        event.status = "created"
        path = _CALENDAR_DIR / f"{event.id}.json"
        path.write_text(json.dumps(event.to_dict(), indent=2), encoding="utf-8")


_email_mgr: Optional[EmailManager] = None
_cal_mgr: Optional[CalendarManager] = None


def get_email_manager() -> EmailManager:
    global _email_mgr
    if _email_mgr is None:
        _email_mgr = EmailManager()
    return _email_mgr


def get_calendar_manager() -> CalendarManager:
    global _cal_mgr
    if _cal_mgr is None:
        _cal_mgr = CalendarManager()
    return _cal_mgr
