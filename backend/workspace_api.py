"""JARVIS Workspace API - HTTP and WebSocket endpoints for workspace control.

Provides endpoints for:
- Creating/starting/stopping/destroying workspaces
- Launching apps inside workspaces
- Streaming workspace display to the frontend
- Mission management (create, plan, start, pause, stop)
- Approval system for high-risk actions
- Interactive control (click, type, key injection)
"""

import os
import sys
import json
import time
import base64
import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

log = logging.getLogger("workspace_api")

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def _get_manager():
    from workspace_manager import get_workspace_manager
    return get_workspace_manager()


def _get_agent():
    from workspace_agent import get_workspace_agent
    return get_workspace_agent()


def _get_mission_engine():
    from mission_engine import get_mission_engine
    return get_mission_engine()


class CreateWorkspaceReq(BaseModel):
    name: str = "JARVIS Workspace"
    width: int = 1920
    height: int = 1080
    capabilities: List[str] = []
    mount_paths: dict = {}


class LaunchAppReq(BaseModel):
    workspace_id: str
    app_name: str
    command: List[str] = []


class ClickReq(BaseModel):
    workspace_id: str
    x: int = 0
    y: int = 0
    button: int = 1


class KeyReq(BaseModel):
    workspace_id: str
    key: str = "Return"


class TypeReq(BaseModel):
    workspace_id: str
    text: str = ""


class MissionReq(BaseModel):
    objective: str
    workspace_id: str


class ApprovalReq(BaseModel):
    mission_id: str
    step_number: int


class ReplicatorScanReq(BaseModel):
    force: bool = False


# ── Workspace Lifecycle ──

@router.get("/list")
async def workspace_list():
    mgr = _get_manager()
    return {"ok": True, "workspaces": mgr.list_workspaces()}


@router.post("/create")
async def workspace_create(req: CreateWorkspaceReq):
    mgr = _get_manager()
    ws = mgr.create_workspace(
        name=req.name,
        resolution=(req.width, req.height),
        capabilities=req.capabilities or None,
        mount_paths=req.mount_paths or None,
    )
    return {"ok": True, "workspace": ws.to_dict()}


@router.post("/start")
async def workspace_start(body: dict):
    ws_id = body.get("workspace_id", "")
    mgr = _get_manager()
    return mgr.start_workspace(ws_id)


@router.post("/stop")
async def workspace_stop(body: dict):
    ws_id = body.get("workspace_id", "")
    mgr = _get_manager()
    return mgr.stop_workspace(ws_id)


@router.post("/destroy")
async def workspace_destroy(body: dict):
    ws_id = body.get("workspace_id", "")
    mgr = _get_manager()
    return mgr.destroy_workspace(ws_id)


@router.get("/status")
async def workspace_status(workspace_id: str = ""):
    mgr = _get_manager()
    if workspace_id:
        ws = mgr.get_workspace(workspace_id)
        if ws:
            return {"ok": True, "workspace": ws.to_dict()}
        return {"ok": False, "error": "Workspace not found"}
    return {"ok": True, "workspaces": mgr.list_workspaces()}


# ── App Management ──

@router.post("/launch")
async def workspace_launch(req: LaunchAppReq):
    mgr = _get_manager()
    return mgr.launch_app(req.workspace_id, req.app_name, req.command or None)


# ── Interactive Control ──

@router.post("/click")
async def workspace_click(req: ClickReq):
    mgr = _get_manager()
    return mgr.inject_click(req.workspace_id, req.x, req.y, req.button)


@router.post("/key")
async def workspace_key(req: KeyReq):
    mgr = _get_manager()
    return mgr.inject_key(req.workspace_id, req.key)


@router.post("/type")
async def workspace_type(req: TypeReq):
    mgr = _get_manager()
    return mgr.inject_text(req.workspace_id, req.text)


# ── Mission Management (via Mission Engine) ──────────────────────────

@router.post("/mission/create")
async def mission_create(req: MissionReq):
    engine = _get_mission_engine()
    graph = engine.create_mission(req.objective, req.workspace_id)
    return {"ok": True, "mission": graph.to_dict()}


