"""JARVIS Computer Adapter — OS-native computer control.

Platform-specific implementations of ComputerAdapter:
  - WindowsAdapter: Win32 API, UI Automation, PowerShell
  - LinuxAdapter: X11, xdotool, accessibility
  - MacOsAdapter: AppleScript, AXUIElement, screencapture

The Mission Engine never sees these details. It just calls:
    adapter.launch_app("Chrome")
    adapter.click(100, 200)
    adapter.screenshot()
"""

import os
import sys
import io
import time
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

log = logging.getLogger("computer_adapter")

# Import the FabricResult from capability_fabric
try:
    from capability_fabric import FabricResult, ComputerAdapter
except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class FabricResult:
        ok: bool
        output: Any = None
        error: str = ""
        method: str = ""
        duration_ms: float = 0
        metadata: Dict[str, Any] = field(default_factory=dict)

    class ComputerAdapter(ABC):
        @abstractmethod
        def is_available(self) -> bool: ...
        @abstractmethod
        def launch_app(self, name: str, command: List[str] = None) -> FabricResult: ...
        @abstractmethod
        def close_app(self, name: str) -> FabricResult: ...
        @abstractmethod
        def click(self, x: int, y: int, button: str = "left") -> FabricResult: ...
        @abstractmethod
        def type_text(self, text: str) -> FabricResult: ...
        @abstractmethod
        def press_key(self, key: str) -> FabricResult: ...
        @abstractmethod
        def screenshot(self) -> Optional[bytes]: ...
        @abstractmethod
        def list_windows(self) -> List[Dict[str, str]]: ...
        @abstractmethod
        def focus_window(self, title: str) -> FabricResult: ...
        @abstractmethod
        def read_screen(self) -> str: ...
        @abstractmethod
        def execute_command(self, cmd: str) -> FabricResult: ...
        @abstractmethod
        def read_file(self, path: str) -> FabricResult: ...
        @abstractmethod
        def write_file(self, path: str, content: str) -> FabricResult: ...


# ══════════════════════════════════════════════════════════════
#  WINDOWS ADAPTER
# ══════════════════════════════════════════════════════════════

class WindowsAdapter(ComputerAdapter):
    """Windows-native computer control via Win32, UIA, PowerShell."""

    name = "windows"

    def __init__(self):
        self._pyautogui = None
        self._mss = None

    def is_available(self) -> bool:
        return sys.platform == "win32"

    def _ensure_pyautogui(self):
        if self._pyautogui is None:
            try:
                import pyautogui
                self._pyautogui = pyautogui
            except ImportError:
                raise RuntimeError("pyautogui not installed: pip install pyautogui")

    def _ensure_mss(self):
        if self._mss is None:
            try:
                import mss
                self._mss = mss
            except ImportError:
                raise RuntimeError("mss not installed: pip install mss")

    def launch_app(self, name: str, command: List[str] = None) -> FabricResult:
        try:
            cmd = command or [name]
            subprocess.Popen(cmd, shell=True)
            time.sleep(0.5)
            return FabricResult(ok=True, method="subprocess", output=f"Launched {name}")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="subprocess")

    def close_app(self, name: str) -> FabricResult:
        try:
            subprocess.run(["taskkill", "/IM", f"{name}.exe", "/F"],
                         capture_output=True, timeout=5)
            return FabricResult(ok=True, method="taskkill", output=f"Closed {name}")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="taskkill")

    def click(self, x: int, y: int, button: str = "left") -> FabricResult:
        try:
            self._ensure_pyautogui()
            btn = "left" if button == "left" else "right" if button == "right" else "middle"
            self._pyautogui.click(x, y, button=btn)
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="pyautogui")

    def type_text(self, text: str) -> FabricResult:
        try:
            self._ensure_pyautogui()
            self._pyautogui.typewrite(text, interval=0.02)
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="pyautogui")

    def press_key(self, key: str) -> FabricResult:
        try:
            self._ensure_pyautogui()
            key_map = {
                "Return": "enter", "enter": "enter", "tab": "tab",
                "escape": "escape", "esc": "escape", "backspace": "backspace",
                "delete": "delete", "space": "space", "super": "win",
                "super+l": "win+l",
            }
            normalized = key_map.get(key, key)
            if "+" in normalized:
                self._pyautogui.hotkey(*normalized.split("+"))
            else:
                self._pyautogui.press(normalized)
            return FabricResult(ok=True, method="pyautogui")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="pyautogui")

    def screenshot(self) -> Optional[bytes]:
        try:
            self._ensure_mss()
            import mss.tools
            with self._mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                raw = mss.tools.to_png(img.rgb, img.size)
                from PIL import Image
                pil_img = Image.open(io.BytesIO(raw))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=70, optimize=True)
                return buf.getvalue()
        except Exception as e:
            log.error(f"[WINDOWS] Screenshot failed: {e}")
            return None

    def list_windows(self) -> List[Dict[str, str]]:
        try:
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
        except Exception:
            return []

    def focus_window(self, title: str) -> FabricResult:
        try:
            windows = self.list_windows()
            for w in windows:
                if title.lower() in w.get("title", "").lower():
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
                        return FabricResult(ok=True, method="powershell")
            return FabricResult(ok=False, error=f"Window '{title}' not found")
        except Exception as e:
            return FabricResult(ok=False, error=str(e))

    def read_screen(self) -> str:
        try:
            from workspace_verifier import WorkspaceVerifier
            verifier = WorkspaceVerifier()
            return verifier.read_screen_ocr()
        except Exception:
            return ""

    def execute_command(self, cmd: str) -> FabricResult:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30,
            )
            return FabricResult(
                ok=result.returncode == 0,
                output=result.stdout + result.stderr,
                method="powershell",
            )
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="powershell")

    def read_file(self, path: str) -> FabricResult:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return FabricResult(ok=True, output=content, method="filesystem")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="filesystem")

    def write_file(self, path: str, content: str) -> FabricResult:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return FabricResult(ok=True, method="filesystem")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="filesystem")


