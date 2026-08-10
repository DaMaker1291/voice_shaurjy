"""Browser Sandbox Workspace Backend.

Runs an isolated browser instance (Chrome/Chromium) in a separate
profile/sandbox for web automation tasks. Provides DOM access via
CDP (Chrome DevTools Protocol) without interfering with the user's
actual browser.

Use for web-only tasks that don't need a full desktop environment.
"""

from __future__ import annotations

import os
import io
import time
import logging
import subprocess
import tempfile
import json
from typing import Optional, List, Dict, Tuple

log = logging.getLogger("workspace_backend.browser_sandbox")


class BrowserSandboxBackend:
    """Isolated browser workspace with CDP access."""

    name = "browser_sandbox"
    cost = 2  # Moderate cost (lighter than full desktop)
    capabilities = [
        "browser", "web_automation", "dom_access",
        "screenshot", "form_fill", "web_scrape",
        "isolated_browser", "sandboxed",
    ]

    def __init__(self):
        self._running = False
        self._process: Optional[subprocess.Popen] = None
        self._cdp_port = 9222
        self._user_data_dir: Optional[str] = None
        self._browser_type = None  # "chrome" or "chromium"

    def is_available(self) -> bool:
        """Check if Chrome or Chromium is available."""
        for browser in ["google-chrome", "chromium-browser", "chrome"]:
            try:
                result = subprocess.run(
                    [browser, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self._browser_type = browser
                    log.info(f"[BROWSER_SANDBOX] {browser} available")
                    return True
            except Exception:
                continue

        # Check Windows
        if os.name == "nt":
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    self._browser_type = path
                    log.info(f"[BROWSER_SANDBOX] Chrome found at {path}")
                    return True

        log.info("[BROWSER_SANDBOX] No browser found")
        return False

    def start(self, resolution: Tuple[int, int] = (1920, 1080)) -> bool:
        """Start an isolated browser instance with CDP enabled."""
        if not self._browser_type:
            return False

        try:
            # Create isolated user data directory
            self._user_data_dir = tempfile.mkdtemp(prefix="jarvis_browser_")

            # Launch browser with CDP
            cmd = [
                self._browser_type,
                f"--remote-debugging-port={self._cdp_port}",
                f"--user-data-dir={self._user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-translate",
                "--disable-extensions",
                "--disable-default-apps",
                f"--window-size={resolution[0]},{resolution[1]}",
                "--headless=new",
            ]

            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # Wait for CDP to be ready
            time.sleep(2)

            if self._process.poll() is None:
                self._running = True
                self._resolution = resolution
                log.info(f"[BROWSER_SANDBOX] Started on port {self._cdp_port}")
                return True
            else:
                log.error("[BROWSER_SANDBOX] Browser exited immediately")
                return False

        except Exception as e:
            log.error(f"[BROWSER_SANDBOX] Start error: {e}")
            return False

    def stop(self):
        """Stop the browser and clean up."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None

        # Clean up user data directory
        if self._user_data_dir and os.path.exists(self._user_data_dir):
            import shutil
            try:
                shutil.rmtree(self._user_data_dir, ignore_errors=True)
            except Exception:
                pass

        self._running = False
        self._user_data_dir = None
        log.info("[BROWSER_SANDBOX] Stopped")

    def is_running(self) -> bool:
        return self._running and self._process and self._process.poll() is None

    def _cdp_request(self, method: str, params: dict = None) -> Optional[dict]:
        """Send a CDP request via HTTP."""
        import urllib.request
        try:
            # Get the list of targets
            req = urllib.request.Request(
                f"http://localhost:{self._cdp_port}/json"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                targets = json.loads(resp.read())

            if not targets:
                return None

            # Use the first page target
            ws_url = targets[0].get("webSocketDebuggerUrl")
            if not ws_url:
                return None

            # For HTTP-based CDP, we use the /json/protocol endpoint
            # Full WebSocket CDP would require websocket library
            return {"targets": targets, "ws_url": ws_url}

        except Exception as e:
            log.debug(f"[BROWSER_SANDBOX] CDP request failed: {e}")
            return None

    def capture_frame(self, quality: int = 60) -> Optional[bytes]:
        """Capture screenshot via CDP."""
        if not self.is_running():
            return None

        try:
            import urllib.request
            import base64

            # Get targets
            req = urllib.request.Request(
                f"http://localhost:{self._cdp_port}/json"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                targets = json.loads(resp.read())

            if not targets:
                return None

            # Use the screenshot endpoint
            target_id = targets[0].get("id")
            screenshot_url = f"http://localhost:{self._cdp_port}/screenshot/{target_id}"

            req = urllib.request.Request(screenshot_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                img_data = resp.read()

            # Convert PNG to JPEG if needed
            from PIL import Image
            pil_img = Image.open(io.BytesIO(img_data))
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()

        except Exception as e:
            log.error(f"[BROWSER_SANDBOX] Screenshot failed: {e}")
            return None

    def inject_click(self, x: int, y: int, button: int = 1) -> "BackendResult":
        """Click via CDP Input.dispatchMouseEvent."""
        # CDP click requires WebSocket, return fallback
        return BackendResult(
            ok=False,
            error="CDP click requires WebSocket connection",
            method="cdp_http",
        )

    def inject_key(self, key: str) -> "BackendResult":
        """Key press via CDP."""
        return BackendResult(
            ok=False,
            error="CDP key requires WebSocket connection",
            method="cdp_http",
        )

    def inject_text(self, text: str) -> "BackendResult":
        """Type text via CDP."""
        return BackendResult(
            ok=False,
            error="CDP text requires WebSocket connection",
            method="cdp_http",
        )

    def launch_app(self, name: str, command: List[str] = None) -> "BackendResult":
        """Navigate to a URL in the sandboxed browser."""
        if not self.is_running():
            return BackendResult(ok=False, error="Browser not running")

        try:
            import urllib.request
            # Navigate via CDP
            url = command[0] if command else f"https://{name}"
            # Use HTTP endpoint to navigate
            req = urllib.request.Request(
                f"http://localhost:{self._cdp_port}/json/navigate?url={url}",
                method="PUT"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
            return BackendResult(ok=True, method="cdp_http", output=f"Navigated to {url}")
        except Exception as e:
            # Fallback: open URL in default browser
            return BackendResult(ok=False, error=str(e))

    def list_windows(self) -> List[Dict]:
        """List browser tabs."""
        if not self.is_running():
            return []
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://localhost:{self._cdp_port}/json"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                targets = json.loads(resp.read())
            return [
                {"id": t.get("id", ""), "title": t.get("title", ""),
                 "url": t.get("url", ""), "type": t.get("type", "")}
                for t in targets
            ]
        except Exception:
            return []

    def focus_window(self, window_title: str) -> "BackendResult":
        """Focus a browser tab by title."""
        return BackendResult(ok=True, method="cdp_http",
                           output="Browser tabs are always focused")


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
