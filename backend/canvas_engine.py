"""
WebGL Workspace Canvas Cockpit
Renders an interactive spatial Bento Grid frontend with:
- 60fps PiP VDI video stream
- WebGL kinetic audio HUD / reactive orb
- Rendered 3D model/PDB viewer
- Live interactive code diffs
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("canvas_engine")

CANVAS_PORT = 8081
CANVAS_HOST = "localhost"
CANVAS_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canvas_dashboard.html")


class BentoGrid:
    """6-panel Bento Grid layout for the workspace canvas."""

    LAYOUT = {
        "video_panel": {"row": 0, "col": 0, "span_row": 2, "span_col": 2},
        "audio_hud": {"row": 0, "col": 2, "span_row": 1, "span_col": 1},
        "code_diff": {"row": 1, "col": 2, "span_row": 1, "span_col": 1},
        "model_viewer": {"row": 2, "col": 0, "span_row": 1, "span_col": 1},
        "action_log": {"row": 2, "col": 1, "span_row": 1, "span_col": 1},
        "status_bar": {"row": 3, "col": 0, "span_row": 1, "span_col": 3},
    }

    def __init__(self):
        self.panels = {}
        self._callbacks = {}

    def set_panel(self, name: str, content: Any) -> None:
        """Set content for a panel."""
        if name not in self.LAYOUT:
            logger.warning(f"Unknown panel: {name}")
            return
        self.panels[name] = content
        self._emit("panel_update", {"name": name, "content": content})

    def get_panel(self, name: str) -> Any:
        """Get content for a panel."""
        return self.panels.get(name)

    def get_layout(self) -> Dict[str, Dict[str, int]]:
        """Get the Bento Grid layout."""
        return self.LAYOUT

    def on_event(self, event: str, callback):
        """Register a callback for panel events."""
        self._callbacks[event] = callback

    def _emit(self, event: str, data: Any = None) -> None:
        if event in self._callbacks:
            try:
                self._callbacks[event](event, data)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")


class PiPVideoStream:
    """60fps Picture-in-Picture VDI video stream."""

    def __init__(self, vdi_manager=None):
        self.vdi_manager = vdi_manager
        self.fps = 60
        self._running = False
        self._frame_count = 0

    def start(self) -> bool:
        """Start the PiP video stream."""
        self._running = True
        self._frame_count = 0
        logger.info(f"PiP video stream started at {self.fps}fps")
        return True

    def stop(self) -> None:
        """Stop the PiP video stream."""
        self._running = False
        logger.info("PiP video stream stopped")

    def capture_frame(self) -> Optional[bytes]:
        """Capture a single VDI frame for PiP streaming."""
        if not self._running:
            return None
        self._frame_count += 1
        if self.vdi_manager:
            return self.vdi_manager.get_vdi_screenshot()
        return None

    def get_frame_count(self) -> int:
        return self._frame_count


class AudioHud:
    """WebGL kinetic audio HUD / reactive orb."""

    def __init__(self):
        self.orb_position = {"x": 0.5, "y": 0.5, "z": 0.0}
        self.orb_color = {"r": 0.0, "g": 1.0, "b": 0.4}
        self.orb_pulse = 0.0
        self.audio_level = 0.0

    def update(self, audio_level: float) -> None:
        """Update the orb based on audio level."""
        self.audio_level = audio_level
        self.orb_pulse = min(1.0, audio_level * 2.0)
        self.orb_position["x"] = 0.5 + 0.3 * (audio_level - 0.5)
        self.orb_position["y"] = 0.5 + 0.2 * (audio_level - 0.5)

    def get_state(self) -> Dict[str, Any]:
        return {
            "orb_position": self.orb_position,
            "orb_color": self.orb_color,
            "orb_pulse": self.orb_pulse,
            "audio_level": self.audio_level,
        }


class CodeDiffViewer:
    """Live interactive code diff viewer."""

    def __init__(self):
        self._diffs: List[Dict[str, Any]] = []
        self._current_diff: Optional[Dict[str, Any]] = None

    def add_diff(self, old_text: str, new_text: str, label: str = "") -> Dict[str, Any]:
        """Add a new code diff."""
        diff = {
            "label": label,
            "old": old_text,
            "new": new_text,
            "timestamp": time.time(),
            "lines_added": len(new_text.splitlines()) - len(old_text.splitlines()),
        }
        self._diffs.append(diff)
        self._current_diff = diff
        return diff

    def get_current_diff(self) -> Optional[Dict[str, Any]]:
        return self._current_diff

    def get_all_diffs(self) -> List[Dict[str, Any]]:
        return self._diffs


class ModelViewer:
    """3D model/PDB viewer panel."""

    def __init__(self):
        self._model_path: Optional[str] = None
        self._rotation = {"x": 0, "y": 0, "z": 0}
        self._zoom = 1.0

    def load_model(self, path: str) -> bool:
        """Load a 3D model file."""
        if not os.path.exists(path):
            logger.warning(f"Model file not found: {path}")
            return False
        self._model_path = path
        logger.info(f"Model loaded: {path}")
        return True

    def rotate(self, dx: float, dy: float, dz: float) -> None:
        """Rotate the model."""
        self._rotation["x"] += dx
        self._rotation["y"] += dy
        self._rotation["z"] += dz

    def zoom(self, factor: float) -> None:
        """Zoom the model."""
        self._zoom = max(0.1, min(5.0, self._zoom * factor))

    def get_state(self) -> Dict[str, Any]:
        return {
            "model_path": self._model_path,
            "rotation": self._rotation,
            "zoom": self._zoom,
        }


class CanvasEngine:
    """Main WebGL Canvas Cockpit engine."""

    def __init__(self):
        self.grid = BentoGrid()
        self.video = PiPVideoStream()
        self.audio = AudioHud()
        self.code_diff = CodeDiffViewer()
        self.model_viewer = ModelViewer()
        self._running = False

    def start(self) -> Dict[str, Any]:
        """Start the canvas cockpit."""
        self._running = True
        self.video.start()
        logger.info("Canvas Engine started")
        return {
            "running": True,
            "layout": self.grid.get_layout(),
            "ws_endpoint": f"ws://{CANVAS_HOST}:{CANVAS_PORT}",
        }

    def stop(self) -> None:
        """Stop the canvas cockpit."""
        self._running = False
        self.video.stop()
        logger.info("Canvas Engine stopped")

    def update_video(self, vdi_manager) -> None:
        """Update the PiP video stream with a VDI manager."""
        self.video.vdi_manager = vdi_manager

    def update_audio(self, level: float) -> None:
        """Update the audio HUD with a new audio level."""
        self.audio.update(level)

    def add_code_diff(self, old_text: str, new_text: str, label: str = "") -> Dict[str, Any]:
        """Add a code diff to the viewer."""
        return self.code_diff.add_diff(old_text, new_text, label)

    def load_model(self, path: str) -> bool:
        """Load a 3D model into the viewer."""
        return self.model_viewer.load_model(path)

    def get_dashboard_state(self) -> Dict[str, Any]:
        """Get the full dashboard state for the WebGL frontend."""
        return {
            "layout": self.grid.get_layout(),
            "video": {"fps": self.video.fps, "frame_count": self.video.get_frame_count()},
            "audio": self.audio.get_state(),
            "code_diff": {
                "current": self.code_diff.get_current_diff(),
                "total": len(self.code_diff.get_all_diffs()),
            },
            "model_viewer": self.model_viewer.get_state(),
            "panels": {k: str(v)[:100] if v else None for k, v in self.grid.panels.items()},
        }

    def render_full(self, sections: List[Dict[str, Any]], title: str = "Dashboard", output: str = None) -> str:
        """Render a full Bento-Grid HTML dashboard to disk."""
        import datetime
        if not output:
            output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "canvas_output", "dashboard.html")
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

        cards = []
        for i, sec in enumerate(sections or []):
            if isinstance(sec, dict):
                heading = sec.get("title", sec.get("name", f"Panel {i + 1}"))
                body = sec.get("content", sec.get("value", sec.get("text", "")))
            else:
                heading, body = f"Panel {i + 1}", str(sec)
            if isinstance(body, (dict, list)):
                body = json.dumps(body, indent=2, default=str)
            cards.append(f"""
    <section class="card card-{i + 1}">
      <h2>{str(heading)[:120]}</h2>
      <div class="body"><pre>{str(body)[:4000]}</pre></div>
    </section>""")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{str(title)[:120]}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#030712; color:#E2E8F0; font-family:'Segoe UI',system-ui,sans-serif; }}
  header {{ padding:24px 32px; border-bottom:1px solid #1E293B; }}
  header h1 {{ color:#00FF66; font-size:24px; }}
  header p {{ color:#64748B; font-size:13px; margin-top:4px; }}
  .grid {{ display:grid; grid-template-columns:repeat(6,1fr); gap:16px; padding:24px 32px; }}
  .card {{ background:#0A1220; border:1px solid #1E293B; border-radius:12px; padding:18px; }}
  .card-1 {{ grid-column:span 2; grid-row:span 2; }}
  .card-2 {{ grid-column:span 2; }}
  .card-3 {{ grid-column:span 2; }}
  .card-4 {{ grid-column:span 2; }}
  .card-5 {{ grid-column:span 2; }}
  h2 {{ color:#00FF66; font-size:16px; margin-bottom:10px; }}
  pre {{ white-space:pre-wrap; word-break:break-word; font-size:13px; color:#E2E8F0; background:#0A1220; }}
  .footer {{ color:#475569; font-size:12px; padding:12px 32px; }}
</style>
</head>
<body>
<header>
  <h1>{str(title)[:120]}</h1>
  <p>JARVIS Canvas Cockpit — rendered {datetime.datetime.now().isoformat(timespec="seconds")}</p>
</header>
<div class="grid">
  {''.join(cards) if cards else '<section class="card"><h2>Empty Dashboard</h2><pre>No sections provided.</pre></section>'}
</div>
<div class="footer">JARVIS OS — Canvas Engine v1</div>
</body>
</html>"""
        with open(output, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Dashboard rendered to {output}")
        return output

    def render_osint(self, target: str, research_data: Dict[str, Any]) -> str:
        """Render an OSINT dashboard for a target."""
        output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "canvas_output", f"osint_{target}.html")
        facts = research_data.get("facts", [])
        relationships = research_data.get("relationships", [])
        rel_text = "\n".join(
            f"• {r.get('from', '?')} --[{r.get('relation', 'related')}]--> {r.get('to', '?')}"
            if isinstance(r, dict) else f"• {r}"
            for r in (relationships or [])
        ) or "No relationships found."
        facts_text = "\n".join(f"• {f}" for f in (facts or [])) or "No facts on record."
        sections = [
            {"title": f"Intel Report: {target}", "content": research_data.get("summary", "No data.")},
            {"title": "Relationships", "content": rel_text},
            {"title": "Known Facts", "content": facts_text},
            {"title": "Tags", "content": ", ".join(research_data.get("tags", []) or []) or "—"},
        ]
        return self.render_full(sections, title=f"OSINT — {target}", output=output)


import time


def create_canvas_engine() -> CanvasEngine:
    """Factory function to create a Canvas Engine instance."""
    return CanvasEngine()


_canvas_singleton = None


def get_canvas() -> CanvasEngine:
    """Get the shared Canvas Engine singleton used by the API."""
    global _canvas_singleton
    if _canvas_singleton is None:
        _canvas_singleton = CanvasEngine()
    return _canvas_singleton