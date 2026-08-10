"""
True Windows Desktop Isolation via Win32 API.

Creates REAL Windows desktop objects using CreateDesktopW/SwitchDesktop.
These are completely isolated — processes on one desktop are INVISIBLE
from other desktops. This is NOT the same as Win+Ctrl+D virtual desktops.

Usage:
    td = TrueDesktop()
    td.create("ai_work")
    td.switch_to("ai_work")
    td.launch_on("ai_work", "chrome.exe", ["https://google.com"])
    td.switch_to("default")  # user's desktop never disturbed
"""

import ctypes
import ctypes.wintypes as wintypes
import subprocess
import time
import os
import sys
import threading
import json
from typing import Optional
from dataclasses import dataclass, field


# ── Win32 Structures (not in ctypes.wintypes) ──────────────────────
class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", wintypes.LPBYTE),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]

# ── Win32 API constants ────────────────────────────────────────────
DESKTOP_READOBJECTS = 0x0001
DESKTOP_CREATEWINDOW = 0x0002
DESKTOP_CREATEMENU = 0x0004
DESKTOP_HOOKCONTROL = 0x0008
DESKTOP_JOURNALRECORD = 0x0010
DESKTOP_JOURNALPLAYBACK = 0x0020
DESKTOP_ENUMERATE = 0x0040
DESKTOP_WRITEOBJECTS = 0x0080
DESKTOP_SWITCHDESKTOP = 0x0100

MAXIMUM_ALLOWED = 0x02000000

STARTF_USESHOWWINDOW = 0x00000001
STARTF_USESTDHANDLES = 0x00000100
SW_SHOW = 5
SW_SHOWNORMAL = 1
CREATE_NEW_CONSOLE = 0x00000010
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
INFINITE = 0xFFFFFFFF

GENERIC_ALL = 0x10000000

# ── Win32 API declarations ─────────────────────────────────────────

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32

# Desktop APIs
user32.CreateDesktopW.restype = wintypes.HANDLE
user32.CreateDesktopW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID
]

user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
]

user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

user32.SwitchDesktop.restype = wintypes.BOOL
user32.SwitchDesktop.argtypes = [wintypes.HANDLE]

user32.CloseDesktop.restype = wintypes.BOOL
user32.CloseDesktop.argtypes = [wintypes.HANDLE]

user32.GetProcessWindowStation.restype = wintypes.HWINSTA

# Process APIs
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
    wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
    wintypes.LPVOID, wintypes.LPVOID
]

kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]


@dataclass
class DesktopInfo:
    name: str
    handle: wintypes.HANDLE = None
    is_active: bool = False


@dataclass
class ProcessInfo:
    name: str
    pid: int
    handle: wintypes.HANDLE = None
    desktop_name: str = ""


