"""CDP Browser Adapter — Chrome DevTools Protocol.

Uses Chrome DevTools Protocol for browser control.
This is API #2 — replaces individual website APIs.

Instead of Booking API + Amazon API + Spotify API,
use the browser itself.
"""

from __future__ import annotations

import os
import io
import json
import logging
import subprocess
import tempfile
from typing import Optional, List

log = logging.getLogger("adapter.cdp")


class CdpBrowserAdapter:
    """Browser control via Chrome DevTools Protocol."""

    def __init__(self):
        self._process = None
        self._cdp_port = 9222
        self._user_data_dir = None
        self._browser_path = None
        self._running = False

    def is_available(self) -> bool:
        """Check if Chrome/Chromium is available."""
        import sys
        if sys.platform == "win32":
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            for p in paths:
                if os.path.exists(p):
                    self._browser_path = p
                    return True
        else:
            for cmd in ["google-chrome", "chromium-browser", "chromium"]:
                try:
                    result = subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                    if result.returncode == 0:
                        self._browser_path = cmd
                        return True
                except Exception:
                    continue
        return False

    def start(self, headless: bool = True):
        """Start Chrome with CDP enabled."""
        if not self._browser_path:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error="No browser found")

        try:
            self._user_data_dir = tempfile.mkdtemp(prefix="jarvis_browser_")
            cmd = [
                self._browser_path,
                f"--remote-debugging-port={self._cdp_port}",
                f"--user-data-dir={self._user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            if headless:
                cmd.append("--headless=new")

            self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            import time
            time.sleep(2)

            if self._process.poll() is None:
                self._running = True
                from capability_fabric import FabricResult
                return FabricResult(ok=True, method="cdp")
            else:
                from capability_fabric import FabricResult
                return FabricResult(ok=False, error="Browser exited immediately")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def stop(self):
        """Stop the browser."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
        self._running = False

    def _cdp_targets(self):
        """Get CDP targets."""
        import urllib.request
        try:
            req = urllib.request.Request(f"http://localhost:{self._cdp_port}/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception:
            return []

    def navigate(self, url: str):
        """Navigate to URL."""
        if not self._running:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error="Browser not running")
        try:
            targets = self._cdp_targets()
            if targets:
                target_id = targets[0].get("id")
                import urllib.request
                req = urllib.request.Request(
                    f"http://localhost:{self._cdp_port}/json/navigate?url={url}",
                    method="PUT"
                )
                urllib.request.urlopen(req, timeout=10)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, method="cdp")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def get_url(self) -> str:
        """Get current URL."""
        targets = self._cdp_targets()
        if targets:
            return targets[0].get("url", "")
        return ""

    def get_title(self) -> str:
        """Get current page title."""
        targets = self._cdp_targets()
        if targets:
            return targets[0].get("title", "")
        return ""

    def screenshot(self):
        """Screenshot the current page."""
        if not self._running:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error="Browser not running")
        try:
            import urllib.request
            targets = self._cdp_targets()
            if not targets:
                from capability_fabric import FabricResult
                return FabricResult(ok=False, error="No targets")
            target_id = targets[0].get("id")
            req = urllib.request.Request(
                f"http://localhost:{self._cdp_port}/screenshot/{target_id}"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                img_data = resp.read()
            from PIL import Image
            pil_img = Image.open(io.BytesIO(img_data))
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=70, optimize=True)
            from capability_fabric import FabricResult
            return FabricResult(ok=True, data=buf.getvalue(), method="cdp")
        except Exception as e:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error=str(e))

    def get_dom(self):
        """Get DOM content via JavaScript."""
        return self.execute_js("document.documentElement.outerHTML")

    def get_text(self):
        """Extract all visible text."""
        return self.execute_js("""
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null, false
            );
            let text = [];
            while(walker.nextNode()) {
                const t = walker.currentNode.textContent.trim();
                if(t) text.push(t);
            }
            text.join('\\n');
        """)

    def click_element(self, selector: str):
        """Click element by CSS selector."""
        return self.execute_js(f"document.querySelector('{selector}')?.click()")

    def click_text(self, text: str):
        """Click element containing text."""
        return self.execute_js(f"""
            const els = document.querySelectorAll('*');
            for(const el of els) {{
                if(el.textContent.includes('{text}')) {{
                    el.click();
                    break;
                }}
            }}
        """)

    def type_into(self, selector: str, text: str):
        """Type into an input field."""
        return self.execute_js(f"""
            const el = document.querySelector('{selector}');
            if(el) {{
                el.value = '{text}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        """)

    def select_option(self, selector: str, value: str):
        """Select dropdown option."""
        return self.execute_js(f"""
            const el = document.querySelector('{selector}');
            if(el) {{
                el.value = '{value}';
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        """)

    def scroll(self, direction: str = "down", amount: int = 3):
        """Scroll the page."""
        pixels = amount * 300
        if direction == "up":
            pixels = -pixels
        return self.execute_js(f"window.scrollBy(0, {pixels})")

    def execute_js(self, script: str):
        """Execute JavaScript in page context."""
        if not self._running:
            from capability_fabric import FabricResult
            return FabricResult(ok=False, error="Browser not running")
        # CDP JS execution requires WebSocket; return placeholder
        from capability_fabric import FabricResult
        return FabricResult(ok=False, error="CDP JS requires WebSocket connection")

    def wait_for(self, selector: str, timeout: int = 10):
        """Wait for element to appear."""
        return self.execute_js(f"""
            new Promise((resolve) => {{
                const check = () => {{
                    const el = document.querySelector('{selector}');
                    if(el) resolve(true);
                    else setTimeout(check, 500);
                }};
                check();
                setTimeout(() => resolve(false), {timeout * 1000});
            }})
        """)

    def search(self, query: str, engine: str = "google"):
        """Search using a search engine."""
        engines = {
            "google": f"https://www.google.com/search?q={query}",
            "bing": f"https://www.bing.com/search?q={query}",
            "duckduckgo": f"https://duckduckgo.com/?q={query}",
        }
        url = engines.get(engine, engines["google"])
        return self.navigate(url)

    def extract_links(self):
        """Extract all links from the page."""
        return self.execute_js("""
            Array.from(document.querySelectorAll('a[href]')).map(a => ({
                text: a.textContent.trim(),
                href: a.href
            }))
        """)

    def extract_structured(self, schema: str = ""):
        """Extract structured data from the page."""
        return self.execute_js("""
            const data = {};
            const meta = document.querySelectorAll('meta[property], meta[name]');
            meta.forEach(m => {
                const key = m.getAttribute('property') || m.getAttribute('name');
                const val = m.getAttribute('content');
                if(key && val) data[key] = val;
            });
            data;
        """)
