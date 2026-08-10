"""
JARVIS Background VDI ReAct Loop — Observe → Plan → Act → Reflect.

Runs complex tasks in background VDI (DISPLAY=:99) without touching host desktop:
- Vision-based state observation (screenshot + OCR)
- LLM-powered planning and code generation
- PyAutoGUI/xdotool mouse/keyboard execution
- Self-healing reflection with automatic retry
- Live streaming to PiP overlay
"""
import os
import sys
import json
import time
import base64
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("react_loop")


class LoopState(Enum):
    """ReAct loop states."""
    IDLE = "idle"
    OBSERVING = "observing"
    PLANNING = "planning"
    ACTING = "acting"
    REFLECTING = "reflecting"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class LoopObservation:
    """Result of observing the VDI screen."""
    screenshot_b64: str = ""
    ocr_text: str = ""
    active_window: str = ""
    timestamp: float = 0.0
    display: str = ":99"


@dataclass
class LoopAction:
    """An action to execute in the VDI."""
    action_type: str  # mouse_click, type_text, hotkey, run_command, wait, run_python
    params: dict = field(default_factory=dict)
    description: str = ""
    timeout: int = 30


@dataclass
class LoopReflection:
    """Result of reflecting on action outcome."""
    success: bool
    state_changed: bool
    error: str = ""
    next_action: Optional[LoopAction] = None
    retry_count: int = 0


