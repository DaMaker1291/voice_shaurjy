"""JARVIS Streaming — WebRTC via LiveKit.

Replaces the old screenshot-polling WebSocket with a proper
low-latency video stream from the workspace to the cockpit.

Architecture:
    VM Display → Frame Capture → LiveKit Publisher → WebRTC → Browser

LiveKit provides:
- Low latency (< 100ms)
- Adaptive bitrate
- Hardware encoding (NVENC/AMF/VideoToolbox)
- Multi-viewer support
- Recording capability
- Simulcast (multiple quality layers)

Requirements:
    pip install livekit livekit-api
"""

import os
import json
import time
import asyncio
import logging
import threading
import subprocess
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("streaming")

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")


@dataclass
class StreamConfig:
    """Configuration for a workspace stream."""
    workspace_id: str
    room_name: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    bitrate: int = 2_000_000  # 2 Mbps
    hardware_encode: bool = True
    adaptive_bitrate: bool = True


@dataclass
class StreamState:
    """Current state of a stream."""
    workspace_id: str
    room_name: str
    active: bool = False
    viewers: int = 0
    bitrate: int = 0
    fps: int = 0
    latency_ms: float = 0
    started_at: float = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "room_name": self.room_name,
            "active": self.active,
            "viewers": self.viewers,
            "bitrate": self.bitrate,
            "fps": self.fps,
            "latency_ms": self.latency_ms,
            "started_at": self.started_at,
            "error": self.error,
        }


