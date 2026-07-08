#!/usr/bin/env python3
"""
System Controller for JARVIS
Controls keyboard, mouse, and apps on macOS via Quartz events + AppleScript.
Runs in background — no headless browser needed for desktop automation.
"""
import subprocess
import json
import time
import os
import sys
import threading
import struct
import math

# macOS Quartz imports
try:
    import Quartz
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        CGEventCreateMouseEvent,
        CGEventCreateScrollWheelEvent,
        kCGEventFlagMaskCommand,
        kCGEventFlagMaskShift,
        kCGEventFlagMaskControl,
        kCGEventFlagMaskAlternate,
        kCGHIDEventTap,
        kCGMouseButtonLeft,
        kCGMouseButtonRight,
        kCGMouseButtonCenter,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventLeftMouseDragged,
        kCGEventRightMouseDown,
        kCGEventRightMouseUp,
        kCGEventScrollWheel,
        kCGScrollEventUnitLine,
        kCGEventMouseMoved,
    )
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

# macOS Keycode mapping
KEYCODES = {
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4,
    "i": 34, "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31,
    "p": 35, "q": 12, "r": 15, "s": 1, "t": 17, "u": 32, "v": 9,
    "w": 13, "x": 7, "y": 16, "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22,
    "7": 26, "8": 28, "9": 25,
    "enter": 36, "return": 36, "tab": 48, "space": 49, "escape": 53, "esc": 53,
    "backspace": 51, "delete": 51,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "-": 27, "=": 24, "[": 33, "]": 30, "\\": 42, ";": 41,
    "'": 39, ",": 43, ".": 47, "/": 44, "`": 50,
}

MODIFIER_FLAGS = {
    "cmd": kCGEventFlagMaskCommand,
    "command": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl,
    "control": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate,
    "option": kCGEventFlagMaskAlternate,
    "opt": kCGEventFlagMaskAlternate,
}


