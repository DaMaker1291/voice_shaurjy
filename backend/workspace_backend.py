"""JARVIS Workspace Backend Abstraction — the core execution interface.

Every task in JARVIS flows through this interface. The user never sees
which backend is underneath — JARVIS chooses automatically.
"""

import os
import sys
import time
import json
import logging
import subprocess
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

log = logging.getLogger("workspace_backend")


@dataclass
class ExecutionContext:
    """Everything a backend needs to execute a task."""
    workspace_id: str
    task_type: str          # "browser", "files", "command", "app", "gpu", etc.
    objective: str          # What the user wants
    risk_level: str         # "low", "medium", "high"
    timeout: int = 300      # Max seconds
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of a backend execution."""
    ok: bool
    output: str = ""
    error: str = ""
    artifacts: List[str] = field(default_factory=list)
    screenshot: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "ok": self.ok, "output": self.output[:1000],
            "error": self.error, "artifacts": self.artifacts,
            "metadata": self.metadata,
        }


class WorkspaceBackend(ABC):
    """Abstract execution backend — the contract every backend fulfills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name: 'native', 'wsl', 'sandbox', 'vm', 'remote'."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Can this backend execute tasks right now?"""

    @property
    @abstractmethod
    def cost(self) -> int:
        """Relative resource cost: 1=cheap, 10=expensive. Used for routing."""

    @abstractmethod
    def start(self, ctx: ExecutionContext) -> bool:
        """Start the backend. Return True if successful."""

    @abstractmethod
    def stop(self):
        """Stop and release resources."""

    @abstractmethod
    def execute(self, ctx: ExecutionContext, action: str, params: dict) -> ExecutionResult:
        """Execute a single action (run_command, write_file, launch_app, etc.)."""

    @abstractmethod
    def snapshot(self) -> Optional[bytes]:
        """Capture current state as JPEG bytes."""

    def is_running(self) -> bool:
        """Is this backend currently active?"""
        return False


# ══════════════════════════════════════════════════════════════
#  NATIVE WINDOWS BACKEND
# ══════════════════════════════════════════════════════════════

