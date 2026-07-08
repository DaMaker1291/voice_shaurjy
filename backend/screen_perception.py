#!/usr/bin/env python3
"""
Screen Perception for JARVIS
Takes screenshots, runs OCR to find all text + positions on screen.
Enables "seeing" the desktop to complete real tasks.
"""
import subprocess
import json
import time
import os
import base64
import re
from typing import Dict, Any, List, Tuple, Optional

class ScreenPerception:
    """
    See the screen:
    - Take screenshots (full or region)
    - OCR to extract all text with positions
    - Find UI elements (buttons, fields, menus)
    - Understand what's on screen
    """

    def __init__(self):
        self._last_screenshot = None
        self._last_elements = []
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Check if tesseract OCR is installed."""
        try:
            result = subprocess.run(["which", "tesseract"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def install_tesseract(self) -> dict:
        """Install tesseract via Homebrew."""
        try:
            subprocess.run(["brew", "install", "tesseract"], capture_output=True, timeout=120)
            self._tesseract_available = True
            return {"status": "installed"}
        except Exception as e:
            return {"error": str(e)}

    # ── Screenshot ────────────────────────────────────────────────────

    def screenshot_full(self, path: str = None) -> dict:
        """Take a full screenshot."""
        if path is None:
            path = f"/tmp/jarvis_screen_{int(time.time())}.png"
        try:
            subprocess.run(["screencapture", "-x", path], timeout=10)
            self._last_screenshot = path
            size = os.path.getsize(path) if os.path.exists(path) else 0
            return {"status": "ok", "path": path, "size": size}
        except Exception as e:
            return {"error": str(e)}

    def screenshot_region(self, x: int, y: int, w: int, h: int, path: str = None) -> dict:
        """Take a screenshot of a specific region."""
        if path is None:
            path = f"/tmp/jarvis_region_{int(time.time())}.png"
        try:
            subprocess.run(["screencapture", "-R", f"{x},{y},{w},{h}", path], timeout=10)
            self._last_screenshot = path
            return {"status": "ok", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def screenshot_window(self, path: str = None) -> dict:
        """Take a screenshot of the frontmost window."""
        if path is None:
            path = f"/tmp/jarvis_window_{int(time.time())}.png"
        try:
            subprocess.run(["screencapture", "-x", "-l", "$(osascript -e 'tell app \"System Events\" to get id of first application process whose frontmost is true')", path], timeout=10)
            self._last_screenshot = path
            return {"status": "ok", "path": path}
        except:
            # Fallback to full screenshot
            return self.screenshot_full(path)

    # ── OCR ───────────────────────────────────────────────────────────

    def ocr_screen(self, path: str = None) -> dict:
        """Run OCR on a screenshot to extract all text with positions."""
        if path is None:
            path = self._last_screenshot
        if not path or not os.path.exists(path):
            return {"error": "No screenshot available"}

        if not self._tesseract_available:
            return self._ocr_fallback(path)

        try:
            # Copy to local dir for tesseract (handles /tmp path issues)
            local_path = f"/tmp/jarvis_ocr_{os.getpid()}.png"
            import shutil
            shutil.copy2(path, local_path)

            # Tesseract with TSV output (gives text + positions)
            result = subprocess.run(
                ["tesseract", local_path, "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
                capture_output=True, text=True, timeout=30,
                cwd="/tmp"
            )

            elements = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 12:
                    try:
                        conf = float(parts[10])
                        if conf < 30:  # Skip low confidence
                            continue
                        text = parts[11].strip()
                        if not text or len(text) < 2:
                            continue
                        elements.append({
                            "text": text,
                            "x": int(parts[6]),
                            "y": int(parts[7]),
                            "w": int(parts[8]),
                            "h": int(parts[9]),
                            "confidence": conf,
                            "center_x": int(parts[6]) + int(parts[8]) // 2,
                            "center_y": int(parts[7]) + int(parts[9]) // 2,
                        })
                    except (ValueError, IndexError):
                        continue

            self._last_elements = elements
            return {
                "status": "ok",
                "elements": elements,
                "count": len(elements),
                "screenshot": path,
            }
        except Exception as e:
            return {"error": str(e)}

    def _ocr_fallback(self, path: str) -> dict:
        """Fallback OCR using macOS Vision framework or pure screenshot."""
        # Just return the screenshot for now - vision framework integration
        return {
            "status": "screenshot_only",
            "screenshot": path,
            "message": "Install tesseract for OCR: brew install tesseract",
            "elements": [],
        }

    # ── Element Finding ───────────────────────────────────────────────

    def find_element(self, text: str, screenshot: str = None) -> Optional[dict]:
        """Find a UI element by text on screen."""
        if not self._last_elements or screenshot:
            self.ocr_screen(screenshot)

        text_lower = text.lower()
        for elem in self._last_elements:
            if text_lower in elem["text"].lower():
                return elem
        return None

    def find_all(self, text: str, screenshot: str = None) -> List[dict]:
        """Find all UI elements matching text."""
        if not self._last_elements or screenshot:
            self.ocr_screen(screenshot)

        text_lower = text.lower()
        return [e for e in self._last_elements if text_lower in e["text"].lower()]

    def find_button(self, text: str, screenshot: str = None) -> Optional[dict]:
        """Find a button by its label text."""
        return self.find_element(text, screenshot)

    def find_field(self, hint: str = "", screenshot: str = None) -> Optional[dict]:
        """Find a text input field (usually near a label)."""
        if not self._last_elements or screenshot:
            self.ocr_screen(screenshot)

        # Look for labels that might be near input fields
        # Input fields are usually below/right of their labels
        hint_lower = hint.lower() if hint else ""

        candidates = []
        for elem in self._last_elements:
            if hint_lower and hint_lower in elem["text"].lower():
                # This might be a label - look for elements below/right
                candidates.append(elem)

        if candidates:
            # Return the label position (click below it for the field)
            label = candidates[0]
            return {
                "text": label["text"],
                "x": label["center_x"],
                "y": label["center_y"] + label["h"],
                "is_label": True,
                "click_y_offset": label["h"],
            }

        return None

    def find_menu_item(self, text: str, screenshot: str = None) -> Optional[dict]:
        """Find a menu item by text."""
        return self.find_element(text, screenshot)

    def find_tab(self, text: str, screenshot: str = None) -> Optional[dict]:
        """Find a tab by its label."""
        return self.find_element(text, screenshot)

    def find_checkbox(self, text: str, screenshot: str = None) -> Optional[dict]:
        """Find a checkbox by its label."""
        return self.find_element(text, screenshot)

    # ── Screen Understanding ──────────────────────────────────────────

    def understand_screen(self, screenshot: str = None) -> dict:
        """Understand what's currently on screen."""
        ocr_result = self.ocr_screen(screenshot)
        elements = ocr_result.get("elements", [])

        if not elements:
            return {"status": "no_text", "screenshot": screenshot or self._last_screenshot}

        # Categorize elements
        buttons = []
        labels = []
        inputs = []
        menus = []
        other = []

        button_keywords = ["button", "submit", "send", "save", "cancel", "ok", "yes", "no", "close", "done", "next", "back"]
        input_keywords = ["search", "enter", "type", "input", "field", "password", "email", "name"]
        menu_keywords = ["file", "edit", "view", "window", "help", "menu"]

        for elem in elements:
            text = elem["text"].lower()
            if any(k in text for k in button_keywords):
                buttons.append(elem)
            elif any(k in text for k in input_keywords):
                inputs.append(elem)
            elif any(k in text for k in menu_keywords):
                menus.append(elem)
            elif len(elem["text"]) < 50:
                labels.append(elem)
            else:
                other.append(elem)

        return {
            "status": "ok",
            "screenshot": ocr_result.get("screenshot"),
            "total_elements": len(elements),
            "buttons": buttons[:10],
            "labels": labels[:20],
            "inputs": inputs[:10],
            "menus": menus[:5],
            "all_elements": elements[:30],
        }

    def describe_screen(self, screenshot: str = None) -> str:
        """Get a natural language description of what's on screen."""
        info = self.understand_screen(screenshot)
        if info["status"] == "no_text":
            return "Screen appears empty or contains no readable text."

        lines = []
        lines.append(f"Screen has {info['total_elements']} text elements.")

        if info["buttons"]:
            lines.append(f"Buttons: {', '.join(b['text'] for b in info['buttons'][:5])}")
        if info["inputs"]:
            lines.append(f"Input fields: {', '.join(i['text'] for i in info['inputs'][:5])}")
        if info["labels"]:
            lines.append(f"Labels: {', '.join(l['text'] for l in info['labels'][:8])}")

        return " ".join(lines)

    # ── Utilities ─────────────────────────────────────────────────────

    def get_screen_size(self) -> dict:
        """Get screen dimensions."""
        try:
            import Quartz
            main_display = Quartz.CGMainDisplayBounds()
            return {"width": int(main_display.size.width), "height": int(main_display.size.height)}
        except:
            return {"error": "Could not get screen size"}

    def wait_and_screenshot(self, wait: float = 1.0) -> dict:
        """Wait then take screenshot."""
        time.sleep(wait)
        return self.screenshot_full()


# Singleton
_perception = None

def get_perception() -> ScreenPerception:
    global _perception
    if _perception is None:
        _perception = ScreenPerception()
    return _perception
