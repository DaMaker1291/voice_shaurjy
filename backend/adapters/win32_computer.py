"""Windows Computer Adapter — Win32 + UIA + PowerShell.

Uses native Windows APIs for desktop control:
  - pyautogui / mss for screenshots
  - Win32 SendInput for mouse/keyboard
  - Windows UI Automation for accessibility
  - PowerShell for app management and commands
  - ctypes for native Win32 calls

No external API required — all local OS mechanisms.
"""

from __future__ import annotations

import os
import io
import sys
import time
import logging
import subprocess
import ctypes
from typing import Optional, List, Tuple

log = logging.getLogger("adapter.win32")

# Only load on Windows
if sys.platform != "win32":
    raise ImportError("Win32 adapter only available on Windows")


class Win32ComputerAdapter:
    """Windows-native computer control."""

    def __init__(self):
        self._pyautogui = None
        self._mss = None

    def is_available(self) -> bool:
        """Check if we're on Windows with required tools."""
        if sys.platform != "win32":
            return False
        try:
            import pyautogui
            import mss
            self._pyautogui = pyautogui
            self._mss = mss
            return True
        except ImportError:
            log.info("[WIN32] Missing pyautogui or mss")
            return False

    def screenshot(self):
        """Capture screen via mss (fast, direct GPU capture)."""
        try:
            with self._mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                raw = self._mss.tools.to_png(img.rgb, img.size)
                from PIL import Image
                pil_img = Image.open(io.BytesIO(raw))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=70, optimize=True)
                from capability_fabric import FabricResult
                return FabricResult(ok=True, data=buf.getvalue(), method="mss")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e), method="mss")

    def click(self, x: int, y: int, button: str = "left"):
        """Click via pyautogui (uses Win32 SendInput internally)."""
        try:
            btn = "left" if button == "left" else "right" if button == "right" else "middle"
            self._pyautogui.click(x, y, button=btn)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def type_text(self, text: str):
        """Type text via pyautogui."""
        try:
            self._pyautogui.typewrite(text, interval=0.02)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def press_key(self, key: str):
        """Press a key via pyautogui."""
        try:
            key_map = {
                "Return": "enter", "enter": "enter", "tab": "tab",
                "escape": "escape", "esc": "escape", "backspace": "backspace",
                "delete": "delete", "space": "space", "super": "win",
            }
            normalized = key_map.get(key.lower(), key)
            if "+" in normalized:
                self._pyautogui.hotkey(*normalized.split("+"))
            else:
                self._pyautogui.press(normalized)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def move_mouse(self, x: int, y: int):
        """Move mouse via pyautogui."""
        try:
            self._pyautogui.moveTo(x, y)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def launch_app(self, name: str, args: List[str] = None):
        """Launch app via ShellExecute (native Win32)."""
        try:
            cmd = args or [name]
            subprocess.Popen(cmd, shell=True)
            time.sleep(1)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="shell_execute", output=f"Launched {name}")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def close_app(self, name: str):
        """Close app via taskkill."""
        try:
            result = subprocess.run(
                ["taskkill", "/IM", f"{name}.exe", "/F"],
                capture_output=True, text=True, timeout=5
            )
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="taskkill")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def list_windows(self):
        """List windows via PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object Id, MainWindowTitle, ProcessName | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5
            )
            import json
            data = json.loads(result.stdout or "[]")
            if isinstance(data, dict):
                data = [data]
            from capability_fabric import WindowInfo, FabricResult
            windows = [
                WindowInfo(
                    id=str(p.get("Id", "")),
                    title=p.get("MainWindowTitle", ""),
                    app=p.get("ProcessName", ""),
                    pid=p.get("Id", 0),
                )
                for p in data
            ]
            return FabricResult(ok=True, data=windows, method="powershell")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def focus_window(self, title: str):
        """Focus window via PowerShell + Win32 SetForegroundWindow."""
        try:
            windows_result = self.list_windows()
            if windows_result.ok:
                for w in windows_result.data:
                    if title.lower() in w.title.lower():
                        # Use PowerShell to focus
                        subprocess.run(
                            ["powershell", "-Command",
                             f"(Get-Process -Id {w.pid}).MainWindowHandle | "
                             f"ForEach-Object {{ Add-Type -Name Win -Namespace User32 "
                             f"-MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);' "
                             f"; [User32.Win]::SetForegroundWindow($_) }}"],
                            timeout=5,
                        )
                        from capability_fabric import FabricResult
                        return FabricResult(ok=True, method="powershell")
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=f"Window '{title}' not found")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def get_screen_state(self):
        """Get full screen state."""
        from capability_fabric import ScreenState
        ss_result = self.screenshot()
        win_result = self.list_windows()
        return ScreenState(
            screenshot_bytes=ss_result.data if ss_result.ok else b"",
            width=1920, height=1080,
            all_windows=win_result.data if win_result.ok else [],
        )

    def execute_command(self, cmd: str, timeout: int = 30):
        """Execute via PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, timeout=timeout
            )
            from capability_fabric import FabricResult
            return FabricResult(
                ok=result.returncode == 0,
                data=result.stdout,
                error=result.stderr,
                method="powershell",
            )
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def read_file(self, path: str):
        """Read file from filesystem."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            from capability_fabric import FabricResult
            return FabricResult(ok=True, data=content, method="filesystem")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def write_file(self, path: str, content: str):
        """Write file to filesystem."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="filesystem")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def list_directory(self, path: str):
        """List directory contents."""
        try:
            entries = []
            for entry in os.scandir(path):
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0,
                })
            from capability_fabric import FabricResult
            return FabricResult(ok=True, data=entries, method="filesystem")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))