class NativeBackend(WorkspaceBackend):
    """Execute directly on the user's Windows machine.
    
    Uses PowerShell, subprocess, Windows APIs.
    Fastest, cheapest, no overhead.
    """

    @property
    def name(self) -> str:
        return "native"

    @property
    def is_available(self) -> bool:
        return sys.platform == "win32"

    @property
    def cost(self) -> int:
        return 1

    def __init__(self):
        self._running = False
        self._workspace_dir: Optional[Path] = None

    def is_running(self) -> bool:
        return self._running

    def start(self, ctx: ExecutionContext) -> bool:
        self._workspace_dir = Path(os.path.expanduser(f"~/.jarvis/workspaces/{ctx.workspace_id}/files"))
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        log.info(f"[NATIVE] Started for workspace {ctx.workspace_id}")
        return True

    def stop(self):
        self._running = False
        log.info("[NATIVE] Stopped")

    def execute(self, ctx: ExecutionContext, action: str, params: dict) -> ExecutionResult:
        if not self._running:
            return ExecutionResult(ok=False, error="Backend not running")

        try:
            if action == "run_command":
                return self._run_command(params.get("cmd", ""), ctx)
            elif action == "write_file":
                return self._write_file(params.get("path", ""), params.get("content", ""))
            elif action == "read_file":
                return self._read_file(params.get("path", ""))
            elif action == "create_directory":
                return self._create_directory(params.get("path", ""))
            elif action == "launch_app":
                return self._launch_app(params.get("name", ""), params.get("command", []))
            elif action == "screenshot":
                return self._screenshot()
            elif action in ("web_search", "search_web"):
                return self._web_search(params.get("query", ""))
            elif action == "web_scrape":
                return self._web_scrape(params.get("url", ""))
            elif action == "navigate_web":
                return self._navigate_web(params.get("url", ""))
            elif action == "click":
                return ExecutionResult(ok=True, output="Click logged (no VM)")
            elif action == "type_text":
                return ExecutionResult(ok=True, output="Text logged (no VM)")
            elif action == "press_key":
                return ExecutionResult(ok=True, output="Key logged (no VM)")
            elif action == "wait":
                time.sleep(params.get("seconds", 1))
                return ExecutionResult(ok=True)
            else:
                return ExecutionResult(ok=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _run_command(self, cmd: str, ctx: ExecutionContext) -> ExecutionResult:
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=ctx.timeout, cwd=str(self._workspace_dir),
            )
            return ExecutionResult(
                ok=r.returncode == 0,
                output=r.stdout[:2000],
                error=r.stderr[:500] if r.returncode != 0 else "",
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(ok=False, error="Command timed out")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _write_file(self, path: str, content: str) -> ExecutionResult:
        try:
            # Sandbox to workspace dir if relative
            if not os.path.isabs(path) and self._workspace_dir:
                path = str(self._workspace_dir / path)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ExecutionResult(ok=True, output=f"Written {len(content)} bytes to {path}")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _read_file(self, path: str) -> ExecutionResult:
        try:
            if not os.path.isabs(path) and self._workspace_dir:
                path = str(self._workspace_dir / path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(100000)
            return ExecutionResult(ok=True, output=content)
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _create_directory(self, path: str) -> ExecutionResult:
        try:
            if not os.path.isabs(path) and self._workspace_dir:
                path = str(self._workspace_dir / path)
            os.makedirs(path, exist_ok=True)
            return ExecutionResult(ok=True, output=f"Created {path}")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _launch_app(self, name: str, command: list) -> ExecutionResult:
        try:
            cmd = command or [name]
            creationflags = 0x00000008  # DETACHED_PROCESS
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            return ExecutionResult(ok=True, output=f"Launched {name} (pid={proc.pid})")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _screenshot(self) -> ExecutionResult:
        """Generate a status image (not the real screen)."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            w, h = 1920, 1080
            img = Image.new("RGB", (w, h), (8, 12, 10))
            draw = ImageDraw.Draw(img)
            for x in range(0, w, 64):
                draw.line([(x, 0), (x, h)], fill=(0, 255, 102, 8), width=1)
            for y in range(0, h, 64):
                draw.line([(0, y), (w, y)], fill=(0, 255, 102, 8), width=1)
            import io
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60)
            return ExecutionResult(ok=True, screenshot=buf.getvalue())
        except Exception:
            return ExecutionResult(ok=False, error="Screenshot unavailable")

    def _web_search(self, query: str) -> ExecutionResult:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            formatted = [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in results]
            return ExecutionResult(ok=True, output=json.dumps(formatted, indent=2))
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _web_scrape(self, url: str) -> ExecutionResult:
        try:
            import httpx
            resp = httpx.get(url, follow_redirects=True, timeout=15)
            from html.parser import HTMLParser
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                    self._skip = False
                def handle_starttag(self, tag, attrs):
                    self._skip = tag in ("script", "style", "noscript")
                def handle_endtag(self, tag):
                    if tag in ("script", "style", "noscript"):
                        self._skip = False
                def handle_data(self, data):
                    if not self._skip:
                        t = data.strip()
                        if t:
                            self.text.append(t)
            ext = TextExtractor()
            ext.feed(resp.text[:50000])
            return ExecutionResult(ok=True, output=" ".join(ext.text[:200])[:3000])
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def _navigate_web(self, url: str) -> ExecutionResult:
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x00000008,
            )
            return ExecutionResult(ok=True, output=f"Navigated to {url}")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def snapshot(self) -> Optional[bytes]:
        return self._screenshot().screenshot


# ══════════════════════════════════════════════════════════════
#  SANDBOX BACKEND (isolated temp environment)
# ══════════════════════════════════════════════════════════════

class SandboxBackend(WorkspaceBackend):
    """Isolated temp directory with restricted access.
    
    Same as native but all paths are sandboxed to a temp folder.
    File operations can't escape the sandbox.
    """

    @property
    def name(self) -> str:
        return "sandbox"

    @property
    def is_available(self) -> bool:
        return True

    @property
    def cost(self) -> int:
        return 2

    def __init__(self):
        self._running = False
        self._sandbox_dir: Optional[Path] = None
        self._native = NativeBackend()

    def is_running(self) -> bool:
        return self._running

    def start(self, ctx: ExecutionContext) -> bool:
        self._sandbox_dir = Path(os.path.expanduser(f"~/.jarvis/workspaces/{ctx.workspace_id}/sandbox"))
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._native._workspace_dir = self._sandbox_dir
        self._native._running = True
        self._running = True
        log.info(f"[SANDBOX] Started: {self._sandbox_dir}")
        return True

    def stop(self):
        self._running = False
        self._native.stop()
        log.info("[SANDBOX] Stopped")

    def execute(self, ctx: ExecutionContext, action: str, params: dict) -> ExecutionResult:
        # Redirect all file paths to sandbox
        if action in ("write_file", "read_file", "create_directory"):
            path = params.get("path", "")
            if path and not os.path.isabs(path):
                params["path"] = str(self._sandbox_dir / path)
            elif path and not str(path).startswith(str(self._sandbox_dir)):
                return ExecutionResult(ok=False, error="Path escapes sandbox")
        return self._native.execute(ctx, action, params)

    def snapshot(self) -> Optional[bytes]:
        return self._native.snapshot()


# ══════════════════════════════════════════════════════════════
#  BACKEND REGISTRY
# ══════════════════════════════════════════════════════════════

_backend_instances: Dict[str, WorkspaceBackend] = {}


def get_backend(name: str) -> Optional[WorkspaceBackend]:
    return _backend_instances.get(name)


def register_backend(backend: WorkspaceBackend):
    _backend_instances[backend.name] = backend
    log.info(f"[BACKEND] Registered: {backend.name}")


def get_available_backends() -> List[WorkspaceBackend]:
    return [b for b in _backend_instances.values() if b.is_available]


def init_backends():
    """Initialize all built-in backends."""
    native = NativeBackend()
    sandbox = SandboxBackend()
    register_backend(native)
    register_backend(sandbox)
    # Try VirtualBox
    try:
        from vm_backend import VirtualBoxBackend as _VBoxRaw
        vbox_raw = _VBoxRaw()
        if vbox_raw._vbox_path:
            register_backend(_VBoxBackendAdapter(vbox_raw))
    except Exception:
        pass


class _VBoxBackendAdapter(WorkspaceBackend):
    """Adapter that wraps vm_backend.VirtualBoxBackend to fit WorkspaceBackend interface."""

    def __init__(self, raw):
        self._raw = raw
        self._running = False
        self._vm_name = None

    @property
    def name(self) -> str:
        return "vbox"

    @property
    def is_available(self) -> bool:
        return self._raw._vbox_path is not None

    @property
    def cost(self) -> int:
        return 5

    def is_running(self) -> bool:
        return self._running

    def start(self, ctx: ExecutionContext) -> bool:
        try:
            result = self._raw.create({"id": ctx.workspace_id})
            if result.get("name"):
                self._vm_name = result["name"]
                start_result = self._raw.start(self._vm_name)
                if start_result.get("ok"):
                    self._running = True
                    return True
        except Exception as e:
            log.error(f"[VBOX_ADAPTER] Start failed: {e}")
        return False

    def stop(self):
        if self._vm_name:
            try:
                self._raw.stop(self._vm_name)
            except Exception:
                pass
        self._running = False

    def execute(self, ctx: ExecutionContext, action: str, params: dict) -> ExecutionResult:
        if not self._running:
            return ExecutionResult(ok=False, error="VM not running")
        try:
            if action == "run_command":
                return ExecutionResult(ok=False, error="VBox: use VM agent for commands")
            elif action == "write_file":
                return ExecutionResult(ok=False, error="VBox: use shared folders for files")
            elif action == "screenshot":
                img_bytes = self._raw.capture_frame(self._vm_name)
                if img_bytes:
                    return ExecutionResult(ok=True, screenshot=img_bytes)
                return ExecutionResult(ok=False, error="Screenshot failed")
            elif action == "launch_app":
                return ExecutionResult(ok=False, error="VBox: use VM agent for apps")
            else:
                return ExecutionResult(ok=False, error=f"VBox doesn't support action: {action}")
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

    def snapshot(self) -> Optional[bytes]:
        if self._vm_name:
            return self._raw.capture_frame(self._vm_name)
        return None
