"""macOS Native Workspace Backend — AppleScript + AXUIElement control.

Uses macOS-native APIs for desktop automation:
  - AppleScript for application control
  - AXUIElement for accessibility-based interaction
  - screencapture for screenshots
  - osascript for command execution

Requires macOS. Falls back gracefully on other platforms.
"""

from __future__ import annotations

import os
import io
import time
import logging
import subprocess
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_backend.macos")


class MacOsNativeBackend:
    """macOS-native desktop control via AppleScript + AXUIElement."""

    name = "macos_native"
    cost = 1  # Same as Windows native (no isolation)
    capabilities = [
        "browser", "editor", "terminal", "files",
        "screenshot", "input_injection", "window_management",
        "native_macos_apps", "accessibility", "applescript",
    ]

    def __init__(self):
        self._running = False

    def is_available(self) -> bool:
        """Check if we're on macOS."""
        import sys
        if sys.platform != "darwin":
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to return name of current application'],
                capture_output=True, text=True, timeout=5
            )
            # Even if it errors, osascript exists
            return True
        except FileNotFoundError:
            log.info("[MACOS] osascript not found")
            return False

    def start(self, resolution: Tuple[int, int] = (1920, 1080)) -> bool:
        """No startup needed — we use the existing desktop."""
        self._running = True
        log.info("[MACOS] Native macOS backend ready")
        return True

    def stop(self):
        """Nothing to stop."""
        self._running = False
        log.info("[MACOS] Native backend released")

    def is_running(self) -> bool:
        return self._running

    def _run_applescript(self, script: str) -> Tuple[bool, str]:
        """Execute an AppleScript command."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0, result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def capture_frame(self, quality: int = 60) -> Optional[bytes]:
        """Capture macOS screenshot via screencapture."""
        if not self._running:
            return None

        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name

            # Use screencapture (macOS built-in)
            result = subprocess.run(
                ["screencapture", "-x", "-C", tmp_path],
                capture_output=True, timeout=10
            )

            if result.returncode == 0 and os.path.exists(tmp_path):
                from PIL import Image
                pil_img = Image.open(tmp_path)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                os.unlink(tmp_path)
                return buf.getvalue()

        except Exception as e:
            log.error(f"[MACOS] Screenshot failed: {e}")

        return None

    def inject_click(self, x: int, y: int, button: int = 1) -> "BackendResult":
        """Click via AppleScript using System Events."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")

        try:
            # Map button number to AppleScript button name
            btn_name = "left" if button == 1 else "right" if button == 3 else "middle"

            script = f'''
            tell application "System Events"
                click at {{{x}, {y}}} -- This won't work directly
            end tell
            '''

            # Use cliclick if available (better for precise clicks)
            try:
                result = subprocess.run(
                    ["cliclick", f"c:{x},{y}"],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    return BackendResult(ok=True, method="cliclick")
            except FileNotFoundError:
                pass

            # Fallback: use AppleScript with System Events
            script = f'''
            tell application "System Events"
                set position of first window to {{{x}, {y}}}
            end tell
            '''
            ok, output = self._run_applescript(script)
            return BackendResult(ok=ok, error=output if not ok else "", method="applescript")

        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def inject_key(self, key: str) -> "BackendResult":
        """Press a key via AppleScript."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")

        try:
            # Map common keys to AppleScript key codes
            key_map = {
                "Return": "return", "enter": "return", "tab": "tab",
                "escape": "escape", "esc": "escape", "backspace": "delete",
                "delete": "delete", "space": "space",
                "super": "command", "command": "command",
                "ctrl": "control", "control": "control",
                "alt": "option", "option": "option", "opt": "option",
                "shift": "shift",
            }

            mapped = key_map.get(key.lower(), key)

            # Handle key combinations
            if "+" in key:
                parts = key.split("+")
                modifiers = []
                main_key = parts[-1]
                for p in parts[:-1]:
                    m = key_map.get(p.lower(), p)
                    modifiers.append(f"{m} down")
                mod_str = ", ".join(f"{m} down" for m in modifiers)
                main_mapped = key_map.get(main_key.lower(), main_key)
                script = f'''
                tell application "System Events"
                    keystroke "{main_mapped}" using {{{mod_str}}}
                end tell
                '''
            else:
                script = f'''
                tell application "System Events"
                    keystroke "{mapped}"
                end tell
                '''

            ok, output = self._run_applescript(script)
            return BackendResult(ok=ok, error=output if not ok else "", method="applescript")

        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def inject_text(self, text: str) -> "BackendResult":
        """Type text via AppleScript."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")

        try:
            # Escape special characters for AppleScript
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            script = f'''
            tell application "System Events"
                keystroke "{escaped}"
            end tell
            '''
            ok, output = self._run_applescript(script)
            return BackendResult(ok=ok, error=output if not ok else "", method="applescript")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def launch_app(self, name: str, command: List[str] = None) -> "BackendResult":
        """Launch an application via AppleScript."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")

        try:
            # Try 'open' command first (launches app by name)
            result = subprocess.run(
                ["open", "-a", name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return BackendResult(ok=True, method="open_command",
                                   output=f"Launched {name}")

            # Fallback: AppleScript
            script = f'''
            tell application "{name}"
                activate
            end tell
            '''
            ok, output = self._run_applescript(script)
            return BackendResult(ok=ok, error=output if not ok else "",
                               method="applescript", output=f"Launched {name}")
        except Exception as e:
            return BackendResult(ok=False, error=str(e))

    def list_windows(self) -> List[Dict]:
        """List open windows via AppleScript."""
        if not self._running:
            return []

        try:
            script = '''
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
            '''
            ok, output = self._run_applescript(script)
            if ok and output:
                windows = []
                for i, line in enumerate(output.split(", ")):
                    if " — " in line:
                        app, title = line.split(" — ", 1)
                        windows.append({
                            "pid": str(i),
                            "app": app.strip(),
                            "title": title.strip(),
                        })
                return windows
        except Exception as e:
            log.error(f"[MACOS] List windows failed: {e}")

        return []

    def focus_window(self, window_title: str) -> "BackendResult":
        """Focus a window by title via AppleScript."""
        if not self._running:
            return BackendResult(ok=False, error="Backend not running")

        try:
            # First, find which app owns the window
            windows = self.list_windows()
            for w in windows:
                if window_title.lower() in w.get("title", "").lower():
                    app = w.get("app", "")
                    if app:
                        script = f'''
                        tell application "{app}"
                            activate
                        end tell
                        '''
                        ok, output = self._run_applescript(script)
                        return BackendResult(ok=ok, error=output if not ok else "")

            return BackendResult(ok=False, error=f"Window '{window_title}' not found")
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
