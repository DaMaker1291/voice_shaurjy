"""JARVIS Hierarchical Dynamic Planner — Goal → Steps → Actions.

Takes a user objective and produces a structured execution plan
of composable primitives from the Action Fabric.

ARCHITECTURE:

    GOAL → SUBGOALS → STEPS → PRIMITIVES → EXECUTION GRAPH
                    ↑              ↑
                    │              │
              OBSERVE ← ← ← ← ← │
              (replan)            │
                    │              │
                    ↓              ↓
              VERIFY ← ← ← ← ← ←

The planner runs in a closed loop:
1. Plan next chunk of work
2. Execute chunk
3. Observe results
4. Replan if needed
5. Repeat until goal achieved
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

log = logging.getLogger("planner")


@dataclass
class PlanStep:
    """A single step in the plan."""
    id: str
    description: str
    primitives: List[str]  # Action Fabric primitive names
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "primitives": self.primitives,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "status": self.status,
            "result": self.result,
            "retry_count": self.retry_count,
        }


@dataclass
class MissionPlan:
    """A complete plan for achieving a mission goal."""
    mission_id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step_idx: int = 0
    status: str = "planning"  # planning, executing, replanning, completed, failed
    context: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    created_at: float = 0
    updated_at: float = 0

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_idx": self.current_step_idx,
            "status": self.status,
            "context": self.context,
            "assumptions": self.assumptions,
            "risk_level": self.risk_level,
        }


class HierarchicalPlanner:
    """Dynamic planner that decomposes goals into executable steps.

    Uses AI for planning when available, falls back to heuristic
    decomposition for known task patterns.
    """

    def __init__(self, model_router=None, world_model=None, action_fabric=None):
        self._router = model_router
        self._world = world_model
        self._fabric = action_fabric
        self._plan_history: Dict[str, MissionPlan] = {}

    async def create_plan(self, mission_id: str, goal: str,
                         context: Dict[str, Any] = None) -> MissionPlan:
        """Create an execution plan for the given goal."""
        plan = MissionPlan(
            mission_id=mission_id,
            goal=goal,
            context=context or {},
            created_at=time.time(),
            updated_at=time.time(),
        )
        log.info(f"[PLAN] Creating plan for: {goal[:80]}...")

        # Try AI planning first
        if self._router:
            try:
                plan = await self._ai_plan(plan)
                self._plan_history[mission_id] = plan
                return plan
            except Exception as e:
                log.warning(f"[PLAN] AI planning failed: {e}")

        # Fallback: heuristic decomposition
        plan = self._heuristic_plan(plan)
        self._plan_history[mission_id] = plan
        return plan

    async def _ai_plan(self, plan: MissionPlan) -> MissionPlan:
        """Use AI to decompose the goal into steps."""
        world_context = ""
        if self._world:
            world_context = self._world.get_context_string()

        prompt = f"""You are JARVIS, an autonomous computer-execution agent.

USER GOAL: {plan.goal}

{world_context}

Available Action Primitives:
- find(query) → locate files, windows, UI elements
- read(path_or_element) → get content
- write(path, content) → create/overwrite file
- search(pattern, path) → find in files
- click(element) → click UI element
- type(text) → type into active field
- screenshot() → capture screen
- launch(app) → open application
- navigate(url) → open in browser
- execute(command) → run shell command
- copy() → copy selection
- paste() → paste clipboard
- move(src, dst) → move file
- delete(path) → remove file
- wait(seconds) → delay

Break this goal into 3-10 concrete steps. For each step, list:
1. What to do
2. Which primitives to use
3. What must be true before this step (preconditions)
4. What must be true after this step (postconditions)

Also assess:
- Risk level: low/medium/high/critical
- Any assumptions you're making
- Whether clarification is needed

