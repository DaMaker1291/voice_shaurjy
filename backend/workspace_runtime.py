"""JARVIS Workspace Runtime — Abstraction layer for multiple workspace backends.

Supports:
- VM (Hyper-V on Windows, QEMU/KVM on Linux, Virtualization.framework on macOS)
- Local (hidden desktop on current OS — fallback for dev/testing)
- Container (Docker/Podman — lightweight option)
- Cloud (future: remote VM instances)

Each backend provides:
- create() / start() / stop() / destroy()
- capture_frame() -> bytes
- inject_input() -> None
- get_apps() -> list
- snapshot() / restore() -> str
"""

from __future__ import annotations

import os
import json
import time
import uuid
import shutil
import logging
import platform
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum

log = logging.getLogger("workspace_runtime")

WORKSPACE_BASE = Path.home() / ".jarvis" / "workspaces"
WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)


class RuntimeType(Enum):
    VM = "vm"
    LOCAL = "local"
    CONTAINER = "container"
    CLOUD = "cloud"


class WorkspaceState(Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DESTROYED = "destroyed"


@dataclass
class WorkspaceConfig:
    name: str = "JARVIS Workspace"
    runtime_type: RuntimeType = RuntimeType.LOCAL
    resolution: tuple = (1920, 1080)
    memory_mb: int = 4096
    cpu_cores: int = 2
    enable_gpu: bool = False
    vm_image: Optional[str] = None
    vm_disk_gb: int = 50
    capabilities: List[str] = field(default_factory=lambda: ["browser", "editor", "files", "terminal"])
    mount_paths: Dict[str, str] = field(default_factory=dict)
    provision_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkspaceStatus:
    id: str
    name: str
    runtime_type: str
    state: str
    resolution: tuple
    display_id: Any
    memory_mb: int
    cpu_cores: int
    apps: List[Dict] = field(default_factory=list)
    snapshots: List[str] = field(default_factory=list)
    current_action: str = ""
    agent_status: str = "idle"
    uptime: float = 0
    error: str = ""
    created_at: float = 0
    started_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "runtime_type": self.runtime_type,
            "state": self.state, "resolution": list(self.resolution),
            "display_id": self.display_id, "memory_mb": self.memory_mb,
            "cpu_cores": self.cpu_cores, "apps": self.apps, "snapshots": self.snapshots,
            "current_action": self.current_action, "agent_status": self.agent_status,
            "uptime": self.uptime, "error": self.error,
            "created_at": self.created_at, "started_at": self.started_at,
        }


class WorkspaceBackend(ABC):
    """Abstract base for workspace execution backends."""

    @abstractmethod
    def create(self, config: WorkspaceConfig) -> WorkspaceStatus:
        ...

    @abstractmethod
    def start(self, workspace_id: str) -> dict:
        ...

    @abstractmethod
    def stop(self, workspace_id: str) -> dict:
        ...

    @abstractmethod
    def destroy(self, workspace_id: str) -> dict:
        ...

    @abstractmethod
    def capture_frame(self, workspace_id: str, quality: int = 60) -> Optional[bytes]:
        ...

    @abstractmethod
    def inject_click(self, workspace_id: str, x: int, y: int, button: int = 1) -> dict:
        ...

    @abstractmethod
    def inject_key(self, workspace_id: str, key: str) -> dict:
        ...

    @abstractmethod
    def inject_text(self, workspace_id: str, text: str) -> dict:
        ...

    @abstractmethod
    def launch_app(self, workspace_id: str, app_name: str, command: List[str] = None) -> dict:
        ...

    @abstractmethod
    def get_apps(self, workspace_id: str) -> List[dict]:
        ...

    @abstractmethod
    def create_snapshot(self, workspace_id: str, name: str) -> dict:
        ...

    @abstractmethod
    def restore_snapshot(self, workspace_id: str, snapshot_id: str) -> dict:
        ...

    @abstractmethod
    def list_snapshots(self, workspace_id: str) -> List[dict]:
        ...

    @abstractmethod
    def get_stream_url(self, workspace_id: str) -> Optional[str]:
        """Return WebRTC/LiveKit stream URL if available."""
        ...


