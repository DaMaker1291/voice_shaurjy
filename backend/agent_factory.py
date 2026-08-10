"""JARVIS Agent Factory — Dynamic Specialized Agent Creation.

JARVIS doesn't have 60 fixed agents.
JARVIS builds a team for the task, then destroys them when done.

Usage:
    factory = AgentFactory()
    agents = factory.build_team("Build a website for my bakery")
    # → [ResearchAgent, DesignAgent, FrontendAgent, DeployAgent]
"""

import os
import json
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any

log = logging.getLogger("agent_factory")


# ══════════════════════════════════════════════════════════════
#  AGENT SPECIFICATION
# ══════════════════════════════════════════════════════════════

@dataclass
class AgentSpec:
    """Specification for a dynamically-created agent."""
    id: str
    role: str                  # "research", "code", "browser", "design", "verify", "deploy"
    objective: str             # What this agent must achieve
    tools: List[str]           # What it can use: "browser", "file_system", "cli", "api", "vision"
    permissions: List[str]     # What it's allowed to do
    context: Dict[str, Any]    # Shared mission context
    budget_tokens: int = 5000  # Max tokens this agent can spend
    timeout: int = 120         # Max seconds
    verification_criteria: str = ""  # How to verify success
    status: str = "pending"    # pending, running, completed, failed
    result: Any = None         # Output of the agent's work
    error: str = ""
    started_at: float = 0
    completed_at: float = 0

    def to_dict(self):
        return {
            "id": self.id, "role": self.role, "objective": self.objective,
            "tools": self.tools, "permissions": self.permissions,
            "status": self.status, "result": self.result, "error": self.error,
            "started_at": self.started_at, "completed_at": self.completed_at,
        }


# ══════════════════════════════════════════════════════════════
#  TASK ANALYSIS — What capabilities are required?
# ══════════════════════════════════════════════════════════════

# Keywords that signal what agents a task needs
ROLE_SIGNALS = {
    "research": ["research", "find", "look up", "search", "analyze", "investigate", "study", "explore", "competitor", "market", "data"],
    "code": ["build", "code", "create", "develop", "write", "implement", "program", "app", "website", "api", "function", "script"],
    "browser": ["browse", "open", "navigate", "web", "url", "site", "online", "scrape", "screenshot"],
    "design": ["design", "style", "css", "layout", "ui", "ux", "visual", "graphic", "logo", "brand", "color", "font"],
    "verify": ["test", "verify", "check", "validate", "ensure", "confirm", "review", "qa", "quality"],
    "deploy": ["deploy", "publish", "launch", "release", "upload", "host", "ship", "distribute"],
    "file": ["file", "folder", "organize", "rename", "move", "copy", "delete", "clean", "structure"],
    "data": ["data", "csv", "json", "spreadsheet", "database", "parse", "extract", "transform", "convert"],
    "media": ["image", "video", "audio", "photo", "animation", "render", "ffmpeg", "convert"],
    "communication": ["email", "message", "notify", "send", "post", "tweet", "publish", "share"],
}

# What tools each role gets
ROLE_TOOLS = {
    "research": ["browser", "api", "file_system"],
    "code": ["file_system", "cli", "browser"],
    "browser": ["browser"],
    "design": ["file_system", "browser"],
    "verify": ["cli", "browser", "file_system", "vision"],
    "deploy": ["cli", "api", "file_system"],
    "file": ["file_system", "cli"],
    "data": ["file_system", "cli", "api"],
    "media": ["cli", "file_system"],
    "communication": ["api", "browser"],
}

# What permissions each role gets
ROLE_PERMISSIONS = {
    "research": ["read_web", "read_file", "write_file"],
    "code": ["read_file", "write_file", "run_command"],
    "browser": ["read_web", "screenshot"],
    "design": ["read_file", "write_file"],
    "verify": ["read_file", "run_command", "screenshot"],
    "deploy": ["read_file", "write_file", "run_command", "access_api"],
    "file": ["read_file", "write_file", "run_command"],
    "data": ["read_file", "write_file", "run_command"],
    "media": ["read_file", "write_file", "run_command"],
    "communication": ["access_api", "read_file"],
}


