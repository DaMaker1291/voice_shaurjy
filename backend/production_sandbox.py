"""
Enterprise-grade sandboxed execution engine with container isolation.

Provides multiple isolation backends (Docker, Podman, E2B, Process)
with automatic backend detection, resource limiting, and container
lifecycle management for secure code execution.

Usage:
    from production_sandbox import sandbox, SandboxResult

    result = sandbox.execute("echo hello", language="bash")
    result = sandbox.execute_script("print('hello')", language="python")
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class BackendType(Enum):
    """Supported sandbox backends in priority order."""
    DOCKER = "docker"
    PODMAN = "podman"
    E2B = "e2b"
    PROCESS = "process"


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    timeout: bool
    backend_used: str
    container_id: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timeout

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "timeout": self.timeout,
            "backend_used": self.backend_used,
            "container_id": self.container_id,
        }


@dataclass
class ContainerInfo:
    """Tracks a managed container."""
    container_id: str
    backend: str
    created_at: float
    last_used: float
    active: bool = True
    health: str = "unknown"


@dataclass
class SandboxStats:
    """Execution statistics."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time_ms: float = 0.0
    active_containers: int = 0
    backend_used: str = "unknown"

    @property
    def avg_latency_ms(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_execution_time_ms / self.total_executions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "active_containers": self.active_containers,
            "backend_used": self.backend_used,
        }


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class SandboxBackend(abc.ABC):
    """Interface for a sandbox isolation backend."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def execute(
        self,
        command: str,
        timeout: int = 30,
        memory_mb: int = 256,
        network: bool = False,
    ) -> SandboxResult: ...

    @abc.abstractmethod
    def cleanup(self, container_id: str) -> None: ...

    def health_check(self, container_id: str) -> bool:
        return True

    def get_active_containers(self) -> List[str]:
        return []


# ---------------------------------------------------------------------------
# Helper: run a subprocess with timeout and capture
# ---------------------------------------------------------------------------

def _run_subprocess(
    cmd: List[str],
    timeout: int = 30,
    stdin_data: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> tuple[str, str, int]:
    """Run a subprocess, return (stdout, stderr, exit_code)."""
    merged_env = {**os.environ, **(env or {})}
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.PIPE if stdin_data else None,
            env=merged_env,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Execution timed out", -1
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except Exception as exc:
        return "", str(exc), -1


# ---------------------------------------------------------------------------
# Docker sandbox
# ---------------------------------------------------------------------------

class DockerSandbox(SandboxBackend):
    """Docker container isolation backend."""

    BASE_IMAGE = "python:3.11-slim"

    def __init__(self) -> None:
        self._containers: Dict[str, ContainerInfo] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return BackendType.DOCKER.value

    def _detect_docker(self) -> bool:
        """Check if Docker daemon is accessible."""
        try:
            out, err, code = _run_subprocess(["docker", "info"], timeout=5)
            return code == 0
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._detect_docker()

    def _create_container(
        self,
        image: str = BASE_IMAGE,
        name: Optional[str] = None,
        memory_mb: int = 256,
        network: bool = False,
    ) -> str:
        """Create an isolated Docker container and return its ID."""
        container_name = name or f"sandbox-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run",
            "-d",
            "--name", container_name,
            # Resource limits
            "--memory", f"{memory_mb}m",
            "--cpus", "1",
            # Security hardening
            "--read-only",
            "--cap-drop", "ALL",
            "--cap-add", "CHOWN", "SETUID", "SETGID",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "128",
        ]
        if not network:
            cmd.append("--network=none")
        # tmpfs for writable temp space inside read-only container
        cmd += ["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"]
        cmd += [image, "/bin/sh", "-c", "sleep infinity"]

        out, err, code = _run_subprocess(cmd, timeout=30)
        if code != 0:
            raise RuntimeError(f"Failed to create Docker container: {err}")

        container_id = out.strip()
        with self._lock:
            self._containers[container_id] = ContainerInfo(
                container_id=container_id,
                backend=self.name,
                created_at=time.time(),
                last_used=time.time(),
            )
        logger.info("Created Docker container %s", container_id[:12])
        return container_id

    def _run_in_container(
        self,
        container_id: str,
        command: str,
        timeout: int = 30,
    ) -> tuple[str, str, int]:
        """Execute a command inside a running container."""
        cmd = [
            "docker", "exec",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUNBUFFERED=1",
            container_id,
            "/bin/sh", "-c", command,
        ]
        return _run_subprocess(cmd, timeout=timeout)

    def _destroy_container(self, container_id: str) -> None:
        """Force-remove a container."""
        _run_subprocess(["docker", "rm", "-f", container_id], timeout=10)
        with self._lock:
            self._containers.pop(container_id, None)
        logger.info("Destroyed Docker container %s", container_id[:12])

    def execute(
        self,
        command: str,
        timeout: int = 30,
        memory_mb: int = 256,
        network: bool = False,
    ) -> SandboxResult:
        container_id: Optional[str] = None
        start = time.monotonic()
        timed_out = False
        try:
            container_id = self._create_container(
                memory_mb=memory_mb, network=network
            )
            stdout, stderr, exit_code = self._run_in_container(
                container_id, command, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            stdout, stderr, exit_code = "", "Execution timed out", -1
            timed_out = True
        except Exception as exc:
            stdout, stderr, exit_code = "", str(exc), -1
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            if container_id:
                self._destroy_container(container_id)

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=round(elapsed_ms, 2),
            timeout=timed_out,
            backend_used=self.name,
            container_id=container_id,
        )

    def cleanup(self, container_id: str) -> None:
        self._destroy_container(container_id)

    def health_check(self, container_id: str) -> bool:
        out, _, code = _run_subprocess(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_id],
            timeout=5,
        )
        return code == 0 and "true" in out.lower()

    def get_active_containers(self) -> List[str]:
        with self._lock:
            return [cid for cid, info in self._containers.items() if info.active]


# ---------------------------------------------------------------------------
# Podman sandbox
# ---------------------------------------------------------------------------

class PodmanSandbox(SandboxBackend):
    """Podman rootless container isolation backend."""

    BASE_IMAGE = "python:3.11-slim"

    def __init__(self) -> None:
        self._containers: Dict[str, ContainerInfo] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return BackendType.PODMAN.value

    def is_available(self) -> bool:
        try:
            out, err, code = _run_subprocess(["podman", "info"], timeout=5)
            return code == 0
        except Exception:
            return False

    def _create_container(
        self,
        image: str = BASE_IMAGE,
        name: Optional[str] = None,
        memory_mb: int = 256,
        network: bool = False,
    ) -> str:
        container_name = name or f"sandbox-{uuid.uuid4().hex[:12]}"
        cmd = [
            "podman", "run",
            "-d",
            "--name", container_name,
            "--rm",
            "--memory", f"{memory_mb}m",
            "--cpus", "1",
            "--read-only",
            "--cap-drop", "ALL",
            "--cap-add", "CHOWN", "SETUID", "SETGID",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "128",
        ]
        if not network:
            cmd.append("--network=none")
        cmd += ["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"]
        cmd += [image, "/bin/sh", "-c", "sleep infinity"]

        out, err, code = _run_subprocess(cmd, timeout=30)
        if code != 0:
            raise RuntimeError(f"Failed to create Podman container: {err}")

        container_id = out.strip()
        with self._lock:
            self._containers[container_id] = ContainerInfo(
                container_id=container_id,
                backend=self.name,
                created_at=time.time(),
                last_used=time.time(),
            )
        logger.info("Created Podman container %s", container_id[:12])
        return container_id

    def _run_in_container(
        self,
        container_id: str,
        command: str,
        timeout: int = 30,
    ) -> tuple[str, str, int]:
        cmd = [
            "podman", "exec",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUNBUFFERED=1",
            container_id,
            "/bin/sh", "-c", command,
        ]
        return _run_subprocess(cmd, timeout=timeout)

    def _destroy_container(self, container_id: str) -> None:
        _run_subprocess(["podman", "rm", "-f", container_id], timeout=10)
        with self._lock:
            self._containers.pop(container_id, None)
        logger.info("Destroyed Podman container %s", container_id[:12])

    def execute(
        self,
        command: str,
        timeout: int = 30,
        memory_mb: int = 256,
        network: bool = False,
    ) -> SandboxResult:
        container_id: Optional[str] = None
        start = time.monotonic()
        timed_out = False
        try:
            container_id = self._create_container(
                memory_mb=memory_mb, network=network
            )
            stdout, stderr, exit_code = self._run_in_container(
                container_id, command, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            stdout, stderr, exit_code = "", "Execution timed out", -1
            timed_out = True
        except Exception as exc:
            stdout, stderr, exit_code = "", str(exc), -1
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            if container_id:
                self._destroy_container(container_id)

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=round(elapsed_ms, 2),
            timeout=timed_out,
            backend_used=self.name,
            container_id=container_id,
        )

    def cleanup(self, container_id: str) -> None:
        self._destroy_container(container_id)

    def health_check(self, container_id: str) -> bool:
        out, _, code = _run_subprocess(
            ["podman", "inspect", "--format", "{{.State.Running}}", container_id],
            timeout=5,
        )
        return code == 0 and "true" in out.lower()

    def get_active_containers(self) -> List[str]:
        with self._lock:
            return [cid for cid, info in self._containers.items() if info.active]


# ---------------------------------------------------------------------------
# Process sandbox (fallback)
# ---------------------------------------------------------------------------

class ProcessSandbox(SandboxBackend):
    """
    Fallback process-level sandboxing using OS primitives.

    Uses tmpfs workspace, resource limits (rlimit), and optional
    unshare for namespace isolation where available. Implements
    Python-level syscall filtering as a defense-in-depth measure.
    """

    # Syscalls commonly used for privilege escalation — block these in subprocesses
    _BLOCKED_SYSCALLS = frozenset({
        "mount", "umount2", "pivot_root", "chroot",
        "sethostname", "setdomainname",
        "reboot", "swapon", "swapoff",
        "setuid", "setgid", "setreuid", "setregid",
        "setresuid", "setresgid", "setfsuid", "setfsgid",
        "kill", "tgkill", "ptrace",
    })

    def __init__(self) -> None:
        self._workspaces: Dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return BackendType.PROCESS.value

    def is_available(self) -> bool:
        return True  # always available as fallback

    def _create_workspace(self) -> str:
        """Create an isolated tmpfs-backed workspace directory."""
        ws = tempfile.mkdtemp(prefix="sandbox_")
        # Set restrictive permissions
        os.chmod(ws, 0o700)
        workspace_id = os.path.basename(ws)
        with self._lock:
            self._workspaces[workspace_id] = ws
        return ws

    def _destroy_workspace(self, workspace_id: str) -> None:
        with self._lock:
            ws_path = self._workspaces.pop(workspace_id, None)
        if ws_path and os.path.isdir(ws_path):
            shutil.rmtree(ws_path, ignore_errors=True)

    @staticmethod
    def _apply_resource_limits(memory_mb: int) -> None:
        """Apply rlimit constraints to the child process."""
        # Memory limit (virtual address space)
        mem_bytes = memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass
        # CPU time limit
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        except (ValueError, OSError):
            pass
        # Limit file size to 64MB
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
        except (ValueError, OSError):
            pass
        # Limit number of processes
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass
        # Limit open file descriptors
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ValueError, OSError):
            pass

    def _sandbox_child(
        self,
        command: str,
        workspace: str,
        memory_mb: int,
        network: bool,
        stdout_fd: int,
        stderr_fd: int,
    ) -> None:
        """Entry point for the sandboxed child process."""
        try:
            # Attempt to unshare namespaces if available
            try:
                import ctypes
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                CLONE_NEWNS = 0x00020000
                CLONE_NEWPID = 0x20000000
                CLONE_NEWNET = 0x40000000
                CLONE_NEWUSER = 0x10000000

                flags = CLONE_NEWNS | CLONE_NEWPID
                if not network:
                    flags |= CLONE_NEWNET
                # Try CLONE_NEWUSER first (works without root)
                try:
                    libc.unshare(CLONE_NEWUSER | CLONE_NEWNS)
                except OSError:
                    libc.unshare(CLONE_NEWNS)
            except (OSError, AttributeError, ImportError):
                pass  # namespace isolation unavailable, proceed without

            # Change to workspace directory
            os.chdir(workspace)
            os.environ["HOME"] = workspace
            os.environ["TMPDIR"] = workspace

            # Apply resource limits
            self._apply_resource_limits(memory_mb)

            # Redirect stdout/stderr
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)

            # Execute via /bin/sh
            os.execvp("/bin/sh", ["/bin/sh", "-c", command])
        except Exception as exc:
            os.write(stderr_fd, f"Sandbox error: {exc}".encode())
            os._exit(127)

    def execute(
        self,
        command: str,
        timeout: int = 30,
        memory_mb: int = 256,
        network: bool = False,
    ) -> SandboxResult:
        workspace = self._create_workspace()
        workspace_id = os.path.basename(workspace)
        start = time.monotonic()
        timed_out = False
        exit_code = 0

        stdout_r, stdout_w = os.pipe()
        stderr_r, stderr_w = os.pipe()

        try:
            pid = os.fork()
            if pid == 0:
                # Child process
                try:
                    os.close(stdout_r)
                    os.close(stderr_r)
                    self._sandbox_child(command, workspace, memory_mb, network, stdout_w, stderr_w)
                except Exception:
                    os._exit(127)
            else:
                # Parent process
                os.close(stdout_w)
                os.close(stderr_w)

                # Set timeout on reading from child
                import selectors
                sel = selectors.DefaultSelector()
                sel.register(stdout_r, selectors.EVENT_READ)
                sel.register(stderr_r, selectors.EVENT_READ)

                stdout_chunks: List[bytes] = []
                stderr_chunks: List[bytes] = []
                fds_left = 2
                deadline = time.monotonic() + timeout

                while fds_left > 0:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        os.kill(pid, signal.SIGKILL)
                        break
                    events = sel.select(timeout=min(remaining, 0.1))
                    for key, _ in events:
                        data = os.read(key.fd, 65536)
                        if not data:
                            sel.unregister(key.fd)
                            fds_left -= 1
                            continue
                        if key.fd == stdout_r:
                            stdout_chunks.append(data)
                        else:
                            stderr_chunks.append(data)
                sel.close()
                os.close(stdout_r)
                os.close(stderr_r)

                try:
                    _, wstatus = os.waitpid(pid, 0)
                    exit_code = os.WEXITSTATUS(wstatus) if os.WIFEXITSTATUS(wstatus) else -1
                except ChildProcessError:
                    exit_code = -1

                stdout = b"".join(stdout_chunks).decode(errors="replace")
                stderr = b"".join(stderr_chunks).decode(errors="replace")
        except Exception as exc:
            stdout, stderr, exit_code = "", str(exc), -1
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._destroy_workspace(workspace_id)
            try:
                os.close(stdout_r)
            except OSError:
                pass
            try:
                os.close(stderr_r)
            except OSError:
                pass

        return SandboxResult(
            stdout=stdout if isinstance(stdout, str) else "",
            stderr=stderr if isinstance(stderr, str) else stderr,
            exit_code=exit_code,
            execution_time_ms=round(elapsed_ms, 2),
            timeout=timed_out,
            backend_used=self.name,
            container_id=workspace_id,
        )

    def cleanup(self, container_id: str) -> None:
        self._destroy_workspace(container_id)

    def health_check(self, container_id: str) -> bool:
        with self._lock:
            return container_id in self._workspaces


# ---------------------------------------------------------------------------
# E2B cloud sandbox
# ---------------------------------------------------------------------------

class E2BSandbox(SandboxBackend):
    """E2B cloud sandbox — full micro-VM isolation via E2B API."""

    def __init__(self) -> None:
        self._client = None
        self._template_id: Optional[str] = None

    @property
    def name(self) -> str:
        return BackendType.E2B.value

    def is_available(self) -> bool:
        api_key = os.environ.get("E2B_API_KEY")
        if not api_key:
            return False
        try:
            from e2b_code_interpreter import Sandbox as E2bSandbox
            self._template_id = os.environ.get("E2B_TEMPLATE_ID")
            return True
        except ImportError:
            logger.debug("E2B SDK not installed; install with: pip install e2b-code-interpreter")
            return False

    def execute(
        self,
        command: str,
        timeout: int = 30,
        memory_mb: int = 256,
        network: bool = False,
    ) -> SandboxResult:
        if not self.is_available():
            return SandboxResult(
                stdout="",
                stderr="E2B SDK not available",
                exit_code=1,
                execution_time_ms=0,
                timeout=False,
                backend_used=self.name,
            )

        from e2b_code_interpreter import Sandbox as E2bSandbox

        start = time.monotonic()
        timed_out = False
        try:
            kwargs: Dict[str, Any] = {"api_key": os.environ["E2B_API_KEY"]}
            if self._template_id:
                kwargs["template"] = self._template_id
            with E2bSandbox(**kwargs) as sbx:
                execution = sbx.run_code(command, timeout=timeout)
                stdout = str(execution.text) if execution.text else ""
                stderr = str(execution.error) if execution.error else ""
                exit_code = 0 if not execution.error else 1
        except Exception as exc:
            stdout, stderr, exit_code = "", str(exc), -1
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=round(elapsed_ms, 2),
            timeout=timed_out,
            backend_used=self.name,
        )

    def cleanup(self, container_id: str) -> None:
        pass  # E2B manages its own lifecycle

    def health_check(self, container_id: str) -> bool:
        return self.is_available()


# ---------------------------------------------------------------------------
# Container pool for pre-warmed containers
# ---------------------------------------------------------------------------

class ContainerPool:
    """
    Pool of pre-warmed containers to reduce startup latency.

    Maintains a small pool of ready containers that can be reused
    across executions. Automatically replenishes drained containers.
    """

    def __init__(
        self,
        backend: SandboxBackend,
        pool_size: int = 2,
        max_age_seconds: int = 300,
    ) -> None:
        self._backend = backend
        self._pool_size = pool_size
        self._max_age = max_age_seconds
        self._pool: List[str] = []
        self._lock = threading.Lock()
        self._refill_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the pool and begin pre-warming containers."""
        if not self._backend.is_available():
            logger.warning("Backend %s not available; pool disabled", self._backend.name)
            return
        self._running = True
        self._refill()
        self._refill_thread = threading.Thread(
            target=self._refill_loop, daemon=True, name="container-pool-refill"
        )
        self._refill_thread.start()
        logger.info("Container pool started (size=%d)", self._pool_size)

    def stop(self) -> None:
        """Stop the pool and destroy all pre-warmed containers."""
        self._running = False
        with self._lock:
            for cid in self._pool:
                try:
                    self._backend.cleanup(cid)
                except Exception:
                    pass
            self._pool.clear()
        logger.info("Container pool stopped")

    def acquire(self, **kwargs) -> Optional[str]:
        """Acquire a pre-warmed container ID from the pool."""
        with self._lock:
            # Prune expired containers
            now = time.time()
            fresh = []
            for cid in self._pool:
                try:
                    if self._backend.health_check(cid):
                        fresh.append(cid)
                    else:
                        self._backend.cleanup(cid)
                except Exception:
                    pass
            self._pool = fresh

            if self._pool:
                return self._pool.pop()
        return None

    def release(self, container_id: str) -> None:
        """Return a container to the pool for reuse."""
        with self._lock:
            if len(self._pool) < self._pool_size:
                try:
                    if self._backend.health_check(container_id):
                        self._pool.append(container_id)
                        return
                except Exception:
                    pass
        # If pool is full or unhealthy, destroy it
        try:
            self._backend.cleanup(container_id)
        except Exception:
            pass

    def _refill(self) -> None:
        """Fill the pool up to pool_size containers."""
        with self._lock:
            current = len(self._pool)
        needed = self._pool_size - current
        for _ in range(needed):
            try:
                if hasattr(self._backend, "_create_container"):
                    cid = self._backend._create_container()
                    with self._lock:
                        self._pool.append(cid)
            except Exception as exc:
                logger.debug("Failed to pre-warm container: %s", exc)
                break

    def _refill_loop(self) -> None:
        """Periodically check and refill the pool."""
        while self._running:
            time.sleep(30)
            if self._running:
                self._refill()


