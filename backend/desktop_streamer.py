"""
Desktop Streamer — Always-on stream from a desktop to the Electron app.

Two capture sources:
  source="cdp"    -> Playwright/CDP browser screenshots (existing behavior)
  source="screen" -> OS-level screen capture via mss (shows the CURRENTLY
                     VISIBLE desktop, e.g. Virtual Desktop #2 when active)

Broadcasts JPEG frames via WebSocket. Auto-reconnects on failure.
"""

import os
import io
import json
import time
import base64
import logging
import threading
from typing import Optional

log = logging.getLogger("jarvis-streamer")


class DesktopStreamer:
    """Always-on streamer. Attach to a browser session or the OS screen."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._clients = []
        self._lock = threading.Lock()
        self._fps = 2
        self._quality = 40
        self._cdp_port = None
        self._browser = None
        self._source = "cdp"

    def start(self, cdp_port: int = 9223, fps: int = 2, quality: int = 40,
              source: str = "cdp"):
        """Start or restart streaming. Idempotent — safe to call multiple times."""
        self._cdp_port = cdp_port
        self._fps = fps
        self._quality = quality
        self._source = source or "cdp"

        # Get browser instance (only needed for cdp source)
        self._browser = None
        if self._source == "cdp":
            try:
                from cdp_browser import get_browser
                self._browser = get_browser()
            except Exception as e:
                log.debug(f"Could not get browser: {e}")

        if self._running:
            return  # Already streaming

        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        log.info(f"[STREAMER] Streaming source={self._source} cdp={cdp_port} @ {fps}fps")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("[STREAMER] Stopped")

    def add_client(self, websocket):
        with self._lock:
            self._clients.append(websocket)
            log.info(f"[STREAMER] +1 client ({len(self._clients)} total)")

    def remove_client(self, websocket):
        with self._lock:
            if websocket in self._clients:
                self._clients.remove(websocket)
                log.info(f"[STREAMER] -1 client ({len(self._clients)} total)")

    def _stream_loop(self):
        """Main loop: capture -> encode -> broadcast. Auto-reconnects on failure."""
        interval = 1.0 / self._fps
        consecutive_failures = 0

        while self._running:
            start = time.time()

            # Auto-reconnect if browser dropped (cdp source only)
            if (self._source == "cdp" and self._browser
                    and not self._browser._connected and self._cdp_port):
                consecutive_failures += 1
                if consecutive_failures > 5:
                    log.info("[STREAMER] Attempting reconnect...")
                    try:
                        self._browser.connect_to_duplicate(port=self._cdp_port)
                        consecutive_failures = 0
                        log.info("[STREAMER] Reconnected")
                    except Exception:
                        pass

            try:
                frame = self._capture_frame()
                if frame:
                    consecutive_failures = 0
                    b64 = base64.b64encode(frame).decode()
                    msg = json.dumps({"type": "frame", "data": b64, "ts": time.time()})
                    with self._lock:
                        dead = []
                        for ws in self._clients:
                            try:
                                ws.send_text(msg)
                            except Exception:
                                dead.append(ws)
                        for ws in dead:
                            self._clients.remove(ws)
                else:
                    consecutive_failures += 1
            except Exception as e:
                log.debug(f"Stream frame error: {e}")
                consecutive_failures += 1

            elapsed = time.time() - start
            time.sleep(max(0, interval - elapsed))

    def _capture_frame(self) -> Optional[bytes]:
        """Capture a single JPEG frame from the selected source."""
        if self._source == "screen":
            return self._capture_screen()
        if self._browser and self._browser._connected:
            try:
                return self._browser.capture_screenshot(quality=self._quality)
            except Exception as e:
                log.debug(f"Frame capture error: {e}")
        return None

    def _capture_screen(self) -> Optional[bytes]:
        """Capture the currently visible screen (mss) as JPEG."""
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary monitor = active visible desktop
                sct_img = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self._quality)
                return buf.getvalue()
        except Exception as e:
            log.debug(f"Screen capture error: {e}")
            return None

    def capture_once(self, cdp_port: int = None, quality: int = 50,
                     source: str = None) -> Optional[bytes]:
        """Capture a single frame on demand."""
        src = source or self._source or "cdp"
        if src == "screen":
            return self._capture_screen()
        if self._browser and self._browser._connected:
            try:
                return self._browser.capture_screenshot(quality=quality)
            except Exception:
                pass
        return None


_streamer = None

def get_streamer() -> DesktopStreamer:
    global _streamer
    if _streamer is None:
        _streamer = DesktopStreamer()
    return _streamer
