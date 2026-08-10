"""
JARVIS VDI XFCE4 Streamer
==========================
Captures the XFCE4 virtual desktop (Xvfb :1) and streams JPEG frames
over WebSocket to the Electron PiP window. Also exposes an HTTP endpoint
for the noVNC viewer.

Architecture:
    Xvfb :1 → XFCE4 Desktop → scrot/xdotool → JPEG → WebSocket → Electron PiP

Usage:
    # Standalone
    python vdi_xfce_streamer.py --port 8765

    # As module
    from vdi_xfce_streamer import start_vdi_stream
    start_vdi_stream(port=8765, fps=10)
"""

import os
import sys
import io
import json
import time
import base64
import asyncio
import threading
import subprocess
import logging
from typing import Optional

log = logging.getLogger("vdi-xfce-stream")

try:
    import websockets
    import websockets.server
except ImportError:
    log.error("pip install websockets")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    log.error("pip install Pillow")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# Frame Capture — scrot from Xvfb :1
# ═══════════════════════════════════════════════════════════════════════════

class VDIFrameCapture:
    """Captures frames from the XFCE4 VDI via scrot."""

    def __init__(self, display: str = ":1", width: int = 480, height: int = 270):
        self.display = display
        self.width = width
        self.height = height
        self._frame: Optional[bytes] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._fps = 10
        self._user = "workuser"
        self._frame_path = f"/tmp/vdi_frame_{os.getpid()}.png"

    def start(self, fps: int = 10):
        """Start capturing frames in background thread."""
        self._fps = fps
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        log.info(f"VDI capture started: DISPLAY={self.display} @ {fps}fps")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("VDI capture stopped")

    def get_latest_frame(self) -> Optional[bytes]:
        """Get latest JPEG frame (thread-safe)."""
        with self._lock:
            return self._frame

    def _capture_loop(self):
        """Background capture loop using scrot."""
        interval = 1.0 / self._fps
        while self._running:
            start = time.time()
            frame = self._capture_once()
            if frame:
                with self._lock:
                    self._frame = frame
            elapsed = time.time() - start
            time.sleep(max(0, interval - elapsed))

    def _capture_once(self) -> Optional[bytes]:
        """Capture a single frame via scrot, resize to PiP dimensions."""
        try:
            result = subprocess.run(
                ["scrot", "-o", self._frame_path],
                env={**os.environ, "DISPLAY": self.display},
                capture_output=True, timeout=5,
                # Run as workuser
            )
            # If running as root, use sudo
            if result.returncode != 0:
                result = subprocess.run(
                    ["sudo", "-u", self._user, "env",
                     f"DISPLAY={self.display}", "scrot", "-o", self._frame_path],
                    capture_output=True, timeout=5,
                )

            if os.path.exists(self._frame_path):
                with open(self._frame_path, "rb") as f:
                    raw = f.read()
                os.unlink(self._frame_path)

                if len(raw) > 100:
                    img = Image.open(io.BytesIO(raw))
                    img = img.convert("RGB")
                    img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85, optimize=False)
                    return buf.getvalue()
        except Exception as e:
            log.debug(f"Capture error: {e}")
        return None

    def capture_full_res(self) -> Optional[bytes]:
        """Capture at full VDI resolution (1920x1080)."""
        try:
            subprocess.run(
                ["sudo", "-u", self._user, "env",
                 f"DISPLAY={self.display}", "scrot", "-o", "/tmp/vdi_full.png"],
                capture_output=True, timeout=5,
            )
            if os.path.exists("/tmp/vdi_full.png"):
                with open("/tmp/vdi_full.png", "rb") as f:
                    raw = f.read()
                os.unlink("/tmp/vdi_full.png")
                if len(raw) > 100:
                    img = Image.open(io.BytesIO(raw))
                    img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=80)
                    return buf.getvalue()
        except Exception as e:
            log.debug(f"Full-res capture error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket Stream Server
# ═══════════════════════════════════════════════════════════════════════════

_viewers: set = set()
_capture: Optional[VDIFrameCapture] = None


async def ws_handler(websocket):
    """Handle a PiP WebSocket connection."""
    _viewers.add(websocket)
    log.info(f"PiP viewer connected ({len(_viewers)} total)")
    try:
        # Send status as binary: header 0x01 + JSON
        status = json.dumps({
            "type": "status",
            "source": "vdi_xfce4",
            "display": _capture.display if _capture else ":1",
            "resolution": f"{_capture.width}x{_capture.height}" if _capture else "480x270",
        }).encode()
        await websocket.send(bytes([0x01]) + status)
        async for message in websocket:
            try:
                if isinstance(message, str):
                    cmd = json.loads(message)
                else:
                    cmd = json.loads(message)
                if cmd.get("type") == "ping":
                    await websocket.send(bytes([0x01]) + json.dumps({"type": "pong"}).encode())
                elif cmd.get("type") == "full_res":
                    if _capture:
                        frame = _capture.capture_full_res()
                        if frame:
                            await websocket.send(bytes([0x02]) + frame)
            except Exception:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _viewers.discard(websocket)
        log.info(f"PiP viewer disconnected ({len(_viewers)} total)")


async def broadcast_loop():
    """Capture and broadcast frames to all connected viewers."""
    while True:
        if _viewers and _capture:
            frame = _capture.get_latest_frame()
            if frame:
                # Binary frame: header 0x02 + raw JPEG bytes
                msg = bytes([0x02]) + frame
                disconnected = set()
                for viewer in _viewers:
                    try:
                        await viewer.send(msg)
                    except Exception:
                        disconnected.add(viewer)
                _viewers.difference_update(disconnected)
        await asyncio.sleep(0.05)  # ~20fps broadcast


async def main(host: str = "127.0.0.1", port: int = 8765,
               display: str = ":1", fps: int = 10):
    """Start the VDI stream server."""
    global _capture

    _capture = VDIFrameCapture(display=display, width=960, height=540)
    _capture.start(fps=fps)

    log.info(f"VDI XFCE4 Stream: ws://{host}:{port + 1}/ws")
    log.info(f"  Display: {display}")
    log.info(f"  PiP resolution: 960x540")
    log.info(f"  Capture FPS: {fps}")

    # Start WebSocket server on port+1
    async with websockets.serve(ws_handler, host, port + 1):
        await broadcast_loop()


def start_vdi_stream(port: int = 8765, display: str = ":1", fps: int = 10):
    """Start VDI streaming (blocking)."""
    asyncio.run(main(port=port, display=display, fps=fps))


# ═══════════════════════════════════════════════════════════════════════════
# Integration with stream_server.py
# ═══════════════════════════════════════════════════════════════════════════

def connect_to_stream_server(stream_server_module=None):
    """Connect this VDI capture as the source for stream_server.py."""
    global _capture
    if stream_server_module is None:
        try:
            import stream_server
            stream_server_module = stream_server
        except ImportError:
            log.error("stream_server.py not found")
            return

    _capture = VDIFrameCapture(display=":1", width=480, height=270)
    _capture.start(fps=10)

    class VDICapturer:
        def get_latest_frame(self):
            return _capture.get_latest_frame()
        def stop(self):
            _capture.stop()

    stream_server_module.set_vdi_source(VDICapturer())
    log.info("Connected VDI XFCE4 to stream_server.py")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS VDI XFCE4 Streamer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--display", default=":1", help="VDI display number")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--connect-stream-server", action="store_true",
                        help="Connect to stream_server.py instead of standalone")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[VDI-STREAM] %(message)s")

    if args.connect_stream_server:
        connect_to_stream_server()
        # Keep alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        asyncio.run(main(
            host=args.host, port=args.port,
            display=args.display, fps=args.fps,
        ))
