"""WSL + Xvfb Workspace Backend — Isolated Linux display on Windows.

Creates a virtual display inside WSL2 where JARVIS can run real applications
(browser, editor, terminal) without touching the user's Windows desktop.

Architecture:
  Windows Host → WSL2 → Xvfb (:99) → Chrome / VS Code / Terminal
                                    ↑ xdotool (input)
                                    ↑ scrot/import (screenshots)
                                    ↑ wmctrl (window management)
"""

from __future__ import annotations

import os
import io
import time
import shutil
import subprocess
import logging
import tempfile
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_backend.wsl")

# Display configuration
DEFAULT_DISPLAY = ":99"
DEFAULT_RESOLUTION = (1920, 1080)
DEFAULT_DEPTH = 24


def _run(cmd: str, timeout: int = 10, check: bool = False) -> subprocess.CompletedProcess:
    """Run a command in WSL with timeout."""
    wsl_cmd = ["wsl", "-e", "bash", "-c", cmd]
    try:
        return subprocess.run(
            wsl_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired:
        log.error(f"[WSL] Command timed out: {cmd[:80]}")
        return subprocess.CompletedProcess(cmd, 1, "", "timeout")
    except Exception as e:
        log.error(f"[WSL] Command failed: {cmd[:80]} — {e}")
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def _run_display(cmd: str, display: str = DEFAULT_DISPLAY, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a command with DISPLAY set to the virtual display."""
    env_cmd = f"DISPLAY={display} {cmd}"
    return _run(env_cmd, timeout=timeout)


class WslXvfbBackend:
    """Isolated workspace using WSL2 + Xvfb."""

    name = "wsl_xvfb"
    cost = 0  # Preferred — cheapest isolated option
    capabilities = [
        "browser", "editor", "terminal", "files",
        "screenshot", "input_injection", "window_management",
        "isolated_display", "real_apps",
    ]

    def __init__(self):
        self._display = DEFAULT_DISPLAY
        self._resolution = DEFAULT_RESOLUTION
        self._xvfb_pid: Optional[int] = None
        self._running = False

    def is_available(self) -> bool:
        """Check if WSL2 is available with required tools."""
        if os.name != "nt":
            return False  # WSL is Windows-only

        # Check WSL is installed
        result = _run("echo ok", timeout=5)
        if result.returncode != 0:
            return False

        # Check required tools exist in WSL
        check = _run("which Xvfb xdotool scrot 2>/dev/null && echo tools_ok", timeout=5)
        if "tools_ok" not in (check.stdout or ""):
            log.info("[WSL] Missing tools — run setup_wsl_workspace.sh in WSL")
            return False

        return True

    def start(self, resolution: Tuple[int, int] = (1920, 1080)) -> bool:
        """Start Xvfb virtual display in WSL."""
        if self._running:
            return True

        self._resolution = resolution
        w, h = resolution

        # Kill any existing Xvfb on this display
        _run(f"killall Xvfb 2>/dev/null || true", timeout=5)
        time.sleep(0.5)

        # Start Xvfb
        xvfb_cmd = f"Xvfb {self._display} -screen 0 {w}x{h}x{DEFAULT_DEPTH} -ac +extension GLX +render -noreset &"
        result = _run(xvfb_cmd, timeout=5)
        if result.returncode != 0:
            log.error(f"[WSL] Failed to start Xvfb: {result.stderr}")
            return False

        # Wait for display to be ready
        for i in range(10):
            time.sleep(0.5)
            check = _run_display("xdpyinfo | head -1", timeout=3)
            if check.returncode == 0 and "Xwayland" in (check.stdout or "") or "Xvfb" in (check.stdout or ""):
                self._running = True
                log.info(f"[WSL] Xvfb started on {self._display} ({w}x{h})")
                return True

        # Accept if display is running (even if xdpyinfo output differs)
        check2 = _run_display("xdotool getactivewindow 2>/dev/null || echo display_ready", timeout=3)
        if check2.returncode == 0:
            self._running = True
            log.info(f"[WSL] Xvfb started on {self._display} ({w}x{h})")
            return True

        log.error("[WSL] Xvfb started but display not responding")
        return False

    def stop(self):
        """Stop Xvfb and clean up."""
        if not self._running:
            return
        _run(f"killall Xvfb 2>/dev/null || true", timeout=5)
        _run(f"killall chrome 2>/dev/null || true", timeout=5)
        _run(f"killall code 2>/dev/null || true", timeout=5)
        self._running = False
        self._xvfb_pid = None
        log.info("[WSL] Xvfb stopped")

    def is_running(self) -> bool:
        """Check if Xvfb is still alive."""
        if not self._running:
            return False
        result = _run("pgrep Xvfb >/dev/null 2>&1 && echo alive", timeout=3)
        alive = "alive" in (result.stdout or "")
        if not alive:
            self._running = False
        return alive

    def capture_frame(self, quality: int = 60) -> Optional[bytes]:
        """Capture a real screenshot from the Xvfb display."""
        if not self._running:
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name

        try:
            # Use scrot for fast screenshot capture
            result = _run_display(
                f"scrot -q {quality} -o {tmp_path} 2>/dev/null || "
                f"import -window root -quality {quality} {tmp_path} 2>/dev/null || "
                f"echo capture_failed",
                timeout=10,
            )

            if "capture_failed" in (result.stdout + result.stderr):
                # Fallback: try xwd + convert
                xwd_path = tmp_path.replace(".jpg", ".xwd")
                _run_display(f"xwd -root -out {xwd_path} 2>/dev/null", timeout=5)
                _run(f"convert {xwd_path} -quality {quality} {tmp_path} 2>/dev/null", timeout=5)
                _run(f"rm -f {xwd_path}", timeout=3)

            # Read the captured file from WSL
            # Convert WSL path to Windows path for reading
            wsl_path = tmp_path
            win_result = _run(f"wslpath -w {tmp_path} 2>/dev/null || echo {tmp_path}", timeout=3)
            win_path = (win_result.stdout or "").strip()

            if win_path and os.path.exists(win_path):
                with open(win_path, "rb") as f:
                    return f.read()

            # Fallback: read via WSL cat + base64
            b64_result = _run(f"base64 {tmp_path} 2>/dev/null", timeout=10)
            if b64_result.stdout:
                import base64
                return base64.b64decode(b64_result.stdout.strip())

            return None
        except Exception as e:
            log.error(f"[WSL] Frame capture failed: {e}")
            return None
        finally:
            _run(f"rm -f {tmp_path}", timeout=3)

    def inject_click(self, x: int, y: int, button: int = 1) -> "BackendResult":
        """Inject a real mouse click via xdotool."""
        if not self._running:
            return BackendResult(ok=False, error="Workspace not running")

        btn_map = {1: "1", 2: "2", 3: "3"}
        btn = btn_map.get(button, "1")
        result = _run_display(f"xdotool mousemove --sync {x} {y} click {btn}", timeout=5)

        if result.returncode == 0:
            return BackendResult(ok=True, method="xdotool")
        return BackendResult(ok=False, error=result.stderr or "click failed")

    def inject_key(self, key: str) -> "BackendResult":
        """Inject a key press via xdotool."""
        if not self._running:
            return BackendResult(ok=False, error="Workspace not running")

        # Normalize key names for xdotool
        key_map = {
            "Return": "Return",
            "enter": "Return",
            "tab": "Tab",
            "escape": "Escape",
            "esc": "Escape",
            "backspace": "BackSpace",
            "delete": "Delete",
            "space": "space",
            "ctrl+c": "ctrl+c",
            "ctrl+v": "ctrl+v",
            "ctrl+x": "ctrl+x",
            "ctrl+z": "ctrl+z",
            "ctrl+a": "ctrl+a",
            "ctrl+s": "ctrl+s",
            "alt+Tab": "alt+Tab",
            "alt+F4": "alt+F4",
            "super": "Super_L",
            "super+l": "super+l",
        }
        xdotool_key = key_map.get(key, key)
        result = _run_display(f"xdotool key {xdotool_key}", timeout=5)

        if result.returncode == 0:
            return BackendResult(ok=True, method="xdotool")
        return BackendResult(ok=False, error=result.stderr or "key failed")

    def inject_text(self, text: str) -> "BackendResult":
        """Type text via xdotool."""
        if not self._running:
            return BackendResult(ok=False, error="Workspace not running")

        # Escape special characters for xdotool
        escaped = text.replace("'", "\\'").replace('"', '\\"')
        result = _run_display(f"xdotool type --clearmodifiers '{escaped}'", timeout=10)

        if result.returncode == 0:
            return BackendResult(ok=True, method="xdotool")
        return BackendResult(ok=False, error=result.stderr or "type failed")

    def launch_app(self, name: str, command: List[str] = None) -> "BackendResult":
        """Launch an app inside the Xvfb display."""
        if not self._running:
            return BackendResult(ok=False, error="Workspace not running")

        cmd_list = command or [name]
        cmd_str = " ".join(cmd_list)

        # Launch in background with display set
        result = _run_display(
            f"nohup {cmd_str} >/dev/null 2>&1 &",
            timeout=5,
        )

        if result.returncode == 0:
            time.sleep(1)  # Give app time to start
            return BackendResult(ok=True, method="subprocess", output=f"Launched {name}")
        return BackendResult(ok=False, error=result.stderr or f"Failed to launch {name}")

    def list_windows(self) -> List[Dict]:
        """List open windows via wmctrl."""
        if not self._running:
            return []

        result = _run_display("wmctrl -l 2>/dev/null || xdotool search --name '' getwindowname 2>/dev/null", timeout=5)
        windows = []
        for line in (result.stdout or "").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 3)
            if len(parts) >= 4:
                windows.append({
                    "id": parts[0],
                    "desktop": parts[1],
                    "pid": parts[2],
                    "title": parts[3],
                })
            elif len(parts) >= 1:
                windows.append({"title": line, "id": "", "desktop": "", "pid": ""})
        return windows

    def focus_window(self, window_title: str) -> "BackendResult":
        """Focus a window by title substring."""
        if not self._running:
            return BackendResult(ok=False, error="Workspace not running")

        result = _run_display(
            f"xdotool search --name '{window_title}' windowactivate --sync 2>/dev/null",
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return BackendResult(ok=True, method="xdotool")

        # Fallback: wmctrl
        result2 = _run_display(
            f"wmctrl -a '{window_title}' 2>/dev/null",
            timeout=5,
        )
        if result2.returncode == 0:
            return BackendResult(ok=True, method="wmctrl")

        return BackendResult(ok=False, error=f"Window '{window_title}' not found")


# Lazy import for type checking
try:
    from . import BackendResult
except ImportError:
    from dataclasses import dataclass, field as _field

    @dataclass
    class BackendResult:
        ok: bool
        output: str = ""
        error: str = ""
        method: str = ""
        artifacts: List[str] = _field(default_factory=list)
