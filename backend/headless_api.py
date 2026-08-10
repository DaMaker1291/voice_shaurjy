#!/usr/bin/env python3
"""
JARVIS Headless Workstation — FastAPI Routes

Provides HTTP endpoints for managing headless sessions.
On HF Space, headless commands are routed through the relay to the user's machine.
On the relay itself, commands execute locally via headless_worker.py.
"""

import asyncio
import base64
import json
import time
from typing import Optional, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/api/headless", tags=["headless"])


def _get_worker():
    """Return the process-wide headless worker singleton (sessions persist)."""
    from headless_worker import get_headless_worker
    return get_headless_worker()


class StartSessionReq(BaseModel):
    session_id: str = "default"
    width: int = 1920
    height: int = 1080
    depth: int = 24

class LaunchAppReq(BaseModel):
    session_id: str = "default"
    app_name: str
    command: List[str]

class ClickReq(BaseModel):
    session_id: str = "default"
    x: int = 0
    y: int = 0
    button: int = 1

class KeyReq(BaseModel):
    session_id: str = "default"
    key: str = "Return"

class TypeReq(BaseModel):
    session_id: str = "default"
    text: str = ""


def _relay_available() -> bool:
    """Check if relay is connected."""
    try:
        from relay import is_relay_alive
        return is_relay_alive()
    except:
        return False


def _queue_headless_action(action: str, params: dict) -> dict:
    """Queue a headless action through the relay."""
    try:
        from relay import queue_action, get_result
        rid = queue_action(f"headless_{action}", json.dumps(params))
        # Poll for result
        for _ in range(60):  # 30 seconds max
            time.sleep(0.5)
            result = get_result(rid)
            if result.get("status") in ("done", "failed"):
                try:
                    return json.loads(result["result"])
                except:
                    return {"ok": result["status"] == "done", "result": result["result"]}
        return {"ok": False, "error": "Relay timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/status")
async def headless_status(session_id: Optional[str] = None):
    if _relay_available():
        params = {"session_id": session_id} if session_id else {}
        return _queue_headless_action("status", params)
    worker = _get_worker()
    return worker.get_status(session_id)


@router.post("/start")
async def headless_start(req: StartSessionReq):
    if _relay_available():
        return _queue_headless_action("start", {"session_id": req.session_id, "width": req.width, "height": req.height, "depth": req.depth})
    worker = _get_worker()
    return worker.start_session(req.session_id, req.width, req.height, req.depth)


@router.post("/stop")
async def headless_stop(session_id: str = "default"):
    if _relay_available():
        return _queue_headless_action("stop", {"session_id": session_id})
    worker = _get_worker()
    return worker.stop_session(session_id)


@router.post("/launch")
async def headless_launch(req: LaunchAppReq):
    if _relay_available():
        return _queue_headless_action("launch", {"session_id": req.session_id, "app_name": req.app_name, "command": req.command})
    worker = _get_worker()
    return worker.launch_app(req.session_id, req.app_name, req.command)


@router.post("/click")
async def headless_click(req: ClickReq):
    if _relay_available():
        return _queue_headless_action("click", {"session_id": req.session_id, "x": req.x, "y": req.y, "button": req.button})
    worker = _get_worker()
    return worker.inject_click(req.session_id, req.x, req.y, req.button)


@router.post("/key")
async def headless_key(req: KeyReq):
    if _relay_available():
        return _queue_headless_action("key", {"session_id": req.session_id, "key": req.key})
    worker = _get_worker()
    return worker.inject_key(req.session_id, req.key)


@router.post("/type")
async def headless_type(req: TypeReq):
    if _relay_available():
        return _queue_headless_action("type", {"session_id": req.session_id, "text": req.text})
    worker = _get_worker()
    return worker.inject_text(req.session_id, req.text)


