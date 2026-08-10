#!/usr/bin/env python3
"""
Headless Browser Controller for JARVIS
Uses Chrome DevTools Protocol — no Xvfb needed on macOS.
Runs browser automation in the background without hijacking user's mouse/keyboard.
"""
import subprocess
import json
import time
import os
import sys
import threading
import websocket
import urllib.request

class HeadlessBrowser:
    """Control Chrome/Safari in headless mode via DevTools Protocol."""

    def __init__(self):
        self.chrome_proc = None
        self.ws = None
        self.debug_url = None
        self._msg_id = 0
        self._responses = {}
        self._events = []
        self._listener_thread = None
        self._running = False

    def start(self, headless=True):
        """Launch Chrome with remote debugging enabled."""
        # Find Chrome
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
        ]
        chrome_bin = None
        for p in chrome_paths:
            if os.path.exists(p):
                chrome_bin = p
                break

        if not chrome_bin:
            return {"error": "Chrome not found. Install Google Chrome."}

        # User data dir for persistent sessions
        user_data = os.path.expanduser("~/.jarvis_chrome_profile")
        os.makedirs(user_data, exist_ok=True)

        args = [
            chrome_bin,
            f"--user-data-dir={user_data}",
            "--remote-debugging-port=9222",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--disable-extensions",
        ]
        if headless:
            args.append("--headless=new")
            args.append("--disable-gpu")

        self.chrome_proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

        # Connect via DevTools Protocol
        try:
            resp = urllib.request.urlopen("http://localhost:9222/json").read()
            tabs = json.loads(resp)
            if tabs:
                self.debug_url = tabs[0].get("webSocketDebuggerUrl")
                if self.debug_url:
                    self.ws = websocket.create_connection(self.debug_url)
                    self._running = True
                    self._listener_thread = threading.Thread(target=self._listen, daemon=True)
                    self._listener_thread.start()
                    # Register with browser manager
                    try:
                        from browser_manager import get_browser_manager
                        get_browser_manager().register_browser(str(self.chrome_proc.pid), {"port": 9222})
                    except: pass
                    return {"status": "connected", "pid": self.chrome_proc.pid}
        except Exception as e:
            return {"error": f"Failed to connect: {e}"}

        return {"error": "Could not get WebSocket URL"}

    def _listen(self):
        """Background listener for DevTools messages."""
        while self._running and self.ws:
            try:
                data = self.ws.recv()
                msg = json.loads(data)
                if "id" in msg:
                    self._responses[msg["id"]] = msg
                elif "method" in msg:
                    self._events.append(msg)
            except:
                break

    def _send(self, method, params=None):
        """Send a DevTools command and wait for response."""
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))

        # Wait for response (up to 30s)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self._msg_id in self._responses:
                resp = self._responses.pop(self._msg_id)
                return resp.get("result", {})
            time.sleep(0.1)
        return {"error": "Timeout"}

    def navigate(self, url, retries=2):
        """Navigate to a URL with retry logic."""
        if not url.startswith("http"):
            url = "https://" + url

        for attempt in range(retries + 1):
            try:
                # Check if browser is still alive
                if not self._is_alive():
                    self._auto_restart()
                    if not self._is_alive():
                        return {"error": "Browser crashed and could not restart"}

                result = self._send("Page.navigate", {"url": url})
                time.sleep(3)

                # Check for navigation errors
                if "error" in result:
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                    return result

                # Check page load status
                status = self.evaluate("document.readyState")
                if status == "complete":
                    return result
                elif attempt < retries:
                    time.sleep(3)
                    continue

                return result
            except Exception as e:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                return {"error": f"Navigation failed: {e}"}

        return {"error": "Navigation failed after all retries"}

    def get_text(self):
        """Get all visible text from the page."""
        js = "document.body.innerText"
        result = self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True
        })
        return result.get("result", {}).get("value", "")

    def get_html(self):
        """Get page HTML."""
        js = "document.documentElement.outerHTML"
        result = self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True
        })
        return result.get("result", {}).get("value", "")

    def screenshot(self, path="/tmp/jarvis_headless.png"):
        """Take a screenshot of the headless browser."""
        result = self._send("Page.captureScreenshot", {"format": "png"})
        if "data" in result:
            import base64
            with open(path, "wb") as f:
                f.write(base64.b64decode(result["data"]))
            return path
        return None

    def click(self, selector):
        """Click an element by CSS selector."""
        js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            if (el) {{ el.click(); return 'clicked'; }}
            return 'not found';
        }})()
        """
        result = self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True
        })
        return result.get("result", {}).get("value", "")

    def type_text(self, text):
        """Type text into the focused element."""
        for char in text:
            self._send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char,
                "key": char,
            })
            self._send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": char,
            })
            time.sleep(0.02)

    def press_key(self, key):
        """Press a key (Enter, Tab, Escape, etc)."""
        key_map = {
            "enter": "\r",
            "tab": "\t",
            "escape": "\x1b",
            "space": " ",
        }
        char = key_map.get(key.lower(), key)
        self._send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "text": char,
            "key": char,
        })
        self._send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": char,
        })

    def evaluate(self, js_code):
        """Execute arbitrary JavaScript."""
        result = self._send("Runtime.evaluate", {
            "expression": js_code,
            "returnByValue": True,
            "awaitPromise": True,
        })
        return result.get("result", {}).get("value", "")

    def find_text(self, search_text):
        """Find if text exists on page and return its context."""
        js = f"""
        (function() {{
            var body = document.body.innerText;
            var idx = body.toLowerCase().indexOf('{search_text.lower()}');
            if (idx === -1) return JSON.stringify({{found: false}});
            var start = Math.max(0, idx - 100);
            var end = Math.min(body.length, idx + 100);
            return JSON.stringify({{
                found: true,
                context: body.substring(start, end),
                position: idx
            }});
        }})()
        """
        result = self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        val = result.get("result", {}).get("value", "{}")
        try:
            return json.loads(val)
        except:
            return {"found": False}

    def scroll_down(self):
        """Scroll down the page."""
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": 400,
            "y": 300,
            "deltaX": 0,
            "deltaY": 300,
        })

    def get_links(self):
        """Get all links on the page."""
        js = """
        Array.from(document.querySelectorAll('a[href]')).map(a => ({
            text: a.innerText.trim().substring(0, 100),
            href: a.href
        })).filter(a => a.text.length > 0).slice(0, 50)
        """
        result = self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        return result.get("result", {}).get("value", [])

    def stop(self):
        """Stop the headless browser."""
        self._running = False
        # Unregister from browser manager
        try:
            from browser_manager import get_browser_manager
            if self.chrome_proc:
                get_browser_manager().unregister_browser(str(self.chrome_proc.pid))
        except: pass
        if self.ws:
            try: self.ws.close()
            except: pass
        if self.chrome_proc:
            try:
                self.chrome_proc.terminate()
                self.chrome_proc.wait(timeout=5)
            except:
                try: self.chrome_proc.kill()
                except: pass

    def _is_alive(self) -> bool:
        """Check if browser process is still alive."""
        if self.chrome_proc is None:
            return False
        if self.chrome_proc.poll() is not None:
            return False
        # Check WebSocket
        if self.ws:
            try:
                self.ws.ping()
                return True
            except:
                return False
        return True

    def _auto_restart(self):
        """Auto-restart the browser after a crash."""
        try:
            self.stop()
        except:
            pass
        time.sleep(2)
        try:
            self.start(headless=True)
        except:
            pass

    def safe_navigate(self, url: str) -> dict:
        """Navigate with full error handling and recovery."""
        try:
            if not self._is_alive():
                self._auto_restart()
            return self.navigate(url)
        except Exception as e:
            return {"error": f"Safe navigate failed: {e}"}

    def safe_click(self, selector: str) -> str:
        """Click with retry and alternative selectors."""
        # Try original selector
        result = self.click(selector)
        if result == "clicked":
            return "clicked"

        # Try common alternatives
        alt_selectors = [
            selector.replace("[", "[aria-label='").replace("]", "']"),
            selector.replace("input", "textarea"),
            f"button:has-text('{selector}')",
            f"[data-testid='{selector}']",
        ]
        for alt in alt_selectors:
            try:
                result = self.click(alt)
                if result == "clicked":
                    return "clicked"
            except:
                continue

        return "not found"

    def safe_type(self, selector: str, text: str) -> dict:
        """Type into an element with retry and fallback."""
        # Click to focus first
        click_result = self.safe_click(selector)
        if click_result == "clicked":
            self.type_text(text)
            return {"status": "typed"}

        # Fallback: use JavaScript to set value
        js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            if (!el) {{
                // Try finding by placeholder text
                var inputs = document.querySelectorAll('input, textarea');
                for (var i = 0; i < inputs.length; i++) {{
                    if (inputs[i].placeholder && inputs[i].placeholder.toLowerCase().includes('{selector.toLowerCase()}')) {{
                        el = inputs[i];
                        break;
                    }}
                }}
            }}
            if (el) {{
                el.focus();
                el.value = '{text}';
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                return 'typed';
            }}
            return 'not found';
        }})()
        """
        result = self.evaluate(js)
        return {"status": result if result else "failed"}


# ── Singleton ────────────────────────────────────────────────────────
_browser = None

def get_browser():
    global _browser
    if _browser is None:
        _browser = HeadlessBrowser()
    return _browser

def ensure_browser():
    b = get_browser()
    if b.chrome_proc is None or b.chrome_proc.poll() is not None:
        result = b.start(headless=True)
        if "error" in result:
            return None, result["error"]
    return b, None
