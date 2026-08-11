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
from typing import Optional, List, Dict, Tuple, Any

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

        # Use the Workspace Broker for intelligent selection
        try:
            from workspace_manager import get_workspace_broker, TaskRequirements
            broker = get_workspace_broker()
            req = TaskRequirements(
                browser="browser" in ws.capabilities,
                gui="editor" in ws.capabilities or "browser" in ws.capabilities,
                filesystem="files" in ws.capabilities,
                network=True,
                gpu=False,
                persistent_state=True,
            )
            decision = broker.select_backend(req)
            log.info(f"[WORKSPACE] Broker selected: {decision.backend} — {decision.reason}")

            b = self._try_backend(decision.backend)
            if b:
                self._backends[ws.id] = b
                return b
        except Exception as e:
            log.debug(f"[WORKSPACE] Broker fallback: {e}")

        # Fallback: try backends in order
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


# ══════════════════════════════════════════════════════════════
#  WORKSPACE BROKER — Intelligent Backend Selection
# ══════════════════════════════════════════════════════════════

@dataclass
class TaskRequirements:
    """What a task needs from its execution environment."""
    browser: bool = False
    gui: bool = False
    filesystem: bool = True
    network: bool = True
    gpu: bool = False
    persistent_state: bool = False
    windows_apps: bool = False
    linux_apps: bool = False
    macos_apps: bool = False
    security_level: str = "standard"  # standard, elevated, maximum

    @classmethod
    def from_goal(cls, goal: str) -> "TaskRequirements":
        """Infer requirements from a natural language goal."""
        goal_lower = goal.lower()
        req = cls()
        # Browser
        if any(w in goal_lower for w in ["browse", "website", "search", "google", "chrome", "firefox", "safari", "url", "http"]):
            req.browser = True
        # GUI
        if any(w in goal_lower for w in ["click", "open", "launch", "screenshot", "visual", "animation", "blender", "photoshop", "gui"]):
            req.gui = True
        # Network
        if any(w in goal_lower for w in ["download", "upload", "email", "send", "api", "fetch", "web"]):
            req.network = True
        # GPU
        if any(w in goal_lower for w in ["3d", "render", "gpu", "cuda", "blender", "animation", "video"]):
            req.gpu = True
        # Persistent state
        if any(w in goal_lower for w in ["save", "project", "workspace", "persistent", "resume"]):
            req.persistent_state = True
        # Windows apps
        if any(w in goal_lower for w in ["word", "excel", "powerpoint", "autocad", "office", "windows"]):
            req.windows_apps = True
        # Linux apps
        if any(w in goal_lower for w in ["linux", "ubuntu", "debian", "container", "docker"]):
            req.linux_apps = True
        return req

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# Backend cost/overhead estimates (lower = cheaper)
BACKEND_COSTS = {
    "native": 1,
    "windows_native": 2,
    "macos_native": 2,
    "linux_xvfb": 3,
    "wsl_xvfb": 4,
    "browser_sandbox": 2,
    "firejail": 3,
    "bubblewrap": 3,
    "nspawn": 5,
    "container": 6,
    "qemu": 15,
    "kvm": 12,
    "hyperv": 20,
    "virtualbox": 18,
    "macos_vz": 15,
    "windows_sandbox": 10,
}

# Backend capability profiles
BACKEND_CAPABILITIES = {
    "native": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "windows_native": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "macos_native": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "linux_xvfb": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "wsl_xvfb": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "browser_sandbox": {"browser": True, "gui": False, "filesystem": False, "network": True, "gpu": False},
    "firejail": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "bubblewrap": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "nspawn": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
    "container": {"browser": True, "gui": False, "filesystem": True, "network": True, "gpu": False},
    "qemu": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": True},
    "kvm": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": True},
    "hyperv": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": True},
    "virtualbox": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": True},
    "macos_vz": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": True},
    "windows_sandbox": {"browser": True, "gui": True, "filesystem": True, "network": True, "gpu": False},
}

