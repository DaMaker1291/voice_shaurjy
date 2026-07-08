#!/usr/bin/env python3
"""
Error Recovery Engine for JARVIS
Handles failures gracefully: retries, alternatives, adaptation, navigation around obstacles.
"""
import time
import traceback
from typing import Dict, Any, List, Optional, Callable

class ErrorRecoveryEngine:
    """
    When a step fails, this engine:
    1. Classifies the error type
    2. Determines if retry is appropriate
    3. Suggests alternative approaches
    4. Adapts the remaining workflow
    5. Reports recovery status
    """

    # Error classifications
    ERROR_TYPES = {
        "network": ["connection", "timeout", "network", "unreachable", "dns", "refused"],
        "element_not_found": ["not found", "no such element", "missing", "selector", "xpath"],
        "page_load": ["page crashed", "navigation failed", "load timeout", "page expired"],
        "rate_limit": ["429", "rate limit", "too many requests", "throttle"],
        "auth": ["401", "403", "unauthorized", "forbidden", "login", "expired"],
        "captcha": ["captcha", "verification", "bot detection", "challenge"],
        "permission": ["permission denied", "access denied", "not allowed"],
        "not_found": ["404", "not found", "does not exist", "no results"],
        "server_error": ["500", "502", "503", "server error", "internal error"],
        "browser": ["chrome", "browser", "cdp", "devtools", "websocket"],
        "unknown": [],
    }

    # Alternative strategies per error type
    ALTERNATIVES = {
        "network": [
            {"action": "wait_and_retry", "description": "Wait 5s and retry", "params": {"seconds": 5}},
            {"action": "try_different_url", "description": "Try alternative URL"},
            {"action": "use_cached_version", "description": "Use cached page version"},
            {"action": "skip_step", "description": "Skip this step and continue"},
        ],
        "element_not_found": [
            {"action": "wait_longer", "description": "Wait longer for element", "params": {"seconds": 10}},
            {"action": "try_different_selector", "description": "Try alternative CSS selector"},
            {"action": "scroll_and_retry", "description": "Scroll page and retry"},
            {"action": "use_javascript", "description": "Use JavaScript to find element"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "page_load": [
            {"action": "wait_and_reload", "description": "Wait and reload page"},
            {"action": "try_different_browser", "description": "Try different browser approach"},
            {"action": "navigate_directly", "description": "Navigate directly to URL"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "rate_limit": [
            {"action": "exponential_backoff", "description": "Wait with exponential backoff", "params": {"base_seconds": 10}},
            {"action": "try_different_endpoint", "description": "Try alternative endpoint"},
            {"action": "reduce_request_size", "description": "Reduce request complexity"},
            {"action": "wait_and_retry", "description": "Wait and retry", "params": {"seconds": 30}},
        ],
        "auth": [
            {"action": "refresh_credentials", "description": "Refresh authentication tokens"},
            {"action": "try_different_account", "description": "Try alternative account"},
            {"action": "use_api_key", "description": "Use API key instead"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "captcha": [
            {"action": "wait_for_human", "description": "Wait for human to solve captcha"},
            {"action": "try_different_site", "description": "Try alternative site"},
            {"action": "use_api", "description": "Use API instead of web"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "not_found": [
            {"action": "search_alternatively", "description": "Search for content differently"},
            {"action": "try_related_page", "description": "Try related page"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "server_error": [
            {"action": "wait_and_retry", "description": "Wait for server to recover", "params": {"seconds": 15}},
            {"action": "try_mirror", "description": "Try mirror/backup site"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "browser": [
            {"action": "restart_browser", "description": "Restart headless browser"},
            {"action": "wait_and_retry", "description": "Wait for browser to stabilize", "params": {"seconds": 5}},
            {"action": "skip_step", "description": "Skip browser step"},
        ],
        "permission": [
            {"action": "try_different_approach", "description": "Try alternative approach"},
            {"action": "request_access", "description": "Request access/permission"},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
        "unknown": [
            {"action": "wait_and_retry", "description": "Wait and retry once", "params": {"seconds": 5}},
            {"action": "skip_step", "description": "Skip and continue"},
        ],
    }

    def __init__(self):
        self.error_history = []
        self.recovery_stats = {"total_errors": 0, "recovered": 0, "skipped": 0}

    def classify_error(self, error: str) -> str:
        """Classify an error message into an error type."""
        lower = error.lower()
        for error_type, keywords in self.ERROR_TYPES.items():
            if error_type == "unknown":
                continue
            for keyword in keywords:
                if keyword in lower:
                    return error_type
        return "unknown"

    def handle_error(self, error: str, step: dict, workflow: list, current_index: int) -> Dict[str, Any]:
        """
        Handle a failed step. Returns recovery strategy.
        """
        self.recovery_stats["total_errors"] += 1
        error_type = self.classify_error(error)
        alternatives = self.ALTERNATIVES.get(error_type, self.ALTERNATIVES["unknown"])

        # Log the error
        self.error_history.append({
            "time": time.time(),
            "step": step.get("description", "unknown"),
            "error": error,
            "error_type": error_type,
            "step_index": current_index,
        })

        # Determine best recovery action
        max_retries = step.get("max_retries", 2)
        retry_count = step.get("retry_count", 0)

        if retry_count < max_retries:
            # Retry the same step
            return {
                "strategy": "retry",
                "action": "retry_step",
                "description": f"Retrying step (attempt {retry_count + 2}/{max_retries + 1})",
                "error_type": error_type,
                "alternatives": alternatives,
                "should_retry": True,
                "retry_delay": self._get_retry_delay(error_type, retry_count),
            }
        else:
            # Try alternatives
            alternative = alternatives[0] if alternatives else {"action": "skip_step", "description": "Skip step"}
            self.recovery_stats["skipped"] += 1

            return {
                "strategy": "alternative",
                "action": alternative["action"],
                "description": alternative["description"],
                "error_type": error_type,
                "alternatives": alternatives,
                "should_retry": False,
                "skip_to": self._find_skip_target(workflow, current_index, error_type),
            }

    def _get_retry_delay(self, error_type: str, retry_count: int) -> float:
        """Calculate retry delay based on error type and attempt number."""
        base_delays = {
            "rate_limit": 15,
            "network": 5,
            "page_load": 8,
            "browser": 5,
            "server_error": 10,
        }
        base = base_delays.get(error_type, 3)
        return base * (2 ** retry_count)  # Exponential backoff

    def _find_skip_target(self, workflow: list, current_index: int, error_type: str) -> Optional[int]:
        """Find the next safe index to skip to after a failure."""
        # For most errors, try the next step
        if error_type in ["element_not_found", "not_found", "permission"]:
            # Skip ahead to next non-optional step
            for i in range(current_index + 1, len(workflow)):
                if not workflow[i].get("optional", False):
                    return i
        return current_index + 1

    def adapt_workflow(self, workflow: list, failed_index: int, error_type: str) -> list:
        """
        Adapt the remaining workflow after a failure.
        Can modify, remove, or reorder remaining steps.
        """
        adapted = workflow.copy()

        if error_type == "captcha":
            # After captcha, skip similar web steps
            for i in range(failed_index + 1, len(adapted)):
                if adapted[i].get("action", "").startswith("browser_"):
                    adapted[i]["skip_if_failed"] = True

        elif error_type == "auth":
            # After auth failure, skip actions requiring login
            for i in range(failed_index + 1, len(adapted)):
                if adapted[i].get("requires_auth", False):
                    adapted[i]["skip_if_failed"] = True

        elif error_type == "browser":
            # After browser failure, prefer non-browser alternatives
            for i in range(failed_index + 1, len(adapted)):
                if adapted[i].get("action", "").startswith("browser_"):
                    adapted[i]["prefer_alternative"] = True

        return adapted

    def get_recovery_summary(self) -> Dict:
        """Get summary of error recovery activity."""
        return {
            "total_errors": self.recovery_stats["total_errors"],
            "recovered": self.recovery_stats["recovered"],
            "skipped": self.recovery_stats["skipped"],
            "recovery_rate": (
                self.recovery_stats["recovered"] / max(self.recovery_stats["total_errors"], 1)
            ),
            "recent_errors": self.error_history[-10:],
        }

    def mark_recovered(self):
        """Mark an error as successfully recovered."""
        self.recovery_stats["recovered"] += 1


# Singleton
_recovery = None

def get_recovery_engine() -> ErrorRecoveryEngine:
    global _recovery
    if _recovery is None:
        _recovery = ErrorRecoveryEngine()
    return _recovery
