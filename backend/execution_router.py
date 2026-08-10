"""
JARVIS Dual-Display Sovereign Execution Controller.

Routes commands to the correct display:
- DISPLAY=:99 (WSL VDI) — Default, non-intrusive background execution
- DISPLAY=:0 (Host) — Foreground when user requests direct interaction

Features:
- Vision & coordinate mapping for OCR-guided automation
- Sub-50ms screen capture using mss
- Automatic display selection based on command type
- Unified execution API for all JARVIS actions
"""
import os
import sys
import time
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("execution_router")


class TargetDisplay(Enum):
    """Target display for command execution."""
    HOST = ":0"           # Foreground host desktop
    VDI = ":99"           # Background WSL VDI
    AUTO = "auto"         # Automatic selection


class ExecutionMode(Enum):
    """Execution mode."""
    BACKGROUND = "background"   # Non-intrusive, runs in VDI
    FOREGROUND = "foreground"   # Direct user interaction
    HYBRID = "hybrid"           # Start in VDI, promote to host if needed


@dataclass
class ExecutionContext:
    """Context for command execution."""
    target_display: TargetDisplay = TargetDisplay.VDI
    mode: ExecutionMode = ExecutionMode.BACKGROUND
    browser: str = "chrome"
    url: str = ""
    app: str = ""
    command: list = field(default_factory=list)
    anti_detect: bool = True
    human_like: bool = True
    timeout: int = 30


class ScreenCapture:
    """Fast screen capture for vision-guided automation."""

    def __init__(self):
        self._capture_cache = {}

    def capture(self, display: str = ":99", region: tuple = None) -> Optional[bytes]:
        """Capture screen buffer from display."""
        try:
            # Use xwd + convert for X11 displays in WSL
            if display.startswith(":"):
                return self._capture_x11(display, region)
            else:
                return self._capture_windows(region)
        except Exception as e:
            logger.warning(f"Screen capture failed: {e}")
            return None

    def _capture_x11(self, display: str, region: tuple = None) -> Optional[bytes]:
        """Capture from X11 display via WSL."""
        try:
            cmd_parts = ["wsl", "-e", "bash", "-c"]
            if region:
                x, y, w, h = region
                capture_cmd = f"DISPLAY={display} import -window root -crop {w}x{h}+{x}+{y} png:- 2>/dev/null"
            else:
                capture_cmd = f"DISPLAY={display} import -window root png:- 2>/dev/null"

            result = subprocess.run(
                cmd_parts + [capture_cmd],
                capture_output=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            pass
        return None

    def _capture_windows(self, region: tuple = None) -> Optional[bytes]:
        """Capture from Windows desktop."""
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                if region:
                    x, y, w, h = region
                    monitor = {"left": x, "top": y, "width": w, "height": h}
                else:
                    monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except Exception:
            pass
        return None

    def ocr_region(self, display: str, region: tuple = None) -> str:
        """OCR a region of the screen."""
        img_bytes = self.capture(display, region)
        if not img_bytes:
            return ""

        try:
            import io
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()
            import numpy as np
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            img_np = np.array(img)
            result, _ = ocr(img_np)
            if result:
                return "\n".join([line[1] for line in result])
        except Exception:
            pass
        return ""


class CoordinateMapper:
    """Map OCR bounding boxes to xdotool/pyautogui coordinates."""

    def __init__(self, display: str = ":99"):
        self.display = display
        self.scale_x = 1.0
        self.scale_y = 1.0

    def calibrate(self):
        """Calibrate coordinate mapping for display."""
        try:
            # Get display resolution
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.display} xdotool getdisplaygeometry 2>/dev/null"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout:
                parts = result.stdout.strip().split()
                if len(parts) == 2:
                    width, height = int(parts[0]), int(parts[1])
                    self.scale_x = width / 1920  # Normalize to 1920
                    self.scale_y = height / 1080
        except Exception:
            pass

    def map_coordinates(self, x: int, y: int) -> tuple[int, int]:
        """Map normalized coordinates to display coordinates."""
        return int(x * self.scale_x), int(y * self.scale_y)

    def click_at(self, x: int, y: int, display: str = None):
        """Click at mapped coordinates."""
        display = display or self.display
        mapped_x, mapped_y = self.map_coordinates(x, y)
        try:
            subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={display} xdotool mousemove {mapped_x} {mapped_y} click 1"],
                timeout=5
            )
        except Exception:
            pass

    def type_at(self, x: int, y: int, text: str, display: str = None):
        """Click and type at coordinates."""
        display = display or self.display
        mapped_x, mapped_y = self.map_coordinates(x, y)
        try:
            subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={display} xdotool mousemove {mapped_x} {mapped_y} click 1 && "
                 f"DISPLAY={display} xdotool type --delay 50 '{text}'"],
                timeout=10
            )
        except Exception:
            pass