class LocalDesktopBackend(WorkspaceBackend):
    """Fallback backend using hidden desktop on current OS (dev/testing)."""

    def __init__(self):
        self._workspaces: Dict[str, dict] = {}

    def create(self, config: WorkspaceConfig) -> WorkspaceStatus:
        ws_id = str(uuid.uuid4())[:8]
        ws_dir = WORKSPACE_BASE / ws_id
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "files").mkdir(exist_ok=True)
        status = WorkspaceStatus(
            id=ws_id, name=config.name, runtime_type=RuntimeType.LOCAL.value,
            state=WorkspaceState.CREATED.value, resolution=config.resolution,
            display_id=0, memory_mb=0, cpu_cores=0,
            created_at=time.time(),
        )
        self._save_status(ws_id, status)
        log.info(f"[LOCAL] Created workspace {ws_id}")
        return status

    def start(self, workspace_id: str) -> dict:
        ws_dir = WORKSPACE_BASE / workspace_id
        if not ws_dir.exists():
            return {"ok": False, "error": "Workspace not found"}
        status = self._load_status(workspace_id)
        if platform.system() == "Windows":
            status = self._start_windows(status)
        else:
            status = self._start_linux(status)
        self._save_status(workspace_id, status)
        return {"ok": True, "workspace": status.to_dict()}

    def _start_windows(self, status: WorkspaceStatus) -> WorkspaceStatus:
        try:
            import ctypes
            desktop_name = f"JARVIS_{status.id}"
            h_desktop = ctypes.windll.user32.CreateDesktopW(
                desktop_name, None, None, 0, 0x001F, None
            )
            if h_desktop:
                status.display_id = desktop_name
                log.info(f"[LOCAL] Created hidden desktop: {desktop_name}")
        except Exception as e:
            log.warning(f"[LOCAL] Desktop creation failed: {e}")
        status.state = WorkspaceState.RUNNING.value
        status.started_at = time.time()
        return status

    def _start_linux(self, status: WorkspaceStatus) -> WorkspaceStatus:
        try:
            display_id = self._find_free_display()
            w, h = status.resolution
            cmd = f"Xvfb :{display_id} -screen 0 {w}x{h}x24 -ac +extension GLX +render -noreset"
            proc = subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            ws_dir = WORKSPACE_BASE / status.id / "env"
            ws_dir.mkdir(exist_ok=True)
            (ws_dir / "xvfb.pid").write_text(str(proc.pid))
            status.display_id = display_id
            log.info(f"[LOCAL] Started Xvfb on :{display_id}")
        except Exception as e:
            log.warning(f"[LOCAL] Xvfb start failed: {e}")
        status.state = WorkspaceState.RUNNING.value
        status.started_at = time.time()
        return status

    def _find_free_display(self) -> int:
        used = set()
        for ws_dir in WORKSPACE_BASE.iterdir():
            if ws_dir.is_dir():
                df = ws_dir / "display_id"
                if df.exists():
                    try:
                        used.add(int(df.read_text().strip()))
                    except ValueError:
                        pass
        for d in range(100, 200):
            if d not in used:
                return d
        return 100

    def stop(self, workspace_id: str) -> dict:
        status = self._load_status(workspace_id)
        ws_dir = WORKSPACE_BASE / workspace_id
        env_dir = ws_dir / "env"
        xvfb_pid = env_dir / "xvfb.pid"
        if xvfb_pid.exists():
            try:
                pid = int(xvfb_pid.read_text().strip())
                os.kill(pid, 9)
            except Exception:
                pass
        status.state = WorkspaceState.STOPPED.value
        status.started_at = 0
        self._save_status(workspace_id, status)
        return {"ok": True}

    def destroy(self, workspace_id: str) -> dict:
        self.stop(workspace_id)
        ws_dir = WORKSPACE_BASE / workspace_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir, ignore_errors=True)
        return {"ok": True}

    def capture_frame(self, workspace_id: str, quality: int = 60) -> Optional[bytes]:
        import io
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                return buf.getvalue()
        except Exception:
            pass
        return None

    def inject_click(self, workspace_id: str, x: int, y: int, button: int = 1) -> dict:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            abs_x = int(x * 65535 / screen_w)
            abs_y = int(y * 65535 / screen_h)
            user32.SetCursorPos(x, y)
            if button == 1:
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def inject_key(self, workspace_id: str, key: str) -> dict:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            VK_MAP = {
                "Return": 0x0D, "Tab": 0x09, "Escape": 0x1B, "space": 0x20,
                "BackSpace": 0x08, "Delete": 0x2E, "Up": 0x26, "Down": 0x28,
                "Left": 0x25, "Right": 0x27, "Home": 0x24, "End": 0x23,
            }
            vk = VK_MAP.get(key)
            if vk:
                user32.keybd_event(vk, 0, 0, 0)
                user32.keybd_event(vk, 0, 2, 0)
                return {"ok": True}
            for ch in key:
                vk_char = user32.VkKeyScanW(ord(ch)) & 0xFF
                user32.keybd_event(vk_char, 0, 0, 0)
                user32.keybd_event(vk_char, 0, 2, 0)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def inject_text(self, workspace_id: str, text: str) -> dict:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            for ch in text:
                vk_scan = user32.VkKeyScanW(ord(ch))
                vk = vk_scan & 0xFF
                shift = (vk_scan >> 8) & 0xFF
                if shift & 1:
                    user32.keybd_event(0x10, 0, 0, 0)
                user32.keybd_event(vk, 0, 0, 0)
                user32.keybd_event(vk, 0, 2, 0)
                if shift & 1:
                    user32.keybd_event(0x10, 0, 2, 0)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def launch_app(self, workspace_id: str, app_name: str, command: List[str] = None) -> dict:
        cmd = command or [app_name]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            status = self._load_status(workspace_id)
            status.apps.append({"name": app_name, "pid": proc.pid, "status": "running"})
            self._save_status(workspace_id, status)
            return {"ok": True, "pid": proc.pid}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_apps(self, workspace_id: str) -> List[dict]:
        status = self._load_status(workspace_id)
        return status.apps

    def create_snapshot(self, workspace_id: str, name: str) -> dict:
        return {"ok": True, "snapshot_id": f"snap_{int(time.time())}", "name": name}

    def restore_snapshot(self, workspace_id: str, snapshot_id: str) -> dict:
        return {"ok": True}

    def list_snapshots(self, workspace_id: str) -> List[dict]:
        return []

    def get_stream_url(self, workspace_id: str) -> Optional[str]:
        return None

    def _save_status(self, workspace_id: str, status: WorkspaceStatus):
        ws_dir = WORKSPACE_BASE / workspace_id
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "status.json").write_text(json.dumps(status.to_dict(), indent=2))

    def _load_status(self, workspace_id: str) -> WorkspaceStatus:
        ws_dir = WORKSPACE_BASE / workspace_id
        path = ws_dir / "status.json"
        if path.exists():
            data = json.loads(path.read_text())
            return WorkspaceStatus(**{k: v for k, v in data.items() if k in WorkspaceStatus.__dataclass_fields__})
        return WorkspaceStatus(
            id=workspace_id, name="Unknown", runtime_type=RuntimeType.LOCAL.value,
            state=WorkspaceState.CREATED.value, resolution=(1920, 1080),
            display_id=0, memory_mb=0, cpu_cores=0,
        )


