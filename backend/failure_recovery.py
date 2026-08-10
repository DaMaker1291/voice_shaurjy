"""JARVIS Failure Recovery — Classify, Diagnose, Repair, Retry.

Classifies failures → selects recovery strategy → retries with budget.
Never retries blindly. Each attempt must be meaningfully different.
"""

import os, sys, json, logging, time, subprocess
from pathlib import Path

log = logging.getLogger("failure_recovery")

sys.path.insert(0, os.path.dirname(__file__))


class FailureType:
    NETWORK = "NETWORK"
    AUTH = "AUTH"
    PERMISSION = "PERMISSION"
    CAPTCHA = "CAPTCHA"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    BAD_OUTPUT = "BAD_OUTPUT"
    WRONG_STATE = "WRONG_STATE"
    TIMEOUT = "TIMEOUT"
    CHROME_DEAD = "CHROME_DEAD"
    VDI_DEAD = "VDI_DEAD"
    EMPTY_RESULT = "EMPTY_RESULT"
    UNKNOWN = "UNKNOWN"


class RecoveryAction:
    RETRY_SAME = "retry_same"
    RETRY_ALTERNATIVE = "retry_alternative"
    SWITCH_TOOL = "switch_tool"
    FIX_ENVIRONMENT = "fix_environment"
    RESTART_CHROME = "restart_chrome"
    RESTART_VDI = "restart_vdi"
    ASK_USER = "ask_user"
    ABORT = "abort"


FAILURE_STRATEGIES = {
    FailureType.NETWORK: {
        "attempts": [RecoveryAction.RETRY_SAME, RecoveryAction.RETRY_ALTERNATIVE, RecoveryAction.ASK_USER],
        "diagnose": "_diagnose_network",
    },
    FailureType.AUTH: {
        "attempts": [RecoveryAction.ASK_USER, RecoveryAction.ABORT],
        "diagnose": "_diagnose_auth",
    },
    FailureType.PERMISSION: {
        "attempts": [RecoveryAction.FIX_ENVIRONMENT, RecoveryAction.ABORT],
        "diagnose": "_diagnose_permission",
    },
    FailureType.CAPTCHA: {
        "attempts": [RecoveryAction.SWITCH_TOOL, RecoveryAction.ASK_USER],
        "diagnose": "_diagnose_captcha",
    },
    FailureType.MISSING_DEPENDENCY: {
        "attempts": [RecoveryAction.FIX_ENVIRONMENT, RecoveryAction.ABORT],
        "diagnose": "_diagnose_missing_dep",
    },
    FailureType.BAD_OUTPUT: {
        "attempts": [RecoveryAction.RETRY_ALTERNATIVE, RecoveryAction.RETRY_SAME, RecoveryAction.ASK_USER],
        "diagnose": "_diagnose_bad_output",
    },
    FailureType.WRONG_STATE: {
        "attempts": [RecoveryAction.FIX_ENVIRONMENT, RecoveryAction.RESTART_CHROME, RecoveryAction.ABORT],
        "diagnose": "_diagnose_wrong_state",
    },
    FailureType.TIMEOUT: {
        "attempts": [RecoveryAction.RETRY_SAME, RecoveryAction.RESTART_CHROME, RecoveryAction.RETRY_ALTERNATIVE],
        "diagnose": "_diagnose_timeout",
    },
    FailureType.CHROME_DEAD: {
        "attempts": [RecoveryAction.RESTART_CHROME, RecoveryAction.RETRY_SAME],
        "diagnose": "_diagnose_chrome_dead",
    },
    FailureType.VDI_DEAD: {
        "attempts": [RecoveryAction.RESTART_VDI, RecoveryAction.RETRY_SAME],
        "diagnose": "_diagnose_vdi_dead",
    },
    FailureType.EMPTY_RESULT: {
        "attempts": [RecoveryAction.RETRY_ALTERNATIVE, RecoveryAction.SWITCH_TOOL, RecoveryAction.ASK_USER],
        "diagnose": "_diagnose_empty_result",
    },
    FailureType.UNKNOWN: {
        "attempts": [RecoveryAction.RETRY_SAME, RecoveryAction.RETRY_ALTERNATIVE, RecoveryAction.ASK_USER],
        "diagnose": None,
    },
}


