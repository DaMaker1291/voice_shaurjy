"""JARVIS Workspace Backends — Execution environment abstraction.

The backend selection is automatic:
  1. WSL + Xvfb (isolated Linux display on Windows)
  2. Native Windows (pyautogui + mss)
  3. Linux VDI (xdotool + scrot)
  4. Synthetic fallback (placeholder frames)

The user never sees which backend is active.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_backend")


@dataclass
class BackendResult:
    ok: bool
    output: str = ""
    error: str = ""
    method: str = ""
    artifacts: List[str] = field(default_factory=list)


class WorkspaceBackend(ABC):
    """Abstract interface for workspace execution backends."""

    name: str = "base"
    cost: int = 0  # lower = preferred
    capabilities: List[str] = field(default_factory=list)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend can run on the current system."""
        ...

    @abstractmethod
    def start(self, resolution: Tuple[int, int] = (1920, 1080)) -> bool:
        """Start the execution environment. Returns True on success."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the execution environment and clean up."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the environment is currently running."""
        ...

    @abstractmethod
    def capture_frame(self, quality: int = 60) -> Optional[bytes]:
        """Capture a JPEG frame from the virtual display. Returns bytes or None."""
        ...

    @abstractmethod
    def inject_click(self, x: int, y: int, button: int = 1) -> BackendResult:
        """Inject a mouse click at (x, y). button: 1=left, 2=middle, 3=right."""
        ...

    @abstractmethod
    def inject_key(self, key: str) -> BackendResult:
        """Inject a key press (e.g. 'Return', 'ctrl+c', 'alt+Tab')."""
        ...

    @abstractmethod
    def inject_text(self, text: str) -> BackendResult:
        """Type text character by character."""
        ...

    @abstractmethod
    def launch_app(self, name: str, command: List[str] = None) -> BackendResult:
        """Launch an application inside the workspace."""
        ...

    @abstractmethod
    def list_windows(self) -> List[Dict]:
        """List open windows in the workspace."""
        ...

    @abstractmethod
    def focus_window(self, window_title: str) -> BackendResult:
        """Focus a window by title substring."""
        ...


_backends: Dict[str, WorkspaceBackend] = {}
_initialized = False


def _detect_backends():
    """Auto-detect available backends and register them."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Try WSL + Xvfb (preferred on Windows)
    try:
        from .wsl_xvfb import WslXvfbBackend
        b = WslXvfbBackend()
        if b.is_available():
            _backends["wsl_xvfb"] = b
            log.info("[BACKEND] WSL + Xvfb available")
    except Exception as e:
        log.debug(f"[BACKEND] WSL + Xvfb not available: {e}")

    # Try native Windows
    if sys.platform == "win32":
        try:
            from .windows_native import WindowsNativeBackend
            b = WindowsNativeBackend()
            if b.is_available():
                _backends["windows_native"] = b
                log.info("[BACKEND] Windows native available")
        except Exception as e:
            log.debug(f"[BACKEND] Windows native not available: {e}")

    # Try Linux VDI
    if sys.platform == "linux":
        try:
            from .linux_vdi import LinuxVdiBackend
            b = LinuxVdiBackend()
            if b.is_available():
                _backends["linux_vdi"] = b
                log.info("[BACKEND] Linux VDI available")
        except Exception as e:
            log.debug(f"[BACKEND] Linux VDI not available: {e}")

    # Try macOS native
    if sys.platform == "darwin":
        try:
            from .macos_native import MacOsNativeBackend
            b = MacOsNativeBackend()
            if b.is_available():
                _backends["macos_native"] = b
                log.info("[BACKEND] macOS native available")
        except Exception as e:
            log.debug(f"[BACKEND] macOS native not available: {e}")

    # Try container backend (Docker/Podman)
    try:
        from .container_backend import ContainerBackend
        b = ContainerBackend()
        if b.is_available():
            _backends["container"] = b
            log.info("[BACKEND] Container backend available")
    except Exception as e:
        log.debug(f"[BACKEND] Container not available: {e}")

    # Try browser sandbox
    try:
        from .browser_sandbox import BrowserSandboxBackend
        b = BrowserSandboxBackend()
        if b.is_available():
            _backends["browser_sandbox"] = b
            log.info("[BACKEND] Browser sandbox available")
    except Exception as e:
        log.debug(f"[BACKEND] Browser sandbox not available: {e}")

    if not _backends:
        log.warning("[BACKEND] No real backends available — synthetic fallback only")


def get_backend(name: str = None) -> Optional[WorkspaceBackend]:
    """Get a specific backend, or the best available one."""
    _detect_backends()
    if name:
        return _backends.get(name)
    # Return best available (lowest cost)
    if _backends:
        return min(_backends.values(), key=lambda b: b.cost)
    return None


def get_available_backends() -> List[WorkspaceBackend]:
    """Get all available backends sorted by cost."""
    _detect_backends()
    return sorted(_backends.values(), key=lambda b: b.cost)
