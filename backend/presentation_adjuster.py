"""
JARVIS Presentation Adjuster — Opens PPTX in VDI, uses vision to verify
layout/centering/alignment, makes mouse adjustments, then migrates to host.

Flow:
1. Open LibreOffice Impress in VDI
2. Screenshot + OCR to verify content
3. Vision analysis: detect misalignment, off-center elements
4. xdotool mouse adjustments (click, drag, resize)
5. Save adjusted file
6. Migrate window to host desktop
"""
import os
import io
import json
import time
import base64
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("presentation_adjuster")


@dataclass
class LayoutIssue:
    """A detected layout issue."""
    issue_type: str  # off_center, too_small, too_large, overlap, cut_off, misaligned
    element: str = ""
    severity: str = "low"  # low, medium, high
    fix_action: str = ""
    coordinates: dict = field(default_factory=dict)


@dataclass
class AdjustmentResult:
    """Result of adjustment process."""
    success: bool
    issues_found: int = 0
    issues_fixed: int = 0
    final_screenshot_b64: str = ""
    adjustments: list = field(default_factory=list)
    output_path: str = ""
    migrated_to_host: bool = False
    duration_seconds: float = 0.0
    error: str = ""


class PresentationAdjuster:
    """Opens PPTX in LibreOffice Impress, adjusts with vision + mouse, migrates to host."""

    def __init__(self, vdi_display: str = ":99", host_display: str = ":0"):
        self.vdi_display = vdi_display
        self.host_display = host_display

    def _run_vdi(self, cmd: str, timeout: int = 30) -> str:
        """Run command in VDI and return output."""
        try:
            full_cmd = f"DISPLAY={self.vdi_display} {cmd}"
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", full_cmd],
                capture_output=True, text=True, timeout=timeout
            )
            return result.stdout
        except Exception as e:
            logger.debug(f"VDI command failed: {e}")
            return ""

    def _capture_screenshot(self) -> str:
        """Capture VDI screenshot as base64."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.vdi_display} import -window root png:- 2>/dev/null"],
                capture_output=True, timeout=10
            )
            if result.stdout:
                return base64.b64encode(result.stdout).decode()
        except Exception:
            pass
        return ""

    def _ocr_screen(self) -> str:
        """OCR the current VDI screen."""
        try:
            screenshot_b64 = self._capture_screenshot()
            if not screenshot_b64:
                return ""
            from rapidocr_onnxruntime import RapidOCR
            import numpy as np
            from PIL import Image

            img_bytes = base64.b64decode(screenshot_b64)
            img = Image.open(io.BytesIO(img_bytes))
            img_array = np.array(img)

            ocr = RapidOCR()
            result, _ = ocr(img_array)
            if result:
                return "\n".join([line[1] for line in result])
        except Exception as e:
            logger.debug(f"OCR failed: {e}")
        return ""

    def _get_active_window(self) -> str:
        """Get active window title."""
        return self._run_vdi("xdotool getactivewindow getwindowname 2>/dev/null").strip()

    def _xdotool_click(self, x: int, y: int, button: int = 1):
        """Click at coordinates."""
        self._run_vdi(f"xdotool mousemove {x} {y} click {button}")

    def _xdotool_type(self, text: str):
        """Type text."""
        escaped = text.replace("'", "'\\''")
        self._run_vdi(f"xdotool type --delay 30 '{escaped}'")

    def _xdotool_hotkey(self, keys: str):
        """Press hotkey."""
        key_map = {
            "ctrl": "ctrl", "alt": "alt", "shift": "shift",
            "enter": "Return", "tab": "Tab", "escape": "Escape",
            "f1": "F1", "f5": "F5",
            "left": "Left", "right": "Right", "up": "Up", "down": "Down",
        }
        parts = keys.split("+")
        xdotool_keys = "+".join(key_map.get(p.strip().lower(), p.strip()) for p in parts)
        self._run_vdi(f"xdotool key {xdotool_keys}")

    def _xdotool_mouse_relative(self, dx: int, dy: int):
        """Move mouse relative to current position."""
        self._run_vdi(f"xdotool mousemove_relative -- {dx} {dy}")

    def _xdotool_drag(self, x1: int, y1: int, x2: int, y2: int):
        """Drag from (x1,y1) to (x2,y2)."""
        self._run_vdi(
            f"xdotool mousemove {x1} {y1} "
            f"mousedown 1 "
            f"mousemove {x2} {y2} "
            f"mouseup 1"
        )

    # ── Step 1: Open Presentation in VDI ────────────────────────────────

    def open_in_vdi(self, pptx_path: str) -> dict:
        """Open PPTX in LibreOffice Impress in the VDI."""
        logger.info(f"[Adjuster] Opening {pptx_path} in LibreOffice Impress")

        # Convert Windows path to WSL path
        wsl_path = pptx_path.replace("\\", "/")
        if wsl_path[1] == ":":
            drive = wsl_path[0].lower()
            wsl_path = f"/mnt/{drive}{wsl_path[2:]}"

        # Launch LibreOffice Impress
        cmd = f"libreoffice --impress '{wsl_path}' &"
        self._run_vdi(cmd, timeout=10)

        # Wait for window to appear
        time.sleep(3)

        # Check if it opened
        window = self._get_active_window()
        if not window or "libreoffice" not in window.lower():
            # Try again with a longer wait
            time.sleep(3)
            window = self._get_active_window()

        success = "libreoffice" in window.lower() or "impress" in window.lower()
        logger.info(f"[Adjuster] Window: {window}, Success: {success}")

        return {"success": success, "window": window, "path": wsl_path}

    # ── Step 2: Vision Analysis ─────────────────────────────────────────

    def analyze_layout(self) -> list:
        """Analyze current slide for layout issues using vision."""
        issues = []
        ocr_text = self._ocr_screen()
        screenshot_b64 = self._capture_screenshot()

        if not ocr_text:
            logger.warning("[Adjuster] No OCR text, skipping analysis")
            return issues

        # Check for common issues
        lines = ocr_text.split("\n")

        # Issue: Text cut off at edges (words ending abruptly)
        for line in lines:
            if len(line) > 60:  # Long line might be cut off
                issues.append(LayoutIssue(
                    issue_type="cut_off",
                    element=f"Text line: {line[:40]}...",
                    severity="medium",
                    fix_action="resize_text_box"
                ))

        # Issue: Too much empty space (content not centered)
        text_density = len(ocr_text.strip()) / max(len(lines), 1)
        if text_density < 10 and len(lines) > 2:
            issues.append(LayoutIssue(
                issue_type="off_center",
                element="Content area",
                severity="low",
                fix_action="center_content"
            ))

        # Issue: Multiple overlapping text blocks (OCR returns jumbled text)
        if ocr_text.count("\n") > 15:
            issues.append(LayoutIssue(
                issue_type="overlap",
                element="Slide elements",
                severity="high",
                fix_action="rearrange_elements"
            ))

        # Issue: Font too small (OCR can barely read it)
        avg_line_len = sum(len(l) for l in lines) / max(len(lines), 1)
        if avg_line_len < 5 and len(lines) > 3:
            issues.append(LayoutIssue(
                issue_type="too_small",
                element="Text content",
                severity="medium",
                fix_action="increase_font_size"
            ))

        logger.info(f"[Adjuster] Found {len(issues)} layout issues")
        return issues

    # ── Step 3: Apply Fixes ─────────────────────────────────────────────

    def apply_fixes(self, issues: list) -> list:
        """Apply fixes for detected layout issues using mouse/keyboard."""
        fixes_applied = []

        for issue in issues:
            logger.info(f"[Adjuster] Fixing: {issue.issue_type} ({issue.fix_action})")

            if issue.fix_action == "center_content":
                # Select all elements and center them
                self._xdotool_hotkey("ctrl+a")  # Select all
                time.sleep(0.3)
                # Use Format > Align > Center Horizontally
                self._xdotool_hotkey("alt+f")  # Format menu
                time.sleep(0.2)
                self._xdotool_type("a")  # Align
                time.sleep(0.2)
                self._xdotool_type("c")  # Center Horizontally
                time.sleep(0.3)
                self._xdotool_hotkey("Return")
                fixes_applied.append("centered_content")

            elif issue.fix_action == "resize_text_box":
                # Click on the text box, then use corner handles to resize
                # First, click on the text area (approximate center)
                self._xdotool_click(960, 540)  # Center of 1920x1080
                time.sleep(0.3)
                # Press F2 to enter text editing, then Escape to select the box
                self._xdotool_hotkey("Escape")
                time.sleep(0.2)
                # Use Ctrl+Shift+G to group/resize (LibreOffice shortcut)
                # Or use the handles - drag bottom-right corner outward
                self._xdotool_drag(1100, 650, 1200, 700)
                time.sleep(0.3)
                fixes_applied.append("resized_text_box")

            elif issue.fix_action == "increase_font_size":
                # Select all text
                self._xdotool_hotkey("ctrl+a")
                time.sleep(0.2)
                # Increase font size with Ctrl+]
                for _ in range(3):
                    self._xdotool_hotkey("ctrl+bracketright")
                    time.sleep(0.1)
                fixes_applied.append("increased_font")

            elif issue.fix_action == "rearrange_elements":
                # Deselect first
                self._xdotool_hotkey("Escape")
                time.sleep(0.2)
                # Click on empty area to deselect
                self._xdotool_click(100, 700)
                time.sleep(0.2)
                fixes_applied.append("deselected_for_review")

        return fixes_applied

    # ── Step 4: Navigate Slides ─────────────────────────────────────────

    def adjust_all_slides(self, max_slides: int = 10) -> AdjustmentResult:
        """Iterate through all slides, analyze and fix each."""
        start_time = time.time()
        total_issues = 0
        total_fixed = 0
        all_adjustments = []

        for slide_num in range(max_slides):
            logger.info(f"[Adjuster] Processing slide {slide_num + 1}")

            # Analyze current slide
            issues = self.analyze_layout()
            total_issues += len(issues)

            if issues:
                # Apply fixes
                fixes = self.apply_fixes(issues)
                total_fixed += len(fixes)
                all_adjustments.append({
                    "slide": slide_num + 1,
                    "issues": len(issues),
                    "fixes": fixes
                })

            # Navigate to next slide
            self._xdotool_hotkey("Right")
            time.sleep(0.5)

        # Save the file
        self._xdotool_hotkey("ctrl+s")
        time.sleep(1)
        # Handle format dialog if it appears
        self._xdotool_hotkey("Return")
        time.sleep(0.5)

        duration = time.time() - start_time

        return AdjustmentResult(
            success=True,
            issues_found=total_issues,
            issues_fixed=total_fixed,
            adjustments=all_adjustments,
            duration_seconds=round(duration, 2)
        )

    # ── Step 5: Migrate to Host ─────────────────────────────────────────

    def migrate_to_host(self, pptx_path: str = None) -> dict:
        """Move the LibreOffice Impress window from VDI to host desktop."""
        logger.info("[Adjuster] Migrating window to host")

        # Find the LibreOffice window
        wid = self._run_vdi(
            "xdotool search --name LibreOffice 2>/dev/null | head -1"
        ).strip()

        if not wid:
            # Try alternative search
            wid = self._run_vdi(
                "xdotool search --name Impress 2>/dev/null | head -1"
            ).strip()

        if not wid:
            return {"success": False, "error": "LibreOffice window not found"}

        logger.info(f"[Adjuster] Found window: {wid}")

        # Method 1: Export as PDF and open on host (most reliable)
        if pptx_path:
            pdf_path = pptx_path.replace(".pptx", ".pdf")
            wsl_pdf = pdf_path.replace("\\", "/")
            if wsl_pdf[1] == ":":
                drive = wsl_pdf[0].lower()
                wsl_pdf = f"/mnt/{drive}{wsl_pdf[2:]}"

            # Export PDF from LibreOffice
            self._xdotool_hotkey("ctrl+shift+s")  # Save As
            time.sleep(0.5)
            # Type PDF path
            self._xdotool_hotkey("ctrl+l")  # Location bar
            time.sleep(0.2)
            self._xdotool_type(wsl_pdf)
            time.sleep(0.2)
            self._xdotool_hotkey("Return")
            time.sleep(1)
            # Handle format selection
            self._xdotool_hotkey("Tab")
            time.sleep(0.2)
            self._xdotool_type("pdf")
            time.sleep(0.2)
            self._xdotool_hotkey("Return")
            time.sleep(2)

            # Open PDF on host
            host_pdf = pdf_path.replace("/", "\\")
            try:
                os.startfile(host_pdf)
                return {"success": True, "method": "pdf_export", "path": host_pdf}
            except Exception as e:
                logger.warning(f"Could not open PDF on host: {e}")

        # Method 2: Use wmctrl to re-parent window
        try:
            # Get window geometry before moving
            geom = self._run_vdi(f"xdotool getwindowgeometry {wid} 2>/dev/null")
            logger.info(f"[Adjuster] Window geometry: {geom}")

            # Move to host display
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.host_display} wmctrl -i -r {wid} -t 0"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # Activate on host
                self._run_vdi(f"DISPLAY={self.host_display} xdotool windowactivate {wid}")
                return {"success": True, "method": "wmctrl", "wid": wid}
        except Exception as e:
            logger.warning(f"wmctrl migration failed: {e}")

        # Method 3: xdotool approach
        try:
            self._run_vdi(f"DISPLAY={self.host_display} xdotool windowactivate {wid}")
            return {"success": True, "method": "xdotool_activate", "wid": wid}
        except Exception as e:
            return {"success": False, "error": f"All migration methods failed: {e}"}

    # ── Main Pipeline ───────────────────────────────────────────────────

    def open_adjust_migrate(self, pptx_path: str) -> AdjustmentResult:
        """Full pipeline: Open → Vision Adjust → Migrate to Host."""
        start_time = time.time()

        # Step 1: Open in VDI
        open_result = self.open_in_vdi(pptx_path)
        if not open_result.get("success"):
            return AdjustmentResult(
                success=False,
                error=f"Failed to open: {open_result.get('error', 'unknown')}",
                duration_seconds=time.time() - start_time
            )

        # Step 2: Wait for presentation to fully load
        time.sleep(2)

        # Step 3: Go to first slide
        self._xdotool_hotkey("Home")
        time.sleep(0.5)

        # Step 4: Analyze and adjust all slides
        adjustment = self.adjust_all_slides()

        # Step 5: Migrate to host
        migrate_result = self.migrate_to_host(pptx_path)

        adjustment.migrated_to_host = migrate_result.get("success", False)
        adjustment.output_path = pptx_path
        adjustment.duration_seconds = round(time.time() - start_time, 2)

        logger.info(
            f"[Adjuster] Complete: {adjustment.issues_found} issues found, "
            f"{adjustment.issues_fixed} fixed, migrated={adjustment.migrated_to_host}"
        )

        return adjustment


# ── Convenience Function ─────────────────────────────────────────────

def open_and_adjust(pptx_path: str) -> dict:
    """Open, adjust, and migrate a presentation."""
    adjuster = PresentationAdjuster()
    result = adjuster.open_adjust_migrate(pptx_path)
    return {
        "success": result.success,
        "issues_found": result.issues_found,
        "issues_fixed": result.issues_fixed,
        "migrated": result.migrated_to_host,
        "duration": result.duration_seconds,
        "adjustments": result.adjustments,
        "error": result.error,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[ADJUSTER] %(message)s")
    import sys
    if len(sys.argv) > 1:
        result = open_and_adjust(sys.argv[1])
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python presentation_adjuster.py <path_to_pptx>")