class VMBackend(WorkspaceBackend):
    """VM-based workspace using Hyper-V (Windows) or QEMU/KVM (Linux)."""

    def __init__(self):
        self._vms: Dict[str, dict] = {}
        self._detect_platform()

    def _detect_platform(self):
        self._os = platform.system()
        self._hypervisor = None
        if self._os == "Windows":
            self._detect_hyperv()
        elif self._os == "Linux":
            self._detect_qemu()
        elif self._os == "Darwin":
            self._detect_macos()

    def _detect_hyperv(self):
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-WindowsOptionalFeature -FeatureName Microsoft-Hyper-V-All -Online | Select-Object -ExpandProperty State"],
                capture_output=True, text=True, timeout=10
            )
            if "Enabled" in result.stdout:
                self._hypervisor = "hyperv"
                log.info("[VM] Hyper-V detected and available")
        except Exception as e:
            log.warning(f"[VM] Hyper-V detection failed: {e}")

    def _detect_qemu(self):
        try:
            result = subprocess.run(["which", "qemu-system-x86_64"], capture_output=True, timeout=5)
            if result.returncode == 0:
                self._hypervisor = "qemu"
                log.info("[VM] QEMU detected")
        except Exception as e:
            log.warning(f"[VM] QEMU detection failed: {e}")

    def _detect_macos(self):
        try:
            result = subprocess.run(["sysctl", "machv.hypervisor"], capture_output=True, text=True, timeout=5)
            if result.stdout.strip().endswith(": 1"):
                self._hypervisor = "hypervisor_framework"
                log.info("[VM] macOS Hypervisor.framework available")
        except Exception:
            pass

    def create(self, config: WorkspaceConfig) -> WorkspaceStatus:
        ws_id = str(uuid.uuid4())[:8]
        ws_dir = WORKSPACE_BASE / ws_id
        ws_dir.mkdir(parents=True, exist_ok=True)

        vm_config = {
            "id": ws_id,
            "name": config.name,
            "memory_mb": config.memory_mb,
            "cpu_cores": config.cpu_cores,
            "enable_gpu": config.enable_gpu,
            "resolution": config.resolution,
            "vm_image": config.vm_image,
            "vm_disk_gb": config.vm_disk_gb,
            "hypervisor": self._hypervisor,
            "created_at": time.time(),
        }
        (ws_dir / "vm_config.json").write_text(json.dumps(vm_config, indent=2))

        status = WorkspaceStatus(
            id=ws_id, name=config.name, runtime_type=RuntimeType.VM.value,
            state=WorkspaceState.CREATED.value, resolution=config.resolution,
            display_id=None, memory_mb=config.memory_mb, cpu_cores=config.cpu_cores,
            created_at=time.time(),
        )
        self._save_status(ws_id, status)
        log.info(f"[VM] Created VM workspace {ws_id} (hypervisor: {self._hypervisor})")
        return status

    def start(self, workspace_id: str) -> dict:
        ws_dir = WORKSPACE_BASE / workspace_id
        vm_config_path = ws_dir / "vm_config.json"
        if not vm_config_path.exists():
            return {"ok": False, "error": "VM config not found"}

        vm_config = json.loads(vm_config_path.read_text())
        hypervisor = vm_config.get("hypervisor")

        if hypervisor == "hyperv":
            return self._start_hyperv(workspace_id, vm_config)
        elif hypervisor == "qemu":
            return self._start_qemu(workspace_id, vm_config)
        else:
            log.warning(f"[VM] No hypervisor available, falling back to local")
            fallback = LocalDesktopBackend()
            return fallback.start(workspace_id)

    def _start_hyperv(self, workspace_id: str, vm_config: dict) -> dict:
        try:
            vm_name = f"JARVIS_{workspace_id}"
            memory_mb = vm_config.get("memory_mb", 4096)
            cpu_cores = vm_config.get("cpu_cores", 2)

            ps_cmds = [
                f"New-VM -Name '{vm_name}' -MemoryStartupBytes {memory_mb}MB -Generation 2",
                f"Set-VMProcessor '{vm_name}' -Count {cpu_cores}",
            ]

            for cmd in ps_cmds:
                subprocess.run(
                    ["powershell", "-Command", cmd],
                    capture_output=True, timeout=30
                )

            subprocess.run(
                ["powershell", "-Command", f"Start-VM -Name '{vm_name}'"],
                capture_output=True, timeout=30
            )

            status = self._load_status(workspace_id)
            status.state = WorkspaceState.RUNNING.value
            status.display_id = vm_name
            status.started_at = time.time()
            self._save_status(workspace_id, status)

            log.info(f"[VM] Started Hyper-V VM: {vm_name}")
            return {"ok": True, "workspace": status.to_dict()}

        except Exception as e:
            log.error(f"[VM] Hyper-V start failed: {e}")
            return {"ok": False, "error": str(e)}

    def _start_qemu(self, workspace_id: str, vm_config: dict) -> dict:
        try:
            vm_name = f"jarvis_{workspace_id}"
            memory_mb = vm_config.get("memory_mb", 4096)
            cpu_cores = vm_config.get("cpu_cores", 2)
            w, h = vm_config.get("resolution", (1920, 1080))

            disk_path = WORKSPACE_BASE / workspace_id / "disk.qcow2"
            if not disk_path.exists():
                subprocess.run(
                    ["qemu-img", "create", "-f", "qcow2", str(disk_path), f"{vm_config.get('vm_disk_gb', 50)}G"],
                    capture_output=True, timeout=30
                )

            spice_port = 5900 + hash(workspace_id) % 1000
            qemu_cmd = [
                "qemu-system-x86_64",
                "-name", vm_name,
                "-m", f"{memory_mb}M",
                "-smp", str(cpu_cores),
                "-enable-kvm",
                "-hda", str(disk_path),
                "-vga", "virtio",
                "-spice", f"port={spice_port},disable-ticketing=on",
                "-display", "none",
                "-daemonize",
            ]

            proc = subprocess.Popen(qemu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            status = self._load_status(workspace_id)
            status.state = WorkspaceState.RUNNING.value
            status.display_id = f"spice://localhost:{spice_port}"
            status.started_at = time.time()
            self._save_status(workspace_id, status)

            ws_dir = WORKSPACE_BASE / workspace_id / "env"
            ws_dir.mkdir(exist_ok=True)
            (ws_dir / "qemu.pid").write_text(str(proc.pid))
            (ws_dir / "spice_port").write_text(str(spice_port))

            log.info(f"[VM] Started QEMU VM: {vm_name} (SPICE port {spice_port})")
            return {"ok": True, "workspace": status.to_dict()}

        except Exception as e:
            log.error(f"[VM] QEMU start failed: {e}")
            return {"ok": False, "error": str(e)}

    def stop(self, workspace_id: str) -> dict:
        status = self._load_status(workspace_id)
        display_id = status.display_id

        if display_id and str(display_id).startswith("JARVIS_"):
            try:
                subprocess.run(
                    ["powershell", "-Command", f"Stop-VM -Name '{display_id}' -Force"],
                    capture_output=True, timeout=30
                )
            except Exception:
                pass

        ws_dir = WORKSPACE_BASE / workspace_id / "env"
        qemu_pid = ws_dir / "qemu.pid"
        if qemu_pid.exists():
            try:
                pid = int(qemu_pid.read_text().strip())
                os.kill(pid, 9)
            except Exception:
                pass

        status.state = WorkspaceState.STOPPED.value
        status.started_at = 0
        self._save_status(workspace_id, status)
        return {"ok": True}

    def destroy(self, workspace_id: str) -> dict:
        self.stop(workspace_id)
        ws_dir = WORKSPACE_BASE / workspace_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir, ignore_errors=True)
        return {"ok": True}

    def capture_frame(self, workspace_id: str, quality: int = 60) -> Optional[bytes]:
        ws_dir = WORKSPACE_BASE / workspace_id / "env"
        spice_port = ws_dir / "spice_port"
        if spice_port.exists():
            try:
                port = int(spice_port.read_text().strip())
                result = subprocess.run(
                    ["spice-cmd", "--screenshot", f"--port={port}"],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0 and result.stdout:
                    return result.stdout
            except Exception:
                pass

        import io
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                return buf.getvalue()
        except Exception:
            pass
        return None

    def inject_click(self, workspace_id: str, x: int, y: int, button: int = 1) -> dict:
        ws_dir = WORKSPACE_BASE / workspace_id / "env"
        spice_port = ws_dir / "spice_port"
        if spice_port.exists():
            try:
                port = int(spice_port.read_text().strip())
                subprocess.run(
                    ["spice-cmd", "--click", f"--port={port}", f"--x={x}", f"--y={y}", f"--button={button}"],
                    timeout=5
                )
                return {"ok": True}
            except Exception:
                pass
        return {"ok": False, "error": "No VM input channel"}

    def inject_key(self, workspace_id: str, key: str) -> dict:
        return {"ok": False, "error": "VM input via WebRTC data channel recommended"}

    def inject_text(self, workspace_id: str, text: str) -> dict:
        return {"ok": False, "error": "VM input via WebRTC data channel recommended"}

    def launch_app(self, workspace_id: str, app_name: str, command: List[str] = None) -> dict:
        return {"ok": False, "error": "Use VM agent for app launching"}

    def get_apps(self, workspace_id: str) -> List[dict]:
        return []

    def create_snapshot(self, workspace_id: str, name: str) -> dict:
        status = self._load_status(workspace_id)
        display_id = status.display_id

        if display_id and str(display_id).startswith("JARVIS_"):
            try:
                snapshot_name = f"snap_{int(time.time())}_{name}"
                subprocess.run(
                    ["powershell", "-Command", f"Checkpoint-VM -Name '{display_id}' -SnapshotName '{snapshot_name}'"],
                    capture_output=True, timeout=60
                )
                snapshot_id = f"snap_{int(time.time())}"
                status.snapshots.append(snapshot_id)
                self._save_status(workspace_id, status)
                return {"ok": True, "snapshot_id": snapshot_id, "name": name}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        return {"ok": False, "error": "Snapshots require Hyper-V"}

    def restore_snapshot(self, workspace_id: str, snapshot_id: str) -> dict:
        status = self._load_status(workspace_id)
        display_id = status.display_id

        if display_id and str(display_id).startswith("JARVIS_"):
            try:
                subprocess.run(
                    ["powershell", "-Command", f"Restore-VMSnapshot -VMName '{display_id}' -Name '{snapshot_id}' -Confirm:$false"],
                    capture_output=True, timeout=60
                )
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        return {"ok": False, "error": "Snapshots require Hyper-V"}

    def list_snapshots(self, workspace_id: str) -> List[dict]:
        return [{"id": s, "name": s} for s in self._load_status(workspace_id).snapshots]

    def get_stream_url(self, workspace_id: str) -> Optional[str]:
        status = self._load_status(workspace_id)
        if status.display_id and not str(status.display_id).startswith("JARVIS_"):
            return str(status.display_id)
        return None

    def _save_status(self, workspace_id: str, status: WorkspaceStatus):
        ws_dir = WORKSPACE_BASE / workspace_id
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "status.json").write_text(json.dumps(status.to_dict(), indent=2))

    def _load_status(self, workspace_id: str) -> WorkspaceStatus:
        ws_dir = WORKSPACE_BASE / workspace_id
        path = ws_dir / "status.json"
        if path.exists():
            data = json.loads(path.read_text())
            return WorkspaceStatus(**{k: v for k, v in data.items() if k in WorkspaceStatus.__dataclass_fields__})
        return WorkspaceStatus(
            id=workspace_id, name="Unknown", runtime_type=RuntimeType.VM.value,
            state=WorkspaceState.CREATED.value, resolution=(1920, 1080),
            display_id=None, memory_mb=4096, cpu_cores=2,
        )


