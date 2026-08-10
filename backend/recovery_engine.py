"""JARVIS Recovery Engine — Mission-Level Recovery + Replanning.

When an action fails, the recovery engine:
1. Retries with backoff
2. Tries alternative approaches
3. Replans the entire mission if needed
4. Learns from failures to avoid them next time

KEY INSIGHT: Pursue the GOAL, not the original plan.
A failed plan is just a failed hypothesis about how to reach the goal.
"""

import time
import logging
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field

log = logging.getLogger("recovery")


@dataclass
class RecoveryAttempt:
    """A single recovery attempt."""
    timestamp: float
    action: str
    result: str  # "success", "failed", "alternative"
    error: str = ""
    duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class RecoveryStrategy:
    """A strategy for recovering from failure."""
    name: str
    description: str
    handler: Optional[Callable] = None
    priority: int = 0  # Lower = tried first
    applicable_errors: List[str] = field(default_factory=list)


class RecoveryEngine:
    """Mission-level recovery and replanning.

    When an action fails, this engine determines the best recovery:
    - Retry (transient error)
    - Alternative approach (wrong method)
    - Replan (wrong strategy)
    - Escalate (needs human help)
    - Abort (impossible task)
    """

    def __init__(self, planner=None, evidence_ledger=None):
        self._planner = planner
        self._evidence = evidence_ledger
        self._strategies: List[RecoveryStrategy] = []
        self._failure_patterns: Dict[str, int] = {}  # error_type -> count
        self._recovery_history: List[RecoveryAttempt] = []

        self._register_default_strategies()

    def _register_default_strategies(self):
        """Register built-in recovery strategies."""
        self._strategies = [
            RecoveryStrategy(
                name="retry_with_backoff",
                description="Retry the failed action with increasing delay",
                priority=0,
                applicable_errors=["timeout", "temporary", "busy", "rate_limit"],
            ),
            RecoveryStrategy(
                name="alternative_approach",
                description="Try a different method to achieve the same result",
                priority=1,
                applicable_errors=["not_found", "permission", "unavailable"],
            ),
            RecoveryStrategy(
                name="replan",
                description="Replan the mission from current state",
                priority=2,
                applicable_errors=["wrong_method", "impossible", "stuck"],
            ),
            RecoveryStrategy(
                name="ask_user",
                description="Ask the user for clarification or permission",
                priority=3,
                applicable_errors=["ambiguous", "permission_required", "unclear"],
            ),
            RecoveryStrategy(
                name="skip_and_continue",
                description="Skip failed step, continue with rest of plan",
                priority=4,
                applicable_errors=["optional", "non_critical"],
            ),
            RecoveryStrategy(
                name="abort",
                description="Abort mission, report failure to user",
                priority=5,
                applicable_errors=["fatal", "impossible"],
            ),
        ]

    async def handle_failure(self, mission_id: str, step_id: str,
                            error: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle a step failure. Returns recovery action to take.

        Returns:
            {
                "action": "retry" | "alternative" | "replan" | "ask" | "skip" | "abort",
                "reason": "...",
                "alternative": {...},  # if action == "alternative"
            }
        """
        context = context or {}
        now = time.time()

        log.warning(f"[RECOVERY] Step {step_id} failed: {error}")

        # Track failure pattern
        error_type = self._classify_error(error)
        self._failure_patterns[error_type] = self._failure_patterns.get(error_type, 0) + 1

        # Determine recovery strategy
        strategy = self._select_strategy(error_type, context)

        attempt = RecoveryAttempt(
            timestamp=now, action=strategy.name,
            result="attempting", error=error,
        )

        recovery = {"action": "", "reason": "", "alternative": None}

        if strategy.name == "retry_with_backoff":
            delay = min(2 ** context.get("retry_count", 0), 30)
            recovery = {
                "action": "retry",
                "reason": f"Transient error, retrying after {delay}s",
                "delay_seconds": delay,
            }

        elif strategy.name == "alternative_approach":
            alternative = await self._find_alternative(
                mission_id, step_id, error, context
            )
            recovery = {
                "action": "alternative",
                "reason": f"Primary method failed, trying: {alternative.get('description', 'unknown')}",
                "alternative": alternative,
            }

        elif strategy.name == "replan":
            if self._planner:
                plan = await self._planner.replan(mission_id, step_id, error, context)
                recovery = {
                    "action": "replan",
                    "reason": "Mission replanned from current state",
                    "new_plan": plan.to_dict() if hasattr(plan, 'to_dict') else None,
                }
            else:
                recovery = {
                    "action": "abort",
                    "reason": "Cannot replan without planner",
                }

        elif strategy.name == "ask_user":
            recovery = {
                "action": "ask",
                "reason": f"Need user input: {self._format_user_question(error, context)}",
                "question": self._format_user_question(error, context),
            }

        elif strategy.name == "skip_and_continue":
            recovery = {
                "action": "skip",
                "reason": "Step is non-critical, continuing",
            }

        elif strategy.name == "abort":
            recovery = {
                "action": "abort",
                "reason": f"Mission cannot continue: {error}",
            }

        attempt.result = recovery["action"]
        self._recovery_history.append(attempt)

        log.info(f"[RECOVERY] Strategy: {strategy.name} → action: {recovery['action']}")
        return recovery

    def _classify_error(self, error: str) -> str:
        """Classify an error into a category."""
        error_lower = error.lower()

        if any(w in error_lower for w in ["timeout", "timed out", "slow"]):
            return "timeout"
        if any(w in error_lower for w in ["not found", "no such", "doesn't exist"]):
            return "not_found"
        if any(w in error_lower for w in ["permission", "denied", "access"]):
            return "permission"
        if any(w in error_lower for w in ["rate limit", "too many"]):
            return "rate_limit"
        if any(w in error_lower for w in ["network", "connection", "dns"]):
            return "temporary"
        if any(w in error_lower for w in ["ambiguous", "unclear", "which"]):
            return "ambiguous"
        if any(w in error_lower for w in ["impossible", "cannot", "unable"]):
            return "impossible"
        if any(w in error_lower for w in ["stuck", "loop", "infinite"]):
            return "stuck"
        if any(w in error_lower for w in ["fatal", "crash", "critical"]):
            return "fatal"

        return "unknown"

    def _select_strategy(self, error_type: str,
                        context: Dict[str, Any]) -> RecoveryStrategy:
        """Select the best recovery strategy."""
        retry_count = context.get("retry_count", 0)
        is_critical = context.get("risk_level") == "critical"
        step_importance = context.get("importance", "normal")

        # Don't retry forever
        if retry_count >= 3:
            return self._find_strategy("replan")

        # For transient errors, retry first
        if error_type in ("timeout", "temporary", "rate_limit") and retry_count < 3:
            return self._find_strategy("retry_with_backoff")

        # For not found, try alternatives
        if error_type == "not_found":
            return self._find_strategy("alternative_approach")

        # For permission, ask user
        if error_type == "permission":
            return self._find_strategy("ask_user")

        # For ambiguous, ask user
        if error_type == "ambiguous":
            return self._find_strategy("ask_user")

        # For critical missions, try harder
        if is_critical and retry_count < 2:
            return self._find_strategy("alternative_approach")

        # Default: replan
        return self._find_strategy("replan")

    def _find_strategy(self, name: str) -> RecoveryStrategy:
        """Find a strategy by name."""
        for s in self._strategies:
            if s.name == name:
                return s
        return self._strategies[-1]  # abort

    async def _find_alternative(self, mission_id: str, step_id: str,
                               error: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Find an alternative approach for a failed step."""
        failed_primitives = context.get("primitives_used", [])
        goal = context.get("goal", "")

        # Common alternatives
        alternatives = {
            "click": [
                {"primitives": ["find", "click"], "description": "Find element first, then click"},
                {"primitives": ["type"], "description": "Type keyboard shortcut instead"},
            ],
            "find": [
                {"primitives": ["search"], "description": "Use text search instead"},
                {"primitives": ["screenshot"], "description": "Take screenshot and look visually"},
            ],
            "navigate": [
                {"primitives": ["launch", "wait"], "description": "Open app directly"},
                {"primitives": ["execute"], "description": "Use command line instead"},
            ],
            "type": [
                {"primitives": ["click", "type"], "description": "Click field first, then type"},
                {"primitives": ["execute"], "description": "Use paste from clipboard"},
            ],
        }

        # Find alternatives for the first failed primitive
        for prim in failed_primitives:
            if prim in alternatives:
                for alt in alternatives[prim]:
                    if alt["primitives"][0] not in failed_primitives:
                        return alt

        # Generic alternative: use a different tool entirely
        return {
            "primitives": ["screenshot", "find"],
            "description": "Take screenshot and find alternative element",
        }

    def _format_user_question(self, error: str, context: Dict[str, Any]) -> str:
        """Format a question for the user."""
        goal = context.get("goal", "the current task")
        return (
            f"I'm trying to {goal}, but encountered: {error}. "
            f"How would you like me to proceed?"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        return {
            "total_attempts": len(self._recovery_history),
            "failure_patterns": dict(self._failure_patterns),
            "recent_attempts": [
                a.to_dict() for a in self._recovery_history[-10:]
            ],
        }


# ── Singleton ──
_recovery: Optional[RecoveryEngine] = None


def get_recovery_engine(planner=None, evidence_ledger=None) -> RecoveryEngine:
    global _recovery
    if _recovery is None:
        _recovery = RecoveryEngine(planner, evidence_ledger)
    return _recovery
