"""
JARVIS VM Infestation Daemon — Persistent, self-healing agent inside the VM.
Runs as a root service, auto-installs dependencies, controls GUI/terminal,
and listens for commands from the main app.

Deploy inside the VM:
  python jarvis_vm_daemon.py              # Run directly
  python jarvis_vm_daemon.py --install    # Install as systemd service
"""
import os
import sys
import json
import time
import subprocess
import threading
import logging
import traceback
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vm_daemon")

# ── Auto-heal: install missing packages ──

def auto_heal(error_traceback: str) -> bool:
    """Analyze error and auto-install missing dependencies."""
    logger.info(f"Auto-healing: {error_traceback[:200]}")

    if "No module named" in error_traceback:
        pkg = error_traceback.split("No module named")[-1].strip("'\" \n")
        pkg = pkg.split(".")[0]  # Get base module name
        logger.info(f"Installing missing Python package: {pkg}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True, timeout=60
            )
            return True
        except Exception as e:
            logger.error(f"pip install failed: {e}")
            return False

    elif "command not found" in error_traceback:
        cmd = error_traceback.split(":")[0].strip()
        logger.info(f"Installing missing system command: {cmd}")
        try:
            subprocess.run(["apt-get", "update", "-y"], capture_output=True, timeout=120)
            subprocess.run(["apt-get", "install", "-y", cmd], capture_output=True, timeout=120)
            return True
        except Exception as e:
            logger.error(f"apt install failed: {e}")
            return False

    return False


# ── Shell Monitor — watch terminal commands ──

class ShellMonitor:
    """Monitor shell commands and auto-fix errors."""

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        """Watch for failed commands in background."""
        # On Windows, monitor PowerShell event logs
        # On Linux, monitor syslog/journal
        while self._running:
            time.sleep(5)
            # Placeholder: in production, hook into system event logs


# ── GUI Controller — keyboard/mouse inside VM ──

class GUIController:
    """Control the VM's GUI — keyboard, mouse, window management."""

    def __init__(self):
        self._keyboard = None
        self._mouse = None
        self._init_controllers()

    def _init_controllers(self):
        try:
            from pynput.keyboard import Controller as KC
            from pynput.mouse import Controller as MC
            self._keyboard = KC()
            self._mouse = MC()
        except ImportError:
            logger.warning("pynput not available — GUI control disabled")

    def type_text(self, text: str):
        """Type text into the focused window."""
        if self._keyboard:
            self._keyboard.type(text)
            return True
        return False

    def press_key(self, key: str):
        """Press a keyboard key."""
        if self._keyboard:
            from pynput.keyboard import Key
            try:
                self._keyboard.press(getattr(Key, key, key))
                self._keyboard.release(getattr(Key, key, key))
                return True
            except Exception:
                return False
        return False

    def click(self, x: int, y: int, button: str = "left"):
        """Click at position."""
        if self._mouse:
            from pynput.mouse import Button
            self._mouse.position = (x, y)
            btn = Button.left if button == "left" else Button.right
            self._mouse.click(btn)
            return True
        return False

    def move_mouse(self, x: int, y: int):
        """Move mouse to position."""
        if self._mouse:
            self._mouse.position = (x, y)
            return True
        return False


# ── Process Manager — monitor and control VM processes ──

class ProcessManager:
    """Monitor and control processes inside the VM."""

    def list_processes(self) -> list[dict]:
        """List running processes."""
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV"],
                    capture_output=True, text=True, timeout=10
                )
                processes = []
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.split(",")
                    if len(parts) >= 5:
                        processes.append({
                            "name": parts[0].strip('"'),
                            "pid": parts[1].strip('"'),
                            "memory": parts[4].strip('"'),
                        })
                return processes
            else:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=10
                )
                processes = []
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        processes.append({
                            "user": parts[0],
                            "pid": parts[1],
                            "cpu": parts[2],
                            "mem": parts[3],
                            "command": parts[10],
                        })
                return processes
        except Exception:
            return []

    def kill_process(self, pid: int) -> bool:
        """Kill a process by PID."""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=10)
            else:
                subprocess.run(["kill", "-9", str(pid)],
                               capture_output=True, timeout=10)
            return True
        except Exception:
            return False

    def find_process(self, name: str) -> list[dict]:
        """Find processes by name."""
        all_procs = self.list_processes()
        return [p for p in all_procs if name.lower() in str(p.get("name", p.get("command", ""))).lower()]


# ── File System Monitor ──

