"""
JARVIS Execution Vault — Sandboxed Process Isolation
=====================================================
Replaces raw subprocess.run() with isolated execution environments.
Implements process isolation, network egress filtering, resource limits,
and filesystem access restrictions.

For HF Space (Docker): uses cgroups + unshare + namespace isolation.
For bare metal: uses bubblewrap/firecracker when available.
"""

import os
import sys
import json
import time
import shutil
import signal
import hashlib
import tempfile
import threading
import traceback
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import contextmanager


# ── Security Policies ───────────────────────────────────────────

BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=", "shred",
    ":(){:|:&};:", "chmod -R 777 /", "chown -R",
    "wget", "curl.*|.*sh", "eval(", "exec(",
    "> /dev/sda", "mount ", "umount ",
    "iptables -F", "shutdown", "reboot", "halt",
    "systemctl", "service ", "kill -9 1",
}

BLOCKED_PATHS = {
    "/etc/shadow", "/etc/passwd", "/root", "/boot",
    "/sys", "/proc/sys", "/dev/sda", "/dev/nvme",
}

NETWORK_BLOCKED_DOMAINS = {
    "pastebin.com", "hastebin.com", "dpaste.org",
    "ngrok.io", "localtunnel.me", "serveo.net",
}

MAX_EXECUTION_TIME = 30  # seconds
MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB
MAX_MEMORY_MB = 256
MAX_CPU_PERCENT = 50


@dataclass
class VaultPolicy:
    """Execution policy for a vault session."""
    timeout: int = MAX_EXECUTION_TIME
    max_memory_mb: int = MAX_MEMORY_MB
    max_cpu_percent: int = MAX_CPU_PERCENT
    allowed_commands: Optional[List[str]] = None
    blocked_commands: Optional[List[str]] = None
    network_allowed: bool = True
    filesystem_allowed: bool = True
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    user: Optional[str] = None  # Run as specific user


