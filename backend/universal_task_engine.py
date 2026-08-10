"""
JARVIS Universal Task Engine — Execute ANY complex task autonomously.

Handles multi-step workflows like:
- "Write a 5-page essay about climate change and save it as Word doc"
- "Research the best laptops under $1000 and create a comparison spreadsheet"
- "Monitor my server every 5 minutes and alert me if it goes down"
- "Set up a full development environment with Node.js, Python, and Docker"
- "Compose and send a professional email to my boss about the project update"
- "Create a presentation with 10 slides about our Q3 financial results"
- "Find all duplicate files in my downloads folder and organize them"
- "Book a flight from NYC to London for next Friday and find hotels near Heathrow"
"""
import os
import sys
import re
import json
import time
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("universal_task")


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"         # 1 step: "what time is it"
    MODERATE = "moderate"     # 2-3 steps: "open chrome and go to google"
    COMPLEX = "complex"       # 4-10 steps: "research X, create spreadsheet, email results"
    AUTONOMOUS = "autonomous" # 10+ steps: "set up full dev environment"


@dataclass
class TaskStep:
    """A single step in a task plan."""
    action: str
    params: dict = field(default_factory=dict)
    description: str = ""
    status: str = "pending"  # pending, running, done, failed, skipped
    result: str = ""
    error: str = ""
    retries: int = 0
    max_retries: int = 2
    timeout: int = 120
    depends_on: list = field(default_factory=list)  # indices of steps this depends on


@dataclass
class TaskPlan:
    """A complete task plan."""
    goal: str
    steps: list = field(default_factory=list)
    reasoning: str = ""
    context: dict = field(default_factory=dict)
    created_at: float = 0.0
    complexity: TaskComplexity = TaskComplexity.MODERATE


