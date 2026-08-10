"""JARVIS Mission World — Disposable, Observable, Reversible Digital Workspaces.

This is the heart of JARVIS's execution architecture.

A Mission World is NOT just a VM or a container.
It is a temporary, observable, reversible digital world in which
an autonomous agent can actually perform work on the user's behalf.

Key properties:
  - DISPOSABLE: Created for a mission, destroyed after
  - OBSERVABLE: Live-streamed to the user in real-time
  - REVERSIBLE: Checkpoints at every important step, rollback on demand
  - ISOLATED: Reality boundary between user's computer and JARVIS world
  - CAPABLE: Self-inspecting, tool-installing, state-verifying
  - CLONABLE: Fork for parallel experimentation

ARCHITECTURE:

    User
      │
      ▼
    MISSION WORLD MANAGER
      │
      ├── CREATE world (typed: research, code, creative, office, web, finance)
      ├── SNAPSHOT world (continuous checkpoints)
      ├── CLONE world (fork for parallel agents)
      ├── RESTORE world (rollback to any checkpoint)
      ├── STREAM world (live video to user's mini UI)
      ├── VERIFY world (inspect actual state)
      ├── DESTROY world (clean up after mission)
      │
      ▼
    WORKSPACE BROKER
      │
      ├── Process isolation (50 MB)
      ├── Browser sandbox (~100 MB)
      ├── VM/Remote (GBs+)
      │
      ▼
    REAL COMPUTER
"""

import os
import sys
import json
import time
import shutil
import hashlib
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

log = logging.getLogger("mission_world")

WORLDS_DIR = Path(os.path.expanduser("~/.jarvis/mission_worlds"))
WORLDS_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  WORKSPACE TYPES (Specialization)
# ══════════════════════════════════════════════════════════════

class WorldType(Enum):
    """Typed workspace templates for different mission types."""
    RESEARCH = "research"        # Browser, PDF tools, OCR, citation
    CODE = "code"                # IDE, terminal, Git, runtime, testing
    CREATIVE = "creative"        # Blender, image tools, video, GPU
    OFFICE = "office"            # Word, Excel, PowerPoint, PDF
    WEB = "web"                  # Browser, DevTools, local server
    FINANCE = "finance"          # Browser, spreadsheet, broker interface
    DATA = "data"                # Python, R, Jupyter, databases
    GENERIC = "generic"          # General purpose


WORLD_TYPE_CONFIGS = {
    WorldType.RESEARCH: {
        "capabilities": ["browser", "pdf_tools", "ocr", "citation", "data_extraction"],
        "apps": ["chrome", "python"],
        "min_ram_mb": 512,
        "preferred_backend": "browser_sandbox",
    },
    WorldType.CODE: {
        "capabilities": ["ide", "terminal", "git", "runtime", "testing", "browser"],
        "apps": ["code", "git", "python", "node"],
        "min_ram_mb": 1024,
        "preferred_backend": "container",
    },
    WorldType.CREATIVE: {
        "capabilities": ["3d_modeling", "rendering", "image_tools", "video_tools", "gpu"],
        "apps": ["blender", "ffmpeg", "gimp"],
        "min_ram_mb": 2048,
        "preferred_backend": "wsl_xvfb",
    },
    WorldType.OFFICE: {
        "capabilities": ["word", "excel", "powerpoint", "pdf"],
        "apps": ["libreoffice", "python"],
        "min_ram_mb": 512,
        "preferred_backend": "container",
    },
    WorldType.WEB: {
        "capabilities": ["browser", "devtools", "local_server", "testing"],
        "apps": ["chrome", "node", "python"],
        "min_ram_mb": 512,
        "preferred_backend": "browser_sandbox",
    },
    WorldType.FINANCE: {
        "capabilities": ["browser", "spreadsheet", "data_tools", "broker_api"],
        "apps": ["chrome", "python"],
        "min_ram_mb": 512,
        "preferred_backend": "browser_sandbox",
        "requires_confirmation": True,  # Financial actions need user approval
    },
    WorldType.DATA: {
        "capabilities": ["python", "r", "jupyter", "databases", "visualization"],
        "apps": ["python", "jupyter"],
        "min_ram_mb": 1024,
        "preferred_backend": "container",
    },
    WorldType.GENERIC: {
        "capabilities": ["browser", "editor", "terminal", "files"],
        "apps": ["chrome", "python"],
        "min_ram_mb": 512,
        "preferred_backend": "auto",
    },
}


