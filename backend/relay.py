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
    """WebSocket handler for relay agent connection — sends actions, receives results."""
    q = await _client_queue()
    await websocket.accept()

    async def send_loop():
        while True:
            msg = await q.get()
            try:
                await websocket.send_text(msg)
            except:
                break

    async def recv_loop():
        while True:
            try:
                raw = await websocket.receive_text()
            except:
                break
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "pong":
                continue
            if data.get("type") == "result":
                submit_result(
                    data.get("relay_id", ""),
                    data.get("result", ""),
                    data.get("success", True),
                )

    try:
        await asyncio.gather(send_loop(), recv_loop())
    except:
        pass
    finally:
        await _remove_queue(q)
        try:
            await websocket.close()
        except:
            pass