class WorkspaceRuntime:
    """Main entry point — dispatches to the appropriate backend."""

    def __init__(self):
        from vm_backend import VirtualBoxBackend
        self._backends: Dict[RuntimeType, WorkspaceBackend] = {
            RuntimeType.LOCAL: LocalDesktopBackend(),
            RuntimeType.VM: VMBackend(),
            RuntimeType.VIRTUALBOX: VirtualBoxBackend(),
        }
        self._default_type = RuntimeType.LOCAL

    def get_backend(self, runtime_type: RuntimeType = None) -> WorkspaceBackend:
        rt = runtime_type or self._default_type
        if rt not in self._backends:
            log.warning(f"No backend for {rt}, falling back to LOCAL")
            return self._backends[RuntimeType.LOCAL]
        return self._backends[rt]

    def create_workspace(self, config: WorkspaceConfig = None) -> WorkspaceStatus:
        config = config or WorkspaceConfig()
        backend = self.get_backend(config.runtime_type)
        return backend.create(config)

    def start_workspace(self, workspace_id: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.start(workspace_id)

    def stop_workspace(self, workspace_id: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.stop(workspace_id)

    def destroy_workspace(self, workspace_id: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.destroy(workspace_id)

    def capture_frame(self, workspace_id: str, runtime_type: RuntimeType = None, quality: int = 60) -> Optional[bytes]:
        backend = self.get_backend(runtime_type)
        return backend.capture_frame(workspace_id, quality)

    def inject_click(self, workspace_id: str, x: int, y: int, button: int = 1, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.inject_click(workspace_id, x, y, button)

    def inject_key(self, workspace_id: str, key: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.inject_key(workspace_id, key)

    def inject_text(self, workspace_id: str, text: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.inject_text(workspace_id, text)

    def launch_app(self, workspace_id: str, app_name: str, command: List[str] = None, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.launch_app(workspace_id, app_name, command)

    def create_snapshot(self, workspace_id: str, name: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.create_snapshot(workspace_id, name)

    def restore_snapshot(self, workspace_id: str, snapshot_id: str, runtime_type: RuntimeType = None) -> dict:
        backend = self.get_backend(runtime_type)
        return backend.restore_snapshot(workspace_id, snapshot_id)

    def list_snapshots(self, workspace_id: str, runtime_type: RuntimeType = None) -> List[dict]:
        backend = self.get_backend(runtime_type)
        return backend.list_snapshots(workspace_id)

    def get_stream_url(self, workspace_id: str, runtime_type: RuntimeType = None) -> Optional[str]:
        backend = self.get_backend(runtime_type)
        return backend.get_stream_url(workspace_id)

    def list_workspaces(self, runtime_type: RuntimeType = None) -> List[dict]:
        workspaces = []
        base = WORKSPACE_BASE
        if not base.exists():
            return workspaces
        for ws_dir in base.iterdir():
            if not ws_dir.is_dir():
                continue
            status_file = ws_dir / "status.json"
            if status_file.exists():
                try:
                    data = json.loads(status_file.read_text())
                    if runtime_type is None or data.get("runtime_type") == runtime_type.value:
                        workspaces.append(data)
                except Exception:
                    pass
        return workspaces


_runtime = None

def get_workspace_runtime() -> WorkspaceRuntime:
    global _runtime
    if _runtime is None:
        _runtime = WorkspaceRuntime()
    return _runtime