class RecoveryEngine:
    """Diagnoses failures and applies recovery strategies."""

    def __init__(self, max_budget: int = 5):
        self.max_budget = max_budget

    def classify(self, error: str, context: dict = None) -> str:
        """Classify a failure from error message and context."""
        e = (error or "").lower()
        ctx = context or {}

        if "network" in e or "connection" in e or "resolve" in e or "timeout" in e:
            return FailureType.TIMEOUT if "timeout" in e else FailureType.NETWORK

        if "permission denied" in e or "403" in e or "forbidden" in e:
            return FailureType.PERMISSION

        if "no such file" in e or "not found" in e and "command" in e:
            return FailureType.MISSING_DEPENDENCY

        if "captcha" in e or "verify you" in e or "blocked" in e:
            return FailureType.CAPTCHA

        if "chrome" in e and ("died" in e or "crash" in e or "not found" in e):
            return FailureType.CHROME_DEAD

        if "xvfb" in e or "display" in e or "vdi" in e:
            return FailureType.VDI_DEAD

        if "empty" in e or "no output" in e or "no prices" in e:
            return FailureType.EMPTY_RESULT

        if ctx.get("exit_code") and ctx["exit_code"] != 0:
            if "timeout" in e:
                return FailureType.TIMEOUT
            return FailureType.BAD_OUTPUT

        return FailureType.UNKNOWN

    def get_strategy(self, failure_type: str, attempt: int) -> str:
        """Get recovery action for this attempt number."""
        strategy = FAILURE_STRATEGIES.get(failure_type, FAILURE_STRATEGIES[FailureType.UNKNOWN])
        actions = strategy["attempts"]
        if attempt < len(actions):
            return actions[attempt]
        return RecoveryAction.ABORT

    def diagnose(self, failure_type: str, error: str, context: dict = None) -> dict:
        """Run diagnosis for a failure type."""
        strategy = FAILURE_STRATEGIES.get(failure_type, {})
        diagnose_fn = strategy.get("diagnose")

        diagnosis = {
            "type": failure_type,
            "error": error[:200],
            "context": context or {},
            "possible_causes": [],
            "suggested_fix": None,
        }

        if failure_type == FailureType.NETWORK:
            diagnosis["possible_causes"] = ["Proxy dead", "Site blocked", "DNS failure", "No internet"]
            diagnosis["suggested_fix"] = "Try different proxy or use direct connection"

        elif failure_type == FailureType.CHROME_DEAD:
            diagnosis["possible_causes"] = ["Chrome crashed", "OOM killed", "Display error"]
            diagnosis["suggested_fix"] = "Kill and restart Chrome"

        elif failure_type == FailureType.VDI_DEAD:
            diagnosis["possible_causes"] = ["Xvfb crashed", "Systemd service down", "Display :99 gone"]
            diagnosis["suggested_fix"] = "Restart vdi-streamer.service"

        elif failure_type == FailureType.EMPTY_RESULT:
            diagnosis["possible_causes"] = [
                "Page didn't load",
                "Prices on dynamic elements not captured",
                "Site uses JavaScript rendering",
                "Clipboard extraction failed",
            ]
            diagnosis["suggested_fix"] = "Try scrolling more, wait longer, or try different site"

        elif failure_type == FailureType.PERMISSION:
            diagnosis["possible_causes"] = ["Need sudo", "File owned by root", "X11 auth issue"]
            diagnosis["suggested_fix"] = "Check file permissions and user context"

        return diagnosis

    def execute_recovery(self, failure_type: str, action: str, context: dict = None) -> dict:
        """Execute a recovery action. Returns {success, message}."""
        ctx = context or {}

        if action == RecoveryAction.RESTART_CHROME:
            return self._restart_chrome()

        if action == RecoveryAction.RESTART_VDI:
            return self._restart_vdi()

        if action == RecoveryAction.FIX_ENVIRONMENT:
            return self._fix_environment(ctx)

        if action == RecoveryAction.SWITCH_TOOL:
            return {"success": True, "message": "Switch to alternative approach",
                    "switch_to": ctx.get("alternative_tool")}

        if action == RecoveryAction.RETRY_ALTERNATIVE:
            return {"success": True, "message": "Try alternative strategy",
                    "strategy": ctx.get("alternative_strategy")}

        if action == RecoveryAction.ASK_USER:
            return {"success": False, "message": "User intervention needed",
                    "question": ctx.get("user_question", "I need help with this task.")}

        if action == RecoveryAction.RETRY_SAME:
            return {"success": True, "message": "Retry same approach"}

        if action == RecoveryAction.ABORT:
            return {"success": False, "message": "Cannot recover. Aborting."}

        return {"success": False, "message": f"Unknown action: {action}"}

    def _restart_chrome(self) -> dict:
        try:
            subprocess.run(
                ["sudo", "-u", "#1001", "bash", "-c",
                 "ps -eo pid,comm | grep -wi chrome | awk '{print $1}' | xargs -r kill -9 2>/dev/null"],
                timeout=5, capture_output=True
            )
            time.sleep(2)
            subprocess.Popen(
                ["sudo", "-u", "#1001", "bash", "-c",
                 "DISPLAY=:99 nohup google-chrome --no-sandbox --disable-gpu > /dev/null 2>&1 &"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(5)
            return {"success": True, "message": "Chrome restarted"}
        except Exception as e:
            return {"success": False, "message": f"Chrome restart failed: {e}"}

    def _restart_vdi(self) -> dict:
        try:
            subprocess.run(
                ["systemctl", "restart", "vdi-streamer.service"],
                timeout=10, capture_output=True
            )
            time.sleep(3)
            return {"success": True, "message": "VDI streamer restarted"}
        except Exception as e:
            return {"success": False, "message": f"VDI restart failed: {e}"}

    def _fix_environment(self, ctx: dict) -> dict:
        fixes_applied = []

        if ctx.get("display_missing"):
            try:
                subprocess.run(
                    ["bash", "-c", "ps -eo comm | grep -q Xvfb || (Xvfb :99 -screen 0 1920x1080x24 &)"],
                    timeout=5, capture_output=True
                )
                fixes_applied.append("Started Xvfb")
            except Exception:
                pass

        if ctx.get("needs_pip"):
            pkg = ctx.get("pip_package", "")
            if pkg:
                try:
                    subprocess.run(
                        ["pip3", "install", "--break-system-packages", pkg],
                        timeout=30, capture_output=True
                    )
                    fixes_applied.append(f"Installed {pkg}")
                except Exception:
                    pass

        if fixes_applied:
            return {"success": True, "message": "; ".join(fixes_applied)}
        return {"success": False, "message": "No fixes applicable"}


def wrap_with_recovery(fn, *args, max_budget=5, context=None, **kwargs):
    """Execute a function with automatic failure recovery.

    Returns (success, result, recovery_log)
    """
    engine = RecoveryEngine(max_budget)
    recovery_log = []

    for attempt in range(max_budget):
        try:
            result = fn(*args, **kwargs)
            if isinstance(result, dict) and result.get("error"):
                error = result["error"]
            elif isinstance(result, Exception):
                error = str(result)
            else:
                return True, result, recovery_log

        except Exception as e:
            error = str(e)

        failure_type = engine.classify(error, context)
        diagnosis = engine.diagnose(failure_type, error, context)
        action = engine.get_strategy(failure_type, attempt)

        log.warning(f"Attempt {attempt+1}/{max_budget} failed: {failure_type} → {action}")
        recovery_log.append({
            "attempt": attempt + 1,
            "failure_type": failure_type,
            "diagnosis": diagnosis,
            "action": action,
        })

        if action == RecoveryAction.ABORT:
            return False, {"error": error, "type": failure_type, "recovery_log": recovery_log}, recovery_log

        if action == RecoveryAction.ASK_USER:
            return False, {"error": error, "type": failure_type,
                          "needs_human": True,
                          "question": diagnosis.get("suggested_fix", "Need help"),
                          "recovery_log": recovery_log}, recovery_log

        recovery_result = engine.execute_recovery(failure_type, action, context)
        log.info(f"Recovery {action}: {recovery_result.get('message', '')}")

    return False, {"error": "Exhausted all recovery attempts", "recovery_log": recovery_log}, recovery_log
