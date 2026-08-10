"""
Visible Windows Virtual Desktop bridge (pyvda / IVirtualDesktopManagerInternal).

Unlike the Win32 CreateDesktopW desktops in true_desktop.py (which are INVISIBLE
to the user), this creates REAL Windows virtual desktops — the same ones you
get with Win+Ctrl+D. They appear in Task View and can be switched to normally.

API:
    ensure_desktop(number)  -> guarantees a desktop with that number exists
    switch_to(number)       -> make that desktop the visible/current one
    current_number()        -> number of the currently visible desktop
    desktop_count()         -> how many virtual desktops exist
    list_desktops()         -> [(number, is_current, name), ...]
"""
import os
import sys

try:
    from pyvda import VirtualDesktop, get_virtual_desktops
except ImportError as e:
    raise RuntimeError(
        "pyvda not installed. Run: pip install pyvda"
    ) from e


def desktop_count() -> int:
    return len(get_virtual_desktops())


def list_desktops():
    out = []
    cur = VirtualDesktop.current().number if get_virtual_desktops() else None
    for d in get_virtual_desktops():
        try:
            name = d.name
        except Exception:
            name = ""
        out.append({"number": d.number, "is_current": d.number == cur, "name": name})
    return out


def current_number() -> int:
    try:
        return VirtualDesktop.current().number
    except Exception:
        return 1


def ensure_desktop(number: int) -> bool:
    """Make sure a desktop with the given number exists. Returns True if created."""
    existing = [d.number for d in get_virtual_desktops()]
    if number in existing:
        return False
    # Create until we reach the requested number
    while number not in [d.number for d in get_virtual_desktops()]:
        VirtualDesktop.create()
    return True


def switch_to(number: int) -> bool:
    existing = [d.number for d in get_virtual_desktops()]
    if number not in existing:
        ensure_desktop(number)
    VirtualDesktop(number).go()
    return current_number() == number


def switch_back(number: int = 1) -> bool:
    try:
        VirtualDesktop(number).go()
        return True
    except Exception:
        return False


def move_hwnd(hwnd: int, number: int) -> bool:
    """Move an existing window to a specific virtual desktop by HWND."""
    try:
        from pyvda import AppView
        existing = [d.number for d in get_virtual_desktops()]
        if number not in existing:
            ensure_desktop(number)
        view = AppView(hwnd)
        view.move(VirtualDesktop(number))
        return True
    except Exception:
        return False


def windows_on(number: int) -> list:
    """Return hwnd+title of visible top-level windows on a given desktop."""
    import win32gui
    existing = [d.number for d in get_virtual_desktops()]
    if number not in existing:
        return []
    target = VirtualDesktop(number)
    out = []

    def _cb(h, _l):
        try:
            from pyvda import AppView
            view = AppView(h)
            if view.is_on_desktop(target) and win32gui.IsWindowVisible(h):
                t = win32gui.GetWindowText(h)
                if t:
                    out.append({"hwnd": h, "title": t})
        except Exception:
            pass

    win32gui.EnumWindows(_cb, None)
    return out


def status() -> dict:
    return {
        "count": desktop_count(),
        "current": current_number(),
        "desktops": list_desktops(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2))
