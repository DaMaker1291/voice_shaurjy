"""
macOS Accessibility API integration module.

Provides programmatic access to the macOS Accessibility hierarchy via
AppleScript/System Events.  All heavy lifting is done through ``osascript``
invocations that talk to AXUIElement through System Events.

Usage::

    from macos_accessibility import accessibility

    app = accessibility.get_frontmost_app()
    tree = accessibility.get_element_tree(pid=app["pid"])
    buttons = accessibility.find_element(pid=app["pid"], role="AXButton")
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_applescript(script: str, *, timeout: float = 15.0) -> str:
    """Execute an AppleScript snippet via ``osascript`` and return stdout.

    Parameters
    ----------
    script:
        Raw AppleScript source text.
    timeout:
        Maximum seconds to wait for the subprocess to finish.

    Returns
    -------
    str
        The stdout produced by the script.

    Raises
    ------
    RuntimeError
        If the subprocess exits with a non-zero return code or times out.
    FileNotFoundError
        If ``osascript`` is not available on the system.
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            "osascript not found – this module requires macOS with Xcode/CLI tools installed."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"AppleScript timed out after {timeout}s")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"osascript exited {result.returncode}: {stderr}")

    return result.stdout


def _safe_json(raw: str) -> Any:
    """Best-effort JSON parse of a string, returning ``None`` on failure."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _element_signature(element: dict) -> str:
    """Return a lightweight string signature for an AX element dict."""
    return json.dumps(
        {
            "role": element.get("role"),
            "title": element.get("title"),
            "position": element.get("position"),
            "value": element.get("value"),
        },
        sort_keys=True,
    )


# ---------------------------------------------------------------------------
# Core AppleScript fragments
# ---------------------------------------------------------------------------

_APPLESSCRIPT_HEADER = """
use framework "Foundation"
use scripting additions

property cocoa : current application's NSAppleScript's alloc()'s init()
"""


def _build_tree_script(pid: int, max_depth: int = 3) -> str:
    """Return a full AppleScript that recursively walks the AXUIElement tree."""
    return f"""
{_APPLESSCRIPT_HEADER}

on buildTree(elem, depth, maxDepth)
    if depth > maxDepth then return missing value

    try
        set role to value of attribute "AXRole" of elem
    on error
        set role to missing value
    end try

    try
        set roleDesc to value of attribute "AXRoleDescription" of elem
    on error
        set roleDesc to missing value
    end try

    try
        set title to value of attribute "AXTitle" of elem
    on error
        set title to missing value
    end try

    try
        set desc to value of attribute "AXDescription" of elem
    on error
        set desc to missing value
    end try

    try
        set val to value of attribute "AXValue" of elem
    on error
        set val to missing value
    end try

    try
        set pos to value of attribute "AXPosition" of elem
    on error
        set pos to missing value
    end try

    try
        set sz to value of attribute "AXSize" of elem
    on error
        set sz to missing value
    end try

    try
        set isEnabled to value of attribute "AXEnabled" of elem
    on error
        set isEnabled to missing value
    end try

    try
        set isFocused to value of attribute "AXFocused" of elem
    on error
        set isFocused to missing value
    end try

    try
        set ident to value of attribute "AXIdentifier" of elem
    on error
        set ident to missing value
    end try

    try
        set subElems to every UI element of elem
    on error
        set subElems to {{}}
    end try

    set children to {{}}
    repeat with sub in subElems
        set childTree to my buildTree(sub, depth + 1, maxDepth)
        if childTree is not missing value then
            set end of children to childTree
        end if
    end repeat

    -- Serialise position and size as strings when they are points/sizes
    if pos is not missing value then
        try
            set x to x of pos as real
            set y to y of pos as real
            set pos to "{{" & x & "," & y & "}}"
        on error
            set pos to (pos as string)
        end try
    end if

    if sz is not missing value then
        try
            set w to width of sz as real
            set h to height of sz as real
            set sz to "{{" & w & "," & h & "}}"
        on error
            set sz to (sz as string)
        end try
    end if

    set node to "{{" & ¬
        "\"role\":" & (role as string) & "," & ¬
        "\"roleDescription\":" & (roleDesc as string) & "," & ¬
        "\"title\":" & (title as string) & "," & ¬
        "\"description\":" & (desc as string) & "," & ¬
        "\"value\":" & (val as string) & "," & ¬
        "\"position\":" & (pos as string) & "," & ¬
        "\"size\":" & (sz as string) & "," & ¬
        "\"enabled\":" & (isEnabled as string) & "," & ¬
        "\"focused\":" & (isFocused as string) & "," & ¬
        "\"identifier\":" & (ident as string) & "," & ¬
        "\"children\":" & (children as string) & ¬
        "}}"

    return node
