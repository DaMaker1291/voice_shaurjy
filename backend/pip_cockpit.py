"""
JARVIS PIP Virtual Cockpit — Enhanced
=====================================
Picture-in-Picture floating live video thumbnail rendering the framebuffer
of the hidden background virtual desktop with 1-click "Take Manual Control".

Enhanced v2 features:
- Real-time framebuffer capture and streaming via WebSocket
- JPEG-compressed frames at configurable FPS (up to 60fps)
- Click-to-take-manual-control override
- Resolution scaling for bandwidth optimization
- Multi-display support
- Action annotation overlay (mouse clicks, keystrokes, AI intentions)
- Mini DOM snapshot sidebar (CDP-powered)
- Thinking bubble overlay showing LLM reasoning in real-time
- Heatmap of agent activity density
"""

import os
import io
import json
import time
import base64
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-pip")


@dataclass
class PIPSession:
    """A PIP streaming session."""
    session_id: str
    display_id: int
    resolution: tuple = (640, 360)
    fps: int = 15
    quality: int = 70  # JPEG quality 1-100
    active: bool = False
    manual_control: bool = False
    connected_clients: int = 0
    started_at: float = 0.0
    frames_sent: int = 0
    bandwidth_kbps: float = 0.0
    # Enhanced v2 fields
    annotations: list = field(default_factory=list)  # mouse clicks, keystrokes
    current_intention: str = ""  # what the AI is currently thinking/doing
    dom_snapshot: Optional[str] = None  # latest CDP DOM summary
    activity_heatmap: list = field(default_factory=list)  # recent cursor positions
    last_thought: str = ""  # last LLM reasoning snippet


