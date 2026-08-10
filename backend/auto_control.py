"""
3-Tier Autonomous Control Engine.
Tier 1: Native Python APIs (python-pptx, openpyxl, etc.) — instant, no GUI needed
Tier 2: CLI/Scripting (subprocess) — sub-100ms
Tier 3: OS Accessibility + Keyboard — sub-50ms fallback
Virtual desktop isolation for parallel work without disturbing user.
"""

import subprocess
import time
import os
import sys
import json
import tempfile
from typing import Optional

_pg = None

def _get_pg():
    global _pg
    if _pg is None:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.015
        _pg = pyautogui
    return _pg

def _ps(cmd, timeout=15.0):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

# Virtual Desktop Management (Win10/11)

def get_desktop_count():
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        return len(engine.tier3._get_td().list_desktops())
    except Exception:
        return 1

def desktop_create():
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        td = engine.tier3._get_td()
        name = f"desktop_{int(time.time())}"
        td.create(name)
        return f"Created isolated desktop: {name}"
    except Exception as e:
        return f"Failed to create desktop: {e}"

def desktop_switch(index=0):
    """Switch the visible display to an isolated desktop (or back home with 0)."""
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        td = engine.tier3._get_td()
        if index == 0:
            return desktop_go_home()
        # Find the Nth isolated desktop (skipping "default")
        names = [n for n in td.list_desktops() if n != "default"]
        if not names:
            return "No isolated desktops. Create one first."
        if index > len(names):
            return f"Only {len(names)} isolated desktop(s) exist"
        name = names[index - 1]
        if td.switch_to(name):
            return f"Switched to isolated desktop: {name}"
        return f"Failed to switch to {name}"
    except Exception as e:
        return f"Switch failed: {e}"

def desktop_go_home():
    """Return the display to the user's primary desktop."""
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        td = engine.tier3._get_td()
        if td.switch_to("default"):
            return "Returned to primary desktop"
        return "Already on primary desktop"
    except Exception as e:
        return f"Failed: {e}"

def desktop_close():
    """Close the currently active isolated desktop (never the user's)."""
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        td = engine.tier3._get_td()
        current = td.get_current()
        if current == "default":
            return "Cannot close the primary desktop"
        if td.close(current):
            td.switch_to("default")
            return f"Closed isolated desktop: {current}"
        return f"Failed to close {current}"
    except Exception as e:
        return f"Close failed: {e}"

def desktop_open_app_on_current(app_name):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.open_app(app_name)
        return result.message
    except Exception as e:
        return f"Failed: {e}"

def desktop_open_browser_on_current(url, browser="chrome", profile_dir=None):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.browse(url, browser)
        return result.message
    except Exception as e:
        return f"Failed: {e}"

def desktop_isolate_and_work(work_fn, *args, **kwargs):
    try:
        result = work_fn(*args, **kwargs)
    except Exception as e:
        result = f"Error: {e}"
    return result

# Isolated Task Execution (uses VirtualDesktopEngine)

def desktop_browse_isolated(url, browser="chrome", actions=None):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.browse(url, browser)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_document_isolated(title, content="", save_path=""):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.create_document(title, content, save_path)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_spreadsheet_isolated(title, headers=None, rows=None, save_path=""):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.create_spreadsheet(title, headers, rows, save_path)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_presentation_isolated(title, slides=None, save_path=""):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.create_presentation(title, slides, save_path)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_email_isolated(to, subject, body):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.send_email(to, subject, body)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_research_isolated(query):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.research(query)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_custom_task_isolated(steps):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        return f"Custom task completed ({len(steps)} steps)"
    except Exception as e:
        return f"Error: {e}"

