"""JARVIS VirtualBox Integration — create/manage VMs for workspace isolation."""

import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict

log = logging.getLogger("vbox_integration")

VBOX_MANAGE = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
VM_NAME_PREFIX = "JARVIS-WS"
VM_DIR = Path(os.path.expanduser("~/.jarvis/vms"))
VM_DIR.mkdir(parents=True, exist_ok=True)

# VM configuration
VM_MEMORY_MB = 2048
VM_CPUS = 2
VM_VRAM_MB = 128
VM_DISK_GB = 10


def vbox_available() -> bool:
    """Check if VBoxManage is accessible."""
    return os.path.isfile(VBOX_MANAGE)


def _run_vbox(args: list, timeout: int = 30) -> tuple:
    """Run VBoxManage command, return (stdout, returncode)."""
    if not vbox_available():
        return "", 1
    try:
        cmd = [VBOX_MANAGE] + args
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr, r.returncode
    except Exception as e:
        return str(e), 1


def list_jarvis_vms() -> list:
    """List all JARVIS workspace VMs."""
    out, rc = _run_vbox(["list", "vms"])
    vms = []
    for line in out.strip().split("\n"):
        if line.strip() and VM_NAME_PREFIX in line:
            # Parse: "JARVIS-WS-abc123" {uuid}
            name = line.split("{")[0].strip().strip('"')
            uuid = line.split("{")[1].rstrip("}").strip() if "{" in line else ""
            vms.append({"name": name, "uuid": uuid})
    return vms


def create_vm(ws_id: str) -> dict:
    """Create a new JARVIS workspace VM."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    vm_path = VM_DIR / vm_name
    vm_path.mkdir(exist_ok=True)

    # Check if VM already exists
    existing = list_jarvis_vms()
    if any(v["name"] == vm_name for v in existing):
        return {"ok": True, "vm_name": vm_name, "note": "VM already exists"}

    # Create VM
    out, rc = _run_vbox([
        "createvm", "--name", vm_name, "--ostype", "Ubuntu_64", "--register",
        "--basefolder", str(VM_DIR),
    ], timeout=30)
    if rc != 0:
        return {"ok": False, "error": f"Failed to create VM: {out}"}

    # Configure VM
    _run_vbox([
        "modifyvm", vm_name,
        "--memory", str(VM_MEMORY_MB),
        "--cpus", str(VM_CPUS),
        "--vram", str(VM_VRAM_MB),
        "--graphicscontroller", "vmsvga",
        "--audio-driver", "none",
        "--boot1", "disk",
        "--boot2", "dvd",
        "--nic1", "nat",
        "--nictype1", "82540EM",
        # Shared folder for file access
        "--shared-folder1", f"{VM_DIR / 'shared'}=jarvis-shared",
    ])

    # Create SATA controller and disk
    _run_vbox(["storagectl", vm_name, "--name", "SATA", "--add", "sata", "--controller", "IntelAhci"])

    # Create a small virtual disk
    disk_path = vm_path / f"{vm_name}.vdi"
    _run_vbox([
        "createmedium", "disk",
        "--filename", str(disk_path),
        "--size", str(VM_DISK_GB * 1024),
        "--format", "VDI",
    ])

    # Attach disk
    _run_vbox([
        "storageattach", vm_name,
        "--storagectl", "SATA",
        "--port", "0", "--device", "0",
        "--type", "hdd",
        "--medium", str(disk_path),
    ])

    # Create IDE controller for Guest Additions
    _run_vbox(["storagectl", vm_name, "--name", "IDE", "--add", "ide"])

    # Mount Guest Additions ISO
    ga_iso = r"C:\Program Files\Oracle\VirtualBox\VBoxGuestAdditions.iso"
    if os.path.isfile(ga_iso):
        _run_vbox([
            "storageattach", vm_name,
            "--storagectl", "IDE",
            "--port", "0", "--device", "0",
            "--type", "dvddrive",
            "--medium", ga_iso,
        ])

    # Port forwarding for SSH
    _run_vbox([
        "modifyvm", vm_name,
        "--natpf1", "ssh,tcp,,2222,,22",
        "--natpf1", "http,tcp,,8080,,80",
    ])

    # Create shared folder directory
    shared_dir = VM_DIR / "shared"
    shared_dir.mkdir(exist_ok=True)

    log.info(f"[VBOX] Created VM: {vm_name}")
    return {"ok": True, "vm_name": vm_name, "disk": str(disk_path)}


def start_vm(ws_id: str) -> dict:
    """Start a JARVIS workspace VM."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    out, rc = _run_vbox(["startvm", vm_name, "--type", "headless"], timeout=30)
    if rc != 0:
        return {"ok": False, "error": f"Failed to start VM: {out}"}

    log.info(f"[VBOX] Started VM: {vm_name}")
    return {"ok": True, "vm_name": vm_name}