# RAM overhead estimates (GB)
BACKEND_RAM_OVERHEAD = {
    "native": 0.1,
    "windows_native": 0.2,
    "macos_native": 0.2,
    "linux_xvfb": 0.3,
    "wsl_xvfb": 0.5,
    "browser_sandbox": 0.1,
    "firejail": 0.1,
    "bubblewrap": 0.1,
    "nspawn": 0.5,
    "container": 0.3,
    "qemu": 2.0,
    "kvm": 1.5,
    "hyperv": 2.0,
    "virtualbox": 2.0,
    "macos_vz": 1.5,
    "windows_sandbox": 1.0,
}


@dataclass
class BrokerDecision:
    """Result of the workspace broker's backend selection."""
    backend: str
    reason: str
    cost: int
    ram_overhead_gb: float
    capabilities_matched: List[str]
    capabilities_missing: List[str]
    alternatives: List[dict]

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "reason": self.reason,
            "cost": self.cost,
            "ram_overhead_gb": self.ram_overhead_gb,
            "capabilities_matched": self.capabilities_matched,
            "capabilities_missing": self.capabilities_missing,
            "alternatives": self.alternatives,
        }


class WorkspaceBroker:
    """Intelligent workspace backend selector.

    Given task requirements + system capabilities, selects the cheapest
    suitable execution environment.
    """

    def __init__(self):
        self._hw = None
        self._virt = None

    def _ensure_detected(self):
        if self._hw is None:
            from hardware_detector import get_hardware_profile
            self._hw = get_hardware_profile()
        if self._virt is None:
            from hardware_detector import get_virtualization_info
            self._virt = get_virtualization_info()

    def select_backend(self, requirements: TaskRequirements) -> BrokerDecision:
        """Select the best backend for the given task requirements."""
        self._ensure_detected()

        available = self._virt.available_backends()
        candidates = []

        for backend_name in available:
            caps = BACKEND_CAPABILITIES.get(backend_name, {})
            cost = BACKEND_COSTS.get(backend_name, 10)
            ram = BACKEND_RAM_OVERHEAD.get(backend_name, 1.0)

            # Check if this backend satisfies all requirements
            matched = []
            missing = []
            for req_key, req_val in requirements.to_dict().items():
                if req_val is True:
                    if caps.get(req_key, False):
                        matched.append(req_key)
                    else:
                        missing.append(req_key)

            # Skip if missing critical capabilities
            if missing:
                continue

            # Check RAM budget
            available_ram = self._hw.ram_available_gb
            if ram > available_ram * 0.5:
                continue

            candidates.append({
                "backend": backend_name,
                "cost": cost,
                "ram_overhead_gb": ram,
                "matched": matched,
                "missing": missing,
            })

        if not candidates:
            # Fallback: pick the cheapest available backend
            fallback = available[0] if available else "native"
            return BrokerDecision(
                backend=fallback,
                reason="No backend satisfies all requirements — using cheapest fallback",
                cost=BACKEND_COSTS.get(fallback, 10),
                ram_overhead_gb=BACKEND_RAM_OVERHEAD.get(fallback, 1.0),
                capabilities_matched=[],
                capabilities_missing=[k for k, v in requirements.to_dict().items() if v],
                alternatives=[],
            )

        # Sort by cost (cheapest first)
        candidates.sort(key=lambda c: c["cost"])
        best = candidates[0]

        alternatives = [
            {"backend": c["backend"], "cost": c["cost"], "ram_gb": c["ram_overhead_gb"]}
            for c in candidates[1:4]
        ]

        return BrokerDecision(
            backend=best["backend"],
            reason=f"Cheapest backend satisfying all {len(best['matched'])} requirements",
            cost=best["cost"],
            ram_overhead_gb=best["ram_overhead_gb"],
            capabilities_matched=best["matched"],
            capabilities_missing=best["missing"],
            alternatives=alternatives,
        )

    def get_system_info(self) -> dict:
        """Get full system info for the frontend."""
        self._ensure_detected()
        return {
            "hardware": self._hw.to_dict(),
            "virtualization": self._virt.to_dict(),
            "available_backends": self._virt.available_backends(),
        }


