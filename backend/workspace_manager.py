"""JARVIS Workspace Manager — Elastic Workspace Lifecycle.

Creates and manages workspaces using the Capability Fabric.
The user never sees which backend is used — JARVIS decides.

Architecture:
  User → WorkspaceManager → Capability Fabric → Platform Adapter
                                                    ↓
                                              Real Screenshot
                                                    ↓
                                              Cockpit UI

The Capability Fabric provides a unified interface:
  fabric.computer.screenshot()
  fabric.computer.click(x, y)
  fabric.browser.navigate(url)
  fabric.app.launch("Blender")

The workspace manager routes to the correct adapter automatically.
"""

import os
import sys
import json
import time
import uuid
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_manager")

WORKSPACE_DIR = Path(os.path.expanduser("~/.jarvis/workspaces"))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class WorkspaceApp:
    name: str
    command: List[str]
    pid: Optional[int] = None
    started_at: float = 0
    status: str = "stopped"

    def to_dict(self):
        return {
            "name": self.name, "command": self.command,
            "pid": self.pid, "started_at": self.started_at,
            "status": self.status,
        }


@dataclass
class WorkspaceState:
    id: str
    name: str
    status: str = "created"
    backend: str = "auto"
    display_id: int = 0
    resolution: tuple = (1920, 1080)
    created_at: float = 0
    started_at: float = 0
    uptime: float = 0
    apps: List[WorkspaceApp] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    mounted_paths: Dict[str, str] = field(default_factory=dict)
    error: str = ""
    current_action: str = ""
    agent_status: str = "idle"

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "status": self.status,
            "backend": self.backend,
            "display_id": self.display_id, "resolution": list(self.resolution),
            "created_at": self.created_at, "started_at": self.started_at,
            "uptime": self.uptime, "apps": [a.to_dict() for a in self.apps],
            "capabilities": self.capabilities,
            "mounted_paths": self.mounted_paths, "error": self.error,
            "current_action": self.current_action, "agent_status": self.agent_status,
        }


