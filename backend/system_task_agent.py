#!/usr/bin/env python3
"""
System Task Agent for JARVIS
Completes real desktop tasks using screen perception + system control.
Sees the screen, finds elements, clicks/types, verifies, repeats.
"""
import subprocess
import json
import time
import os
import threading
from typing import Dict, Any, List, Optional

class SystemTaskAgent:
    """
    Autonomous desktop task completion:
    1. Take screenshot → OCR to see screen
    2. Plan next action based on goal
    3. Execute action (click/type/key/scroll)
    4. Verify result
    5. Repeat until done
    """

    MAX_STEPS = 50
    STEP_DELAY = 1.0
    VERIFY_DELAY = 1.5

    def __init__(self):
        self._running = False
        self._current_goal = ""
        self._steps_taken = []
        self._log = []

    def execute_goal(self, goal: str, max_steps: int = None) -> dict:
        """
        Execute a high-level goal on the desktop.
        Examples:
          - "Open Chrome and go to google.com"
          - "Turn on Dark Mode in System Settings"
          - "Send an email to john@example.com"
          - "Clean up my Downloads folder"
        """
        if max_steps:
            self.MAX_STEPS = max_steps

        self._running = True
        self._current_goal = goal
        self._steps_taken = []
        self._log = [f"Goal: {goal}"]

        try:
            from screen_perception import get_perception
            from system_controller import get_controller

            perception = get_perception()
            controller = get_controller()

            # Take initial screenshot
            self._log.append("Taking initial screenshot...")
            perception.screenshot_full()
            screen_info = perception.describe_screen()
            self._log.append(f"Screen: {screen_info}")

            # Plan steps based on goal
            self._log.append("Planning steps...")
            steps = self._plan_steps(goal, screen_info)
            self._log.append(f"Planned {len(steps)} steps")

            # Execute each step
            for i, step in enumerate(steps):
                if not self._running:
                    self._log.append("Stopped by user")
                    break

                if i >= self.MAX_STEPS:
                    self._log.append(f"Max steps ({self.MAX_STEPS}) reached")
                    break

                self._log.append(f"Step {i+1}/{len(steps)}: {step['description']}")

                # Take screenshot before action
                perception.screenshot_full()
                time.sleep(0.3)

                # Execute the action
                result = self._execute_step(step, perception, controller)
                self._log.append(f"  Result: {result.get('status', 'unknown')}")
                self._steps_taken.append({"step": step, "result": result})

                # Wait for screen to update
                time.sleep(self.STEP_DELAY)

                # Verify if needed
                if step.get("verify"):
                    self._log.append("  Verifying...")
                    time.sleep(self.VERIFY_DELAY)
                    perception.screenshot_full()
                    new_screen = perception.describe_screen()
                    self._log.append(f"  Screen after: {new_screen[:100]}...")

            self._running = False
            return {
                "status": "completed",
                "goal": goal,
                "steps_taken": len(self._steps_taken),
                "log": self._log,
            }

        except Exception as e:
            self._running = False
            self._log.append(f"Error: {str(e)}")
            return {"status": "error", "error": str(e), "log": self._log}

    def _plan_steps(self, goal: str, screen_info: str) -> List[dict]:
        """Plan action steps based on goal and current screen."""
        goal_lower = goal.lower()
        steps = []

        # ── App Launch ────────────────────────────────────────────────
        if "open" in goal_lower and ("chrome" in goal_lower or "browser" in goal_lower):
            steps.append({"action": "launch_app", "app": "Google Chrome", "description": "Open Chrome"})
            steps.append({"action": "wait", "seconds": 2, "description": "Wait for Chrome to open"})
            if "google" in goal_lower:
                steps.append({"action": "hotkey", "keys": ["cmd", "l"], "description": "Focus address bar"})
                steps.append({"action": "type_text", "text": "google.com", "description": "Type URL"})
                steps.append({"action": "press_key", "key": "return", "description": "Navigate"})

        elif "open" in goal_lower and "safari" in goal_lower:
            steps.append({"action": "launch_app", "app": "Safari", "description": "Open Safari"})

        elif "open" in goal_lower and "finder" in goal_lower:
            steps.append({"action": "launch_app", "app": "Finder", "description": "Open Finder"})

        elif "open" in goal_lower and ("settings" in goal_lower or "system preferences" in goal_lower):
            steps.append({"action": "launch_app", "app": "System Settings", "description": "Open System Settings"})

        elif "open" in goal_lower and "mail" in goal_lower:
            steps.append({"action": "launch_app", "app": "Mail", "description": "Open Mail"})

        elif "open" in goal_lower and "notes" in goal_lower:
            steps.append({"action": "launch_app", "app": "Notes", "description": "Open Notes"})

        elif "open" in goal_lower and "terminal" in goal_lower:
            steps.append({"action": "launch_app", "app": "Terminal", "description": "Open Terminal"})

        # ── URL Navigation ────────────────────────────────────────────
        elif "go to" in goal_lower or "navigate to" in goal_lower:
            # Extract URL/website
            url_match = None
            for word in goal_lower.split():
                if "." in word and len(word) > 3:
                    url_match = word
                    break
            if url_match:
                if not url_match.startswith("http"):
                    url_match = "https://" + url_match
                steps.append({"action": "hotkey", "keys": ["cmd", "l"], "description": "Focus address bar"})
                steps.append({"action": "type_text", "text": url_match, "description": f"Type URL: {url_match}"})
                steps.append({"action": "press_key", "key": "return", "description": "Navigate"})

        # ── Dark Mode Toggle ──────────────────────────────────────────
        elif "dark mode" in goal_lower or "dark theme" in goal_lower:
            steps.append({"action": "launch_app", "app": "System Settings", "description": "Open System Settings"})
            steps.append({"action": "wait", "seconds": 2, "description": "Wait for Settings"})
            steps.append({"action": "hotkey", "keys": ["cmd", "f"], "description": "Focus search"})
            steps.append({"action": "type_text", "text": "Appearance", "description": "Search for Appearance"})
            steps.append({"action": "wait", "seconds": 1, "description": "Wait for results"})
            steps.append({"action": "press_key", "key": "return", "description": "Select Appearance"})
            steps.append({"action": "wait", "seconds": 1, "description": "Wait for page"})
            steps.append({"action": "find_and_click", "text": "Dark", "description": "Click Dark mode option"})

        # ── Screenshot ────────────────────────────────────────────────
        elif "screenshot" in goal_lower or "screen capture" in goal_lower:
            steps.append({"action": "screenshot", "description": "Take screenshot"})

        # ── Email ─────────────────────────────────────────────────────
        elif "send email" in goal_lower or "send mail" in goal_lower:
            steps.append({"action": "launch_app", "app": "Mail", "description": "Open Mail"})
            steps.append({"action": "wait", "seconds": 2, "description": "Wait for Mail"})
            steps.append({"action": "hotkey", "keys": ["cmd", "n"], "description": "New message"})
            steps.append({"action": "wait", "seconds": 1, "description": "Wait for compose window"})
            # Try to find and fill fields
            steps.append({"action": "find_and_type", "find_text": "To", "type_text": "", "description": "Fill recipient"})
            steps.append({"action": "press_key", "key": "tab", "description": "Move to subject"})
            steps.append({"action": "find_and_type", "find_text": "Subject", "type_text": "", "description": "Fill subject"})

        # ── Terminal Commands ─────────────────────────────────────────
        elif "run" in goal_lower and ("command" in goal_lower or "terminal" in goal_lower):
            steps.append({"action": "launch_app", "app": "Terminal", "description": "Open Terminal"})
            steps.append({"action": "wait", "seconds": 1, "description": "Wait for Terminal"})
            # Extract command from goal
            cmd = goal_lower.split("run")[-1].strip()
            cmd = cmd.replace("command", "").replace("in terminal", "").strip()
            if cmd:
                steps.append({"action": "type_text", "text": cmd, "description": f"Type command: {cmd}"})
                steps.append({"action": "press_key", "key": "return", "description": "Execute command"})

        # ── Generic Click ─────────────────────────────────────────────
        elif "click" in goal_lower:
            # Extract what to click
            words = goal_lower.replace("click", "").strip().split()
            target = " ".join(words[:3])
            steps.append({"action": "find_and_click", "text": target, "description": f"Click '{target}'"})

        # ── Generic Type ──────────────────────────────────────────────
        elif "type" in goal_lower:
            # Extract what to type
            text_match = None
            if '"' in goal:
                text_match = goal.split('"')[1]
            elif "'" in goal:
                text_match = goal.split("'")[1]
            if text_match:
                steps.append({"action": "type_text", "text": text_match, "description": f"Type: {text_match}"})

        # ── Scroll ────────────────────────────────────────────────────
        elif "scroll" in goal_lower:
            direction = "down" if "down" in goal_lower else "up"
            amount = 5 if direction == "down" else -5
            steps.append({"action": "scroll", "amount": amount, "description": f"Scroll {direction}"})

        # ── Close / Quit ──────────────────────────────────────────────
        elif "close" in goal_lower or "quit" in goal_lower:
            app_name = None
            for app in ["Chrome", "Safari", "Mail", "Notes", "Finder", "Terminal"]:
                if app.lower() in goal_lower:
                    app_name = app
                    break
            if app_name:
                steps.append({"action": "quit_app", "app": app_name, "description": f"Quit {app_name}"})
            else:
                steps.append({"action": "hotkey", "keys": ["cmd", "q"], "description": "Quit current app"})

        # ── Window Management ─────────────────────────────────────────
        elif "minimize" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "m"], "description": "Minimize window"})
        elif "maximize" in goal_lower or "full screen" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "ctrl", "f"], "description": "Toggle full screen"})
        elif "new window" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "n"], "description": "New window"})
        elif "new tab" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "t"], "description": "New tab"})

        # ── Copy/Paste ────────────────────────────────────────────────
        elif "copy" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "c"], "description": "Copy"})
        elif "paste" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "v"], "description": "Paste"})
        elif "undo" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "z"], "description": "Undo"})
        elif "select all" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "a"], "description": "Select all"})
        elif "save" in goal_lower:
            steps.append({"action": "hotkey", "keys": ["cmd", "s"], "description": "Save"})

        # ── Disk Cleanup ──────────────────────────────────────────────
        elif "clean" in goal_lower or "free space" in goal_lower or "disk" in goal_lower:
            steps.append({"action": "system_action", "action_type": "disk_scan", "description": "Scan disk usage"})
            steps.append({"action": "report", "description": "Report findings and ask for confirmation"})

        # ── Fallback: Try to read screen and figure it out ────────────
        else:
            # For unknown goals, try to understand from screen
            steps.append({"action": "screenshot", "description": "Take screenshot to understand current state"})
            steps.append({"action": "analyze", "description": f"Analyze screen for: {goal}"})

        return steps

    def _execute_step(self, step: dict, perception, controller) -> dict:
        """Execute a single action step."""
        action = step["action"]

        try:
            if action == "launch_app":
                return controller.launch_app(step["app"])

            elif action == "quit_app":
                return controller.quit_app(step["app"])

            elif action == "hotkey":
                return controller.hotkey(*step["keys"])

            elif action == "press_key":
                return controller.press_key(step["key"])

            elif action == "type_text":
                return controller.type_string(step["text"])

            elif action == "screenshot":
                return perception.screenshot_full()

            elif action == "scroll":
                # Get screen center and scroll
                screen = perception.get_screen_size()
                cx = screen.get("width", 1440) // 2
                cy = screen.get("height", 900) // 2
                return controller.mouse_scroll(cx, cy, step.get("amount", 3))

            elif action == "find_and_click":
                text = step["text"]
                elem = perception.find_element(text)
                if elem:
                    return controller.mouse_click(elem["center_x"], elem["center_y"])
                else:
                    return {"status": "not_found", "text": text}

            elif action == "find_and_type":
                # Find field, click it, then type
                hint = step.get("find_text", "")
                elem = perception.find_field(hint)
                if elem:
                    controller.mouse_click(elem["x"], elem["y"])
                    time.sleep(0.3)
                    return controller.type_string(step.get("type_text", ""))
                return {"status": "field_not_found", "hint": hint}

            elif action == "wait":
                time.sleep(step.get("seconds", 1))
                return {"status": "waited", "seconds": step.get("seconds", 1)}

            elif action == "system_action":
                if step.get("action_type") == "disk_scan":
                    return self._action_disk_scan()
                return {"status": "unknown_action"}

            elif action == "analyze":
                info = perception.understand_screen()
                return {"status": "analyzed", "info": info}

            elif action == "report":
                return {"status": "needs_confirmation", "message": step.get("description", "")}

            else:
                return {"status": "unknown_action", "action": action}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _action_disk_scan(self) -> dict:
        """Scan disk usage."""
        try:
            from disk_cleaner import get_cleaner
            cleaner = get_cleaner()
            usage = cleaner.get_disk_usage()
            suggestions = cleaner.suggest_cleaning()
            return {"status": "scanned", "usage": usage, "suggestions": suggestions}
        except Exception as e:
            return {"error": str(e)}

    def stop(self):
        """Stop the current task."""
        self._running = False

    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "running": self._running,
            "goal": self._current_goal,
            "steps_taken": len(self._steps_taken),
            "log": self._log[-10:],  # Last 10 log entries
        }


