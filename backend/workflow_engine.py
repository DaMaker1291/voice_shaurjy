"""Workflow Engine — AI generates workflows on the fly. No templates. Every workflow is unique to your request."""

import json
import os
import re
import time
import threading
from datetime import datetime
from collections import defaultdict
from groq_agent import generate as groq_generate

_WORKFLOW_DIR = os.path.join(os.path.dirname(__file__), ".workflow_data")
os.makedirs(_WORKFLOW_DIR, exist_ok=True)

AVAILABLE_ACTIONS = [
    "ask", "present", "groq_generate", "open_url", "search_google",
    "type_keys", "run", "onenote_write", "word_write", "excel_write",
    "wait", "screenshot", "send_keys", "click", "scroll",
]


# ── Workflow Definition ────────────────────────────────────────────

class WorkflowStep:
    def __init__(self, step_id: str, action: str, params: dict = None,
                 depends_on: list = None, condition: str = None,
                 retry_count: int = 2, fallback_action: str = None,
                 fallback_params: dict = None, timeout: int = 60,
                 label: str = "", parallel_group: str = None):
        self.step_id = step_id
        self.action = action
        self.params = params or {}
        self.depends_on = depends_on or []
        self.condition = condition
        self.retry_count = retry_count
        self.fallback_action = fallback_action
        self.fallback_params = fallback_params
        self.timeout = timeout
        self.label = label or step_id
        self.parallel_group = parallel_group


class Workflow:
    def __init__(self, workflow_id: str, name: str, steps: list[WorkflowStep],
                 description: str = ""):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.steps = steps

    def to_dict(self):
        return {
            "id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "id": s.step_id, "action": s.action,
                    "label": s.label, "depends_on": s.depends_on,
                    "condition": s.condition, "retry_count": s.retry_count,
                    "fallback_action": s.fallback_action,
                    "parallel_group": s.parallel_group,
                }
                for s in self.steps
            ],
        }


# ── AI Workflow Generation ─────────────────────────────────────────

def generate_workflow(user_input: str, context: dict = None) -> Workflow:
    """Use AI to dynamically generate a workflow for ANY user request."""
    context_str = ""
    if context:
        goals = context.get("active_goals", [])
        memory = context.get("memory_summary", "")
        if goals:
            context_str += "Active goals: " + "; ".join(g["goal"] for g in goals[:3]) + "\n"
        if memory:
            context_str += memory[:300] + "\n"

    prompt = f"""You are a workflow designer AI. Given a user request, design a multi-step workflow to accomplish it on Windows.

Available actions:
- ask: Ask user for information (params: question, field)
- present: Show final results to user
- groq_generate: Generate content using AI (params: prompt_template)
- open_url: Open a URL in browser (params: url)
- search_google: Search Google (params: query)
- type_keys: Type text into active window (params: text)
- run: Launch an app or run a command (params: params)
- onenote_write: Write content to OneNote (params: text)
- word_write: Open Word and write content (params: text)
- excel_write: Write data to Excel (params: data - 2D array)
- wait: Pause execution (params: seconds)
- screenshot: Take a screenshot (no params)
- send_keys: Send keyboard shortcut (params: keys)
- click: Click mouse (params: button)
- scroll: Scroll page (params: amount)

User request: {user_input}

{context_str}

Design a 3-8 step workflow. Each step should have:
1. A unique step id (no spaces, use underscores)
2. An action from the list above
3. Parameters for that action (use {"{collected.field}"} to reference values from previous steps)
4. depends_on: list of step ids this step depends on (empty for first steps)
5. A short label describing the step
6. retry_count (default 2)
7. Optionally a fallback_action if the main action might fail

IMPORTANT RULES:
- First step should ask the user for key info if needed
- Break the task into concrete, executable steps
- Use groq_generate with detailed prompts for AI-powered steps
- Use open_url/search_google for web research
- Use onenote_write/word_write/excel_write for document tasks
- End with a present step to show results
- Steps that don't depend on each other can run in parallel (share the same depends_on)

Output ONLY valid JSON. No other text.

Format:
{{
  "workflow_name": "Short name",
  "description": "Brief description",
  "steps": [
    {{
      "id": "step_name",
      "action": "ask",
      "params": {{"question": "What info do you need?", "field": "info_field"}},
      "depends_on": [],
      "label": "Get Info",
      "retry_count": 2
    }}
  ]
}}"""

    raw = groq_generate(prompt + " _RESPOND_ONLY_JSON", max_tokens=400)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        raise ValueError("AI failed to generate a valid workflow")

    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        raise ValueError("AI generated invalid JSON for workflow")

    steps = []
    for s in data.get("steps", []):
        step = WorkflowStep(
            step_id=s.get("id", f"step_{len(steps)}"),
            action=s.get("action", "groq_generate"),
            params=s.get("params", {}),
            depends_on=s.get("depends_on", []),
            condition=s.get("condition"),
            retry_count=s.get("retry_count", 2),
            fallback_action=s.get("fallback_action"),
            fallback_params=s.get("fallback_params"),
            label=s.get("label", s.get("id", "")),
            parallel_group=s.get("parallel_group"),
        )
        steps.append(step)

    wf_id = f"wf_{int(time.time())}_{os.urandom(4).hex()}"
    return Workflow(
        workflow_id=wf_id,
        name=data.get("workflow_name", "AI Workflow"),
        description=data.get("description", user_input),
        steps=steps,
    )