class TrueDesktop:
    """Real Windows desktop isolation via CreateDesktopW API."""

    def __init__(self):
        self._desktops: dict[str, wintypes.HANDLE] = {}
        self._processes: dict[str, ProcessInfo] = {}
        self._current_desktop: str = "default"
        self._lock = threading.Lock()
        self._hwinsta = user32.GetProcessWindowStation()

        # Open the default (user's) desktop
        default = user32.OpenInputDesktop(0, False, GENERIC_ALL)
        if default:
            self._desktops["default"] = default
        else:
            # Fallback: create it
            self._desktops["default"] = self._create_desktop_handle("Default")

        print(f"[TRUE_DESKTOP] Initialized. Default desktop handle: {self._desktops['default']}")

    def _create_desktop_handle(self, name: str) -> wintypes.HANDLE:
        """Create a real Windows desktop object."""
        handle = user32.CreateDesktopW(
            name,           # desktop name
            None,           # device (unused)
            None,           # devmode (unused)
            0,              # flags
            GENERIC_ALL,    # desired access
            None            # security attributes
        )
        if not handle:
            error = kernel32.GetLastError()
            # Try opening if it already exists
            handle = user32.OpenDesktopW(name, 0, False, GENERIC_ALL)
            if not handle:
                raise RuntimeError(f"Failed to create/open desktop '{name}' (error {error})")
        return handle

    def create(self, name: str) -> bool:
        """Create a new isolated desktop."""
        with self._lock:
            if name in self._desktops:
                return True  # Already exists
            try:
                handle = self._create_desktop_handle(name)
                self._desktops[name] = handle
                print(f"[TRUE_DESKTOP] Created desktop '{name}' (handle: {handle})")
                return True
            except Exception as e:
                print(f"[TRUE_DESKTOP] Failed to create '{name}': {e}")
                return False

    def switch_to(self, name: str) -> bool:
        """Switch to a desktop. The user's display changes to show that desktop."""
        with self._lock:
            handle = self._desktops.get(name)
            if not handle:
                print(f"[TRUE_DESKTOP] Desktop '{name}' not found")
                return False

            result = user32.SwitchDesktop(handle)
            if result:
                self._current_desktop = name
                print(f"[TRUE_DESKTOP] Switched to '{name}'")
                return True
            else:
                error = kernel32.GetLastError()
                print(f"[TRUE_DESKTOP] SwitchDesktop failed for '{name}' (error {error})")
                return False

    def launch_on(self, desktop_name: str, exe_path: str, args: list = None,
                  wait: bool = False, window_style: int = SW_SHOW) -> Optional[ProcessInfo]:
        """Launch a process on a specific desktop WITHOUT switching.

        GUI apps (notepad, Chrome) will exit immediately on an inactive desktop
        — this is a Windows limitation. Use console apps (cmd, python, powershell)
        or headless tools for background automation.
        """
        handle = self._desktops.get(desktop_name)
        if not handle:
            print(f"[TRUE_DESKTOP] Desktop '{desktop_name}' not found")
            return None

        # Build command line — exe is quoted, args are NOT (Windows convention)
        cmd_line = f'"{exe_path}"'
        if args:
            cmd_line += " " + " ".join(args)

        creation_flags = CREATE_NEW_CONSOLE

        # STARTUPINFO with desktop set to our isolated desktop
        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(si)
        si.lpDesktop = desktop_name
        si.dwFlags = STARTF_USESHOWWINDOW
        si.wShowWindow = window_style

        pi = PROCESS_INFORMATION()

        # Mutable buffer for command line (Win32 requires writable buffer)
        cmd_buffer = ctypes.create_unicode_buffer(cmd_line, len(cmd_line) + 1)

        success = kernel32.CreateProcessW(
            None,           # application name (None = use command line)
            cmd_buffer,     # command line
            None,           # process security attributes
            None,           # thread security attributes
            False,          # inherit handles
            creation_flags, # creation flags
            None,           # environment (inherit)
            None,           # current directory (inherit)
            ctypes.byref(si),  # startup info
            ctypes.byref(pi)   # process info
        )

        if not success:
            error = kernel32.GetLastError()
            print(f"[TRUE_DESKTOP] CreateProcessW failed for '{exe_path}' (error {error})")
            return None

        proc_info = ProcessInfo(
            name=exe_path.split("\\")[-1] if "\\" in exe_path else exe_path,
            pid=pi.dwProcessId,
            handle=pi.hProcess,
            desktop_name=desktop_name
        )

        with self._lock:
            self._processes[str(proc_info.pid)] = proc_info

        print(f"[TRUE_DESKTOP] Launched '{proc_info.name}' (PID {proc_info.pid}) on desktop '{desktop_name}'")

        if wait:
            kernel32.WaitForSingleObject(pi.hProcess, INFINITE)

        # Don't close the thread handle — we might need it
        kernel32.CloseHandle(pi.hThread)

        return proc_info

    def terminate(self, process_id: str) -> bool:
        """Terminate a process by its PID string key."""
        with self._lock:
            proc = self._processes.get(process_id)
            if not proc or not proc.handle:
                return False

            result = kernel32.TerminateProcess(proc.handle, 1)
            kernel32.CloseHandle(proc.handle)
            del self._processes[process_id]
            return bool(result)

    def list_desktops(self) -> list[str]:
        """List all desktop names."""
        with self._lock:
            return list(self._desktops.keys())

    def list_processes(self) -> list[dict]:
        """List all tracked processes."""
        with self._lock:
            return [
                {"name": p.name, "pid": p.pid, "desktop": p.desktop_name}
                for p in self._processes.values()
            ]

    def close(self, name: str) -> bool:
        """Close a desktop — terminates tracked processes on it, then releases the handle."""
        import os, signal

        with self._lock:
            if name == "default":
                return False

            to_kill = [p for p in self._processes.values() if p.desktop_name == name]
            for proc in to_kill:
                # Try handle-based kill first
                killed = False
                if proc.handle:
                    try:
                        kernel32.TerminateProcess(proc.handle, 1)
                        kernel32.CloseHandle(proc.handle)
                        killed = True
                    except Exception:
                        pass
                # Fallback: kill by PID
                if not killed and proc.pid:
                    try:
                        os.kill(proc.pid, signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        pass
                self._processes.pop(str(proc.pid), None)

            handle = self._desktops.pop(name, None)
            if handle:
                user32.CloseDesktop(handle)
                print(f"[TRUE_DESKTOP] Closed desktop '{name}'")
                return True
            return False

    def get_current(self) -> str:
        return self._current_desktop

    def capture(self, name: str) -> Optional[bytes]:
        """Capture windows on an isolated desktop WITHOUT switching.

        Uses PrintWindow(PW_RENDERFULLCONTENT) which renders a window's
        content directly into a memory DC — no screen surface, no desktop
        switch. The user's desktop is NEVER touched.
        """
        if name not in self._desktops:
            return None

        import ctypes
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        kernel32 = ctypes.windll.kernel32

        # 64-bit-safe signatures
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
        user32.GetDesktopWindow.restype = wintypes.HWND
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.restype = ctypes.c_int
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.PrintWindow.restype = wintypes.BOOL
        user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.DWORD]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteDC.restype = wintypes.BOOL
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        gdi32.GetDIBits.restype = ctypes.c_int
        gdi32.GetDIBits.argtypes = [
            wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
            ctypes.c_void_p, wintypes.LPVOID, wintypes.UINT,
        ]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        result: dict = {"data": None, "error": None}

        def _worker_thread():
            target = self._desktops.get(name)
            if not target:
                result["error"] = "Desktop not found"
                return

            # Collect PIDs of processes we launched on this desktop
            known_pids = set()
            with self._lock:
                for proc in self._processes.values():
                    if proc.desktop_name == name:
                        known_pids.add(proc.pid)

            if not known_pids:
                result["error"] = "No processes tracked on desktop"
                return

            # Enumerate ALL windows (on the default desktop — no switch needed)
            # then filter by PID to find windows belonging to our processes.
            hwnds = []
            def _enum_cb(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in known_pids:
                        length = user32.GetWindowTextLengthW(hwnd)
                        title = ""
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value
                        hwnds.append((hwnd, title))
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

            if not hwnds:
                result["error"] = "No windows found on desktop"
                return

            # Capture the largest visible window via PrintWindow
            best_hwnd = None
            best_area = 0
            for hwnd, title in hwnds:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                area = (rect.right - rect.left) * (rect.bottom - rect.top)
                if area > best_area:
                    best_area = area
                    best_hwnd = hwnd

            if not best_hwnd:
                result["error"] = "No capturable window"
                return

            rect = wintypes.RECT()
            user32.GetWindowRect(best_hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                result["error"] = "Window has zero size"
                return

            # Screen-compatible DC for CreateCompatibleBitmap
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            user32.ReleaseDC(0, hdc_screen)

            if not hdc_mem or not hbitmap:
                if hdc_mem:
                    gdi32.DeleteDC(hdc_mem)
                if hbitmap:
                    gdi32.DeleteObject(hbitmap)
                result["error"] = "GDI alloc failed"
                return

            gdi32.SelectObject(hdc_mem, hbitmap)

            # PrintWindow renders the window into hdc_mem — no screen surface needed
            user32.PrintWindow(best_hwnd, hdc_mem, 2)  # PW_RENDERFULLCONTENT = 2

            bmp_info = BITMAPINFOHEADER()
            bmp_info.biSize = ctypes.sizeof(bmp_info)
            bmp_info.biWidth = w
            bmp_info.biHeight = -h
            bmp_info.biPlanes = 1
            bmp_info.biBitCount = 32
            bmp_info.biCompression = 0
            bits = (ctypes.c_ubyte * (w * h * 4))()
            gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, ctypes.byref(bits), ctypes.byref(bmp_info), 0)

            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)

            # BGRA -> PIL -> PNG
            try:
                from PIL import Image
                import io
                img = Image.frombytes("RGBA", (w, h), bytes(bits), "raw", "BGRA")
                img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                result["data"] = buf.getvalue()
            except ImportError:
                result["error"] = "PIL not available"

        thread = threading.Thread(target=_worker_thread, daemon=True)
        thread.start()
        thread.join(timeout=8)

        if result["error"]:
            print(f"[TRUE_DESKTOP] Capture of '{name}' failed: {result['error']}")
        return result["data"]

    def capture_desktop_surface(self, name: str) -> Optional[bytes]:
        """Capture the entire framebuffer of an isolated desktop.

        Uses a dedicated thread (no windows) to switch to the target desktop,
        grab the framebuffer via GDI BitBlt, then switch back.
        """
        if name not in self._desktops:
            return None

        result = [None]

        def _worker():
            import ctypes
            import ctypes.wintypes as wintypes

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            user32.GetDC.restype = wintypes.HDC
            user32.GetDC.argtypes = [wintypes.HWND]
            user32.ReleaseDC.restype = ctypes.c_int
            user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
            user32.GetSystemMetrics.restype = ctypes.c_int
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            gdi32.CreateCompatibleDC.restype = wintypes.HDC
            gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
            gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
            gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
            gdi32.SelectObject.restype = wintypes.HGDIOBJ
            gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
            gdi32.BitBlt.restype = wintypes.BOOL
            gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
            gdi32.DeleteObject.restype = wintypes.BOOL
            gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
            gdi32.DeleteDC.restype = wintypes.BOOL
            gdi32.DeleteDC.argtypes = [wintypes.HDC]
            gdi32.GetDIBits.restype = ctypes.c_int
            gdi32.GetDIBits.argtypes = [
                wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                ctypes.c_void_p, wintypes.LPVOID, wintypes.UINT,
            ]

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            target_handle = self._desktops.get(name)
            if not target_handle:
                return

            # Get original desktop so we can switch back
            orig_desktop = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())

            # Switch this thread to the isolated desktop
            if not user32.SetThreadDesktop(target_handle):
                return

            try:
                SM_CXSCREEN = 0
                SM_CYSCREEN = 1
                w = user32.GetSystemMetrics(SM_CXSCREEN)
                h = user32.GetSystemMetrics(SM_CYSCREEN)
                if w <= 0 or h <= 0:
                    return

                hdc_screen = user32.GetDC(0)
                hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
                gdi32.SelectObject(hdc_mem, hbitmap)

                SRCCOPY = 0x00CC0020
                gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY)

                bmp_info = BITMAPINFOHEADER()
                bmp_info.biSize = ctypes.sizeof(bmp_info)
                bmp_info.biWidth = w
                bmp_info.biHeight = -h
                bmp_info.biPlanes = 1
                bmp_info.biBitCount = 32
                bmp_info.biCompression = 0
                bits = (ctypes.c_ubyte * (w * h * 4))()
                gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, ctypes.byref(bits), ctypes.byref(bmp_info), 0)

                gdi32.DeleteObject(hbitmap)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)

                from PIL import Image
                import io
                img = Image.frombytes("RGBA", (w, h), bytes(bits), "raw", "BGRA")
                img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=70, optimize=True)
                result[0] = buf.getvalue()

            except Exception as e:
                print(f"[TRUE_DESKTOP] Surface capture error: {e}")
            finally:
                # Switch back to original desktop
                user32.SetThreadDesktop(orig_desktop)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=8)

        return result[0]

    def _set_thread_desktop(self, handle) -> bool:
        """Switch the current thread to a given desktop handle."""
        import ctypes
        import ctypes.wintypes as wintypes
        user32 = ctypes.windll.user32
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
        return bool(user32.SetThreadDesktop(handle))

    def get_status(self) -> dict:
        with self._lock:
            return {
                "current_desktop": self._current_desktop,
                "desktops": list(self._desktops.keys()),
                "processes": self.list_processes(),
                "desktop_count": len(self._desktops),
            }


# ── Singleton ──────────────────────────────────────────────────────

_instance = None
_instance_lock = threading.Lock()

def get_true_desktop() -> TrueDesktop:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TrueDesktop()
    return _instance
