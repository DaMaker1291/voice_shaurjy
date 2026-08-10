"""
JARVIS VDI Manager — Virtual Display Isolation.
Runs apps in an isolated background display, streams frames to the viewer.

Linux: Xvfb virtual display
Windows: Hidden Win32 desktop + per-window capture via PrintWindow API
"""
import os
import sys
import time
import json
import ctypes
import ctypes.wintypes as wintypes
import subprocess
import threading
import logging
import io
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vdi")

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"


# ── Windows Win32 Structures ──

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    SRCCOPY = 0x00CC0020
    PW_CLIENTONLY = 0x01
    PW_RENDERFULLCONTENT = 0x02

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class WNDENUMPROC(ctypes.WINFUNCTYPE, wintypes.BOOL,
                       wintypes.HWND, wintypes.LPARAM):
        pass


class VDIManager:
    """Manages virtual display isolation for the agent."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self._hdesktop = None
        self._desktop_name = None
        self._xvfb_proc = None
        self._running = False
        self._frame_callback = None
        self._capture_thread = None

    def start(self) -> bool:
        """Start the virtual display."""
        if IS_WINDOWS:
            return self._start_windows()
        elif IS_LINUX:
            return self._start_linux()
        else:
            logger.warning(f"VDI not supported on {sys.platform}")
            return False

    def stop(self):
        """Stop the virtual display."""
        self._running = False
        if IS_WINDOWS and self._hdesktop:
            try:
                user32.CloseDesktop(self._hdesktop)
            except Exception:
                pass
            self._hdesktop = None
        if self._xvfb_proc:
            self._xvfb_proc.terminate()
            self._xvfb_proc = None
        logger.info("VDI stopped")

    # ── Windows: Hidden Win32 Desktop ──

    def _start_windows(self) -> bool:
        """Create a hidden Win32 desktop."""
        self._desktop_name = f"jarvis_vdi_{int(time.time())}"
        GENERIC_ALL = 0x02000000

        self._hdesktop = user32.CreateDesktopW(
            self._desktop_name, None, None, 0, GENERIC_ALL, None
        )
        if not self._hdesktop:
            self._hdesktop = kernel32.OpenDesktopW(
                self._desktop_name, 0, False, GENERIC_ALL
            )
        if not self._hdesktop:
            logger.error("Failed to create hidden desktop")
            return False

        self._running = True
        logger.info(f"Hidden desktop created: {self._desktop_name}")
        return True

    def launch_on_desktop(self, cmd: list[str], env: dict = None) -> Optional[int]:
        """Launch a process on the hidden desktop. Returns PID."""
        if not IS_WINDOWS or not self._hdesktop:
            # Fallback: launch normally
            proc = subprocess.Popen(cmd, env=env)
            return proc.pid

        # Create process on hidden desktop
        class STARTUPINFOW(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", wintypes.LPBYTE), ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
            ]

        STARTF_USESHOWWINDOW = 0x00000001
        SW_HIDE = 0
        CREATE_NO_WINDOW = 0x08000000

        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(si)
        si.lpDesktop = self._desktop_name
        si.dwFlags = STARTF_USESHOWWINDOW
        si.wShowWindow = SW_HIDE

        pi = PROCESS_INFORMATION()
        cmd_line = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        cmd_buffer = ctypes.create_unicode_buffer(cmd_line, len(cmd_line) + 1)

        success = kernel32.CreateProcessW(
            None, cmd_buffer, None, None, False,
            CREATE_NO_WINDOW, None, None,
            ctypes.byref(si), ctypes.byref(pi)
        )

        if success:
            pid = pi.dwProcessId
            kernel32.CloseHandle(pi.hThread)
            logger.info(f"Launched on hidden desktop: PID {pid}")
            return pid
        else:
            logger.error(f"Failed to launch: {cmd_line[:100]}")
            return None

    def capture_window(self, hwnd: int) -> Optional[bytes]:
        """Capture a specific window using PrintWindow API. Returns JPEG bytes."""
        if not IS_WINDOWS:
            return None

        try:
            from PIL import Image

            # Get window rect
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return None

            # Create device contexts
            hdc_window = user32.GetDC(hwnd)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_window, w, h)
            gdi32.SelectObject(hdc_mem, hbmp)

            # PrintWindow captures the window even if it's on a hidden desktop
            result = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
            if not result:
                # Fallback to BitBlt
                gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_window, 0, 0, SRCCOPY)

            # Extract bitmap data
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0
            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), 0)

            # Cleanup
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_window)

            # Convert to JPEG
            img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
            img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=70)
            return out.getvalue()

        except Exception as e:
            logger.debug(f"Capture failed for hwnd {hwnd}: {e}")
            return None

    def capture_desktop(self) -> Optional[bytes]:
        """Capture the entire desktop. Uses GDI for Windows."""
        if IS_WINDOWS:
            return self._capture_desktop_gdi()
        elif IS_LINUX:
            return self._capture_desktop_x11()
        return None

    def _capture_desktop_gdi(self) -> Optional[bytes]:
        """Capture using GDI (works for visible desktop)."""
        try:
            from PIL import Image
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            hscreen = user32.GetDC(0)
            hmemdc = gdi32.CreateCompatibleDC(hscreen)
            hbmp = gdi32.CreateCompatibleBitmap(hscreen, w, h)
            gdi32.SelectObject(hmemdc, hbmp)
            gdi32.BitBlt(hmemdc, 0, 0, w, h, hscreen, 0, 0, SRCCOPY)
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0
            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(hmemdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hmemdc)
            user32.ReleaseDC(0, hscreen)
            img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
            img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=60)
            return out.getvalue()
        except Exception as e:
            logger.error(f"GDI capture failed: {e}")
            return None

    def _capture_desktop_x11(self) -> Optional[bytes]:
        """Capture using X11 (Linux)."""
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png") as f:
                subprocess.run(
                    ["xwd", "-root", "-out", f.name],
                    timeout=5, capture_output=True
                )
                from PIL import Image
                img = Image.open(f.name)
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=60)
                return out.getvalue()
        except Exception as e:
            logger.error(f"X11 capture failed: {e}")
            return None

    def list_windows(self) -> list[dict]:
        """List all visible windows on the desktop."""
        if not IS_WINDOWS:
            return []

        windows = []

        def enum_callback(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "x": rect.left, "y": rect.top,
                        "w": rect.right - rect.left,
                        "h": rect.bottom - rect.top,
                    })
            return True

        WNDENUMPROC(callback = enum_callback)
        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(enum_callback), 0)
        return windows

    def focus_window(self, hwnd: int) -> bool:
        """Bring a window to focus on the hidden desktop."""
        if not IS_WINDOWS:
            return False
        try:
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    # ── Linux: Xvfb Virtual Display ──

    def _start_linux(self) -> bool:
        """Start Xvfb virtual display on DISPLAY=:1 (isolated from :0)."""
        display_num = ":1"
        try:
            self._xvfb_proc = subprocess.Popen(
                ["Xvfb", display_num, "-screen", "0",
                 f"{self.width}x{self.height}x24", "-ac"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(0.5)
            if self._xvfb_proc.poll() is not None:
                raise RuntimeError(f"Xvfb exited with code {self._xvfb_proc.returncode}")
            self._display_num = display_num
            self._running = True
            logger.info(f"Xvfb started on {display_num} (isolated from :0)")
            return True
        except FileNotFoundError:
            logger.error("Xvfb not found. Install with: apt install xvfb")
            return False
        except Exception as e:
            logger.error(f"Xvfb failed: {e}")
            return False

    def get_display_env(self) -> str:
        """Get the DISPLAY environment variable for the virtual display."""
        if IS_WINDOWS:
            return self._desktop_name or "default"
        return getattr(self, "_display_num", os.environ.get("DISPLAY", ":0"))

    def launch_application(self, cmd: list[str], env: dict = None) -> Optional[int]:
        """Launch an application on the isolated VDI display (:1).
        
        The application runs fully isolated from the user's physical display (DISPLAY=:0).
        Returns PID of the launched process.
        """
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        if IS_LINUX:
            full_env["DISPLAY"] = getattr(self, "_display_num", ":1")
        elif IS_WINDOWS:
            full_env["JARVIS_HEADLESS"] = "1"
        else:
            full_env["JARVIS_HEADLESS"] = "1"

        try:
            proc = subprocess.Popen(cmd, env=full_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Launched '{cmd[0]}' on VDI (PID {proc.pid})")
            return proc.pid
        except Exception as e:
            logger.error(f"Failed to launch on VDI: {e}")
            return None


class FrameCapturer:
    """Captures frames from the VDI at configurable FPS (supports up to 60fps for live backstage canvas)."""

    def __init__(self, vdi: VDIManager, fps: int = 10):
        self.vdi = vdi
        self.fps = fps
        self._running = False
        self._thread = None
        self._frame_callback = None
        self._latest_frame = None
        self._lock = threading.Lock()

    def start(self, on_frame=None, fps: int = None):
        """Start capturing frames. FPS can be updated on the fly."""
        if fps:
            self.fps = fps
        self._frame_callback = on_frame
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop():
        self._running = False

    def set_fps(self, fps: int):
        """Update capture FPS (for 60fps live preview mode)."""
        self.fps = fps

    def get_latest_frame(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_frame

    def _capture_loop(self):
        interval = 1.0 / self.fps
        while self._running:
            start = time.time()
            frame = self.vdi.capture_desktop()
            if frame:
                with self._lock:
                    self._latest_frame = frame
                if self._frame_callback:
                    self._frame_callback(frame)
            elapsed = time.time() - start
            time.sleep(max(0, interval - elapsed))