# ── Workflow Execution ─────────────────────────────────────────────

class WorkflowExecution:
    def __init__(self, workflow: Workflow, inputs: dict = None):
        self.workflow = workflow
        self.execution_id = f"wf_{int(time.time())}_{os.urandom(4).hex()}"
        self.inputs = inputs or {}
        self.outputs = {}
        self.step_results: dict[str, dict] = {}
        self.status = "pending"
        self.current_step = ""
        self.error = None
        self.started_at = datetime.now().isoformat()
        self.completed_at = None
        self.progress = 0.0
        self._lock = threading.Lock()
        self._state = {
            "inputs": self.inputs,
            "collected": {},
            "branch_decisions": {},
            "loop_counters": defaultdict(int),
        }

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "workflow_name": self.workflow.name,
            "workflow_description": self.workflow.description,
            "status": self.status,
            "current_step": self.current_step,
            "progress": self.progress,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "step_results": {
                sid: {
                    "status": r.get("status"),
                    "label": r.get("label", sid),
                    "result": str(r.get("result", ""))[:200],
                    "duration": r.get("duration", 0),
                }
                for sid, r in self.step_results.items()
            },
            "steps_planned": [
                {"id": s.step_id, "label": s.label, "action": s.action}
                for s in self.workflow.steps
            ],
        }