class UniversalTaskEngine:
    """Execute any complex task using LLM planning + action registry + vision."""

    def __init__(self):
        self._action_cache = {}
        self._vision_cache = {}
        self._last_screenshot = None

    # ── Task Classification ────────────────────────────────────────────

    def classify_complexity(self, goal: str) -> TaskComplexity:
        """Classify task complexity from natural language."""
        goal_lower = goal.lower().strip()
        words = goal_lower.split()
        word_count = len(words)

        # Simple: single action, short
        if word_count <= 4:
            simple_verbs = {"what", "how", "who", "when", "where", "time", "date", "weather",
                            "battery", "volume", "brightness", "lock", "sleep", "restart"}
            if any(w in goal_lower for w in simple_verbs):
                return TaskComplexity.SIMPLE

        # Complex indicators
        complex_indicators = [
            " and then ", " after that ", " next ", " also ", " additionally ",
            " first.*then ", " before ", " while ", " during ",
            " create.*and ", " write.*and ", " find.*and ",
            " research ", " compare ", " analyze ", " summarize ",
            " set up ", " install ", " configure ", " deploy ",
            " monitor ", " track ", " schedule ", " automate ",
            " every ", " daily ", " weekly ", " hourly ",
        ]
        has_complex = any(re.search(ind, goal_lower) for ind in complex_indicators)

        # Multi-step action verbs
        multi_step_verbs = ["research", "compare", "analyze", "create", "write", "build",
                            "set up", "install", "configure", "deploy", "automate", "monitor",
                            "track", "organize", "backup", "migrate", "upgrade", "audit"]
        has_multi = any(v in goal_lower for v in multi_step_verbs)

        if has_complex or has_multi or word_count > 15:
            return TaskComplexity.COMPLEX
        if word_count > 8:
            return TaskComplexity.MODERATE
        return TaskComplexity.SIMPLE

    # ── LLM Plan Generation ────────────────────────────────────────────

    def generate_plan(self, goal: str, context: dict = None) -> TaskPlan:
        """Generate a step-by-step plan using LLM."""
        complexity = self.classify_complexity(goal)
        plan = TaskPlan(goal=goal, complexity=complexity, created_at=time.time())

        if complexity == TaskComplexity.SIMPLE:
            return self._simple_plan(goal, plan)
        elif complexity == TaskComplexity.MODERATE:
            return self._moderate_plan(goal, plan)
        else:
            return self._complex_plan(goal, plan, context)

    def _simple_plan(self, goal: str, plan: TaskPlan) -> TaskPlan:
        """Simple single-step plan."""
        # Map common simple goals to actions
        simple_map = {
            "what time": ("time", {}, "Get current time"),
            "what date": ("time", {}, "Get current date"),
            "current time": ("time", {}, "Get current time"),
            "battery": ("battery_status", {}, "Check battery status"),
            "volume": ("vol_level", {}, "Check volume level"),
            "brightness": ("brightness_set", {"level": -1}, "Check brightness"),
            "weather": ("weather", {}, "Get weather"),
            "lock": ("lock", {}, "Lock computer"),
            "sleep": ("sleep", {}, "Sleep computer"),
            "restart": ("restart", {}, "Restart computer"),
            "shutdown": ("shutdown", {}, "Shutdown computer"),
            "screenshot": ("screenshot", {}, "Take screenshot"),
            "clipboard": ("clipboard_show", {}, "Show clipboard"),
            "whoami": ("whoami", {}, "Get current user"),
            "ip": ("public_ip", {}, "Get public IP"),
            "network": ("network_info", {}, "Get network info"),
            "cpu": ("cpu_usage", {}, "Check CPU usage"),
            "memory": ("memory_info", {}, "Check memory"),
            "disk": ("disk_info", {}, "Check disk space"),
            "processes": ("process_list", {}, "List processes"),
            "wifi": ("wifi_list", {}, "List WiFi networks"),
            "bluetooth": ("bt_devices", {}, "List Bluetooth devices"),
            "help": ("help", {}, "Show help"),
        }
        for key, (action, params, desc) in simple_map.items():
            if key in goal.lower():
                plan.steps.append(TaskStep(action=action, params=params, description=desc))
                plan.reasoning = f"Simple action: {desc}"
                return plan

        # Default: single step
        plan.steps.append(TaskStep(
            action="run_shell",
            params={"command": goal},
            description=f"Execute: {goal}"
        ))
        plan.reasoning = "Simple execution"
        return plan

    def _moderate_plan(self, goal: str, plan: TaskPlan) -> TaskPlan:
        """Moderate 2-3 step plan."""
        goal_lower = goal.lower()

        # Common moderate patterns
        if "open" in goal_lower and ("go to" in goal_lower or "navigate" in goal_lower or ".com" in goal_lower):
            # "open chrome and go to google.com"
            app = "chrome"
            url = ""
            if "edge" in goal_lower: app = "edge"
            if "firefox" in goal_lower: app = "firefox"
            url_match = re.search(r'(?:go to|navigate to|open)\s+(\S+\.(?:com|org|net|io))', goal_lower)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = "https://" + url
            plan.steps.append(TaskStep(action="wsl_launch", params={"app": app, "url": url},
                                       description=f"Open {app} with {url}"))
            plan.reasoning = "Browser + URL pattern"
            return plan

        if "search" in goal_lower and ("google" in goal_lower or "for" in goal_lower):
            query = re.sub(r'^(?:search|look up|find|google)\s+(?:for\s+|on\s+google\s+)?', '', goal_lower).strip()
            plan.steps.append(TaskStep(action="web_search", params={"query": query},
                                       description=f"Search for: {query}"))
            plan.reasoning = "Search pattern"
            return plan

        if "email" in goal_lower or "send" in goal_lower and "mail" in goal_lower:
            plan.steps.append(TaskStep(action="compose_email", params={"goal": goal},
                                       description="Compose email"))
            plan.steps.append(TaskStep(action="send_email_smtp", params={"goal": goal},
                                       description="Send email", depends_on=[0]))
            plan.reasoning = "Email composition pattern"
            return plan

        if "write" in goal_lower and ("file" in goal_lower or "document" in goal_lower or "save" in goal_lower):
            content = re.sub(r'^(?:write|create|make)\s+(?:a\s+)?(?:new\s+)?', '', goal_lower).strip()
            filename = re.search(r'(?:save|as|to)\s+(\S+)', goal_lower)
            fname = filename.group(1) if filename else "output.txt"
            plan.steps.append(TaskStep(action="write_file", params={"path": fname, "content": content},
                                       description=f"Write file: {fname}"))
            plan.reasoning = "File creation pattern"
            return plan

        if "create" in goal_lower and "folder" in goal_lower:
            folder = re.sub(r'^(?:create|make)\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)\s*(?:called|named)?\s*', '', goal_lower).strip()
            plan.steps.append(TaskStep(action="create_directory", params={"path": folder},
                                       description=f"Create folder: {folder}"))
            plan.reasoning = "Folder creation pattern"
            return plan

        # Default: use LLM
        return self._llm_plan(goal, plan)

    def _complex_plan(self, goal: str, plan: TaskPlan, context: dict = None) -> TaskPlan:
        """Complex multi-step plan via LLM."""
        return self._llm_plan(goal, plan, context)

    def _llm_plan(self, goal: str, plan: TaskPlan, context: dict = None) -> TaskPlan:
        """Generate plan using LLM (Groq cloud or local)."""
        # Build available actions description
        actions_desc = self._get_actions_description()

        prompt = f"""You are JARVIS — an autonomous computer-use agent with FULL desktop access.
Generate a step-by-step plan to accomplish this goal: "{goal}"

AVAILABLE ACTIONS (use ONLY these action names):
{actions_desc}

PLANNING RULES:
1. Use MINIMAL steps — combine related actions when possible
2. Each step must use a VALID action name from the list above
3. For web tasks: prefer headless tools (web_search, web_scrape, http_get) over browser automation
4. For file operations: use full Windows paths (C:\\Users\\username\\...)
5. For app operations: use wsl_launch for VDI apps, open_app for Windows apps
6. Output ONLY valid JSON: {{ "steps": [...], "reasoning": "..." }}

Each step must have:
- "action": action name from the list
- "params": {{}} with required parameters
- "description": what this step does

Example:
{{ "steps": [
    {{"action": "web_search", "params": {{"query": "best laptops under 1000"}}, "description": "Search for laptops"}},
    {{"action": "web_scrape", "params": {{"url": "{{scrape_result}}"}}, "description": "Scrape results"}},
    {{"action": "write_file", "params": {{"path": "C:\\\\Users\\\\supro\\\\Desktop\\\\laptops.txt", "content": "{{scrape_result}}"}}, "description": "Save results"}}
], "reasoning": "Research and save laptop comparison" }}

JSON:"""

        # Try Groq first
        plan_data = None
        try:
            plan_data = self._call_llm(prompt)
        except Exception as e:
            logger.warning(f"LLM plan failed: {e}")

        if plan_data and isinstance(plan_data, dict) and "steps" in plan_data:
            for step_data in plan_data["steps"]:
                plan.steps.append(TaskStep(
                    action=step_data.get("action", "unknown"),
                    params=step_data.get("params", {}),
                    description=step_data.get("description", ""),
                ))
            plan.reasoning = plan_data.get("reasoning", "LLM-generated plan")
            return plan

        # Fallback: pattern-based plan
        return self._pattern_fallback(goal, plan)

    def _call_llm(self, prompt: str) -> dict:
        """Call LLM (Groq API) and parse JSON response."""
        try:
            from groq_agent import generate
            response = generate(prompt, user_id="task_engine", max_tokens=1500, temperature=0.1)
            if response:
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Groq LLM failed: {e}")

        # Fallback: try local model
        try:
            from local_model import generate_local
            response = generate_local(prompt, max_tokens=1500)
            if response:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
        except Exception:
            pass

        return None

    def _get_actions_description(self) -> str:
        """Get formatted list of available actions for LLM prompt."""
        actions = [
            ("wsl_launch", "app, url — Launch app/URL in WSL VDI DISPLAY=:99"),
            ("web_search", "query — Search the web"),
            ("web_scrape", "url — Scrape webpage content"),
            ("http_get", "url — Make HTTP GET request"),
            ("http_post", "url, data — Make HTTP POST request"),
            ("read_file", "path — Read file contents"),
            ("write_file", "path, content — Write content to file"),
            ("create_directory", "path — Create directory"),
            ("list_directory", "path — List directory contents"),
            ("search_files", "path, pattern — Search for files"),
            ("run_shell", "command — Execute shell command"),
            ("run_python", "code — Execute Python code"),
            ("open_app", "app — Open Windows application"),
            ("screenshot", " — Take screenshot"),
            ("ocr_screen", " — Read text from screen"),
            ("mouse_click", "x, y — Click at coordinates"),
            ("type_text", "text — Type text"),
            ("hotkey", "keys — Press hotkey combination"),
            ("send_keys", "keys — Send keystrokes"),
            ("clipboard_copy", "text — Copy to clipboard"),
            ("clipboard_paste", " — Paste from clipboard"),
            ("send_email_smtp", "to, subject, body — Send email"),
            ("compose_email", "to, subject, body — Compose email draft"),
            ("send_whatsapp_message", "contact, message — Send WhatsApp message"),
            ("search_youtube", "query — Search YouTube"),
            ("search_wiki", "query — Search Wikipedia"),
            ("search_news", "query — Search news"),
            ("weather", " — Get weather"),
            ("time", " — Get current time"),
            ("timer", "seconds — Set timer"),
            ("alarm", "time — Set alarm"),
            ("cpu_usage", " — Check CPU usage"),
            ("memory_info", " — Check memory"),
            ("disk_info", " — Check disk space"),
            ("network_info", " — Get network info"),
            ("battery_status", " — Check battery"),
            ("process_list", " — List processes"),
            ("process_kill", "pid — Kill process"),
            ("volume_control", "action, level — Control volume"),
            ("brightness_control", "level — Control brightness"),
            ("media_control", "action — Control media playback"),
            ("lock", " — Lock computer"),
            ("shutdown", " — Shutdown computer"),
            ("restart", " — Restart computer"),
            ("sleep", " — Sleep computer"),
            ("window_snap", "direction — Snap window"),
            ("show_desktop", " — Show desktop"),
            ("alt_tab", " — Switch windows"),
            ("focus_window", "title — Focus window by title"),
            ("close_window", "title — Close window"),
            ("wifi_control", "action — WiFi on/off/scan"),
            ("bluetooth_control", "action — Bluetooth on/off"),
            ("vpn_control", "action — VPN connect/disconnect"),
            ("firewall_control", "action — Firewall on/off"),
            ("service_control", "action, name — Service start/stop"),
            ("reg_read", "path — Read registry"),
            ("reg_write", "path, value — Write registry"),
            ("env_get", "name — Get env variable"),
            ("env_set", "name, value — Set env variable"),
            ("install_software", "name — Install software"),
            ("uninstall_software", "name — Uninstall software"),
            ("download_file", "url, path — Download file"),
            ("compress_zip", "paths, output — Create zip"),
            ("extract_zip", "path, output — Extract zip"),
            ("file_hash", "path — Get file hash"),
            ("convert_file", "input, output, format — Convert file format"),
            ("read_pdf", "path — Read PDF"),
            ("read_image", "path — Read image with OCR"),
            ("speak_text", "text — Text to speech"),
            ("send_notification", "title, message — Send notification"),
            ("calendar_add", "title, date — Add calendar event"),
            ("calendar_events", " — List calendar events"),
            ("schedule_task", "name, command, time — Schedule task"),
        ]
        return "\n".join(f"- {name}: {desc}" for name, desc in actions)

    def _pattern_fallback(self, goal: str, plan: TaskPlan) -> TaskPlan:
        """Fallback plan generation using pattern matching."""
        goal_lower = goal.lower()

        # Research + save pattern
        if "research" in goal_lower or "compare" in goal_lower:
            query = re.sub(r'^(?:research|compare|find|look up)\s+', '', goal_lower).strip()
            plan.steps = [
                TaskStep(action="web_search", params={"query": query}, description=f"Search: {query}"),
                TaskStep(action="web_scrape", params={"url": "{scrape_result}"}, description="Scrape results"),
                TaskStep(action="write_file", params={"path": "C:\\Users\\supro\\Desktop\\research.txt", "content": "{scrape_result}"}, description="Save results"),
            ]
            plan.reasoning = "Research and save pattern"
            return plan

        # Create document pattern
        if "create" in goal_lower and any(w in goal_lower for w in ["document", "file", "report", "essay", "article"]):
            topic = re.sub(r'^(?:create|write|make)\s+(?:a\s+)?(?:new\s+)?', '', goal_lower).strip()
            plan.steps = [
                TaskStep(action="web_search", params={"query": topic}, description=f"Research: {topic}"),
                TaskStep(action="write_file", params={"path": "C:\\Users\\supro\\Desktop\\document.txt", "content": "{scrape_result}"}, description="Create document"),
            ]
            plan.reasoning = "Document creation pattern"
            return plan

        # Email pattern
        if "email" in goal_lower or "send mail" in goal_lower:
            plan.steps = [
                TaskStep(action="compose_email", params={"goal": goal}, description="Compose email"),
                TaskStep(action="send_email_smtp", params={"goal": goal}, description="Send email"),
            ]
            plan.reasoning = "Email pattern"
            return plan

        # Install/setup pattern
        if "install" in goal_lower or "set up" in goal_lower or "setup" in goal_lower:
            software = re.sub(r'^(?:install|set up|setup)\s+(?:a\s+)?(?:new\s+)?', '', goal_lower).strip()
            plan.steps = [
                TaskStep(action="install_software", params={"name": software}, description=f"Install {software}"),
            ]
            plan.reasoning = "Installation pattern"
            return plan

        # Default: single step
        plan.steps = [
            TaskStep(action="run_shell", params={"command": goal}, description=f"Execute: {goal}"),
        ]
        plan.reasoning = "Default execution"
        return plan


