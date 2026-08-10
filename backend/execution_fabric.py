"""JARVIS Execution Fabric — Tool Execution Layer.

Executes actions using the best available method:
Level 1: Native API (Python, CLI)
Level 2: Application automation (CDP, DOM)
Level 3: CLI (bash, PowerShell)
Level 4: Vision (screenshot analysis)
Level 5: Mouse/keyboard (xdotool)

Falls back through levels if higher level fails.
"""

import os, sys, json, subprocess, logging, time, base64
from pathlib import Path

log = logging.getLogger("execution_fabric")

WORKUSER_UID = 1001
DISPLAY = ":99"
VENV = (f"HOME=/home/workuser "
        f"XDG_DATA_HOME=/home/workuser/.local/share "
        f"XDG_CACHE_HOME=/home/workuser/.cache "
        f"DISPLAY={DISPLAY} "
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{WORKUSER_UID}/bus")


class ExecutionResult:
    """Result of an execution attempt."""
    def __init__(self, success: bool, output: str = "", error: str = "",
                 method: str = "", artifacts: list = None):
        self.success = success
        self.output = output
        self.error = error
        self.method = method
        self.artifacts = artifacts or []
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output[:500],
            "error": self.error[:200],
            "method": self.method,
            "artifacts": self.artifacts,
            "timestamp": self.timestamp,
        }


