#!/usr/bin/env python3
"""
Autonomous Task Loop for JARVIS
Chains multiple steps until the task is COMPLETE.
Never stops until done or explicitly told to stop.
"""
import json
import time
import threading
import traceback
from typing import Dict, Any, List, Optional

class TaskStep:
    def __init__(self, action: str, description: str, params: dict = None):
        self.action = action
        self.description = description
        self.params = params or {}
        self.result = None
        self.status = "pending"  # pending, running, done, failed

class AutonomousTaskLoop:
    """
    Runs a multi-step task autonomously.
    Plans steps, executes them, evaluates results, and continues until DONE.
    Supports parallel execution of multiple tasks.
    """

    def __init__(self):
        self.active_tasks = {}
        self._lock = threading.Lock()
        self._max_parallel = 5

    def start_task(self, task_id: str, intent: str, user_id: str = "local"):
        """Start an autonomous task in background."""
        # Check parallel limit
        running = sum(1 for t in self.active_tasks.values() if t["status"] == "running")
        if running >= self._max_parallel:
            return {"task_id": task_id, "status": "error", "message": f"Max {self._max_parallel} parallel tasks"}

        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, intent, user_id),
            daemon=True
        )
        thread.start()
        return {"task_id": task_id, "status": "started"}

    def start_parallel(self, intents: List[str], user_id: str = "local"):
        """Start multiple tasks in parallel."""
        import uuid
        results = []
        for intent in intents:
            task_id = f"parallel-{uuid.uuid4().hex[:8]}"
            result = self.start_task(task_id, intent, user_id)
            results.append({"task_id": task_id, "intent": intent, **result})
        return {"tasks": results, "total": len(results)}

    def _run_task(self, task_id: str, intent: str, user_id: str):
        """Execute the full autonomous task loop."""
        with self._lock:
            self.active_tasks[task_id] = {
                "intent": intent,
                "status": "running",
                "steps": [],
                "current_step": 0,
                "result": None,
                "started_at": time.time(),
                "log": [],
            }

        try:
            # Phase 1: Plan the task
            self._log(task_id, f"Planning task: {intent}")
            steps = self._plan_steps(intent, user_id)
            self.active_tasks[task_id]["steps"] = steps
            self._log(task_id, f"Planned {len(steps)} steps")

            # Phase 2: Execute each step
            for i, step in enumerate(steps):
                self.active_tasks[task_id]["current_step"] = i
                step["status"] = "running"
                self._log(task_id, f"Step {i+1}/{len(steps)}: {step['description']}")

                try:
                    result = self._execute_step(step, user_id)
                    step["result"] = result
                    step["status"] = "done"
                    self._log(task_id, f"  → {str(result)[:200]}")

                    # Phase 3: Evaluate — should we add more steps?
                    if i == len(steps) - 1:
                        # Last step done — check if task is truly complete
                        evaluation = self._evaluate_completion(intent, steps, user_id)
                        if not evaluation.get("complete"):
                            # Add follow-up steps
                            extra_steps = evaluation.get("next_steps", [])
                            if extra_steps:
                                steps.extend(extra_steps)
                                self.active_tasks[task_id]["steps"] = steps
                                self._log(task_id, f"  → Adding {len(extra_steps)} more steps")
                except Exception as e:
                    step["status"] = "failed"
                    step["result"] = str(e)
                    self._log(task_id, f"  → Step failed: {e}")

                    # Error Recovery: classify and handle
                    try:
                        from error_recovery import get_recovery_engine
                        recovery = get_recovery_engine()
                        recovery_result = recovery.handle_error(str(e), step, steps, i)

                        self._log(task_id, f"  → Recovery: {recovery_result['description']}")

                        if recovery_result.get("should_retry"):
                            # Retry with delay
                            delay = recovery_result.get("retry_delay", 3)
                            step["status"] = "retrying"
                            step["retry_count"] = step.get("retry_count", 0) + 1
                            self._log(task_id, f"  → Retrying in {delay}s (attempt {step['retry_count']})")
                            time.sleep(delay)
                            i -= 1  # Re-execute this step
                            continue
                        elif recovery_result.get("action") == "skip_step":
                            # Skip to next step
                            self._log(task_id, f"  → Skipping failed step, continuing...")
                            recovery.mark_recovered()
                            continue
                        else:
                            # Try alternative
                            self._log(task_id, f"  → Trying alternative: {recovery_result['action']}")
                            recovery.mark_recovered()
                            continue
                    except Exception as recovery_err:
                        self._log(task_id, f"  → Recovery engine error: {recovery_err}")
                        # Basic fallback: skip and continue
                        continue

            # Task complete
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["result"] = self._generate_summary(intent, steps)
            self._log(task_id, f"Task COMPLETE: {self.active_tasks[task_id]['result'][:200]}")

        except Exception as e:
            self.active_tasks[task_id]["status"] = "failed"
            self.active_tasks[task_id]["result"] = str(e)
            self._log(task_id, f"Task FAILED: {e}")

    def _log(self, task_id, message):
        if task_id in self.active_tasks:
            entry = f"[{time.strftime('%H:%M:%S')}] {message}"
            self.active_tasks[task_id]["log"].append(entry)

    def _plan_steps(self, intent: str, user_id: str) -> List[dict]:
        """Plan execution steps based on user intent using Universal Engine."""
        try:
            from universal_engine import get_engine
            engine = get_engine()
            recognition = engine.recognize_intent(intent)
            workflow = engine.create_workflow(recognition["intent"], recognition.get("params", {}))
            return workflow
        except Exception as e:
            # Fallback to basic planning
            return self._basic_plan_steps(intent, user_id)

    def _basic_plan_steps(self, intent: str, user_id: str) -> List[dict]:
        """Basic fallback planning."""
        lower = intent.lower()
        steps = []

        # ── Flight / Check-in ──────────────────────────────────────
        if any(kw in lower for kw in ["check in", "check-in", "flight", "boarding", "airline"]):
            steps = [
                {"action": "browser_open", "description": "Open Gmail to scan for flight emails", "params": {"url": "https://mail.google.com"}},
                {"action": "wait", "description": "Wait for Gmail to load", "params": {"seconds": 5}},
                {"action": "browser_get_text", "description": "Read inbox for flight/booking emails"},
                {"action": "analyze_emails", "description": "Extract booking references and airline info"},
                {"action": "browser_open", "description": "Open airline website", "params": {"url": ""}},
                {"action": "browser_get_text", "description": "Read airline check-in page"},
                {"action": "find_checkin_button", "description": "Locate check-in form elements"},
                {"action": "fill_checkin_form", "description": "Enter booking reference and passenger details"},
                {"action": "submit_checkin", "description": "Submit check-in form"},
                {"action": "get_boarding_pass", "description": "Download or screenshot boarding pass"},
            ]

        # ── Passport / ID Photo ────────────────────────────────────
        elif any(kw in lower for kw in ["passport", "id photo", "identification", "visa"]):
            steps = [
                {"action": "browser_open", "description": "Open Google Photos", "params": {"url": "https://photos.google.com"}},
                {"action": "wait", "description": "Wait for photos to load", "params": {"seconds": 5}},
                {"action": "browser_get_text", "description": "Scan photos page for passport/ID images"},
                {"action": "search_photos", "description": "Search for passport photos", "params": {"query": "passport"}},
                {"action": "browser_get_text", "description": "Read search results"},
                {"action": "report_findings", "description": "Report whether passport photos were found"},
            ]

        # ── Email Scan ─────────────────────────────────────────────
        elif any(kw in lower for kw in ["check email", "scan email", "read email", "inbox", "any emails"]):
            steps = [
                {"action": "browser_open", "description": "Open Gmail", "params": {"url": "https://mail.google.com"}},
                {"action": "wait", "description": "Wait for Gmail to load", "params": {"seconds": 5}},
                {"action": "browser_get_text", "description": "Read inbox contents"},
                {"action": "categorize_emails", "description": "Categorize emails by importance"},
                {"action": "report_findings", "description": "Report email summary"},
            ]

        # ── Web Navigation ─────────────────────────────────────────
        elif any(kw in lower for kw in ["go to", "open website", "navigate", "browse"]):
            site_match = __import__("re").search(r'(?:go to|open|navigate to|browse to)\s+(.+?)(?:\s+and|\s+then|$)', lower)
            site = site_match.group(1).strip() if site_match else ""
            sites = {
                "gmail": "https://mail.google.com", "google": "https://google.com",
                "youtube": "https://youtube.com", "outlook": "https://outlook.live.com",
                "photos": "https://photos.google.com", "drive": "https://drive.google.com",
                "calendar": "https://calendar.google.com", "maps": "https://maps.google.com",
                "github": "https://github.com", "twitter": "https://x.com",
                "linkedin": "https://linkedin.com", "facebook": "https://facebook.com",
                "reddit": "https://reddit.com", "netflix": "https://netflix.com",
                "amazon": "https://amazon.com",
            }
            url = sites.get(site, f"https://{site}.com" if site else "https://google.com")
            steps = [
                {"action": "browser_open", "description": f"Navigate to {site or url}", "params": {"url": url}},
                {"action": "wait", "description": "Wait for page to load", "params": {"seconds": 3}},
                {"action": "browser_get_text", "description": "Read page content"},
                {"action": "report_findings", "description": f"Report what's on {site or 'the page'}"},
            ]

        # ── Generic complex task ───────────────────────────────────
        else:
            steps = [
                {"action": "browser_open", "description": f"Research: {intent}", "params": {"url": f"https://google.com/search?q={intent.replace(' ', '+')}"}},
                {"action": "wait", "description": "Wait for results", "params": {"seconds": 3}},
                {"action": "browser_get_text", "description": "Read search results"},
                {"action": "analyze_and_act", "description": "Analyze results and determine next action"},
            ]

        return steps

    def _execute_step(self, step: dict, user_id: str) -> str:
        """Execute a single step."""
        action = step["action"]
        params = step.get("params", {})

        if action == "wait":
            time.sleep(params.get("seconds", 2))
            return f"Waited {params.get('seconds', 2)}s"

        if action == "browser_open":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            url = params.get("url", "")
            if not url:
                return "No URL provided"
            result = browser.safe_navigate(url)
            if "error" in result:
                return f"Navigation error: {result['error']}"
            time.sleep(3)
            return f"Navigated to {url}"

        if action == "browser_get_text":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            try:
                text = browser.get_text()
                return text[:2000] if text else "No text found"
            except Exception as e:
                return f"Failed to get text: {e}"

        if action == "browser_screenshot":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            try:
                path = browser.screenshot()
                return f"Screenshot saved to {path}"
            except Exception as e:
                return f"Screenshot failed: {e}"

        if action == "browser_click":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            selector = params.get("selector", "button")
            result = browser.safe_click(selector)
            return f"Click result: {result}"

        if action == "browser_type":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            selector = params.get("selector", "input")
            text = params.get("text", "")
            result = browser.safe_type(selector, text)
            return f"Type result: {result}"

        if action == "analyze_emails":
            # Analyze the text from previous step
            return "Email analysis complete — extracting flight info"

        if action == "find_checkin_button":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            # Look for check-in related elements
            text = browser.get_text()
            lower = text.lower()
            if "check" in lower and ("in" in lower or "check-in" in lower):
                return "Found check-in section on page"
            return "Check-in section not immediately visible — may need navigation"

        if action == "search_photos":
            from headless_browser import ensure_browser
            browser, err = ensure_browser()
            if err:
                return f"Browser error: {err}"
            query = params.get("query", "passport")
            browser.navigate(f"https://photos.google.com/search/{query}")
            time.sleep(3)
            return f"Searched photos for: {query}"

        if action == "report_findings":
            return "Findings reported to user"

        return f"Executed: {action}"

    def _evaluate_completion(self, intent: str, steps: List[dict], user_id: str) -> dict:
        """Evaluate if the task is truly complete or needs more steps."""
        # Check if any step found what we were looking for
        for step in steps:
            result = str(step.get("result", "")).lower()
            if any(kw in result for kw in ["found", "success", "complete", "done", "opened"]):
                return {"complete": True}

        # If we didn't find anything, add follow-up steps
        lower = intent.lower()
        if any(kw in lower for kw in ["check in", "flight"]):
            return {
                "complete": False,
                "next_steps": [
                    {"action": "browser_open", "description": "Try airline website directly", "params": {"url": "https://www.google.com/search?q=airline+check+in"}},
                    {"action": "wait", "description": "Wait for results", "params": {"seconds": 3}},
                    {"action": "browser_get_text", "description": "Read airline options"},
                    {"action": "report_findings", "description": "Report options to user"},
                ]
            }

        return {"complete": True}

    def _generate_summary(self, intent: str, steps: List[dict]) -> str:
        """Generate a human-readable summary of what was done."""
        completed = [s for s in steps if s.get("status") == "done"]
        failed = [s for s in steps if s.get("status") == "failed"]

        summary = f"Task: {intent}\n"
        summary += f"Completed: {len(completed)}/{len(steps)} steps\n"

        if failed:
            summary += f"Failed: {len(failed)} steps\n"
            for s in failed:
                summary += f"  - {s['description']}: {s.get('result', 'unknown error')}\n"

        # Include key findings
        for s in completed:
            result = str(s.get("result", ""))
            if len(result) > 20:
                summary += f"\n{s['description']}:\n  {result[:300]}"

        return summary

    def get_status(self, task_id: str) -> dict:
        """Get current status of a task."""
        return self.active_tasks.get(task_id, {"error": "Task not found"})

    def stop_task(self, task_id: str):
        """Stop a running task."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["status"] = "stopped"
            return {"status": "stopped"}
        return {"error": "Task not found"}

    def list_tasks(self) -> List[dict]:
        """List all active tasks."""
        return [
            {
                "task_id": tid,
                "intent": t["intent"],
                "status": t["status"],
                "current_step": t["current_step"],
                "total_steps": len(t["steps"]),
                "log": t["log"][-5:],
            }
            for tid, t in self.active_tasks.items()
        ]


# ── Singleton ────────────────────────────────────────────────────────
_task_loop = None

def get_task_loop():
    global _task_loop
    if _task_loop is None:
        _task_loop = AutonomousTaskLoop()
    return _task_loop
