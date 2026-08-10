"""
VM Agent — autonomous agent that operates in an isolated virtual desktop.
Has its OWN mouse, keyboard, OCR, and vision — completely separate from the user's screen.
"""

import json
import time
import base64
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VMTaskResult:
    success: bool = False
    summary: str = ""
    steps: int = 0
    duration_sec: float = 0.0
    screenshots: list = field(default_factory=list)
    target: str = "vm"
    blocked: bool = False
    block_type: str = ""
    block_message: str = ""


class VMAgent:
    """Autonomous agent that operates in a headless virtual desktop.
    Uses its own mouse/keyboard/OCR/vision — never touches the user's screen."""

    def __init__(self, session_id: str = "jarvis_vm"):
        self.session_id = session_id
        self._worker = None
        self._session_active = False

    def _ensure_worker(self):
        if self._worker is None:
            try:
                from headless_worker import JarvisHeadlessWorker
                self._worker = JarvisHeadlessWorker()
            except ImportError:
                raise RuntimeError("headless_worker not available")

    def _ensure_session(self) -> bool:
        self._ensure_worker()
        if self._session_active:
            return True
        try:
            result = self._worker.start_session(self.session_id)
            if isinstance(result, dict) and result.get("ok", True):
                self._session_active = True
                return True
        except Exception:
            pass
        return False

    def screenshot(self) -> Optional[bytes]:
        """Capture the VM screen. Returns PNG bytes or None."""
        self._ensure_worker()
        try:
            data = self._worker.screenshot(self.session_id)
            return data
        except Exception:
            return None

    def screenshot_base64(self) -> str:
        """Capture VM screen and return base64 string."""
        data = self.screenshot()
        if data:
            return base64.b64encode(data).decode()
        return ""

    def click(self, x: int, y: int, button: str = "left") -> str:
        """Click at position in the VM. Uses its OWN mouse."""
        self._ensure_worker()
        try:
            self._worker.inject_click(self.session_id, x, y, 1 if button == "left" else 3)
            return f"Clicked ({x},{y})"
        except Exception as e:
            return f"Click error: {e}"

    def type_text(self, text: str) -> str:
        """Type text in the VM. Uses its OWN keyboard."""
        self._ensure_worker()
        try:
            self._worker.inject_text(self.session_id, text)
            return f"Typed: {text[:50]}"
        except Exception as e:
            return f"Type error: {e}"

    def press_key(self, key: str) -> str:
        """Press a key in the VM."""
        self._ensure_worker()
        try:
            self._worker.inject_key(self.session_id, key)
            return f"Pressed: {key}"
        except Exception as e:
            return f"Key error: {e}"

    def launch_app(self, app_name: str, command: list = None) -> str:
        """Launch an app in the VM."""
        self._ensure_worker()
        if not self._session_active:
            self._ensure_session()
        try:
            cmd = command or [app_name]
            result = self._worker.launch_app(self.session_id, app_name, cmd)
            return f"Launched {app_name} in VM"
        except Exception as e:
            return f"Launch error: {e}"

    def ocr_screen(self) -> list[dict]:
        """Read text from VM screen using OCR. Returns list of {text, x, y, w, h}."""
        try:
            from PIL import Image
            import io

            data = self.screenshot()
            if not data:
                return []

            img = Image.open(io.BytesIO(data))

            try:
                import pytesseract
                raw = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                elements = []
                for i in range(len(raw["text"])):
                    if raw["text"][i].strip() and int(raw["conf"][i] or 0) > 20:
                        elements.append({
                            "text": raw["text"][i],
                            "x": raw["left"][i],
                            "y": raw["top"][i],
                            "w": raw["width"][i],
                            "h": raw["height"][i],
                            "confidence": int(raw["conf"][i] or 0),
                        })
                return elements
            except ImportError:
                # No pytesseract — return basic info
                return [{"text": "[OCR unavailable]", "x": 0, "y": 0, "w": 0, "h": 0}]
        except Exception:
            return []

    def get_windows(self) -> list[str]:
        """List windows in the VM."""
        self._ensure_worker()
        try:
            tree = self._worker.get_window_tree(self.session_id)
            if isinstance(tree, list):
                return [str(w) for w in tree]
            return [str(tree)] if tree else []
        except Exception:
            return []

    def execute_task(self, task_text: str, max_steps: int = 20) -> VMTaskResult:
        """Execute a task autonomously in the VM using vision + mouse/keyboard.
        This is the core loop: screenshot → OCR/vision → decide action → execute → repeat."""
        start = time.time()
        result = VMTaskResult(target="vm")

        if not self._ensure_session():
            result.summary = "Failed to start VM session"
            return result

        try:
            from screen_analyzer import get_analyzer
            has_analyzer = True
        except ImportError:
            has_analyzer = False

        try:
            import pyautogui
            has_pyautogui = True
        except ImportError:
            has_pyautogui = False

        # Load intervention manager
        try:
            from human_intervention import get_intervention_manager
            intervention_mgr = get_intervention_manager()
        except ImportError:
            intervention_mgr = None

        for step in range(max_steps):
            # 1. Screenshot
            png_data = self.screenshot()
            if not png_data:
                result.summary = f"Step {step+1}: Could not capture VM screen"
                break

            result.screenshots.append(base64.b64encode(png_data).decode()[:500])

            # 2. OCR — read what's on screen
            ocr_elements = self.ocr_screen()
            ocr_text = " ".join(e["text"] for e in ocr_elements if e["text"] != "[OCR unavailable]")

            # 3. CHECK FOR BLOCKS — login, CAPTCHA, payment, account creation
            if intervention_mgr:
                intervention = intervention_mgr.scan_page(ocr_text)
                if intervention:
                    # Block detected — pause and notify user
                    result.blocked = True
                    result.block_type = intervention.type.value
                    result.block_message = intervention_mgr.notify_user(intervention)
                    result.summary = f"BLOCKED: {intervention.type.value} — waiting for user"
                    log.info(f"VM task blocked at step {step+1}: {intervention.type.value}")
                    break

            # 4. Analyze with vision model if available
            action = self._vision_decide(task_text, ocr_text, png_data)

            # 5. Execute the action in the VM
            if action:
                act_type = action.get("action", "")
                if act_type == "click":
                    self.click(action.get("x", 0), action.get("y", 0))
                elif act_type == "type":
                    self.type_text(action.get("text", ""))
                elif act_type == "key":
                    self.press_key(action.get("key", "enter"))
                elif act_type == "scroll":
                    # Scroll in VM
                    self._worker.inject_click(self.session_id, action.get("x", 500),
                                               action.get("y", 500), 0)  # placeholder
                elif act_type == "done":
                    result.success = True
                    result.summary = action.get("summary", "Task completed")
                    break
                elif act_type == "error":
                    result.summary = action.get("error", "Unknown error")
                    break

                result.steps += 1
                time.sleep(0.5)  # Brief pause between steps
            else:
                # No vision model — use simple OCR-based heuristics
                if self._ocr_heuristic(task_text, ocr_elements):
                    result.steps += 1
                else:
                    result.summary = f"Step {step+1}: Could not determine next action"
                    break

        if not result.summary:
            result.summary = f"Completed {result.steps} steps in VM" if result.steps else "No steps executed"

        result.duration_sec = time.time() - start
        result.success = result.steps > 0 and not result.blocked
        return result

    def _vision_decide(self, task: str, ocr_text: str, screenshot_png: bytes) -> Optional[dict]:
        """Use a vision model to decide the next action based on VM screenshot."""
        try:
            from groq_agent import generate
            prompt = (
                f"Task: {task}\n"
                f"Screen text: {ocr_text[:500]}\n\n"
                f"Reply with JSON: {{\"action\": \"click\"|\"type\"|\"key\"|\"scroll\"|\"done\"|\"error\", "
                f"\"x\": N, \"y\": N, \"text\": \"...\", \"key\": \"...\", \"summary\": \"...\"}}\n"
                f"If the task is complete, use action=done. If stuck, use action=error."
            )
            reply = generate(prompt, max_tokens=200, temperature=0.3)
            if reply:
                import re
                m = re.search(r'\{[^{}]*\}', reply, re.DOTALL)
                if m:
                    return json.loads(m.group())
        except Exception:
            pass
        return None

    def _ocr_heuristic(self, task: str, elements: list[dict]) -> bool:
        """Simple OCR-based heuristics when no vision model is available."""
        lower = task.lower()
        # If task mentions typing, find a text field and type
        if "type" in lower or "enter" in lower or "write" in lower:
            # Find input-like elements (high confidence, reasonable size)
            for el in elements:
                if el.get("confidence", 0) > 50 and el.get("w", 0) > 50:
                    self.click(el["x"] + el["w"] // 2, el["y"] + el["h"] // 2)
                    time.sleep(0.3)
                    # Type the part after "type" or "enter"
                    for trigger in ["type ", "enter ", "write "]:
                        idx = lower.find(trigger)
                        if idx >= 0:
                            text = task[idx + len(trigger):].strip().strip('"\'')
                            if text:
                                self.type_text(text)
                                return True
            return False

        # If task mentions clicking something, find it by OCR
        for el in elements:
            text = el.get("text", "").lower()
            if text and text in lower:
                self.click(el["x"] + el["w"] // 2, el["y"] + el["h"] // 2)
                return True

        return False

    def stop(self):
        """Stop the VM session."""
        if self._worker and self._session_active:
            try:
                self._worker.stop_session(self.session_id)
            except Exception:
                pass
            self._session_active = False


# Singletons
_agents: dict[str, VMAgent] = {}


def get_vm_agent(session_id: str = "jarvis_vm") -> VMAgent:
    if session_id not in _agents:
        _agents[session_id] = VMAgent(session_id)
    return _agents[session_id]