# Quick-access actions for the relay
def quick_action(action: str, params: dict = None) -> dict:
    """Execute a quick system action without full goal planning."""
    from system_controller import get_controller
    from screen_perception import get_perception

    ctrl = get_controller()
    perception = get_perception()

    if action == "click":
        x, y = params.get("x", 0), params.get("y", 0)
        return ctrl.mouse_click(x, y)

    elif action == "type":
        return ctrl.type_string(params.get("text", ""))

    elif action == "hotkey":
        return ctrl.hotkey(*params.get("keys", []))

    elif action == "launch":
        return ctrl.launch_app(params.get("app", ""))

    elif action == "screenshot":
        return perception.screenshot_full()

    elif action == "find":
        text = params.get("text", "")
        elem = perception.find_element(text)
        if elem:
            return {"found": True, "element": elem}
        return {"found": False, "text": text}

    elif action == "find_click":
        text = params.get("text", "")
        elem = perception.find_element(text)
        if elem:
            ctrl.mouse_click(elem["center_x"], elem["center_y"])
            return {"clicked": True, "text": text, "position": [elem["center_x"], elem["center_y"]]}
        return {"clicked": False, "text": text, "error": "Not found on screen"}

    elif action == "see":
        return perception.understand_screen()

    elif action == "describe":
        return {"description": perception.describe_screen()}

    return {"error": f"Unknown quick action: {action}"}


# Singleton
_agent = None

def get_system_agent() -> SystemTaskAgent:
    global _agent
    if _agent is None:
        _agent = SystemTaskAgent()
    return _agent