def analyze_task(objective: str) -> List[str]:
    """Analyze a task objective and return the list of required roles."""
    text = objective.lower()
    roles = []
    for role, signals in ROLE_SIGNALS.items():
        if any(signal in text for signal in signals):
            roles.append(role)
    # Always include verification
    if "verify" not in roles:
        roles.append("verify")
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for r in roles:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


# ══════════════════════════════════════════════════════════════
#  AGENT FACTORY
# ══════════════════════════════════════════════════════════════

class AgentFactory:
    """Creates dynamic specialized agents for a mission."""

    def __init__(self, workspace_id: str = "", llm_call: Optional[Callable] = None):
        self.workspace_id = workspace_id
        self.llm_call = llm_call or self._default_llm
        self._agents: Dict[str, AgentSpec] = {}

    def build_team(self, objective: str, context: Dict = None) -> List[AgentSpec]:
        """Analyze objective and create the right team of agents."""
        roles = analyze_task(objective)
        team = []
        for role in roles:
            spec = AgentSpec(
                id=f"{role}_{uuid.uuid4().hex[:6]}",
                role=role,
                objective=self._derive_objective(role, objective),
                tools=ROLE_TOOLS.get(role, ["file_system"]),
                permissions=ROLE_PERMISSIONS.get(role, ["read_file"]),
                context=context or {},
                verification_criteria=self._derive_criteria(role, objective),
            )
            self._agents[spec.id] = spec
            team.append(spec)
            log.info(f"[FACTORY] Created {role} agent: {spec.id}")
        return team

    def get_agent(self, agent_id: str) -> Optional[AgentSpec]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentSpec]:
        return list(self._agents.values())

    def _derive_objective(self, role: str, mission: str) -> str:
        """Derive a specific objective for a role from the mission."""
        templates = {
            "research": f"Research and gather information relevant to: {mission}",
            "code": f"Write code and implement: {mission}",
            "browser": f"Browse the web and interact with pages for: {mission}",
            "design": f"Design the visual/UX for: {mission}",
            "verify": f"Verify the work completed for: {mission}",
            "deploy": f"Deploy and publish the result of: {mission}",
            "file": f"Organize and manage files for: {mission}",
            "data": f"Process and transform data for: {mission}",
            "media": f"Create and process media for: {mission}",
            "communication": f"Handle communications for: {mission}",
        }
        return templates.get(role, f"{role}: {mission}")

    def _derive_criteria(self, role: str, mission: str) -> str:
        """Define verification criteria for a role."""
        criteria = {
            "research": "Information gathered, sources cited, summary provided",
            "code": "Code written, files created, no syntax errors",
            "browser": "Pages loaded, data extracted, screenshots captured",
            "design": "Design files created, visual assets generated",
            "verify": "All tests pass, output matches expected result",
            "deploy": "Deployment confirmed, URL accessible",
            "file": "Files organized correctly, structure matches plan",
            "data": "Data processed, output file created and valid",
            "media": "Media files created, correct format and quality",
            "communication": "Message sent, confirmation received",
        }
        return criteria.get(role, "Task completed successfully")

    def _default_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """Default LLM call — tries groq_agent, falls back to echo."""
        try:
            from groq_agent import call_llm
            return call_llm(prompt, max_tokens=max_tokens)
        except Exception:
            return f"[LLM unavailable] Would process: {prompt[:80]}..."


# ══════════════════════════════════════════════════════════════
#  SINGLETON
# ══════════════════════════════════════════════════════════════

_factory: Optional[AgentFactory] = None


def get_agent_factory(workspace_id: str = "") -> AgentFactory:
    global _factory
    if _factory is None:
        _factory = AgentFactory(workspace_id=workspace_id)
    return _factory


def reset_factory():
    global _factory
    _factory = None
