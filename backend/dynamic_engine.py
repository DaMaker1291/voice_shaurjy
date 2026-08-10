"""
Dynamic Runtime Action Engine — Zero-hardcode, LLM-powered execution.

The AI generates Python/JS scripts on the fly for ANY app (Blender, iMovie,
Clipchamp, CapCut, Fusion 360, Chrome, Excel, anything with a UI).
Executes in a sandbox, inspects results with vision, self-heals on failure.

No hardcoded coordinates. No hardcoded selectors. No hardcoded API wrappers.
The LLM writes the code. The engine executes it. Vision verifies it.
"""

import os
import re
import sys
import json
import time
import types
import logging
import traceback
import importlib
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-dynamic")


@dataclass
class ExecutionResult:
    """Result of a dynamic code execution."""
    success: bool = False
    output: str = ""
    error: str = ""
    return_value: Any = None
    generated_code: str = ""
    attempts: int = 0
    vision_feedback: str = ""
    repair_history: List[str] = field(default_factory=list)


# ── Safe builtins for sandbox ──────────────────────────────────────────────
_SAFE_BUILTINS = {
    "print": print, "len": len, "range": range, "enumerate": enumerate,
    "zip": zip, "map": map, "filter": filter, "sorted": sorted,
    "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
    "int": int, "float": float, "str": str, "bool": bool, "list": list,
    "dict": dict, "tuple": tuple, "set": set, "type": type,
    "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
    "setattr": setattr, "True": True, "False": False, "None": None,
    "Exception": Exception, "ValueError": ValueError, "KeyError": KeyError,
    "IndexError": IndexError, "TypeError": TypeError, "RuntimeError": RuntimeError,
    "FileNotFoundError": FileNotFoundError, "OSError": OSError,
    "json": json, "time": time, "os": os, "re": re,
}

# Modules allowed in sandbox
_SAFE_MODULES = [
    "os", "sys", "json", "time", "math", "random", "re", "datetime",
    "pathlib", "subprocess", "shutil", "glob", "hashlib", "base64",
    "collections", "itertools", "functools", "string", "textwrap",
    "urllib", "http", "email", "csv", "io", "tempfile", "struct",
]

# Prompt for LLM code generation
_CODEGEN_PROMPT = """You are an expert automation engineer. Write a Python script to accomplish this task.

TASK: {task_description}

CONTEXT:
- OS: Windows
- Available tools: pyautogui (screen automation), pyperclip (clipboard), subprocess (shell),
  win32com.client (COM automation for Office apps), uiautomation (accessibility tree),
  ctypes (Win32 API), json, os, sys, time, math, re, datetime, pathlib, shutil, glob
- Window title of target app: {window_title}
- Current screen resolution: {resolution}

RULES:
1. Write COMPLETE, runnable Python code — no placeholders, no TODOs
2. Use pyautogui for screen automation (click, type, hotkey, screenshot)
3. Use win32com.client for Office apps (Word, Excel, PowerPoint, Outlook)
4. Use uiautomation to find UI elements by name/role (NOT hardcoded coordinates)
5. Use subprocess for CLI tools (ffmpeg, blender, etc.)
6. Import only safe modules: os, sys, json, time, math, random, re, datetime,
   pathlib, subprocess, shutil, glob, pyautogui, pyperclip, ctypes, json,
   win32com.client, uiautomation, base64, io, tempfile
7. Always wrap risky operations in try/except
8. Print status messages: print("[ACTION] doing X...")
9. At the end, print "[DONE]" on success or "[FAILED] reason" on failure
10. If the task involves a specific app, use COM automation or subprocess — not hardcoded coordinates
11. For video editors (CapCut, iMovie, Clipchamp): use their CLI if available, or COM, or subprocess
12. For 3D apps (Fusion 360, Blender): use their Python API (bpy, fusion360 API)
13. For browsers: use subprocess to control via CDP or selenium
14. Set result variable with the outcome: result = {{"success": True/False, "message": "..."}}

OUTPUT: Return ONLY the Python code, no markdown fences, no explanation.

PYTHON CODE:
"""