def desktop_open_app_isolated(app_name, args=None):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.open_app(app_name, args)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def desktop_silent_work(task_type="browse", duration=60, url="", **kwargs):
    if task_type == "browse" and url:
        return desktop_browse_isolated(url)
    elif task_type == "document":
        return desktop_document_isolated(kwargs.get("title", "Document"), kwargs.get("content", ""))
    elif task_type == "spreadsheet":
        return desktop_spreadsheet_isolated(kwargs.get("title", "Spreadsheet"))
    elif task_type == "email":
        return desktop_email_isolated(kwargs.get("to", ""), kwargs.get("subject", ""), kwargs.get("body", ""))
    elif task_type == "research":
        return desktop_research_isolated(kwargs.get("query", ""))
    return f"Unknown task type: {task_type}"

# Mouse Control

def mouse_goto(x, y):
    pg = _get_pg(); pg.moveTo(x, y, duration=0.08)

def mouse_click(x=None, y=None, button="left"):
    pg = _get_pg()
    if x is not None: pg.click(x, y, button=button)
    else: pg.click(button=button)

def mouse_double(x=None, y=None):
    pg = _get_pg()
    if x is not None: pg.doubleClick(x, y)
    else: pg.doubleClick()

def mouse_right(x=None, y=None):
    mouse_click(x, y, button="right")

def mouse_scroll(amount, x=None, y=None):
    pg = _get_pg()
    if x is not None: pg.scroll(amount, x, y)
    else: pg.scroll(amount)

def mouse_drag(x1, y1, x2, y2, duration=0.3):
    pg = _get_pg(); pg.moveTo(x1, y1); pg.drag(x2 - x1, y2 - y1, duration=duration)

# Keyboard Control

def key_press(*keys):
    pg = _get_pg()
    for k in keys: pg.press(k)

def key_combo(*keys):
    pg = _get_pg(); pg.hotkey(*keys)

def type_text(text, interval=0.02):
    pg = _get_pg()
    if text.isascii():
        pg.typewrite(text, interval=interval)
    else:
        import pyperclip
        pyperclip.copy(text)
        pg.hotkey("ctrl", "v")
        time.sleep(0.05)

def paste_text(text):
    import pyperclip
    pyperclip.copy(text)
    pg = _get_pg()
    pg.hotkey("ctrl", "v")
    time.sleep(0.05)

def select_all(): key_combo("ctrl", "a")
def copy_text(): key_combo("ctrl", "c")
def cut_text(): key_combo("ctrl", "x")
def undo(): key_combo("ctrl", "z")
def enter(): key_press("enter")
def tab(): key_press("tab")
def escape(): key_press("escape")
def alt_tab(): key_combo("alt", "tab")
def win_key(): key_press("win")

# Window Management

def focus_window(title_substring):
    import win32gui
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if title_substring.lower() in t.lower():
                result.append(hwnd)
    win32gui.EnumWindows(callback, None)
    if result:
        win32gui.SetForegroundWindow(result[0])
        time.sleep(0.3)
        return True
    return False

def get_active_title():
    import win32gui
    return win32gui.GetWindowText(win32gui.GetForegroundWindow())

def get_screen_size():
    pg = _get_pg()
    return pg.size()

# Tier 1: Native Python APIs (instant, no GUI)

def create_powerpoint(title, slides_content, output_path=None):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.create_presentation(title, slides_content, output_path)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def create_word_document(title, content, output_path=None):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.create_document(title, content, output_path)
        return result.message
    except Exception as e:
        return f"Error: {e}"

def create_excel_sheet(title, headers, rows, output_path=None):
    try:
        from virtual_desktop_engine import get_engine
        engine = get_engine()
        result = engine.create_spreadsheet(title, headers, rows, output_path)
        return result.message
    except Exception as e:
        return f"Error: {e}"

# Tier 2: CLI/Scripting (sub-100ms)

def run_cli(command, cwd=None, timeout=30):
    try:
        from execution_vault import vaulted_run, VaultPolicy
        policy = VaultPolicy(timeout=timeout)
        if cwd:
            policy.working_dir = cwd
        vr = vaulted_run(command, timeout=timeout, cwd=cwd)
        if vr.blocked:
            return f"BLOCKED: {vr.block_reason}"
        output = (vr.stdout or "").strip()
        if vr.stderr.strip():
            output += "\nSTDERR: " + vr.stderr.strip()
        return output or "Command executed (no output)"
    except Exception as e:
        return f"Command failed: {e}"

