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

    def navigate(self, url):
        """Navigate to a URL."""
        if not url.startswith("http"):
            url = "https://" + url
        result = self._send("Page.navigate", {"url": url})
        time.sleep(3)
        return result

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
        if self.ws:
            try: self.ws.close()
            except: pass
        if self.chrome_proc:
            self.chrome_proc.terminate()
            self.chrome_proc.wait(timeout=5)


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
