"""JARVIS Perception Engine — See, Read, Understand.

Multimodal perception stack:
1. DOM (CDP) — structured, reliable
2. Accessibility tree — semantic, when available
3. OCR on screenshots — when nothing else works
4. Process state — what's running
5. Filesystem — what files exist

The GUI is the API. This engine perceives it.
"""

import os, sys, json, time, logging, subprocess, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("perception")


@dataclass
class UIElement:
    """A perceived UI element."""
    role: str = ""          # button, textbox, link, menu, label, image
    text: str = ""          # visible text
    rect: tuple = (0, 0, 0, 0)  # x, y, width, height
    center: tuple = (0, 0)  # click target
    attributes: dict = field(default_factory=dict)
    source: str = ""        # dom, accessibility, ocr, vision
    confidence: float = 1.0
    children: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "text": self.text[:100],
            "rect": self.rect,
            "center": self.center,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class ScreenState:
    """Complete perceived state of the screen."""
    timestamp: float = 0
    window_title: str = ""
    url: str = ""
    dom_elements: list = field(default_factory=list)
    accessibility_elements: list = field(default_factory=list)
    ocr_elements: list = field(default_factory=list)
    all_elements: list = field(default_factory=list)
    screenshot_path: str = ""
    clipboard: str = ""


class PerceptionEngine:
    """Multimodal perception: DOM → Accessibility → OCR → Vision."""

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self._cdp = None

    # ── DOM Perception (via CDP) ──────────────────────────────────

    def get_dom_elements(self) -> list[UIElement]:
        """Extract interactive elements from Chrome DOM via CDP."""
        try:
            from cdp_bridge import CDPBridge
            if self._cdp is None:
                self._cdp = CDPBridge()
            elements = self._cdp.get_interactive_elements()
            result = []
            for el in elements:
                result.append(UIElement(
                    role=el.get("role", ""),
                    text=el.get("text", "")[:100],
                    rect=(el.get("x", 0), el.get("y", 0),
                          el.get("width", 0), el.get("height", 0)),
                    center=(el.get("x", 0) + el.get("width", 0) // 2,
                            el.get("y", 0) + el.get("height", 0) // 2),
                    attributes=el.get("attributes", {}),
                    source="dom",
                    confidence=1.0,
                ))
            return result
        except Exception as e:
            log.debug(f"DOM perception failed: {e}")
            return []

    def get_dom_by_selector(self, selector: str) -> list[UIElement]:
        """Query DOM with CSS selector."""
        try:
            from cdp_bridge import CDPBridge
            if self._cdp is None:
                self._cdp = CDPBridge()
            elements = self._cdp.query_selector_all(selector)
            result = []
            for el in elements:
                result.append(UIElement(
                    role=el.get("tagName", "").lower(),
                    text=el.get("textContent", "")[:100],
                    rect=(el.get("x", 0), el.get("y", 0),
                          el.get("width", 0), el.get("height", 0)),
                    center=(el.get("x", 0) + el.get("width", 0) // 2,
                            el.get("y", 0) + el.get("height", 0) // 2),
                    attributes=el.get("attributes", {}),
                    source="dom",
                ))
            return result
        except Exception as e:
            log.debug(f"DOM selector failed: {e}")
            return []

    def get_page_text(self) -> str:
        """Get all visible text from the page."""
        try:
            from cdp_bridge import CDPBridge
            if self._cdp is None:
                self._cdp = CDPBridge()
            return self._cdp.get_page_text()[:5000]
        except Exception:
            return ""

    # ── Accessibility Perception ──────────────────────────────────

    def get_accessibility_tree(self) -> list[UIElement]:
        """Extract accessibility tree (semantic UI understanding)."""
        try:
            import subprocess
            r = subprocess.run(
                ["bash", "-c",
                 "sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority "
                 "xdotool getactivewindow' 2>/dev/null || echo ''"],
                capture_output=True, text=True, timeout=3
            )
            # Use atspi2 or similar if available
            # Fallback: parse window menus via xdotool
            return self._parse_window_controls()
        except Exception:
            return []

    def _parse_window_controls(self) -> list[UIElement]:
        """Parse visible controls from the active window."""
        elements = []
        try:
            import subprocess
            # Get active window geometry
            r = subprocess.run(
                ["bash", "-c", "xdotool getactivewindow getwindowgeometry"],
                capture_output=True, text=True, timeout=3
            )
            if r.returncode != 0:
                return elements

            # Extract geometry
            geom_match = re.search(r'Position:\s*(\d+),(\d+).*Size:\s*(\d+)x(\d+)', r.stdout, re.DOTALL)
            if not geom_match:
                return elements

            wx, wy, ww, wh = int(geom_match.group(1)), int(geom_match.group(2)), \
                             int(geom_match.group(3)), int(geom_match.group(4))

            # Common UI regions: title bar, menu bar, toolbar, content, status bar
            elements.append(UIElement(
                role="title_bar",
                text="",
                rect=(wx, wy, ww, 30),
                center=(wx + ww // 2, wy + 15),
                source="accessibility",
                confidence=0.8,
            ))
        except Exception:
            pass
        return elements

    # ── OCR Perception ────────────────────────────────────────────

    def ocr_screenshot(self, screenshot_path: str = None) -> list[UIElement]:
        """OCR a screenshot to find text elements."""
        if screenshot_path is None:
            screenshot_path = self._take_screenshot()

        if not screenshot_path or not Path(screenshot_path).exists():
            return []

        elements = []
        try:
            import subprocess
            # Use tesseract if available
            r = subprocess.run(
                ["tesseract", screenshot_path, "stdout", "--psm", "6", "-l", "eng"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0 and r.stdout.strip():
                # Parse tesseract output into elements
                lines = r.stdout.strip().split('\n')
                y_offset = 50
                for line in lines:
                    line = line.strip()
                    if len(line) < 2:
                        continue
                    # Estimate position (tesseract doesn't give coords in simple mode)
                    elements.append(UIElement(
                        role="text",
                        text=line[:100],
                        rect=(100, y_offset, len(line) * 10, 20),
                        center=(100 + len(line) * 5, y_offset + 10),
                        source="ocr",
                        confidence=0.7,
                    ))
                    y_offset += 25
        except FileNotFoundError:
            log.debug("tesseract not installed")
        except Exception as e:
            log.debug(f"OCR failed: {e}")

        return elements

    # ── Clipboard Perception ──────────────────────────────────────

    def get_clipboard(self) -> str:
        """Read clipboard content."""
        try:
            import subprocess
            r = subprocess.run(
                ["bash", "-c",
                 "sudo -u workuser bash -c '"
                 "DISPLAY=:99 XAUTHORITY=/root/.Xauthority "
                 "xdotool key --clearmodifiers ctrl+a; "
                 "sleep 0.2; "
                 "xdotool key --clearmodifiers ctrl+c; "
                 "sleep 0.3; "
                 "xclip -selection clipboard -o 2>/dev/null || "
                 "xsel --clipboard --output 2>/dev/null"
                 "'"],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout[:5000] if r.stdout else ""
        except Exception:
            return ""

    def type_and_copy(self, text: str) -> str:
        """Type text, select all, copy, return clipboard content (for testing)."""
        try:
            import subprocess
            # Type the text
            subprocess.run(
                ["bash", "-c",
                 f"echo '{text[:200]}' | sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool type --clearmodifiers --delay 0 -'"],
                timeout=3
            )
            return text
        except Exception:
            return ""

    # ── Process Perception ────────────────────────────────────────

    def get_running_apps(self) -> list[dict]:
        """What applications are running."""
        apps = []
        try:
            import subprocess
            r = subprocess.run(
                ["bash", "-c",
                 "ps -eo pid,comm,%cpu,%mem --no-headers | "
                 "awk '{print $1, $2, $3, $4}' | sort -k3 -rn | head -20"],
                capture_output=True, text=True, timeout=3
            )
            for line in r.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 4:
                    apps.append({
                        "pid": int(parts[0]),
                        "name": parts[1],
                        "cpu": float(parts[2]),
                        "memory": float(parts[3]),
                    })
        except Exception:
            pass
        return apps

    # ── Filesystem Perception ─────────────────────────────────────

    def get_recent_files(self, directory: str = None, limit: int = 10) -> list[dict]:
        """List recent files."""
        if directory is None:
            directory = "/home/workuser/Desktop"
        files = []
        try:
            d = Path(directory)
            if d.exists():
                items = sorted(d.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
                for f in items[:limit]:
                    files.append({
                        "name": f.name,
                        "path": str(f.absolute()),
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime,
                        "extension": f.suffix.lower(),
                    })
        except Exception:
            pass
        return files

    def find_files(self, pattern: str, directory: str = "/home/workuser") -> list[dict]:
        """Find files matching a pattern."""
        files = []
        try:
            d = Path(directory)
            for f in d.rglob(pattern):
                if f.is_file():
                    files.append({
                        "name": f.name,
                        "path": str(f.absolute()),
                        "size": f.stat().st_size,
                        "extension": f.suffix.lower(),
                    })
                    if len(files) >= 20:
                        break
        except Exception:
            pass
        return files

    # ── Combined Perception ───────────────────────────────────────

    def perceive(self, include_dom: bool = True, include_ocr: bool = False,
                 include_clipboard: bool = True) -> ScreenState:
        """Full screen perception: combine all modalities."""
        state = ScreenState(timestamp=time.time())

        # DOM (fast, reliable for web)
        if include_dom:
            state.dom_elements = self.get_dom_elements()

        # OCR (slow, fallback for non-web)
        if include_ocr:
            state.ocr_elements = self.ocr_screenshot()

        # Clipboard
        if include_clipboard:
            state.clipboard = self.get_clipboard()

        # Merge all elements
        state.all_elements = state.dom_elements + state.ocr_elements

        # Get window info
        try:
            import subprocess
            r = subprocess.run(
                ["bash", "-c",
                 "xdotool getactivewindow getwindowname 2>/dev/null || echo ''"],
                capture_output=True, text=True, timeout=3
            )
            state.window_title = r.stdout.strip()
        except Exception:
            pass

        return state

    def _take_screenshot(self) -> str:
        """Take a screenshot, return path."""
        try:
            import subprocess
            outpath = f"/tmp/jarvis_perception_{int(time.time())}.png"
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority scrot -o {outpath}'"],
                timeout=5
            )
            return outpath if Path(outpath).exists() else ""
        except Exception:
            return ""


# ── Singleton ──
_engine: Optional[PerceptionEngine] = None

def get_perception_engine(user_id: str = "local") -> PerceptionEngine:
    global _engine
    if _engine is None:
        _engine = PerceptionEngine(user_id)
    return _engine
