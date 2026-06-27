"""Relay bridge — queues Windows actions by user_id. Multi-tenant."""

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


def record_heartbeat(user_id: str = "local"):
    with _lock:
        _last_heartbeat[user_id] = time.time()


def is_relay_alive(user_id: str = "local") -> bool:
    with _lock:
        last = _last_heartbeat.get(user_id)
        if last is None:
            return False
        return (time.time() - last) < _HEARTBEAT_TIMEOUT


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
