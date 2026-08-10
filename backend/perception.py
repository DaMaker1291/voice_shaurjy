"""JARVIS Universal Perception — The Eyes and Ears of JARVIS.

JARVIS needs to understand what currently exists on the computer,
not just execute commands.

This module provides continuous perception across multiple channels:
  - Screenshot + Vision
  - OCR (text recognition)
  - Window Detection
  - Accessibility Tree
  - DOM/CDP (browser)
  - Filesystem State
  - Process Information
  - Application-Specific State
  - Clipboard
  - Network State

The output is a unified PERCEPTION FRAMEWORK that feeds into
the World Model.

ARCHITECTURE:

    COMPUTER STATE
          │
          ▼
    ┌─────────────────────────────────────┐
    │         PERCEPTION CHANNELS         │
    │                                     │
    │  ┌─────────┐  ┌─────────┐          │
    │  │ SCREEN  │  │  OCR    │          │
    │  └────┬────┘  └────┬────┘          │
    │       │            │               │
    │  ┌────┴────┐  ┌────┴────┐          │
    │  │ WINDOWS │  │ ACCESS  │          │
    │  └────┬────┘  └────┬────┘          │
    │       │            │               │
    │  ┌────┴────┐  ┌────┴────┐          │
    │  │  DOM    │  │ PROCESS │          │
    │  └────┬────┘  └────┬────┘          │
    │       │            │               │
    │  ┌────┴────┐  ┌────┴────┐          │
    │  │ FILES   │  │CLIPBOARD│          │
    │  └────┬────┘  └────┬────┘          │
    │       │            │               │
    └───────┼────────────┼───────────────┘
            │            │
            ▼            ▼
      UNIFIED PERCEPTION STATE
            │
            ▼
        WORLD MODEL
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

log = logging.getLogger("perception")


# ══════════════════════════════════════════════════════════════
#  PERCEPTION DATA TYPES
# ══════════════════════════════════════════════════════════════

class PerceptionType(Enum):
    SCREENSHOT = "screenshot"
    OCR = "ocr"
    WINDOW = "window"
    ACCESSIBILITY = "accessibility"
    DOM = "dom"
    FILESYSTEM = "filesystem"
    PROCESS = "process"
    APPLICATION = "application"
    CLIPBOARD = "clipboard"
    NETWORK = "network"


@dataclass
class UIElement:
    """A semantic UI element detected on screen."""
    id: str
    role: str  # "button", "textbox", "menuitem", "link", "text", etc.
    name: str  # Visible text/label
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, width, height
    center: Tuple[int, int] = (0, 0)
    enabled: bool = True
    focused: bool = False
    children: List[str] = field(default_factory=list)  # Child element IDs
    properties: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # "accessibility", "ocr", "dom", "vision"
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "bounds": self.bounds,
            "center": self.center,
            "enabled": self.enabled,
            "focused": self.focused,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class WindowInfo:
    """Information about an open window."""
    id: str
    title: str
    app_name: str = ""
    pid: int = 0
    is_active: bool = False
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)
    state: str = "normal"  # normal, minimized, maximized
    ui_elements: List[UIElement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "app_name": self.app_name,
            "pid": self.pid,
            "is_active": self.is_active,
            "bounds": self.bounds,
            "state": self.state,
            "ui_elements_count": len(self.ui_elements),
        }


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    name: str
    cpu_percent: float = 0
    memory_mb: float = 0
    status: str = "running"
    command_line: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BrowserState:
    """State of the browser."""
    url: str = ""
    title: str = ""
    tabs: List[Dict[str, str]] = field(default_factory=list)
    dom_snapshot: str = ""
    visible_text: str = ""
    links: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FilesystemState:
    """State of relevant filesystem locations."""
    desktop_files: List[Dict[str, Any]] = field(default_factory=list)
    recent_files: List[Dict[str, Any]] = field(default_factory=list)
    workspace_files: List[Dict[str, Any]] = field(default_factory=list)
    downloads_files: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PerceptionSnapshot:
    """A complete snapshot of computer state at a point in time."""
    timestamp: float
    screenshot_bytes: bytes = b""
    screenshot_width: int = 0
    screenshot_height: int = 0
    ocr_text: str = ""
    windows: List[WindowInfo] = field(default_factory=list)
    active_window: Optional[WindowInfo] = None
    processes: List[ProcessInfo] = field(default_factory=list)
    browser: Optional[BrowserState] = None
    filesystem: Optional[FilesystemState] = None
    clipboard_text: str = ""
    ui_elements: List[UIElement] = field(default_factory=list)
    cursor_position: Tuple[int, int] = (0, 0)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "screenshot_size": len(self.screenshot_bytes),
            "screenshot_dimensions": f"{self.screenshot_width}x{self.screenshot_height}",
            "ocr_text_length": len(self.ocr_text),
            "windows_count": len(self.windows),
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "processes_count": len(self.processes),
            "browser_url": self.browser.url if self.browser else None,
            "ui_elements_count": len(self.ui_elements),
            "clipboard_length": len(self.clipboard_text),
        }


# ══════════════════════════════════════════════════════════════
#  PERCEPTION CHANNELS
# ══════════════════════════════════════════════════════════════

class ScreenshotChannel:
    """Captures and analyzes screenshots."""

    def capture(self) -> Tuple[bytes, int, int]:
        """Capture screenshot, return (jpeg_bytes, width, height)."""
        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            result = fabric.computer.screenshot()
            if result.ok and result.data:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(result.data))
                return result.data, img.width, img.height
        except Exception as e:
            log.debug(f"Screenshot capture failed: {e}")
        return b"", 0, 0

    def analyze_with_vision(self, screenshot_bytes: bytes,
                           question: str = "Describe what you see") -> str:
        """Use vision model to analyze screenshot."""
        if not screenshot_bytes:
            return ""
        try:
            from model_provider import get_model_router
            router = get_model_router()
            response = router.vision(screenshot_bytes, question)
            return response.text
        except Exception as e:
            log.debug(f"Vision analysis failed: {e}")
            return ""


class OCRChannel:
    """Extracts text from screenshots."""

    def extract_text(self, screenshot_bytes: bytes) -> str:
        """Extract all visible text from a screenshot."""
        if not screenshot_bytes:
            return ""

        # Try Tesseract OCR
        try:
            import pytesseract
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(screenshot_bytes))
            text = pytesseract.image_to_string(img)
            return text.strip()
        except ImportError:
            pass

        # Try Windows OCR (if available)
        if sys.platform == "win32":
            try:
                # Windows OCR via PowerShell
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(screenshot_bytes)
                    tmp_path = f.name

                result = subprocess.run(
                    ["powershell", "-Command",
                     f"Add-Type -AssemblyName System.Windows.Forms; "
                     f"$img = [System.Drawing.Image]::FromFile('{tmp_path}'); "
                     f"# Windows OCR not directly accessible via PS"],
                    capture_output=True, text=True, timeout=10
                )
                os.unlink(tmp_path)
            except Exception:
                pass

        # Fallback: use vision model for OCR
        try:
            from model_provider import get_model_router
            router = get_model_router()
            response = router.vision(screenshot_bytes, "Extract all visible text from this image. Return only the text, no description.")
            return response.text
        except Exception:
            return ""


class WindowChannel:
    """Detects and lists open windows."""

    def list_windows(self) -> List[WindowInfo]:
        """Get all open windows."""
        windows = []

        try:
            if sys.platform == "win32":
                windows = self._list_windows_win32()
            elif sys.platform == "darwin":
                windows = self._list_windows_macos()
            elif sys.platform == "linux":
                windows = self._list_windows_linux()
        except Exception as e:
            log.debug(f"Window listing failed: {e}")

        return windows

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the currently active/focused window."""
        windows = self.list_windows()
        for w in windows:
            if w.is_active:
                return w
        return windows[0] if windows else None

    def _list_windows_win32(self) -> List[WindowInfo]:
        """List windows on Windows via PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object Id, MainWindowTitle, ProcessName | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5
            )
            data = json.loads(result.stdout or "[]")
            if isinstance(data, dict):
                data = [data]

            windows = []
            for p in data:
                w = WindowInfo(
                    id=str(p.get("Id", "")),
                    title=p.get("MainWindowTitle", ""),
                    app_name=p.get("ProcessName", ""),
                    pid=p.get("Id", 0),
                )
                windows.append(w)
            return windows
        except Exception:
            return []

    def _list_windows_macos(self) -> List[WindowInfo]:
        """List windows on macOS via AppleScript."""
        try:
            script = '''
            tell application "System Events"
                set windowList to {}
                repeat with proc in (every process whose background only is false)
                    set procName to name of proc
                    repeat with win in (every window of proc)
                        set winTitle to name of win
                        if winTitle is not "" then
                            set end of windowList to procName & " — " & winTitle
                        end if
                    end repeat
                end repeat
                return windowList
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10
            )
            windows = []
            for line in result.stdout.strip().split(", "):
                if " — " in line:
                    app, title = line.split(" — ", 1)
                    windows.append(WindowInfo(
                        id=f"win_{len(windows)}",
                        title=title.strip(),
                        app_name=app.strip(),
                    ))
            return windows
        except Exception:
            return []

    def _list_windows_linux(self) -> List[WindowInfo]:
        """List windows on Linux via wmctrl."""
        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True, text=True, timeout=5
            )
            windows = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append(WindowInfo(
                        id=parts[0],
                        title=parts[3],
                        pid=int(parts[2]) if parts[2].isdigit() else 0,
                    ))
            return windows
        except Exception:
            return []


class AccessibilityChannel:
    """Reads the accessibility tree for semantic UI understanding."""

    def get_ui_elements(self) -> List[UIElement]:
        """Get UI elements from the accessibility tree."""
        elements = []

        try:
            if sys.platform == "win32":
                elements = self._get_elements_win32()
            elif sys.platform == "darwin":
                elements = self._get_elements_macos()
        except Exception as e:
            log.debug(f"Accessibility reading failed: {e}")

        return elements

    def _get_elements_win32(self) -> List[UIElement]:
        """Get UI elements via Windows UI Automation."""
        try:
            # Try uiautomation library
            import uiautomation as auto
            elements = []

            def walk_element(ctrl, depth=0):
                if depth > 5:
                    return
                try:
                    name = ctrl.Name or ""
                    control_type = ctrl.ControlTypeName or ""
                    if name:
                        rect = ctrl.BoundingRectangle
                        bounds = (0, 0, 0, 0)
                        if rect:
                            bounds = (int(rect.left), int(rect.top),
                                     int(rect.width), int(rect.height))
                        center = (bounds[0] + bounds[2] // 2,
                                 bounds[1] + bounds[3] // 2)

                        elements.append(UIElement(
                            id=f"uia_{len(elements)}",
                            role=control_type.lower(),
                            name=name,
                            bounds=bounds,
                            center=center,
                            source="accessibility",
                        ))

                    for child in ctrl.GetChildren():
                        walk_element(child, depth + 1)
                except Exception:
                    pass

            root = auto.GetRootControl()
            walk_element(root)
            return elements[:100]  # Limit to prevent overwhelming

        except ImportError:
            log.debug("uiautomation not available")
            return []

    def _get_elements_macos(self) -> List[UIElement]:
        """Get UI elements via macOS Accessibility API."""
        # macOS accessibility requires PyObjC
        return []


class DOMChannel:
    """Reads browser DOM via CDP."""

    def get_dom_state(self) -> BrowserState:
        """Get current browser state from DOM."""
        state = BrowserState()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            if fabric._browser:
                state.url = fabric.browser.get_url()
                state.title = fabric.browser.get_title()

                # Get visible text
                result = fabric.browser.get_text()
                if result.ok:
                    state.visible_text = result.data or ""

                # Get links
                result = fabric.browser.extract_links()
                if result.ok and result.data:
                    state.links = result.data if isinstance(result.data, list) else []

                # Get tabs
                result = fabric.browser.list_windows()  # CDP targets
                if result.ok and result.data:
                    state.tabs = [
                        {"title": t.get("title", ""), "url": t.get("url", "")}
                        for t in result.data if isinstance(t, dict)
                    ]
        except Exception as e:
            log.debug(f"DOM reading failed: {e}")

        return state


class FilesystemChannel:
    """Reads filesystem state."""

    def get_state(self, watch_dirs: List[str] = None) -> FilesystemState:
        """Get filesystem state for watched directories."""
        state = FilesystemState()
        home = os.path.expanduser("~")

        dirs_to_watch = watch_dirs or [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Downloads"),
        ]

        for d in dirs_to_watch:
            files = self._list_dir(d)
            if "Desktop" in d:
                state.desktop_files = files
            elif "Documents" in d:
                state.recent_files = files  # Sort by mod time
            elif "Downloads" in d:
                state.downloads_files = files

        return state

    def _list_dir(self, path: str, max_files: int = 20) -> List[Dict[str, Any]]:
        """List files in a directory."""
        try:
            entries = []
            p = Path(path)
            if not p.exists():
                return []

            for f in sorted(p.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if len(entries) >= max_files:
                    break
                if f.name.startswith("."):
                    continue
                stat = f.stat()
                entries.append({
                    "name": f.name,
                    "path": str(f),
                    "is_dir": f.is_dir(),
                    "size": stat.st_size if f.is_file() else 0,
                    "modified": stat.st_mtime,
                })
            return entries
        except Exception:
            return []


class ProcessChannel:
    """Lists running processes."""

    def list_processes(self) -> List[ProcessInfo]:
        """Get running processes."""
        try:
            if sys.platform == "win32":
                return self._list_win32()
            else:
                return self._list_unix()
        except Exception as e:
            log.debug(f"Process listing failed: {e}")
            return []

    def _list_win32(self) -> List[ProcessInfo]:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Select-Object Id, ProcessName, CPU, "
                 "WorkingSet64 | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5
            )
            data = json.loads(result.stdout or "[]")
            if isinstance(data, dict):
                data = [data]
            return [
                ProcessInfo(
                    pid=p.get("Id", 0),
                    name=p.get("ProcessName", ""),
                    cpu_percent=p.get("CPU", 0) or 0,
                    memory_mb=(p.get("WorkingSet64", 0) or 0) / 1024 / 1024,
                )
                for p in data
            ]
        except Exception:
            return []

    def _list_unix(self) -> List[ProcessInfo]:
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            processes = []
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append(ProcessInfo(
                        pid=int(parts[1]),
                        name=parts[10].split("/")[-1],
                        cpu_percent=float(parts[2]),
                        memory_mb=float(parts[5]) / 1024 if parts[5].isdigit() else 0,
                    ))
            return processes[:50]
        except Exception:
            return []


class ClipboardChannel:
    """Reads clipboard state."""

    def get_text(self) -> str:
        """Get current clipboard text content."""
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-Clipboard -Format Text -Raw"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()
            elif sys.platform == "darwin":
                result = subprocess.run(
                    ["pbpaste"], capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()
            else:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()
        except Exception:
            return ""


# ══════════════════════════════════════════════════════════════
#  UNIVERSAL PERCEPTION ENGINE
# ══════════════════════════════════════════════════════════════

class UniversalPerception:
    """The unified perception engine.

    Continuously builds a picture of what exists on the computer.
    Multiple perception channels feed into a unified snapshot.
    """

    def __init__(self):
        self._screenshot = ScreenshotChannel()
        self._ocr = OCRChannel()
        self._windows = WindowChannel()
        self._accessibility = AccessibilityChannel()
        self._dom = DOMChannel()
        self._filesystem = FilesystemChannel()
        self._processes = ProcessChannel()
        self._clipboard = ClipboardChannel()
        self._last_snapshot: Optional[PerceptionSnapshot] = None
        self._lock = threading.Lock()

    def perceive(self, include_screenshot: bool = True,
                include_ocr: bool = True,
                include_windows: bool = True,
                include_accessibility: bool = True,
                include_dom: bool = True,
                include_filesystem: bool = True,
                include_processes: bool = True,
                include_clipboard: bool = True) -> PerceptionSnapshot:
        """Take a complete perception snapshot.

        This is the main entry point. Gathers state from all channels.
        """
        snapshot = PerceptionSnapshot(timestamp=time.time())

        # Screenshot
        if include_screenshot:
            ss_bytes, w, h = self._screenshot.capture()
            snapshot.screenshot_bytes = ss_bytes
            snapshot.screenshot_width = w
            snapshot.screenshot_height = h

        # OCR
        if include_ocr and snapshot.screenshot_bytes:
            snapshot.ocr_text = self._ocr.extract_text(snapshot.screenshot_bytes)

        # Windows
        if include_windows:
            snapshot.windows = self._windows.list_windows()
            snapshot.active_window = self._windows.get_active_window()

        # Accessibility
        if include_accessibility:
            snapshot.ui_elements = self._accessibility.get_ui_elements()

        # Browser DOM
        if include_dom:
            snapshot.browser = self._dom.get_dom_state()

        # Filesystem
        if include_filesystem:
            snapshot.filesystem = self._filesystem.get_state()

        # Processes
        if include_processes:
            snapshot.processes = self._processes.list_processes()

        # Clipboard
        if include_clipboard:
            snapshot.clipboard_text = self._clipboard.get_text()

        with self._lock:
            self._last_snapshot = snapshot

        return snapshot

    def get_snapshot(self) -> Optional[PerceptionSnapshot]:
        """Get the last perception snapshot."""
        with self._lock:
            return self._last_snapshot

    def find_ui_element(self, text: str,
                       role: str = None) -> Optional[UIElement]:
        """Find a UI element by text or role.

        Uses the perception system to locate semantic UI elements.
        """
        snapshot = self.get_snapshot()
        if not snapshot:
            snapshot = self.perceive(include_screenshot=False)

        text_lower = text.lower()

        # Search accessibility elements first (highest confidence)
        for elem in snapshot.ui_elements:
            if text_lower in elem.name.lower():
                if role is None or elem.role.lower() == role.lower():
                    return elem

        # Search OCR elements
        if snapshot.ocr_text:
            # OCR text is less structured, but we can search it
            pass

        # Use vision model as last resort
        if snapshot.screenshot_bytes:
            vision_result = self._screenshot.analyze_with_vision(
                snapshot.screenshot_bytes,
                f"Find the UI element labeled '{text}'. What are its approximate coordinates?"
            )
            if vision_result:
                # Parse coordinates from vision response
                import re
                coords = re.findall(r'(\d+)[\s,]+(\d+)', vision_result)
                if coords:
                    x, y = int(coords[0][0]), int(coords[0][1])
                    return UIElement(
                        id="vision_detected",
                        role="unknown",
                        name=text,
                        center=(x, y),
                        source="vision",
                        confidence=0.7,
                    )

        return None

    def get_context_summary(self) -> str:
        """Get a human-readable summary of current computer state."""
        snapshot = self.get_snapshot()
        if not snapshot:
            return "No perception data available"

        lines = []

        # Active window
        if snapshot.active_window:
            lines.append(f"Active: {snapshot.active_window.app_name} — {snapshot.active_window.title}")

        # Other windows
        if snapshot.windows:
            other = [w for w in snapshot.windows if not w.is_active][:5]
            if other:
                lines.append("Other windows:")
                for w in other:
                    lines.append(f"  - {w.app_name}: {w.title}")

        # Browser
        if snapshot.browser and snapshot.browser.url:
            lines.append(f"Browser: {snapshot.browser.url}")

        # Recent files
        if snapshot.filesystem:
            recent = snapshot.filesystem.desktop_files[:3]
            if recent:
                lines.append("Desktop files:")
                for f in recent:
                    lines.append(f"  - {f['name']}")

        # Clipboard
        if snapshot.clipboard_text:
            clip_preview = snapshot.clipboard_text[:100]
            lines.append(f"Clipboard: {clip_preview}...")

        return "\n".join(lines)


# ── Singleton ──
_perception: Optional[UniversalPerception] = None


def get_perception() -> UniversalPerception:
    global _perception
    if _perception is None:
        _perception = UniversalPerception()
    return _perception
