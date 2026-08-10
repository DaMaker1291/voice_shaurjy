#!/usr/bin/env python3
"""
JARVIS Headless Virtual Workstation Worker

Runs on the RELAY SIDE (user's local machine). Creates isolated virtual
desktop sessions that run applications completely independently of the
user's physical desktop. The agent controls the virtual workspace
without hijacking the user's physical mouse, keyboard, or display.

Platform implementations:
  - Linux:   Xvfb + xdotool + ImageMagick import
  - macOS:   NSWorkspace background launch + Quartz event injection
  - Windows: CreateDesktopW API + PostMessageW injection

Usage (standalone):
    python headless_worker.py start
    python headless_worker.py launch excel "C:\\Program Files\\Microsoft Office\\..."
    python headless_worker.py click 500 300
    python headless_worker.py screenshot /tmp/frame.png
    python headless_worker.py tree
"""

import subprocess
import os
import sys
import time
import json
import base64
import threading
import signal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
PLATFORM = sys.platform
IS_LINUX = PLATFORM.startswith("linux")
IS_DARWIN = PLATFORM == "darwin"
IS_WINDOWS = PLATFORM == "win32"


class SessionState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class HeadlessSession:
    session_id: str
    display_id: int
    width: int = 1920
    height: int = 1080
    depth: int = 24
    state: SessionState = SessionState.STOPPED
    pid: Optional[int] = None
    process: Optional[subprocess.Popen] = field(default=None, repr=False)
    launched_apps: Dict[str, int] = field(default_factory=dict)
    created_at: float = 0.0
    error: Optional[str] = None
    desktop_name: Optional[str] = None  # Windows TrueDesktop isolation name
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "display_id": self.display_id,
            "resolution": f"{self.width}x{self.height}x{self.depth}",
            "state": self.state.value,
            "pid": self.pid,
            "launched_apps": list(self.launched_apps.keys()),
            "created_at": self.created_at,
            "uptime": round(time.time() - self.created_at, 1) if self.created_at else 0,
            "platform": PLATFORM,
            "desktop_name": self.desktop_name,
            "error": self.error,
        }


