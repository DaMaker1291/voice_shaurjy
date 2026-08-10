"""JARVIS Verification Engine — Verify results against reality.

The key insight: agents say "done" but nothing happened.
This engine checks if actions actually succeeded.

Flow:
    AGENT → ACTION → OBSERVE RESULT → VERIFY
                                      ├── SUCCESS → continue
                                      └── FAILURE → DIAGNOSE → REPAIR → RETRY
"""

import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

log = logging.getLogger("verification_engine")


@dataclass
class VerificationResult:
    success: bool
    action: str
    expected: str
    actual: str
    diagnosis: str = ""
    repair_hint: str = ""
    retry_approved: bool = False

    def to_dict(self):
        return {
            "success": self.success, "action": self.action,
            "expected": self.expected, "actual": self.actual,
            "diagnosis": self.diagnosis, "repair_hint": self.repair_hint,
            "retry_approved": self.retry_approved,
        }


class VerificationEngine:
    """Verifies that agent actions produced real results."""

    def __init__(self, workspace_dir: str = ""):
        self.workspace_dir = workspace_dir

    def verify(self, action: str, params: dict, result: dict) -> VerificationResult:
        """Verify an action's result against reality."""
        if action == "write_file":
            return self._verify_write_file(params, result)
        elif action == "run_command":
            return self._verify_run_command(params, result)
        elif action == "create_directory":
            return self._verify_create_directory(params, result)
        elif action == "read_file":
            return self._verify_read_file(params, result)
        elif action == "web_search":
            return self._verify_web_search(params, result)
        elif action == "web_scrape":
            return self._verify_web_scrape(params, result)
        elif action == "navigate_web":
            return self._verify_navigate_web(params, result)
        elif action == "launch_app":
            return self._verify_launch_app(params, result)
        elif action == "screenshot":
            return self._verify_screenshot(params, result)
        else:
            # Unknown action — trust the result
            return VerificationResult(
                success=result.get("ok", False),
                action=action, expected="completed",
                actual=result.get("output", "unknown"),
            )

    def _verify_write_file(self, params: dict, result: dict) -> VerificationResult:
        path = params.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(self.workspace_dir, path)
        exists = os.path.isfile(path)
        size = os.path.getsize(path) if exists else 0
        return VerificationResult(
            success=exists and size > 0,
            action="write_file",
            expected=f"File exists at {path} with content",
            actual=f"exists={exists}, size={size} bytes",
            diagnosis="" if exists else "File was not created",
            repair_hint="Retry with absolute path or check permissions" if not exists else "",
            retry_approved=not exists,
        )

    def _verify_run_command(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        stdout = result.get("output", "")
        stderr = result.get("error", "")
        return VerificationResult(
            success=ok and not stderr,
            action="run_command",
            expected="Command executed successfully",
            actual=f"stdout={stdout[:100]}, stderr={stderr[:100]}",
            diagnosis="" if ok else f"Command failed: {stderr[:200]}",
            repair_hint="Check command syntax and dependencies" if not ok else "",
            retry_approved=not ok,
        )

    def _verify_create_directory(self, params: dict, result: dict) -> VerificationResult:
        path = params.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(self.workspace_dir, path)
        exists = os.path.isdir(path)
        return VerificationResult(
            success=exists,
            action="create_directory",
            expected=f"Directory exists at {path}",
            actual=f"exists={exists}",
            diagnosis="" if exists else "Directory was not created",
            repair_hint="Check parent directory permissions" if not exists else "",
            retry_approved=not exists,
        )

    def _verify_read_file(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        content = result.get("output", "")
        return VerificationResult(
            success=ok and len(content) > 0,
            action="read_file",
            expected="File content returned",
            actual=f"content_length={len(content)}",
            diagnosis="" if ok else "Could not read file",
            repair_hint="Check file exists and is readable" if not ok else "",
            retry_approved=False,
        )

    def _verify_web_search(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        output = result.get("output", "")
        has_results = len(output) > 20
        return VerificationResult(
            success=ok and has_results,
            action="web_search",
            expected="Search results returned",
            actual=f"results_length={len(output)}",
            diagnosis="" if ok else "Search failed or returned no results",
            repair_hint="Try different query or check network" if not ok else "",
            retry_approved=not ok,
        )

    def _verify_web_scrape(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        text = result.get("output", "")
        return VerificationResult(
            success=ok and len(text) > 50,
            action="web_scrape",
            expected="Page content extracted",
            actual=f"text_length={len(text)}",
            diagnosis="" if ok else "Could not scrape page",
            repair_hint="Check URL is accessible and page loads" if not ok else "",
            retry_approved=not ok,
        )

    def _verify_navigate_web(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        return VerificationResult(
            success=ok,
            action="navigate_web",
            expected="Browser opened to URL",
            actual="launched" if ok else "failed",
            diagnosis="" if ok else "Could not open browser",
            repair_hint="Check default browser is set" if not ok else "",
            retry_approved=not ok,
        )

    def _verify_launch_app(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        return VerificationResult(
            success=ok,
            action="launch_app",
            expected="Application launched",
            actual="launched" if ok else "failed",
            diagnosis="" if ok else "Could not launch application",
            repair_hint="Check application is installed" if not ok else "",
            retry_approved=not ok,
        )

    def _verify_screenshot(self, params: dict, result: dict) -> VerificationResult:
        ok = result.get("ok", False)
        has_data = bool(result.get("screenshot"))
        return VerificationResult(
            success=ok and has_data,
            action="screenshot",
            expected="Screenshot captured",
            actual=f"has_data={has_data}",
            diagnosis="" if ok else "Could not capture screenshot",
            repair_hint="Check display is available" if not ok else "",
            retry_approved=False,
        )


# ══════════════════════════════════════════════════════════════
#  SINGLETON
# ══════════════════════════════════════════════════════════════

_engine: Optional[VerificationEngine] = None


def get_verification_engine(workspace_dir: str = "") -> VerificationEngine:
    global _engine
    if _engine is None:
        _engine = VerificationEngine(workspace_dir=workspace_dir)
    _engine.workspace_dir = workspace_dir
    return _engine
