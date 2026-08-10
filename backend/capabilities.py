"""JARVIS Capability Detection — auto-detect available isolation backends and tools."""

import os
import sys
import json
import shutil
import subprocess
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict

log = logging.getLogger("capabilities")

CONFIG_PATH = Path(os.path.expanduser("~/.jarvis/capabilities.json"))


@dataclass
class ToolStatus:
    name: str
    available: bool
    path: str = ""
    version: str = ""
    note: str = ""
    install_url: str = ""
    install_cmd: str = ""

    def to_dict(self):
        return {
            "name": self.name, "available": self.available,
            "path": self.path, "version": self.version,
            "note": self.note, "install_url": self.install_url,
            "install_cmd": self.install_cmd,
        }


@dataclass
class CapabilityReport:
    platform: str = ""
    arch: str = ""
    isolation_backend: str = "sandbox"
    isolation_available: bool = False
    tools: Dict[str, ToolStatus] = field(default_factory=dict)
    recommended_action: str = ""
    setup_complete: bool = False

    def to_dict(self):
        return {
            "platform": self.platform,
            "arch": self.arch,
            "isolation_backend": self.isolation_backend,
            "isolation_available": self.isolation_available,
            "tools": {k: v.to_dict() for k, v in self.tools.items()},
            "recommended_action": self.recommended_action,
            "setup_complete": self.setup_complete,
        }