# Tier 3: Accessibility Tree (sub-50ms)

def get_ui_elements(window_title=None):
    try:
        import pywinauto
        from pywinauto import Desktop
        if window_title:
            windows = Desktop(backend="uia").windows(title_re=".*%s.*" % window_title)
            if not windows: return []
            app = windows[0]
        else:
            app = Desktop(backend="uia").focus()
        elements = []
        for child in app.children():
            try:
                elements.append({"name": child.window_text(), "type": child.element_info.control_type, "rect": str(child.rectangle())})
            except Exception: pass
        return elements
    except Exception:
        return []

def click_ui_element(name, window_title=None):
    try:
        import pywinauto
        from pywinauto import Desktop
        if window_title:
            windows = Desktop(backend="uia").windows(title_re=".*%s.*" % window_title)
            if not windows: return f"Window not found: {window_title}"
            app = windows[0]
        else:
            app = Desktop(backend="uia").focus()
        for child in app.children():
            if name.lower() in child.window_text().lower():
                child.click_input()
                return f"Clicked '{name}'"
        return f"Element '{name}' not found"
    except Exception as e:
        return f"Click failed: {e}"

# Form Filling

def fill_form_by_tabbing(fields, start_x=None, start_y=None):
    pg = _get_pg()
    if start_x is not None:
        pg.click(start_x, start_y)
        time.sleep(0.2)
    results = []
    for i, value in enumerate(fields):
        if i > 0: tab(); time.sleep(0.08)
        select_all(); time.sleep(0.03)
        type_text(value)
        results.append(f"Field {i + 1} = '{value}'")
    return "\n".join(results)

def fill_form(fields):
    results = []
    for i, field in enumerate(fields):
        label = field.get("label", "")
        value = field.get("value", "")
        if i > 0: tab(); time.sleep(0.08)
        type_text(value)
        results.append(f"Filled '{label}' = '{value}'")
    return "\n".join(results)

# Autonomous Task Runner

def execute_task(steps):
    results = []
    for i, step in enumerate(steps):
        action = step.get("action", "")
        params = step.get("params", {})
        desc = step.get("desc", f"{action} {params}")
        try:
            if action == "click": mouse_click(params.get("x"), params.get("y"), params.get("button", "left"))
            elif action == "double": mouse_double(params.get("x"), params.get("y"))
            elif action == "right_click": mouse_right(params.get("x"), params.get("y"))
            elif action == "type": type_text(params.get("text", ""))
            elif action == "paste": paste_text(params.get("text", ""))
            elif action == "hotkey": key_combo(*params.get("keys", []))
            elif action == "press": key_press(params.get("key", "enter"))
            elif action == "scroll": mouse_scroll(params.get("amount", -3))
            elif action == "wait": time.sleep(params.get("seconds", 1))
            elif action == "goto": mouse_goto(params.get("x", 0), params.get("y", 0))
            elif action == "focus": focus_window(params.get("title", ""))
            elif action == "select_all": select_all()
            elif action == "enter": enter()
            elif action == "tab": tab()
            elif action == "escape": escape()
            elif action == "alt_tab": alt_tab()
            elif action == "desktop_create": desktop_create()
            elif action == "desktop_switch": desktop_switch(params.get("index", 0))
            elif action == "open_app": desktop_open_app_on_current(params.get("app", ""))
            elif action == "screenshot":
                default_path = os.environ.get(
                    "JARVIS_SCREENSHOT_PATH",
                    os.path.join(tempfile.gettempdir(), "jarvis_task.png"),
                )
                path = params.get("path", default_path)
                pg = _get_pg(); pg.screenshot(path)
                results.append(f"Screenshot: {path}"); continue
            results.append(f"OK: {desc}")
        except Exception as e:
            results.append(f"FAIL: {desc} — {e}")
        time.sleep(params.get("delay", 0.08))
    return "\n".join(results)
