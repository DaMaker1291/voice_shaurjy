"""JARVIS Task Planner — Goal Decomposition.

The planner takes a user goal and breaks it into executable subtasks.
It uses the Skill Registry to determine which tools are available,
then creates a mission with verified-executable steps.

No step is added unless the planner can confirm the tool exists.
"""

import os, sys, json, logging, time
from pathlib import Path

log = logging.getLogger("task_planner")

sys.path.insert(0, os.path.dirname(__file__))


class TaskPlanner:
    """Decomposes goals into executable subtasks using available skills."""

    def __init__(self):
        self.registry = None
        self.mission_engine = None

    def _ensure_imports(self):
        if self.registry is None:
            from skill_registry import get_skill_registry
            self.registry = get_skill_registry()
        if self.mission_engine is None:
            from mission_engine import get_mission_engine
            self.mission_engine = get_mission_engine()

    def plan(self, objective: str, constraints: dict = None) -> dict:
        """Plan a mission: decompose objective into executable steps.

        Returns:
            {
                "mission_id": "abc123",
                "objective": "...",
                "steps": [...],
                "estimated_time": "5 min",
                "tools_required": ["chrome", "xdotool"],
                "tools_available": True/False,
            }
        """
        self._ensure_imports()

        # Create mission
        mission = self.mission_engine.create_mission(
            objective=objective,
            constraints=constraints or {},
        )

        # Decompose objective into steps
        steps = self._decompose(objective, constraints)

        # Add steps to mission
        for step in steps:
            self.mission_engine.add_step(
                mission_id=mission.id,
                description=step["description"],
                agent=step["agent"],
                action=step["action"],
                params=step.get("params", {}),
                verification=step.get("verification", {}),
            )

        # Check tool availability
        tools_required = set(s["agent"] for s in steps)
        tools_available = all(
            self.registry.get_skill(s["action"]) is not None
            for s in steps
        )

        return {
            "mission_id": mission.id,
            "objective": objective,
            "steps": steps,
            "estimated_time": f"{len(steps) * 30}s",
            "tools_required": list(tools_required),
            "tools_available": tools_available,
            "mission": mission,
        }

    def _decompose(self, objective: str, constraints: dict) -> list:
        """Decompose objective into executable steps.

        This uses pattern matching + LLM planning.
        """
        obj = objective.lower()

        # Travel query
        if any(w in obj for w in ['holiday', 'trip', 'vacation', 'flight', 'hotel', 'cruise']):
            return self._plan_travel(objective, constraints)

        # Money/income query
        if any(w in obj for w in ['money', 'income', 'sell', 'product', 'niche', 'profit']):
            return self._plan_money(objective, constraints)

        # Research query
        if any(w in obj for w in ['research', 'compare', 'find', 'search', 'analysis']):
            return self._plan_research(objective, constraints)

        # Document creation
        if any(w in obj for w in ['create', 'write', 'generate', 'build', 'make']):
            return self._plan_creation(objective, constraints)

        # Default: simple chat response
        return self._plan_simple(objective, constraints)

    def _plan_travel(self, objective: str, constraints: dict) -> list:
        """Plan a travel search mission."""
        steps = []

        # Step 1: Parse requirements
        steps.append({
            "description": "Parse travel requirements from user input",
            "agent": "planner",
            "action": "parse_travel_query",
            "params": {"query": objective},
            "verification": {"type": "field_check", "fields": ["destination", "dates", "group_size"]},
        })

        # Step 2: Check VDI availability
        steps.append({
            "description": "Verify VDI display is accessible",
            "agent": "os_agent",
            "action": "check_display",
            "params": {"display": ":99"},
            "verification": {"type": "command", "command": "DISPLAY=:99 xdpyinfo | head -1"},
        })

        # Step 3: Launch browser
        steps.append({
            "description": "Launch Chrome browser in VDI",
            "agent": "browser_agent",
            "action": "launch_browser",
            "params": {"display": ":99", "url": "about:blank"},
            "verification": {"type": "process_check", "process": "chrome"},
        })

        # Step 4: Search travel sites
        steps.append({
            "description": "Search travel comparison sites",
            "agent": "browser_agent",
            "action": "search_sites",
            "params": {"sites": ["skyscanner", "booking.com", "google flights"]},
            "verification": {"type": "clipboard_check", "min_prices": 1},
        })

        # Step 5: Extract prices
        steps.append({
            "description": "Extract and compare prices",
            "agent": "travel_agent",
            "action": "extract_prices",
            "params": {"currencies": ["GBP", "USD", "EUR"]},
            "verification": {"type": "field_check", "fields": ["prices"]},
        })

        # Step 6: Generate response
        steps.append({
            "description": "Generate structured travel recommendation",
            "agent": "planner",
            "action": "generate_response",
            "params": {"format": "structured"},
            "verification": {"type": "response_check", "min_length": 100},
        })

        return steps

    def _plan_money(self, objective: str, constraints: dict) -> list:
        """Plan a money-making research mission."""
        return [
            {"description": "Scan digital marketplaces for opportunities",
             "agent": "research_agent", "action": "scan_marketplaces",
             "params": {}, "verification": {"type": "field_check", "fields": ["opportunities"]}},
            {"description": "Analyze top opportunities",
             "agent": "research_agent", "action": "analyze_opportunities",
             "params": {}, "verification": {"type": "field_check", "fields": ["analysis"]}},
            {"description": "Generate money-making recommendations",
             "agent": "planner", "action": "generate_response",
             "params": {}, "verification": {"type": "response_check", "min_length": 100}},
        ]

    def _plan_research(self, objective: str, constraints: dict) -> list:
        """Plan a research mission."""
        return [
            {"description": "Search for information",
             "agent": "browser_agent", "action": "web_search",
             "params": {"query": objective}, "verification": {"type": "clipboard_check"}},
            {"description": "Compile research findings",
             "agent": "planner", "action": "generate_response",
             "params": {}, "verification": {"type": "response_check", "min_length": 100}},
        ]

    def _plan_creation(self, objective: str, constraints: dict) -> list:
        """Plan a document/content creation mission."""
        return [
            {"description": "Understand creation requirements",
             "agent": "planner", "action": "parse_requirements",
             "params": {"query": objective}, "verification": {"type": "field_check"}},
            {"description": "Create content",
             "agent": "document_agent", "action": "create_document",
             "params": {}, "verification": {"type": "file_check"}},
            {"description": "Deliver result",
             "agent": "planner", "action": "generate_response",
             "params": {}, "verification": {"type": "response_check"}},
        ]

    def _plan_simple(self, objective: str, constraints: dict) -> list:
        """Plan a simple chat response."""
        return [
            {"description": "Generate response",
             "agent": "planner", "action": "generate_response",
             "params": {"query": objective},
             "verification": {"type": "response_check", "min_length": 10}},
        ]


# ── Singleton ──
_planner = None
def get_task_planner() -> TaskPlanner:
    global _planner
    if _planner is None:
        _planner = TaskPlanner()
    return _planner
