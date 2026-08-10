"""
JARVIS State Migrator — Hot-swap application windows between displays.

Moves live application windows between:
- DISPLAY=:0 (Host foreground desktop)
- DISPLAY=:99 (WSL VDI background desktop)

For web apps: extracts URL + DOM state, spawns matching tab on target display.
For desktop apps: uses xdotool/wmctrl to re-parent windows across X11 displays.
"""
import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("state_migrator")


@dataclass
class WindowInfo:
    """Info about a window on a display."""
    wid: str
    title: str
    app_name: str
    display: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    is_maximized: bool = False


class StateMigrator:
    """Migrates application state between X11 displays."""

    def __init__(self, host_display: str = ":0", vdi_display: str = ":99"):
        self.host_display = host_display
        self.vdi_display = vdi_display

    # ── Window Enumeration ────────────────────────────────────────────────
    def list_windows(self, display: str = None) -> list[WindowInfo]:
        """List all windows on a display."""
        display = display or self.vdi_display
        windows = []

        try:
            # Get all window IDs in one call
            ids_raw = self._x11_exec(
                display,
                "xdotool search --name '' 2>/dev/null || true",
                timeout=5
            )
            wids = [w.strip() for w in ids_raw.strip().split("\n") if w.strip()]
            if not wids:
                return windows

            # Get all names in one batched call
            wid_list = " ".join(wids[:50])  # cap at 50
            names_raw = self._x11_exec(
                display,
                f"for w in {wid_list}; do xdotool getwindowname $w 2>/dev/null || echo ''; done",
                timeout=10
            )
            names = names_raw.strip().split("\n")

            for i, wid in enumerate(wids[:50]):
                title = names[i].strip() if i < len(names) else ""
                windows.append(WindowInfo(
                    wid=wid, title=title, app_name=self._guess_app(title),
                    display=display
                ))

        except Exception as e:
            logger.warning(f"Failed to list windows on {display}: {e}")

        return windows

    def find_window(self, title_pattern: str, display: str = None) -> Optional[WindowInfo]:
        """Find a window by title pattern."""
        display = display or self.vdi_display
        try:
            wid = self._x11_exec(
                display,
                f"xdotool search --name '{title_pattern}' 2>/dev/null | head -1"
            ).strip()
            if wid:
                title = self._x11_exec(display, f"xdotool getwindowname {wid} 2>/dev/null")
                return WindowInfo(
                    wid=wid, title=title.strip(), app_name=self._guess_app(title),
                    display=display
                )
        except Exception:
            pass
        return None

    # ── Window Transfer ───────────────────────────────────────────────────
    def transfer_to_foreground(self, window_id: str = None, title_pattern: str = None) -> dict:
        """Move a VDI window to host foreground display."""
        if not window_id and title_pattern:
            win = self.find_window(title_pattern, self.vdi_display)
            if not win:
                return {"success": False, "error": f"Window not found: {title_pattern}"}
            window_id = win.wid

        if not window_id:
            return {"success": False, "error": "No window specified"}

        try:
            # Method 1: Try wmctrl to re-parent
            result = self._wmctrl_move(window_id, self.host_display)
            if result.get("success"):
                return result

            # Method 2: Try xdotool approach
            result = self._xdotool_move(window_id, self.host_display)
            if result.get("success"):
                return result

            # Method 3: For web apps, extract URL and open on host
            return {"success": False, "error": "Could not migrate window"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def transfer_to_background(self, window_id: str = None, title_pattern: str = None) -> dict:
        """Move a host window to VDI background display."""
        if not window_id and title_pattern:
            win = self.find_window(title_pattern, self.host_display)
            if not win:
                return {"success": False, "error": f"Window not found: {title_pattern}"}
            window_id = win.wid

        if not window_id:
            return {"success": False, "error": "No window specified"}

        try:
            result = self._wmctrl_move(window_id, self.vdi_display)
            if result.get("success"):
                return result
            return self._xdotool_move(window_id, self.vdi_display)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _wmctrl_move(self, wid: str, target_display: str) -> dict:
        """Move window using wmctrl."""
        try:
            # wmctrl can re-parent windows between displays
            cmd = f"wmctrl -i -r {wid} -t {target_display}"
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return {"success": True, "method": "wmctrl", "wid": wid, "target": target_display}
        except Exception:
            pass
        return {"success": False}

    def _xdotool_move(self, wid: str, target_display: str) -> dict:
        """Move window using xdotool."""
        try:
            # Remove window from current display
            self._x11_exec(self.host_display, f"xdotool windowminimize {wid} 2>/dev/null")
            # Re-show on target display
            self._x11_exec(target_display, f"xdotool windowactivate {wid} 2>/dev/null")
            return {"success": True, "method": "xdotool", "wid": wid, "target": target_display}
        except Exception:
            pass
        return {"success": False}

    # ── Web App State Transfer ────────────────────────────────────────────
    def extract_web_state(self, display: str = None) -> dict:
        """Extract current web app state from browser on display."""
        display = display or self.vdi_display
        try:
            # Get active browser tab info via xdotool
            active_title = self._x11_exec(
                display,
                "xdotool getactivewindow getwindowname 2>/dev/null"
            ).strip()

            # If it looks like a browser tab, extract URL
            if any(browser in active_title.lower() for browser in ["chrome", "firefox", "edge", "http"]):
                # Try to get URL from browser
                url = self._extract_browser_url(display)
                return {
                    "success": True,
                    "title": active_title,
                    "url": url,
                    "app_type": "web",
                }

            return {"success": True, "title": active_title, "app_type": "desktop"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _extract_browser_url(self, display: str) -> str:
        """Extract current URL from browser via xdotool keyboard shortcut."""
        try:
            # Focus browser
            self._x11_exec(display, "xdotool search --name Chrome windowactivate 2>/dev/null || true")
            time.sleep(0.3)

            # Select address bar (Ctrl+L)
            self._x11_exec(display, "xdotool key ctrl+l 2>/dev/null || true")
            time.sleep(0.2)

            # Copy URL
            self._x11_exec(display, "xdotool key ctrl+c 2>/dev/null || true")
            time.sleep(0.1)

            # Get clipboard
            url = self._x11_exec(display, "xclip -selection clipboard -o 2>/dev/null || true")
            return url.strip()

        except Exception:
            return ""

    def open_url_on_display(self, url: str, display: str = None) -> dict:
        """Open URL on specified display."""
        display = display or self.host_display
        try:
            browser_cmd = f"DISPLAY={display} google-chrome-stable '{url}' &"
            self._x11_exec(display, browser_cmd)
            return {"success": True, "url": url, "display": display}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Bulk Transfer ─────────────────────────────────────────────────────
    def transfer_all_to_foreground(self) -> dict:
        """Move all VDI windows to host display."""
        windows = self.list_windows(self.vdi_display)
        results = {}
        for win in windows:
            result = self.transfer_to_foreground(win.wid)
            results[win.title or win.wid] = result
        return {"transferred": len([r for r in results.values() if r.get("success")]), "total": len(windows), "details": results}

    def transfer_all_to_background(self) -> dict:
        """Move all host windows to VDI."""
        windows = self.list_windows(self.host_display)
        results = {}
        for win in windows:
            result = self.transfer_to_background(win.wid)
            results[win.title or win.wid] = result
        return {"transferred": len([r for r in results.values() if r.get("success")]), "total": len(windows), "details": results}

    # ── Helpers ───────────────────────────────────────────────────────────
    def _x11_exec(self, display: str, cmd: str, timeout: int = 5) -> str:
        """Execute command on specific X11 display."""
        try:
            full_cmd = f"DISPLAY={display} {cmd}"
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", full_cmd],
                capture_output=True, text=True, timeout=timeout
            )
            return result.stdout
        except Exception:
            return ""

    def _guess_app(self, title: str) -> str:
        """Guess app name from window title."""
        title_lower = title.lower()
        if any(b in title_lower for b in ["chrome", "firefox", "edge", "browser"]):
            return "browser"
        if "terminal" in title_lower or "bash" in title_lower:
            return "terminal"
        if "thunar" in title_lower or "files" in title_lower:
            return "file_manager"
        if "gimp" in title_lower:
            return "gimp"
        return "unknown"

    def get_status(self) -> dict:
        """Get migration status."""
        vdi_windows = self.list_windows(self.vdi_display)
        # Skip host display — xdotool on :0 via WSL hangs with no X server
        host_apps = []
        host_count = 0
        try:
            check = subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"DISPLAY={self.host_display} xdpyinfo >/dev/null 2>&1 && echo OK || echo FAIL"],
                capture_output=True, text=True, timeout=3
            )
            if "OK" in check.stdout:
                host_windows = self.list_windows(self.host_display)
                host_count = len(host_windows)
                host_apps = [w.app_name for w in host_windows]
        except Exception:
            pass
        return {
            "host_display": self.host_display,
            "vdi_display": self.vdi_display,
            "host_windows": host_count,
            "vdi_windows": len(vdi_windows),
            "host_apps": host_apps,
            "vdi_apps": [w.app_name for w in vdi_windows],
        }


# ── Convenience Functions ──────────────────────────────────────────────────

def quick_transfer(title_pattern: str, to_foreground: bool = True) -> dict:
    """Quick transfer a window by title."""
    migrator = StateMigrator()
    if to_foreground:
        return migrator.transfer_to_foreground(title_pattern=title_pattern)
    else:
        return migrator.transfer_to_background(title_pattern=title_pattern)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[MIGRATE] %(message)s")
    migrator = StateMigrator()
    print("=== State Migrator Status ===")
    status = migrator.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    print("\n=== VDI Windows ===")
    for win in migrator.list_windows():
        print(f"  [{win.wid}] {win.title} ({win.app_name})")
