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
MAX_ITERATIONS = 80
MAX_TASK_SEC = 300
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

Your task: break down the user's request into small steps and output ONE action at a time as JSON.

COMMON UI PATTERNS:
• Address bar top of browser: click it, type URL, press enter
• Search box: click it, type query, press enter
• Button: click its center coordinates
• Dropdown: click to open, then click the option
• Text field: click first, then type
• Checkbox/radio: click directly on it
• Link: click on the link text
• Window title bar: drag by clicking top edge
• Scroll: scroll down to see more content
• Right-click: use button:"right" on click action

CHROME PROFILES:
After opening Chrome, look for the profile picker window (shows profile avatars/names).
Click the profile matching the name the user asked for. If you don't see the picker,
Chrome may have auto-opened to the default profile — look for the profile icon in the
top-right corner of the browser window.

AVAILABLE ACTIONS (output ONLY valid JSON):
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

CRITICAL RULES:
1. Examine the full screen before every action. Read all visible text.
2. For text input: ALWAYS click the text field first, THEN type.
3. Break complex tasks down to ONE action per response.
4. After each action, wait for the screen to update before deciding the next step.
5. If an app isn't visible, press Win key and search for it.
6. If stuck (same screen after action), try a different approach.
7. Coordinate order: (x=horizontal from left, y=vertical from top). Stay within screen bounds.
8. Only use "done" when the task is genuinely complete.
9. Use "wait" liberally (0.5-1.0s) after actions that change the screen.
10. If you see a login page, notify the user — don't try to type passwords."""


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


def _extract_json(raw: str) -> dict | None:
    """Robust JSON extraction supporting nested objects."""
    raw = raw.strip()
    # Direct parse
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # Balanced-brace scan for outermost JSON object
    stack = []
    for i, ch in enumerate(raw):
        if ch == "{":
            stack.append(i)
        elif ch == "}":
            if stack:
                start = stack.pop()
                if not stack:
                    try:
                        return json.loads(raw[start:i+1])
                    except json.JSONDecodeError:
                        # Nested brace might still be inside — continue scanning
                        continue
    # Last resort: find any {…} block with regex (may miss nested)
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def _hash_img(img_bytes: bytes) -> str:
    """Quick perceptual-ish hash to detect screen changes."""
    import hashlib
    # Downsample then hash — fast approximate comparison
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes))
        tiny = img.resize((16, 12), Image.NEAREST)
        buf = io.BytesIO()
        tiny.save(buf, format="JPEG", quality=10)
        return hashlib.md5(buf.getvalue()).hexdigest()
    except Exception:
        return hashlib.md5(img_bytes).hexdigest()


def analyze_screen(task: str, img_bytes: bytes, history: list = None) -> dict:
    client = _get_vision_client()
    b64_img = _b64(img_bytes)

    # Build context from previous steps so the model knows what's been done
    history_text = ""
    if history:
        recent = history[-6:]  # last 6 steps for context
        lines = []
        for h in recent:
            step = h.get("step", "?")
            act = h.get("action", {})
            res = h.get("result", "")
            lines.append(f"  Step {step}: {json.dumps(act)} → {res[:80]}")
        if lines:
            history_text = "Previous actions:\n" + "\n".join(lines) + "\n\n"

    prompt = f"Task: {task}\n\n{history_text}What does the screen look like and what action should I take next? Output ONLY valid JSON."

    # Try Groq models first
    for attempt, model in enumerate([VIS_MODEL, VIS_FALLBACK]):
        for retry in range(2):  # retry once on parse failure
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "high"}},
                            ],
                        }
                    ],
                    temperature=0.1,
                    max_tokens=600,
                )
                raw = resp.choices[0].message.content.strip()
                parsed = _extract_json(raw)
                if parsed:
                    return parsed
                if retry == 0:
                    continue
                raise ValueError(f"Could not parse after retry: {raw[:200]}")
            except Exception as e:
                if retry == 0 and not isinstance(e, ValueError):
                    continue
                if attempt == 0:
                    break  # try fallback model
                # Both Groq models failed — try HF Inference API
                return _analyze_screen_hf(task, b64_img, history, model_error=e)

    # Fallback to Hugging Face Inference API
    return _analyze_screen_hf(task, b64_img, history)


def _analyze_screen_hf(task: str, b64_img: str, history: list = None, model_error: Exception = None) -> dict:
    """Fallback: use Hugging Face Inference API with HF_TOKEN."""
    if not HF_TOKEN:
        reason = f"Vision API error: {model_error}" if model_error else "No HF_TOKEN set and all vision models failed"
        return {"action": "fail", "reason": reason}

    try:
        import urllib.request
        import urllib.error

        history_text = ""
        if history:
            recent = history[-6:]
            lines = []
            for h in recent:
                step = h.get("step", "?")
                act = h.get("action", {})
                res = h.get("result", "")
                lines.append(f"  Step {step}: {json.dumps(act)} → {res[:80]}")
            if lines:
                history_text = "Previous actions:\n" + "\n".join(lines) + "\n\n"

        prompt = f"Task: {task}\n\n{history_text}What does the screen look like and what action should I take next? Output ONLY valid JSON."

        payload = json.dumps({
            "model": HF_VIS_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 400,
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
        parsed = _extract_json(raw)
        if parsed:
            return parsed
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
    history = []  # Track action history for context in vision prompts
    last_hash = None
    stuck_count = 0
    MAX_STUCK = 4  # consecutive no-change screenshots → force recovery

    try:
        for step in range(1, max_iter + 1):
            elapsed = time.time() - start
            if elapsed > MAX_TASK_SEC:
                return TaskResult(False, f"Timeout after {elapsed:.0f}s", step, elapsed, log)

            # Capture screen
            img = capture_screen()
            if img is None:
                return TaskResult(False, "Screen capture failed", step, elapsed, log)

            # Stuck-state detection: if screen hasn't changed after an action, increment counter
            current_hash = _hash_img(img)
            if last_hash and current_hash == last_hash and step > 1:
                stuck_count += 1
                if stuck_count >= MAX_STUCK:
                    # Force a different action: press escape, wait, then re-evaluate
                    pyautogui.press("escape")
                    time.sleep(0.5)
                    stuck_count = 0
                    log.append(f"Step {step}: ⚠ Stuck detected — pressed Escape")
            else:
                stuck_count = 0
            last_hash = current_hash

            # Analyze with vision — pass history so model knows what's been done
            action = analyze_screen(task_description, img, history)

            # Execute action
            result = execute_vision_action(action)
            log.append(f"Step {step}: {json.dumps(action)} → {result}")

            # Track for next iteration's context
            history.append({"step": step, "action": action, "result": result})

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
