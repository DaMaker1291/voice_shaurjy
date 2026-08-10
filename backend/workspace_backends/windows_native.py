"""Windows Native Workspace Backend — Direct desktop control.

Uses pyautogui, mss, and win32api for real desktop automation on Windows.
No isolation — operates on the user's actual desktop.

Use when WSL is not available or for tasks that require native Windows apps.
"""

from __future__ import annotations

import os
import io
import time
import logging
import subprocess
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_backend.windows")


class WindowsNativeBackend:
    """Direct Windows desktop control via pyautogui + mss."""

    name = "windows_native"
    cost = 1  # Higher cost than WSL (no isolation)
    capabilities = [
        "browser", "editor", "terminal", "files",
        "screenshot", "input_injection", "window_management",
        "native_windows_apps",
    ]

    def __init__(self):
        self._running = False
        self._mss_instance = None

    def is_available(self) -> bool:
        """Check if we're on Windows with pyautogui/mss."""
        if os.name != "nt":
            return False
        try:
            import pyautogui
            import mss
            return True
        except ImportError:
            log.info("[WIN] Missing pyautogui or mss — pip install pyautogui mss")
            return False

    def start(self, resolution: Tuple[int, int] = (1920, 1080)) -> bool:
        """No startup needed — we use the existing desktop."""
        self._running = True
        log.info("[WIN] Native Windows backend ready")
        return True

    def stop(self):
        """Nothing to stop — we don't own the desktop."""
        self._running = False
        self._mss_instance = None
        log.info("[WIN] Native backend released")

    def is_running(self) -> bool:
        return self._running

    def capture_frame(self, quality: int = 60) -> Optional[bytes]:
        """Capture the real Windows desktop screenshot."""
        if not self._running:
            return None
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                img = sct.grab(monitor)
                # Convert to JPEG
                raw = mss.tools.to_png(img.rgb, img.size)
                # Re-encode as JPEG via PIL
                from PIL import Image
                pil_img = Image.open(io.BytesIO(raw))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                return buf.getvalue()
        except Exception as e:
            log.error(f"[WIN] Screenshot failed: {e}")
            return None

    def inject_click(self, x: int, y: int, button: int = 1) -> "BackendResult":
        """Real mouse click via pyautogui."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")
        try:
            import pyautogui
            btn = "left" if button == 1 else "right" if button == 3 else "middle"
            pyautogui.click(x, y, button=btn)
            return BackendResult(ok=True, method="pyautogui")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def inject_key(self, key: str) -> "BackendResult":
        """Real key press via pyautogui."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")
        try:
            import pyautogui
            # Normalize key names
            key_map = {
                "Return": "enter",
                "enter": "enter",
                "tab": "tab",
                "escape": "escape",
                "esc": "escape",
                "backspace": "backspace",
                "delete": "delete",
                "space": "space",
                "super": "win",
                "super+l": "win+l",
            }
            normalized = key_map.get(key, key)
            if "+" in normalized:
                pyautogui.hotkey(*normalized.split("+"))
            else:
                pyautogui.press(normalized)
            return BackendResult(ok=True, method="pyautogui")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def inject_text(self, text: str) -> "BackendResult":
        """Type text via pyautogui."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
            return BackendResult(ok=True, method="pyautogui")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def launch_app(self, name: str, command: List[str] = None) -> "BackendResult":
        """Launch an app on Windows."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")
        try:
            cmd = command or [name]
            subprocess.Popen(cmd, shell=True)
            time.sleep(1)
            return BackendResult(ok=True, method="subprocess", output=f"Launched {name}")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def list_windows(self) -> List[Dict]:
        """List windows via pyautogui."""
        if not self._running:
            return []
        try:
            import pyautogui
            # pyautogui doesn't have a list windows function on Windows
            # Use PowerShell
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object Id, MainWindowTitle | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5,
            )
            import json
            data = json.loads(result.stdout or "[]")
            if isinstance(data, dict):
                data = [data]
            return [{"pid": str(p.get("Id", "")), "title": p.get("MainWindowTitle", "")} for p in data]
        except Exception as e:
            log.error(f"[WIN] List windows failed: {e}")
            return []

    def focus_window(self, window_title: str) -> "BackendResult":
        """Focus a window by title."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")
        try:
            import pyautogui
            # Search for window
            windows = self.list_windows()
            for w in windows:
                if window_title.lower() in w.get("title", "").lower():
                    pid = w.get("pid")
                    if pid:
                        subprocess.run(
                            ["powershell", "-Command",
                             f"(Get-Process -Id {pid}).MainWindowHandle | "
                             f"ForEach-Object {{ Add-Type -Name Win -Namespace User32 "
                             f'-MemberDefinition \'[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);\' '
                             f'; [User32.Win]::SetForegroundWindow($_) }}'],
                            timeout=5,
                        )
                        return BackendResult(ok=True, method="powershell")
            return BackendResult(ok=False, error=f"Window '{window_title}' not found")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))


# Lazy import fallback
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