Respond in JSON:
{{
  "risk_level": "...",
  "assumptions": ["..."],
  "steps": [
    {{
      "id": "step_1",
      "description": "...",
      "primitives": ["primitive_name"],
      "preconditions": ["..."],
      "postconditions": ["..."]
    }}
  ]
}}"""

        response = await self._router.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        text = response.get("text", "")

        # Parse JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])

            plan.risk_level = data.get("risk_level", "low")
            plan.assumptions = data.get("assumptions", [])

            for step_data in data.get("steps", []):
                step = PlanStep(
                    id=step_data.get("id", f"step_{len(plan.steps)+1}"),
                    description=step_data.get("description", ""),
                    primitives=step_data.get("primitives", []),
                    preconditions=step_data.get("preconditions", []),
                    postconditions=step_data.get("postconditions", []),
                )
                plan.steps.append(step)

            plan.status = "executing"
            log.info(f"[PLAN] AI created {len(plan.steps)} steps")
            return plan

        raise ValueError("Could not parse AI response")

    def _heuristic_plan(self, plan: MissionPlan) -> MissionPlan:
        """Fallback: decompose using known task patterns."""
        goal_lower = plan.goal.lower()

        # Pattern matching for common tasks
        if any(w in goal_lower for w in ["file", "create", "write", "document"]):
            plan.steps = [
                PlanStep("s1", "Determine file location and name",
                        ["find", "screenshot"], [], ["file_path_determined"]),
                PlanStep("s2", "Create file content",
                        ["read", "type"], ["file_path_determined"], ["content_written"]),
                PlanStep("s3", "Verify file was created",
                        ["find", "read"], ["content_written"], ["file_verified"]),
            ]

        elif any(w in goal_lower for w in ["search", "find", "look"]):
            plan.steps = [
                PlanStep("s1", "Search for target",
                        ["search", "find"], [], ["target_found"]),
                PlanStep("s2", "Review results",
                        ["read"], ["target_found"], ["results_reviewed"]),
            ]

        elif any(w in goal_lower for w in ["open", "launch", "start", "run"]):
            plan.steps = [
                PlanStep("s1", "Launch target application",
                        ["launch"], [], ["app_launched"]),
                PlanStep("s2", "Wait for app to load",
                        ["wait", "screenshot"], ["app_launched"], ["app_ready"]),
            ]

        elif any(w in goal_lower for w in ["browser", "website", "url", "web"]):
            plan.steps = [
                PlanStep("s1", "Navigate to URL",
                        ["navigate"], [], ["page_loaded"]),
                PlanStep("s2", "Wait for page",
                        ["wait", "screenshot"], ["page_loaded"], ["page_ready"]),
            ]

        elif any(w in goal_lower for w in ["email", "send", "message"]):
            plan.steps = [
                PlanStep("s1", "Open email application",
                        ["launch", "find"], [], ["email_app_open"]),
                PlanStep("s2", "Compose message",
                        ["click", "type"], ["email_app_open"], ["message_composed"]),
                PlanStep("s3", "Send message",
                        ["click"], ["message_composed"], ["message_sent"]),
            ]

        else:
            # Generic: observe → understand → act → verify
            plan.steps = [
                PlanStep("s1", "Observe current state",
                        ["screenshot"], [], ["state_observed"]),
                PlanStep("s2", "Determine approach",
                        ["find"], ["state_observed"], ["approach_determined"]),
                PlanStep("s3", "Execute action",
                        ["type", "click"], ["approach_determined"], ["action_performed"]),
                PlanStep("s4", "Verify outcome",
                        ["screenshot", "find"], ["action_performed"], ["outcome_verified"]),
            ]

        plan.status = "executing"
        log.info(f"[PLAN] Heuristic created {len(plan.steps)} steps")
        return plan

    async def replan(self, mission_id: str, failed_step_id: str,
                    error: str, context: Dict[str, Any] = None) -> MissionPlan:
        """Replan after a step failure."""
        plan = self._plan_history.get(mission_id)
        if not plan:
            log.error(f"[PLAN] No plan for mission {mission_id}")
            return MissionPlan(mission_id=mission_id, goal="Unknown", status="failed")

        log.info(f"[PLAN] Replanning after step {failed_step_id} failed: {error}")
        plan.status = "replanning"
        plan.updated_at = time.time()

        # Get completed steps for context
        completed = [s for s in plan.steps if s.status == "completed"]
        failed_idx = next(
            (i for i, s in enumerate(plan.steps) if s.id == failed_step_id), -1
        )

        # Try AI replanning
        if self._router:
            try:
                completed_summary = "\n".join(
                    f"  ✓ {s.description}" for s in completed
                )
                prompt = f"""JARVIS replanning after failure.

GOAL: {plan.goal}

COMPLETED STEPS:
{completed_summary or "  (none yet)"}

FAILED STEP: {plan.steps[failed_idx].description if failed_idx >= 0 else 'unknown'}
ERROR: {error}

Given the failure, either:
1. Try a different approach for the failed step
2. Skip the failed step if it's not critical
3. Find an alternative path to the goal

Respond in JSON:
{{
  "steps": [
    {{
      "id": "...",
      "description": "...",
      "primitives": ["..."],
      "preconditions": ["..."],
      "postconditions": ["..."]
    }}
  ]
}}"""

                response = await self._router.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1000,
                )

                text = response.get("text", "")
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(text[start:end])

                    # Keep completed steps, replace from failed onwards
                    new_steps = completed.copy()
                    for step_data in data.get("steps", []):
                        new_steps.append(PlanStep(
                            id=step_data["id"],
                            description=step_data["description"],
                            primitives=step_data.get("primitives", []),
                            preconditions=step_data.get("preconditions", []),
                            postconditions=step_data.get("postconditions", []),
                        ))

                    plan.steps = new_steps
                    plan.current_step_idx = len(completed)
                    plan.status = "executing"
                    log.info(f"[PLAN] AI replanned: {len(new_steps)} total steps")
                    return plan
            except Exception as e:
                log.warning(f"[PLAN] AI replanning failed: {e}")

        # Fallback: retry failed step with different primitives
        if failed_idx >= 0 and failed_idx < len(plan.steps):
            failed_step = plan.steps[failed_idx]
            if failed_step.retry_count < failed_step.max_retries:
                failed_step.retry_count += 1
                failed_step.status = "pending"
                failed_step.result = None
                plan.status = "executing"
                log.info(f"[PLAN] Retrying step {failed_step.id} (attempt {failed_step.retry_count})")
                return plan

        # Skip failed step, move to next
        if failed_idx >= 0:
            plan.steps[failed_idx].status = "skipped"
            plan.current_step_idx = failed_idx + 1

        plan.status = "executing"
        return plan

    def get_current_step(self, plan: MissionPlan) -> Optional[PlanStep]:
        """Get the current step to execute."""
        for i, step in enumerate(plan.steps):
            if step.status == "pending":
                plan.current_step_idx = i
                return step
        return None

    def mark_step_completed(self, plan: MissionPlan, step_id: str,
                           result: Dict[str, Any]):
        """Mark a step as completed."""
        for step in plan.steps:
            if step.id == step_id:
                step.status = "completed"
                step.result = result
                log.info(f"[PLAN] Step {step_id} completed")
                break

        # Check if all steps done
        if all(s.status in ("completed", "skipped") for s in plan.steps):
            plan.status = "completed"
            log.info(f"[PLAN] Mission {plan.mission_id} plan completed!")

    def mark_step_failed(self, plan: MissionPlan, step_id: str,
                        error: str):
        """Mark a step as failed."""
        for step in plan.steps:
            if step.id == step_id:
                step.status = "failed"
                step.result = {"error": error}
                break

    def get_progress(self, plan: MissionPlan) -> Dict[str, Any]:
        """Get plan progress summary."""
        total = len(plan.steps)
        completed = sum(1 for s in plan.steps if s.status == "completed")
        failed = sum(1 for s in plan.steps if s.status == "failed")
        skipped = sum(1 for s in plan.steps if s.status == "skipped")

        return {
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "percentage": int(completed / max(total, 1) * 100),
            "current_step": plan.current_step_idx + 1,
            "status": plan.status,
        }


# ── Singleton ──
_planner: Optional[HierarchicalPlanner] = None


def get_planner(model_router=None, world_model=None, action_fabric=None) -> HierarchicalPlanner:
    global _planner
    if _planner is None:
        _planner = HierarchicalPlanner(model_router, world_model, action_fabric)
    return _planner
