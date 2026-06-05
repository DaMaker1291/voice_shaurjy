"""Relay bridge — queues Windows actions for local agent. Dead simple."""

import json
import threading
import time
import uuid

_lock = threading.Lock()
_pending: dict[str, dict] = {}
_results: dict[str, dict] = {}
_expiry = 120


def queue_action(action: str, params: str = "") -> str:
    rid = str(uuid.uuid4())[:8]
    with _lock:
        _pending[rid] = {"relay_id": rid, "action": action, "params": params, "queued_at": time.time()}
    return rid


def claim_next() -> dict | None:
    with _lock:
        for rid in sorted(_pending, key=lambda r: _pending[r]["queued_at"]):
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
