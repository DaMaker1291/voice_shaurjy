"""JARVIS Workspace Agent - Autonomous Observe/Act/Verify Loop.

The agent operates independently inside a workspace, executing missions
while the user's real desktop remains untouched. It follows a ReAct pattern:
OBSERVE the workspace state, PLAN the next action, ACT on the workspace,
VERIFY the result, and loop until the mission is complete.

Capability Resolution Hierarchy (Vision Point #5):
  API → CLI → GUI
If an app has a native API, use it. If it has a CLI, use that.
Only fall back to GUI (mouse/keyboard) when nothing else exists.
"""

import os
import sys
import json
import time
import base64
import logging
import threading
import subprocess
from typing import Optional, Dict, List, Callable, Tuple
from dataclasses import dataclass, field
from mission_state import get_mission_state, validate_action

log = logging.getLogger("workspace_agent")

HIGH_RISK_ACTIONS = {
    "execute_system_command", "install_software", "delete_files",
    "send_email", "send_message", "purchase", "payment",
    "modify_system_settings", "access_financial", "transfer_funds",
    "run_admin_command", "modify_registry", "shutdown_system",
}

CAPABILITY_REGISTRY: Dict[str, Dict[str, any]] = {
    "chrome": {
        "api": {"available": True, "method": "cdp", "port": 9222},
        "cli": {"available": True, "commands": ["google-chrome", "chrome"]},
        "gui": {"available": True},
    },
    "git": {
        "api": {"available": False},
        "cli": {"available": True, "commands": ["git"]},
        "gui": {"available": True},
    },
    "vscode": {
        "api": {"available": True, "method": "cli_ext", "commands": ["code"]},
        "cli": {"available": True, "commands": ["code"]},
        "gui": {"available": True},
    },
    "terminal": {
        "api": {"available": True, "method": "subprocess"},
        "cli": {"available": True, "commands": ["cmd.exe", "bash"]},
        "gui": {"available": True},
    },
    "browser": {
        "api": {"available": True, "method": "cdp", "port": 9222},
        "cli": {"available": True, "commands": ["google-chrome", "chrome"]},
        "gui": {"available": True},
    },
    "files": {
        "api": {"available": True, "method": "os_module"},
        "cli": {"available": True, "commands": ["cmd.exe", "bash"]},
        "gui": {"available": True},
    },
}


@dataclass
class AgentStep:
    number: int
    action: str
    description: str
    params: dict
    status: str = "pending"
    result: str = ""
    error: str = ""
    timestamp: float = 0
    requires_approval: bool = False
    screenshot_before: str = ""
    screenshot_after: str = ""

    def to_dict(self):
        return {
            "number": self.number, "action": self.action,
            "description": self.description, "params": self.params,
            "status": self.status, "result": self.result, "error": self.error,
            "timestamp": self.timestamp, "requires_approval": self.requires_approval,
        }


@dataclass
class AgentMission:
    id: str
    objective: str
    workspace_id: str
    status: str = "planning"
    steps: List[AgentStep] = field(default_factory=list)
    current_step: int = 0
    artifacts: List[str] = field(default_factory=list)
    created_at: float = 0
    started_at: float = 0
    completed_at: float = 0
    error: str = ""
    progress: float = 0.0
    current_action: str = ""

    def to_dict(self):
        return {
            "id": self.id, "objective": self.objective,
            "workspace_id": self.workspace_id, "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step, "artifacts": self.artifacts,
            "created_at": self.created_at, "started_at": self.started_at,
            "completed_at": self.completed_at, "error": self.error,
            "progress": self.progress, "current_action": self.current_action,
        }