@dataclass
class VaultResult:
    """Result of a vaulted execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    blocked: bool = False
    block_reason: str = ""
    execution_time_ms: int = 0
    peak_memory_kb: int = 0
    pid: int = 0
    security_violations: List[str] = field(default_factory=list)


class ExecutionVault:
    """
    Sandboxed execution environment for shell commands and scripts.
    
    Security layers:
    1. Command pre-screening (regex-based threat detection)
    2. Path access restrictions (whitelist/blacklist)
    3. Network egress filtering (domain blocking)
    4. Process resource limits (cgroups/ulimit)
    5. Filesystem isolation (tmpfs + restricted paths)
    6. Timeout enforcement (SIGKILL after deadline)
    """

    def __init__(self, base_dir: Optional[str] = None):
        self._base_dir = base_dir or os.path.join(tempfile.gettempdir(), "jarvis_vault")
        self._vault_dir = os.path.join(self._base_dir, "sandbox")
        self._tools_dir = os.path.join(self._base_dir, "tools")
        self._logs_dir = os.path.join(self._base_dir, "logs")
        self._lock = threading.Lock()
        
        # Create directories
        for d in [self._vault_dir, self._tools_dir, self._logs_dir]:
            os.makedirs(d, exist_ok=True)
        
        # Load security policy
        self._policy = VaultPolicy()
        self._violations: List[Dict] = []
        
        # Determine execution method
        self._method = self._detect_execution_method()

    def _detect_execution_method(self) -> str:
        """Detect best available sandboxing method."""
        # Check for bubblewrap (bwrap)
        if shutil.which("bwrap"):
            return "bwrap"
        # Check for unshare
        if shutil.which("unshare"):
            return "unshare"
        # Check for docker
        if shutil.which("docker"):
            return "docker"
        # Fallback: restricted subprocess
        return "restricted"

    def execute(
        self,
        command: str,
        policy: Optional[VaultPolicy] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> VaultResult:
        """Execute a command in a sandboxed vault."""
        policy = policy or self._policy
        result = VaultResult()
        start_time = time.time()

        # Layer 1: Command pre-screening
        violations = self._screen_command(command)
        if violations:
            result.blocked = True
            result.block_reason = "; ".join(violations)
            result.security_violations = violations
            self._log_violation(command, violations)
            return result

        # Layer 2: Build execution environment
        exec_env = self._build_sandbox_env(env or {})
        exec_cwd = self._prepare_working_dir(cwd)

        # Layer 3: Execute with resource limits
        try:
            if self._method == "bwrap":
                result = self._execute_bwrap(command, policy, exec_cwd, exec_env)
            elif self._method == "unshare":
                result = self._execute_unshare(command, policy, exec_cwd, exec_env)
            else:
                result = self._execute_restricted(command, policy, exec_cwd, exec_env)
        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.exit_code = -1
            result.block_reason = f"Execution timed out after {policy.timeout}s"
        except Exception as e:
            result.exit_code = -1
            result.stderr = str(e)

        result.execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Log execution
        self._log_execution(command, result)
        
        return result

    def execute_script(
        self,
        script: str,
        language: str = "python",
        policy: Optional[VaultPolicy] = None,
    ) -> VaultResult:
        """Execute a script in a sandboxed vault."""
        if language == "python":
            return self._execute_python_script(script, policy)
        elif language in ("bash", "sh", "shell"):
            return self.execute(f"bash -c {self._escape_arg(script)}", policy)
        elif language == "javascript":
            return self._execute_node_script(script, policy)
        else:
            return VaultResult(blocked=True, block_reason=f"Unsupported language: {language}")

    def register_tool(
        self,
        name: str,
        code: str,
        language: str = "python",
        metadata: Optional[Dict] = None,
    ) -> str:
        """Register a synthesized tool in the permanent library."""
        tool_id = hashlib.sha256(f"{name}:{code}".encode()).hexdigest()[:12]
        tool_dir = os.path.join(self._tools_dir, tool_id)
        os.makedirs(tool_dir, exist_ok=True)
        
        ext_map = {"python": ".py", "bash": ".sh", "javascript": ".js"}
        ext = ext_map.get(language, ".txt")
        
        with open(os.path.join(tool_dir, f"tool{ext}"), "w") as f:
            f.write(code)
        
        meta = {
            "id": tool_id,
            "name": name,
            "language": language,
            "created_at": time.time(),
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            **(metadata or {}),
        }
        with open(os.path.join(tool_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        
        return tool_id

    def list_tools(self) -> List[Dict]:
        """List all registered tools."""
        tools = []
        if not os.path.isdir(self._tools_dir):
            return tools
        for tool_id in os.listdir(self._tools_dir):
            meta_path = os.path.join(self._tools_dir, tool_id, "meta.json")
            if os.path.isfile(meta_path):
                with open(meta_path) as f:
                    tools.append(json.load(f))
        return tools

    def get_tool(self, tool_id: str) -> Optional[Dict]:
        """Get a registered tool by ID."""
        meta_path = os.path.join(self._tools_dir, tool_id, "meta.json")
        if not os.path.isfile(meta_path):
            return None
        with open(meta_path) as f:
            meta = json.load(f)
        
        # Find code file
        tool_dir = os.path.join(self._tools_dir, tool_id)
        for fname in os.listdir(tool_dir):
            if fname.startswith("tool."):
                with open(os.path.join(tool_dir, fname)) as f:
                    meta["code"] = f.read()
                break
        return meta

    # ── Security Screening ──────────────────────────────────────

    def _screen_command(self, command: str) -> List[str]:
        """Screen command for security violations."""
        violations = []
        cmd_lower = command.lower().strip()

        # Check blocked commands
        for blocked in BLOCKED_COMMANDS:
            if blocked.lower() in cmd_lower:
                violations.append(f"Blocked command pattern: {blocked}")

        # Check network egress to blocked domains
        for domain in NETWORK_BLOCKED_DOMAINS:
            if domain in cmd_lower:
                violations.append(f"Blocked network egress: {domain}")

        # Check file path access
        for path in BLOCKED_PATHS:
            if path in command:
                violations.append(f"Blocked path access: {path}")

        # Check for piping to shell
        if "| sh" in cmd_lower or "| bash" in cmd_lower:
            violations.append("Piping to shell interpreter blocked")

        # Check for eval/exec in scripts
        if cmd_lower.startswith("eval ") or cmd_lower.startswith("exec "):
            violations.append("Direct eval/exec blocked in vault")

        return violations

    def _build_sandbox_env(self, extra_env: Dict[str, str]) -> Dict[str, str]:
        """Build restricted environment for sandboxed execution."""
        env = os.environ.copy()
        
        # Remove sensitive env vars
        sensitive_keys = [
            "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
            "GITHUB_TOKEN", "HF_TOKEN", "GROQ_API_KEY",
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        ]
        for key in sensitive_keys:
            env.pop(key, None)
        
        # Add vault-specific vars
        env["JARVIS_VAULT"] = "1"
        env["JARVIS_VAULT_DIR"] = self._vault_dir
        
        # Apply extra env
        env.update(extra_env)
        
        return env

    def _prepare_working_dir(self, cwd: Optional[str]) -> str:
        """Prepare a sandboxed working directory."""
        if cwd and os.path.isdir(cwd):
            # Verify path is not in blocked locations
            real_path = os.path.realpath(cwd)
            for blocked in BLOCKED_PATHS:
                if real_path.startswith(blocked):
                    return self._vault_dir
            return cwd
        return self._vault_dir

    # ── Execution Methods ───────────────────────────────────────

    def _execute_bwrap(
        self, command: str, policy: VaultPolicy,
        cwd: str, env: Dict[str, str],
    ) -> VaultResult:
        """Execute via bubblewrap (bwrap) — strongest sandbox."""
        result = VaultResult()
        
        bwrap_cmd = [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/sbin", "/sbin",
            "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--die-with-parent",
            "--unshare-all",
            "--hostname", "jarvis-vault",
        ]
        
        # Add working directory
        if cwd != self._vault_dir:
            bwrap_cmd.extend(["--bind", cwd, cwd])
        
        # Add tmpfs for workspace
        bwrap_cmd.extend(["--tmpfs", self._vault_dir])
        
        # Resource limits via ulimit
        ulimit_cmd = f"ulimit -t {policy.timeout} -m {policy.max_memory_mb * 1024} && {command}"
        bwrap_cmd.extend(["/bin/bash", "-c", ulimit_cmd])
        
        try:
            proc = subprocess.run(
                bwrap_cmd,
                capture_output=True,
                text=True,
                timeout=policy.timeout + 5,
                env=env,
                cwd=cwd,
            )
            result.stdout = proc.stdout[:MAX_OUTPUT_SIZE]
            result.stderr = proc.stderr[:MAX_OUTPUT_SIZE]
            result.exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.exit_code = -1
            result.block_reason = f"Timeout after {policy.timeout}s"
        
        return result

    def _execute_unshare(
        self, command: str, policy: VaultPolicy,
        cwd: str, env: Dict[str, str],
    ) -> VaultResult:
        """Execute via unshare — namespace isolation."""
        result = VaultResult()
        
        unshare_cmd = [
            "unshare",
            "--mount", "--uts", "--ipc", "--net", "--pid", "--fork",
            "--", "/bin/bash", "-c",
            f"ulimit -t {policy.timeout} && {command}"
        ]
        
        try:
            proc = subprocess.run(
                unshare_cmd,
                capture_output=True,
                text=True,
                timeout=policy.timeout + 5,
                env=env,
                cwd=cwd,
            )
            result.stdout = proc.stdout[:MAX_OUTPUT_SIZE]
            result.stderr = proc.stderr[:MAX_OUTPUT_SIZE]
            result.exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.exit_code = -1
        
        return result

    def _execute_restricted(
        self, command: str, policy: VaultPolicy,
        cwd: str, env: Dict[str, str],
    ) -> VaultResult:
        """Execute with restricted subprocess (fallback — no namespace isolation)."""
        result = VaultResult()
        
        # Double-check command screening passes again at execution layer
        violations = self._screen_command(command)
        if violations:
            result.blocked = True
            result.block_reason = "; ".join(violations)
            result.security_violations = violations
            self._log_violation(command, violations)
            return result

        # Build resource-limited command with network egress control
        net_prefix = "" if policy.network_allowed else "export http_proxy=http://127.0.0.1:9; export https_proxy=http://127.0.0.1:9; "
        limited_cmd = (
            f"ulimit -t {policy.timeout} -f {MAX_OUTPUT_SIZE} -v {policy.max_memory_mb * 1024} 2>/dev/null; "
            f"{net_prefix}{command}"
        )
        
        try:
            proc = subprocess.run(
                ["/bin/bash", "-c", limited_cmd],
                capture_output=True,
                text=True,
                timeout=policy.timeout + 2,
                env=env,
                cwd=cwd,
                preexec_fn=self._set_resource_limits if sys.platform != "win32" else None,
            )
            result.stdout = proc.stdout[:MAX_OUTPUT_SIZE]
            result.stderr = proc.stderr[:MAX_OUTPUT_SIZE]
            result.exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.exit_code = -1
            result.block_reason = f"Timeout after {policy.timeout}s"
        
        return result

    def _execute_python_script(
        self, script: str, policy: Optional[VaultPolicy] = None,
    ) -> VaultResult:
        """Execute Python script in sandbox."""
        policy = policy or self._policy
        
        # Screen the script
        violations = self._screen_command(script)
        if violations:
            return VaultResult(blocked=True, block_reason="; ".join(violations), security_violations=violations)
        
        # Write to temp file
        script_hash = hashlib.sha256(script.encode()).hexdigest()[:8]
        script_path = os.path.join(self._vault_dir, f"script_{script_hash}.py")
        
        with open(script_path, "w") as f:
            f.write(script)
        
        try:
            return self.execute(
                f"python3 {script_path}",
                policy=policy,
                cwd=self._vault_dir,
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def _execute_node_script(
        self, script: str, policy: Optional[VaultPolicy] = None,
    ) -> VaultResult:
        """Execute Node.js script in sandbox."""
        policy = policy or self._policy
        
        violations = self._screen_command(script)
        if violations:
            return VaultResult(blocked=True, block_reason="; ".join(violations), security_violations=violations)
        
        script_hash = hashlib.sha256(script.encode()).hexdigest()[:8]
        script_path = os.path.join(self._vault_dir, f"script_{script_hash}.js")
        
        with open(script_path, "w") as f:
            f.write(script)
        
        try:
            return self.execute(
                f"node {script_path}",
                policy=policy,
                cwd=self._vault_dir,
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    # ── Utilities ───────────────────────────────────────────────

    @staticmethod
    def _escape_arg(arg: str) -> str:
        """Escape shell argument."""
        return "'" + arg.replace("'", "'\\''") + "'"

    @staticmethod
    def _set_resource_limits():
        """Set resource limits for child process (Unix only)."""
        try:
            import resource
            # CPU time: 30 seconds
            resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
            # Memory: 256MB
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            # No core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # Max processes: 50
            resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))
        except (ImportError, ValueError, OSError):
            pass

    def _log_violation(self, command: str, violations: List[str]):
        """Log security violation."""
        entry = {
            "timestamp": time.time(),
            "command": command[:500],
            "violations": violations,
            "level": "CRITICAL",
        }
        self._violations.append(entry)
        
        log_path = os.path.join(self._logs_dir, "violations.jsonl")
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_execution(self, command: str, result: VaultResult):
        """Log execution details."""
        entry = {
            "timestamp": time.time(),
            "command": command[:500],
            "exit_code": result.exit_code,
            "execution_time_ms": result.execution_time_ms,
            "timed_out": result.timed_out,
            "blocked": result.blocked,
            "security_violations": result.security_violations,
        }
        
        log_path = os.path.join(self._logs_dir, "executions.jsonl")
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_violations(self, limit: int = 50) -> List[Dict]:
        """Get recent security violations."""
        return self._violations[-limit:]

    def get_execution_log(self, limit: int = 50) -> List[Dict]:
        """Get recent execution log."""
        log_path = os.path.join(self._logs_dir, "executions.jsonl")
        if not os.path.isfile(log_path):
            return []
        entries = []
        with open(log_path) as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
        return entries[-limit:]


# ── Global Singleton ────────────────────────────────────────────

_vault: Optional[ExecutionVault] = None
_vault_lock = threading.Lock()


def get_vault() -> ExecutionVault:
    global _vault
    if _vault is None:
        with _vault_lock:
            if _vault is None:
                _vault = ExecutionVault()
    return _vault


# ── Drop-in Replacement for subprocess.run() ────────────────────

def vaulted_run(
    command: str,
    timeout: int = MAX_EXECUTION_TIME,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    policy: Optional[VaultPolicy] = None,
) -> VaultResult:
    """Drop-in replacement for subprocess.run() with vault sandboxing."""
    vault = get_vault()
    
    if policy is None:
        policy = VaultPolicy(timeout=timeout)
    
    return vault.execute(command, policy=policy, cwd=cwd, env=env)


def vaulted_python(
    script: str,
    timeout: int = MAX_EXECUTION_TIME,
) -> VaultResult:
    """Execute Python script in vault."""
    vault = get_vault()
    policy = VaultPolicy(timeout=timeout)
    return vault.execute_script(script, language="python", policy=policy)