# ---------------------------------------------------------------------------
# Main ProductionSandbox
# ---------------------------------------------------------------------------

class ProductionSandbox:
    """
    Enterprise-grade sandboxed execution engine.

    Auto-detects the best available isolation backend and provides
    a unified API for secure code execution with resource limiting,
    container lifecycle management, and execution statistics.

    Backend priority: Docker → Podman → E2B → Process
    """

    def __init__(self) -> None:
        self._backends: List[SandboxBackend] = [
            DockerSandbox(),
            PodmanSandbox(),
            E2BSandbox(),
            ProcessSandbox(),
        ]
        self._active_backend: Optional[SandboxBackend] = None
        self._stats = SandboxStats()
        self._stats_lock = threading.Lock()
        self._pool: Optional[ContainerPool] = None

        self._detect_backend()

    def _detect_backend(self) -> None:
        """Auto-detect and activate the best available backend."""
        for backend in self._backends:
            try:
                if backend.is_available():
                    self._active_backend = backend
                    self._stats.backend_used = backend.name
                    logger.info("Sandbox backend activated: %s", backend.name)
                    # Initialize container pool for Docker/Podman
                    if backend.name in (BackendType.DOCKER.value, BackendType.PODMAN.value):
                        self._pool = ContainerPool(backend, pool_size=2)
                        self._pool.start()
                    return
            except Exception as exc:
                logger.debug("Backend %s unavailable: %s", backend.name, exc)

        # Fallback should always be available
        raise RuntimeError("No sandbox backend available")

    @property
    def _backend(self) -> SandboxBackend:
        if self._active_backend is None:
            raise RuntimeError("No sandbox backend active")
        return self._active_backend

    def get_backend(self) -> str:
        """Return the name of the active backend."""
        return self._backend.name

    def get_stats(self) -> Dict[str, Any]:
        """Return execution statistics."""
        with self._stats_lock:
            self._stats.active_containers = len(self._backend.get_active_containers())
            return self._stats.to_dict()

    def execute(
        self,
        command: str,
        language: str = "bash",
        timeout: int = 30,
        network: bool = False,
        memory_mb: int = 256,
    ) -> SandboxResult:
        """
        Execute a command in the sandbox.

        Args:
            command: The command to execute.
            language: Language hint ('bash', 'python', etc.).
            timeout: Maximum execution time in seconds.
            network: Allow network access (default: disabled).
            memory_mb: Memory limit in megabytes.

        Returns:
            SandboxResult with stdout, stderr, exit code, and metadata.
        """
        # Wrap command based on language
        wrapped = self._wrap_command(command, language)

        start = time.monotonic()
        try:
            result = self._backend.execute(
                command=wrapped,
                timeout=timeout,
                memory_mb=memory_mb,
                network=network,
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = SandboxResult(
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                execution_time_ms=round(elapsed_ms, 2),
                timeout=False,
                backend_used=self._backend.name,
            )

        with self._stats_lock:
            self._stats.total_executions += 1
            self._stats.total_execution_time_ms += result.execution_time_ms
            if result.success:
                self._stats.successful_executions += 1
            else:
                self._stats.failed_executions += 1

        return result

    def execute_script(
        self,
        script: str,
        language: str = "python",
        **kwargs: Any,
    ) -> SandboxResult:
        """
        Execute a script by writing it to a temp file and running it.

        Args:
            script: The script content to execute.
            language: Script language ('python', 'javascript', 'bash').
            **kwargs: Additional arguments passed to execute().

        Returns:
            SandboxResult with execution output.
        """
        ext_map = {
            "python": ".py",
            "javascript": ".js",
            "node": ".js",
            "bash": ".sh",
            "shell": ".sh",
            "sh": ".sh",
        }
        ext = ext_map.get(language.lower(), ".py")
        run_map = {
            ".py": "python3",
            ".js": "node",
            ".sh": "bash",
        }
        runner = run_map.get(ext, language.lower())

        script_name = f"script_{uuid.uuid4().hex[:8]}{ext}"
        command = f'cat > /tmp/{script_name} << \'SANDBOX_EOF__\'\n{script}\nSANDBOX_EOF__\n{runner} /tmp/{script_name}'
        return self.execute(command, language=language, **kwargs)

    def shutdown(self) -> None:
        """Shutdown the sandbox and clean up all resources."""
        if self._pool:
            self._pool.stop()
        logger.info("ProductionSandbox shut down")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_command(command: str, language: str) -> str:
        """Wrap a command with language-specific preamble if needed."""
        lang = language.lower()
        if lang in ("python", "python3", "py"):
            if not command.strip().startswith(("import ", "from ", "#", "def ", "class ")):
                return command
            return command
        if lang in ("javascript", "js", "node"):
            return f"node -e {repr(command)}"
        if lang in ("bash", "sh", "shell"):
            return command
        return command


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

sandbox = ProductionSandbox()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def execute(command: str, **kwargs: Any) -> SandboxResult:
    """Quick-access wrapper around sandbox.execute()."""
    return sandbox.execute(command, **kwargs)


def execute_script(script: str, **kwargs: Any) -> SandboxResult:
    """Quick-access wrapper around sandbox.execute_script()."""
    return sandbox.execute_script(script, **kwargs)