class WorkspaceAgent:
    """Autonomous agent that operates inside a JARVIS workspace.

    Uses the existing computer_use.py action registry and LLM planning
    but executes against the workspace display, not the user's real desktop.

    Capability resolver picks the best execution method:
      1. API (CDP for browser, subprocess for terminal)
      2. CLI (git, code, etc.)
      3. GUI (PyAutoGUI/Win32 input — last resort)
    """

    def __init__(self):
        self._missions: Dict[str, AgentMission] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._paused: Dict[str, bool] = {}
        self._stopped: Dict[str, bool] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._learned_procedures: Dict[str, dict] = {}
        self._load_procedures()

    def _load_procedures(self):
        proc_path = os.path.join(os.path.dirname(__file__), ".agent_procedures.json")
        if os.path.exists(proc_path):
            try:
                with open(proc_path, "r") as f:
                    self._learned_procedures = json.load(f)
            except Exception:
                pass

    def _save_procedures(self):
        proc_path = os.path.join(os.path.dirname(__file__), ".agent_procedures.json")
        try:
            with open(proc_path, "w") as f:
                json.dump(self._learned_procedures, f, indent=2)
        except Exception:
            pass

    def resolve_capability(self, app_name: str) -> Tuple[str, dict]:
        """Pick the best execution method for an application.
        Returns (method_type, config_dict).
        """
        app_key = app_name.lower()
        caps = CAPABILITY_REGISTRY.get(app_name.lower(), {})
        if not caps:
            for key in CAPABILITY_REGISTRY:
                if key in app_key or app_key in key:
                    caps = CAPABILITY_REGISTRY[key]
                    break
        if not caps:
            return ("gui", {})
        if caps.get("api", {}).get("available"):
            return ("api", caps["api"])
        if caps.get("cli", {}).get("available"):
            return ("cli", caps["cli"])
        return ("gui", caps.get("gui", {}))

    def on_event(self, mission_id: str, callback: Callable):
        with self._lock:
            if mission_id not in self._callbacks:
                self._callbacks[mission_id] = []
            self._callbacks[mission_id].append(callback)

    def _emit(self, mission_id: str, event_type: str, data: dict):
        with self._lock:
            callbacks = self._callbacks.get(mission_id, [])
        for cb in callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass

    def create_mission(self, objective: str, workspace_id: str) -> AgentMission:
        import uuid
        mission_id = str(uuid.uuid4())[:8]
        state = get_mission_state()
        state.create(mission_id, objective, workspace_id)

        mission = AgentMission(
            id=mission_id,
            objective=objective,
            workspace_id=workspace_id,
            created_at=time.time(),
        )
        with self._lock:
            self._missions[mission.id] = mission
        log.info(f"[AGENT] Mission created: {mission.id} - {objective[:60]}")
        return mission

    def plan_mission(self, mission_id: str) -> dict:
        with self._lock:
            mission = self._missions.get(mission_id)
        if not mission:
            return {"ok": False, "error": "Mission not found"}

        state = get_mission_state()
        state.transition(mission_id, "planning")
        mission.status = "planning"
        self._emit(mission_id, "status", {"status": "planning"})

        try:
            steps = self._llm_plan(mission)
            mission.steps = steps
            mission.status = "ready"
            state.set_steps(mission_id, [s.to_dict() for s in steps])
            state.transition(mission_id, "executing")
            self._emit(mission_id, "planned", {"steps": len(steps)})
            return {"ok": True, "steps": [s.to_dict() for s in steps]}
        except Exception as e:
            state.transition(mission_id, "failure", str(e))
            mission.status = "failed"
            mission.error = str(e)
            self._emit(mission_id, "error", {"error": str(e)})
            return {"ok": False, "error": str(e)}

    def _llm_plan(self, mission: AgentMission) -> List[AgentStep]:
        """Use LLM to decompose the objective into workspace actions with context."""
        try:
            from groq_agent import call as groq_call
            from workspace_replicator import get_workspace_replicator
            replicator = get_workspace_replicator()
            profile = replicator.get_profile_dict()
            installed = [a.get("name", "") for a in profile.get("installed_apps", [])[:30]]
            browsers = [b.get("browser", "") for b in profile.get("browser_profiles", [])]
            dev_tools = [t.get("name", "") for t in profile.get("dev_tools", [])]

            prompt = f"""You are JARVIS, an autonomous workspace agent. Decompose this objective into concrete steps.

OBJECTIVE: {mission.objective}

WORKSPACE ENVIRONMENT:
- Installed applications: {', '.join(installed) if installed else 'Standard apps available'}
- Browsers: {', '.join(browsers) if browsers else 'Chrome, Firefox'}
- Dev tools: {', '.join(dev_tools) if dev_tools else 'Python, Node.js, Git'}
- OS: Windows (use Win32 APIs for input)

You MUST return a JSON array. Each element is ONE step. Use ONLY these action schemas:

{{
  "action": "launch_app",
  "params": {{"name": "app name", "command": ["full", "path", "args"]}},
  "description": "Launch the app"
}}

{{
  "action": "click",
  "params": {{"x": 960, "y": 540, "button": 1}},
  "description": "Click at coordinates"
}}

{{
  "action": "type_text",
  "params": {{"text": "text to type"}},
  "description": "Type text"
}}

{{
  "action": "press_key",
  "params": {{"key": "Return"}},
  "description": "Press key"
}}

{{
  "action": "navigate_web",
  "params": {{"url": "https://example.com"}},
  "description": "Navigate to URL"
}}

{{
  "action": "web_search",
  "params": {{"query": "search terms"}},
  "description": "Search the web"
}}

{{
  "action": "web_scrape",
  "params": {{"url": "https://example.com"}},
  "description": "Extract page content"
}}

{{
  "action": "read_file",
  "params": {{"path": "/absolute/path"}},
  "description": "Read file"
}}

{{
  "action": "write_file",
  "params": {{"path": "/absolute/path", "content": "file content"}},
  "description": "Write file"
}}

{{
  "action": "create_directory",
  "params": {{"path": "/absolute/path"}},
  "description": "Create directory"
}}

{{
  "action": "run_command",
  "params": {{"cmd": "shell command"}},
  "description": "Run command"
}}

{{
  "action": "screenshot",
  "params": {{}},
  "description": "Take screenshot"
}}

{{
  "action": "wait",
  "params": {{"seconds": 2}},
  "description": "Wait"
}}

RULES:
1. First step MUST be "screenshot" to see the current state
2. Each step does exactly ONE thing
3. Add "screenshot" after important actions to verify
4. Use absolute paths for file operations
5. Coordinate system: 1920x1080 virtual display
6. Return ONLY the JSON array, no markdown, no explanation"""

            response = groq_call([
                {"role": "system", "content": "You are a precise workspace automation planner. Return only JSON."},
                {"role": "user", "content": prompt}
            ])
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            raw_steps = self._parse_json_robust(text)
            if raw_steps is None:
                raise ValueError(f"Could not parse LLM response as JSON")
            steps = []
            for i, s in enumerate(raw_steps):
                step = AgentStep(
                    number=i + 1,
                    action=s.get("action", "unknown"),
                    description=s.get("description", ""),
                    params=s.get("params", {}),
                    requires_approval=s.get("action", "") in HIGH_RISK_ACTIONS,
                )
                steps.append(step)
            return steps
        except Exception as e:
            log.warning(f"[AGENT] LLM planning failed, using fallback: {e}")
            return self._fallback_plan(mission)

    def _parse_json_robust(self, text: str) -> list:
        """Parse JSON from LLM response, handling common formatting errors."""
        import re
        text = text.strip()
        # Try direct parse first
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "steps" in result:
                return result["steps"]
            return None
        except json.JSONDecodeError:
            pass
        # Try to extract JSON array from text
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Try to fix unterminated strings - find last complete object
        try:
            # Find all complete JSON objects
            objects = []
            decoder = json.JSONDecoder()
            idx = 0
            text_to_parse = text
            # Find the array start
            array_start = text_to_parse.find('[')
            if array_start >= 0:
                text_to_parse = text_to_parse[array_start:]
            while idx < len(text_to_parse):
                try:
                    obj, end = decoder.raw_decode(text_to_parse, idx)
                    objects.append(obj)
                    idx = end
                    # Skip whitespace and commas
                    while idx < len(text_to_parse) and text_to_parse[idx] in ' \t\n\r,':
                        idx += 1
                except json.JSONDecodeError:
                    idx += 1
            if objects:
                return objects
        except Exception:
            pass
        return None

    def _fallback_plan(self, mission: AgentMission) -> List[AgentStep]:
        """Fallback plan when LLM is unavailable — generates real executable steps."""
        import sys
        ws_dir = os.path.expanduser(f"~/.jarvis/workspaces/{mission.workspace_id}/files")
        obj = mission.objective.lower()
        steps = []

        steps.append(AgentStep(number=1, action="create_directory",
            description="Create workspace output directory",
            params={"path": ws_dir}))

        if any(w in obj for w in ["website", "web", "html", "page", "site"]):
            steps.append(AgentStep(number=2, action="write_file",
                description="Create HTML file",
                params={"path": os.path.join(ws_dir, "index.html"),
                        "content": "<!DOCTYPE html>\n<html lang='en'>\n<head>\n<meta charset='UTF-8'>\n<meta name='viewport' content='width=device-width, initial-scale=1.0'>\n<title>My Website</title>\n<style>\n* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }\n.hero { text-align: center; padding: 60px 20px; }\nh1 { font-size: 3rem; font-weight: 300; letter-spacing: -0.02em; margin-bottom: 16px; background: linear-gradient(135deg, #00FF66, #00B4D8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }\np { font-size: 1.2rem; color: #888; max-width: 500px; line-height: 1.6; }\n</style>\n</head>\n<body>\n<div class='hero'>\n<h1>Hello World</h1>\n<p>This website was created by JARVIS — an autonomous AI workspace agent.</p>\n</div>\n</body>\n</html>"}))
            steps.append(AgentStep(number=3, action="write_file",
                description="Create CSS stylesheet",
                params={"path": os.path.join(ws_dir, "style.css"),
                        "content": "body { background: #0a0a0a; color: #e0e0e0; }"}))
            steps.append(AgentStep(number=4, action="write_file",
                description="Create JavaScript file",
                params={"path": os.path.join(ws_dir, "script.js"),
                        "content": "console.log('JARVIS website created');\ndocument.addEventListener('DOMContentLoaded', () => { console.log('Ready'); });"}))
            steps.append(AgentStep(number=5, action="run_command",
                description="Verify files were created",
                params={"cmd": f'dir "{ws_dir}"' if sys.platform == "win32" else f'ls "{ws_dir}"'}))
        elif any(w in obj for w in ["research", "find", "search", "info"]):
            steps.append(AgentStep(number=2, action="web_search",
                description=f"Search for: {mission.objective}",
                params={"query": mission.objective}))
            steps.append(AgentStep(number=3, action="write_file",
                description="Save research notes",
                params={"path": os.path.join(ws_dir, "research_notes.md"),
                        "content": f"# Research: {mission.objective}\n\n## Results\n\n(Research results will be populated after search)"}))
            steps.append(AgentStep(number=4, action="run_command",
                description="Verify output",
                params={"cmd": f'dir "{ws_dir}"' if sys.platform == "win32" else f'ls "{ws_dir}"'}))
        elif any(w in obj for w in ["animation", "video", "animate"]):
            steps.append(AgentStep(number=2, action="write_file",
                description="Create animation HTML",
                params={"path": os.path.join(ws_dir, "animation.html"),
                        "content": "<!DOCTYPE html>\n<html><head><title>Animation</title>\n<style>body{margin:0;background:#000;display:flex;align-items:center;justify-content:center;height:100vh;}\n.ball{width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#00FF66,#00B4D8);animation:bounce 1.5s ease-in-out infinite;}\n@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-200px)}}\n</style></head><body><div class='ball'></div></body></html>"}))
            steps.append(AgentStep(number=3, action="run_command",
                description="Verify output",
                params={"cmd": f'dir "{ws_dir}"' if sys.platform == "win32" else f'ls "{ws_dir}"'}))
        else:
            steps.append(AgentStep(number=2, action="write_file",
                description="Create output file",
                params={"path": os.path.join(ws_dir, "output.txt"),
                        "content": f"JARVIS Mission: {mission.objective}\n\nThis file was created by the JARVIS workspace agent."}))
            steps.append(AgentStep(number=3, action="run_command",
                description="Verify output",
                params={"cmd": f'dir "{ws_dir}"' if sys.platform == "win32" else f'ls "{ws_dir}"'}))

        return steps

    def start_mission(self, mission_id: str) -> dict:
        with self._lock:
            mission = self._missions.get(mission_id)
        if not mission:
            return {"ok": False, "error": "Mission not found"}
        if not mission.steps:
            result = self.plan_mission(mission_id)
            if not result.get("ok"):
                return result

        mission.status = "executing"
        mission.started_at = time.time()
        self._paused[mission_id] = False
        self._stopped[mission_id] = False

        thread = threading.Thread(
            target=self._execute_mission_loop,
            args=(mission_id,),
            daemon=True
        )
        self._threads[mission_id] = thread
        thread.start()

        self._emit(mission_id, "started", {})
        return {"ok": True, "mission": mission.to_dict()}

    def _execute_mission_loop(self, mission_id: str):
        with self._lock:
            mission = self._missions.get(mission_id)
        if not mission:
            return

        from workspace_manager import get_workspace_manager
        from workspace_verifier import get_workspace_verifier
        wm = get_workspace_manager()
        verifier = get_workspace_verifier()
        state = get_mission_state()
        recovery_attempts = 0
        max_recovery = 3

        state.transition(mission_id, "executing")

        while mission.current_step < len(mission.steps):
            if self._stopped.get(mission_id):
                state.transition(mission_id, "stopped")
                mission.status = "stopped"
                self._emit(mission_id, "stopped", {})
                return

            while self._paused.get(mission_id):
                time.sleep(0.5)
                if self._stopped.get(mission_id):
                    state.transition(mission_id, "stopped")
                    mission.status = "stopped"
                    return

            step = mission.steps[mission.current_step]
            if step.status in ("completed", "skipped"):
                mission.current_step += 1
                continue

            ok, err, risk = validate_action(step.action, step.params)
            if not ok:
                log.warning(f"[AGENT] Step {step.number} failed validation: {err}")
                step.status = "failed"
                step.error = f"Validation error: {err}"
                mission.current_step += 1
                state.advance_step(mission_id, step.number, {"ok": False, "error": err})
                self._emit(mission_id, "step_error", step.to_dict())
                continue

            step.status = "running"
            step.timestamp = time.time()
            mission.current_action = step.description
            mission.progress = mission.current_step / max(len(mission.steps), 1)
            wm.update_action(mission.workspace_id, step.description, "working")
            self._emit(mission_id, "step_start", step.to_dict())

            # ── OBSERVE: Capture workspace state BEFORE executing ──
            # This is the critical ReAct OBSERVE phase — re-assess the environment
            # before acting, so the agent can adapt if the state changed.
            try:
                screenshot_before = wm.capture_frame(mission.workspace_id, quality=50)
                if screenshot_before:
                    step.screenshot_before = base64.b64encode(screenshot_before).decode()
                    # Feed observation to evidence ledger
                    from evidence_ledger import get_evidence_ledger
                    ledger = get_evidence_ledger(mission_id)
                    ledger.record_observation(
                        action_id=f"pre_step_{step.number}",
                        observation_type="workspace_state",
                        description=f"Observed workspace before step {step.number}: {step.description[:60]}",
                        data={"step": step.number, "action": step.action},
                    )
            except Exception as obs_err:
                log.debug(f"[AGENT] Pre-step observation failed: {obs_err}")

            try:
                from permission_model import get_permission_manager
                perm = get_permission_manager()
                approval_check = perm.requires_approval(step.action, step.params, risk)
                needs_approval = step.requires_approval or approval_check["required"]

                if needs_approval:
                    step.status = "awaiting_approval"
                    self._emit(mission_id, "approval_needed", {
                        **step.to_dict(),
                        "approval_reason": approval_check["reason"],
                        "hold_to_approve": approval_check["hold_to_approve"],
                        "hold_duration_s": approval_check["hold_duration_s"],
                        "category": approval_check["category"],
                    })
                    self._wait_for_approval(mission_id, step)

                result = self._execute_step(mission, step, wm)

                state.transition(mission_id, "verifying")

                screenshot = wm.capture_frame(mission.workspace_id, quality=50)
                verified = False
                if screenshot:
                    step.screenshot_after = base64.b64encode(screenshot).decode()
                    verification = verifier.verify_step(
                        screenshot, step.action, step.params,
                        expected_outcome=step.params.get("expected_text", "")
                    )
                    verified = verification.verified and verification.confidence >= 0.4

                    if not verified and verification.confidence < 0.4:
                        if recovery_attempts < max_recovery:
                            recovery_attempts += 1
                            log.warning(f"[AGENT] Step {step.number} verification failed (confidence={verification.confidence:.2f}), recovering...")
                            self._emit(mission_id, "recovering", {
                                "step": step.to_dict(),
                                "attempt": recovery_attempts,
                                "evidence": verification.evidence,
                            })
                            can_recover = state.start_recovery(mission_id)
                            if not can_recover:
                                step.status = "failed"
                                step.error = f"Max recovery attempts exhausted"
                                mission.current_step += 1
                                self._emit(mission_id, "step_error", step.to_dict())
                                state.transition(mission_id, "failure", step.error)
                                mission.status = "failed"
                                wm.update_action(mission.workspace_id, "Mission failed", "idle")
                                return

                            recovery_result = self._try_recover(mission, step, wm, verifier)
                            if recovery_result:
                                step.status = "completed"
                                step.result = str(recovery_result)
                                mission.current_step += 1
                                mission.progress = mission.current_step / len(mission.steps)
                                recovery_attempts = 0
                                state.advance_step(mission_id, step.number, {"ok": True, "recovered": True}, verified=True)
                                state.transition(mission_id, "executing")
                                self._emit(mission_id, "step_complete", step.to_dict())
                                continue
                            else:
                                step.status = "failed"
                                step.error = f"Verification failed: {verification.evidence}"
                                mission.current_step += 1
                                state.advance_step(mission_id, step.number, {"ok": False, "error": step.error})
                                state.transition(mission_id, "executing")
                                self._emit(mission_id, "step_error", step.to_dict())
                                continue

                step.status = "completed"
                step.result = str(result)
                mission.current_step += 1
                mission.progress = mission.current_step / len(mission.steps)
                recovery_attempts = 0
                state.advance_step(mission_id, step.number, result, verified=verified)
                state.transition(mission_id, "executing")
                self._emit(mission_id, "step_complete", step.to_dict())

            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                log.error(f"[AGENT] Step {step.number} failed: {e}")
                state.advance_step(mission_id, step.number, {"ok": False, "error": str(e)})
                self._emit(mission_id, "step_error", step.to_dict())
                if step.error and "approval denied" in str(e).lower():
                    state.transition(mission_id, "stopped")
                    mission.status = "stopped"
                    wm.update_action(mission.workspace_id, "Mission stopped by user", "idle")
                    return
                mission.current_step += 1

        state.transition(mission_id, "success")
        mission.status = "completed"
        mission.completed_at = time.time()
        mission.progress = 1.0
        mission.current_action = "Mission complete"
        wm.update_action(mission.workspace_id, "Mission complete", "idle")
        self._emit(mission_id, "completed", mission.to_dict())

    def _try_recover(self, mission: AgentMission, step: AgentStep, wm, verifier) -> Optional[str]:
        """Attempt self-healing recovery for a failed step.
        Uses the full OBSERVE→DIAGNOSE→REPAIR→VERIFY loop.
        """
        screenshot = wm.capture_frame(mission.workspace_id, quality=50)
        if screenshot:
            b64 = base64.b64encode(screenshot).decode()
            step.screenshot_before = b64
        recovery_strategies = self._diagnose_failure(step)
        for strategy in recovery_strategies:
            try:
                s = AgentStep(
                    number=step.number,
                    action=strategy["action"],
                    description=strategy["description"],
                    params=strategy.get("params", {}),
                )
                result = self._execute_step(mission, s, wm)
                screenshot_after = wm.capture_frame(mission.workspace_id, quality=50)
                if screenshot_after:
                    v = verifier.verify_step(screenshot_after, step.action, step.params)
                    if v.verified and v.confidence >= 0.4:
                        step.screenshot_after = base64.b64encode(screenshot_after).decode()
                        return result
            except Exception:
                continue
        return None

    def _diagnose_failure(self, step: AgentStep) -> List[dict]:
        """Analyze step failure and return targeted recovery strategies."""
        error_lower = step.error.lower() if step.error else ""
        strategies = []
        if "not found" in error_lower or "404" in error_lower:
            strategies.append({"action": "web_search", "params": {"query": step.description}, "description": "Search for correct resource"})
            strategies.append({"action": "screenshot", "description": "Reassess screen state"})
        elif "timeout" in error_lower or "timed out" in error_lower:
            strategies.append({"action": "wait", "params": {"seconds": 5}, "description": "Extended wait for slow resource"})
            strategies.append({"action": "screenshot", "description": "Check if page loaded after wait"})
        elif "permission" in error_lower or "access" in error_lower:
            strategies.append({"action": "press_key", "params": {"key": "Escape"}, "description": "Dismiss permission dialog"})
            strategies.append({"action": "screenshot", "description": "Check screen after dialog dismiss"})
        else:
            strategies = [
                {"action": "screenshot", "description": "Take screenshot to reassess state"},
                {"action": "press_key", "params": {"key": "Escape"}, "description": "Press Escape to clear dialog/state"},
                {"action": "wait", "params": {"seconds": 3}, "description": "Wait for UI to settle"},
                {"action": "screenshot", "description": "Verify state after recovery attempt"},
            ]
        return strategies

    def _execute_step(self, mission: AgentMission, step: AgentStep, wm) -> str:
        """Execute a single step via the task router."""
        from task_router import route_and_execute
        from mission_state import HIGH_RISK_ACTIONS

        risk = "high" if step.action in HIGH_RISK_ACTIONS else "low"
        result = route_and_execute(
            step.action, step.params, mission.workspace_id,
            risk_level=risk, objective=mission.objective,
        )

        if result.ok and step.action == "screenshot":
            if result.screenshot:
                mission.artifacts.append(f"screenshot_{step.number}.jpg")

        if not result.ok:
            raise RuntimeError(result.error or f"Action {step.action} failed")

        return result.output or json.dumps(result.to_dict())

    def _wait_for_approval(self, mission_id: str, step: AgentStep, timeout: float = 300):
        """Wait for user approval of a high-risk action."""
        start = time.time()
        while time.time() - start < timeout:
            if self._stopped.get(mission_id):
                raise RuntimeError("Mission stopped by user")
            with self._lock:
                mission = self._missions.get(mission_id)
            if mission and mission.status == "stopped":
                raise RuntimeError("Mission stopped by user")
            if step.status == "running":
                return
            if step.status == "skipped":
                raise RuntimeError("Step skipped by user")
            time.sleep(0.5)
        raise RuntimeError("Approval timeout - action denied")

    def approve_step(self, mission_id: str, step_number: int) -> dict:
        with self._lock:
            mission = self._missions.get(mission_id)
        if not mission:
            return {"ok": False, "error": "Mission not found"}
        for step in mission.steps:
            if step.number == step_number and step.status == "awaiting_approval":
                step.status = "running"
                self._emit(mission_id, "approved", step.to_dict())
                return {"ok": True}
        return {"ok": False, "error": "No pending approval at this step"}

    def deny_step(self, mission_id: str, step_number: int) -> dict:
        with self._lock:
            mission = self._missions.get(mission_id)
        if not mission:
            return {"ok": False, "error": "Mission not found"}
        for step in mission.steps:
            if step.number == step_number and step.status == "awaiting_approval":
                step.status = "skipped"
                step.error = "approval denied"
                self._emit(mission_id, "denied", step.to_dict())
                return {"ok": True}
        return {"ok": False, "error": "No pending approval at this step"}

    def pause_mission(self, mission_id: str) -> dict:
        self._paused[mission_id] = True
        state = get_mission_state()
        state.transition(mission_id, "paused")
        with self._lock:
            mission = self._missions.get(mission_id)
            if mission:
                mission.status = "paused"
        self._emit(mission_id, "paused", {})
        return {"ok": True}

    def resume_mission(self, mission_id: str) -> dict:
        self._paused[mission_id] = False
        state = get_mission_state()
        state.transition(mission_id, "executing")
        with self._lock:
            mission = self._missions.get(mission_id)
            if mission:
                mission.status = "executing"
        self._emit(mission_id, "resumed", {})
        return {"ok": True}

    def stop_mission(self, mission_id: str) -> dict:
        self._stopped[mission_id] = True
        self._paused[mission_id] = False
        state = get_mission_state()
        state.transition(mission_id, "stopped")
        with self._lock:
            mission = self._missions.get(mission_id)
            if mission:
                mission.status = "stopped"
        self._emit(mission_id, "stopped", {})
        return {"ok": True}

    def recover_orphaned(self) -> List[dict]:
        """Resume missions that were mid-execution when JARVIS crashed."""
        state = get_mission_state()
        resumable = state.get_resumable()
        results = []
        for record in resumable:
            with self._lock:
                mission = self._missions.get(record.id)
            if mission and mission.status in ("executing", "planning"):
                continue
            if mission is None:
                mission = AgentMission(
                    id=record.id, objective=record.objective,
                    workspace_id=record.workspace_id,
                    created_at=record.created_at,
                )
                mission.steps = [AgentStep(
                    number=s["number"], action=s["action"],
                    description=s["description"], params=s["params"],
                    status=s.get("status", "pending"),
                ) for s in record.steps]
                mission.current_step = record.current_step
                mission.artifacts = record.artifacts
                with self._lock:
                    self._missions[record.id] = mission

            mission.status = "executing"
            results.append({
                "mission_id": record.id,
                "objective": record.objective,
                "step": record.current_step,
                "total_steps": len(record.steps),
            })
            log.info(f"[AGENT] Resuming orphaned mission {record.id} at step {record.current_step}")

            self._paused[record.id] = False
            self._stopped[record.id] = False
            thread = threading.Thread(
                target=self._execute_mission_loop,
                args=(record.id,),
                daemon=True,
            )
            self._threads[record.id] = thread
            thread.start()

        return results

    def get_mission(self, mission_id: str) -> Optional[dict]:
        with self._lock:
            mission = self._missions.get(mission_id)
            return mission.to_dict() if mission else None

    def list_missions(self) -> List[dict]:
        with self._lock:
            return [m.to_dict() for m in self._missions.values()]

    def get_pending_approvals(self) -> List[dict]:
        result = []
        with self._lock:
            for mission in self._missions.values():
                for step in mission.steps:
                    if step.status == "awaiting_approval":
                        result.append({
                            "mission_id": mission.id,
                            "objective": mission.objective,
                            "step": step.to_dict(),
                            "workspace_id": mission.workspace_id,
                        })
        return result


_agent = None

def get_workspace_agent() -> WorkspaceAgent:
    global _agent
    if _agent is None:
        _agent = WorkspaceAgent()
    return _agent