_broker: Optional[WorkspaceBroker] = None


def get_workspace_broker() -> WorkspaceBroker:
    global _broker
    if _broker is None:
        _broker = WorkspaceBroker()
    return _broker


# ══════════════════════════════════════════════════════════════
#  WORKSPACE ORCHESTRATOR — Resource Lifecycle & Federation
# ══════════════════════════════════════════════════════════════

@dataclass
class WorkerSlot:
    """A single execution worker in the federation."""
    id: str
    app_name: str
    backend_name: str
    status: str = "creating"  # creating, running, suspended, released
    pid: Optional[int] = None
    ram_allocated_mb: float = 0
    created_at: float = 0
    started_at: float = 0
    released_at: float = 0
    # Semantic activity channel
    current_action: str = ""
    current_tool: str = ""
    current_object: str = ""
    progress: float = 0
    verification_status: str = ""  # pending, passed, failed
    # Pixel channel
    last_frame_at: float = 0
    frame_count: int = 0
    # Take control
    user_control: bool = False
    user_control_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_name": self.app_name,
            "backend_name": self.backend_name,
            "status": self.status,
            "pid": self.pid,
            "ram_allocated_mb": self.ram_allocated_mb,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "released_at": self.released_at,
            "current_action": self.current_action,
            "current_tool": self.current_tool,
            "current_object": self.current_object,
            "progress": self.progress,
            "verification_status": self.verification_status,
            "user_control": self.user_control,
            "uptime": time.time() - self.started_at if self.started_at else 0,
        }


@dataclass
class TimelineEvent:
    """An event in the application timeline."""
    timestamp: float
    event_type: str  # app_start, app_release, action, verification, error
    app_name: str
    description: str
    worker_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "app_name": self.app_name,
            "description": self.description,
            "worker_id": self.worker_id,
            "metadata": self.metadata,
        }


@dataclass
class MissionStepDetail:
    """Detailed view of a mission step for the inspector."""
    step_number: int
    action: str
    description: str
    status: str  # pending, running, completed, failed, awaiting_approval
    worker_id: str = ""
    app_name: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    sub_steps: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0
    screenshot_before: str = ""
    screenshot_after: str = ""
    verification: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "description": self.description,
            "status": self.status,
            "worker_id": self.worker_id,
            "app_name": self.app_name,
            "evidence": self.evidence,
            "sub_steps": self.sub_steps,
            "duration_ms": self.duration_ms,
            "screenshot_before": self.screenshot_before[:100] + "..." if self.screenshot_before else "",
            "screenshot_after": self.screenshot_after[:100] + "..." if self.screenshot_after else "",
            "verification": self.verification,
        }