end buildTree

on run argv
    set pid to item 1 of argv as integer
    set maxDepth to item 2 of argv as integer

    set appElem to missing value
    try
        set appElem to (a reference to application process id pid)
    on error
        return "{{\"error\":\"Could not get application process for pid \" & pid}}"
    end try

    try
        set root to first window of appElem
    on error
        set root to appElem
    end try

    set tree to my buildTree(root, 0, maxDepth)
    return tree
end run
"""


# ---------------------------------------------------------------------------
# Element cache
# ---------------------------------------------------------------------------

@dataclass
class _TreeCache:
    """Simple thread-safe TTL cache for accessibility trees."""
    _cache: Dict[int, tuple] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    ttl: float = 2.0  # seconds

    def get(self, pid: int) -> Optional[dict]:
        with self._lock:
            entry = self._cache.get(pid)
            if entry is None:
                return None
            data, ts = entry
            if (time.monotonic() - ts) > self.ttl:
                del self._cache[pid]
                return None
            return data

    def put(self, pid: int, data: dict) -> None:
        with self._lock:
            self._cache[pid] = (data, time.monotonic())

    def invalidate(self, pid: Optional[int] = None) -> None:
        with self._lock:
            if pid is None:
                self._cache.clear()
            else:
                self._cache.pop(pid, None)


# ---------------------------------------------------------------------------
# Public API – standalone functions
# ---------------------------------------------------------------------------

def get_frontmost_app() -> dict:
    """Return information about the currently focused application.

    Returns
    -------
    dict
        ``{pid, name, bundle_id, role}`` of the frontmost app.
    """
    script = """
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp
        set appPID to unix id of frontApp
        try
            set bundleID to bundle identifier of frontApp
        on error
            set bundleID to ""
        end try
        try
            set appRole to role of frontApp
        on error
            set appRole to ""
        end try
        return "{\"pid\":" & appPID & ",\"name\":\"" & appName & "\",\"bundle_id\":\"" & bundleID & "\",\"role\":\"" & appRole & "\"}"
    end tell
    """
    raw = _run_applescript(script)
    parsed = _safe_json(raw.strip())
    if parsed is None:
        raise RuntimeError(f"Failed to parse frontmost app info: {raw!r}")
    return parsed


def get_running_apps() -> list[dict]:
    """List all running applications with basic accessibility info.

    Returns
    -------
    list[dict]
        Each dict contains ``pid``, ``name``, ``bundle_id``, and ``role``.
    """
    script = """
    tell application "System Events"
        set appList to {}
        repeat with proc in (every application process)
            set appName to name of proc
            set appPID to unix id of proc
            try
                set bundleID to bundle identifier of proc
            on error
                set bundleID to ""
            end try
            try
                set appRole to role of proc
            on error
                set appRole to ""
            end try
            set end of appList to "{\\"pid\\":" & appPID & ",\\"name\\":\\"" & appName & "\\",\\"bundle_id\\":\\"" & bundleID & "\\",\\"role\\":\\"" & appRole & "\\"}"
        end repeat
        set AppleScript's text item delimiters to ","
        set raw to "[" & appList & "]"
        set AppleScript's text item delimiters to ""
        return raw
    end tell
    """
    raw = _run_applescript(script)
    parsed = _safe_json(raw.strip())
    if parsed is None:
        raise RuntimeError(f"Failed to parse running apps: {raw!r}")
    return parsed


def get_element_tree(pid: int = None, max_depth: int = 3) -> dict:
    """Recursively retrieve the accessibility tree for *pid*.

    Parameters
    ----------
    pid:
        Process ID to inspect.  Defaults to the frontmost app.
    max_depth:
        How deep to recurse into child elements (default 3).

    Returns
    -------
    dict
        Nested dict with ``role``, ``title``, ``children``, etc.
    """
    if pid is None:
        pid = get_frontmost_app()["pid"]

    script = _build_tree_script(pid, max_depth)
    raw = _run_applescript(script, timeout=30.0)
    parsed = _safe_json(raw.strip())
    if parsed is None:
        raise RuntimeError(f"Failed to parse element tree: {raw!r}")
    return parsed


def find_element(
    pid: int,
    role: str = None,
    title: str = None,
    identifier: str = None,
) -> list[dict]:
    """Search the accessibility tree for elements matching the criteria.

    Parameters
    ----------
    pid:
        Process ID of the target application.
    role:
        AX role to match (e.g. ``"AXButton"``).
    title:
        AX title substring to match.
    identifier:
        AX identifier to match exactly.

    Returns
    -------
    list[dict]
        Matching element dicts.
    """
    tree = get_element_tree(pid, max_depth=6)
    matches: list[dict] = []

    def _walk(node: dict) -> None:
        if not isinstance(node, dict):
            return
        node_role = (node.get("role") or "").strip()
        node_title = (node.get("title") or "").strip()
        node_ident = (node.get("identifier") or "").strip()

        hit = True
        if role and node_role != role:
            hit = False
        if title and title.lower() not in node_title.lower():
            hit = False
        if identifier and node_ident != identifier:
            hit = False

        if hit and (role or title or identifier):
            matches.append(node)

        for child in node.get("children", []):
            _walk(child)

    _walk(tree)
    return matches


def click_element(pid: int, element_position: dict) -> bool:
    """Perform an AX press action on an element at *element_position*.

    Parameters
    ----------
    pid:
        Process ID of the target application.
    element_position:
        Dict with ``x`` and ``y`` keys representing the element's screen position.

    Returns
    -------
    bool
        ``True`` if the click succeeded.
    """
    x = int(element_position.get("x", 0))
    y = int(element_position.get("y", 0))

    script = f"""
    tell application "System Events"
        set appProc to (first application process whose unix id is {pid})
        try
            click at {{{x}, {y}}}
            return "true"
        on error errMsg
            return "{{\\"error\\":\\"" & errMsg & "\\"}}"
        end try
    end tell
    """
    try:
        raw = _run_applescript(script, timeout=10.0)
        return raw.strip().lower() == "true"
    except RuntimeError as exc:
        logger.warning("click_element failed: %s", exc)
        return False


def set_value(pid: int, element_position: dict, value: str) -> bool:
    """Set the AX value of an element at *element_position*.

    Parameters
    ----------
    pid:
        Process ID of the target application.
    element_position:
        Dict with ``x`` and ``y`` keys.
    value:
        The string value to set.

    Returns
    -------
    bool
        ``True`` if the value was set successfully.
    """
    x = int(element_position.get("x", 0))
    y = int(element_position.get("y", 0))
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')

    script = f"""
    tell application "System Events"
        set appProc to (first application process whose unix id is {pid})
        try
            set value of (first UI element of appProc whose value is not missing value) to "{escaped}"
            return "true"
        on error errMsg
            return "{{\\"error\\":\\"" & errMsg & "\\"}}"
        end try
    end tell
    """
    try:
        raw = _run_applescript(script, timeout=10.0)
        return raw.strip().lower() == "true"
    except RuntimeError as exc:
        logger.warning("set_value failed: %s", exc)
        return False


def get_element_attributes(pid: int, element_position: dict) -> dict:
    """Retrieve all AX attributes of an element at *element_position*.

    Parameters
    ----------
    pid:
        Process ID of the target application.
    element_position:
        Dict with ``x`` and ``y`` keys.

    Returns
    -------
    dict
        Attribute name/value pairs.
    """
    x = int(element_position.get("x", 0))
    y = int(element_position.get("y", 0))

    script = f"""
    tell application "System Events"
        set appProc to (first application process whose unix id is {pid})
        try
            set elem to (first UI element of appProc)
            set attrNames to name of every attribute of elem
            set resultDict to "{{"
            repeat with attrName in attrNames
                try
                    set attrVal to value of attribute attrName of elem
                    set resultDict to resultDict & "\\"" & attrName & "\\":\\"" & (attrVal as string) & "\\","
                end try
            end repeat
            set resultDict to resultDict & "}}"
            return resultDict
        on error errMsg
            return "{{\\"error\\":\\"" & errMsg & "\\"}}"
        end try
    end tell
    """
    raw = _run_applescript(script, timeout=10.0)
    parsed = _safe_json(raw.strip())
    if parsed is None:
        return {"raw": raw.strip()}
    return parsed


def type_text(text: str, pid: int = None) -> bool:
    """Type *text* into the focused element.

    Attempts an AX value set first; falls back to System Events keystrokes.

    Parameters
    ----------
    text:
        The text to type.
    pid:
        Optional process ID.  If ``None`` the keystroke path is used directly.

    Returns
    -------
    bool
        ``True`` if typing succeeded.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')

    # Try AX approach when a pid is provided
    if pid is not None:
        ax_script = f"""
        tell application "System Events"
            set appProc to (first application process whose unix id is {pid})
            try
                set focusedElem to first UI element of appProc whose focused is true
                set value of focusedElem to "{escaped}"
                return "true"
            on error
                return "false"
            end try
        end tell
        """
        try:
            raw = _run_applescript(ax_script, timeout=10.0)
            if raw.strip().lower() == "true":
                return True
        except RuntimeError:
            pass

    # Fallback: use System Events key strokes
    keystroke_script = f"""
    tell application "System Events"
        keystroke "{escaped}"
    end tell
    """
    try:
        _run_applescript(keystroke_script, timeout=10.0)
        return True
    except RuntimeError as exc:
        logger.warning("type_text keystroke fallback failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Class wrapper with caching
# ---------------------------------------------------------------------------

class MacOSAccessibility:
    """High-level wrapper around macOS Accessibility functions.

    Caches the element tree for a short TTL to avoid repeated expensive
    AXUIElement walks within the same request cycle.
    """

    def __init__(self, cache_ttl: float = 2.0) -> None:
        self._cache = _TreeCache(ttl=cache_ttl)

    # -- public interface ---------------------------------------------------

    def get_frontmost_app(self) -> dict:
        """Return ``{pid, name, bundle_id, role}`` of the focused app."""
        return get_frontmost_app()

    def get_element_tree(self, pid: int = None, max_depth: int = 3) -> dict:
        """Return the recursive AX tree, using a 2-second cache when possible."""
        if pid is None:
            pid = self.get_frontmost_app()["pid"]

        cached = self._cache.get(pid)
        if cached is not None:
            return cached

        tree = get_element_tree(pid, max_depth)
        self._cache.put(pid, tree)
        return tree

    def find_element(
        self,
        pid: int,
        role: str = None,
        title: str = None,
        identifier: str = None,
    ) -> list[dict]:
        """Search cached tree for matching elements."""
        tree = self.get_element_tree(pid, max_depth=6)
        matches: list[dict] = []

        def _walk(node: dict) -> None:
            if not isinstance(node, dict):
                return
            node_role = (node.get("role") or "").strip()
            node_title = (node.get("title") or "").strip()
            node_ident = (node.get("identifier") or "").strip()

            hit = True
            if role and node_role != role:
                hit = False
            if title and title.lower() not in node_title.lower():
                hit = False
            if identifier and node_ident != identifier:
                hit = False

            if hit and (role or title or identifier):
                matches.append(node)

            for child in node.get("children", []):
                _walk(child)

        _walk(tree)
        return matches

    def click_element(self, pid: int, element_position: dict) -> bool:
        """Press the AX element at *element_position*."""
        result = click_element(pid, element_position)
        if result:
            self._cache.invalidate(pid)
        return result

    def set_value(self, pid: int, element_position: dict, value: str) -> bool:
        """Set the AX value of the element at *element_position*."""
        result = set_value(pid, element_position, value)
        if result:
            self._cache.invalidate(pid)
        return result

    def get_element_attributes(self, pid: int, element_position: dict) -> dict:
        """Return all AX attributes for the element at *element_position*."""
        return get_element_attributes(pid, element_position)

    def type_text(self, text: str, pid: int = None) -> bool:
        """Type *text* using AX or keystroke fallback."""
        return type_text(text, pid)

    def get_running_apps(self) -> list[dict]:
        """List every running app with basic AX metadata."""
        return get_running_apps()

    def invalidate_cache(self, pid: int = None) -> None:
        """Manually expire cached trees."""
        self._cache.invalidate(pid)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

accessibility = MacOSAccessibility()

__all__ = [
    "MacOSAccessibility",
    "accessibility",
    "get_frontmost_app",
    "get_element_tree",
    "find_element",
    "click_element",
    "set_value",
    "get_element_attributes",
    "type_text",
    "get_running_apps",
]
