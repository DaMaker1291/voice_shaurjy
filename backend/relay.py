"""Relay bridge — queues Windows actions for the local relay agent via WebSocket."""

import asyncio
import json
import threading
import time
import uuid
from typing import Optional

_lock = threading.Lock()
_pending: dict[str, dict] = {}
_results: dict[str, dict] = {}
_ws_clients: list[asyncio.Queue] = []
_expiry = 60


def queue_action(action: str, params: str = "") -> str:
    relay_id = str(uuid.uuid4())[:8]
    with _lock:
        _pending[relay_id] = {
            "relay_id": relay_id,
            "action": action,
            "params": params,
            "queued_at": time.time(),
        }
        msg = json.dumps({"type": "action", **dict(_pending[relay_id])})
        for q in list(_ws_clients):
            try:
                q.put_nowait(msg)
            except:
                pass
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


async def _client_queue() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    with _lock:
        _ws_clients.append(q)
    return q


async def _remove_queue(q: asyncio.Queue):
    with _lock:
        if q in _ws_clients:
            _ws_clients.remove(q)


async def ws_relay_handler(websocket):
    """WebSocket handler for relay agent connection."""
    import json as _json
    q = await _client_queue()
    try:
        await websocket.accept()
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=_expiry)
                await websocket.send_text(msg)
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')
                try:
                    pong = await asyncio.wait_for(websocket.receive_text(), timeout=5)
                    if pong == '{"type":"pong"}':
                        pass
                except:
                    break
    except:
        pass
    finally:
        await _remove_queue(q)
        try:
            await websocket.close()
        except:
            pass