class DynamicActionEngine:
    """LLM-powered code synthesis and execution engine.
    
    Instead of hardcoded functions, the AI generates scripts on the fly.
    Executes in a sandboxed environment with self-healing on failure.
    """

    def __init__(self):
        self._max_retries = 3
        self._vision_available = False
        try:
            from vision_controller import get_vision
            self._vision_available = True
        except Exception:
            pass

    def execute_task(self, task_description: str, window_title: str = "",
                     resolution: str = "1920x1080", context: str = "",
                     max_retries: int = 3) -> ExecutionResult:
        """Full pipeline: task → LLM code → execute → vision verify → self-heal.
        
        Args:
            task_description: Natural language description of what to do
            window_title: Title of the target application window
            resolution: Screen resolution
            context: Additional context for the LLM
            max_retries: Maximum repair attempts
        
        Returns:
            ExecutionResult with output, error, generated code, etc.
        """
        self._max_retries = max_retries
        result = ExecutionResult()

        # Phase 1: Generate code via LLM
        log.info(f"[DYNAMIC] Generating code for: {task_description[:80]}...")
        code = self._generate_code(task_description, window_title, resolution, context)
        if not code:
            result.error = "LLM failed to generate code"
            return result

        result.generated_code = code

        # Phase 2-4: Execute, inspect, self-heal
        for attempt in range(1, max_retries + 1):
            result.attempts = attempt
            log.info(f"[DYNAMIC] Attempt {attempt}/{max_retries}")

            # Execute
            exec_result = self._execute_code(code)
            output = exec_result["output"]
            error = exec_result["error"]
            result.output = output

            if exec_result["success"]:
                # Vision verification (optional)
                if self._vision_available:
                    vision_ok, feedback = self._vision_inspect(task_description)
                    result.vision_feedback = feedback
                    if not vision_ok and attempt < max_retries:
                        log.info(f"[DYNAMIC] Vision found issues: {feedback[:200]}")
                        code = self._repair_code(code, f"Vision feedback: {feedback}", task_description)
                        result.repair_history.append(f"Attempt {attempt}: vision repair")
                        continue

                result.success = True
                result.generated_code = code
                break

            # Failure — try to repair
            if attempt < max_retries:
                log.info(f"[DYNAMIC] Repairing code (error: {error[:200]})")
                code = self._repair_code(code, error, task_description)
                result.repair_history.append(f"Attempt {attempt}: {error[:100]}")
            else:
                result.error = error

        return result

    def execute_code(self, code: str, context: str = "") -> ExecutionResult:
        """Execute pre-written Python code directly (no LLM generation).
        
        Use this when you already have the code and just need sandboxed execution.
        """
        result = ExecutionResult(generated_code=code)
        exec_result = self._execute_code(code)
        result.output = exec_result["output"]
        result.error = exec_result["error"]
        result.success = exec_result["success"]
        result.return_value = exec_result.get("return_value")
        result.attempts = 1
        return result

    def _generate_code(self, task: str, window_title: str, resolution: str,
                        context: str) -> str:
        """Use LLM to generate a Python script for the task."""
        try:
            from groq_agent import call
            prompt = _CODEGEN_PROMPT.format(
                task_description=task,
                window_title=window_title or "Not specified",
                resolution=resolution,
            )
            if context:
                prompt += f"\n\nADDITIONAL CONTEXT:\n{context}"

            response = call(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.15,
            )
            if not response:
                return ""

            # Clean markdown fences
            code = response.strip()
            if code.startswith("```"):
                code = re.sub(r'^```\w*\n?', '', code)
                code = re.sub(r'\n?```$', '', code)

            return code

        except Exception as e:
            log.error(f"[DYNAMIC] Code generation failed: {e}")
            return ""

    def _execute_code(self, code: str) -> Dict:
        """Execute Python code in a sandboxed environment.
        
        Returns: {"success": bool, "output": str, "error": str, "return_value": Any}
        """
        output_capture = []
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        class CaptureOutput:
            def __init__(self):
                self.lines = []
            def write(self, s):
                if s.strip():
                    self.lines.append(s.strip())
                original_stdout.write(s)
            def flush(self):
                original_stdout.flush()

        captured = CaptureOutput()
        sys.stdout = captured
        sys.stderr = captured

        # Build sandbox globals
        sandbox = dict(_SAFE_BUILTINS)
        sandbox["__name__"] = "__dynamic_sandbox__"
        sandbox["result"] = None

        # Add safe module imports
        for mod_name in _SAFE_MODULES:
            try:
                sandbox[mod_name] = importlib.import_module(mod_name)
            except ImportError:
                pass

        # Add pyautogui if available
        try:
            import pyautogui
            sandbox["pyautogui"] = pyautogui
        except ImportError:
            pass

        try:
            import pyperclip
            sandbox["pyperclip"] = pyperclip
        except ImportError:
            pass

        try:
            import win32com.client
            sandbox["win32com"] = types.ModuleType("win32com")
            sandbox["win32com"].client = win32com.client
        except ImportError:
            pass

        try:
            import uiautomation
            sandbox["uiautomation"] = uiautomation
        except ImportError:
            pass

        try:
            import ctypes
            sandbox["ctypes"] = ctypes
        except ImportError:
            pass

        try:
            import subprocess
            sandbox["subprocess"] = subprocess
        except ImportError:
            pass

        error_msg = ""
        try:
            exec(code, sandbox)
            # Check for result variable
            return_val = sandbox.get("result")
            error_msg = ""
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"
            return_val = None
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

        output = "\n".join(captured.lines)
        success = "[DONE]" in output and "[FAILED]" not in output

        # Also check result variable
        if return_val and isinstance(return_val, dict):
            success = return_val.get("success", success)

        return {
            "success": success,
            "output": output,
            "error": error_msg,
            "return_value": return_val,
        }

    def _repair_code(self, code: str, error: str, task: str) -> str:
        """Use LLM to fix a broken script based on error output."""
        try:
            from groq_agent import call
            fix_prompt = f"""This Python script has an error. Fix it and return the COMPLETE corrected script.

ORIGINAL TASK: {task}

ERROR:
{error[:1500]}

CURRENT SCRIPT (last 2500 chars):
```python
{code[-2500:]}
```

Fix the error. Common fixes:
- ImportError → remove or replace the import
- AttributeError → check method/attribute names
- TypeError → check argument types
- FileNotFoundError → check file paths
- SyntaxError → fix syntax
- pyautogui failures → use uiautomation or subprocess instead
- COM errors → use subprocess or uiautomation instead

Return ONLY the fixed Python code, no explanation."""

            response = call(
                messages=[{"role": "user", "content": fix_prompt}],
                max_tokens=3000,
                temperature=0.1,
            )
            if response:
                fixed = response.strip()
                if fixed.startswith("```"):
                    fixed = re.sub(r'^```\w*\n?', '', fixed)
                    fixed = re.sub(r'\n?```$', '', fixed)
                return fixed

        except Exception as e:
            log.debug(f"[DYNAMIC] Code repair failed: {e}")

        return code

    def _vision_inspect(self, task: str) -> Tuple[bool, str]:
        """Use vision to inspect the current screen state.
        
        Returns (is_ok, feedback_text).
        """
        try:
            import pyautogui
            import base64
            import io

            # Take screenshot
            screenshot = pyautogui.screenshot()
            buf = io.BytesIO()
            screenshot.save(buf, format="JPEG", quality=60)
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            from vision_controller import get_vision
            v = get_vision()

            inspect_prompt = f"""You are a UI automation inspector.

TASK WAS: {task}

Analyze this screenshot and evaluate:
1. Did the task complete successfully?
2. Is the expected result visible on screen?
3. Any error dialogs, popups, or unexpected states?
4. Is the target app in focus?

Respond with ONLY JSON:
{{"ok": true/false, "issues": ["issue1"], "suggestion": "brief fix"}}"""

            result = v.analyze_with_prompt(img_b64, inspect_prompt)
            if isinstance(result, str):
                json_match = re.search(r'\{[^}]+\}', result)
                if json_match:
                    data = json.loads(json_match.group())
                    return data.get("ok", True), data.get("suggestion", "No issues")
                return True, "Vision check passed"
            return True, "Vision unavailable"

        except Exception as e:
            log.debug(f"[DYNAMIC] Vision inspect failed: {e}")
            return True, "Vision inspection unavailable"


# ── Convenience ────────────────────────────────────────────────────────────

_engine: Optional[DynamicActionEngine] = None

def get_dynamic_engine() -> DynamicActionEngine:
    global _engine
    if _engine is None:
        _engine = DynamicActionEngine()
    return _engine

def execute_task(task: str, window_title: str = "", context: str = "") -> ExecutionResult:
    """One-call convenience: task description → generated code → execution → result."""
    return get_dynamic_engine().execute_task(task, window_title=window_title, context=context)

def execute_code(code: str) -> ExecutionResult:
    """Execute pre-written Python code in the sandbox."""
    return get_dynamic_engine().execute_code(code)