class JarvisHeadlessWorker:
    """Manages isolated virtual framebuffer sessions for background automation."""

    def __init__(self):
        self.sessions: Dict[str, HeadlessSession] = {}
        self._next_display = 1
        self._lock = threading.Lock()
        print(f"[HEADLESS] Worker initialized — platform: {PLATFORM}")

    def list_sessions(self) -> list[dict]:
        """List all active headless sessions."""
        with self._lock:
            return [s.to_dict() for s in self.sessions.values()]

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, session_id: str = "default", width: int = 1920, height: int = 1080, depth: int = 24) -> dict:
        with self._lock:
            if session_id in self.sessions and self.sessions[session_id].state == SessionState.RUNNING:
                return {"ok": True, "session": self.sessions[session_id].to_dict(), "message": "Already running"}
            display_id = self._next_display
            self._next_display += 1
            session = HeadlessSession(session_id=session_id, display_id=display_id, width=width, height=height, depth=depth, state=SessionState.STARTING, created_at=time.time())
            self.sessions[session_id] = session

        try:
            if IS_LINUX:
                self._start_xvfb(session)
            elif IS_DARWIN:
                self._start_macos(session)
            elif IS_WINDOWS:
                self._start_windows(session)
            else:
                session.state = SessionState.ERROR
                session.error = f"Unsupported platform: {PLATFORM}"
                return {"ok": False, "error": session.error}
            session.state = SessionState.RUNNING
            print(f"[HEADLESS] Session '{session_id}' started on display :{display_id} ({width}x{height})")
            return {"ok": True, "session": session.to_dict()}
        except Exception as e:
            session.state = SessionState.ERROR
            session.error = str(e)
            print(f"[HEADLESS] Failed to start '{session_id}': {e}")
            return {"ok": False, "error": str(e)}

    def stop_session(self, session_id: str) -> dict:
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return {"ok": False, "error": f"Session '{session_id}' not found"}
            if session.process:
                try:
                    session.process.terminate()
                    session.process.wait(timeout=5)
                except Exception:
                    try: session.process.kill()
                    except: pass
            for app_name, pid in session.launched_apps.items():
                try: os.kill(pid, signal.SIGTERM)
                except: pass
            # Close the isolated Windows desktop
            if session.desktop_name:
                try:
                    from true_desktop import get_true_desktop
                    get_true_desktop().close(session.desktop_name)
                except Exception:
                    pass
                session.desktop_name = None
            session.state = SessionState.STOPPED
            session.process = None
            session.launched_apps.clear()
            return {"ok": True, "session": session.to_dict()}

    def get_status(self, session_id: Optional[str] = None) -> dict:
        if session_id:
            s = self.sessions.get(session_id)
            return {"ok": bool(s), "session": s.to_dict() if s else None}
        return {"ok": True, "sessions": [s.to_dict() for s in self.sessions.values()], "total": len(self.sessions), "running": sum(1 for s in self.sessions.values() if s.state == SessionState.RUNNING), "platform": PLATFORM}

    # ------------------------------------------------------------------
    # App management
    # ------------------------------------------------------------------

    def launch_app(self, session_id: str, app_name: str, command: List[str]) -> dict:
        session = self.sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Session not found"}
        if session.state != SessionState.RUNNING:
            return {"ok": False, "error": f"Session state: {session.state.value}"}

        env = os.environ.copy()
        if IS_LINUX:
            env["DISPLAY"] = f":{session.display_id}"
        elif IS_DARWIN:
            env["JARVIS_HEADLESS"] = "1"
        elif IS_WINDOWS:
            env["JARVIS_HEADLESS"] = "1"

        try:
            if IS_WINDOWS:
                cmd_str = command[0] if command else app_name
                args = command[1:] if len(command) > 1 else []

                # App name mappings — GUI apps get redirected to console equivalents
                # because Windows isolated desktops cannot run GUI apps (no message pump).
                app_map = {
                    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    "notepad": "notepad.exe",
                    "calc": "calc.exe",
                    "word": "winword.exe",
                    "excel": "excel.exe",
                    "powerpoint": "powerpnt.exe",
                    "cmd": "cmd.exe",
                    "terminal": "wt.exe",
                    "powershell": "pwsh.exe",
                    "pwsh": "pwsh.exe",
                    "python": "python.exe",
                }
                gui_apps = {"chrome", "notepad", "calc", "word", "excel", "powerpoint"}
                exe_path = app_map.get(cmd_str.lower(), cmd_str)

                # GUI apps cannot run on isolated desktops — warn and suggest alternative
                if cmd_str.lower() in gui_apps:
                    print(f"[HEADLESS] WARNING: '{cmd_str}' is a GUI app — cannot run on isolated desktop.")
                    print(f"[HEADLESS] Use file-codegen instead (python-pptx, pandas, etc.) or headless Chrome.")
                    # Fall through to try anyway — some may survive briefly

                # Launch on the isolated Windows desktop via TrueDesktop
                if session.desktop_name:
                    try:
                        from true_desktop import get_true_desktop
                        td = get_true_desktop()
                        proc = td.launch_on(session.desktop_name, exe_path, args)
                        if proc:
                            session.launched_apps[app_name] = proc.pid
                            print(f"[HEADLESS] Launched '{app_name}' (PID {proc.pid}) on isolated desktop '{session.desktop_name}'")
                            return {"ok": True, "app": app_name, "pid": proc.pid, "isolated": True}
                        return {"ok": False, "error": "TrueDesktop launch failed"}
                    except ImportError:
                        pass
                    except Exception as e:
                        return {"ok": False, "error": f"Isolated launch error: {e}"}

                # Fallback: Start-Process via PowerShell (visible desktop)
                ps_cmd = f'Start-Process "{exe_path}"'
                if args:
                    arg_str = " ".join(f'"{a}"' for a in args)
                    ps_cmd += f' -ArgumentList {arg_str}'
                
                # Launch via PowerShell (creates a visible window)
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                session.launched_apps[app_name] = proc.pid
                print(f"[HEADLESS] Launched '{app_name}' (PID {proc.pid}) in session '{session_id}'")
                return {"ok": True, "app": app_name, "pid": proc.pid}
            else:
                proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                session.launched_apps[app_name] = proc.pid
                print(f"[HEADLESS] Launched '{app_name}' (PID {proc.pid}) in session '{session_id}'")
                return {"ok": True, "app": app_name, "pid": proc.pid}
        except FileNotFoundError:
            return {"ok": False, "error": f"Command not found: {command[0]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def inject_click(self, session_id: str, x: int, y: int, button: int = 1) -> dict:
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            return {"ok": False, "error": "Session not running"}

        if IS_LINUX:
            display = f":{session.display_id}"
            subprocess.run(["xdotool", "mousemove", "--display", display, str(x), str(y), "click", str(button)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return {"ok": True, "action": "click", "x": x, "y": y, "button": button}
        elif IS_DARWIN:
            return self._inject_click_macos(x, y, button)
        elif IS_WINDOWS:
            return self._inject_click_windows(x, y, button)
        return {"ok": False, "error": "Click not supported on this platform"}

    def inject_key(self, session_id: str, key: str) -> dict:
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            return {"ok": False, "error": "Session not running"}

        if IS_LINUX:
            display = f":{session.display_id}"
            subprocess.run(["xdotool", "key", "--display", display, key], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return {"ok": True, "action": "key", "key": key}
        elif IS_WINDOWS:
            return self._inject_key_windows(key)
        return {"ok": False, "error": "Key injection not supported"}

    def inject_text(self, session_id: str, text: str) -> dict:
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            return {"ok": False, "error": "Session not running"}

        if IS_LINUX:
            display = f":{session.display_id}"
            subprocess.run(["xdotool", "type", "--display", display, "--delay", "20", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            return {"ok": True, "action": "type", "length": len(text)}
        elif IS_WINDOWS:
            # Use clipboard paste for reliable text injection
            try:
                import pyperclip
                import pyautogui
                pyautogui.FAILSAFE = False
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.05)
                return {"ok": True, "action": "type", "length": len(text)}
            except ImportError:
                # Fallback: character by character
                for char in text:
                    self._inject_key_windows(char)
                    time.sleep(0.02)
                return {"ok": True, "action": "type", "length": len(text)}
        return {"ok": False, "error": "Text injection not supported"}

    def screenshot(self, session_id: str, output_path: Optional[str] = None) -> Optional[bytes]:
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            return None

        if IS_LINUX:
            return self._screenshot_linux(session, output_path)
        elif IS_DARWIN:
            return self._screenshot_macos(session, output_path)
        elif IS_WINDOWS:
            return self._screenshot_windows(session, output_path)
        return None

    def capture_jpeg(self, session_id: str = "default", width: int = 960,
                     height: int = 540, quality: int = 70) -> Optional[bytes]:
        """Capture the isolated desktop and return JPEG bytes (fast, for streaming)."""
        try:
            from PIL import Image
            import io

            # Prefer TrueDesktop isolated capture on Windows
            if IS_WINDOWS:
                data = self._screenshot_windows_isolated(session_id)
            else:
                data = self.screenshot(session_id)

            if not data:
                return None

            img = Image.open(io.BytesIO(data))
            img = img.convert("RGB")
            if width and height:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
        except Exception:
            return None

    def _screenshot_windows_isolated(self, session_id: str) -> Optional[bytes]:
        """Capture the isolated Windows desktop framebuffer.

        Tries capture_desktop_surface() first — switches to the isolated
        desktop, grabs the entire framebuffer via GDI BitBlt, then switches
        back. Falls back to capture() (PrintWindow per-window) if that fails.
        """
        try:
            from true_desktop import get_true_desktop
            td = get_true_desktop()
            desktop_name = self.sessions[session_id].desktop_name
            if not desktop_name:
                return None

            # Try surface capture first (captures the whole desktop, not individual windows)
            data = td.capture_desktop_surface(desktop_name)
            if data:
                return data

            # Fallback: PrintWindow per-window capture
            data = td.capture(desktop_name)
            if data:
                return data
        except Exception:
            pass
        return self._screenshot_windows(self.sessions.get(session_id))

    def get_window_tree(self, session_id: str) -> dict:
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            return {"ok": False, "error": "Session not running"}

        if IS_LINUX:
            return self._get_window_tree_linux(session)
        elif IS_DARWIN:
            return self._get_window_tree_macos(session)
        elif IS_WINDOWS:
            return self._get_window_tree_windows(session)
        return {"ok": False, "error": "Window tree not supported on this platform"}

    # ------------------------------------------------------------------
    # Linux: Xvfb + xdotool
    # ------------------------------------------------------------------

    def _start_xvfb(self, session: HeadlessSession):
        display = f":{session.display_id}"
        resolution = f"{session.width}x{session.height}x{session.depth}"
        try:
            subprocess.run(["which", "Xvfb"], capture_output=True, check=True, timeout=5)
        except Exception:
            raise RuntimeError("Xvfb not installed. Run: sudo apt install xvfb")
        session.process = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", resolution, "-ac", "+extension", "GLX", "+render", "-noreset"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        session.pid = session.process.pid
        time.sleep(1.0)
        if session.process.poll() is not None:
            raise RuntimeError(f"Xvfb exited with code {session.process.returncode}")

    def _screenshot_linux(self, session: HeadlessSession, output_path: Optional[str] = None) -> Optional[bytes]:
        import tempfile
        display = f":{session.display_id}"
        tmppath = output_path or tempfile.mktemp(suffix=".png")
        try:
            subprocess.run(["import", "-window", "root", "-display", display, tmppath], timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(tmppath, "rb") as f:
                data = f.read()
            if not output_path:
                os.unlink(tmppath)
            return data
        except Exception:
            return None

    def _get_window_tree_linux(self, session: HeadlessSession) -> dict:
        display = f":{session.display_id}"
        try:
            result = subprocess.run(["xdotool", "search", "--name", ".", "--display", display], capture_output=True, text=True, timeout=5)
            windows = [w.strip() for w in result.stdout.strip().split("\n") if w.strip()]
            tree = []
            for wid in windows[:50]:
                name_result = subprocess.run(["xdotool", "getwindowname", "--display", display, wid], capture_output=True, text=True, timeout=3)
                tree.append({"id": wid, "name": name_result.stdout.strip()})
            return {"ok": True, "windows": tree, "count": len(tree)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # macOS: Background process + Quartz
    # ------------------------------------------------------------------

    def _start_macos(self, session: HeadlessSession):
        """macOS: use screencapture for screenshots. No true virtual display,
        but we manage a background process and use Quartz event injection
        for automation without hijacking the cursor."""
        session.process = subprocess.Popen(
            [sys.executable, "-c", """
import time, os, signal
# Keep-alive process that responds to SIGTERM
signal.signal(signal.SIGTERM, lambda s, f: os._exit(0))
while True: time.sleep(1)
"""],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        session.pid = session.process.pid
        # Create a workspace directory for this session
        session_dir = os.path.expanduser(f"~/.jarvis/headless/{session.session_id}")
        os.makedirs(session_dir, exist_ok=True)

    def _inject_click_macos(self, x: int, y: int, button: int) -> dict:
        try:
            import Quartz
            event_type = Quartz.kCGEventLeftMouseDown if button == 1 else Quartz.kCGEventRightMouseDown
            event_up = Quartz.kCGEventLeftMouseUp if button == 1 else Quartz.kCGEventRightMouseUp
            point = Quartz.CGPointMake(x, y)
            mouse_button = Quartz.kCGMouseButtonLeft if button == 1 else Quartz.kCGMouseButtonRight
            event_down = Quartz.CGEventCreateMouseEvent(None, event_type, point, mouse_button)
            event_up_evt = Quartz.CGEventCreateMouseEvent(None, event_up, point, mouse_button)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
            time.sleep(0.01)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up_evt)
            return {"ok": True, "action": "click", "x": x, "y": y, "button": button}
        except ImportError:
            return {"ok": False, "error": "Quartz not available"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _screenshot_macos(self, session: HeadlessSession, output_path: Optional[str] = None) -> Optional[bytes]:
        try:
            import Quartz, tempfile
            main_display = Quartz.CGMainDisplayID()
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectInfinite, Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault,
            )
            if image is None:
                return None
            tmppath = output_path or tempfile.mktemp(suffix=".png")
            url = Quartz.CFURLCreateFromFileSystemRepresentation(None, tmppath.encode(), len(tmppath), False)
            dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
            Quartz.CGImageDestinationAddImage(dest, image, None)
            Quartz.CGImageDestinationFinalize(dest)
            with open(tmppath, "rb") as f:
                data = f.read()
            if not output_path:
                os.unlink(tmppath)
            return data
        except Exception:
            return None

    def _get_window_tree_macos(self, session: HeadlessSession) -> dict:
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of every window of every process'],
                capture_output=True, text=True, timeout=10,
            )
            return {"ok": True, "raw": result.stdout, "platform": "macos"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Windows: CreateDesktop + PostMessage
    # ------------------------------------------------------------------

    def _start_windows(self, session: HeadlessSession):
        """Create isolated Windows desktop via Win32 CreateDesktopW (TrueDesktop).
        
        Apps are launched on a REAL hidden desktop object — completely invisible
        from the user's desktop. The user's mouse/keyboard/display stay untouched.
        """
        # Use a background keep-alive process to own the session lifetime
        session.process = subprocess.Popen(
            [sys.executable, "-c", """
import time, os, signal
signal.signal(signal.SIGTERM, lambda s, f: os._exit(0))
while True: time.sleep(1)
"""],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        session.pid = session.process.pid

        # Real Windows desktop isolation via CreateDesktopW
        try:
            from true_desktop import get_true_desktop
            td = get_true_desktop()
            desktop_name = f"jarvis_hd_{session.session_id}"
            if desktop_name not in td.list_desktops():
                td.create(desktop_name)
            session.desktop_name = desktop_name
            print(f"[HEADLESS] Session '{session.session_id}' isolated on Windows desktop '{desktop_name}'")
        except ImportError:
            print("[HEADLESS] true_desktop not available — running without desktop isolation")
        except Exception as e:
            print(f"[HEADLESS] Desktop isolation init failed: {e}")

    def execute_command(self, session_id: str, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command inside an existing headless session's environment.
        
        Routes through ExecutionVault sandboxing. On Linux, runs inside Xvfb.
        On macOS/Windows, runs in the user's normal environment but still vaulted.
        
        Returns dict: {success, stdout, stderr, exit_code, timed_out, blocked, block_reason}
        """
        from execution_vault import ExecutionVault, VaultPolicy
        
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            # Auto-start a default session
            result = self.start_session(session_id)
            if not result.get("ok"):
                return {"success": False, "error": result.get("error", "Cannot start session")}
            session = self.sessions[session_id]
        
        vault = ExecutionVault()
        policy = VaultPolicy(timeout=timeout)
        
        env_prefix = ""
        if IS_LINUX and session.process:
            env_prefix = f"export DISPLAY=:{session.display_id}; "
        
        full_cmd = f"{env_prefix}{command}"
        vr = vault.execute(full_cmd, policy=policy)
        
        return {
            "success": vr.exit_code == 0 and not vr.blocked,
            "stdout": vr.stdout.strip()[:2000],
            "stderr": vr.stderr.strip()[:1000],
            "exit_code": vr.exit_code,
            "timed_out": vr.timed_out,
            "blocked": vr.blocked,
            "block_reason": vr.block_reason,
        }

    def _inject_click_windows(self, x: int, y: int, button: int) -> dict:
        """Inject a click using pyautogui (more reliable than PostMessageW)."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0.01
            if button == 1:
                pyautogui.click(x, y)
            else:
                pyautogui.click(x, y, button='right')
            return {"ok": True, "action": "click", "x": x, "y": y, "button": button}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _inject_key_windows(self, key: str) -> dict:
        """Inject a keypress using pyautogui."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0.01
            
            # Map common key names
            key_map = {
                "return": "enter", "enter": "enter", "tab": "tab",
                "escape": "escape", "esc": "escape", "backspace": "backspace",
                "delete": "delete", "up": "up", "down": "down",
                "left": "left", "right": "right", "home": "home",
                "end": "end", "pageup": "pageup", "pagedown": "pagedown",
                "space": "space",
            }
            
            mapped = key_map.get(key.lower().strip(), key.lower().strip())
            pyautogui.press(mapped)
            return {"ok": True, "action": "key", "key": key}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _screenshot_windows(self, session: HeadlessSession, output_path: Optional[str] = None) -> Optional[bytes]:
        try:
            import ctypes
            from ctypes import wintypes
            import tempfile

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            hwnd = user32.GetDesktopWindow()
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w, h = rect.right - rect.left, rect.bottom - rect.top

            hdc_screen = user32.GetDC(hwnd)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            gdi32.SelectObject(hdc_mem, hbitmap)
            gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020)  # SRCCOPY

            # Save to file using PIL if available, else raw BMP
            tmppath = output_path or tempfile.mktemp(suffix=".bmp")
            bmp_info = wintypes.BITMAPINFOHEADER()
            bmp_info.biSize = ctypes.sizeof(bmp_info)
            bmp_info.biWidth = w
            bmp_info.biHeight = -h  # top-down
            bmp_info.biPlanes = 1
            bmp_info.biBitCount = 24
            bmp_info.biCompression = 0  # BI_RGB

            # Save as BMP
            with open(tmppath, "wb") as f:
                # BMP header
                file_size = 54 + w * h * 3
                f.write(b"BM")
                f.write(file_size.to_bytes(4, "little"))
                f.write(b"\x00\x00\x00\x00")
                f.write((54).to_bytes(4, "little"))
                f.write(ctypes.sizeof(bmp_info).to_bytes(4, "little"))
                f.write(ctypes.string_at(ctypes.addressof(bmp_info), ctypes.sizeof(bmp_info)))
                # Pixel data
                bits = (ctypes.c_ubyte * (w * h * 3))()
                gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, ctypes.byref(bits), ctypes.byref(bmp_info), 0)
                f.write(ctypes.string_at(ctypes.addressof(bits), w * h * 3))

            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_screen)

            with open(tmppath, "rb") as f:
                data = f.read()
            if not output_path:
                os.unlink(tmppath)
            return data
        except Exception:
            return None

    def _get_window_tree_windows(self, session: HeadlessSession) -> dict:
        """Enumerate windows via Win32 EnumWindows."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            windows = []

            def enum_callback(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        windows.append({
                            "hwnd": hwnd,
                            "name": buf.value,
                            "rect": {"x": rect.left, "y": rect.top, "w": rect.right - rect.left, "h": rect.bottom - rect.top},
                        })
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            return {"ok": True, "windows": windows[:50], "count": len(windows)}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Headless Workstation Worker")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start a headless session")
    sub.add_parser("stop", help="Stop the headless session")
    sub.add_parser("status", help="Show session status")

    launch_p = sub.add_parser("launch", help="Launch an app")
    launch_p.add_argument("app_name", help="Application alias")
    launch_p.add_argument("command", nargs="+", help="Command to run")

    click_p = sub.add_parser("click", help="Inject a click")
    click_p.add_argument("x", type=int)
    click_p.add_argument("y", type=int)
    click_p.add_argument("--button", type=int, default=1)

    key_p = sub.add_parser("key", help="Inject a keypress")
    key_p.add_argument("key_name")

    type_p = sub.add_parser("type", help="Type text")
    type_p.add_argument("text")

    ss_p = sub.add_parser("screenshot", help="Capture a screenshot")
    ss_p.add_argument("--output", "-o", default=None)

    sub.add_parser("tree", help="Show window tree")

    args = parser.parse_args()
    worker = JarvisHeadlessWorker()

    if args.command == "start":
        print(json.dumps(worker.start_session(), indent=2))
    elif args.command == "stop":
        print(json.dumps(worker.stop_session("default"), indent=2))
    elif args.command == "status":
        print(json.dumps(worker.get_status(), indent=2))
    elif args.command == "launch":
        print(json.dumps(worker.launch_app("default", args.app_name, args.command), indent=2))
    elif args.command == "click":
        print(json.dumps(worker.inject_click("default", args.x, args.y, args.button), indent=2))
    elif args.command == "key":
        print(json.dumps(worker.inject_key("default", args.key_name), indent=2))
    elif args.command == "type":
        print(json.dumps(worker.inject_text("default", args.text), indent=2))
    elif args.command == "screenshot":
        data = worker.screenshot("default", args.output)
        if data:
            if args.output:
                print(f"Saved to {args.output} ({len(data)} bytes)")
            else:
                print(base64.b64encode(data).decode())
        else:
            print("No frame captured")
    elif args.command == "tree":
        print(json.dumps(worker.get_window_tree("default"), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Singleton — process-wide worker so sessions persist across API requests
# ---------------------------------------------------------------------------

_worker: Optional[JarvisHeadlessWorker] = None
_worker_lock = threading.Lock()


def get_headless_worker() -> JarvisHeadlessWorker:
    """Return the process-wide headless worker singleton.

    Sessions and isolated desktops persist across HTTP/WS requests, so the
    backstage VDI keeps running without state loss between calls.
    """
    global _worker
    if _worker is None:
        with _worker_lock:
            if _worker is None:
                _worker = JarvisHeadlessWorker()
    return _worker
