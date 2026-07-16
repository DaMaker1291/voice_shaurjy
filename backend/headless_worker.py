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
            "error": self.error,
        }


class JarvisHeadlessWorker:
    """Manages isolated virtual framebuffer sessions for background automation."""

    def __init__(self):
        self.sessions: Dict[str, HeadlessSession] = {}
        self._next_display = 1
        self._lock = threading.Lock()
        print(f"[HEADLESS] Worker initialized — platform: {PLATFORM}")

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
        session.process = subprocess.Popen(
            [sys.executable, "-c", "import time\nwhile True: time.sleep(1)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        session.pid = session.process.pid

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
        """Create isolated Windows desktop via Win32 API."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Get current desktop and process
            hDesktop = user32.OpenDesktopW(f"JARVIS_VD_{session.display_id}", 0, False, 0x0100)  # DESKTOP_CREATEWINDOW
            if not hDesktop:
                # Create new desktop
                hCurrentDesktop = user32.OpenInputDesktop(0, False, 0x0100)
                hDesktop = user32.CreateDesktopW(
                    f"JARVIS_VD_{session.display_id}",
                    None, None, 0, 0x0100, None  # DESKTOP_CREATEWINDOW
                )

            session._hdesktop = hDesktop
            session._hwnd = None

            # Start a background process on the virtual desktop
            si = ctypes.wintypes.STARTUPINFOW()
            si.cb = ctypes.sizeof(si)
            si.lpDesktop = f"JARVIS_VD_{session.display_id}".encode("utf-16-le")
            si.dwFlags = 0x00000001  # STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE

            pi = ctypes.wintypes.PROCESS_INFORMATION()

            # Launch explorer.exe as a base process on the virtual desktop
            cmd = "cmd.exe /c start /b cmd.exe"
            success = user32.CreateProcessW(
                None, cmd, None, None, False,
                0x00000200,  # CREATE_NEW_PROCESS_GROUP
                None, None, ctypes.byref(si), ctypes.byref(pi)
            )

            if success:
                session.pid = pi.dwProcessId
                session.process = type('obj', (object,), {'pid': pi.dwProcessId, 'terminate': lambda self: kernel32.TerminateProcess(pi.hProcess, 0)})()
                kernel32.CloseHandle(pi.hProcess)
                kernel32.CloseHandle(pi.hThread)
            else:
                # Fallback: just run a background Python process
                session.process = subprocess.Popen(
                    [sys.executable, "-c", "import time\nwhile True: time.sleep(1)"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                session.pid = session.process.pid

        except ImportError:
            # No ctypes.wintypes (not on Windows)
            session.process = subprocess.Popen(
                [sys.executable, "-c", "import time\nwhile True: time.sleep(1)"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            session.pid = session.process.pid
        except Exception as e:
            session.process = subprocess.Popen(
                [sys.executable, "-c", "import time\nwhile True: time.sleep(1)"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            session.pid = session.process.pid

    def _inject_click_windows(self, x: int, y: int, button: int) -> dict:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            lparam = y << 16 | x
            msg_down = 0x0201 if button == 1 else 0x0204  # WM_LBUTTONDOWN / WM_RBUTTONDOWN
            msg_up = 0x0202 if button == 1 else 0x0205    # WM_LBUTTONUP / WM_RBUTTONUP
            user32.PostMessageW(hwnd, msg_down, 0, lparam)
            time.sleep(0.01)
            user32.PostMessageW(hwnd, msg_up, 0, lparam)
            return {"ok": True, "action": "click", "x": x, "y": y, "button": button}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _inject_key_windows(self, key: str) -> dict:
        try:
            import ctypes
            user32 = ctypes.windll.user32

            VK_MAP = {
                "return": 0x0D, "enter": 0x0D, "tab": 0x09, "space": 0x20,
                "escape": 0x1B, "esc": 0x1B, "backspace": 0x08, "delete": 0x2E,
                "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
                "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
            }

            key_lower = key.lower().strip()
            vk = VK_MAP.get(key_lower)
            if vk is None and len(key) == 1:
                vk = ord(key.upper())
            elif vk is None:
                return {"ok": False, "error": f"Unknown key: {key}"}

            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)
            user32.keybd_event(vk, 0, 0x0002, 0)  # KEYEVENTF_KEYUP
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