@router.post("/mission/plan")
async def mission_plan(body: dict):
    mission_id = body.get("mission_id", "")
    engine = _get_mission_engine()
    graph = engine.plan_mission(mission_id)
    return {"ok": True, "mission": graph.to_dict()}


@router.post("/mission/start")
async def mission_start(body: dict):
    mission_id = body.get("mission_id", "")
    engine = _get_mission_engine()
    graph = engine.start_mission(mission_id)
    return {"ok": True, "mission": graph.to_dict()}


@router.post("/mission/pause")
async def mission_pause(body: dict):
    mission_id = body.get("mission_id", "")
    engine = _get_mission_engine()
    engine.pause_mission(mission_id)
    return {"ok": True}


@router.post("/mission/resume")
async def mission_resume(body: dict):
    mission_id = body.get("mission_id", "")
    engine = _get_mission_engine()
    engine.resume_mission(mission_id)
    return {"ok": True}


@router.post("/mission/stop")
async def mission_stop(body: dict):
    mission_id = body.get("mission_id", "")
    engine = _get_mission_engine()
    engine.stop_mission(mission_id)
    return {"ok": True}


@router.get("/mission/status")
async def mission_status(mission_id: str = ""):
    engine = _get_mission_engine()
    if mission_id:
        m = engine.get_mission(mission_id)
        if m:
            return {"ok": True, "mission": m.to_dict()}
        return {"ok": False, "error": "Mission not found"}
    return {"ok": True, "missions": [m.to_dict() for m in engine.list_missions()]}


# ── Approval System ──

@router.get("/approvals/pending")
async def approvals_pending():
    agent = _get_agent()
    return {"ok": True, "approvals": agent.get_pending_approvals()}


@router.post("/approvals/approve")
async def approvals_approve(req: ApprovalReq):
    agent = _get_agent()
    return agent.approve_step(req.mission_id, req.step_number)


@router.post("/approvals/deny")
async def approvals_deny(req: ApprovalReq):
    agent = _get_agent()
    return agent.deny_step(req.mission_id, req.step_number)


# ── Workspace Replicator ──

@router.get("/replicator/profile")
async def replicator_profile():
    from workspace_replicator import get_workspace_replicator
    r = get_workspace_replicator()
    return {"ok": True, "profile": r.get_profile_dict()}


@router.post("/replicator/scan")
async def replicator_scan(req: ReplicatorScanReq = None):
    from workspace_replicator import get_workspace_replicator
    r = get_workspace_replicator()
    if req and not req.force and not r.needs_rescan():
        return {"ok": True, "cached": True, "profile": r.get_profile_dict()}
    return r.scan_all()


@router.get("/replicator/auth-needing-apps")
async def replicator_auth_apps():
    from workspace_replicator import get_workspace_replicator
    r = get_workspace_replicator()
    return {"ok": True, "apps": r.get_auth_needing_apps()}


@router.get("/replicator/app-manifest")
async def replicator_manifest():
    from workspace_replicator import get_workspace_replicator
    r = get_workspace_replicator()
    return {"ok": True, "manifest": r.get_workspace_app_manifest()}


# ── Workspace Verification ──

@router.post("/verify/screenshot")
async def verify_screenshot(body: dict):
    from workspace_manager import get_workspace_manager
    from workspace_verifier import get_workspace_verifier
    ws_id = body.get("workspace_id", "")
    action = body.get("action", "screenshot")
    params = body.get("params", {})
    expected = body.get("expected_text", "")
    mgr = get_workspace_manager()
    verifier = get_workspace_verifier()
    screenshot = mgr.capture_frame(ws_id, quality=70)
    if not screenshot:
        return {"ok": False, "error": "No screenshot available"}
    result = verifier.verify_step(screenshot, action, params, expected)
    return {"ok": True, "verification": result.to_dict()}


# ── WebSocket: Live Workspace Stream + Interactive Control ──

