"""
JARVIS Self-Healing Tool Synthesis Engine
==========================================
Catches failures → LLM-based repair generation → vault sandbox validation
→ permanent tool library storage. Fully wired into the agent router pipeline.
"""

import os
import json
import time
import hashlib
import traceback
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass, field

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "local_tools")
REPAIR_LOG = os.path.join(os.path.dirname(__file__), "healing_log.jsonl")


@dataclass
class RepairAttempt:
    tool_name: str
    original_error: str
    stack_trace: str
    repaired_code: str
    validation_passed: bool
    stored: bool
    timestamp: float = field(default_factory=time.time)
    repair_time_ms: int = 0


class SelfHealingEngine:
    """
    Self-healing loop: error → supervisor re-route → LLM repair →
    sandbox validation → permanent tool library storage.
    """

    def __init__(self):
        os.makedirs(TOOLS_DIR, exist_ok=True)
        self._vault = None
        self._repair_cache: Dict[str, str] = {}  # error_hash → repaired_code
        self._attempt_log: List[RepairAttempt] = []

    def _get_vault(self):
        if self._vault is None:
            try:
                from execution_vault import get_vault
                self._vault = get_vault()
            except ImportError:
                self._vault = False
        return self._vault if self._vault is not False else None

    def register_tool(
        self,
        tool_name: str,
        code_body: str,
        language: str = "python",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store a validated tool in the permanent library."""
        vault = self._get_vault()
        if vault:
            return vault.register_tool(tool_name, code_body, language, metadata)

        # Fallback: direct file write
        clean_name = "".join(c for c in tool_name if c.isalnum() or c in ("_", "-")).lower()
        filepath = os.path.join(TOOLS_DIR, f"{clean_name}.py")
        with open(filepath, "w") as f:
            f.write("# JARVIS AUTO-SYNTHESIZED TOOL\n")
            if metadata:
                f.write(f"# Metadata: {json.dumps(metadata)}\n\n")
            f.write(code_body)
        return filepath

    def list_tools(self) -> List[Dict]:
        """List all synthesized tools."""
        vault = self._get_vault()
        if vault:
            return vault.list_tools()

        tools = []
        if not os.path.isdir(TOOLS_DIR):
            return tools
        for fname in os.listdir(TOOLS_DIR):
            if fname.endswith(".py"):
                fpath = os.path.join(TOOLS_DIR, fname)
                tools.append({
                    "name": fname[:-3],
                    "path": fpath,
                    "created_at": os.path.getmtime(fpath),
                })
        return tools

    def search_tools(self, query: str) -> List[Dict]:
        """Search tools by name or content."""
        all_tools = self.list_tools()
        query_lower = query.lower()
        return [
            t for t in all_tools
            if query_lower in t.get("name", "").lower()
            or query_lower in json.dumps(t).lower()
        ]

    def generate_repair(
        self,
        error_msg: str,
        stack_trace: str,
        original_code: str = "",
        context: str = "",
    ) -> Optional[str]:
        """
        Use LLM to generate a repaired version of the failed code.
        Returns repaired code or None if repair fails.
        """
        # Check cache first
        error_hash = hashlib.sha256(f"{error_msg}:{original_code[:200]}".encode()).hexdigest()[:16]
        if error_hash in self._repair_cache:
            return self._repair_cache[error_hash]

        try:
            from groq_agent import call as llm_call
            system = """You are a Python repair engineer. Given a failed script's error and stack trace,
generate a CORRECTED version of the script. Rules:
1. Return ONLY valid Python code (no markdown, no explanation)
2. Include a `run()` function as the entrypoint
3. Handle the specific error that occurred
4. Add proper error handling
5. Keep the original intent intact"""

            user_msg = f"""Original code:
```python
{original_code or '# No original code available'}
```

Error: {error_msg}

Stack trace:
{stack_trace}

{context or ''}

Generate the repaired Python script with a run() function."""

            code = llm_call(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                max_tokens=1000,
                temperature=0.2,
            )
            if not code:
                return self._generate_repair_regex(error_msg, stack_trace, original_code)
            code = code.strip()
            # Strip markdown code fences if present
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            self._repair_cache[error_hash] = code
            return code

        except Exception:
            return self._generate_repair_regex(error_msg, stack_trace, original_code)

    def _generate_repair_regex(
        self, error_msg: str, stack_trace: str, original_code: str,
    ) -> Optional[str]:
        """Fallback regex-based repair for when LLM is unavailable."""
        if not original_code:
            return None

        repaired = original_code

        # Fix common patterns
        if "ModuleNotFoundError" in error_msg:
            module = error_msg.split("'")[-2] if "'" in error_msg else "unknown"
            repaired = f"""import subprocess, sys
try:
    import {module}
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "{module}"])
    import {module}