class WorkspaceOrchestrator:
    """Manages the execution fabric — dynamic workers, resource lifecycle,
    application timeline, semantic activity, and user intervention.

    The agent never creates a permanent VM. It creates tiny workers on demand,
    streams their activity, and releases them when done.
    """

    def __init__(self):
        self._workers: Dict[str, WorkerSlot] = {}
        self._timeline: List[TimelineEvent] = []
        self._step_details: Dict[str, Dict[int, MissionStepDetail]] = {}
        self._lock = threading.Lock()
        self._max_workers = 8
        self._total_ram_budget_mb = 4096  # Default 4GB budget

    # ── Worker Lifecycle ────────────────────────────────────────────

    def create_worker(self, mission_id: str, app_name: str,
                      backend_hint: str = None,
                      requirements: TaskRequirements = None) -> WorkerSlot:
        """Create a new execution worker for an application."""
        worker_id = f"w_{mission_id}_{app_name}_{int(time.time())}"

        # Use broker to select backend if not hinted
        if not backend_hint:
            try:
                broker = get_workspace_broker()
                if requirements is None:
                    requirements = TaskRequirements.from_goal(app_name)
                decision = broker.select_backend(requirements)
                backend_name = decision.backend
            except Exception:
                backend_name = "native"
        else:
            backend_name = backend_hint

        # Check worker limit
        with self._lock:
            active = sum(1 for w in self._workers.values() if w.status == "running")
            if active >= self._max_workers:
                # Release oldest idle worker
                self._release_oldest_worker()

        worker = WorkerSlot(
            id=worker_id,
            app_name=app_name,
            backend_name=backend_name,
            status="creating",
            created_at=time.time(),
        )

        with self._lock:
            self._workers[worker_id] = worker

        # Record timeline event
        self._record_event(mission_id, "app_start", app_name,
                          f"Starting {app_name} in {backend_name}",
                          worker_id=worker_id)

        log.info(f"[ORCHESTRATOR] Created worker {worker_id} ({app_name} → {backend_name})")
        return worker

    def activate_worker(self, worker_id: str, pid: int = None,
                       ram_mb: float = 0) -> None:
        """Mark a worker as running."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.status = "running"
                w.pid = pid
                w.ram_allocated_mb = ram_mb
                w.started_at = time.time()

    def release_worker(self, worker_id: str, mission_id: str = "",
                       save_state: bool = True) -> None:
        """Release a worker and free its resources."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return
            w.status = "released"
            w.released_at = time.time()

        self._record_event(mission_id, "app_release", w.app_name,
                          f"Released {w.app_name} (saved={'yes' if save_state else 'no'})",
                          worker_id=worker_id)

        # Free the backend
        mgr = get_workspace_manager()
        for ws in mgr.list_workspaces():
            if ws.status == "running":
                mgr._backends.pop(ws.id, None)

        log.info(f"[ORCHESTRATOR] Released worker {worker_id} ({w.app_name})")

    def _release_oldest_worker(self) -> None:
        """Release the oldest running worker to free resources."""
        oldest = None
        oldest_time = float("inf")
        for w in self._workers.values():
            if w.status == "running" and not w.user_control:
                if w.started_at < oldest_time:
                    oldest_time = w.started_at
                    oldest = w
        if oldest:
            self.release_worker(oldest.id)

    def update_activity(self, worker_id: str, action: str = "",
                       tool: str = "", object_name: str = "",
                       progress: float = None) -> None:
        """Update the semantic activity channel for a worker."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                if action: w.current_action = action
                if tool: w.current_tool = tool
                if object_name: w.current_object = object_name
                if progress is not None: w.progress = progress

    def set_verification(self, worker_id: str, status: str) -> None:
        """Set verification status for a worker."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.verification_status = status

    # ── Take Control ────────────────────────────────────────────────

    def take_control(self, worker_id: str) -> dict:
        """User takes control of a live workspace."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return {"ok": False, "error": "Worker not found"}
            if w.status != "running":
                return {"ok": False, "error": "Worker not running"}
            w.user_control = True
            w.user_control_at = time.time()
        log.info(f"[ORCHESTRATOR] User took control of {worker_id}")
        return {"ok": True, "worker": w.to_dict()}

    def return_control(self, worker_id: str) -> dict:
        """User returns control to JARVIS."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return {"ok": False, "error": "Worker not found"}
            w.user_control = False
            w.user_control_at = 0
        log.info(f"[ORCHESTRATOR] User returned control of {worker_id}")
        return {"ok": True, "worker": w.to_dict()}

    # ── Application Timeline ────────────────────────────────────────

    def _record_event(self, mission_id: str, event_type: str,
                     app_name: str, description: str,
                     worker_id: str = "", metadata: dict = None) -> None:
        """Record a timeline event."""
        event = TimelineEvent(
            timestamp=time.time(),
            event_type=event_type,
            app_name=app_name,
            description=description,
            worker_id=worker_id,
            metadata=metadata or {},
        )
        with self._lock:
            self._timeline.append(event)
            # Keep last 500 events
            if len(self._timeline) > 500:
                self._timeline = self._timeline[-500:]

    def get_timeline(self, mission_id: str = None, count: int = 50) -> List[dict]:
        """Get recent timeline events."""
        with self._lock:
            events = self._timeline[-count:]
        return [e.to_dict() for e in events]

    def get_timeline_summary(self, mission_id: str = None) -> Dict[str, Any]:
        """Get a summary of which apps ran and for how long."""
        with self._lock:
            events = list(self._timeline)

        app_sessions = {}
        for e in events:
            if e.event_type == "app_start":
                app_sessions[e.app_name] = {"start": e.timestamp, "end": None}
            elif e.event_type == "app_release":
                if e.app_name in app_sessions:
                    app_sessions[e.app_name]["end"] = e.timestamp

        summary = []
        for app, session in app_sessions.items():
            duration = (session["end"] or time.time()) - session["start"]
            summary.append({
                "app": app,
                "start": session["start"],
                "end": session["end"],
                "duration_s": round(duration, 1),
            })

        return {
            "sessions": summary,
            "total_events": len(events),
            "apps_used": list(set(e.app_name for e in events)),
        }

    # ── Mission Inspector ───────────────────────────────────────────

    def record_step(self, mission_id: str, step: MissionStepDetail) -> None:
        """Record a detailed mission step for inspection."""
        with self._lock:
            if mission_id not in self._step_details:
                self._step_details[mission_id] = {}
            self._step_details[mission_id][step.step_number] = step

    def update_step(self, mission_id: str, step_number: int, **kwargs) -> None:
        """Update a mission step's details."""
        with self._lock:
            steps = self._step_details.get(mission_id, {})
            step = steps.get(step_number)
            if step:
                for k, v in kwargs.items():
                    if hasattr(step, k):
                        setattr(step, k, v)

    def get_step_details(self, mission_id: str, step_number: int = None) -> Any:
        """Get step details for inspection."""
        with self._lock:
            steps = self._step_details.get(mission_id, {})
        if step_number is not None:
            step = steps.get(step_number)
            return step.to_dict() if step else None
        return {num: s.to_dict() for num, s in steps.items()}

    # ── Compositor — Unified View ───────────────────────────────────

    def get_composite_view(self, mission_id: str) -> Dict[str, Any]:
        """Get the unified workspace view — what the user sees.

        Combines all workers, timeline, and semantic activity into one view.
        """
        with self._lock:
            workers = [w.to_dict() for w in self._workers.values()
                      if w.status in ("creating", "running")]
            all_workers = [w.to_dict() for w in self._workers.values()]

        timeline = self.get_timeline(mission_id, count=30)
        timeline_summary = self.get_timeline_summary(mission_id)
        step_details = self.get_step_details(mission_id)

        # Build the presentation layer
        windows = []
        for w in workers:
            windows.append({
                "id": w["id"],
                "title": w["app_name"],
                "status": w["status"],
                "backend": w["backend_name"],
                "activity": {
                    "action": w["current_action"],
                    "tool": w["current_tool"],
                    "object": w["current_object"],
                    "progress": w["progress"],
                    "verification": w["verification_status"],
                },
                "user_control": w["user_control"],
                "uptime": w["uptime"],
            })

        return {
            "mission_id": mission_id,
            "windows": windows,
            "active_workers": len(workers),
            "total_workers_created": len(all_workers),
            "timeline": timeline,
            "timeline_summary": timeline_summary,
            "step_details": step_details,
        }

    # ── Resource Stats ──────────────────────────────────────────────

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource usage across all workers."""
        with self._lock:
            workers = list(self._workers.values())

        active = [w for w in workers if w.status == "running"]
        total_ram = sum(w.ram_allocated_mb for w in active)

        return {
            "active_workers": len(active),
            "total_workers": len(workers),
            "total_ram_mb": round(total_ram, 1),
            "ram_budget_mb": self._total_ram_budget_mb,
            "ram_usage_pct": round(total_ram / self._total_ram_budget_mb * 100, 1),
            "user_controlled": sum(1 for w in active if w.user_control),
        }


# ── Singleton ────────────────────────────────────────────────────
_orchestrator: Optional[WorkspaceOrchestrator] = None


def get_workspace_orchestrator() -> WorkspaceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkspaceOrchestrator()
    return _orchestrator
