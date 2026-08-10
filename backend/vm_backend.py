"""JARVIS VirtualBox Backend — Works on Windows Home, macOS, Linux.

VirtualBox provides:
- Works without Hyper-V (Windows Home compatible)
- VRDE/RDP streaming built-in
- Snapshots via `VBoxManage snapshot`
- Shared folders for agent communication
- USB/device passthrough
"""

import os
import re
import json
import time
import uuid
import shutil
import logging
import platform
import subprocess
from typing import Optional, List, Dict
from pathlib import Path

log = logging.getLogger("virtualbox_backend")

VBOX_MANAGE = "VBoxManage"


def find_vbox_manage() -> Optional[str]:
    """Locate VBoxManage executable across platforms."""
    # Check PATH first
    try:
        result = subprocess.run(["which", "VBoxManage"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Windows common paths
    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
            r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path

    # macOS
    if platform.system() == "Darwin":
        candidates = [
            "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage",
            "/usr/local/bin/VBoxManage",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path

    # Linux
    candidates = [
        "/usr/bin/VBoxManage",
        "/usr/local/bin/VBoxManage",
        "/snap/bin/VBoxManage",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def vbox_available() -> bool:
    """Check if VirtualBox is installed and functional."""
    path = find_vbox_manage()
    if not path:
        return False
    try:
        result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


class VirtualBoxBackend:
    """VM backend using VirtualBox (cross-platform, works on Windows Home)."""

    def __init__(self):
        self._vbox_path = find_vbox_manage()
        self._version = self._get_version()
        log.info(f"[VBOX] Initialized (path: {self._vbox_path}, version: {self._version})")

    def _get_version(self) -> Optional[str]:
        if not self._vbox_path:
            return None
        try:
            result = subprocess.run([self._vbox_path, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip().split()[0]
        except Exception:
            pass
        return None

    def _run(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a VBoxManage command."""
        if not self._vbox_path:
            raise RuntimeError("VBoxManage not found")
        cmd = [self._vbox_path] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def create(self, config: dict) -> dict:
        """Create a new VirtualBox VM."""
        vm_name = f"JARVIS_{config.get('id', str(uuid.uuid4())[:8])}"
        memory_mb = config.get('memory_mb', 4096)
        cpu_cores = config.get('cpu_cores', 2)
        resolution = config.get('resolution', (1920, 1080))
        disk_gb = config.get('disk_gb', 50)
        enable_gpu = config.get('enable_gpu', False)
        vm_image = config.get('vm_image')

        # Create VM
        self._run(["createvm", "--name", vm_name, "--ostype", "Windows11_64", "--register"])

        # Configure hardware
        vrde_port = 5900 + hash(vm_name) % 1000
        self._run([
            "modifyvm", vm_name,
            "--memory", str(memory_mb),
            "--cpus", str(cpu_cores),
            "--vram", "128" if enable_gpu else "64",
            "--graphicscontroller", "VBoxSVGA" if enable_gpu else "VBoxVGA",
            "--accelerate3d", "on" if enable_gpu else "off",
            "--audio", "none",
            "--usb", "xhci",
            "--clipboard", "bidirectional",
            "--draganddrop", "bidirectional",
        ])

        # Enable VRDE (remote desktop) for streaming
        self._run([
            "modifyvm", vm_name,
            "--vrde", "on",
            "--vrdeport", str(vrde_port),
            "--vrdeaddress", "127.0.0.1",
        ])

        # Create storage controller and disk
        disk_path = Path(config.get('vm_dir', os.path.expanduser("~/.jarvis/vms"))) / f"{vm_name}.vdi"
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(["storagectl", vm_name, "--name", "SATA", "--add", "sata", "--controller", "IntelAhci"])
        self._run(["createhd", "--filename", str(disk_path), "--size", str(disk_gb * 1024), "--format", "VDI"])
        self._run(["storageattach", vm_name, "--storagectl", "SATA", "--port", "0", "--device", "0", "--type", "hdd", "--medium", str(disk_path)])

        # Attach ISO or clone from base image
        if vm_image and os.path.isfile(vm_image):
            self._run(["storageattach", vm_name, "--storagectl", "SATA", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", vm_image])
            self._run(["modifyvm", vm_name, "--boot1", "dvd", "--boot2", "disk"])
        else:
            # Create empty DVD drive for later ISO attachment
            self._run(["storageattach", vm_name, "--storagectl", "SATA", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", "emptydrive"])

        # Create shared folder for agent communication
        shared_dir = Path(config.get('vm_dir', os.path.expanduser("~/.jarvis/vms"))) / "shared"
        shared_dir.mkdir(parents=True, exist_ok=True)
        self._run(["sharedfolder", "add", vm_name, "--name", "jarvis_share", "--hostpath", str(shared_dir), "--automount"])

        # Save config
        vm_config = {
            "name": vm_name,
            "memory_mb": memory_mb,
            "cpu_cores": cpu_cores,
            "resolution": resolution,
            "vrde_port": vrde_port,
            "disk_path": str(disk_path),
            "shared_dir": str(shared_dir),
            "enable_gpu": enable_gpu,
            "created_at": time.time(),
        }
        config_path = Path(config.get('vm_dir', os.path.expanduser("~/.jarvis/vms"))) / f"{vm_name}.json"
        config_path.write_text(json.dumps(vm_config, indent=2))

        return {
            "id": config.get('id', ''),
            "name": vm_name,
            "state": "created",
            "display_id": vm_name,
            "vrde_port": vrde_port,
            "stream_url": f"vrde://127.0.0.1:{vrde_port}",
            "shared_dir": str(shared_dir),
            "config": vm_config,
        }

    def start(self, vm_name: str) -> dict:
        """Start the VM headless (no GUI window)."""
        result = self._run(["startvm", vm_name, "--type", "headless"], timeout=60)
        if result.returncode != 0:
            # Try to extract error from stderr
            error = result.stderr.strip() if result.stderr else "Unknown error"
            return {"ok": False, "error": error}

        # Wait for VRDE to be ready
        time.sleep(2)
        return {"ok": True, "message": f"VM {vm_name} started (headless)"}

    def stop(self, vm_name: str) -> dict:
        """Gracefully stop the VM."""
        result = self._run(["controlvm", vm_name, "acpipowerbutton"], timeout=30)
        # Wait for shutdown
        for _ in range(30):
            state = self.get_state(vm_name)
            if state == "poweroff":
                return {"ok": True, "message": "VM stopped gracefully"}
            time.sleep(1)
        # Force stop
        self._run(["controlvm", vm_name, "poweroff"], timeout=10)
        return {"ok": True, "message": "VM force stopped"}

    def pause(self, vm_name: str) -> dict:
        """Pause the VM (preserve state)."""
        result = self._run(["controlvm", vm_name, "pause"], timeout=10)
        return {"ok": result.returncode == 0}

    def destroy(self, vm_name: str) -> dict:
        """Destroy the VM and all associated files."""
        self.stop(vm_name)
        result = self._run(["unregistervm", vm_name, "--delete"], timeout=30)
        return {"ok": result.returncode == 0}

    def get_state(self, vm_name: str) -> str:
        """Get VM state (running, poweroff, paused, etc.)."""
        result = self._run(["showvminfo", vm_name, "--machinereadable"], timeout=10)
        if result.returncode != 0:
            return "unknown"
        for line in result.stdout.split('\n'):
            if line.startswith('VMState='):
                return line.split('=', 1)[1].strip('"')
        return "unknown"

    def capture_frame(self, vm_name: str, quality: int = 60) -> Optional[bytes]:
        """Capture a screenshot of the VM display."""
        result = self._run([
            "controlvm", vm_name, "screenshotpng", "--filename", "-"
        ], timeout=10)
        if result.returncode == 0:
            return result.stdout.encode('latin1') if isinstance(result.stdout, str) else result.stdout
        return None

    def inject_click(self, vm_name: str, x: int, y: int, button: int = 1) -> dict:
        """Inject mouse click into VM via keyboard/mouse events."""
        # VirtualBox doesn't have direct mouse injection via VBoxManage
        # Would need to use the VirtualBox SDK or RDP input channel
        return {"ok": False, "error": "Use VRDE/RDP for input injection"}

    def inject_key(self, vm_name: str, key: str) -> dict:
        """Inject keyboard event into VM."""
        return {"ok": False, "error": "Use VRDE/RDP for input injection"}

    def inject_text(self, vm_name: str, text: str) -> dict:
        """Inject text input into VM."""
        return {"ok": False, "error": "Use VRDE/RDP for input injection"}

    def launch_app(self, vm_name: str, app_name: str, command: List[str] = None) -> dict:
        """Launch an application inside the VM."""
        return {"ok": False, "error": "Use VM agent for app launching"}

    def create_snapshot(self, vm_name: str, name: str) -> dict:
        """Create a snapshot of the VM."""
        snapshot_name = f"snap_{int(time.time())}_{name}"
        result = self._run(["snapshot", vm_name, "take", snapshot_name], timeout=60)
        if result.returncode == 0:
            return {"ok": True, "snapshot_id": snapshot_name, "name": name}
        return {"ok": False, "error": result.stderr}

    def restore_snapshot(self, vm_name: str, snapshot_id: str) -> dict:
        """Restore a VM to a previous snapshot."""
        result = self._run(["snapshot", vm_name, "restore", snapshot_id], timeout=60)
        return {"ok": result.returncode == 0}

    def list_snapshots(self, vm_name: str) -> List[dict]:
        """List all snapshots for the VM."""
        result = self._run(["snapshot", vm_name, "list", "--machinereadable"], timeout=10)
        if result.returncode != 0:
            return []
        snapshots = []
        for line in result.stdout.split('\n'):
            match = re.match(r'SnapshotName(?:\d*)="(.+?)"', line)
            if match:
                snapshots.append({"id": match.group(1), "name": match.group(1)})
        return snapshots

    def get_stream_url(self, vm_name: str) -> Optional[str]:
        """Get the VRDE stream URL for the VM."""
        result = self._run(["showvminfo", vm_name, "--machinereadable"], timeout=10)
        if result.returncode != 0:
            return None
        for line in result.stdout.split('\n'):
            if line.startswith('VRDEPort='):
                port = line.split('=', 1)[1].strip('"')
                return f"vrde://127.0.0.1:{port}"
        return None

    def resize(self, vm_name: str, memory_mb: int = None, cpu_cores: int = None) -> dict:
        """Resize VM resources."""
        args = ["modifyvm", vm_name]
        if memory_mb:
            args.extend(["--memory", str(memory_mb)])
        if cpu_cores:
            args.extend(["--cpus", str(cpu_cores)])
        result = self._run(args, timeout=10)
        return {"ok": result.returncode == 0}

    def attach_iso(self, vm_name: str, iso_path: str) -> dict:
        """Attach an ISO image to the VM DVD drive."""
        result = self._run(["storageattach", vm_name, "--storagectl", "SATA", "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", iso_path])
        return {"ok": result.returncode == 0}

    def clone(self, source_vm: str, new_name: str) -> dict:
        """Clone an existing VM."""
        result = self._run(["clonevm", source_vm, "--name", new_name, "--register", "--mode", "machine"], timeout=120)
        if result.returncode == 0:
            return {"ok": True, "new_vm": new_name}
        return {"ok": False, "error": result.stderr}

    @property
    def available(self) -> bool:
        return vbox_available()

    @property
    def version(self) -> Optional[str]:
        return self._version