def stop_vm(ws_id: str) -> dict:
    """Stop a JARVIS workspace VM gracefully."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    # Try ACPI shutdown first
    _run_vbox(["controlvm", vm_name, "acpipowerbutton"], timeout=10)
    time.sleep(5)
    # Force power off if still running
    _run_vbox(["controlvm", vm_name, "poweroff"], timeout=10)

    log.info(f"[VBOX] Stopped VM: {vm_name}")
    return {"ok": True}


def destroy_vm(ws_id: str) -> dict:
    """Destroy a JARVIS workspace VM."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    _run_vbox(["controlvm", vm_name, "poweroff"], timeout=10)
    time.sleep(2)
    _run_vbox(["unregistervm", vm_name, "--delete"], timeout=30)

    log.info(f"[VBOX] Destroyed VM: {vm_name}")
    return {"ok": True}


def capture_screenshot(ws_id: str, output_path: str) -> bool:
    """Capture VM screenshot."""
    if not vbox_available():
        return False

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    out, rc = _run_vbox(["controlvm", vm_name, "screenshotpng", output_path], timeout=10)
    return rc == 0 and os.path.isfile(output_path)


def run_in_vm(ws_id: str, command: str, username: str = "root", password: str = "") -> dict:
    """Run a command inside the VM via Guest Additions."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    args = [
        "guestcontrol", vm_name, "run",
        "--exe", "/bin/bash",
        "--username", username,
        "--password", password,
        "--", "-c", command,
    ]
    out, rc = _run_vbox(args, timeout=30)
    return {"ok": rc == 0, "output": out, "exit_code": rc}


def inject_key(ws_id: str, key: str) -> dict:
    """Send a keyboard key to the VM."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    # Map key names to VBoxManage keyboard codes
    key_map = {
        "Return": "Return", "Tab": "Tab", "Escape": "Escape",
        "BackSpace": "BackSpace", "Delete": "Delete",
        "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
        "space": "space", "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4",
    }
    vk = key_map.get(key, key)
    _run_vbox(["controlvm", vm_name, "keyboardputstring", f"{vk}\n"], timeout=5)
    return {"ok": True}


def inject_text(ws_id: str, text: str) -> dict:
    """Type text into the VM."""
    if not vbox_available():
        return {"ok": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    _run_vbox(["controlvm", vm_name, "keyboardputstring", text], timeout=10)
    return {"ok": True}


def vm_status(ws_id: str) -> dict:
    """Get VM running status."""
    if not vbox_available():
        return {"running": False, "error": "VirtualBox not installed"}

    vm_name = f"{VM_NAME_PREFIX}-{ws_id}"
    out, rc = _run_vbox(["showvminfo", vm_name, "--machinereadable"])
    if rc != 0:
        return {"running": False, "error": "VM not found"}

    state = "stopped"
    for line in out.split("\n"):
        if line.startswith("VMState="):
            state = line.split("=")[1].strip('"')
            break

    return {"running": state in ("running", "paused"), "state": state, "vm_name": vm_name}