# ── Task Executor ─────────────────────────────────────────────────────

class TaskExecutor:
    """Execute a task plan with error recovery and vision verification."""

    def __init__(self):
        from computer_use import ComputerUseAgent
        self.agent = ComputerUseAgent()
        self.engine = UniversalTaskEngine()

    async def execute_task(self, goal: str, safety: str = "full_auto") -> dict:
        """Execute any complex task end-to-end."""
        start_time = time.time()

        # Generate plan
        plan = self.engine.generate_plan(goal)

        # Execute steps
        results = []
        for i, step in enumerate(plan.steps):
            step.status = "running"
            step_result = await self._execute_step_with_retry(step, plan, i)
            results.append(step_result)

            # Check if step failed critically
            if step.status == "failed" and not step_result.get("recoverable", False):
                return {
                    "success": False,
                    "goal": goal,
                    "error": f"Step {i+1} failed: {step.error}",
                    "steps_done": i,
                    "steps_total": len(plan.steps),
                    "results": results,
                    "duration_seconds": time.time() - start_time,
                }

        duration = time.time() - start_time
        return {
            "success": True,
            "goal": goal,
            "steps_done": len(plan.steps),
            "steps_total": len(plan.steps),
            "results": results,
            "reasoning": plan.reasoning,
            "duration_seconds": round(duration, 2),
        }

    async def _execute_step_with_retry(self, step: TaskStep, plan: TaskPlan, index: int) -> dict:
        """Execute a step with automatic retry on failure."""
        while step.retries <= step.max_retries:
            try:
                result = await self._execute_single_step(step, plan, index)
                step.status = "done"
                step.result = str(result)
                return {"success": True, "step": index, "action": step.action, "result": result}
            except Exception as e:
                step.retries += 1
                step.error = str(e)
                logger.warning(f"Step {index} failed (attempt {step.retries}): {e}")

                if step.retries > step.max_retries:
                    step.status = "failed"
                    return {"success": False, "step": index, "action": step.action, "error": str(e), "recoverable": True}

                # Wait before retry
                await asyncio.sleep(1)

        return {"success": False, "step": index, "action": step.action, "error": "Max retries exceeded"}

    async def _execute_single_step(self, step: TaskStep, plan: TaskPlan, index: int) -> str:
        """Execute a single step using the agent's action registry."""
        # Resolve placeholders from previous step results
        resolved_params = self._resolve_placeholders(step.params, plan, index)

        # Use the agent's execute_step
        from computer_use import ExecutionStep, ActionResult
        exec_step = ExecutionStep(
            action=step.action,
            params=resolved_params,
            description=step.description,
        )

        result = await self.agent._execute_step(exec_step)

        if isinstance(result, ActionResult):
            return result.output
        elif isinstance(result, dict):
            return result.get("output", result.get("result", str(result)))
        return str(result)

    def _resolve_placeholders(self, params: dict, plan: TaskPlan, current_index: int) -> dict:
        """Resolve {scrape_result}, {step_N_result} placeholders."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                # {scrape_result} → last step's scrape output
                if "{scrape_result}" in value:
                    for j in range(current_index - 1, -1, -1):
                        prev_step = plan.steps[j]
                        if prev_step.result and prev_step.status == "done":
                            value = value.replace("{scrape_result}", prev_step.result)
                            break

                # {step_N_result} → specific step's result
                step_ref = re.search(r'\{step_(\d+)_result\}', value)
                if step_ref:
                    ref_idx = int(step_ref.group(1))
                    if 0 <= ref_idx < len(plan.steps) and plan.steps[ref_idx].result:
                        value = value.replace(step_ref.group(0), plan.steps[ref_idx].result)

            resolved[key] = value
        return resolved


# ── Convenience Functions ─────────────────────────────────────────────

async def execute_complex_task(goal: str, safety: str = "full_auto") -> dict:
    """Execute any complex task autonomously."""
    executor = TaskExecutor()
    return await executor.execute_task(goal, safety)


def plan_task(goal: str) -> dict:
    """Generate a plan without executing it."""
    engine = UniversalTaskEngine()
    plan = engine.generate_plan(goal)
    return {
        "goal": goal,
        "complexity": plan.complexity.value,
        "steps": [
            {"action": s.action, "params": s.params, "description": s.description}
            for s in plan.steps
        ],
        "reasoning": plan.reasoning,
        "step_count": len(plan.steps),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[TASK] %(message)s")
    import sys
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "open chrome and go to google.com"
    engine = UniversalTaskEngine()
    plan = engine.generate_plan(goal)
    print(f"\nGoal: {goal}")
    print(f"Complexity: {plan.complexity.value}")
    print(f"Steps: {len(plan.steps)}")
    print(f"Reasoning: {plan.reasoning}")
    for i, step in enumerate(plan.steps):
        print(f"  {i+1}. [{step.action}] {step.description} {step.params}")