class FileSystemMonitor:
    """Monitor file system changes inside the VM."""

    def __init__(self, watch_dirs: list[str] = None):
        self.watch_dirs = watch_dirs or [str(Path.home())]
        self._callbacks = []

    def on_change(self, callback):
        """Register a callback for file changes."""
        self._callbacks.append(callback)

    def scan_directory(self, path: str) -> list[dict]:
        """Scan a directory and return file info."""
        files = []
        try:
            for item in Path(path).iterdir():
                files.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                    "modified": item.stat().st_mtime,
                })
        except Exception:
            pass
        return files


# ── VM Infestation Engine ──

class VMInfestationEngine:
    """
    Sovereign OS daemon running inside the VM with root privileges.
    Executes code, inspects windows, manipulates app states,
    auto-heals dependencies, and listens for commands.
    """

    def __init__(self, ws_port: int = 8767):
        self.ws_port = ws_port
        self.gui = GUIController()
        self.processes = ProcessManager()
        self.filesystem = FileSystemMonitor()
        self.shell_monitor = ShellMonitor()
        self._running = False
        self._command_handlers = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default command handlers."""
        self._command_handlers = {
            "exec": self._handle_exec,
            "type": self._handle_type,
            "click": self._handle_click,
            "key": self._handle_key,
            "kill": self._handle_kill,
            "list_processes": self._handle_list_processes,
            "list_files": self._handle_list_files,
            "read_file": self._handle_read_file,
            "write_file": self._handle_write_file,
            "install": self._handle_install,
            "screenshot": self._handle_screenshot,
            "status": self._handle_status,
        }

    def start(self):
        """Start the infestation daemon."""
        self._running = True
        logger.info("VM Infestation Daemon starting...")
        logger.info(f"PID: {os.getpid()}")
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Python: {sys.version}")

        # Start shell monitor
        self.shell_monitor.start()

        # Start WebSocket command listener
        self._start_ws_listener()

        logger.info("VM Infestation Daemon active and listening")

    def stop(self):
        """Stop the daemon."""
        self._running = False
        self.shell_monitor.stop()

    def _start_ws_listener(self):
        """Start WebSocket server for receiving commands."""
        try:
            import websockets

            async def handler(websocket, path=None):
                logger.info("Main app connected to VM daemon")
                try:
                    async for message in websocket:
                        try:
                            cmd = json.loads(message)
                            response = await self.dispatch(cmd)
                            await websocket.send(json.dumps(response, default=str))
                        except json.JSONDecodeError:
                            await websocket.send(json.dumps({"success": False, "error": "Invalid JSON"}))
                        except Exception as e:
                            await websocket.send(json.dumps({"success": False, "error": str(e)}))
                except Exception:
                    pass
                logger.info("Main app disconnected")

            async def main():
                async with websockets.serve(handler, "127.0.0.1", self.ws_port):
                    logger.info(f"VM daemon listening on ws://127.0.0.1:{self.ws_port}")
                    await asyncio.Future()

            threading.Thread(target=lambda: asyncio.run(main()), daemon=True).start()
        except ImportError:
            logger.warning("websockets not installed — daemon runs without WS listener")

    async def dispatch(self, cmd: dict) -> dict:
        """Dispatch a command to the appropriate handler."""
        action = cmd.get("action", cmd.get("type", ""))
        handler = self._command_handlers.get(action)
        if handler:
            try:
                result = handler(cmd)
                if asyncio.iscoroutine(result):
                    result = await result
                return {"success": True, "result": result}
            except Exception as e:
                # Auto-heal on failure
                tb = traceback.format_exc()
                if auto_heal(tb):
                    # Retry after healing
                    try:
                        result = handler(cmd)
                        if asyncio.iscoroutine(result):
                            result = await result
                        return {"success": True, "result": result, "healed": True}
                    except Exception as e2:
                        return {"success": False, "error": str(e2)}
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Unknown action: {action}"}

    # ── Command Handlers ──

    def _handle_exec(self, cmd: dict) -> dict:
        """Execute a shell command."""
        command = cmd.get("command", "")
        if not command:
            return {"error": "No command"}
        try:
            from execution_vault import vaulted_run
            vr = vaulted_run(command, timeout=cmd.get("timeout", 60))
            if vr.blocked:
                return {"error": f"BLOCKED: {vr.block_reason}", "stdout": "", "stderr": vr.block_reason, "returncode": -1}
            return {
                "stdout": vr.stdout[:5000],
                "stderr": vr.stderr[:2000],
                "returncode": vr.exit_code,
            }
        except Exception as e:
            return {"error": f"Execution error: {e}"}

    def _handle_type(self, cmd: dict) -> dict:
        """Type text into focused window."""
        text = cmd.get("text", "")
        return {"typed": self.gui.type_text(text)}

    def _handle_click(self, cmd: dict) -> dict:
        """Click at position."""
        x = cmd.get("x", 0)
        y = cmd.get("y", 0)
        button = cmd.get("button", "left")
        return {"clicked": self.gui.click(x, y, button)}

    def _handle_key(self, cmd: dict) -> dict:
        """Press a key."""
        key = cmd.get("key", "")
        return {"pressed": self.gui.press_key(key)}

    def _handle_kill(self, cmd: dict) -> dict:
        """Kill a process."""
        pid = cmd.get("pid", 0)
        name = cmd.get("name", "")
        if pid:
            return {"killed": self.processes.kill_process(pid)}
        elif name:
            procs = self.processes.find_process(name)
            for p in procs:
                self.processes.kill_process(int(p.get("pid", 0)))
            return {"killed": len(procs), "processes": procs}
        return {"error": "No pid or name"}

    def _handle_list_processes(self, cmd: dict) -> dict:
        """List running processes."""
        return {"processes": self.processes.list_processes()}

    def _handle_list_files(self, cmd: dict) -> dict:
        """List files in a directory."""
        path = cmd.get("path", str(Path.home()))
        return {"files": self.filesystem.scan_directory(path)}

    def _handle_read_file(self, cmd: dict) -> dict:
        """Read a file."""
        path = cmd.get("path", "")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(cmd.get("max_bytes", 50000))
            return {"content": content}
        except Exception as e:
            return {"error": str(e)}

    def _handle_write_file(self, cmd: dict) -> dict:
        """Write a file."""
        path = cmd.get("path", "")
        content = cmd.get("content", "")
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"written": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_install(self, cmd: dict) -> dict:
        """Install a package."""
        package = cmd.get("package", "")
        pkg_type = cmd.get("type", "pip")
        if pkg_type == "pip":
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True, text=True, timeout=120
            )
        elif pkg_type == "apt":
            subprocess.run(["apt-get", "update", "-y"], capture_output=True, timeout=120)
            result = subprocess.run(
                ["apt-get", "install", "-y", package],
                capture_output=True, text=True, timeout=120
            )
        else:
            return {"error": f"Unknown package type: {pkg_type}"}
        return {
            "installed": result.returncode == 0,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
        }

    def _handle_screenshot(self, cmd: dict) -> dict:
        """Take a screenshot."""
        try:
            from PIL import Image
            import io
            if sys.platform == "win32":
                import ctypes
                user32 = ctypes.windll.user32
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                # Use mss as fallback
                from mss import mss
                with mss() as sct:
                    shot = sct.grab(sct.monitors[1])
                    img = Image.frombytes("RGB", shot.size, shot.rgb)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    import base64
                    return {"screenshot": base64.b64encode(buf.getvalue()).decode()}
            else:
                from mss import mss
                with mss() as sct:
                    shot = sct.grab(sct.monitors[1])
                    img = Image.frombytes("RGB", shot.size, shot.rgb)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    import base64
                    return {"screenshot": base64.b64encode(buf.getvalue()).decode()}
        except Exception as e:
            return {"error": str(e)}

    def _handle_status(self, cmd: dict) -> dict:
        """Get daemon status."""
        return {
            "running": self._running,
            "pid": os.getpid(),
            "platform": sys.platform,
            "python": sys.version,
            "handlers": list(self._command_handlers.keys()),
        }


# ── Systemd Service Installation ──

SYSTEMD_SERVICE = """[Unit]
Description=JARVIS VM Infestation Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={workdir}
ExecStart={python} {script}
Restart=always
RestartSec=2
KillMode=process
Environment=JARVIS_VM_MODE=1

[Install]
WantedBy=multi-user.target
"""


def install_systemd_service():
    """Install the daemon as a systemd service."""
    workdir = str(Path(__file__).parent)
    script = str(Path(__file__))
    python = sys.executable

    service_content = SYSTEMD_SERVICE.format(
        workdir=workdir, python=python, script=script
    )
    service_path = "/etc/systemd/system/jarvis-vm-daemon.service"

    try:
        with open(service_path, "w") as f:
            f.write(service_content)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", "jarvis-vm-daemon"], check=True)
        subprocess.run(["systemctl", "start", "jarvis-vm-daemon"], check=True)
        logger.info(f"Service installed: {service_path}")
        return True
    except Exception as e:
        logger.error(f"Service installation failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[VM] %(message)s")

    if "--install" in sys.argv:
        install_systemd_service()
    else:
        daemon = VMInfestationEngine()
        daemon.start()

        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            daemon.stop()
            logger.info("VM daemon stopped")
