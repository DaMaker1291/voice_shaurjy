"""JARVIS Task Router — selects the right backend for each task.

The user doesn't see this. JARVIS decides automatically.
"""

import logging
from typing import Optional, Dict, List, Tuple
from workspace_backend import (
    WorkspaceBackend, ExecutionContext, ExecutionResult,
    get_available_backends, get_backend,
)

log = logging.getLogger("task_router")


# Task type → preferred backend order (first available wins)
TASK_BACKEND_MAP = {
    # Browser tasks → native Chrome/CDP
    "browser": ["native"],
    "web_search": ["native"],
    "web_scrape": ["native"],
    "navigate_web": ["native"],

    # File tasks → native or sandbox
    "files": ["sandbox", "native"],
    "write_file": ["sandbox", "native"],
    "read_file": ["sandbox", "native"],
    "create_directory": ["sandbox", "native"],

    # Command execution → depends on risk
    "command_low": ["native"],
    "command_high": ["sandbox"],

    # App launch → native
    "app": ["native"],
    "launch_app": ["native"],

    # GPU tasks → remote (future)
    "gpu": ["remote", "native"],

    # Dangerous/untrusted → sandbox
    "untrusted": ["sandbox"],
    "unknown": ["sandbox"],
}

# Risk level → backend override
RISK_BACKEND_MAP = {
    "low": None,       # Use task type mapping
    "medium": None,    # Use task type mapping
    "high": "sandbox", # Always sandbox for high-risk
}


def classify_task(action: str, params: dict) -> str:
    """Classify an action into a task type for routing."""
    if action in ("web_search", "web_scrape", "navigate_web"):
        return action
    if action in ("write_file", "read_file", "create_directory"):
        return action
    if action == "run_command":
        return "command_low"  # Risk level handled separately
    if action == "launch_app":
        return "launch_app"
    if action in ("click", "type_text", "press_key"):
        return "browser"
    if action == "screenshot":
        return "browser"
    if action == "wait":
        return "command_low"
    return "unknown"


def select_backend(
    action: str,
    params: dict,
    risk_level: str = "low",
    prefer: Optional[str] = None,
) -> Tuple[Optional[WorkspaceBackend], str]:
    """Select the best backend for a task.

    Returns (backend, reason).
    """
    available = get_available_backends()
    if not available:
        return None, "No backends available"

    # If a specific backend is preferred and available
    if prefer:
        b = get_backend(prefer)
        if b and b.is_available:
            return b, f"Preferred: {prefer}"

    # Check risk override
    risk_backend = RISK_BACKEND_MAP.get(risk_level)
    if risk_backend:
        b = get_backend(risk_backend)
        if b and b.is_available:
            return b, f"Risk override: {risk_level} → {risk_backend}"

    # Classify task and find backend
    task_type = classify_task(action, params)
    preferred_list = TASK_BACKEND_MAP.get(task_type, ["sandbox", "native"])

    for name in preferred_list:
        b = get_backend(name)
        if b and b.is_available:
            return b, f"Task router: {task_type} → {name}"

    # Fallback to cheapest available
    cheapest = min(available, key=lambda b: b.cost)
    return cheapest, f"Fallback: {cheapest.name}"


def route_and_execute(
    action: str,
    params: dict,
    workspace_id: str,
    risk_level: str = "low",
    timeout: int = 300,
    objective: str = "",
) -> ExecutionResult:
    """Route a task to the best backend and execute it."""
    backend, reason = select_backend(action, params, risk_level)
    if not backend:
        return ExecutionResult(ok=False, error="No backend available")

    log.info(f"[ROUTER] {action} → {backend.name} ({reason})")

    ctx = ExecutionContext(
        workspace_id=workspace_id,
        task_type=classify_task(action, params),
        objective=objective,
        risk_level=risk_level,
        timeout=timeout,
    )

    # Start backend if not running
    if not backend.is_running():
        if not backend.start(ctx):
            return ExecutionResult(ok=False, error=f"Failed to start {backend.name}")

    return backend.execute(ctx, action, params)