class LiveKitStreamer:
    """Publishes workspace display to LiveKit room via WebRTC."""

    def __init__(self):
        self._streams: Dict[str, StreamState] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._publisher = None
        self._init_livekit()

    def _init_livekit(self):
        """Initialize LiveKit SDK."""
        try:
            from livekit import rtc, api
            self._livekit_available = True
            log.info("[STREAM] LiveKit SDK loaded")
        except ImportError:
            self._livekit_available = False
            log.warning("[STREAM] LiveKit SDK not available, using fallback")

    async def start_stream(self, config: StreamConfig) -> dict:
        """Start streaming a workspace to a LiveKit room."""
        if not self._livekit_available:
            return await self._start_ffmpeg_stream(config)

        try:
            from livekit import rtc, api

            # Create room if needed
            room_service = api.LiveKitAPI(
                LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
            )
            try:
                await room_service.room.create_room(
                    api.CreateRoomRequest(name=config.room_name)
                )
            except Exception:
                pass  # Room may already exist

            # Generate token for publisher
            token = (
                api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
                .with_identity(f"jarvis-{config.workspace_id}")
                .with_can_publish(True)
                .with_can_subscribe(False)
                .with_grants(api.VideoGrants(room_join=True, room=config.room_name))
                .to_jwt()
            )

            # Connect to room
            room = rtc.Room()
            await room.connect(LIVEKIT_URL, token)

            # Create video source
            source = rtc.VideoSource(config.width, config.height)
            track = rtc.LocalVideoTrack.create_video_track(
                f"workspace-{config.workspace_id}", source
            )

            # Publish track
            options = rtc.TrackPublishOptions(
                video_encoding=rtc.VideoEncoding(
                    max_bitrate=config.bitrate,
                    max_fps=config.fps,
                ),
                source=rtc.TrackSource.SOURCE_CAMERA,
            )
            publication = await room.local_participant.publish_track(track, options)

            # Start capture thread
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._capture_loop,
                args=(config, source, stop_event),
                daemon=True,
            )

            state = StreamState(
                workspace_id=config.workspace_id,
                room_name=config.room_name,
                active=True,
                started_at=time.time(),
            )

            self._streams[config.workspace_id] = state
            self._stop_events[config.workspace_id] = stop_event
            self._threads[config.workspace_id] = thread

            thread.start()

            log.info(f"[STREAM] Started LiveKit stream for {config.workspace_id}")
            return {"ok": True, "stream_url": f"livekit://{LIVEKIT_URL}/{config.room_name}"}

        except Exception as e:
            log.error(f"[STREAM] LiveKit stream failed: {e}")
            return await self._start_ffmpeg_stream(config)

    async def _start_ffmpeg_stream(self, config: StreamConfig) -> dict:
        """Fallback: Use FFmpeg to stream via RTMP/WebRTC."""
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._ffmpeg_capture_loop,
            args=(config, stop_event),
            daemon=True,
        )

        state = StreamState(
            workspace_id=config.workspace_id,
            room_name=config.room_name,
            active=True,
            started_at=time.time(),
        )

        self._streams[config.workspace_id] = state
        self._stop_events[config.workspace_id] = stop_event
        self._threads[config.workspace_id] = thread

        thread.start()

        log.info(f"[STREAM] Started FFmpeg fallback stream for {config.workspace_id}")
        return {"ok": True, "stream_url": f"rtmp://localhost/live/{config.workspace_id}"}

    def _capture_loop(
        self,
        config: StreamConfig,
        source,
        stop_event: threading.Event,
    ):
        """Capture frames from workspace and feed to LiveKit."""
        from livekit import rtc

        while not stop_event.is_set():
            try:
                frame = self._capture_workspace_frame(config.workspace_id)
                if frame:
                    # Convert to I420 format for WebRTC
                    video_frame = rtc.VideoFrame(
                        config.width,
                        config.height,
                        rtc.VideoBufferType.BGRA,
                        frame,
                    )
                    source.capture_frame(video_frame)
            except Exception as e:
                log.debug(f"[STREAM] Capture error: {e}")

            time.sleep(1.0 / config.fps)

    def _ffmpeg_capture_loop(
        self,
        config: StreamConfig,
        stop_event: threading.Event,
    ):
        """Capture using FFmpeg subprocess."""
        # Build FFmpeg command for screen capture + encode + stream
        platform_cmd = self._get_ffmpeg_input(config)

        ffmpeg_cmd = [
            "ffmpeg",
            *platform_cmd,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", f"{config.bitrate // 1000}k",
            "-maxrate", f"{config.bitrate // 1000}k",
            "-bufsize", f"{config.bitrate // 500}k",
            "-g", str(config.fps * 2),
            "-f", "flv",
            f"rtmp://localhost/live/{config.workspace_id}",
        ]

        try:
            proc = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            while not stop_event.is_set():
                if proc.poll() is not None:
                    break
                time.sleep(0.5)

            proc.terminate()

        except Exception as e:
            log.error(f"[STREAM] FFmpeg error: {e}")

    def _get_ffmpeg_input(self, config: StreamConfig) -> list:
        """Get FFmpeg input arguments for current platform."""
        system = os.name
        w, h = config.width, config.height

        if system == "nt":  # Windows
            return [
                "-f", "gdigrab",
                "-framerate", str(config.fps),
                "-offset_x", "0",
                "-offset_y", "0",
                "-video_size", f"{w}x{h}",
                "-i", "desktop",
            ]
        elif system == "posix":
            if os.uname().sysname == "Darwin":  # macOS
                return [
                    "-f", "avfoundation",
                    "-framerate", str(config.fps),
                    "-video_size", f"{w}x{h}",
                    "-i", "1",
                ]
            else:  # Linux
                return [
                    "-f", "x11grab",
                    "-framerate", str(config.fps),
                    "-video_size", f"{w}x{h}",
                    "-i", ":0.0",
                ]
        return []

    def _capture_workspace_frame(self, workspace_id: str) -> Optional[bytes]:
        """Capture a single frame from the workspace."""
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                return sct_img.rgb
        except Exception:
            return None

    def stop_stream(self, workspace_id: str) -> dict:
        """Stop streaming a workspace."""
        if workspace_id in self._stop_events:
            self._stop_events[workspace_id].set()

        if workspace_id in self._threads:
            self._threads[workspace_id].join(timeout=5)

        if workspace_id in self._streams:
            self._streams[workspace_id].active = False

        self._stop_events.pop(workspace_id, None)
        self._threads.pop(workspace_id, None)

        return {"ok": True}

    def get_stream_state(self, workspace_id: str) -> Optional[dict]:
        """Get current stream state."""
        if workspace_id in self._streams:
            return self._streams[workspace_id].to_dict()
        return None

    def get_token(self, workspace_id: str, identity: str = "viewer") -> str:
        """Generate a viewer token for a workspace stream."""
        try:
            from livekit import api
            room_name = f"jarvis-workspace-{workspace_id}"
            token = (
                api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
                .with_identity(identity)
                .with_can_publish(False)
                .with_can_subscribe(True)
                .with_grants(api.VideoGrants(room_join=True, room=room_name))
                .to_jwt()
            )
            return token
        except Exception as e:
            log.error(f"[STREAM] Token generation failed: {e}")
            return ""

    def list_active_streams(self) -> List[dict]:
        """List all active streams."""
        return [s.to_dict() for s in self._streams.values() if s.active]


class ScreenshotFallbackStreamer:
    """
    Fallback streamer that uses the existing screenshot-over-WebSocket approach.
    Used when LiveKit is not available or for simple deployments.
    """

    def __init__(self):
        self._connections: Dict[str, list] = {}

    async def handle_websocket(self, workspace_id: str, websocket):
        """Handle a WebSocket connection for screenshot streaming."""
        from starlette.websockets import WebSocket

        if workspace_id not in self._connections:
            self._connections[workspace_id] = []
        self._connections[workspace_id].append(websocket)

        try:
            while True:
                frame = self._capture_frame(workspace_id)
                if frame:
                    await websocket.send_bytes(frame)
                await asyncio.sleep(0.1)  # 10 FPS
        except Exception:
            pass
        finally:
            self._connections[workspace_id].remove(websocket)

    def _capture_frame(self, workspace_id: str) -> Optional[bytes]:
        """Capture a screenshot of the workspace."""
        import io
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=60, optimize=True)
                return buf.getvalue()
        except Exception:
            return None

    def broadcast_frame(self, workspace_id: str, frame: bytes):
        """Broadcast a frame to all connected viewers."""
        import asyncio
        if workspace_id in self._connections:
            for ws in self._connections[workspace_id]:
                try:
                    asyncio.run(ws.send_bytes(frame))
                except Exception:
                    pass


# Global instances
_streamer = None
_fallback = None


def get_streamer() -> LiveKitStreamer:
    global _streamer
    if _streamer is None:
        _streamer = LiveKitStreamer()
    return _streamer


def get_fallback_streamer() -> ScreenshotFallbackStreamer:
    global _fallback
    if _fallback is None:
        _fallback = ScreenshotFallbackStreamer()
    return _fallback
