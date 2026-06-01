"""Workflow Engine — DAG-based workflow execution with branching, parallel steps, retry, and state persistence."""

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

WORKFLOW_TEMPLATES = {}


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
                 description: str = "", input_schema: dict = None,
                 output_schema: dict = None, tags: list = None):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.steps = steps
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}
        self.tags = tags or []

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
            "tags": self.tags,
        }


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
            "workflow_id": self.workflow.workflow_id,
            "workflow_name": self.workflow.name,
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
        }


class WorkflowEngine:
    """Executes DAG-based workflows with conditional branching, parallel steps, and retry."""

    def __init__(self):
        self._executions: dict[str, WorkflowExecution] = {}
        self._lock = threading.Lock()
        self._register_default_templates()

    def _register_default_templates(self):
        """Register built-in workflow templates."""
        WORKFLOW_TEMPLATES["business_setup"] = Workflow(
            "business_setup", "Start a Business",
            description="Full business setup workflow: registration, banking, website, tools",
            steps=[
                WorkflowStep("research", "groq_generate", {"prompt_template": "Research business ideas for: {query}"}),
                WorkflowStep("register", "open_url", {"url": "https://register.com"}, depends_on=["research"]),
                WorkflowStep("banking", "open_url", {"url": "https://bank.com"}, depends_on=["research"]),
                WorkflowStep("website", "groq_generate", {"prompt_template": "Create a business plan for: {query}"}, depends_on=["research"]),
                WorkflowStep("tools", "groq_generate", {"prompt_template": "List essential tools and software for: {query}"}, depends_on=["website"]),
                WorkflowStep("present", "present", {}, depends_on=["tools", "banking"]),
            ],
            tags=["business", "setup"]
        )

        WORKFLOW_TEMPLATES["trading_bot"] = Workflow(
            "trading_bot", "Automate Trading",
            description="Set up automated trading: platform, strategy, data feeds, execution",
            steps=[
                WorkflowStep("platform", "ask", {"question": "Which trading platform do you use? (MT4/MT5/TradingView/Binance/Other)"}, label="Choose Platform"),
                WorkflowStep("strategy", "groq_generate", {"prompt_template": "Create a trading strategy for: {platform}. User wants: {query}"}, depends_on=["platform"]),
                WorkflowStep("data", "open_url", {"url": "https://tradingview.com"}, depends_on=["strategy"]),
                WorkflowStep("automation", "type_keys", {}, depends_on=["strategy"],
                             condition="platform in ['MT4','MT5']"),
                WorkflowStep("paper_trade", "ask", {"question": "Start with paper trading first?"}, depends_on=["automation", "data"]),
                WorkflowStep("monitor", "groq_generate", {"prompt_template": "Create a monitoring dashboard plan for trading strategy"}, depends_on=["paper_trade"]),
            ],
            tags=["trading", "automation", "finance"]
        )

        WORKFLOW_TEMPLATES["onenote_homework"] = Workflow(
            "onenote_homework", "Do Homework in OneNote",
            description="Complete homework assignments directly in OneNote",
            steps=[
                WorkflowStep("subject", "ask", {"question": "What subject/homework is this for?"}, label="Subject"),
                WorkflowStep("content", "groq_generate", {"prompt_template": "Generate detailed homework content for: {query}. Subject: {subject}"},
                             depends_on=["subject"], label="Generate Content"),
                WorkflowStep("onenote_open", "run", {"params": "onenote"}, label="Open OneNote"),
                WorkflowStep("write", "onenote_write", {},
                             depends_on=["content", "onenote_open"], label="Write to OneNote"),
                WorkflowStep("verify", "ask", {"question": "Check the content in OneNote. Does it look correct?"},
                             depends_on=["write"], label="Verify"),
            ],
            tags=["education", "onenote", "homework"]
        )

        WORKFLOW_TEMPLATES["team_page_fix"] = Workflow(
            "team_page_fix", "Fix Team Page",
            description="Fix issues on a team/company page",
            steps=[
                WorkflowStep("url", "ask", {"question": "What's the URL of the team page?"}, label="Get URL"),
                WorkflowStep("issue", "ask", {"question": "What needs to be fixed?"}, label="Describe Issue"),
                WorkflowStep("open_page", "open_url", {"url": "{url}"}, depends_on=["url"]),
                WorkflowStep("plan_fix", "groq_generate",
                             {"prompt_template": "Plan the fix for: {issue} on page {url}"},
                             depends_on=["issue", "open_page"], label="Plan Fix"),
                WorkflowStep("implement", "groq_generate",
                             {"prompt_template": "Generate the code/content needed to fix: {issue}"},
                             depends_on=["plan_fix"], label="Generate Fix"),
                WorkflowStep("present", "present", {}, depends_on=["implement"], label="Show Results"),
            ],
            tags=["web", "development", "fix"]
        )

        WORKFLOW_TEMPLATES["research_project"] = Workflow(
            "research_project", "Research & Analyze",
            description="Deep research on any topic with analysis and report generation",
            steps=[
                WorkflowStep("topic", "ask", {"question": "What topic should I research?"}),
                WorkflowStep("depth", "ask", {"question": "How deep? Quick summary (5 min) or comprehensive (30 min)?"}),
                WorkflowStep("search", "search_google", {"query": "{topic} research 2026"},
                             depends_on=["topic"]),
                WorkflowStep("analyze", "groq_generate",
                             {"prompt_template": "Analyze and summarize key findings about: {topic}. Depth: {depth}"},
                             depends_on=["search"]),
                WorkflowStep("report", "groq_generate",
                             {"prompt_template": "Create a structured report on: {topic} with key findings, analysis, and recommendations"},
                             depends_on=["analyze"], label="Generate Report"),
                WorkflowStep("save", "type_keys", {},
                             depends_on=["report"],
                             condition="depth contains 'comprehensive'"),
                WorkflowStep("present", "present", {}, depends_on=["report", "save"]),
            ],
            tags=["research", "analysis", "report"]
        )

    def create_from_template(self, template_id: str, inputs: dict = None) -> WorkflowExecution:
        """Create a workflow execution from a named template."""
        template = WORKFLOW_TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Unknown workflow template: {template_id}")
        execution = WorkflowExecution(template, inputs)
        with self._lock:
            self._executions[execution.execution_id] = execution
        return execution

    def create_custom(self, workflow: Workflow, inputs: dict = None) -> WorkflowExecution:
        """Create a workflow execution from a custom workflow definition."""
        execution = WorkflowExecution(workflow, inputs)
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
        """Execute a single workflow step and return the result."""
        try:
            # Check condition
            if step.condition:
                try:
                    if not eval(step.condition, {"__builtins__": {}}, state):
                        return {"status": "skipped", "result": "Condition not met"}
                except:
                    pass

            # Resolve template variables in params
            resolved_params = {}
            for k, v in step.params.items():
                if isinstance(v, str):
                    try:
                        resolved_params[k] = v.format(**state)
                    except:
                        resolved_params[k] = v
                else:
                    resolved_params[k] = v

            # Execute based on action type
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
                result = groq_generate(prompt, task_id="__workflow__")
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
            else:
                # Try action system
                if action_executor:
                    try:
                        result = action_executor(action, str(resolved_params))
                    except:
                        result = f"Step {step.step_id}: {action}"

            # Handle ask results specially
            if isinstance(result, dict) and result.get("type") == "ask":
                return {"status": "waiting_input", "result": result}

            return {"status": "completed", "result": result or "Done."}

        except Exception as e:
            return {"status": "error", "result": str(e)}

    def advance(self, execution_id: str, user_input: str = None,
                action_executor: callable = None) -> dict:
        """Advance a workflow execution to the next step(s)."""
        execution = self.get_execution(execution_id)
        if not execution:
            return {"error": "Execution not found"}

        with execution._lock:
            wf = execution.workflow
            state = execution._state

            if user_input and execution.status == "waiting_input":
                # Store the input
                last_step = execution.current_step
                state["collected"][last_step] = user_input
                state[last_step] = user_input
                execution.status = "running"

            # Build adjacency: step -> list of dependants
            dependants = defaultdict(list)
            for s in wf.steps:
                for dep in s.depends_on:
                    dependants[dep].append(s.step_id)

            # Find which steps are ready to execute
            completed = set(execution.step_results.keys())
            ready = []
            for s in wf.steps:
                if s.step_id in completed:
                    continue
                if all(dep in completed for dep in s.depends_on):
                    # Check condition
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

            # Execute ready steps (parallel steps can run together)
            results = []
            for step in ready:
                execution.current_step = step.step_id
                execution.status = "running"

                # Try with retry
                last_error = None
                for attempt in range(step.retry_count + 1):
                    result = self.execute_step(step, {**state, **state.get("collected", {})}, action_executor)
                    if result["status"] != "error":
                        break
                    last_error = result["result"]
                    time.sleep(1)

                if result["status"] == "error" and step.fallback_action:
                    # Try fallback
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

            # Update progress
            total = len(wf.steps)
            done = len([s for s in wf.steps if s.step_id in execution.step_results])
            execution.progress = (done / total) * 100 if total else 100

            if execution.status != "waiting_input":
                # Check if fully done
                all_done = all(
                    s.step_id in execution.step_results
                    for s in wf.steps
                )
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