class WorkflowEngine:
    """Executes AI-generated workflows with DAG-based planning, parallel steps, and retry."""

    def __init__(self):
        self._executions: dict[str, WorkflowExecution] = {}
        self._lock = threading.Lock()

    def create_workflow(self, user_input: str, context: dict = None) -> WorkflowExecution:
        """AI-generates a workflow from a user request and creates an execution."""
        workflow = generate_workflow(user_input, context)
        execution = WorkflowExecution(workflow, context or {})
        with self._lock:
            self._executions[execution.execution_id] = execution
        return execution

    def get_execution(self, execution_id: str) -> WorkflowExecution:
        with self._lock:
            return self._executions.get(execution_id)

    def list_executions(self) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self._executions.values()]

    def execute_step(self, step: WorkflowStep, state: dict,
                     action_executor: callable = None) -> dict:
        try:
            if step.condition:
                try:
                    if not eval(step.condition, {"__builtins__": {}}, state):
                        return {"status": "skipped", "result": "Condition not met"}
                except:
                    pass

            resolved_params = {}
            for k, v in step.params.items():
                if isinstance(v, str):
                    try:
                        resolved_params[k] = v.format(**state)
                    except:
                        resolved_params[k] = v
                else:
                    resolved_params[k] = v

            result = None
            action = step.action

            if action == "ask":
                result = {
                    "type": "ask",
                    "question": resolved_params.get("question", "What?"),
                    "field": resolved_params.get("field", step.step_id),
                }
            elif action == "present":
                result = {"type": "present", "text": "All steps completed."}
            elif action == "groq_generate":
                prompt_template = resolved_params.get("prompt_template", "Generate: {query}")
                prompt = prompt_template.format(**state)
                result = groq_generate(prompt, max_tokens=300)
            elif action == "open_url":
                from actions import _ps
                url = resolved_params.get("url", "https://google.com")
                _ps(f'Start-Process "{url}"')
                result = f"Opened {url}"
            elif action == "search_google":
                from actions import _ps
                from urllib.parse import quote
                query = resolved_params.get("query", "")
                _ps(f'Start-Process "https://google.com/search?q={quote(query)}"')
                result = f"Searched: {query}"
            elif action == "type_keys":
                from actions import _ps
                text = resolved_params.get("text", resolved_params.get("params", ""))
                escaped = text[:200].replace('"', '\\"')
                _ps(f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{escaped}")')
                result = "Typed."
            elif action == "run":
                from actions import _ps
                params = resolved_params.get("params", "")
                _ps(f'Start-Process "{params}"')
                result = f"Launched {params}"
            elif action == "onenote_write":
                from app_automation import onenote_write_content
                text = resolved_params.get("text", state.get("content", ""))
                result = onenote_write_content(text)
            elif action == "word_write":
                from app_automation import word_new_document, word_type_text
                text = resolved_params.get("text", "")
                word_new_document()
                word_type_text(text)
                result = "Written."
            elif action == "excel_write":
                from app_automation import excel_new_workbook, excel_set_cells
                data = resolved_params.get("data", [["Data"]])
                excel_new_workbook()
                excel_set_cells(1, data)
                result = "Data written."
            elif action == "wait":
                seconds = int(resolved_params.get("seconds", 1))
                time.sleep(seconds)
                result = f"Waited {seconds}s."
            elif action == "screenshot":
                from app_automation import screenshot_with_ocr
                result = screenshot_with_ocr()
            elif action == "send_keys":
                from actions import _ps
                keys = resolved_params.get("keys", "{ENTER}")
                _ps(f'$k = New-Object -ComObject WScript.Shell; $k.SendKeys("{keys}")')
                result = f"Sent keys: {keys}"
            elif action == "click":
                from actions import _ps
                button = resolved_params.get("button", "left")
                b = "Left" if button == "left" else "Right"
                _ps(f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Mouse]::Click([System.Windows.Forms.MouseButtons]::{b})')
                result = f"Clicked {button}"
            elif action == "scroll":
                from actions import _ps
                amount = int(resolved_params.get("amount", 1))
                _ps(f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Mouse]::Wheel({amount})')
                result = f"Scrolled {amount}"
            else:
                if action_executor:
                    try:
                        result = action_executor(action, str(resolved_params))
                    except:
                        result = f"Step {step.step_id}: {action}"

            if isinstance(result, dict) and result.get("type") == "ask":
                return {"status": "waiting_input", "result": result}

            return {"status": "completed", "result": result or "Done."}

        except Exception as e:
            return {"status": "error", "result": str(e)}

    def advance(self, execution_id: str, user_input: str = None,
                action_executor: callable = None) -> dict:
        execution = self.get_execution(execution_id)
        if not execution:
            return {"error": "Execution not found"}

        with execution._lock:
            wf = execution.workflow
            state = execution._state

            if user_input and execution.status == "waiting_input":
                last_step = execution.current_step
                state["collected"][last_step] = user_input
                state[last_step] = user_input
                execution.status = "running"

            completed = set(execution.step_results.keys())
            ready = []
            for s in wf.steps:
                if s.step_id in completed:
                    continue
                if all(dep in completed for dep in s.depends_on):
                    if s.condition:
                        try:
                            if not eval(s.condition, {"__builtins__": {}}, {**state, **state.get("collected", {})}):
                                execution.step_results[s.step_id] = {"status": "skipped", "label": s.label}
                                continue
                        except:
                            pass
                    ready.append(s)

            if not ready:
                execution.status = "completed"
                execution.completed_at = datetime.now().isoformat()
                execution.progress = 100.0
                return {"type": "complete", "text": "Workflow complete!", "execution_id": execution_id}

            results = []
            for step in ready:
                execution.current_step = step.step_id
                execution.status = "running"

                for attempt in range(step.retry_count + 1):
                    result = self.execute_step(step, {**state, **state.get("collected", {})}, action_executor)
                    if result["status"] != "error":
                        break
                    time.sleep(1)

                if result["status"] == "error" and step.fallback_action:
                    fallback_step = WorkflowStep(
                        f"{step.step_id}_fallback", step.fallback_action,
                        step.fallback_params or step.params
                    )
                    result = self.execute_step(fallback_step, state, action_executor)

                execution.step_results[step.step_id] = {
                    "status": result["status"],
                    "result": result.get("result", ""),
                    "label": step.label,
                    "duration": 0,
                }

                if result["status"] == "waiting_input":
                    execution.status = "waiting_input"
                    results.append({
                        "type": "ask",
                        "question": result["result"].get("question", "What?"),
                        "field": step.step_id,
                        "step_label": step.label,
                        "execution_id": execution_id,
                    })
                    break
                else:
                    state[step.step_id] = result.get("result", "")
                    state["collected"][step.step_id] = result.get("result", "")
                    results.append({
                        "type": "notify",
                        "text": f"{step.label}: {str(result.get('result', ''))[:100]}",
                        "step_label": step.label,
                        "execution_id": execution_id,
                    })

            total = len(wf.steps)
            done = len([s for s in wf.steps if s.step_id in execution.step_results])
            execution.progress = (done / total) * 100 if total else 100

            if execution.status != "waiting_input":
                all_done = all(s.step_id in execution.step_results for s in wf.steps)
                if all_done:
                    execution.status = "completed"
                    execution.completed_at = datetime.now().isoformat()
                    execution.progress = 100.0
                    results.append({"type": "complete", "text": "Workflow complete!", "execution_id": execution_id})

            return {"type": "batch", "results": results, "execution_id": execution_id}


# Singleton
_ENGINE_INSTANCE = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> WorkflowEngine:
    global _ENGINE_INSTANCE
    with _ENGINE_LOCK:
        if _ENGINE_INSTANCE is None:
            _ENGINE_INSTANCE = WorkflowEngine()
        return _ENGINE_INSTANCE