# ══════════════════════════════════════════════════════════════
#  LINUX ADAPTER
# ══════════════════════════════════════════════════════════════

class LinuxAdapter(ComputerAdapter):
    """Linux computer control via X11, xdotool, subprocess."""

    name = "linux"

    def is_available(self) -> bool:
        return sys.platform == "linux"

    def _has_cmd(self, cmd: str) -> bool:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def launch_app(self, name: str, command: List[str] = None) -> FabricResult:
        try:
            cmd = command or [name]
            subprocess.Popen(cmd)
            time.sleep(0.5)
            return FabricResult(ok=True, method="subprocess", output=f"Launched {name}")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="subprocess")

    def close_app(self, name: str) -> FabricResult:
        try:
            subprocess.run(["pkill", "-f", name], capture_output=True, timeout=5)
            return FabricResult(ok=True, method="pkill")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="pkill")

    def click(self, x: int, y: int, button: str = "left") -> FabricResult:
        if self._has_cmd("xdotool"):
            btn = "1" if button == "left" else "3" if button == "right" else "2"
            try:
                subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", btn],
                             capture_output=True, timeout=5)
                return FabricResult(ok=True, method="xdotool")
            except Exception as e:
                return FabricResult(ok=False, error=str(e), method="xdotool")
        return FabricResult(ok=False, error="No click method available")

    def type_text(self, text: str) -> FabricResult:
        if self._has_cmd("xdotool"):
            try:
                subprocess.run(["xdotool", "type", "--", text],
                             capture_output=True, timeout=10)
                return FabricResult(ok=True, method="xdotool")
            except Exception as e:
                return FabricResult(ok=False, error=str(e), method="xdotool")
        return FabricResult(ok=False, error="No type method available")

    def press_key(self, key: str) -> FabricResult:
        if self._has_cmd("xdotool"):
            try:
                subprocess.run(["xdotool", "key", key],
                             capture_output=True, timeout=5)
                return FabricResult(ok=True, method="xdotool")
            except Exception as e:
                return FabricResult(ok=False, error=str(e), method="xdotool")
        return FabricResult(ok=False, error="No key method available")

    def screenshot(self) -> Optional[bytes]:
        if self._has_cmd("scrot"):
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                subprocess.run(["scrot", "-x", tmp], capture_output=True, timeout=5)
                with open(tmp, "rb") as f:
                    data = f.read()
                os.unlink(tmp)
                return data
            except Exception:
                pass
        # Fallback: mss
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                return mss.tools.to_png(img.rgb, img.size)
        except Exception:
            return None

    def list_windows(self) -> List[Dict[str, str]]:
        if self._has_cmd("wmctrl"):
            try:
                result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=5)
                windows = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append({"pid": parts[0], "title": parts[3]})
                return windows
            except Exception:
                pass
        return []

    def focus_window(self, title: str) -> FabricResult:
        if self._has_cmd("wmctrl"):
            try:
                subprocess.run(["wmctrl", "-a", title], capture_output=True, timeout=5)
                return FabricResult(ok=True, method="wmctrl")
            except Exception as e:
                return FabricResult(ok=False, error=str(e), method="wmctrl")
        return FabricResult(ok=False, error="No focus method available")

    def read_screen(self) -> str:
        try:
            from workspace_verifier import WorkspaceVerifier
            verifier = WorkspaceVerifier()
            return verifier.read_screen_ocr()
        except Exception:
            return ""

    def execute_command(self, cmd: str) -> FabricResult:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30,
            )
            return FabricResult(
                ok=result.returncode == 0,
                output=result.stdout + result.stderr,
                method="shell",
            )
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="shell")

    def read_file(self, path: str) -> FabricResult:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return FabricResult(ok=True, output=f.read(), method="filesystem")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="filesystem")

    def write_file(self, path: str, content: str) -> FabricResult:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return FabricResult(ok=True, method="filesystem")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="filesystem")