class ExecutionRouter:
    """Routes execution commands to the correct display."""

    def __init__(self):
        self.screen = ScreenCapture()
        self.mapper = CoordinateMapper()
        self._context_stack: list[ExecutionContext] = []

    def route(self, ctx: ExecutionContext) -> dict:
        """Route a command to the correct display and execute."""
        # Auto-select display
        if ctx.target_display == TargetDisplay.AUTO:
            ctx.target_display = self._auto_select(ctx)

        display = ctx.target_display.value
        logger.info(f"Routing to {display}: {ctx.app or ctx.url or ctx.command}")

        # Execute based on type
        if ctx.url or ctx.app in ("chrome", "edge", "firefox", "google-chrome"):
            return self._execute_browser(ctx, display)
        elif ctx.app:
            return self._execute_app(ctx, display)
        elif ctx.command:
            return self._execute_command(ctx, display)
        else:
            return {"success": False, "error": "No command specified"}

    def _auto_select(self, ctx: ExecutionContext) -> TargetDisplay:
        """Auto-select display based on command type."""
        # Background tasks → VDI
        if ctx.mode == ExecutionMode.BACKGROUND:
            return TargetDisplay.VDI

        # User explicitly wants foreground
        if ctx.mode == ExecutionMode.FOREGROUND:
            return TargetDisplay.HOST

        # Default: VDI for non-intrusive execution
        return TargetDisplay.VDI

    def _execute_browser(self, ctx: ExecutionContext, display: str) -> dict:
        """Execute browser command on display."""
        url = ctx.url
        app = ctx.app or "chrome"

        app_map = {
            "chrome": "google-chrome-stable",
            "google-chrome": "google-chrome-stable",
            "edge": "microsoft-edge-stable",
            "firefox": "firefox",
        }
        cmd = app_map.get(app, "google-chrome-stable")

        args = [
            cmd,
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if ctx.anti_detect:
            args.extend([
                "--disable-blink-features=AutomationControlled",
                "--password-store=basic",
            ])
        if url:
            args.append(url)

        launch_cmd = f"DISPLAY={display} {' '.join(args)} &"
        self._wsl_exec(launch_cmd)

        return {"success": True, "display": display, "app": app, "url": url}

    def _execute_app(self, ctx: ExecutionContext, display: str) -> dict:
        """Execute app launch on display."""
        app_map = {
            "terminal": "xfce4-terminal",
            "thunar": "thunar",
            "gimp": "gimp",
            "calculator": "gnome-calculator",
            "notepad": "mousepad",
            "vlc": "vlc",
        }
        cmd = app_map.get(ctx.app, ctx.app)
        self._wsl_exec(f"DISPLAY={display} {cmd} &")
        return {"success": True, "display": display, "app": ctx.app}

    def _execute_command(self, ctx: ExecutionContext, display: str) -> dict:
        """Execute arbitrary command on display."""
        cmd_str = " ".join(ctx.command)
        self._wsl_exec(f"DISPLAY={display} {cmd_str} &")
        return {"success": True, "display": display, "command": cmd_str}

    def _wsl_exec(self, cmd: str) -> str:
        """Execute in WSL."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout
        except Exception:
            return ""

    # ── Vision-Guided Automation ──────────────────────────────────────────
    def find_on_screen(self, display: str, ocr_text: str) -> Optional[tuple]:
        """Find text on screen and return coordinates."""
        img_bytes = self.screen.capture(display)
        if not img_bytes:
            return None

        try:
            import io, numpy as np
            from PIL import Image
            from rapidocr_onnxruntime import RapidOCR

            ocr = RapidOCR()
            img = Image.open(io.BytesIO(img_bytes))
            img_np = np.array(img)
            result, _ = ocr(img_np)

            if result:
                for line in result:
                    bbox, text, confidence = line
                    if ocr_text.lower() in text.lower() and confidence > 0.7:
                        # Return center of bounding box
                        x = sum(p[0] for p in bbox) / 4
                        y = sum(p[1] for p in bbox) / 4
                        return (int(x), int(y))
        except Exception:
            pass
        return None

    def click_text(self, display: str, text: str) -> dict:
        """Find and click on text on screen."""
        coords = self.find_on_screen(display, text)
        if coords:
            self.mapper.display = display
            self.mapper.click_at(coords[0], coords[1], display)
            return {"success": True, "clicked": text, "coords": coords}
        return {"success": False, "error": f"Text not found: {text}"}

    def get_screenshot_base64(self, display: str = ":99") -> str:
        """Get screenshot as base64 for PiP display."""
        import base64
        img_bytes = self.screen.capture(display)
        if img_bytes:
            return base64.b64encode(img_bytes).decode()
        return ""


# ── Convenience Functions ──────────────────────────────────────────────────

def execute_in_vdi(app: str = "", url: str = "", command: list = None) -> dict:
    """Quick execute in VDI background."""
    router = ExecutionRouter()
    ctx = ExecutionContext(
        target_display=TargetDisplay.VDI,
        mode=ExecutionMode.BACKGROUND,
        app=app, url=url, command=command or [],
    )
    return router.route(ctx)


def execute_on_host(app: str = "", url: str = "", command: list = None) -> dict:
    """Quick execute on host foreground."""
    router = ExecutionRouter()
    ctx = ExecutionContext(
        target_display=TargetDisplay.HOST,
        mode=ExecutionMode.FOREGROUND,
        app=app, url=url, command=command or [],
    )
    return router.route(ctx)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[ROUTE] %(message)s")
    router = ExecutionRouter()
    print("=== Execution Router Status ===")
    print(f"  Host Display: {TargetDisplay.HOST.value}")
    print(f"  VDI Display: {TargetDisplay.VDI.value}")
    print(f"  Screen capture: {type(router.screen).__name__}")
    print(f"  Coordinate mapper: {type(router.mapper).__name__}")