class WorkspaceManager:
    def __init__(self):
        self._workspaces: Dict[str, WorkspaceState] = {}
        self._backends: Dict[str, object] = {}
        self._lock = threading.Lock()
        self._platform = sys.platform
        self._recover_workspaces()

    def _get_backend(self, ws_id: str):
        """Get the active backend for a workspace."""
        with self._lock:
            ws = self._workspaces.get(ws_id)
        if not ws:
            return None
        return self._backends.get(ws_id)

    def _recover_workspaces(self):
        for ws_dir in WORKSPACE_DIR.iterdir():
            if ws_dir.is_dir():
                state_file = ws_dir / "state.json"
                if state_file.exists():
                    try:
                        with open(state_file) as f:
                            data = json.load(f)
                        ws = WorkspaceState(
                            id=data["id"], name=data["name"],
                            status="created",  # Reset to created on recovery
                            backend=data.get("backend", "auto"),
                            display_id=data.get("display_id", 0),
                            resolution=tuple(data.get("resolution", [1920, 1080])),
                            created_at=data.get("created_at", 0),
                            capabilities=data.get("capabilities", []),
                            mounted_paths=data.get("mounted_paths", {}),
                        )
                        with self._lock:
                            self._workspaces[ws.id] = ws
                        log.info(f"[WORKSPACE] Recovered: {ws.id} ({ws.name})")
                    except Exception as e:
                        log.error(f"[WORKSPACE] Failed to recover {ws_dir}: {e}")

    def _save_state(self, ws: WorkspaceState):
        ws_dir = WORKSPACE_DIR / ws.id
        ws_dir.mkdir(parents=True, exist_ok=True)
        state_file = ws_dir / "state.json"
        with open(state_file, "w") as f:
            json.dump(ws.to_dict(), f, indent=2)

    def create_workspace(self, name: str = "JARVIS Workspace",
                         resolution: tuple = (1920, 1080),
                         capabilities: List[str] = None,
                         mount_paths: Dict[str, str] = None) -> WorkspaceState:
        ws_id = str(uuid.uuid4())[:8]
        ws = WorkspaceState(
            id=ws_id, name=name,
            resolution=resolution,
            created_at=time.time(),
            capabilities=capabilities or ["browser", "editor", "files", "terminal"],
            mounted_paths=mount_paths or {},
        )
        with self._lock:
            self._workspaces[ws_id] = ws
        self._save_state(ws)
        ws_dir = WORKSPACE_DIR / ws_id
        (ws_dir / "files").mkdir(exist_ok=True)
        (ws_dir / "screenshots").mkdir(exist_ok=True)
        (ws_dir / "env").mkdir(exist_ok=True)
        log.info(f"[WORKSPACE] Created: {ws_id} ({name})")
        return ws

    def start_workspace(self, ws_id: str) -> dict:
        with self._lock:
            ws = self._workspaces.get(ws_id)
        if not ws:
            return {"ok": False, "error": f"Workspace {ws_id} not found"}
        if ws.status == "running":
            return {"ok": True, "workspace": ws.to_dict()}

        # Auto-detect and initialize the best backend
        backend = self._init_backend(ws)
        if not backend:
            ws.error = "No execution backends available — install WSL2 or pyautogui"
            self._save_state(ws)
            return {"ok": False, "error": ws.error}

        # Start the backend
        try:
            started = backend.start(resolution=ws.resolution)
            if not started:
                ws.error = f"Backend {backend.name} failed to start"
                self._save_state(ws)
                return {"ok": False, "error": ws.error}
        except Exception as e:
            ws.error = f"Backend start error: {e}"
            self._save_state(ws)
            return {"ok": False, "error": ws.error}

        ws.backend = backend.name
        ws.status = "running"
        ws.started_at = time.time()
        ws.error = ""
        self._save_state(ws)
        log.info(f"[WORKSPACE] Started: {ws_id} (backend={backend.name})")
        return {"ok": True, "workspace": ws.to_dict()}

    def _init_backend(self, ws: WorkspaceState):
        """Auto-detect and create the best backend for this workspace."""
        # If a specific backend is requested, try that first
        if ws.backend and ws.backend != "auto":
            b = self._try_backend(ws.backend)
            if b:
                self._backends[ws.id] = b
                return b

        # Auto-detect: try WSL first, then native, then fallback
        for backend_name in ["wsl_xvfb", "windows_native", "macos_native", "linux_vdi", "container", "browser_sandbox"]:
            b = self._try_backend(backend_name)
            if b:
                self._backends[ws.id] = b
                return b

        return None

    def _try_backend(self, name: str):
        """Try to create a specific backend."""
        try:
            if name == "wsl_xvfb":
                from workspace_backends.wsl_xvfb import WslXvfbBackend
                b = WslXvfbBackend()
                if b.is_available():
                    return b
            elif name == "windows_native":
                from workspace_backends.windows_native import WindowsNativeBackend
                b = WindowsNativeBackend()
                if b.is_available():
                    return b
            elif name == "macos_native":
                from workspace_backends.macos_native import MacOsNativeBackend
                b = MacOsNativeBackend()
                if b.is_available():
                    return b
            elif name == "container":
                from workspace_backends.container_backend import ContainerBackend
                b = ContainerBackend()
                if b.is_available():
                    return b
            elif name == "browser_sandbox":
                from workspace_backends.browser_sandbox import BrowserSandboxBackend
                b = BrowserSandboxBackend()
                if b.is_available():
                    return b
            elif name == "linux_vdi":
                # Try the existing execution_fabric
                from execution_fabric import get_execution_fabric
                fabric = get_execution_fabric()
                if fabric:
                    return fabric
        except Exception as e:
            log.debug(f"[WORKSPACE] Backend {name} not available: {e}")
        return None

    def stop_workspace(self, ws_id: str) -> dict:
        with self._lock:
            ws = self._workspaces.get(ws_id)
        if not ws:
            return {"ok": False, "error": "Workspace not found"}

        backend = self._backends.get(ws_id)
        if backend:
            try:
                backend.stop()
            except Exception as e:
                log.warning(f"[WORKSPACE] Backend stop error: {e}")
            del self._backends[ws_id]

        ws.status = "stopped"
        ws.uptime = time.time() - ws.started_at if ws.started_at else 0
        self._save_state(ws)
        log.info(f"[WORKSPACE] Stopped: {ws_id}")
        return {"ok": True}

    def destroy_workspace(self, ws_id: str) -> dict:
        self.stop_workspace(ws_id)
        with self._lock:
            self._workspaces.pop(ws_id, None)
        ws_dir = WORKSPACE_DIR / ws_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir, ignore_errors=True)
        log.info(f"[WORKSPACE] Destroyed: {ws_id}")
        return {"ok": True}

    def get_workspace(self, ws_id: str) -> Optional[WorkspaceState]:
        with self._lock:
            return self._workspaces.get(ws_id)

    def list_workspaces(self) -> List[WorkspaceState]:
        with self._lock:
            return list(self._workspaces.values())

    def update_action(self, ws_id: str, action: str, status: str = "working"):
        with self._lock:
            ws = self._workspaces.get(ws_id)
        if ws:
            ws.current_action = action
            ws.agent_status = status
            self._save_state(ws)

    def launch_app(self, ws_id: str, app_name: str, command: List[str] = None) -> dict:
        with self._lock:
            ws = self._workspaces.get(ws_id)
        if not ws:
            return {"ok": False, "error": f"Workspace {ws_id} not found"}
        if ws.status != "running":
            return {"ok": False, "error": "Workspace not running"}

        backend = self._backends.get(ws_id)
        if not backend:
            return {"ok": False, "error": "No backend available"}

        result = backend.launch_app(app_name, command)
        if result.ok:
            app = WorkspaceApp(
                name=app_name, command=command or [app_name],
                started_at=time.time(), status="running",
            )
            ws.apps.append(app)
            self._save_state(ws)
        return {"ok": result.ok, "output": result.output, "error": result.error}

    def capture_frame(self, ws_id: str, quality: int = 60) -> Optional[bytes]:
        """Capture a real frame from the workspace backend."""
        with self._lock:
            ws = self._workspaces.get(ws_id)
        if not ws or ws.status != "running":
            return None

        backend = self._backends.get(ws_id)
        if not backend:
            return self._synthetic_frame(ws, quality)

        try:
            frame = backend.capture_frame(quality=quality)
            if frame:
                # Save screenshot for verification
                ss_dir = WORKSPACE_DIR / ws.id / "screenshots"
                ss_dir.mkdir(exist_ok=True)
                ss_path = ss_dir / f"frame_{int(time.time() * 1000)}.jpg"
                with open(ss_path, "wb") as f:
                    f.write(frame)
                return frame
        except Exception as e:
            log.error(f"[WORKSPACE] Frame capture failed: {e}")

        # Fallback to synthetic
        return self._synthetic_frame(ws, quality)

    def _synthetic_frame(self, ws: WorkspaceState, quality: int) -> Optional[bytes]:
        """Generate a synthetic placeholder frame (fallback only)."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            w, h = ws.resolution
            img = Image.new("RGB", (w, h), (8, 12, 10))
            draw = ImageDraw.Draw(img)
            for x in range(0, w, 64):
                draw.line([(x, 0), (x, h)], fill=(0, 255, 102, 8), width=1)
            for y in range(0, h, 64):
                draw.line([(0, y), (w, y)], fill=(0, 255, 102, 8), width=1)
            try:
                font_l = ImageFont.truetype("arial.ttf", 36)
                font_s = ImageFont.truetype("arial.ttf", 18)
            except Exception:
                font_l = ImageFont.load_default()
                font_s = ImageFont.load_default()
            title = "JARVIS WORKSPACE"
            bb = draw.textbbox((0, 0), title, font=font_l)
            draw.text(((w - bb[2]) // 2, h // 2 - 60), title, fill=(0, 255, 102), font=font_l)
            status = ws.current_action or f"Backend: {ws.backend}"
            bb2 = draw.textbbox((0, 0), status, font=font_s)
            draw.text(((w - bb2[2]) // 2, h // 2), status, fill=(100, 200, 140), font=font_s)
            info = f"~/.jarvis/workspaces/{ws.id}/files/"
            bb3 = draw.textbbox((0, 0), info, font=font_s)
            draw.text(((w - bb3[2]) // 2, h // 2 + 40), info, fill=(80, 120, 100), font=font_s)
            import io
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
        except Exception as e:
            log.debug(f"[WORKSPACE] Synthetic frame failed: {e}")
            return None

    def inject_click(self, ws_id: str, x: int, y: int, button: int = 1) -> dict:
        """Inject a real click into the workspace."""
        backend = self._backends.get(ws_id)
        if not backend:
            return {"ok": False, "error": "No backend"}
        result = backend.inject_click(x, y, button)
        return {"ok": result.ok, "error": result.error, "method": result.method}

    def inject_key(self, ws_id: str, key: str) -> dict:
        """Inject a real key press into the workspace."""
        backend = self._backends.get(ws_id)
        if not backend:
            return {"ok": False, "error": "No backend"}
        result = backend.inject_key(key)
        return {"ok": result.ok, "error": result.error, "method": result.method}

    def inject_text(self, ws_id: str, text: str) -> dict:
        """Type real text into the workspace."""
        backend = self._backends.get(ws_id)
        if not backend:
            return {"ok": False, "error": "No backend"}
        result = backend.inject_text(text)
        return {"ok": result.ok, "error": result.error, "method": result.method}

    def list_windows(self, ws_id: str) -> List[Dict]:
        """List windows in the workspace."""
        backend = self._backends.get(ws_id)
        if not backend:
            return []
        try:
            return backend.list_windows()
        except Exception:
            return []

    def focus_window(self, ws_id: str, title: str) -> dict:
        """Focus a window in the workspace."""
        backend = self._backends.get(ws_id)
        if not backend:
            return {"ok": False, "error": "No backend"}
        result = backend.focus_window(title)
        return {"ok": result.ok, "error": result.error}

    def get_backend_info(self, ws_id: str) -> Dict:
        """Get info about the active backend."""
        backend = self._backends.get(ws_id)
        if not backend:
            return {"name": "none", "capabilities": []}
        return {
            "name": backend.name,
            "capabilities": backend.capabilities,
            "running": backend.is_running(),
        }


_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager
