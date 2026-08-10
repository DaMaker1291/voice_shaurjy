"""
Goal Planner — Decomposes complex multi-goal prompts into executable sub-tasks.

Parses directives like:
  "Research Jensen Huang, build a timeline spreadsheet, generate a deck, and draft an email"
Into ordered steps that task_planner can execute sequentially.

Uses LLM for decomposition when available, falls back to keyword-based splitting.
"""

import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

log = logging.getLogger("jarvis-goals")


@dataclass
class SubGoal:
    id: str
    description: str
    intent: str          # matches edge_router intents or task_planner actions
    action: str          # specific task_planner action to invoke
    params: Dict = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)  # sub-goal IDs this depends on
    status: str = "pending"
    result: Optional[str] = None
    priority: int = 0    # lower = higher priority

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GoalPlan:
    raw_prompt: str
    sub_goals: List[SubGoal]
    mode: str = "sequential"  # sequential | parallel | autonomous
    background_vdi: bool = False
    laser_gate: bool = False
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "raw_prompt": self.raw_prompt,
            "sub_goals": [sg.to_dict() for sg in self.sub_goals],
            "mode": self.mode,
            "background_vdi": self.background_vdi,
            "laser_gate": self.laser_gate,
        }

    def pending_goals(self) -> List[SubGoal]:
        return [sg for sg in self.sub_goals if sg.status == "pending"]

    def completed_goals(self) -> List[SubGoal]:
        return [sg for sg in self.sub_goals if sg.status == "done"]

    def is_complete(self) -> bool:
        return all(sg.status in ("done", "failed", "skipped") for sg in self.sub_goals)


# ── Keyword-based decomposition (fallback when no LLM) ──────────────────────

_ACTION_KEYWORDS = {
    "research":     ("search", "search_web", {"query": "__extract__"}),
    "osint":        ("search", "search_web", {"query": "__extract__"}),
    "investigate":  ("search", "search_web", {"query": "__extract__"}),
    "find":         ("search", "search_web", {"query": "__extract__"}),
    "search":       ("search", "search_web", {"query": "__extract__"}),
    "lookup":       ("search", "search_web", {"query": "__extract__"}),
    "look up":      ("search", "search_web", {"query": "__extract__"}),

    "spreadsheet":  ("file", "create_spreadsheet", {}),
    "excel":        ("file", "create_spreadsheet", {}),
    "matrix":       ("file", "create_spreadsheet", {}),
    "table":        ("file", "create_spreadsheet", {}),
    "dataset":      ("file", "create_spreadsheet", {}),

    "deck":         ("file", "create_presentation", {}),
    "powerpoint":   ("file", "create_presentation", {}),
    "pptx":         ("file", "create_presentation", {}),
    "presentation": ("file", "create_presentation", {}),
    "slides":       ("file", "create_presentation", {}),

    "document":     ("file", "create_document", {}),
    "doc":          ("file", "create_document", {}),
    "docx":         ("file", "create_document", {}),
    "brief":        ("file", "create_document", {}),
    "report":       ("file", "create_document", {}),
    "summary":      ("file", "create_document", {}),
    "memo":         ("file", "create_document", {}),

    "email":        ("email", "send_email", {}),
    "draft":        ("email", "send_email", {}),
    "outreach":     ("email", "send_email", {}),
    "compose":      ("email", "send_email", {}),

    "calendar":     ("schedule", "create_event", {}),
    "meeting":      ("schedule", "create_event", {}),
    "event":        ("schedule", "create_event", {}),

    "flight":       ("economic", "plan_travel", {}),
    "hotel":        ("economic", "plan_travel", {}),
    "travel":       ("economic", "plan_travel", {}),
    "trip":         ("economic", "plan_travel", {}),
    "booking":      ("economic", "plan_travel", {}),

    "compare":      ("search", "compare_prices", {}),
    "price":        ("search", "compare_prices", {}),
    "shop":         ("search", "compare_prices", {}),
    "buy":          ("search", "compare_prices", {}),
    "purchase":     ("search", "compare_prices", {}),

    "timeline":     ("file", "create_spreadsheet", {"template": "timeline"}),
    "graph":        ("file", "create_document", {"template": "graph"}),
    "chart":        ("file", "create_document", {"template": "chart"}),
    "dashboard":    ("file", "create_document", {"template": "dashboard"}),

    "open":         ("system", "open_app", {}),
    "launch":       ("system", "open_app", {}),
    "run":          ("system", "open_app", {}),
    "start":        ("system", "open_app", {}),
    "close":        ("system", "close_window", {}),
    "quit":         ("system", "close_window", {}),
    "kill":         ("system", "close_window", {}),

    "save":         ("file", "write_file", {}),
    "download":     ("file", "download_file", {}),
    "copy":         ("system", "set_clipboard", {}),
    "paste":        ("system", "get_clipboard", {}),
    "type":         ("system", "type_text", {}),
    "click":        ("system", "click", {}),
    "scroll":       ("system", "scroll", {}),

    "screenshot":   ("system", "screenshot", {}),
    "analyze":      ("system", "analyze_screen", {}),
    "vision":       ("system", "vision_control", {}),
}


def _extract_target_entity(text: str) -> str:
    """Extract the main entity/subject from the prompt."""
    # Remove directive prefixes
    cleaned = re.sub(r'^(execute|run|perform|do|complete|finish)\s+(directive|task|command)?[:\s]*', '', text, flags=re.I)
    # Remove quoted strings as separate targets
    cleaned = re.sub(r'"[^"]*"', '', cleaned)
    # Try to find "about X" or "for X" or "target: X"
    m = re.search(r'(?:about|for|target|regarding|on|of)\s+(.+?)(?:\s+(?:and|then|next|after|,)\s|$)', cleaned, re.I)
    if m:
        return m.group(1).strip()
    # Try capitalized words after common prepositions
    words = cleaned.split()
    for i, w in enumerate(words):
        if w.istitle() and i > 0:
            return ' '.join(words[i:i+3])
    return cleaned[:80]


def _split_clauses(text: str) -> List[str]:
    """Split a complex prompt into individual action clauses."""
    # First remove the directive prefix if present
    cleaned = re.sub(r'^(?:execute|run|perform|do|complete|finish)\s+(?:directive|task|command)?[:\s]*', '', text, flags=re.I)
    cleaned = re.sub(r'EXECUTE\s+DIRECTIVE[:\s]*', '', cleaned, flags=re.I)

    # Split on common separators
    parts = re.split(r'\s*,\s*|\s+and\s+|\s+then\s+|\s+next\s+|\s+after\s+that\s+|\s+also\s+|\s*;\s*|\n+', cleaned, flags=re.I)
    result = []
    for p in parts:
        p = p.strip()
        # Remove trailing prepositions
        p = re.sub(r'\s+(?:and|then|next|also)\s*$', '', p, flags=re.I)
        if p and len(p) > 3:
            result.append(p)
    return result


def _match_action(clause: str) -> Tuple[str, str, Dict]:
    """Match a clause to a task_planner action. Returns (intent, action, params)."""
    clause_lower = clause.lower()
    best_match = None
    best_len = 0

    for keyword, (intent, action, extra_params) in _ACTION_KEYWORDS.items():
        if keyword in clause_lower and len(keyword) > best_len:
            best_match = (intent, action, extra_params.copy())
            best_len = len(keyword)

    if best_match:
        intent, action, params = best_match
        # Extract query/text from clause for search actions
        if action in ("search_web", "compare_prices"):
            query = _extract_target_entity(clause)
            if query:
                params["query"] = query
        elif action == "open_app":
            # Try to extract app name
            m = re.search(r'(?:open|launch|start|run)\s+(\w+)', clause, re.I)
            if m:
                params["app"] = m.group(1)
        elif action in ("create_document", "create_spreadsheet", "create_presentation"):
            # Extract title from clause
            title = _extract_target_entity(clause)
            if title:
                params["title"] = title
        elif action == "plan_travel":
            m = re.search(r'(?:to|for|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', clause)
            if m:
                params["destination"] = m.group(1).lower()
        elif action == "send_email":
            m = re.search(r'(?:to|about|regarding)\s+(.+?)(?:\s+and\s|$)', clause, re.I)
            if m:
                params["subject"] = m.group(1).strip()
        return intent, action, params

    # Default: treat as a research/search query
    return "search", "search_web", {"query": clause[:200]}


def decompose_with_keywords(text: str) -> GoalPlan:
    """Keyword-based decomposition of complex prompts."""
    import time as _time

    # Parse directive flags
    background_vdi = bool(re.search(r'--background-vdi|background.*vdi|vdi.*background', text, re.I))
    laser_gate = bool(re.search(r'--laser-gate|laser.*gate', text, re.I))
    autonomous = bool(re.search(r'--mode=autonomous|autonomous\s+mode', text, re.I))

    # Clean the text of directive flags
    cleaned = re.sub(r'/\w+(\s+--[^\s]+)*\s*', '', text)
    cleaned = re.sub(r'--\w+[\s=]\S+', '', cleaned)

    # Extract the core directive
    directive_match = re.search(r'(?:execute|run|perform|do|complete)?\s*(?:directive)?[:\s]*(.+)', cleaned, re.I | re.S)
    core = directive_match.group(1).strip() if directive_match else cleaned.strip()

    # Split into clauses
    clauses = _split_clauses(core)

    sub_goals = []
    for i, clause in enumerate(clauses):
        intent, action, params = _match_action(clause)
        sg = SubGoal(
            id=f"step_{i+1}",
            description=clause[:200],
            intent=intent,
            action=action,
            params=params,
            priority=i,
            depends_on=[f"step_{i}"] if i > 0 and action in ("create_presentation", "create_document", "send_email") else [],
        )
        sub_goals.append(sg)

    if not sub_goals:
        # Fallback: treat entire prompt as a single search
        sub_goals.append(SubGoal(
            id="step_1",
            description=core[:200],
            intent="search",
            action="search_web",
            params={"query": core[:200]},
        ))

    mode = "autonomous" if autonomous else "sequential"

    return GoalPlan(
        raw_prompt=text,
        sub_goals=sub_goals,
        mode=mode,
        background_vdi=background_vdi,
        laser_gate=laser_gate,
        created_at=_time.time(),
    )


