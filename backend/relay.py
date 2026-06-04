"""Relay bridge — queues Windows actions for the local relay agent to execute."""

import threading
import time
import uuid
from typing import Optional

_lock = threading.Lock()
_pending: dict[str, dict] = {}      # relay_id → action info
_results: dict[str, dict] = {}       # relay_id → result
_expiry = 60  # seconds


def queue_action(action: str, params: str = "") -> str:
    relay_id = str(uuid.uuid4())[:8]
    with _lock:
        _pending[relay_id] = {
            "relay_id": relay_id,
            "action": action,
            "params": params,
            "queued_at": time.time(),
        }
    return relay_id


def get_pending() -> list[dict]:
    now = time.time()
    with _lock:
        expired = [rid for rid, a in _pending.items() if now - a["queued_at"] > _expiry]
        for rid in expired:
            _pending.pop(rid, None)
            _results[rid] = {"status": "timeout", "result": "Relay agent did not respond in time"}
        return [dict(a) for a in _pending.values()]


def claim_action(relay_id: str) -> Optional[dict]:
    with _lock:
        return _pending.pop(relay_id, None)


def claim_next_pending() -> Optional[dict]:
    """Claim and remove the oldest pending action (FIFO)."""
    with _lock:
        for rid in sorted(_pending, key=lambda r: _pending[r]["queued_at"]):
            return _pending.pop(rid)
        return None


def submit_result(relay_id: str, result: str, success: bool = True):
    with _lock:
        _results[relay_id] = {"status": "done" if success else "failed", "result": result, "completed_at": time.time()}


def get_result(relay_id: str) -> dict:
    with _lock:
        r = _results.get(relay_id)
        if r:
            return r
        if relay_id in _pending:
            return {"status": "pending"}
        return {"status": "not_found"}
