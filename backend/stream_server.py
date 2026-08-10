"""
JARVIS Stream Server — WebSocket screen capture + HTML viewer.
Streams the desktop to a browser tab so the user can watch the agent work.

Usage:
  python stream_server.py              # Start stream server on localhost:8765
  python stream_server.py --port 9000  # Custom port

Then open http://localhost:8765 in any browser to watch.
"""
import asyncio
import base64
import io
import json
import os
import sys
import time
import threading
import logging

logging.basicConfig(level=logging.INFO, format="[STREAM] %(message)s")
logger = logging.getLogger("stream")

try:
    import websockets
    import websockets.server
except ImportError:
    logger.error("pip install websockets")
    sys.exit(1)

try:
    from mss import mss
    from PIL import Image
except ImportError:
    logger.error("pip install mss Pillow")
    sys.exit(1)

import ctypes
import ctypes.wintypes as wintypes

# ── Win32 screen capture via GDI (captures actual desktop, not just primary monitor) ──
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

SRCCOPY = 0x00CC0020
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def capture_screen_gdi() -> bytes | None:
    """Capture screen using Win32 GDI. Returns PNG bytes."""
    try:
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        hscreen = user32.GetDC(0)
        hmemdc = gdi32.CreateCompatibleDC(hscreen)
        hbmp = gdi32.CreateCompatibleBitmap(hscreen, w, h)
        gdi32.SelectObject(hmemdc, hbmp)
        gdi32.BitBlt(hmemdc, 0, 0, w, h, hscreen, 0, 0, SRCCOPY)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hmemdc, hbmp, 0, h, buf, ctypes.byref(bmi), BI_RGB)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hmemdc)
        user32.ReleaseDC(0, hscreen)
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
        img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=60)
        return out.getvalue()
    except Exception as e:
        logger.error(f"GDI capture failed: {e}")
        return None


def capture_screen_mss() -> bytes | None:
    """Fallback: capture using mss."""
    try:
        with mss() as sct:
            shot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=60)
            return out.getvalue()
    except Exception as e:
        logger.error(f"mss capture failed: {e}")
        return None


def capture_screen() -> bytes | None:
    """Capture screen — try GDI first, fall back to mss."""
    return capture_screen_gdi() or capture_screen_mss()


# ── VDI Frame Source ──
_vdi_capturer = None
_capture_mode = "desktop"  # "desktop" or "vdi"


def set_vdi_source(capturer):
    """Set a VDI/VM frame capturer as the source."""
    global _vdi_capturer, _capture_mode
    _vdi_capturer = capturer
    _capture_mode = "vdi"
    logger.info("Stream source: VM/VDI")


def set_vm_source(vm_name: str):
    """Set a VirtualBox VM as the stream source."""
    try:
        from vm_stream import VMFrameCapturer
        capturer = VMFrameCapturer(vm_name)
        capturer.start()
        set_vdi_source(capturer)
        return capturer
    except Exception as e:
        logger.error(f"Failed to set VM source: {e}")
        return None


def set_desktop_source():
    """Revert to desktop capture."""
    global _vdi_capturer, _capture_mode
    if _vdi_capturer and hasattr(_vdi_capturer, "stop"):
        _vdi_capturer.stop()
    _vdi_capturer = None
    _capture_mode = "desktop"
    logger.info("Stream source: local desktop")


def get_stream_status() -> dict:
    """Get current stream status."""
    return {
        "source": _capture_mode,
        "viewers": len(_viewers),
        "log_entries": len(_step_log),
    }


def capture_frame() -> bytes | None:
    """Capture a frame from the current source (VDI or desktop)."""
    if _capture_mode == "vdi" and _vdi_capturer:
        return _vdi_capturer.get_latest_frame()
    return capture_screen()