def _run(cmd: str, timeout: int = 10) -> tuple:
    """Run a command and return (stdout, returncode)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", 1


def _find_executable(name: str) -> str:
    """Find an executable by name."""
    path = shutil.which(name)
    if path:
        return path
    # Check common Windows locations
    if sys.platform == "win32":
        common = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), name),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), name),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), name),
        ]
        for c in common:
            if os.path.isfile(c):
                return c
            # Check with .exe extension
            if os.path.isfile(c + ".exe"):
                return c + ".exe"
    return ""


def detect_virtualbox() -> ToolStatus:
    """Detect Oracle VirtualBox."""
    vbox = _find_executable("VBoxManage")
    if not vbox:
        # Check default install path
        default = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
        if os.path.isfile(default):
            vbox = default
    if vbox:
        out, rc = _run(f'"{vbox}" --version')
        version = out.split("\n")[0] if out else "unknown"
        return ToolStatus(
            name="VirtualBox", available=True, path=vbox,
            version=version, note="Full VM isolation available",
            install_url="https://www.virtualbox.org/wiki/Downloads",
        )
    return ToolStatus(
        name="VirtualBox", available=False,
        note="Recommended for full VM isolation",
        install_url="https://www.virtualbox.org/wiki/Downloads",
        install_cmd="choco install virtualbox -y",
    )


def detect_qemu() -> ToolStatus:
    """Detect QEMU."""
    qemu = _find_executable("qemu-system-x86_64")
    if not qemu:
        qemu = _find_executable("qemu-system-x86_64.exe")
    if qemu:
        out, rc = _run(f'"{qemu}" --version')
        version = out.split("\n")[0] if out else "unknown"
        return ToolStatus(
            name="QEMU", available=True, path=qemu,
            version=version, note="Open-source VM emulation",
            install_url="https://qemu.weilnetz.de/w64/",
        )
    return ToolStatus(
        name="QEMU", available=False,
        note="Alternative VM backend",
        install_url="https://qemu.weilnetz.de/w64/",
    )


def detect_docker() -> ToolStatus:
    """Detect Docker."""
    docker = _find_executable("docker")
    if docker:
        out, rc = _run('docker info --format "{{.ServerVersion}}"')
        if rc == 0:
            return ToolStatus(
                name="Docker", available=True, path=docker,
                version=out, note="Container isolation available",
                install_url="https://docker.com/products/docker-desktop",
            )
    return ToolStatus(
        name="Docker", available=False,
        note="Container-based isolation",
        install_url="https://docker.com/products/docker-desktop",
    )


def detect_python() -> ToolStatus:
    """Detect Python."""
    python = _find_executable("python")
    if python:
        out, _ = _run('python --version')
        version = out.replace("Python ", "") if out else "unknown"
        return ToolStatus(
            name="Python", available=True, path=python,
            version=version, note="Core runtime",
        )
    return ToolStatus(name="Python", available=False, note="Required")


def detect_node() -> ToolStatus:
    """Detect Node.js."""
    node = _find_executable("node")
    if node:
        out, _ = _run('node --version')
        version = out if out else "unknown"
        return ToolStatus(
            name="Node.js", available=True, path=node,
            version=version, note="Frontend runtime",
        )
    return ToolStatus(name="Node.js", available=False, note="Required for frontend")


def detect_chrome() -> ToolStatus:
    """Detect Chrome browser."""
    if sys.platform == "win32":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]
        for p in paths:
            if os.path.isfile(p):
                return ToolStatus(
                    name="Chrome", available=True, path=p,
                    note="Browser automation available",
                )
    chrome = _find_executable("google-chrome") or _find_executable("chrome")
    if chrome:
        return ToolStatus(
            name="Chrome", available=True, path=chrome,
            note="Browser automation available",
        )
    return ToolStatus(
        name="Chrome", available=False,
        note="Needed for browser automation",
        install_url="https://google.com/chrome",
    )


def detect_ffmpeg() -> ToolStatus:
    """Detect FFmpeg."""
    ffmpeg = _find_executable("ffmpeg")
    if ffmpeg:
        out, _ = _run('ffmpeg -version')
        version = out.split("\n")[0] if out else "unknown"
        return ToolStatus(
            name="FFmpeg", available=True, path=ffmpeg,
            version=version, note="Media processing available",
        )
    return ToolStatus(
        name="FFmpeg", available=False,
        note="Optional for media tasks",
        install_url="https://ffmpeg.org/download.html",
    )


def detect_git() -> ToolStatus:
    """Detect Git."""
    git = _find_executable("git")
    if git:
        out, _ = _run('git --version')
        version = out.replace("git version ", "") if out else "unknown"
        return ToolStatus(
            name="Git", available=True, path=git,
            version=version, note="Version control available",
        )
    return ToolStatus(
        name="Git", available=False,
        note="Optional for code projects",
        install_url="https://git-scm.com/downloads",
    )


def detect_all() -> CapabilityReport:
    """Run full capability detection."""
    report = CapabilityReport(
        platform=sys.platform,
        arch=os.environ.get("PROCESSOR_ARCHITECTURE", "unknown"),
    )

    # Detect all tools
    report.tools["python"] = detect_python()
    report.tools["node"] = detect_node()
    report.tools["chrome"] = detect_chrome()
    report.tools["git"] = detect_git()
    report.tools["ffmpeg"] = detect_ffmpeg()
    report.tools["virtualbox"] = detect_virtualbox()
    report.tools["qemu"] = detect_qemu()
    report.tools["docker"] = detect_docker()

    # Determine best isolation backend
    if report.tools["virtualbox"].available:
        report.isolation_backend = "virtualbox"
        report.isolation_available = True
    elif report.tools["qemu"].available:
        report.isolation_backend = "qemu"
        report.isolation_available = True
    elif report.tools["docker"].available:
        report.isolation_backend = "docker"
        report.isolation_available = True
    else:
        report.isolation_backend = "sandbox"
        report.isolation_available = False

    # Generate recommendation
    required_ok = report.tools["python"].available and report.tools["node"].available
    if not required_ok:
        report.recommended_action = "install_required"
    elif not report.isolation_available:
        report.recommended_action = "install_vm"
    else:
        report.recommended_action = "ready"
        report.setup_complete = True

    # Save config
    _save_config(report)

    log.info(f"[CAPS] Platform: {report.platform} | Backend: {report.isolation_backend} | Ready: {report.setup_complete}")
    return report


def _save_config(report: CapabilityReport):
    """Save capability report to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(report.to_dict(), f, indent=2)


def load_config() -> Optional[dict]:
    """Load cached capability config."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return None


# Singleton
_report: Optional[CapabilityReport] = None


def get_capabilities() -> CapabilityReport:
    global _report
    if _report is None:
        _report = detect_all()
    return _report


def refresh_capabilities() -> CapabilityReport:
    global _report
    _report = detect_all()
    return _report
