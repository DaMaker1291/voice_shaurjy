"""
Vision Controller — AI sees the screen and controls ANY app.

Works with ANY application — games, custom UIs, web apps — anything visible on screen.
Uses EasyOCR for text detection + Cloudflare text model for understanding.
No accessibility API needed. Just a screenshot + AI.
"""

import base64
import io
import json
import logging
import os
import re
import time
import subprocess
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

log = logging.getLogger("jarvis-vision")

# Cloudflare credentials
CF_ACCOUNT = os.getenv("CF_ACCOUNT_ID", "")
CF_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_TEXT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

# EasyOCR reader (lazy loaded)
_ocr_reader = None
_ocr_loading = False

def _get_ocr():
    global _ocr_reader, _ocr_loading
    if _ocr_reader is not None:
        return _ocr_reader
    if _ocr_loading:
        return None
    _ocr_loading = True
    try:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    except Exception as e:
        log.warning("EasyOCR init failed: " + str(e))
        _ocr_loading = False
    return _ocr_reader

try:
    import mss
    import mss.tools
    _HAS_MSS = True
except ImportError:
    _HAS_MSS = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


@dataclass
class ScreenAction:
    """An action to perform on screen."""
    action_type: str  # click, type, press, scroll, drag, done, fail
    x: int = 0
    y: int = 0
    text: str = ""
    key: str = ""
    button: str = "left"
    dx: int = 0
    dy: int = 0
    reason: str = ""
    confidence: float = 0.0

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v}


