"""Ambient Overlay — Spotlight/Alfred-style quick-command popup."""

import os
import json
import asyncio
import threading
import tempfile
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

router = APIRouter(prefix="/ambient", tags=["ambient"])

OVERLAY_HTML = None


def _load_overlay_html():
    global OVERLAY_HTML
    html_path = Path(__file__).parent / "overlay.html"
    if html_path.exists():
        OVERLAY_HTML = html_path.read_text(encoding="utf-8")
    return OVERLAY_HTML


@router.get("/overlay", response_class=HTMLResponse)
async def get_overlay():
    html = _load_overlay_html()
    if not html:
        return HTMLResponse("<h1>Overlay not found</h1>", status_code=404)
    return HTMLResponse(html)


@router.get("/overlay-search")
async def overlay_search(q: str = Query("", description="Search query")):
    """REST endpoint for the Electron overlay's quick search."""
    if not q:
        return JSONResponse({"results": []})
    results = await _route_query(q)
    return JSONResponse({"results": results, "query": q})


@router.websocket("/ws")
async def overlay_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action", "")

            if action == "ping":
                await websocket.send_json({"type": "pong"})

            elif action == "query":
                query = msg.get("query", "")
                results = await _route_query(query)
                await websocket.send_json({
                    "type": "results",
                    "query": query,
                    "results": results
                })

            elif action == "execute":
                command = msg.get("command", "")
                await websocket.send_json({
                    "type": "executing",
                    "command": command
                })
                result = await _execute_command(command)
                await websocket.send_json({
                    "type": "result",
                    "command": command,
                    "result": result
                })

            elif action == "hide":
                await websocket.send_json({"type": "hidden"})

            elif action == "voice":
                await websocket.send_json({
                    "type": "voice",
                    "status": "listening",
                    "hint": "Say your command..."
                })

    except WebSocketDisconnect:
        pass


async def _route_query(query: str) -> list:
    try:
        from edge_router import classify_intent
        intent, confidence, sub_type = classify_intent(query)
        return [{
            "label": f"[{intent}] {query}",
            "description": f"{sub_type} ({confidence:.0%})",
            "action": intent,
            "confidence": confidence
        }]
    except Exception:
        return [{
            "label": query,
            "description": "Direct execution",
            "action": "chat",
            "confidence": 1.0
        }]


async def _execute_command(command: str) -> dict:
    try:
        from ai_agent import generate_response
        response = await generate_response(command)
        return {"success": True, "output": response}
    except Exception as e:
        return {"success": False, "error": str(e)}


class AmbientOverlayController:
    def __init__(self):
        self._process = None
        self._visible = False

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self):
        self._visible = True
        self._open_overlay_window()

    def hide(self):
        self._visible = False

    def _open_overlay_window(self):
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:7890/ambient/overlay")

    @property
    def is_visible(self):
        return self._visible


overlay_controller = AmbientOverlayController()