class ExecutionFabric:
    """Executes actions using the best available method."""

    def __init__(self):
        self._methods = [
            self._execute_api,
            self._execute_cli,
            self._execute_vdi_command,
            self._execute_mouse_keyboard,
        ]

    def execute(self, action: str, params: dict = None) -> ExecutionResult:
        """Execute an action using the best available method.

        Tries each method in order:
        1. API (Python import, HTTP request)
        2. CLI (bash command)
        3. VDI command (via sudo to workuser)
        4. Mouse/keyboard (xdotool)
        """
        params = params or {}

        for method in self._methods:
            try:
                result = method(action, params)
                if result and result.success:
                    return result
            except Exception as e:
                log.debug(f"Method {method.__name__} failed: {e}")
                continue

        return ExecutionResult(False, error=f"All methods failed for action: {action}")

    def _execute_api(self, action: str, params: dict) -> ExecutionResult | None:
        """Level 1: Try API/Python execution."""
        if action == "generate_response":
            try:
                from groq_agent import generate as groq_gen
                query = params.get("query", "")
                reply = groq_gen(query, max_tokens=500, temperature=0.7)
                if reply:
                    return ExecutionResult(True, output=reply, method="api")
            except Exception:
                pass

        if action == "exchange_rate":
            try:
                import requests
                from_currency = params.get("from", "GBP")
                to_currency = params.get("to", "USD")
                url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    rate = r.json().get("rates", {}).get(to_currency, 1.0)
                    return ExecutionResult(True, output=str(rate), method="api")
            except Exception:
                pass

        if action == "check_display":
            try:
                result = subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} xdpyinfo | head -1"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return ExecutionResult(True, output=result.stdout.strip(), method="api")
            except Exception:
                pass

        return None

    def _execute_cli(self, action: str, params: dict) -> ExecutionResult | None:
        """Level 2-3: Try CLI execution."""
        if action == "launch_browser":
            url = params.get("url", "about:blank")
            try:
                subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} google-chrome --no-sandbox --disable-gpu '{url}' &"],
                    timeout=10, capture_output=True
                )
                time.sleep(2)
                # Verify Chrome launched
                check = subprocess.run(
                    ["pgrep", "-f", "chrome"],
                    capture_output=True, text=True, timeout=5
                )
                if check.returncode == 0:
                    return ExecutionResult(True, output="Chrome launched", method="cli")
            except Exception:
                pass

        if action == "screenshot":
            try:
                filepath = f"/tmp/screenshot_{int(time.time())}.png"
                subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} scrot -o {filepath}"],
                    timeout=10, capture_output=True
                )
                if Path(filepath).exists():
                    with open(filepath, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    return ExecutionResult(True, output=b64, method="cli",
                                          artifacts=[filepath])
            except Exception:
                pass

        if action == "extract_clipboard":
            try:
                # First select all and copy
                subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} xdotool key ctrl+a && sleep 0.2 && "
                     f"env -i {VENV} xdotool key ctrl+c"],
                    timeout=5, capture_output=True
                )
                time.sleep(0.5)
                # Then read clipboard
                result = subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     "xclip -selection clipboard -o 2>/dev/null | head -500"],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout:
                    return ExecutionResult(True, output=result.stdout, method="cli")
            except Exception:
                pass

        if action == "list_windows":
            try:
                result = subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c", "wmctrl -l"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return ExecutionResult(True, output=result.stdout, method="cli")
            except Exception:
                pass

        return None

    def _execute_vdi_command(self, action: str, params: dict) -> ExecutionResult | None:
        """Level 3-4: Execute commands in VDI context."""
        if action == "vdi_type":
            text = params.get("text", "")
            if text:
                try:
                    escaped = text.replace("'", "'\\''")
                    subprocess.run(
                        ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                         f"env -i {VENV} xdotool type --delay 20 '{escaped}'"],
                        timeout=10, capture_output=True
                    )
                    return ExecutionResult(True, output=f"Typed: {text}", method="vdi")
                except Exception:
                    pass

        if action == "vdi_click":
            x = params.get("x", 0)
            y = params.get("y", 0)
            try:
                subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} xdotool mousemove {x} {y} && sleep 0.05 && xdotool click 1"],
                    timeout=5, capture_output=True
                )
                return ExecutionResult(True, output=f"Clicked ({x},{y})", method="vdi")
            except Exception:
                pass

        if action == "vdi_scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 5)
            button = 5 if direction == "down" else 4
            try:
                for _ in range(amount):
                    subprocess.run(
                        ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                         f"env -i {VENV} xdotool click {button}"],
                        timeout=5, capture_output=True
                    )
                    time.sleep(0.05)
                return ExecutionResult(True, output=f"Scrolled {direction} {amount}x", method="vdi")
            except Exception:
                pass

        if action == "vdi_key":
            key = params.get("key", "Return")
            try:
                subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} xdotool key {key}"],
                    timeout=5, capture_output=True
                )
                return ExecutionResult(True, output=f"Pressed {key}", method="vdi")
            except Exception:
                pass

        if action == "vdi_hotkey":
            keys = params.get("keys", ["ctrl", "t"])
            combo = "+".join(keys)
            try:
                subprocess.run(
                    ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                     f"env -i {VENV} xdotool key {combo}"],
                    timeout=5, capture_output=True
                )
                return ExecutionResult(True, output=f"Hotkey {combo}", method="vdi")
            except Exception:
                pass

        if action == "vdi_open_tab":
            url = params.get("url", "")
            if url:
                try:
                    # Ctrl+T
                    subprocess.run(
                        ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                         f"env -i {VENV} xdotool key ctrl+t"],
                        timeout=5, capture_output=True
                    )
                    time.sleep(0.4)
                    # Type URL
                    escaped = url.replace("'", "'\\''")
                    subprocess.run(
                        ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                         f"env -i {VENV} xdotool type --delay 20 '{escaped}'"],
                        timeout=10, capture_output=True
                    )
                    time.sleep(0.2)
                    # Enter
                    subprocess.run(
                        ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                         f"env -i {VENV} xdotool key Return"],
                        timeout=5, capture_output=True
                    )
                    time.sleep(2)
                    return ExecutionResult(True, output=f"Opened tab: {url[:50]}", method="vdi")
                except Exception:
                    pass

        if action == "vdi_focus_tab":
            wid = params.get("wid", "")
            if wid:
                try:
                    subprocess.run(
                        ["sudo", "-u", f"#{WORKUSER_UID}", "bash", "-c",
                         f"wmctrl -i -a {wid}"],
                        timeout=5, capture_output=True
                    )
                    time.sleep(0.3)
                    return ExecutionResult(True, output=f"Focused tab {wid}", method="vdi")
                except Exception:
                    pass

        return None

    def _execute_mouse_keyboard(self, action: str, params: dict) -> ExecutionResult | None:
        """Level 5: Mouse/keyboard fallback."""
        # Already handled by _execute_vdi_command
        return None


# ── Singleton ──
_fabric = None
def get_execution_fabric() -> ExecutionFabric:
    global _fabric
    if _fabric is None:
        _fabric = ExecutionFabric()
    return _fabric