{original_code}"""

        elif "FileNotFoundError" in error_msg:
            repaired = f"""import os
{original_code}"""

        elif "PermissionError" in error_msg:
            repaired = f"""import os, stat
{original_code}"""

        elif "TimeoutError" in error_msg or "timed out" in error_msg.lower():
            repaired = f"""import signal
def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)
try:
{chr(10).join('    ' + line for line in original_code.split(chr(10)))}
finally:
    signal.alarm(0)"""

        elif "IndexError" in error_msg:
            repaired = f"""{original_code}
def run():
    try:
        return main()
    except IndexError:
        return None"""

        if repaired != original_code:
            return repaired
        return None

    def execute_with_healing(
        self,
        tool_name: str,
        execute_fn: Callable[[], Any],
        repair_fn: Optional[Callable[[str, str], str]] = None,
        max_retries: int = 2,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Execute with self-healing loop:
        1. Try execution
        2. On failure: generate repair via LLM/regex
        3. Validate repaired code in vault sandbox
        4. Store permanently if validation passes
        5. Retry with repaired code
        """
        last_error = None
        last_trace = None
        original_code = ""

        for attempt in range(max_retries + 1):
            try:
                result = execute_fn()
                return {
                    "status": "SUCCESS",
                    "result": result,
                    "healed": attempt > 0,
                    "attempts": attempt + 1,
                }
            except Exception as e:
                last_error = str(e)
                last_trace = traceback.format_exc()

                if attempt >= max_retries:
                    break

                # Generate repair
                if repair_fn:
                    try:
                        repaired_code = repair_fn(last_error, last_trace)
                    except Exception:
                        repaired_code = self.generate_repair(
                            last_error, last_trace, original_code, context
                        )
                else:
                    repaired_code = self.generate_repair(
                        last_error, last_trace, original_code, context
                    )

                if not repaired_code:
                    continue

                # Validate in vault sandbox
                vault = self._get_vault()
                if vault:
                    vr = vault.execute_script(repaired_code, language="python")
                    if vr.blocked or vr.exit_code != 0:
                        # Repair failed validation — try again
                        self._log_attempt(RepairAttempt(
                            tool_name=tool_name,
                            original_error=last_error,
                            stack_trace=last_trace,
                            repaired_code=repaired_code,
                            validation_passed=False,
                            stored=False,
                        ))
                        continue

                # Store validated repair
                self.register_tool(
                    tool_name,
                    repaired_code,
                    metadata={
                        "error_repaired": last_error,
                        "attempt": attempt + 1,
                        "context": context,
                    },
                )

                self._log_attempt(RepairAttempt(
                    tool_name=tool_name,
                    original_error=last_error,
                    stack_trace=last_trace,
                    repaired_code=repaired_code,
                    validation_passed=True,
                    stored=True,
                ))

                # Update execute_fn to use repaired code
                namespace = {}
                try:
                    exec(repaired_code, namespace)
                    if "run" in namespace:
                        execute_fn = namespace["run"]
                        original_code = repaired_code
                except Exception:
                    continue

        return {
            "status": "FAILED_HEAL",
            "error": last_error,
            "trace": last_trace,
            "attempts": max_retries + 1,
        }

    def _log_attempt(self, attempt: RepairAttempt):
        """Log repair attempt to disk."""
        self._attempt_log.append(attempt)
        entry = {
            "tool_name": attempt.tool_name,
            "original_error": attempt.original_error[:500],
            "validation_passed": attempt.validation_passed,
            "stored": attempt.stored,
            "timestamp": attempt.timestamp,
        }
        with open(REPAIR_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_healing_log(self, limit: int = 50) -> List[Dict]:
        """Get recent healing log entries."""
        if not os.path.isfile(REPAIR_LOG):
            return []
        entries = []
        with open(REPAIR_LOG) as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
        return entries[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get healing engine statistics."""
        tools = self.list_tools()
        log = self.get_healing_log(1000)
        healed = [e for e in log if e.get("stored")]
        return {
            "total_tools": len(tools),
            "total_attempts": len(log),
            "successful_heals": len(healed),
            "heal_rate": f"{len(healed)/max(len(log),1)*100:.1f}%",
            "cache_size": len(self._repair_cache),
        }


# Global singleton
healer = SelfHealingEngine()