class VisionController:
    """
    See the screen, understand it, control it.
    Works with ANY visible application.
    """

    def __init__(self):
        self._history: List[Dict] = []
        self._max_history = 20

    # ═══════════════════════════════════════════════════════════════
    # SCREEN CAPTURE
    # ═══════════════════════════════════════════════════════════════

    def screenshot(self, region=None) -> Optional[bytes]:
        """Take screenshot, return PNG bytes."""
        if not _HAS_MSS:
            return None
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]  # Primary monitor
                if region:
                    mon = {"left": region[0], "top": region[1],
                           "width": region[2], "height": region[3]}
                raw = sct.grab(mon)
                return mss.tools.to_png(raw.rgb, raw.size)
        except Exception as e:
            log.error(f"Screenshot failed: {e}")
            return None

    def screenshot_base64(self, region=None) -> Optional[str]:
        """Take screenshot, return base64 encoded JPEG."""
        img_bytes = self.screenshot(region)
        if not img_bytes:
            return None
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            if max(w, h) > 1280:
                ratio = 1280 / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return base64.b64encode(img_bytes).decode()

    # ═══════════════════════════════════════════════════════════════
    # OCR - Read text from screen
    # ═══════════════════════════════════════════════════════════════

    def ocr_screen(self, region=None) -> List[Dict]:
        """Read all text on screen with positions."""
        reader = _get_ocr()
        if not reader:
            return []

        img_bytes = self.screenshot(region)
        if not img_bytes:
            return []

        try:
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            if max(w, h) > 1280:
                ratio = 1280 / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            img_array = __import__("numpy").array(img)
        except Exception:
            return []

        try:
            results = reader.readtext(img_array)
            elements = []
            for (bbox, text, conf) in results:
                if conf < 0.3:
                    continue
                # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                x1 = min(p[0] for p in bbox)
                y1 = min(p[1] for p in bbox)
                x2 = max(p[0] for p in bbox)
                y2 = max(p[1] for p in bbox)
                elements.append({
                    "text": text,
                    "x": int(x1),
                    "y": int(y1),
                    "w": int(x2 - x1),
                    "h": int(y2 - y1),
                    "cx": int((x1 + x2) / 2),
                    "cy": int((y1 + y2) / 2),
                    "conf": float(conf),
                })
            return elements
        except Exception as e:
            log.debug(f"OCR failed: {e}")
            return []

    def find_text(self, target: str) -> Optional[Dict]:
        """Find specific text on screen, return its center coordinates."""
        elements = self.ocr_screen()
        target_lower = target.lower()
        for el in elements:
            if target_lower in el["text"].lower():
                return el
        return None

    # ═══════════════════════════════════════════════════════════════
    # VISION ANALYSIS
    # ═══════════════════════════════════════════════════════════════

    def analyze(self, task: str, screenshot_b64: str = None) -> Dict[str, Any]:
        """
        Analyze screen and decide what action to take.
        Uses OCR text + Cloudflare text model.
        """
        # Get OCR text with positions
        elements = self.ocr_screen()
        screen_text = "\n".join(el["text"] for el in elements)

        # Build context from history
        history_text = ""
        if self._history:
            recent = self._history[-5:]
            for h in recent:
                history_text += "  Step " + str(h.get("step", "?")) + ": " + str(h.get("action", "")) + " -> " + str(h.get("result", ""))[:60] + "\n"

        # Build element list for the model
        el_list = ""
        for i, el in enumerate(elements[:30]):
            el_list += "  [" + str(i) + "] \"" + el["text"] + "\" at (" + str(el["cx"]) + "," + str(el["cy"]) + ") size " + str(el["w"]) + "x" + str(el["h"]) + "\n"

        prompt = """You are a computer user looking at a screen. Based on the OCR text detected, decide the next action.

TASK: """ + task + """

SCREEN TEXT:
""" + screen_text[:2000] + """

DETECTED ELEMENTS (index, text, center_x, center_y, size):
""" + el_list + """
PREVIOUS STEPS:
""" + (history_text if history_text else "  (none)") + """

RULES:
1. Match elements to what the task needs
2. Return center coordinates of the target element
3. If task is done, return {"action": "done"}
4. If you can't find the right element, return {"action": "fail"}

Respond with ONLY valid JSON:
{"action": "click", "x": 500, "y": 300, "element": "text of element", "reason": "clicking the button"}
or: {"action": "type", "text": "hello", "reason": "typing in field"}
or: {"action": "press", "key": "enter", "reason": "pressing enter"}
or: {"action": "scroll", "dy": -3, "reason": "scrolling down"}
or: {"action": "done", "reason": "task completed"}
or: {"action": "fail", "reason": "cannot find element"}

JSON:"""

        result = self._call_llm(prompt)
        if result:
            self._history.append({
                "step": len(self._history) + 1,
                "action": result.get("action", "?"),
                "result": result.get("reason", ""),
            })
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        return result or {"action": "fail", "reason": "Analysis unavailable"}

    def _call_llm(self, prompt: str) -> Optional[Dict]:
        """Call Cloudflare text model."""
        if not CF_TOKEN:
            return None
        try:
            import urllib.request
            url = "https://api.cloudflare.com/client/v4/accounts/" + CF_ACCOUNT + "/ai/run/" + CF_TEXT_MODEL
            payload = json.dumps({
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.1,
            }).encode()

            req = urllib.request.Request(url, data=payload, headers={
                "Authorization": "Bearer " + CF_TOKEN,
                "Content-Type": "application/json",
            })

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                result = data.get("result", {})
                if isinstance(result, dict):
                    text = result.get("response", "")
                    if not text and "choices" in result:
                        choices = result.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            text = msg.get("content", "")
                else:
                    text = str(result)
                return self._parse_json(text)

        except Exception as e:
            log.debug("LLM call failed: " + str(e))
            return None

    def _parse_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from model response."""
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return None

    # ═══════════════════════════════════════════════════════════════
    # EXECUTE ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def execute(self, action: Dict[str, Any]) -> str:
        """Execute a screen action."""
        if not _HAS_PYAUTOGUI:
            return "pyautogui not available"

        act = action.get("action", "")

        if act == "click":
            x, y = action.get("x", 0), action.get("y", 0)
            button = action.get("button", "left")
            if x > 0 and y > 0:
                pyautogui.click(x, y, button=button)
                return "Clicked (" + str(x) + "," + str(y) + ")"
            return "Invalid coordinates"

        elif act == "type":
            text = action.get("text", "")
            if text:
                pyautogui.typewrite(text, interval=0.02)
                return "Typed: " + text[:50]
            return "No text"

        elif act == "press":
            key = action.get("key", "enter")
            pyautogui.press(key)
            return "Pressed: " + key

        elif act == "scroll":
            dy = action.get("dy", -3)
            pyautogui.scroll(dy)
            return "Scrolled " + str(dy)

        elif act == "drag":
            x1, y1 = action.get("x1", 0), action.get("y1", 0)
            x2, y2 = action.get("x2", 0), action.get("y2", 0)
            pyautogui.moveTo(x1, y1)
            pyautogui.drag(x2 - x1, y2 - y1, duration=0.5)
            return "Dragged"

        elif act == "done":
            return "Task completed: " + action.get("reason", "")

        elif act == "fail":
            return "Failed: " + action.get("reason", "Unknown")

        return "Unknown action: " + act

    # ═══════════════════════════════════════════════════════════════
    # AUTONOMOUS LOOP
    # ═══════════════════════════════════════════════════════════════

    def do_task(self, task: str, max_steps: int = 15, callback=None) -> str:
        """
        Autonomously complete a task by repeatedly:
        1. Taking screenshot + OCR
        2. Analyzing with AI
        3. Executing the action
        4. Repeating until done
        """
        self._history = []
        log.info("[VISION] Starting task: " + task)

        for step in range(max_steps):
            # Analyze
            action = self.analyze(task)
            log.info("[VISION] Step " + str(step + 1) + ": " + action.get("action", "") + " - " + action.get("reason", ""))

            if callback:
                callback(step + 1, action)

            # Check done/failed
            if action.get("action") == "done":
                return "Completed in " + str(step + 1) + " steps: " + action.get("reason", "")
            if action.get("action") == "fail":
                return "Failed at step " + str(step + 1) + ": " + action.get("reason", "")

            # Execute
            result = self.execute(action)
            log.info("[VISION] Result: " + result)

            # Brief pause for UI to update
            time.sleep(0.5)

        return "Max steps (" + str(max_steps) + ") reached"


# Singleton
_vision = None

def get_vision() -> VisionController:
    global _vision
    if _vision is None:
        _vision = VisionController()
    return _vision