@router.get("/screenshot")
async def headless_screenshot(session_id: str = "default"):
    if _relay_available():
        result = _queue_headless_action("screenshot", {"session_id": session_id})
        return result
    worker = _get_worker()
    data = worker.capture_jpeg(session_id)
    if data:
        return {"ok": True, "image": base64.b64encode(data).decode(), "format": "jpeg"}
    return {"ok": False, "error": "No frame available"}


@router.get("/windows")
async def headless_windows(session_id: str = "default"):
    if _relay_available():
        return _queue_headless_action("windows", {"session_id": session_id})
    worker = _get_worker()
    return worker.get_window_tree(session_id)


@router.get("/sessions")
async def headless_sessions():
    if _relay_available():
        return _queue_headless_action("status", {})
    worker = _get_worker()
    return {"ok": True, "sessions": worker.list_sessions()}


@router.websocket("/ws/stream")
async def headless_ws_stream(websocket: WebSocket):
    """
    WebSocket endpoint for live low-latency frame streaming from the isolated
    backstage virtual desktop (JPEG). Interactive commands (click/type/key/launch)
    are executed against the isolated desktop so the user's screen is never touched.

    Query params:
      session_id (default "default"), fps (default 30), quality (default 60),
      width (default 960), height (default 540)

    Client -> server (JSON): {"cmd": "click|key|type|launch|set_session|quit", ...}
    Server -> client: {"type": "frame", "data": "<base64 jpeg>", "format": "jpeg", ...}
                      {"type": "status", "state": "waiting|running|error", ...}
    """
    await websocket.accept()
    params = websocket.query_params
    session_id = params.get("session_id", "default")
    fps_target = max(1, min(int(params.get("fps", "30")), 60))
    quality = max(10, min(int(params.get("quality", "60")), 95))
    width = int(params.get("width", "960"))
    height = int(params.get("height", "540"))

    frame_interval = 1.0 / fps_target
    adaptive_interval = frame_interval
    running = True
    worker = _get_worker()

    try:
        while running:
            start = time.time()

            # Try to get a JPEG frame from the isolated desktop
            frame_data = None
            if _relay_available():
                result = _queue_headless_action("screenshot", {"session_id": session_id})
                if result.get("ok") and result.get("image"):
                    frame_data = base64.b64decode(result["image"])
            else:
                frame_data = worker.capture_jpeg(
                    session_id, width=width, height=height, quality=quality
                )

            if frame_data:
                b64 = base64.b64encode(frame_data).decode()
                await websocket.send_json({
                    "type": "frame",
                    "data": b64,
                    "format": "jpeg",
                    "session_id": session_id,
                    "fps": fps_target,
                    "timestamp": time.time(),
                })
            else:
                await websocket.send_json({
                    "type": "status",
                    "state": "waiting",
                    "session_id": session_id,
                    "timestamp": time.time(),
                })

            # Handle incoming interactive commands (isolated desktop only)
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                msg = json.loads(raw)
                cmd = msg.get("cmd", "")

                if cmd == "click":
                    _queue_headless_action("click", {"session_id": session_id, "x": msg.get("x", 0), "y": msg.get("y", 0), "button": msg.get("button", 1)})
                elif cmd == "key":
                    _queue_headless_action("key", {"session_id": session_id, "key": msg.get("key", "Return")})
                elif cmd == "type":
                    _queue_headless_action("type", {"session_id": session_id, "text": msg.get("text", "")})
                elif cmd == "launch":
                    _queue_headless_action("launch", {"session_id": session_id, "app_name": msg.get("app", ""), "command": msg.get("command", [])})
                elif cmd == "set_session":
                    session_id = msg.get("session_id", "default")
                elif cmd == "quit":
                    running = False
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

            # Adaptive FPS: slow down if frame capture took too long
            elapsed = time.time() - start
            if elapsed > frame_interval * 1.5:
                adaptive_interval = min(adaptive_interval * 1.2, 0.5)
            else:
                adaptive_interval = max(adaptive_interval * 0.95, frame_interval)

            await asyncio.sleep(max(0, adaptive_interval - elapsed))

            elapsed = time.time() - start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except:
            pass
