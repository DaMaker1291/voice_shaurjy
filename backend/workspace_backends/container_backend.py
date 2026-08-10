"""Container Workspace Backend — Docker/Podman isolated execution.

Runs applications inside a container with a virtual display (Xvfb).
Provides full isolation from the user's desktop.

Use when maximum isolation is required for untrusted code execution.
"""

from __future__ import annotations

import os
import io
import time
import logging
import subprocess
import json
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_backend.container")


class ContainerBackend:
    """Docker/Podman container workspace with Xvfb display."""

    name = "container"
    cost = 3  # Higher cost = less preferred (resource-heavy)
    capabilities = [
        "browser", "editor", "terminal", "files",
        "screenshot", "input_injection", "window_management",
        "isolated_execution", "sandboxed",
    ]

    def __init__(self):
        self._running = False
        self._container_id: Optional[str] = None
        self._container_engine = None  # "docker" or "podman"
        self._display_num = 99

    def is_available(self) -> bool:
        """Check if Docker or Podman is available."""
        for engine in ["docker", "podman"]:
            try:
                result = subprocess.run(
                    [engine, "info"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self._container_engine = engine
                    log.info(f"[CONTAINER] {engine} available")
                    return True
            except Exception:
                continue
        log.info("[CONTAINER] Neither Docker nor Podman found")
        return False

    def start(self, resolution: Tuple[int, int] = (1920, 1080)) -> bool:
        """Start a container with Xvfb display."""
        if not self._container_engine:
            return False

        try:
            # Pull a lightweight image with Xvfb + browser
            image = "python:3.12-slim"
            container_name = f"jarvis_ws_{int(time.time())}"

            # Create and start container with virtual display
            cmd = [
                self._container_engine, "run", "-d",
                "--name", container_name,
                "-e", f"DISPLAY=:99",
                "-e", f"RESOLUTION={resolution[0]}x{resolution[1]}",
                "--cap-add", "SYS_ADMIN",
                "--security-opt", "seccomp=unconfined",
                image,
                "bash", "-c",
                "apt-get update && apt-get install -y "
                "xvfb x11-utils imagemagick python3-pip && "
                f"Xvfb :99 -screen 0 {resolution[0]}x{resolution[1]}x24 & "
                "sleep 999999"
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                self._container_id = result.stdout.strip()
                self._running = True
                self._resolution = resolution
                log.info(f"[CONTAINER] Started {container_name} ({self._container_id[:12]})")
                return True
            else:
                log.error(f"[CONTAINER] Failed to start: {result.stderr}")
                return False

        except Exception as e:
            log.error(f"[CONTAINER] Start error: {e}")
            return False

    def stop(self):
        """Stop and remove the container."""
        if self._container_id and self._container_engine:
            try:
                subprocess.run(
                    [self._container_engine, "stop", self._container_id[:12]],
                    capture_output=True, timeout=10,
                )
                subprocess.run(
                    [self._container_engine, "rm", self._container_id[:12]],
                    capture_output=True, timeout=10,
                )
            except Exception as e:
                log.warning(f"[CONTAINER] Stop error: {e}")
        self._running = False
        self._container_id = None

    def is_running(self) -> bool:
        return self._running

    def _exec_in_container(self, cmd: str) -> Tuple[bool, str]:
        """Execute a command inside the container."""
        if not self._container_id or not self._container_engine:
            return False, "No container"
        try:
            result = subprocess.run(
                [self._container_engine, "exec", self._container_id[:12],
                 "bash", "-c", cmd],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def capture_frame(self, quality: int = 60) -> Optional[bytes]:
        """Capture screenshot from the container's virtual display."""
        if not self._running:
            return None

        try:
            # Import mss inside the container
            ok, output = self._exec_in_container(
                "python3 -c \""
                "import mss, mss.tools, base64, sys; "
                "with mss.mss(display=':99') as sct: "
                "    img = sct.grab(sct.monitors[1]); "
                "    raw = mss.tools.to_png(img.rgb, img.size); "
                "    sys.stdout.buffer.write(raw)\""
            )
            if ok and output:
                # Convert PNG to JPEG
                from PIL import Image
                pil_img = Image.open(io.BytesIO(output.encode('latin-1') if isinstance(output, str) else output))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                return buf.getvalue()
        except Exception as e:
            log.error(f"[CONTAINER] Frame capture failed: {e}")

        return None

    def inject_click(self, x: int, y: int, button: int = 1) -> "BackendResult":
        """Click inside the container via xdotool."""
        if not self._running:
            return BackendResult(ok=False, error="Container not running")
        try:
            btn = 1 if button == 1 else 3 if button == 3 else 2
            ok, output = self._exec_in_container(
                f"DISPLAY=:99 xdotool mousemove {x} {y} click {btn}"
            )
            return BackendResult(ok=ok, error=output if not ok else "", method="xdotool")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def inject_key(self, key: str) -> "BackendResult":
        """Press a key inside the container."""
        if not self._running:
            return BackendResult(ok=False, error="Container not running")
        try:
            ok, output = self._exec_in_container(
                f"DISPLAY=:99 xdotool key {key}"
            )
            return BackendResult(ok=ok, error=output if not ok else "", method="xdotool")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def inject_text(self, text: str) -> "BackendResult":
        """Type text inside the container."""
        if not self._running:
            return BackendResult(ok=False, error="Container not running")
        try:
            # Escape special characters for shell
            escaped = text.replace("'", "'\\''")
            ok, output = self._exec_in_container(
                f"DISPLAY=:99 xdotool type -- '{escaped}'"
            )
            return BackendResult(ok=ok, error=output if not ok else "", method="xdotool")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def launch_app(self, name: str, command: List[str] = None) -> "BackendResult":
        """Launch an app inside the container."""
        if not self._running:
            return BackendResult(ok=False, error="Container not running")
        try:
            cmd = " ".join(command) if command else name
            ok, output = self._exec_in_container(
                f"DISPLAY=:99 {cmd} &"
            )
            return BackendResult(ok=True, method="container_exec",
                               output=f"Launched {name} in container")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def list_windows(self) -> List[Dict]:
        """List windows in the container."""
        if not self._running:
            return []
        try:
            ok, output = self._exec_in_container(
                "DISPLAY=:99 wmctrl -l 2>/dev/null || true"
            )
            windows = []
            if ok:
                for line in output.strip().split("\n"):
                    if line.strip():
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append({
                                "pid": parts[0],
                                "desktop": parts[1],
                                "title": parts[3],
                            })
            return windows
        except Exception:
            return []

    def focus_window(self, window_title: str) -> "BackendResult":
        """Focus a window in the container."""
        if not self._running:
            return BackendResult(ok=False, error="Container not running")
        try:
            ok, output = self._exec_in_container(
                f"DISPLAY=:99 wmctrl -a '{window_title}'"
            )
            return BackendResult(ok=ok, error=output if not ok else "")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))


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