class SystemController:
    """
    Control macOS via Quartz events:
    - Type text, press keys, hotkeys
    - Move mouse, click, scroll
    - Launch/control apps via AppleScript
    """

    def __init__(self):
        self._check_accessibility()

    def _check_accessibility(self):
        """Check if we have accessibility permissions."""
        if not QUARTZ_AVAILABLE:
            print("[SystemCtrl] Quartz not available — install pyobjc-framework-Quartz")
            return

        # Test if we can post events
        try:
            event = CGEventCreateKeyboardEvent(None, 0, False)
            if not event:
                print("[SystemCtrl] WARNING: Accessibility permissions needed")
                print("[SystemCtrl] Go to: System Settings → Privacy & Security → Accessibility")
                print("[SystemCtrl] Add Terminal/Python to allowed apps")
        except:
            print("[SystemCtrl] Could not verify accessibility — may need permissions")

    # ── Keyboard ──────────────────────────────────────────────────────

    def type_text(self, text: str, delay: float = 0.02) -> dict:
        """Type a string character by character."""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}

        for char in text:
            if char.isupper():
                # Shift + lowercase
                self._press_key(char.lower(), shift=True)
            elif char in KEYCODES:
                self._press_key(char)
            else:
                # Use CGEventKeyboardSetUnicodeString for special chars
                self._type_char_unicode(char)
            time.sleep(delay)
        return {"status": "typed", "length": len(text)}

    def _press_key(self, key: str, shift=False, cmd=False, ctrl=False, alt=False):
        """Press and release a single key."""
        keycode = KEYCODES.get(key.lower())
        if keycode is None:
            return

        flags = 0
        if shift: flags |= kCGEventFlagMaskShift
        if cmd: flags |= kCGEventFlagMaskCommand
        if ctrl: flags |= kCGEventFlagMaskControl
        if alt: flags |= kCGEventFlagMaskAlternate

        event_down = CGEventCreateKeyboardEvent(None, keycode, True)
        event_up = CGEventCreateKeyboardEvent(None, keycode, False)

        if flags:
            CGEventSetFlags(event_down, flags)
            CGEventSetFlags(event_up, flags)

        CGEventPost(kCGHIDEventTap, event_down)
        time.sleep(0.005)
        CGEventPost(kCGHIDEventTap, event_up)

    def _type_char_unicode(self, char: str):
        """Type a character using Unicode input."""
        try:
            event = CGEventCreateKeyboardEvent(None, 0, True)
            CGEventKeyboardSetUnicodeString(event, len(char), char)
            CGEventPost(kCGHIDEventTap, event)
            time.sleep(0.005)
            event_up = CGEventCreateKeyboardEvent(None, 0, False)
            CGEventKeyboardSetUnicodeString(event_up, len(char), char)
            CGEventPost(kCGHIDEventTap, event_up)
        except:
            pass

    def press_key(self, key: str) -> dict:
        """Press a single key (not a character)."""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}
        self._press_key(key)
        return {"status": "pressed", "key": key}

    def hotkey(self, *keys: str) -> dict:
        """Press a hotkey combo. Example: hotkey("cmd", "space")"""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}

        flags = 0
        regular_key = None

        for k in keys:
            if k.lower() in MODIFIER_FLAGS:
                flags |= MODIFIER_FLAGS[k.lower()]
            else:
                regular_key = k.lower()

        if regular_key is None:
            return {"error": "No regular key specified"}

        keycode = KEYCODES.get(regular_key)
        if keycode is None:
            return {"error": f"Unknown key: {regular_key}"}

        event_down = CGEventCreateKeyboardEvent(None, keycode, True)
        event_up = CGEventCreateKeyboardEvent(None, keycode, False)

        if flags:
            CGEventSetFlags(event_down, flags)
            CGEventSetFlags(event_up, flags)

        CGEventPost(kCGHIDEventTap, event_down)
        time.sleep(0.005)
        CGEventPost(kCGHIDEventTap, event_up)
        return {"status": "hotkey", "keys": list(keys)}

    def type_string(self, text: str) -> dict:
        """Type a string using AppleScript (more reliable for long text)."""
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        return self._run_applescript(script)

    # ── Mouse ─────────────────────────────────────────────────────────

    def mouse_move(self, x: int, y: int) -> dict:
        """Move mouse to absolute position."""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}

        event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, y), 0)
        CGEventPost(kCGHIDEventTap, event)
        return {"status": "moved", "x": x, "y": y}

    def mouse_click(self, x: int, y: int, button: str = "left") -> dict:
        """Click at position."""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}

        btn = {"left": kCGMouseButtonLeft, "right": kCGMouseButtonRight, "center": kCGMouseButtonCenter}.get(button, kCGMouseButtonLeft)
        down_event = {"left": kCGEventLeftMouseDown, "right": kCGEventRightMouseDown}.get(button, kCGEventLeftMouseDown)
        up_event = {"left": kCGEventLeftMouseUp, "right": kCGEventRightMouseUp}.get(button, kCGEventLeftMouseUp)

        event_down = CGEventCreateMouseEvent(None, down_event, (x, y), btn)
        event_up = CGEventCreateMouseEvent(None, up_event, (x, y), btn)

        CGEventPost(kCGHIDEventTap, event_down)
        time.sleep(0.01)
        CGEventPost(kCGHIDEventTap, event_up)
        return {"status": "clicked", "x": x, "y": y, "button": button}

    def mouse_double_click(self, x: int, y: int) -> dict:
        """Double-click at position."""
        self.mouse_click(x, y)
        time.sleep(0.05)
        self.mouse_click(x, y)
        return {"status": "double_clicked", "x": x, "y": y}

    def mouse_scroll(self, x: int, y: int, clicks: int) -> dict:
        """Scroll at position. Positive = up, negative = down."""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}

        event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, -clicks)
        CGEventPost(kCGHIDEventTap, event)
        return {"status": "scrolled", "clicks": clicks}

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> dict:
        """Drag from (x1,y1) to (x2,y2)."""
        if not QUARTZ_AVAILABLE:
            return {"error": "Quartz not available"}

        # Mouse down at start
        event_down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, (x1, y1), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, event_down)

        # Smooth drag
        steps = 20
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)
            event_move = CGEventCreateMouseEvent(None, kCGEventLeftMouseDragged, (cx, cy), kCGMouseButtonLeft)
            CGEventPost(kCGHIDEventTap, event_move)
            time.sleep(0.01)

        # Mouse up at end
        event_up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, (x2, y2), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, event_up)
        return {"status": "dragged", "from": [x1, y1], "to": [x2, y2]}

    # ── App Control (AppleScript) ─────────────────────────────────────

    def launch_app(self, app_name: str) -> dict:
        """Launch an application."""
        escaped = app_name.replace('"', '\\"')
        script = f'tell application "{escaped}" to activate'
        result = self._run_applescript(script)
        result["app"] = app_name
        return result

    def quit_app(self, app_name: str) -> dict:
        """Quit an application."""
        escaped = app_name.replace('"', '\\"')
        script = f'tell application "{escaped}" to quit'
        return self._run_applescript(script)

    def get_frontmost_app(self) -> dict:
        """Get the frontmost application."""
        script = 'tell application "System Events" to get name of first application process whose frontmost is true'
        result = self._run_applescript(script)
        return result

    def get_running_apps(self) -> dict:
        """Get list of running applications."""
        script = 'tell application "System Events" to get name of every application process'
        result = self._run_applescript(script)
        return result

    def click_at_app(self, app_name: str, x: int, y: int) -> dict:
        """Click inside a specific app window."""
        # First activate the app
        self.launch_app(app_name)
        time.sleep(0.5)
        # Then click
        return self.mouse_click(x, y)

    def get_window_position(self, app_name: str) -> dict:
        """Get app window position and size."""
        escaped = app_name.replace('"', '\\"')
        script = f'''
        tell application "System Events"
            tell process "{escaped}"
                set pos to position of window 1
                set siz to size of window 1
                return {{item 1 of pos, item 2 of pos, item 1 of siz, item 2 of siz}}
            end tell
        end tell
        '''
        result = self._run_applescript(script)
        return result

    def get_screen_size(self) -> dict:
        """Get screen dimensions."""
        try:
            import Quartz
            main_display = Quartz.CGMainDisplayBounds()
            return {"width": int(main_display.size.width), "height": int(main_display.size.height)}
        except:
            script = 'tell application "Finder" to get bounds of window of desktop'
            return self._run_applescript(script)

    # ── Clipboard ─────────────────────────────────────────────────────

    def get_clipboard(self) -> dict:
        """Get clipboard contents."""
        script = 'the clipboard as record'
        result = self._run_applescript(script)
        # Simpler approach
        try:
            output = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=5
            )
            return {"content": output.stdout}
        except:
            return {"error": "Could not read clipboard"}

    def set_clipboard(self, text: str) -> dict:
        """Set clipboard contents."""
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-8"))
            return {"status": "clipboard_set", "length": len(text)}
        except Exception as e:
            return {"error": str(e)}

    def copy_paste(self, text: str) -> dict:
        """Copy text to clipboard then paste it."""
        self.set_clipboard(text)
        time.sleep(0.1)
        return self.hotkey("cmd", "v")

    # ── Utilities ─────────────────────────────────────────────────────

    def _run_applescript(self, script: str) -> dict:
        """Run an AppleScript command."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return {"error": result.stderr.strip()}
            return {"output": output} if output else {"status": "ok"}
        except subprocess.TimeoutExpired:
            return {"error": "AppleScript timed out"}
        except Exception as e:
            return {"error": str(e)}

    def screenshot_region(self, x: int, y: int, w: int, h: int, path: str = None) -> dict:
        """Take a screenshot of a screen region."""
        if path is None:
            path = f"/tmp/jarvis_screenshot_{int(time.time())}.png"
        try:
            script = f'screencapture -R{x},{y},{w},{h} "{path}"'
            subprocess.run(script, shell=True, timeout=10)
            return {"status": "screenshot", "path": path, "region": {"x": x, "y": y, "w": w, "h": h}}
        except Exception as e:
            return {"error": str(e)}

    def get_mouse_position(self) -> dict:
        """Get current mouse position."""
        try:
            import Quartz
            point = Quartz.NSEvent.mouseLocation()
            main_display = Quartz.CGMainDisplayBounds()
            return {"x": int(point.x), "y": int(main_display.size.height - point.y)}
        except:
            return {"error": "Could not get mouse position"}


# Singleton
_controller = None

def get_controller() -> SystemController:
    global _controller
    if _controller is None:
        _controller = SystemController()
    return _controller