# ══════════════════════════════════════════════════════════════
#  macOS ADAPTER
# ══════════════════════════════════════════════════════════════

class MacOsAdapter(ComputerAdapter):
    """macOS computer control via AppleScript, AXUIElement, screencapture."""

    name = "macos"

    def is_available(self) -> bool:
        return sys.platform == "darwin"

    def _run_applescript(self, script: str):
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0, result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def launch_app(self, name: str, command: List[str] = None) -> FabricResult:
        try:
            subprocess.run(["open", "-a", name], capture_output=True, timeout=10)
            return FabricResult(ok=True, method="open_command", output=f"Launched {name}")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="open_command")

    def close_app(self, name: str) -> FabricResult:
        try:
            ok, _ = self._run_applescript(f'''
                tell application "{name}" to quit
            ''')
            return FabricResult(ok=ok, method="applescript")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="applescript")

    def click(self, x: int, y: int, button: str = "left") -> FabricResult:
        try:
            result = subprocess.run(
                ["cliclick", f"c:{x},{y}"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return FabricResult(ok=True, method="cliclick")
        except FileNotFoundError:
            pass
        return FabricResult(ok=False, error="No click method available (install cliclick)")

    def type_text(self, text: str) -> FabricResult:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        ok, _ = self._run_applescript(f'tell application "System Events" to keystroke "{escaped}"')
        return FabricResult(ok=ok, method="applescript")

    def press_key(self, key: str) -> FabricResult:
        key_map = {
            "Return": "return", "enter": "return", "tab": "tab",
            "escape": "escape", "esc": "escape", "backspace": "delete",
            "delete": "delete", "space": "space", "super": "command",
            "command": "command", "ctrl": "control", "control": "control",
            "alt": "option", "option": "option", "shift": "shift",
        }
        mapped = key_map.get(key.lower(), key)
        if "+" in key:
            parts = key.split("+")
            mods = ", ".join(f"{key_map.get(p.lower(), p)} down" for p in parts[:-1])
            main_key = key_map.get(parts[-1].lower(), parts[-1])
            ok, _ = self._run_applescript(f'tell application "System Events" to keystroke "{main_key}" using {{{mods}}}')
        else:
            ok, _ = self._run_applescript(f'tell application "System Events" to keystroke "{mapped}"')
        return FabricResult(ok=ok, method="applescript")

    def screenshot(self) -> Optional[bytes]:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp = f.name
            subprocess.run(["screencapture", "-x", "-C", tmp], capture_output=True, timeout=10)
            if os.path.exists(tmp):
                from PIL import Image
                pil_img = Image.open(tmp)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=70, optimize=True)
                os.unlink(tmp)
                return buf.getvalue()
        except Exception as e:
            log.error(f"[MACOS] Screenshot failed: {e}")
        return None

    def list_windows(self) -> List[Dict[str, str]]:
        try:
            ok, output = self._run_applescript('''
                tell application "System Events"
                    set windowList to {}
                    repeat with proc in (every process whose background only is false)
                        set procName to name of proc
                        repeat with win in (every window of proc)
                            set winTitle to name of win
                            if winTitle is not "" then
                                set end of windowList to procName & " — " & winTitle
                            end if
                        end repeat
                    end repeat
                    return windowList
                end tell
            ''')
            if ok and output:
                windows = []
                for line in output.split(", "):
                    if " — " in line:
                        app, title = line.split(" — ", 1)
                        windows.append({"app": app.strip(), "title": title.strip()})
                return windows
        except Exception:
            pass
        return []

    def focus_window(self, title: str) -> FabricResult:
        windows = self.list_windows()
        for w in windows:
            if title.lower() in w.get("title", "").lower():
                app = w.get("app", "")
                if app:
                    ok, _ = self._run_applescript(f'tell application "{app}" to activate')
                    return FabricResult(ok=ok, method="applescript")
        return FabricResult(ok=False, error=f"Window '{title}' not found")

    def read_screen(self) -> str:
        try:
            from workspace_verifier import WorkspaceVerifier
            verifier = WorkspaceVerifier()
            return verifier.read_screen_ocr()
        except Exception:
            return ""

    def execute_command(self, cmd: str) -> FabricResult:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30,
            )
            return FabricResult(ok=result.returncode == 0, output=result.stdout + result.stderr, method="shell")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="shell")

    def read_file(self, path: str) -> FabricResult:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return FabricResult(ok=True, output=f.read(), method="filesystem")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="filesystem")

    def write_file(self, path: str, content: str) -> FabricResult:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return FabricResult(ok=True, method="filesystem")
        except Exception as e:
            return FabricResult(ok=False, error=str(e), method="filesystem")