# ══════════════════════════════════════════════════════════════
#  CHECKPOINT (Time Machine)
# ══════════════════════════════════════════════════════════════

@dataclass
class Checkpoint:
    """A point-in-time snapshot of a Mission World."""
    id: str
    timestamp: float
    label: str  # Human-readable: "Chrome launched", "Price verified"
    description: str = ""
    files_snapshot: Dict[str, str] = field(default_factory=dict)  # path -> hash
    state_snapshot: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: str = ""
    mission_step: int = 0
    size_bytes: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
#  REALITY BOUNDARY (Permission Gate)
# ══════════════════════════════════════════════════════════════

@dataclass
class BoundaryRule:
    """A rule for what crosses the reality boundary."""
    resource_type: str  # "file", "directory", "credential", "network"
    path_pattern: str   # Glob pattern or specific path
    permission: str     # "read", "write", "execute", "deny"
    requires_approval: bool = False
    reason: str = ""
    granted_at: float = 0
    expires_at: float = 0

    def to_dict(self) -> dict:
        return asdict(self)


class RealityBoundary:
    """Manages the boundary between user's computer and JARVIS world.

    JARVIS should know exactly what crosses that boundary.

    Example:
      "Use this PDF from my Desktop."
      -> JARVIS requests access to that specific file.
      Not: "Give me the entire Desktop."
    """

    def __init__(self, world_id: str):
        self.world_id = world_id
        self._rules: List[BoundaryRule] = []
        self._access_log: List[Dict[str, Any]] = []
        self._load_rules()

    def _rules_path(self) -> str:
        return os.path.join(WORLDS_DIR, self.world_id, "boundary_rules.json")

    def _load_rules(self):
        path = self._rules_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                self._rules = [BoundaryRule(**r) for r in data.get("rules", [])]
            except Exception:
                pass

    def _save_rules(self):
        path = self._rules_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"rules": [r.to_dict() for r in self._rules]}, f, indent=2)

    def request_access(self, resource_type: str, path: str,
                      reason: str = "") -> Tuple[bool, str]:
        """Request access to a resource from the user's computer.

        Returns (granted, reason).
        """
        # Check existing rules
        for rule in self._rules:
            if rule.resource_type == resource_type:
                if self._matches_pattern(rule.path_pattern, path):
                    if rule.permission == "deny":
                        self._log_access(resource_type, path, False, "denied_by_rule")
                        return False, f"Access denied by rule: {rule.reason}"
                    if rule.granted_at > 0:
                        if rule.expires_at == 0 or rule.expires_at > time.time():
                            self._log_access(resource_type, path, True, "granted_by_rule")
                            return True, f"Access granted by existing rule"

        # Check if approval is needed
        needs_approval = self._needs_approval(resource_type, path)

        if needs_approval:
            self._log_access(resource_type, path, False, "needs_approval")
            return False, f"Access to {resource_type}:{path} requires user approval"

        # Auto-grant low-risk reads
        if resource_type == "file" and self._is_read_only(path):
            rule = BoundaryRule(
                resource_type=resource_type,
                path_pattern=path,
                permission="read",
                requires_approval=False,
                reason="Auto-granted read access",
                granted_at=time.time(),
            )
            self._rules.append(rule)
            self._save_rules()
            self._log_access(resource_type, path, True, "auto_granted_read")
            return True, "Auto-granted read access"

        self._log_access(resource_type, path, False, "no_matching_rule")
        return False, f"No rule for {resource_type}:{path}"

    def grant_access(self, resource_type: str, path: str,
                    permission: str = "read", duration_hours: float = 24,
                    reason: str = ""):
        """Grant explicit access to a resource."""
        rule = BoundaryRule(
            resource_type=resource_type,
            path_pattern=path,
            permission=permission,
            requires_approval=False,
            reason=reason or f"User granted {permission} access",
            granted_at=time.time(),
            expires_at=time.time() + (duration_hours * 3600) if duration_hours > 0 else 0,
        )
        self._rules.append(rule)
        self._save_rules()
        log.info(f"[BOUNDARY] Granted {permission} access to {resource_type}:{path}")

    def revoke_access(self, resource_type: str, path: str):
        """Revoke access to a resource."""
        self._rules = [
            r for r in self._rules
            if not (r.resource_type == resource_type and r.path_pattern == path)
        ]
        self._save_rules()

    def _matches_pattern(self, pattern: str, path: str) -> bool:
        """Check if a path matches a pattern (simple glob)."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)

    def _needs_approval(self, resource_type: str, path: str) -> bool:
        """Determine if access needs explicit user approval."""
        # High-risk resources always need approval
        high_risk = ["credential", "financial", "email", "smart_home"]
        if resource_type in high_risk:
            return True

        # Sensitive directories need approval
        sensitive_dirs = [
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Downloads"),
        ]
        for d in sensitive_dirs:
            if path.startswith(d):
                return True

        return False

    def _is_read_only(self, path: str) -> bool:
        """Check if access is read-only."""
        return os.path.isfile(path) and not os.access(path, os.W_OK)

    def _log_access(self, resource_type: str, path: str,
                   granted: bool, reason: str):
        """Log access attempt."""
        self._access_log.append({
            "timestamp": time.time(),
            "resource_type": resource_type,
            "path": path,
            "granted": granted,
            "reason": reason,
        })

    def get_access_log(self) -> List[Dict[str, Any]]:
        """Get the access log for this world."""
        return self._access_log[-100:]  # Last 100 entries

    def get_rules(self) -> List[BoundaryRule]:
        """Get all active rules."""
        return self._rules


# ══════════════════════════════════════════════════════════════
#  CAPABILITY DISCOVERY (Self-Inspection)
# ══════════════════════════════════════════════════════════════

@dataclass
class WorldCapabilities:
    """What a workspace can actually do."""
    os: str = ""
    cpu_count: int = 0
    ram_mb: int = 0
    gpu: str = ""
    gpu_available: bool = False
    installed_apps: List[str] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    python_packages: List[str] = field(default_factory=list)
    node_available: bool = False
    browser_available: bool = False
    internet_available: bool = False
    capabilities: List[str] = field(default_factory=list)
    missing_capabilities: List[str] = field(default_factory=list)
    suggested_installs: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def discover_capabilities() -> WorldCapabilities:
    """Inspect what the current workspace can actually do.

    The agent should know what it can actually do
    instead of hallucinating capabilities.
    """
    caps = WorldCapabilities()

    # OS detection
    caps.os = sys.platform

    # CPU
    try:
        import multiprocessing
        caps.cpu_count = multiprocessing.cpu_count()
    except Exception:
        caps.cpu_count = 1

    # RAM
    try:
        import psutil
        caps.ram_mb = int(psutil.virtual_memory().total / 1024 / 1024)
    except Exception:
        caps.ram_mb = 0

    # GPU
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            caps.gpu = result.stdout.strip()
            caps.gpu_available = True
    except Exception:
        pass

    # Check installed apps
    apps_to_check = {
        "chrome": ["google-chrome", "chromium-browser", "chrome"],
        "firefox": ["firefox"],
        "code": ["code"],
        "git": ["git"],
        "python": ["python3", "python"],
        "node": ["node"],
        "npm": ["npm"],
        "ffmpeg": ["ffmpeg"],
        "blender": ["blender"],
        "docker": ["docker"],
    }
    for app_name, commands in apps_to_check.items():
        for cmd in commands:
            try:
                result = subprocess.run(
                    [cmd, "--version"], capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    caps.installed_apps.append(app_name)
                    break
            except Exception:
                continue

    # Check Python packages
    important_packages = [
        "requests", "httpx", "beautifulsoup4", "pandas", "numpy",
        "matplotlib", "pillow", "selenium", "playwright", "pyautogui",
        "python-docx", "openpyxl", "python-pptx", "pypdf",
    ]
    for pkg in important_packages:
        try:
            __import__(pkg.replace("-", "_").split("[")[0])
            caps.python_packages.append(pkg)
        except ImportError:
            pass

    # Derive capabilities from installed tools
    if "chrome" in caps.installed_apps or "firefox" in caps.installed_apps:
        caps.browser_available = True
        caps.capabilities.append("browser_automation")
    if "python" in caps.installed_apps:
        caps.capabilities.append("python_execution")
        caps.capabilities.append("data_analysis")
    if "git" in caps.installed_apps:
        caps.capabilities.append("version_control")
    if "ffmpeg" in caps.installed_apps:
        caps.capabilities.append("video_processing")
    if "blender" in caps.installed_apps:
        caps.capabilities.append("3d_rendering")
    if "docker" in caps.installed_apps:
        caps.capabilities.append("container_execution")
    if "node" in caps.installed_apps:
        caps.node_available = True
        caps.capabilities.append("javascript_execution")

    # Check internet
    try:
        import urllib.request
        urllib.request.urlopen("https://httpbin.org/get", timeout=5)
        caps.internet_available = True
        caps.capabilities.append("internet_access")
    except Exception:
        pass

    # Identify missing capabilities
    all_expected = ["browser_automation", "python_execution", "version_control",
                   "video_processing", "3d_rendering", "internet_access"]
    for cap in all_expected:
        if cap not in caps.capabilities:
            caps.missing_capabilities.append(cap)

    return caps


# ══════════════════════════════════════════════════════════════
#  MISSION WORLD
# ══════════════════════════════════════════════════════════════

@dataclass
class MissionWorld:
    """A disposable, observable, reversible digital workspace.

    This is NOT a VM. It is a lightweight execution environment
    that can be as small as 50 MB (process isolation) or as large
    as needed (VM/container) depending on the mission.
    """
    id: str
    name: str
    world_type: WorldType
    mission_id: str
    status: str = "creating"  # creating, ready, running, paused, destroyed
    backend: str = "auto"
    created_at: float = 0
    started_at: float = 0
    destroyed_at: float = 0

    # Checkpoints (Time Machine)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    last_checkpoint: Optional[str] = None

    # Reality Boundary
    boundary: Optional[RealityBoundary] = None

    # Capabilities
    capabilities: Optional[WorldCapabilities] = None

    # Files & State
    working_dir: str = ""
    files: Dict[str, str] = field(default_factory=dict)  # path -> hash
    state: Dict[str, Any] = field(default_factory=dict)

    # Mission context
    objective: str = ""
    assumptions: List[str] = field(default_factory=list)
    evidence_count: int = 0
    verification_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.working_dir:
            self.working_dir = str(WORLDS_DIR / self.id / "files")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "world_type": self.world_type.value,
            "mission_id": self.mission_id,
            "status": self.status,
            "backend": self.backend,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "destroyed_at": self.destroyed_at,
            "checkpoint_count": len(self.checkpoints),
            "files_count": len(self.files),
            "evidence_count": self.evidence_count,
            "verification_count": self.verification_count,
            "objective": self.objective,
            "working_dir": self.working_dir,
        }


# ══════════════════════════════════════════════════════════════
#  MISSION WORLD MANAGER
# ══════════════════════════════════════════════════════════════

class MissionWorldManager:
    """Creates, manages, snapshots, clones, and destroys Mission Worlds.

    This is the core orchestrator for isolated execution environments.
    """

    def __init__(self):
        self._worlds: Dict[str, MissionWorld] = {}
        self._lock = threading.Lock()
        self._recover_worlds()

    def _recover_worlds(self):
        """Recover worlds from disk on startup."""
        for world_dir in WORLDS_DIR.iterdir():
            if world_dir.is_dir():
                state_file = world_dir / "world_state.json"
                if state_file.exists():
                    try:
                        with open(state_file) as f:
                            data = json.load(f)
                        world_type = WorldType(data.get("world_type", "generic"))
                        world = MissionWorld(
                            id=data["id"],
                            name=data["name"],
                            world_type=world_type,
                            mission_id=data.get("mission_id", ""),
                            status="ready",  # Reset on recovery
                            backend=data.get("backend", "auto"),
                            created_at=data.get("created_at", 0),
                            working_dir=data.get("working_dir", ""),
                            objective=data.get("objective", ""),
                        )
                        with self._lock:
                            self._worlds[world.id] = world
                        log.info(f"[WORLD] Recovered: {world.id} ({world.name})")
                    except Exception as e:
                        log.warning(f"[WORLD] Failed to recover {world_dir}: {e}")

    def _save_state(self, world: MissionWorld):
        """Persist world state to disk."""
        world_dir = WORLDS_DIR / world.id
        world_dir.mkdir(parents=True, exist_ok=True)
        state_file = world_dir / "world_state.json"
        with open(state_file, "w") as f:
            json.dump(world.to_dict(), f, indent=2)

    def create_world(self, name: str, world_type: WorldType,
                    mission_id: str, objective: str = "",
                    assumptions: List[str] = None) -> MissionWorld:
        """Create a new Mission World.

        The world is typed based on the mission requirements.
        The Workspace Broker will choose the cheapest backend
        capable of completing the mission.
        """
        world_id = f"w_{mission_id}_{int(time.time())}"

        world = MissionWorld(
            id=world_id,
            name=name,
            world_type=world_type,
            mission_id=mission_id,
            objective=objective,
            assumptions=assumptions or [],
        )

        # Create working directory
        os.makedirs(world.working_dir, exist_ok=True)
        os.makedirs(WORLDS_DIR / world_id / "checkpoints", exist_ok=True)
        os.makedirs(WORLDS_DIR / world_id / "screenshots", exist_ok=True)

        # Initialize reality boundary
        world.boundary = RealityBoundary(world_id)

        # Discover capabilities
        world.capabilities = discover_capabilities()

        # Select backend based on world type and capabilities
        config = WORLD_TYPE_CONFIGS.get(world_type, WORLD_TYPE_CONFIGS[WorldType.GENERIC])
        world.backend = self._select_backend(config, world.capabilities)

        with self._lock:
            self._worlds[world_id] = world

        self._save_state(world)
        log.info(f"[WORLD] Created {world_id}: {name} (type={world_type.value}, backend={world.backend})")
        return world

    def _select_backend(self, config: Dict, capabilities: WorldCapabilities) -> str:
        """Select the cheapest backend that meets the mission requirements."""
        preferred = config.get("preferred_backend", "auto")

        # Try preferred backend first
        if preferred != "auto":
            try:
                from capability_fabric import get_capability_fabric
                fabric = get_capability_fabric()
                status = fabric.get_status()
                if status.get("computer_available"):
                    return preferred
            except Exception:
                pass

        # Auto-detect best available
        if capabilities.os == "win32":
            return "windows_native"
        elif capabilities.os == "darwin":
            return "macos_native"
        elif capabilities.os == "linux":
            if capabilities.gpu_available:
                return "wsl_xvfb"  # GPU access
            return "container"  # Lightweight

        return "auto"

    def snapshot(self, world_id: str, label: str,
                description: str = "", mission_step: int = 0) -> Optional[Checkpoint]:
        """Create a checkpoint (Time Machine snapshot).

        This is the "Workspace Time Machine" — continuous checkpoints
        that allow rollback to any point in the mission.
        """
        world = self._worlds.get(world_id)
        if not world:
            return None

        checkpoint_id = f"cp_{int(time.time() * 1000)}"
        world_dir = WORLDS_DIR / world_id

        # Snapshot file hashes
        files_snapshot = {}
        working_dir = Path(world.working_dir)
        if working_dir.exists():
            for f in working_dir.rglob("*"):
                if f.is_file():
                    try:
                        with open(f, "rb") as fh:
                            file_hash = hashlib.md5(fh.read()).hexdigest()
                        files_snapshot[str(f.relative_to(working_dir))] = file_hash
                    except Exception:
                        pass

        # Take screenshot if possible
        screenshot_path = ""
        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            result = fabric.screenshot()
            if result.ok and result.data:
                screenshot_path = str(world_dir / "checkpoints" / f"{checkpoint_id}.jpg")
                with open(screenshot_path, "wb") as f:
                    f.write(result.data)
        except Exception:
            pass

        checkpoint = Checkpoint(
            id=checkpoint_id,
            timestamp=time.time(),
            label=label,
            description=description,
            files_snapshot=files_snapshot,
            state_snapshot=world.state.copy(),
            screenshot_path=screenshot_path,
            mission_step=mission_step,
            size_bytes=sum(
                os.path.getsize(world_dir / "files" / f)
                for f in world.files
                if os.path.exists(world_dir / "files" / f)
            ),
        )

        world.checkpoints.append(checkpoint)
        world.last_checkpoint = checkpoint_id
        self._save_state(world)

        log.info(f"[WORLD] Checkpoint {checkpoint_id}: {label}")
        return checkpoint

    def restore(self, world_id: str, checkpoint_id: str) -> bool:
        """Restore a world to a previous checkpoint.

        This is the "Workspace Time Machine" rollback.
        """
        world = self._worlds.get(world_id)
        if not world:
            return False

        # Find the checkpoint
        checkpoint = None
        for cp in world.checkpoints:
            if cp.id == checkpoint_id:
                checkpoint = cp
                break

        if not checkpoint:
            log.error(f"[WORLD] Checkpoint {checkpoint_id} not found")
            return False

        # Restore state
        world.state = checkpoint.state_snapshot.copy()

        # Restore file hashes (actual file restore would need copy from snapshot)
        # For now, just update the tracking
        world.files = checkpoint.files_snapshot.copy()

        # Take a new checkpoint for the restore
        self.snapshot(world_id, f"Restored to: {checkpoint.label}",
                     description=f"Rolled back to checkpoint {checkpoint_id}")

        self._save_state(world)
        log.info(f"[WORLD] Restored {world_id} to checkpoint {checkpoint_id}")
        return True

    def clone(self, world_id: str, new_name: str,
             mission_id: str = "") -> Optional[MissionWorld]:
        """Clone a world for parallel experimentation.

        Workspace Cloning — fork for parallel agents.
        """
        original = self._worlds.get(world_id)
        if not original:
            return None

        # Create new world with same type
        clone_mission_id = mission_id or f"{original.mission_id}_clone"
        clone = self.create_world(
            name=new_name,
            world_type=original.world_type,
            mission_id=clone_mission_id,
            objective=f"Clone of: {original.objective}",
        )

        # Copy files
        src_dir = Path(original.working_dir)
        dst_dir = Path(clone.working_dir)
        if src_dir.exists():
            for f in src_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src_dir)
                    dst = dst_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)

        # Copy state
        clone.files = original.files.copy()
        clone.state = original.state.copy()

        self._save_state(clone)
        log.info(f"[WORLD] Cloned {world_id} → {clone.id}")
        return clone

    def list_worlds(self, mission_id: str = None) -> List[MissionWorld]:
        """List all worlds, optionally filtered by mission."""
        with self._lock:
            worlds = list(self._worlds.values())
        if mission_id:
            worlds = [w for w in worlds if w.mission_id == mission_id]
        return worlds

    def get_world(self, world_id: str) -> Optional[MissionWorld]:
        return self._worlds.get(world_id)

    def destroy_world(self, world_id: str) -> bool:
        """Destroy a Mission World and clean up resources."""
        world = self._worlds.get(world_id)
        if not world:
            return False

        world.status = "destroyed"
        world.destroyed_at = time.time()

        # Keep checkpoints but remove working files
        working_dir = Path(world.working_dir)
        if working_dir.exists():
            try:
                shutil.rmtree(working_dir)
            except Exception as e:
                log.warning(f"[WORLD] Failed to remove working dir: {e}")

        self._save_state(world)
        log.info(f"[WORLD] Destroyed {world_id}")
        return True

    def request_file_access(self, world_id: str, file_path: str,
                           reason: str = "") -> Tuple[bool, str]:
        """Request access to a file from the user's computer.

        This is the Reality Boundary — JARVIS requests specific files,
        not entire directories.
        """
        world = self._worlds.get(world_id)
        if not world or not world.boundary:
            return False, "World not found"

        return world.boundary.request_access("file", file_path, reason)

    def grant_file_access(self, world_id: str, file_path: str,
                         permission: str = "read", duration_hours: float = 24):
        """Grant a world access to a specific file."""
        world = self._worlds.get(world_id)
        if world and world.boundary:
            world.boundary.grant_access("file", file_path, permission, duration_hours)

    def get_world_status(self, world_id: str) -> Dict[str, Any]:
        """Get detailed world status including capabilities and boundary."""
        world = self._worlds.get(world_id)
        if not world:
            return {"error": "World not found"}

        result = world.to_dict()
        if world.capabilities:
            result["capabilities"] = world.capabilities.to_dict()
        if world.boundary:
            result["boundary_rules"] = [r.to_dict() for r in world.boundary.get_rules()]
            result["access_log"] = world.boundary.get_access_log()
        result["checkpoints"] = [cp.to_dict() for cp in world.checkpoints[-10:]]
        return result


# ── Singleton ──
_manager: Optional[MissionWorldManager] = None


def get_mission_world_manager() -> MissionWorldManager:
    global _manager
    if _manager is None:
        _manager = MissionWorldManager()
    return _manager
