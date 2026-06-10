"""Computer Use Agent — AI sees and controls the screen via vision models + pyautogui."""

import base64
import io
import json
import logging
import os
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.25
    _HAS_PYGUI = True
except Exception:
    _HAS_PYGUI = False

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

try:
    import mss
    _HAS_MSS = True
except Exception:
    _HAS_MSS = False

logger = logging.getLogger(__name__)

VIS_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
VIS_FALLBACK = "meta-llama/llama-4-maverick-17b-128e-instruct"
HF_VIS_MODEL = "meta-llama/Llama-4-Scout-17B-16E"
MAX_ITERATIONS = 50
MAX_TASK_SEC = 180
SCREENSHOT_QUALITY = 40  # JPEG compression 1-100
MAX_IMAGE_SIZE = 1280  # Resize longest edge to this

_vision_client = None
_vision_lock = threading.Lock()


def _get_vision_client():
    global _vision_client
    if _vision_client is None:
        with _vision_lock:
            if _vision_client is None:
                from groq import Groq
                _vision_client = Groq(api_key=GROQ_API_KEY)
    return _vision_client


# ── Screen capture ─────────────────────────────────────────────


def capture_screen() -> Optional[bytes]:
    if not _HAS_MSS:
        return None
    try:
        with mss.mss() as sct:
            mon = sct.monitors[1]
            raw = sct.grab(mon)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
            # Resize if needed
            w, h = img.size
            if max(w, h) > MAX_IMAGE_SIZE:
                ratio = MAX_IMAGE_SIZE / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=SCREENSHOT_QUALITY, optimize=True)
            return buf.getvalue()
    except Exception as e:
        logger.error(f"capture_screen failed: {e}")
        return None


# ── Vision analysis ────────────────────────────────────────────

SYSTEM_PROMPT = """You are a computer-use AI. You see the screen and control the mouse and keyboard.

Your task: analyze what's on screen and output a **single next action** as JSON.

Available actions (output ONLY valid JSON, no other text):
{"action": "click", "x": int, "y": int, "button": "left"|"right"}
{"action": "double_click", "x": int, "y": int}
{"action": "move", "x": int, "y": int}
{"action": "type", "text": "string to type"}
{"action": "keypress", "key": "key_name"}   — e.g. "enter", "tab", "escape", "ctrl", "win"
{"action": "hotkey", "keys": ["ctrl", "c"]} — key combination
{"action": "scroll", "amount": int}          — negative = down, positive = up
{"action": "wait", "seconds": 0.5}
{"action": "done", "result": "summary of what was accomplished"}
{"action": "fail", "reason": "why the task cannot be completed"}

RULES:
1. Always look at the full screen before acting. Read all visible text carefully.
2. For text input: first click the text field, then use "type" action.
3. For OneNote/homework: navigate through the interface step by step.
4. If you see an error or unexpected state, try to recover.
5. Use wait(0.5-1.0) between actions to let UI update.
6. Only use "done" when the task is genuinely complete.
7. Coordinates must be within screen bounds.
8. Be precise with coordinates — look at button/text positions carefully."""


def _resize_for_api(img_bytes: bytes, max_side: int = MAX_IMAGE_SIZE) -> bytes:
    try:
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=SCREENSHOT_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception:
        return img_bytes


def _b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode("utf-8")


def analyze_screen(task: str, img_bytes: bytes) -> dict:
    client = _get_vision_client()
    b64_img = _b64(img_bytes)

    # Try Groq models first
    for attempt, model in enumerate([VIS_MODEL, VIS_FALLBACK]):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Task: {task}\n\nWhat does the screen look like and what action should I take next? Output ONLY valid JSON."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "high"}},
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            json_match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt == 0:
                    continue
                raise ValueError(f"Could not parse: {raw[:200]}")
        except Exception as e:
            if attempt == 0:
                continue
            # Both Groq models failed — try HF Inference API as fallback
            return _analyze_screen_hf(task, b64_img, model_error=e)

    # Fallback to Hugging Face Inference API
    return _analyze_screen_hf(task, b64_img)


def _analyze_screen_hf(task: str, b64_img: str, model_error: Exception = None) -> dict:
    """Fallback: use Hugging Face Inference API with HF_TOKEN."""
    if not HF_TOKEN:
        reason = f"Vision API error: {model_error}" if model_error else "No HF_TOKEN set and all vision models failed"
        return {"action": "fail", "reason": reason}

    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "model": HF_VIS_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Task: {task}\n\nWhat does the screen look like and what action should I take next? Output ONLY valid JSON."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 300,
        }).encode()

        req = urllib.request.Request(
            f"https://api-inference.huggingface.co/models/{HF_VIS_MODEL}/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {HF_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())

        raw = data["choices"][0]["message"]["content"].strip()
        json_match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"action": "fail", "reason": f"HF parse error: {raw[:200]}"}
    except Exception as e:
        reason = f"HF Inference API error: {e}"
        if model_error:
            reason = f"Vision API error: {model_error}; HF fallback also failed: {e}"
        return {"action": "fail", "reason": reason}


# ── Action execution ───────────────────────────────────────────

def _screen_size():
    try:
        import pyautogui as pg
        return pg.size()
    except Exception:
        return (1920, 1080)


