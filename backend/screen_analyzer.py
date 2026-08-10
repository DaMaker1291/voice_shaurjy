"""Screen Analyzer — sees and understands everything on screen using OCR + CV.

Capabilities:
  - OCR all text on screen with bounding boxes → "see" what's displayed
  - Find UI elements (buttons, text fields, labels) → "understand" the interface
  - Detect clickable regions → "interact" with anything
  - Read form fields and their labels → "fill in" forms
  - Find and click buttons by label text → "press" any button
  - Analyze screen structure (sections, panels) → "navigate" complex UIs
"""
import io
import re
import json
import os
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
    # Auto-detect Tesseract binary: env override → common install paths → PATH
    import shutil
    _env_tess = os.environ.get("TESSERACT_CMD", "").strip()
    if _env_tess and os.path.isfile(_env_tess):
        pytesseract.pytesseract.tesseract_cmd = _env_tess
        logger.info(f"[ScreenAnalyzer] Tesseract from env: {_env_tess}")
    elif not shutil.which("tesseract"):
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for p in common_paths:
            from pathlib import Path as _Path
            if _Path(p).exists():
                pytesseract.pytesseract.tesseract_cmd = p
                logger.info(f"[ScreenAnalyzer] Auto-detected Tesseract at {p}")
                break
except ImportError:
    HAS_TESSERACT = False
    logger.warning("[ScreenAnalyzer] pytesseract/PIL not installed — OCR disabled")


@dataclass
class ScreenElement:
    """A detected element on screen with position and text."""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0
    element_type: str = "text"  # text, button, text_field, label, checkbox, radio, image, icon
    center_x: int = 0
    center_y: int = 0

    def __post_init__(self):
        self.center_x = self.x + self.width // 2
        self.center_y = self.y + self.height // 2

    def contains(self, x: int, y: int) -> bool:
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "center_x": self.center_x, "center_y": self.center_y,
            "confidence": self.confidence,
            "type": self.element_type,
        }


@dataclass
class ScreenAnalysis:
    """Complete analysis of a screen capture."""
    elements: List[ScreenElement] = field(default_factory=list)
    text: str = ""
    width: int = 0
    height: int = 0
    form_fields: List[ScreenElement] = field(default_factory=list)
    buttons: List[ScreenElement] = field(default_factory=list)
    labels: List[ScreenElement] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text[:2000],
            "width": self.width, "height": self.height,
            "elements": [e.to_dict() for e in self.elements],
            "buttons": [e.to_dict() for e in self.buttons],
            "form_fields": [e.to_dict() for e in self.form_fields],
            "labels": [e.to_dict() for e in self.labels],
            "element_count": len(self.elements),
            "timestamp": self.timestamp,
        }