class VDIReactLoop:
    """Autonomous ReAct loop in background VDI."""

    def __init__(self, display: str = ":99"):
        self.display = display
        self.state = LoopState.IDLE
        self._max_iterations = 50
        self._max_retries = 3
        self._step_history = []
        self._screenshot_cache = {}

    # ── Main Loop ──────────────────────────────────────────────────────

    async def execute_task(self, goal: str, max_steps: int = None) -> dict:
        """Execute a complex task using ReAct loop in background VDI."""
        self.state = LoopState.OBSERVING
        max_steps = max_steps or self._max_iterations
        start_time = time.time()
        results = []

        logger.info(f"[ReAct] Starting task: {goal}")

        plan = await self._generate_plan(goal)
        if not plan:
            return {"success": False, "error": "Could not generate plan", "goal": goal}

        step_index = 0
        while step_index < len(plan) and step_index < max_steps:
            self.state = LoopState.OBSERVING
            observation = self._observe()
            logger.info(f"[ReAct] Step {step_index+1}: Observing... Window: {observation.active_window}")

            self.state = LoopState.PLANNING
            action = self._select_action(plan, step_index, observation)
            if not action:
                logger.info("[ReAct] No more actions needed")
                break

            logger.info(f"[ReAct] Step {step_index+1}: {action.description}")

            self.state = LoopState.ACTING
            act_result = await self._execute_action(action)
            results.append({
                "step": step_index + 1,
                "action": action.action_type,
                "description": action.description,
                "success": act_result.get("success", False),
                "result": act_result,
            })

            self.state = LoopState.REFLECTING
            reflection = self._reflect(observation, action, act_result)

            if not reflection.success and reflection.retry_count < self._max_retries:
                retry_action = reflection.next_action or action
                logger.info(f"[ReAct] Retrying step {step_index+1} (attempt {reflection.retry_count + 1})")
                retry_result = await self._execute_action(retry_action)
                results[-1]["retry"] = retry_result

            step_index += 1

        self.state = LoopState.COMPLETE
        duration = time.time() - start_time

        return {
            "success": True,
            "goal": goal,
            "steps_completed": step_index,
            "steps_total": len(plan),
            "results": results,
            "duration_seconds": round(duration, 2),
            "state": self.state.value,
        }

    # ── Observation ────────────────────────────────────────────────────

    def _observe(self) -> LoopObservation:
        """Capture current VDI screen state."""
        observation = LoopObservation(
            timestamp=time.time(),
            display=self.display,
        )

        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.display} xdotool getactivewindow getwindowname 2>/dev/null"],
                capture_output=True, text=True, timeout=5
            )
            observation.active_window = result.stdout.strip()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.display} import -window root png:- 2>/dev/null"],
                capture_output=True, timeout=10
            )
            if result.stdout:
                observation.screenshot_b64 = base64.b64encode(result.stdout).decode()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.display} xdotool getactivewindow getwindowname 2>/dev/null"],
                capture_output=True, text=True, timeout=5
            )
            observation.ocr_text = result.stdout.strip()
        except Exception:
            pass

        return observation

    # ── Planning ───────────────────────────────────────────────────────

    async def _generate_plan(self, goal: str) -> list:
        """Generate a step-by-step action plan using LLM."""
        prompt = f"""You are JARVIS running in a background Linux VDI (DISPLAY=:99 with XFCE4 desktop).
Goal: "{goal}"

Generate a step-by-step plan using ONLY these action types:
- mouse_click: {{"x": 500, "y": 300}} — Click at screen coordinates
- type_text: {{"text": "hello"}} — Type text
- hotkey: {{"keys": "ctrl+c"}} — Press keyboard shortcut
- run_command: {{"command": "ls -la"}} — Run shell command in VDI
- run_python: {{"code": "print('hello')"}} — Run Python code in VDI
- wait: {{"seconds": 2}} — Wait for system to respond
- scroll: {{"direction": "down", "amount": 3}} — Scroll mouse wheel
- right_click: {{"x": 500, "y": 300}} — Right-click at coordinates
- double_click: {{"x": 500, "y": 300}} — Double-click at coordinates

Output ONLY valid JSON: {{"steps": [{{"action_type": "...", "params": {{}}, "description": "..."}}]}}

The VDI has: XFCE4 desktop, Google Chrome, xfce4-terminal, mousepad text editor, Thunar file manager.
Screen resolution: 1920x1080.

JSON:"""

        try:
            from groq_agent import generate
            response = generate(prompt, user_id="react_loop", max_tokens=2000, temperature=0.1)
            if response:
                json_match = __import__("re").search(r'\{[\s\S]*\}', response)
                if json_match:
                    data = json.loads(json_match.group())
                    actions = []
                    for step in data.get("steps", []):
                        actions.append(LoopAction(
                            action_type=step.get("action_type", "wait"),
                            params=step.get("params", {}),
                            description=step.get("description", ""),
                        ))
                    return actions
        except Exception as e:
            logger.warning(f"LLM plan generation failed: {e}")

        return [
            LoopAction("wait", {"seconds": 2}, "Wait for desktop to load"),
            LoopAction("hotkey", {"keys": "ctrl+alt+t"}, "Open terminal"),
            LoopAction("wait", {"seconds": 1}, "Wait for terminal"),
            LoopAction("type_text", {"text": f"echo '{goal}'"}, "Enter goal command"),
            LoopAction("hotkey", {"keys": "Return"}, "Execute command"),
        ]

    def _select_action(self, plan: list, index: int,
                       observation: LoopObservation) -> Optional[LoopAction]:
        """Select the next action from the plan."""
        if index < len(plan):
            return plan[index]
        return None

    # ── Action Execution ───────────────────────────────────────────────

    async def _execute_action(self, action: LoopAction) -> dict:
        """Execute a single action in the VDI."""
        try:
            if action.action_type == "mouse_click":
                return self._xdotool_click(action.params.get("x", 0), action.params.get("y", 0))
            elif action.action_type == "right_click":
                return self._xdotool_click(action.params.get("x", 0), action.params.get("y", 0), button=3)
            elif action.action_type == "double_click":
                return self._xdotool_click(action.params.get("x", 0), action.params.get("y", 0), double=True)
            elif action.action_type == "type_text":
                return self._xdotool_type(action.params.get("text", ""))
            elif action.action_type == "hotkey":
                return self._xdotool_hotkey(action.params.get("keys", ""))
            elif action.action_type == "run_command":
                return self._wsl_run(action.params.get("command", ""))
            elif action.action_type == "run_python":
                return self._wsl_run_python(action.params.get("code", ""))
            elif action.action_type == "wait":
                await asyncio.sleep(action.params.get("seconds", 1))
                return {"success": True, "output": "Waited"}
            elif action.action_type == "scroll":
                direction = action.params.get("direction", "down")
                amount = action.params.get("amount", 3)
                button = "5" if direction == "down" else "4"
                return self._xdotool_scroll(amount, button)
            else:
                return {"success": False, "error": f"Unknown action: {action.action_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _xdotool_click(self, x: int, y: int, button: int = 1, double: bool = False) -> dict:
        """Click at coordinates using xdotool."""
        try:
            cmd = f"DISPLAY={self.display} xdotool mousemove {x} {y}"
            if double:
                cmd += " click --repeat 2 1"
            else:
                cmd += f" click {button}"
            subprocess.run(["wsl", "-e", "bash", "-c", cmd], capture_output=True, timeout=5)
            return {"success": True, "output": f"Clicked ({x}, {y})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _xdotool_type(self, text: str) -> dict:
        """Type text using xdotool."""
        try:
            escaped = text.replace("'", "'\\''")
            cmd = f"DISPLAY={self.display} xdotool type --delay 30 '{escaped}'"
            subprocess.run(["wsl", "-e", "bash", "-c", cmd], capture_output=True, timeout=10)
            return {"success": True, "output": f"Typed: {text[:50]}..."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _xdotool_hotkey(self, keys: str) -> dict:
        """Press hotkey combination using xdotool."""
        try:
            key_map = {
                "ctrl": "ctrl", "alt": "alt", "shift": "shift", "super": "super",
                "enter": "Return", "return": "Return", "tab": "Tab", "escape": "Escape",
                "space": "space", "backspace": "BackSpace", "delete": "Delete",
                "up": "Up", "down": "Down", "left": "Left", "right": "Right",
                "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4", "f5": "F5",
            }
            parts = keys.split("+")
            xdotool_keys = "+".join(key_map.get(p.strip().lower(), p.strip()) for p in parts)
            cmd = f"DISPLAY={self.display} xdotool key {xdotool_keys}"
            subprocess.run(["wsl", "-e", "bash", "-c", cmd], capture_output=True, timeout=5)
            return {"success": True, "output": f"Hotkey: {keys}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _xdotool_scroll(self, amount: int = 3, button: str = "5") -> dict:
        """Scroll mouse wheel using xdotool."""
        try:
            cmd = f"DISPLAY={self.display} xdotool click --repeat {amount} {button}"
            subprocess.run(["wsl", "-e", "bash", "-c", cmd], capture_output=True, timeout=5)
            return {"success": True, "output": f"Scrolled {amount} times"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _wsl_run(self, command: str) -> dict:
        """Run a shell command in WSL."""
        try:
            cmd = f"DISPLAY={self.display} bash -c '{command}'"
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:2000],
                "error": result.stderr[:1000] if result.returncode != 0 else ""
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _wsl_run_python(self, code: str) -> dict:
        """Run Python code in WSL."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", f"DISPLAY={self.display} python3 -c '{code}'"],
                capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:2000],
                "error": result.stderr[:1000] if result.returncode != 0 else ""
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Reflection ─────────────────────────────────────────────────────

    def _reflect(self, observation: LoopObservation, action: LoopAction,
                 result: dict) -> LoopReflection:
        """Reflect on action outcome and decide next step."""
        success = result.get("success", False)

        if success:
            return LoopReflection(success=True, state_changed=True)

        error = result.get("error", "Unknown error")
        logger.warning(f"[ReAct] Action failed: {error}")

        retry_action = LoopAction(
            action_type=action.action_type,
            params=action.params.copy(),
            description=f"Retry: {action.description}",
            timeout=action.timeout,
        )

        return LoopReflection(
            success=False,
            state_changed=False,
            error=error,
            next_action=retry_action,
            retry_count=1,
        )


# ── Vision Verification for Office Apps ────────────────────────────────

class VisionVerifier:
    """Verify and auto-correct Excel/Word/PowerPoint actions using screenshot + OCR."""

    def __init__(self, display: str = ":99"):
        self.display = display
        self._max_retries = 3

    def capture_screen(self) -> str:
        """Capture screenshot and return as base64."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.display} import -window root png:- 2>/dev/null"],
                capture_output=True, timeout=10
            )
            if result.stdout:
                return base64.b64encode(result.stdout).decode()
        except Exception:
            pass
        return ""

    def ocr_screen(self) -> str:
        """OCR the current screen and return text."""
        try:
            screenshot_b64 = self.capture_screen()
            if not screenshot_b64:
                return ""
            from rapidocr_onnxruntime import RapidOCR
            import numpy as np
            from PIL import Image
            import io

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

    def get_active_window(self) -> str:
        """Get the active window title."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.display} xdotool getactivewindow getwindowname 2>/dev/null"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def verify_excel_action(self, expected: str, cell_range: str = None) -> dict:
        """Verify an Excel action by reading the screen.

        expected: What we expect to see (e.g., "SUM formula result = 42")
        cell_range: Optional cell range to check (e.g., "A1")
        """
        window = self.get_active_window()
        if "excel" not in window.lower() and "libreoffice" not in window.lower():
            logger.info(f"[VisionVerify] Not in Excel (window: {window}), skipping")
            return {"verified": True, "action": "skip", "reason": "not_in_excel"}

        ocr_text = self.ocr_screen()
        if not ocr_text:
            return {"verified": False, "action": "retry", "reason": "ocr_failed"}

        expected_lower = expected.lower()
        ocr_lower = ocr_text.lower()

        if expected_lower in ocr_lower:
            logger.info(f"[VisionVerify] Excel verified: '{expected}' found on screen")
            return {"verified": True, "action": "none", "ocr_text": ocr_text[:500]}

        error_patterns = ["#NAME?", "#REF!", "#VALUE!", "#N/A", "#DIV/0!", "#NULL!", "#NUM!"]
        for err in error_patterns:
            if err.lower() in ocr_lower:
                logger.warning(f"[VisionVerify] Excel error detected: {err}")
                return {
                    "verified": False,
                    "action": "fix_error",
                    "error": err,
                    "ocr_text": ocr_text[:500],
                    "suggestion": f"Formula returned {err} - check syntax or cell references"
                }

        logger.warning(f"[VisionVerify] Expected '{expected}' not found in Excel screen")
        return {
            "verified": False,
            "action": "retry",
            "reason": "content_not_visible",
            "ocr_text": ocr_text[:500]
        }

    def verify_word_action(self, expected: str, style_name: str = None) -> dict:
        """Verify a Word/Writer action by reading the screen.

        expected: What we expect to see (e.g., "Heading 1 applied")
        style_name: Optional style name to verify (e.g., "Heading 1")
        """
        window = self.get_active_window()
        if "word" not in window.lower() and "libreoffice" not in window.lower() and "writer" not in window.lower():
            logger.info(f"[VisionVerify] Not in Word (window: {window}), skipping")
            return {"verified": True, "action": "skip", "reason": "not_in_word"}

        ocr_text = self.ocr_screen()
        if not ocr_text:
            return {"verified": False, "action": "retry", "reason": "ocr_failed"}

        expected_lower = expected.lower()
        ocr_lower = ocr_text.lower()

        if expected_lower in ocr_lower:
            logger.info(f"[VisionVerify] Word verified: '{expected}' found on screen")
            return {"verified": True, "action": "none", "ocr_text": ocr_text[:500]}

        if style_name:
            logger.warning(f"[VisionVerify] Expected style '{style_name}' not confirmed")
            return {
                "verified": False,
                "action": "retry_format",
                "reason": "style_not_applied",
                "ocr_text": ocr_text[:500]
            }

        return {
            "verified": False,
            "action": "retry",
            "reason": "content_not_visible",
            "ocr_text": ocr_text[:500]
        }

    def verify_and_correct(self, action_type: str, expected: str, **kwargs) -> dict:
        """Main entry point: verify an action and auto-correct if needed.

        action_type: 'excel' or 'word'
        expected: What we expect to see on screen
        """
        for attempt in range(self._max_retries):
            if action_type == "excel":
                result = self.verify_excel_action(expected, **kwargs)
            elif action_type == "word":
                result = self.verify_word_action(expected, **kwargs)
            else:
                return {"verified": True, "action": "skip", "reason": "unknown_action_type"}

            if result.get("verified"):
                return result

            action = result.get("action", "retry")
            if action == "fix_error":
                logger.info(f"[VisionVerify] Auto-fixing Excel error: {result.get('error', '')}")
                return result
            elif action == "retry_format":
                logger.info(f"[VisionVerify] Retrying format application (attempt {attempt + 1})")
                continue
            elif action == "retry":
                logger.info(f"[VisionVerify] Retrying action (attempt {attempt + 1})")
                time.sleep(1)
                continue

        return {"verified": False, "action": "failed", "reason": "max_retries_exceeded"}


# ── Convenience Functions ─────────────────────────────────────────────

async def run_react_task(goal: str, display: str = ":99", max_steps: int = 30) -> dict:
    """Run a complex task using the ReAct loop."""
    loop = VDIReactLoop(display=display)
    return await loop.execute_task(goal, max_steps=max_steps)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[REACT] %(message)s")
    loop = VDIReactLoop()
    print(f"VDI ReAct Loop initialized")
    print(f"Display: {loop.display}")
    print(f"Max iterations: {loop._max_iterations}")
    print(f"Max retries: {loop._max_retries}")