def execute_vision_action(action: dict) -> str:
    act = action.get("action", "")
    try:
        if act == "click":
            x, y = int(action["x"]), int(action["y"])
            btn = action.get("button", "left")
            sw, sh = _screen_size()
            x, y = max(0, min(x, sw - 1)), max(0, min(y, sh - 1))
            pyautogui.click(x, y, button=btn)
            return f"Clicked ({x},{y})"

        elif act == "double_click":
            x, y = int(action["x"]), int(action["y"])
            sw, sh = _screen_size()
            x, y = max(0, min(x, sw - 1)), max(0, min(y, sh - 1))
            pyautogui.doubleClick(x, y)
            return f"Double-clicked ({x},{y})"

        elif act == "move":
            x, y = int(action["x"]), int(action["y"])
            sw, sh = _screen_size()
            x, y = max(0, min(x, sw - 1)), max(0, min(y, sh - 1))
            pyautogui.moveTo(x, y)
            return f"Moved to ({x},{y})"

        elif act == "type":
            text = action.get("text", "")
            pyautogui.write(text, interval=0.05)
            return f"Typed {len(text)} chars"

        elif act == "keypress":
            key = action.get("key", "")
            pyautogui.press(key)
            return f"Pressed {key}"

        elif act == "hotkey":
            keys = action.get("keys", [])
            pyautogui.hotkey(*keys)
            return f"Hotkey: {'+'.join(keys)}"

        elif act == "scroll":
            amount = int(action.get("amount", 0))
            pyautogui.scroll(amount)
            return f"Scrolled {amount}"

        elif act == "wait":
            time.sleep(float(action.get("seconds", 0.5)))
            return f"Waited {action.get('seconds', 0.5)}s"

        elif act == "done":
            return f"DONE: {action.get('result', 'Task complete')}"

        elif act == "fail":
            return f"FAIL: {action.get('reason', 'Unknown failure')}"

        else:
            return f"Unknown action: {act}"

    except Exception as e:
        return f"Action error: {e}"


# ── Main task loop ─────────────────────────────────────────────

@dataclass
class TaskResult:
    success: bool
    summary: str
    steps: int = 0
    duration_sec: float = 0.0
    log: list = field(default_factory=list)


def run_task(task_description: str, max_iter: int = MAX_ITERATIONS) -> TaskResult:
    if not _HAS_PYGUI or not _HAS_PIL or not _HAS_MSS:
        return TaskResult(False, "Missing dependencies: pyautogui, Pillow, or mss")

    from groq_agent import GROQ_API_KEY as GAK
    if not GAK:
        return TaskResult(False, "GROQ_API_KEY not set")

    start = time.time()
    log = []
    prev_screenshots = []  # Track recent screenshots to detect no change

    try:
        for step in range(1, max_iter + 1):
            elapsed = time.time() - start
            if elapsed > MAX_TASK_SEC:
                return TaskResult(False, f"Timeout after {elapsed:.0f}s", step, elapsed, log)

            # Capture screen
            img = capture_screen()
            if img is None:
                return TaskResult(False, "Screen capture failed", step, elapsed, log)

            # Check if screen changed from last iteration (avoid loops)
            if prev_screenshots:
                pass  # We could check similarity, but skip for speed

            prev_screenshots.append(img)
            if len(prev_screenshots) > 5:
                prev_screenshots.pop(0)

            # Analyze with vision
            action = analyze_screen(task_description, img)

            # Execute action
            result = execute_vision_action(action)
            log.append(f"Step {step}: {json.dumps(action)} → {result}")

            # Check completion
            if result.startswith("DONE:"):
                return TaskResult(True, result[5:].strip(), step, time.time() - start, log)
            if result.startswith("FAIL:"):
                return TaskResult(False, result[5:].strip(), step, time.time() - start, log)

    except Exception as e:
        return TaskResult(False, f"Error: {e}", 0, time.time() - start, log)

    return TaskResult(False, f"Max iterations ({max_iter}) reached", max_iter, time.time() - start, log)


# ── Background execution ───────────────────────────────────────

_current_task: Optional[dict] = None
_task_lock = threading.Lock()
_task_thread: Optional[threading.Thread] = None


def start_task_bg(task_description: str) -> str:
    global _current_task, _task_thread
    task_id = f"task_{int(time.time())}"
    with _task_lock:
        _current_task = {"id": task_id, "description": task_description, "status": "running", "result": None}
    _task_thread = threading.Thread(target=_run_bg, args=(task_id, task_description), daemon=True)
    _task_thread.start()
    return task_id


def _run_bg(task_id: str, desc: str):
    result = run_task(desc)
    with _task_lock:
        if _current_task and _current_task["id"] == task_id:
            _current_task["status"] = "done" if result.success else "failed"
            _current_task["result"] = result


def get_task_status(task_id: str = None) -> dict:
    with _task_lock:
        if _current_task is None:
            return {"status": "idle"}
        if task_id and _current_task["id"] != task_id:
            return {"status": "not_found"}
        d = dict(_current_task)
        if d.get("result"):
            r = d["result"]
            d["summary"] = r.summary
            d["steps"] = r.steps
            d["duration_sec"] = round(r.duration_sec, 1)
            d["log"] = r.log
        return d