class ScreenAnalyzer:
    """Analyzes screen captures to find and understand UI elements."""

    def __init__(self, tesseract_cmd: str = ""):
        self._tesseract_cmd = tesseract_cmd
        if tesseract_cmd and HAS_TESSERACT:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        # Button-like text patterns — match individual words within text
        self._button_keywords = re.compile(
            r'\b(OK|Cancel|Save|Delete|Submit|Close|Exit|Yes|No|'
            r'Apply|Reset|Next|Back|Finish|Install|Browse|'
            r'Search|Find|Open|Create|Edit|Copy|Paste|Cut|'
            r'Print|Preview|Download|Upload|Send|Reply|Forward|'
            r'Enable|Disable|Start|Stop|Pause|Resume|Retry|'
            r'Add|Remove|Clear|Refresh|Update|Upgrade|'
            r'Continue|Proceed|Confirm|Accept|Reject|'
            r'Sign in|Sign out|Log in|Log out|Register|Subscribe|'
            r'Buy|Purchase|Checkout|Pay|Donate|'
            r'Allow|Deny|Grant|Block|'
            r'Connect|Disconnect|Join|Leave|'
            r'Yes|No|I agree|I disagree|'
            r'[A-Z\s]{2,})\b', re.IGNORECASE
        )
        # Text-field-like patterns (labels near blank areas or input-like text)
        self._field_indicators = re.compile(
            r'(.*(?:name|user|pass|email|phone|address|search|'
            r'enter|input|type|field|box|fill|write|'
            r'https?://|@|\.com|\.org|\.net))$', re.IGNORECASE
        )

    def analyze_screenshot(self, image: Image.Image) -> ScreenAnalysis:
        """Full screen analysis: OCR + element detection + form detection."""
        analysis = ScreenAnalysis(
            width=image.width,
            height=image.height,
            timestamp=time.time()
        )

        if not HAS_TESSERACT:
            analysis.text = "(OCR not available — install pytesseract + Tesseract)"
            return analysis

        try:
            # Phase 1: OCR — get all text with positions
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            elements = self._parse_ocr_data(ocr_data)
            analysis.elements = elements
            analysis.text = " ".join(e.text for e in elements if e.text.strip())

            # Phase 2: Classify elements
            for el in elements:
                text = el.text.strip()
                if not text:
                    continue
                # Detect buttons (short, uppercase/action-oriented text, centered in a box)
                if (self._is_button_text(text) and
                    el.width < 300 and el.height < 80):
                    el.element_type = "button"
                    analysis.buttons.append(el)
                # Detect text field labels
                elif self._is_field_label(text, el, elements):
                    el.element_type = "label"
                    analysis.labels.append(el)
                    # Find the field area near this label
                    field = self._find_field_near_label(el, elements, image)
                    if field:
                        analysis.form_fields.append(field)

            # Phase 3: Find additional form fields (input-like areas)
            self._find_input_fields(analysis, image)

            logger.info(f"[ScreenAnalyzer] Found {len(analysis.elements)} elements, "
                       f"{len(analysis.buttons)} buttons, {len(analysis.form_fields)} fields")
            return analysis

        except Exception as e:
            logger.error(f"[ScreenAnalyzer] Analysis failed: {e}")
            analysis.text = f"(Analysis error: {e})"
            return analysis

    def analyze_file(self, image_path: str) -> ScreenAnalysis:
        """Analyze a screenshot file."""
        try:
            img = Image.open(image_path)
            return self.analyze_screenshot(img)
        except Exception as e:
            logger.error(f"[ScreenAnalyzer] File analysis failed: {e}")
            return ScreenAnalysis(text=f"(Error: {e})")

    def find_text(self, analysis: ScreenAnalysis, text: str, partial: bool = True) -> List[ScreenElement]:
        """Find all elements containing the given text."""
        text_lower = text.lower()
        results = []
        for el in analysis.elements:
            el_text = el.text.lower()
            if (partial and text_lower in el_text) or (el_text == text_lower):
                results.append(el)
        return results

    def find_button(self, analysis: ScreenAnalysis, label: str) -> Optional[ScreenElement]:
        """Find a button by its label text."""
        label_lower = label.lower()
        for btn in analysis.buttons:
            if label_lower == btn.text.lower() or label_lower in btn.text.lower():
                return btn
        # Fallback: search all elements
        for el in analysis.elements:
            if label_lower in el.text.lower():
                if el.element_type == "button" or (el.width < 300 and el.height < 80):
                    return el
        return None

    def find_text_field(self, analysis: ScreenAnalysis, label: str = "") -> Optional[ScreenElement]:
        """Find a text input field, optionally by its label."""
        if label and analysis.labels:
            label_lower = label.lower()
            for lbl in analysis.labels:
                if label_lower in lbl.text.lower() or label == lbl.text:
                    near = self._find_field_near_label(lbl, analysis.elements, None)
                    if near:
                        return near
        if analysis.form_fields:
            return analysis.form_fields[0]
        return None

    def get_element_at(self, analysis: ScreenAnalysis, x: int, y: int) -> Optional[ScreenElement]:
        """Get the topmost element at screen coordinates."""
        for el in reversed(analysis.elements):
            if el.contains(x, y):
                return el
        return None

    def get_clickable_regions(self, analysis: ScreenAnalysis) -> List[ScreenElement]:
        """Get all clickable regions (buttons + any element > 30px)."""
        clickable = list(analysis.buttons)
        for el in analysis.elements:
            if el.text.strip() and el not in clickable:
                if el.width > 30 and el.height > 20 and el.width < 500:
                    clickable.append(el)
        return clickable

    def _parse_ocr_data(self, ocr_data: dict) -> List[ScreenElement]:
        """Parse pytesseract OCR output into ScreenElements."""
        elements = []
        n = len(ocr_data.get("text", []))
        # Group by block/paragraph for coarser elements
        blocks = defaultdict(list)
        for i in range(n):
            text = ocr_data["text"][i] if ocr_data["text"][i] else ""
            conf = int(ocr_data["conf"][i]) if ocr_data["conf"][i] != '-1' else 0
            block_num = ocr_data["block_num"][i]
            if text.strip() and conf > 10:
                blocks[block_num].append({
                    "text": text.strip(),
                    "x": ocr_data["left"][i],
                    "y": ocr_data["top"][i],
                    "w": ocr_data["width"][i],
                    "h": ocr_data["height"][i],
                    "conf": conf,
                })

        for block_id, items in blocks.items():
            if not items:
                continue
            # Merge horizontally aligned items into lines
            lines = self._merge_into_lines(items)
            for line in lines:
                first = line[0]
                last = line[-1]
                x = first["x"]
                y = first["y"]
                w = (last["x"] + last["w"]) - x
                h = max(it["h"] for it in line)
                text = " ".join(it["text"] for it in line)
                avg_conf = sum(it["conf"] for it in line) / len(line)
                elements.append(ScreenElement(
                    text=text, x=x, y=y, width=w, height=h,
                    confidence=avg_conf / 100.0
                ))
        return elements

    def _merge_into_lines(self, items: List[dict]) -> List[List[dict]]:
        """Merge OCR items into lines based on y-position proximity."""
        if not items:
            return []
        sorted_items = sorted(items, key=lambda it: (it["y"], it["x"]))
        lines = []
        current_line = [sorted_items[0]]
        for item in sorted_items[1:]:
            prev = current_line[-1]
            # Same line if y within ~half the line height
            mid_prev = prev["y"] + prev["h"] // 2
            mid_cur = item["y"] + item["h"] // 2
            if abs(mid_cur - mid_prev) < max(prev["h"], item["h"]) * 0.6:
                current_line.append(item)
            else:
                lines.append(current_line)
                current_line = [item]
        if current_line:
            lines.append(current_line)
        return lines

    def _is_button_text(self, text: str) -> bool:
        """Heuristic: is this text likely a button label?"""
        if self._button_keywords.search(text):
            return True
        # Buttons are usually short (1-3 words), may be all caps
        words = text.split()
        if 1 <= len(words) <= 4 and len(text) < 40:
            if text.isupper() or text[0].isupper():
                return True
        return False

    def _is_field_label(self, text: str, element: ScreenElement,
                        all_elements: List[ScreenElement]) -> bool:
        """Heuristic: is this element a label for an input field?"""
        text_lower = text.lower().rstrip(": ")
        # Field indicator patterns
        field_keywords = ["name", "user", "email", "phone", "address",
                          "password", "search", "enter", "input",
                          "first", "last", "city", "state", "zip",
                          "code", "country", "title", "description",
                          "comment", "message", "subject", "from", "to"]
        for kw in field_keywords:
            if kw in text_lower:
                return True
        # Ends with colon (common for form labels)
        if text.endswith(":") or text.endswith(":"):
            return True
        # Short text (under 30 chars) near a blank area to the right
        if len(text) < 30:
            right_of = [e for e in all_elements if
                       e.y < element.y + element.height and
                       e.y + e.height > element.y and
                       e.x > element.x + element.width and
                       e.x < element.x + element.width + 300]
            if not right_of:
                return True
        return False

    def _find_field_near_label(self, label: ScreenElement,
                                all_elements: List[ScreenElement],
                                image: Optional[Image.Image]) -> Optional[ScreenElement]:
        """Given a label element, find the adjacent input field."""
        # Look to the right or below for a blank rectangular area
        field_x = label.x + label.width + 5
        field_y = label.y
        field_w = 200
        field_h = label.height + 10

        # Check if there's an existing element in that area
        for el in all_elements:
            if el is label:
                continue
            if (abs(el.x - field_x) < 50 and abs(el.y - field_y) < 20):
                if el.width < 400 and el.height < 60:
                    el.element_type = "text_field"
                    return el

        # Create synthetic field area
        return ScreenElement(
            text="",
            x=field_x, y=field_y,
            width=field_w, height=field_h,
            confidence=0.5,
            element_type="text_field"
        )

    def _find_input_fields(self, analysis: ScreenAnalysis, image: Optional[Image.Image]):
        """Find input-style UI elements (text boxes, dropdowns, etc.)."""
        if not image:
            return
        # Look for rectangular regions that are lighter/white (common for input fields)
        try:
            import cv2
            import numpy as np
            img_np = np.array(image.convert("RGB"))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            # Threshold to find bright rectangular regions
            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if 50 < w < 600 and 15 < h < 60:
                    # Check if this overlaps with existing elements
                    is_new = True
                    for el in analysis.elements:
                        if abs(el.x - x) < 20 and abs(el.y - y) < 10:
                            is_new = False
                            break
                    if is_new:
                        field = ScreenElement(
                            text="", x=x, y=y, width=w, height=h,
                            confidence=0.4, element_type="text_field"
                        )
                        analysis.form_fields.append(field)
                        analysis.elements.append(field)
        except ImportError:
            pass  # cv2 not available


# ── Global singleton ────────────────────────────────────────────────
_analyzer: Optional[ScreenAnalyzer] = None


def get_analyzer(tesseract_cmd: str = "") -> ScreenAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = ScreenAnalyzer(tesseract_cmd)
    return _analyzer


def analyze(image: Image.Image) -> ScreenAnalysis:
    """Quick one-shot screen analysis."""
    return get_analyzer().analyze_screenshot(image)
