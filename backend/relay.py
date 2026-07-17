"""Relay bridge — queues actions by user_id. Multi-tenant."""

import json
import threading
import time
import uuid

_lock = threading.Lock()
_pending: dict[str, dict] = {}
_results: dict[str, dict] = {}
_expiry = 120

# Heartbeat tracking
_last_heartbeat: dict[str, float] = {}
_HEARTBEAT_TIMEOUT = 60  # seconds before relay is considered dead

# Relay device registry (updated by main.py on register/heartbeat)
_relay_devices: dict[str, dict] = {}


def record_heartbeat(user_id: str = "local"):
    with _lock:
        _last_heartbeat[user_id] = time.time()


def update_relay_device(user_id: str, data: dict):
    """Update relay device info (called from main.py on register/heartbeat)."""
    with _lock:
        if user_id in _relay_devices:
            _relay_devices[user_id].update(data)
        else:
            _relay_devices[user_id] = data


def get_relay_device(user_id: str = "local") -> dict:
    """Get relay device info."""
    with _lock:
        return _relay_devices.get(user_id, {})


def is_relay_alive(user_id: str = "local") -> bool:
    with _lock:
        last = _last_heartbeat.get(user_id)
        if last is not None and (time.time() - last) < _HEARTBEAT_TIMEOUT:
            return True
        # Fallback: check relay device last_seen
        dev = _relay_devices.get(user_id, {})
        relay_ls = dev.get("last_seen", 0)
        if relay_ls > 0 and (time.time() - relay_ls) < 120:
            return True
    return False


def queue_action(action: str, params: str = "", user_id: str = "local") -> str:
    rid = str(uuid.uuid4())[:8]
    with _lock:
        _pending[rid] = {"relay_id": rid, "action": action, "params": params, "user_id": user_id, "queued_at": time.time()}
    return rid


def claim_next(user_id: str = "local") -> dict | None:
    with _lock:
        for rid in sorted(_pending, key=lambda r: _pending[r]["queued_at"]):
            if _pending[rid].get("user_id") == user_id:
                return _pending.pop(rid)
        return None


def submit_result(rid: str, result: str, success: bool = True):
    with _lock:
        _pending.pop(rid, None)
        _results[rid] = {"status": "done" if success else "failed", "result": result}


def get_result(rid: str) -> dict:
    with _lock:
        r = _results.get(rid)
        if r:
            return r
        if rid in _pending:
            return {"status": "pending"}
        return {"status": "not_found"}


# ── Context Push (Outlook/Calendar/Email from user's machine) ─────────────

def push_context_to_backend(backend_url: str, user_id: str = "local"):
    """Read local Outlook/Calendar and push to backend for hyper-personalization."""
    import os
    if os.name != "nt":
        return  # Only Windows for now

    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

        # Calendar
        calendar = outlook.GetDefaultFolder(9)
        items = calendar.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        from datetime import datetime, timedelta
        start = datetime.now().strftime("%Y-%m-%d %H:%M %p")
        end = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M %p")
        items = items.Restrict(f"[Start] >= '{start}' AND [End] <= '{end}'")
        events = []
        for item in items:
            events.append({
                "subject": item.Subject,
                "start": str(item.Start),
                "duration_min": item.Duration,
                "location": item.Location or "",
                "importance": item.Importance,
            })

        # Emails
        inbox = outlook.GetDefaultFolder(6)
        msgs = inbox.Items
        msgs.Sort("[ReceivedTime]", True)
        emails = []
        for i in range(1, min(11, msgs.Count + 1)):
            try:
                m = msgs[i]
                emails.append({
                    "sender": m.SenderName,
                    "subject": m.Subject,
                    "received_at": str(m.ReceivedTime),
                    "is_read": m.IsRead,
                })
            except:
                continue

        # Contacts
        contacts_folder = outlook.GetDefaultFolder(10)
        citems = contacts_folder.Items
        contacts = []
        for i in range(1, min(21, citems.Count + 1)):
            try:
                c = citems[i]
                contacts.append({
                    "name": getattr(c, "FullName", ""),
                    "email": getattr(c, "Email1Address", ""),
                    "company": getattr(c, "CompanyName", ""),
                })
            except:
                continue

        # Push to backend
        import urllib.request
        import json
        data = json.dumps({
            "calendar": events,
            "emails": emails,
            "contacts": contacts,
        }).encode()
        req = urllib.request.Request(
            f"{backend_url}/api/context/relay/inject",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"[Relay] Pushed context: {len(events)} events, {len(emails)} emails, {len(contacts)} contacts")
    except ImportError:
        print("[Relay] win32com not available — context push skipped")
    except Exception as e:
        print(f"[Relay] Context push error: {e}")