class PIPCockpit:
    """
    Picture-in-Picture Virtual Cockpit streaming engine.
    Captures virtual desktop framebuffer and streams to frontend.
    """

    def __init__(self):
        self._sessions: Dict[str, PIPSession] = {}
        self._frame_generator = None

    def create_session(
        self,
        session_id: str = "default",
        display_id: int = 1,
        resolution: tuple = (640, 360),
        fps: int = 15,
        quality: int = 70,
    ) -> Dict[str, Any]:
        """Create or update a PIP streaming session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.resolution = resolution
            session.fps = fps
            session.quality = quality
        else:
            session = PIPSession(
                session_id=session_id,
                display_id=display_id,
                resolution=resolution,
                fps=fps,
                quality=quality,
                active=True,
                started_at=time.time(),
            )
            self._sessions[session_id] = session

        return {
            "ok": True,
            "session": {
                "session_id": session.session_id,
                "display_id": session.display_id,
                "resolution": list(session.resolution),
                "fps": session.fps,
                "quality": session.quality,
                "active": session.active,
            },
        }

    def stop_session(self, session_id: str) -> Dict[str, Any]:
        """Stop a PIP streaming session."""
        if session_id in self._sessions:
            self._sessions[session_id].active = False
            del self._sessions[session_id]
            return {"ok": True}
        return {"ok": False, "error": "Session not found"}

    async def generate_frames(
        self,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate JPEG frames from the virtual desktop framebuffer.
        Yields frame messages suitable for WebSocket sending.
        """
        session = self._sessions.get(session_id)
        if not session:
            return

        session.connected_clients += 1
        log.info(f"PIP client connected to session {session_id}")

        try:
            while session.active:
                frame_data = await self._capture_frame(session)
                if frame_data:
                    session.frames_sent += 1
                    yield {
                        "type": "frame",
                        "data": frame_data,
                        "width": session.resolution[0],
                        "height": session.resolution[1],
                        "frame_num": session.frames_sent,
                        "timestamp": time.time(),
                    }

                # Calculate frame interval
                interval = 1.0 / session.fps
                await asyncio.sleep(interval)
        finally:
            session.connected_clients -= 1
            log.info(f"PIP client disconnected from session {session_id}")

    async def _capture_frame(self, session: PIPSession) -> Optional[str]:
        """Capture a single frame from the virtual desktop.
        Returns base64-encoded JPEG with overlay annotations (v2).
        """
        raw_frame = None
        
        # Try headless worker first
        try:
            from headless_worker import get_headless_worker
            worker = get_headless_worker()
            if worker and hasattr(worker, 'capture_jpeg'):
                raw_frame = worker.capture_jpeg(
                    session_id=f"pip_{session.display_id}",
                    width=session.resolution[0],
                    height=session.resolution[1],
                    quality=session.quality,
                )
                if raw_frame:
                    from base64 import b64decode
                    raw_frame = b64decode(raw_frame)
            if not raw_frame and worker and hasattr(worker, 'capture_screen'):
                raw_frame = await worker.capture_screen(display_id=session.display_id)
        except Exception:
            pass

        # Fallback: mss screen capture
        if not raw_frame:
            try:
                import mss
                from PIL import Image
                with mss.mss(display=f":{session.display_id}") as sct:
                    monitor = sct.monitors[session.display_id] if session.display_id < len(sct.monitors) else sct.monitors[1]
                    scaled = {
                        "left": monitor["left"],
                        "top": monitor["top"],
                        "width": min(monitor["width"], session.resolution[0] * 2),
                        "height": min(monitor["height"], session.resolution[1] * 2),
                    }
                    screenshot = sct.grab(scaled)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                    img = img.resize(session.resolution, Image.Resampling.LANCZOS)
                    img = img.convert("RGB")
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=session.quality, optimize=True)
                    raw_frame = buffer.getvalue()
            except Exception as e:
                log.debug(f"Frame capture fallback: {e}")

        # Load image for annotation
        try:
            from PIL import Image
            if raw_frame:
                img = Image.open(io.BytesIO(raw_frame))
                if img.size != session.resolution:
                    img = img.resize(session.resolution, Image.Resampling.LANCZOS)
                if img.mode != "RGB":
                    img = img.convert("RGB")
            else:
                img = Image.new("RGB", session.resolution, (10, 10, 20))
            
            # Apply overlay annotations
            img = self._apply_overlay(img, session)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=session.quality, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode()
        except Exception as e:
            log.debug(f"Frame encode/overlay failed: {e}")
            if raw_frame:
                return base64.b64encode(raw_frame).decode()
            return None

    def _apply_overlay(self, img, session):
        """Apply annotation overlays: badges, AI intention, click markers, heatmap."""
        from PIL import ImageDraw, ImageFont
        
        draw = ImageDraw.Draw(img)
        w, h = img.size
        
        try:
            font = ImageFont.truetype("arial", 12)
            font_small = ImageFont.truetype("arial", 10)
        except Exception:
            font = ImageFont.load_default()
            font_small = font
        
        # Gradient bars at top/bottom for text readability
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for y in range(int(h * 0.18)):
            a = int(100 * (1 - y / (h * 0.18)))
            overlay_draw.line([(0, y), (w, y)], fill=(0, 0, 0, a))
        for y in range(int(h * 0.82), h):
            a = int(100 * (y - h * 0.82) / (h * 0.18))
            overlay_draw.line([(0, y), (w, y)], fill=(0, 0, 0, a))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Top-left badge
        draw.rectangle([5, 5, 160, 22], fill=(3, 7, 12, 200))
        draw.text((8, 7), "JARVIS PIP | AI Active", fill=(0, 255, 69), font=font_small)
        
        # Top-right: AI thinking bubble
        if session.last_thought:
            thought = session.last_thought[:85] + "..." if len(session.last_thought) > 85 else session.last_thought
            tw = draw.textlength(f"THINKING: {thought}", font=font_small)
            draw.rectangle([w - 12 - tw, 5, w - 8, 24], fill=(40, 40, 50, 220))
            draw.text((w - 10 - tw, 8), f"THINKING: {thought}", fill=(255, 255, 255), font=font_small)
        
        # Bottom bar: current intention
        if session.current_intention:
            intent = session.current_intention[:90] + "..." if len(session.current_intention) > 90 else session.current_intention
            by = h - 50
            draw.rectangle([5, by, w - 5, by + 18], fill=(30, 30, 50, 220))
            draw.text((8, by + 2), f"ACTION: {intent}", fill=(0, 255, 69), font=font_small)
        
        # Click annotations (yellow rings that shrink+fade)
        now = time.time()
        for ann in session.annotations[-20:]:
            age = now - ann.get("ts", now)
            if age > 4:
                continue
            x, y_a = ann.get("x", 0), ann.get("y", 0)
            atype = ann.get("type", "click")
            alpha = max(50, int(255 * (4 - age) / 4))
            if atype == "click":
                r = max(6, int(16 * (4 - age) / 4))
                draw.ellipse([x-r, y_a-r, x+r, y_a+r], outline=(255, 255, 0, alpha), width=2, fill=(255, 255, 0, 30))
            elif atype == "keypress":
                key = ann.get("key", "?")
                draw.rectangle([x-12, y_a-12, x+12, y_a+12], outline=(0, 255, 255, alpha), fill=(0, 255, 255, 30))
                draw.text((x-5, y_a-5), key[:2], fill=(0, 255, 255, alpha), font=font_small)
        
        # Activity heatmap dots (magenta translucent)
        for pos in session.activity_heatmap[-50:]:
            hx, hy, ts_val = pos
            if now - ts_val > 3:
                continue
            alpha = max(15, int(50 * (3 - (now - ts_val)) / 3))
            r = max(1, int(4 * (3 - (now - ts_val)) / 3))
            draw.ellipse([hx-r, hy-r, hx+r, hy+r], fill=(255, 0, 255, alpha))
        
        # Bottom-right: DOM summary
        if session.dom_snapshot:
            dom = session.dom_snapshot[:55] + "..." if len(session.dom_snapshot) > 55 else session.dom_snapshot
            dw = draw.textlength(f"DOM: {dom}", font=font_small)
            draw.rectangle([w - 12 - dw, h - 22, w - 8, h - 4], fill=(10, 10, 20, 220))
            draw.text((w - 10 - dw, h - 20), f"DOM: {dom}", fill=(150, 150, 255), font=font_small)
        
        # Timestamp
        ts = time.strftime("%H:%M:%S")
        draw.text((w - 40, 7), ts, fill=(100, 100, 100), font=font_small)
        
        return img

    def _compress_frame(self, raw_frame: bytes, session: PIPSession) -> str:
        """Compress a raw frame to base64 JPEG."""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(raw_frame))
            img = img.resize(session.resolution, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=session.quality, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode()
        except Exception:
            # If PIL not available, just base64 encode raw
            return base64.b64encode(raw_frame).decode()

    def take_manual_control(self, session_id: str) -> Dict[str, Any]:
        """Toggle manual control mode for a PIP session."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.manual_control = not session.manual_control
        log.info(f"PIP manual control {'enabled' if session.manual_control else 'disabled'} for {session_id}")

        return {
            "ok": True,
            "manual_control": session.manual_control,
            "session_id": session_id,
        }

    def add_annotation(self, session_id: str, annotation: Dict[str, Any]) -> None:
        """Add an annotation (mouse click, keypress) to the session's overlay."""
        session = self._sessions.get(session_id)
        if session:
            annotation["ts"] = time.time()
            session.annotations.append(annotation)
            if annotation.get("type") == "move":
                session.activity_heatmap.append((annotation.get("x", 0), annotation.get("y", 0), time.time()))

    def set_intention(self, session_id: str, intention: str) -> None:
        """Set the AI's current intention/action label for the overlay."""
        session = self._sessions.get(session_id)
        if session:
            session.current_intention = intention

    def set_last_thought(self, session_id: str, thought: str) -> None:
        """Set the last LLM reasoning snippet to show in the thinking bubble."""
        session = self._sessions.get(session_id)
        if session:
            session.last_thought = thought

    def set_dom_snapshot(self, session_id: str, dom_summary: str) -> None:
        """Update the DOM snapshot shown in the bottom-right of the overlay."""
        session = self._sessions.get(session_id)
        if session:
            session.dom_snapshot = dom_summary

    def get_status(self) -> Dict[str, Any]:
        """Get PIP cockpit status with enhanced detail."""
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "display_id": s.display_id,
                    "resolution": list(s.resolution),
                    "fps": s.fps,
                    "active": s.active,
                    "manual_control": s.manual_control,
                    "connected_clients": s.connected_clients,
                    "frames_sent": s.frames_sent,
                    "uptime": round(time.time() - s.started_at, 1) if s.started_at else 0,
                    "current_intention": s.current_intention,
                    "last_thought": s.last_thought,
                    "dom_snapshot": s.dom_snapshot,
                    "annotations": len(s.annotations),
                    "heatmap_points": len(s.activity_heatmap),
                }
                for s in self._sessions.values()
            ],
            "total_sessions": len(self._sessions),
        }


# ── Singleton ────────────────────────────────────────────────────────────
_cockpit: Optional[PIPCockpit] = None


def get_pip_cockpit() -> PIPCockpit:
    global _cockpit
    if _cockpit is None:
        _cockpit = PIPCockpit()
    return _cockpit
