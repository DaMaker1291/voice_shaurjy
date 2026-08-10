"""
Standalone Worker Desktop — Runs tasks on a HIDDEN desktop.
Spawned as a separate process by isolated_worker.py.

CRITICAL: This script NEVER calls SwitchDesktop.
The child process is placed on the hidden desktop via CreateProcessW(lpDesktop=...).
The parent process (JARVIS server) stays on the user's default desktop.
The user's screen NEVER changes.

Usage: python worker_desktop.py <task_file.json>
"""
import ctypes
import ctypes.wintypes as wintypes
import subprocess
import os
import sys
import time
import json
import tempfile


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

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GENERIC_ALL = 0x02000000
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0
CREATE_NEW_CONSOLE = 0x00000010

user32.CreateDesktopW.restype = wintypes.HANDLE
user32.CreateDesktopW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPVOID, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID
]
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
]
user32.CloseDesktop.restype = wintypes.BOOL
user32.CloseDesktop.argtypes = [wintypes.HANDLE]

kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
    wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID,
    wintypes.LPVOID, wintypes.LPVOID
]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.restype = wintypes.BOOL


def find_exe(name):
    name_lower = name.lower().strip()
    known = {
        "notepad": "notepad.exe", "calculator": "calc.exe",
        "word": "winword.exe", "excel": "excel.exe",
        "powerpoint": "powerpnt.exe", "cmd": "cmd.exe",
        "terminal": "wt.exe", "powershell": "pwsh.exe",
        "paint": "mspaint.exe", "explorer": "explorer.exe",
    }
    if name_lower in known:
        return known[name_lower]
    try:
        r = subprocess.run(["where", name_lower], capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            return r.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return None


def launch_on_desktop(desktop_name, exe_path, args=None, hidden=False):
    """Launch process on a specific desktop WITHOUT switching to it."""
    cmd_line = '"' + exe_path + '"'
    if args:
        cmd_line += " " + " ".join('"' + str(a) + '"' for a in args)

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(si)
    si.lpDesktop = desktop_name  # This puts the child on the hidden desktop
    if hidden:
        si.dwFlags = STARTF_USESHOWWINDOW
        si.wShowWindow = SW_HIDE

    pi = PROCESS_INFORMATION()
    cmd_buffer = ctypes.create_unicode_buffer(cmd_line, len(cmd_line) + 1)

    success = kernel32.CreateProcessW(
        None, cmd_buffer, None, None, False,
        CREATE_NEW_CONSOLE, None, None,
        ctypes.byref(si), ctypes.byref(pi)
    )

    if success:
        kernel32.CloseHandle(pi.hThread)
        return pi.dwProcessId, pi.hProcess
    return None, None


def main():
    if len(sys.argv) < 2:
        print("Usage: python worker_desktop.py <task_file.json>")
        return

    task_file = sys.argv[1]
    with open(task_file, "r") as f:
        task = json.load(f)

    task_id = task["task_id"]
    task_type = task.get("type", "python")
    result_dir = os.path.dirname(task_file)
    result_path = os.path.join(result_dir, task_id + ".json")

    def save_result(status, result="", error=""):
        with open(result_path, "w") as f:
            json.dump({"task_id": task_id, "status": status, "result": result, "error": error}, f)

    # Create hidden desktop object (NO SwitchDesktop — user stays on their desktop)
    desktop_name = "jarvis_" + task_id
    hDesktop = user32.CreateDesktopW(desktop_name, None, None, 0, GENERIC_ALL, None)
    if not hDesktop:
        hDesktop = user32.OpenDesktopW(desktop_name, 0, False, GENERIC_ALL)
    if not hDesktop:
        save_result("error", error="Failed to create desktop")
        return

    # NEVER call SwitchDesktop. Child processes go to hidden desktop via lpDesktop.

    try:
        if task_type == "app":
            app_name = task.get("app", "")
            exe = find_exe(app_name)
            if not exe:
                save_result("error", error="App not found: " + app_name)
                return

            pid, handle = launch_on_desktop(desktop_name, exe, task.get("args"), hidden=True)
            if not pid:
                save_result("error", error="Failed to launch " + app_name)
                return

            timeout = task.get("timeout", 60)
            kernel32.WaitForSingleObject(handle, timeout * 1000)
            kernel32.CloseHandle(handle)
            save_result("done", result=app_name + " completed on hidden desktop")

        elif task_type == "python":
            code = task.get("command", "")
            script = os.path.join(tempfile.gettempdir(), "jarvis_iso_" + str(int(time.time())) + ".py")
            with open(script, "w", encoding="utf-8") as f:
                f.write(code)

            pid, handle = launch_on_desktop(desktop_name, sys.executable, [script], hidden=True)
            if not pid:
                save_result("error", error="Failed to run Python")
                return

            kernel32.WaitForSingleObject(handle, 120000)
            kernel32.CloseHandle(handle)
            try:
                os.remove(script)
            except Exception:
                pass
            save_result("done", result="Python script completed on hidden desktop")

        elif task_type == "blender":
            blender = None
            for p in [r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
                       r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"]:
                if os.path.exists(p):
                    blender = p
                    break
            if not blender:
                save_result("error", error="Blender not found")
                return

            code = task.get("command", "")
            script = os.path.join(tempfile.gettempdir(), "jarvis_blender_" + str(int(time.time())) + ".py")
            with open(script, "w", encoding="utf-8") as f:
                f.write(code)

            pid, handle = launch_on_desktop(desktop_name, blender, ["--background", "--python", script], hidden=True)
            if not pid:
                save_result("error", error="Failed to launch Blender")
                return

            kernel32.WaitForSingleObject(handle, 300000)
            kernel32.CloseHandle(handle)
            try:
                os.remove(script)
            except Exception:
                pass
            save_result("done", result="Blender completed on hidden desktop")

        else:
            save_result("error", error="Unknown task type: " + task_type)

    except Exception as e:
        save_result("error", error=str(e))

    # Cleanup — close the hidden desktop (NO SwitchDesktop ever)
    user32.CloseDesktop(hDesktop)


if __name__ == "__main__":
    main()