@router.websocket("/ws/stream")
async def workspace_ws_stream(websocket: WebSocket):
    """WebSocket endpoint for live workspace frame streaming and control.

    Query params: workspace_id (required), fps (default 10), quality (default 60)

    Client -> server (JSON):
      {"cmd": "click", "x": 100, "y": 200, "button": 1}
      {"cmd": "key", "key": "Return"}
      {"cmd": "type", "text": "hello"}
      {"cmd": "launch", "name": "chrome", "command": ["google-chrome"]}
      {"cmd": "quit"}

    Server -> client:
      {"type": "frame", "data": "<base64 jpeg>", "ts": ...}
      {"type": "status", "workspace": {...}, "mission": {...}}
      {"type": "approval_needed", "mission_id": ..., "step": {...}}
    """
    await websocket.accept()
    params = websocket.query_params
    ws_id = params.get("workspace_id", "")
    fps_target = max(1, min(int(params.get("fps", "10")), 30))
    quality = max(10, min(int(params.get("quality", "60")), 95))

    if not ws_id:
        await websocket.send_json({"type": "error", "error": "workspace_id required"})
        await websocket.close()
        return

    mgr = _get_manager()
    agent = _get_agent()
    frame_interval = 1.0 / fps_target
    running = True

    # Track missions in this workspace for real-time events
    def on_mission_event(mission_id, event_type, data):
        try:
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({
                    "type": "mission_event",
                    "mission_id": mission_id,
                    "event": event_type,
                    "data": data,
                }),
                asyncio.get_event_loop()
            )
        except Exception:
            pass

    try:
        while running:
            start = time.time()

            ws = mgr.get_workspace(ws_id)
            if not ws or ws.status != "running":
                await websocket.send_json({
                    "type": "status",
                    "workspace": ws.to_dict() if ws else None,
                    "ts": time.time(),
                })
                await asyncio.sleep(1)
                continue

            # Capture frame
            frame_data = mgr.capture_frame(ws_id, quality)
            if frame_data:
                b64 = base64.b64encode(frame_data).decode()
                await websocket.send_json({
                    "type": "frame",
                    "data": b64,
                    "ts": time.time(),
                    "fps": fps_target,
                })

            # Send workspace + mission status
            active_missions = [m for m in agent.list_missions() if m.get("workspace_id") == ws_id]
            await websocket.send_json({
                "type": "status",
                "workspace": ws.to_dict(),
                "missions": active_missions,
                "ts": time.time(),
            })

            # Handle incoming commands
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                msg = json.loads(raw)
                cmd = msg.get("cmd", "")

                if cmd == "click":
                    mgr.inject_click(ws_id, msg.get("x", 0), msg.get("y", 0), msg.get("button", 1))
                elif cmd == "key":
                    mgr.inject_key(ws_id, msg.get("key", "Return"))
                elif cmd == "type":
                    mgr.inject_text(ws_id, msg.get("text", ""))
                elif cmd == "launch":
                    mgr.launch_app(ws_id, msg.get("name", ""), msg.get("command"))
                elif cmd == "quit":
                    running = False
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

            elapsed = time.time() - start
            await asyncio.sleep(max(0, frame_interval - elapsed))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"[WORKSPACE WS] Error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


# ── Capabilities Detection ─────────────────────────────────────────────────

@router.get("/capabilities")
def capabilities():
    from capabilities import get_capabilities
    return get_capabilities().to_dict()


@router.post("/capabilities/refresh")
def capabilities_refresh():
    from capabilities import refresh_capabilities
    return refresh_capabilities().to_dict()


@router.get("/setup/status")
def setup_status():
    from capabilities import get_capabilities
    caps = get_capabilities()
    return {
        "setup_complete": caps.setup_complete,
        "isolation_backend": caps.isolation_backend,
        "isolation_available": caps.isolation_available,
        "recommended_action": caps.recommended_action,
        "tools": {k: v.to_dict() for k, v in caps.tools.items()},
    }


# ── File Browser ─────────────────────────────────────────────────────────

@router.get("/files")
def workspace_files(workspace_id: str):
    """List files in a workspace directory."""
    import os
    from pathlib import Path
    ws_dir = Path(os.path.expanduser(f"~/.jarvis/workspaces/{workspace_id}/files"))
    if not ws_dir.exists():
        return {"files": []}
    files = []
    for f in ws_dir.rglob("*"):
        if f.is_file():
            stat = f.stat()
            files.append({
                "path": str(f.relative_to(ws_dir)),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": files}