def decompose_with_llm(text: str) -> Optional[GoalPlan]:
    """Use LLM to decompose complex prompts. Returns None if LLM unavailable."""
    try:
        from groq_agent import call_groq

        system_prompt = """You are a task decomposition engine. Break complex user prompts into ordered sub-tasks.

Return a JSON array of sub-tasks. Each sub-task must have:
- "description": what to do (short)
- "action": one of [search_web, compare_prices, plan_travel, create_document, create_spreadsheet, create_presentation, send_email, open_app, type_text, click, scroll, screenshot, analyze_screen, vision_control, write_file, download_file, run_python, run_command]
- "params": object with action-specific parameters (query, destination, title, app, etc.)
- "depends_on": array of step indices (0-based) this depends on, or []

Rules:
- Extract the main entity/subject from the prompt
- If the prompt mentions research, use search_web with a good query
- If it mentions a spreadsheet/timeline, use create_spreadsheet
- If it mentions a deck/presentation, use create_presentation
- If it mentions email/draft, use send_email
- If it mentions travel/flights/hotels, use plan_travel
- If it mentions comparison/prices, use compare_prices
- Order steps logically: research first, then build artifacts, then output
- Steps that don't depend on each other can have empty depends_on
- Keep it to 3-8 steps max

Return ONLY the JSON array, no explanation."""

        response = call_groq(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        if not response:
            return None

        # Extract JSON from response
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r'^```\w*\n?', '', response)
            response = re.sub(r'\n?```$', '', response)

        steps = json.loads(response)
        if not isinstance(steps, list):
            return None

        sub_goals = []
        for i, step in enumerate(steps):
            sg = SubGoal(
                id=f"step_{i+1}",
                description=step.get("description", f"Step {i+1}"),
                intent="auto",
                action=step.get("action", "search_web"),
                params=step.get("params", {}),
                depends_on=[f"step_{d+1}" for d in step.get("depends_on", [])],
                priority=i,
            )
            sub_goals.append(sg)

        if not sub_goals:
            return None

        import time as _time
        return GoalPlan(
            raw_prompt=text,
            sub_goals=sub_goals,
            mode="sequential",
            created_at=_time.time(),
        )

    except Exception as e:
        log.debug(f"LLM decomposition failed: {e}")
        return None


def decompose(text: str) -> GoalPlan:
    """Decompose a complex prompt into executable sub-goals.
    
    Tries LLM first for best quality, falls back to keyword matching.
    """
    # Try LLM decomposition first
    plan = decompose_with_llm(text)
    if plan and plan.sub_goals:
        log.info(f"[GOALS] LLM decomposed into {len(plan.sub_goals)} sub-goals")
        return plan

    # Fallback to keyword-based
    plan = decompose_with_keywords(text)
    log.info(f"[GOALS] Keyword decomposed into {len(plan.sub_goals)} sub-goals")
    return plan


def execute_plan(plan: GoalPlan, execute_fn=None) -> GoalPlan:
    """Execute a GoalPlan step by step, respecting dependencies.
    
    Args:
        plan: The GoalPlan to execute
        execute_fn: Callable(action, params) -> result_string. If None, uses task_planner.
    
    Returns:
        Updated GoalPlan with results.
    """
    if execute_fn is None:
        from task_planner import TaskPlanner
        planner = TaskPlanner()
        def execute_fn(action, params):
            return planner.execute(action, params)

    completed = set()

    while not plan.is_complete():
        # Find next executable goal (all dependencies met)
        ready = None
        for sg in plan.pending_goals():
            deps_met = all(d in completed for d in sg.depends_on)
            if deps_met:
                ready = sg
                break

        if ready is None:
            # Circular dependency or error — mark remaining as failed
            for sg in plan.pending_goals():
                sg.status = "failed"
                sg.result = "Dependency not met"
            break

        ready.status = "running"
        try:
            result = execute_fn(ready.action, ready.params)
            ready.result = str(result)
            ready.status = "done"
        except Exception as e:
            ready.result = f"Error: {e}"
            ready.status = "failed"
            log.error(f"[GOALS] Step {ready.id} failed: {e}")

        completed.add(ready.id)

    return plan


# ── Singleton ────────────────────────────────────────────────────────────────

_planner = None

def get_planner():
    global _planner
    if _planner is None:
        _planner = GoalPlanner()
    return _planner


class GoalPlanner:
    """High-level orchestrator for multi-goal execution."""

    def plan(self, text: str) -> GoalPlan:
        return decompose(text)

    def execute(self, text: str, execute_fn=None) -> GoalPlan:
        plan = self.plan(text)
        return execute_plan(plan, execute_fn)