# ── HTML Viewer ──
VIEWER_HTML = """<!DOCTYPE html>
<html>
<head>
<title>JARVIS Live Stream</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0a1a; color: #c9d1d9; font-family: Consolas, monospace; }
  #header { background: #161b22; padding: 12px 20px; border-bottom: 1px solid #30363d;
            display: flex; align-items: center; gap: 20px; }
  #header h1 { color: #00ff88; font-size: 16px; }
  #status { color: #8b949e; font-size: 13px; }
  #fps { color: #58a6ff; font-size: 13px; }
  #screen { display: flex; justify-content: center; align-items: center;
            min-height: calc(100vh - 50px); padding: 10px; }
  #screen img { max-width: 100%; max-height: calc(100vh - 70px); border: 1px solid #30363d;
                border-radius: 4px; background: #000; }
  #log { position: fixed; bottom: 0; left: 0; right: 0; height: 150px; overflow-y: auto;
         background: rgba(13,17,23,0.95); border-top: 1px solid #30363d; padding: 8px 16px;
         font-size: 11px; color: #8b949e; }
  .log-entry { margin: 2px 0; }
  .log-done { color: #3fb950; }
  .log-fail { color: #f85149; }
  .log-info { color: #58a6ff; }
</style>
</head>
<body>
<div id="header">
  <h1>JARVIS LIVE</h1>
  <span id="status">Connecting...</span>
  <span id="fps"></span>
</div>
<div id="screen">
  <img id="frame" src="" alt="Waiting for stream...">
</div>
<div id="log"></div>
<script>
const img = document.getElementById('frame');
const statusEl = document.getElementById('status');
const fpsEl = document.getElementById('fps');
const logEl = document.getElementById('log');
let frameCount = 0, lastFpsTime = Date.now();

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { statusEl.textContent = 'Connected'; statusEl.style.color = '#3fb950'; };
  ws.onclose = () => { statusEl.textContent = 'Disconnected — reconnecting...'; statusEl.style.color = '#f85149'; setTimeout(connect, 2000); };
    ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'frame') {
      img.src = 'data:image/jpeg;base64,' + data.data;
      frameCount++;
      const now = Date.now();
      if (now - lastFpsTime >= 1000) {
        fpsEl.textContent = frameCount + ' fps';
        frameCount = 0;
        lastFpsTime = now;
      }
    } else if (data.type === 'status') {
      const src = data.source === 'vdi' ? 'VM' : 'Local';
      statusEl.textContent = `Connected (${src})`;
      statusEl.style.color = '#3fb950';
    } else if (data.type === 'log') {
      const div = document.createElement('div');
      div.className = 'log-entry ' + (data.level || '');
      div.textContent = data.message;
      logEl.appendChild(div);
      logEl.scrollTop = logEl.scrollHeight;
    } else if (data.type === 'step') {
      const div = document.createElement('div');
      div.className = 'log-entry ' + (data.status === 'done' ? 'log-done' : data.status === 'failed' ? 'log-fail' : 'log-info');
      div.textContent = `[${data.status}] ${data.action}: ${(data.result || '').substring(0, 200)}`;
      logEl.appendChild(div);
      logEl.scrollTop = logEl.scrollHeight;
    }
  };
}
connect();
</script>
</body>
</html>"""

# ── Connected viewers ──
_viewers: set = set()
_step_log: list = []


async def handler(websocket):
    """Handle a WebSocket connection."""
    _viewers.add(websocket)
    logger.info(f"Viewer connected ({len(_viewers)} total)")
    try:
        # Send current status
        await websocket.send(json.dumps({
            "type": "status",
            "source": _capture_mode,
        }))
        # Send recent log entries
        for entry in _step_log[-50:]:
            await websocket.send(json.dumps(entry))
        # Keep alive — listen for commands
        async for message in websocket:
            try:
                cmd = json.loads(message)
                if cmd.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _viewers.discard(websocket)
        logger.info(f"Viewer disconnected ({len(_viewers)} total)")


async def stream_frames():
    """Capture screen and broadcast to all viewers."""
    while True:
        if _viewers:
            frame = capture_frame()
            if frame:
                b64 = base64.b64encode(frame).decode()
                msg = json.dumps({"type": "frame", "data": b64})
                disconnected = set()
                for viewer in _viewers:
                    try:
                        await viewer.send(msg)
                    except Exception:
                        disconnected.add(viewer)
                _viewers.difference_update(disconnected)
        await asyncio.sleep(0.1)  # ~10 fps


def broadcast_log(message: str, level: str = "log-info"):
    """Send a log entry to all connected viewers."""
    entry = {"type": "log", "message": message, "level": level}
    _step_log.append(entry)
    if len(_step_log) > 500:
        _step_log.pop(0)
    # Fire and forget to all viewers
    if _viewers:
        msg = json.dumps(entry)
        for viewer in list(_viewers):
            try:
                asyncio.get_event_loop().create_task(viewer.send(msg))
            except Exception:
                _viewers.discard(viewer)


def broadcast_step(action: str, status: str, result: str = ""):
    """Send a step completion event to all viewers."""
    entry = {"type": "step", "action": action, "status": status, "result": result}
    _step_log.append(entry)
    if _viewers:
        msg = json.dumps(entry)
        for viewer in list(_viewers):
            try:
                asyncio.get_event_loop().create_task(viewer.send(msg))
            except Exception:
                _viewers.discard(viewer)


async def main(host: str = "127.0.0.1", port: int = 8765):
    """Start the stream server."""
    # Serve the HTML viewer on the root path
    async def ws_handler(websocket, path=None):
        if path == "/ws" or path is None:
            await handler(websocket)
        elif path == "/":
            # Send the HTML viewer
            await websocket.send(VIEWER_HTML)
            await websocket.close()

    # Use a simple approach: serve HTML on HTTP, WebSocket on /ws
    import functools

    # HTTP handler for the viewer page
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse

        class ViewerHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(VIEWER_HTML.encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress HTTP logs

        # Start HTTP server in a thread
        httpd = HTTPServer((host, port), ViewerHandler)
        http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        http_thread.start()
        logger.info(f"Viewer: http://{host}:{port}")

    except ImportError:
        logger.warning("http.server not available, viewer page won't be served")

    # Start WebSocket server
    logger.info(f"WebSocket: ws://{host}:{port}/ws")
    async with websockets.serve(handler, host, port + 1):
        logger.info(f"Stream server running — open http://{host}:{port} to watch")
        await stream_frames()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Stream Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
