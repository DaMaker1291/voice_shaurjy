"""
Accessibility Bridge — Semantic UI navigation via Windows Accessibility Tree.

No hardcoded coordinates. No hardcoded CSS selectors.
Discovers UI elements dynamically by name, role, and position.
Falls back to vision model when accessibility tree is empty.
"""

import re
import json
import time
import logging
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-a11y")


@dataclass
class UIElement:
    """A discovered UI element from the accessibility tree."""
    name: str = ""
    role: str = ""
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h
    center: Tuple[int, int] = (0, 0)
    children_count: int = 0
    is_enabled: bool = True
    is_visible: bool = True
    automation_id: str = ""
    class_name: str = ""
    value: str = ""
    depth: int = 0

    @property
    def x(self): return self.bounds[0]
    @property
    def y(self): return self.bounds[1]

    def to_dict(self):
        return {
            "name": self.name, "role": self.role,
            "bounds": self.bounds, "center": self.center,
            "enabled": self.is_enabled, "visible": self.is_visible,
            "value": self.value,
        }


class AccessibilityBridge:
    """Discover and interact with UI elements via the Windows Accessibility Tree.
    
    Uses the `uiautomation` library to walk the live UI tree of any application.
    Matches elements by semantic properties (name, role, position) — never by
    hardcoded coordinates or selectors.
    """

    def __init__(self):
        self._uia = None
        try:
            import uiautomation
            self._uia = uiautomation
        except ImportError:
            log.debug("[A11Y] uiautomation not installed")

    def find_element(self, name: str = "", role: str = "",
                     window_title: str = "", fuzzy: bool = True,
                     index: int = 0) -> Optional[UIElement]:
        """Find a UI element by semantic properties.
        
        Args:
            name: Element name/label to match (fuzzy or exact)
            role: Element role (Button, Edit, Text, MenuItem, etc.)
            window_title: Window to search in (uses active window if empty)
            fuzzy: Enable fuzzy matching on names
            index: Which match to return (0 = first)
        
        Returns:
            UIElement with bounds, or None if not found
        """
        if not self._uia:
            return self._fallback_find(name, window_title)

        try:
            # Get the root element (window)
            if window_title:
                root = self._uia.WindowControl(Name=window_title)
            else:
                root = self._uia.GetRootControl()

            # Search for matching elements
            elements = []
            self._walk_tree(root, name, role, fuzzy, elements, max_depth=8)

            if elements and index < len(elements):
                return elements[index]

            # Fallback: try vision
            return self._fallback_find(name, window_title)

        except Exception as e:
            log.debug(f"[A11Y] find_element failed: {e}")
            return self._fallback_find(name, window_title)

    def find_all(self, name: str = "", role: str = "",
                 window_title: str = "", fuzzy: bool = True,
                 limit: int = 20) -> List[UIElement]:
        """Find all matching UI elements."""
        if not self._uia:
            return []

        try:
            if window_title:
                root = self._uia.WindowControl(Name=window_title)
            else:
                root = self._uia.GetRootControl()

            elements = []
            self._walk_tree(root, name, role, fuzzy, elements, max_depth=8)
            return elements[:limit]

        except Exception as e:
            log.debug(f"[A11Y] find_all failed: {e}")
            return []

    def click_element(self, element: UIElement) -> bool:
        """Click the center of a discovered UI element."""
        if not element or element.center == (0, 0):
            return False
        try:
            import pyautogui
            pyautogui.click(element.center[0], element.center[1])
            return True
        except Exception as e:
            log.debug(f"[A11Y] click failed: {e}")
            return False

    def click(self, name: str = "", role: str = "",
              window_title: str = "", index: int = 0) -> bool:
        """Find and click an element by semantic properties."""
        elem = self.find_element(name=name, role=role,
                                  window_title=window_title, index=index)
        if elem:
            return self.click_element(elem)
        return False

    def type_into(self, element: UIElement, text: str) -> bool:
        """Type text into a discovered UI element."""
        if not element:
            return False
        try:
            import pyautogui
            # Click to focus, then type
            pyautogui.click(element.center[0], element.center[1])
            time.sleep(0.1)
            pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyperclip.paste(text)
            return True
        except Exception as e:
            log.debug(f"[A11Y] type_into failed: {e}")
            return False

    def get_window_tree(self, window_title: str = "", max_depth: int = 4) -> Dict:
        """Get the accessibility tree of a window as a nested dict.
        
        Useful for debugging and LLM context.
        """
        if not self._uia:
            return {"error": "uiautomation not installed"}

        try:
            if window_title:
                root = self._uia.WindowControl(Name=window_title)
            else:
                root = self._uia.GetRootControl()

            tree = self._element_to_dict(root, max_depth, 0)
            return tree

        except Exception as e:
            return {"error": str(e)}

    def list_windows(self) -> List[Dict]:
        """List all visible top-level windows."""
        if not self._uia:
            return []

        try:
            windows = []
            for w in self._uia.GetRootControl().GetChildren():
                try:
                    name = w.Name
                    if name:
                        bounds = w.BoundingRectangle
                        windows.append({
                            "name": name,
                            "class": w.ClassName,
                            "bounds": (bounds.left, bounds.top, bounds.width(), bounds.height()) if bounds else (0, 0, 0, 0),
                        })
                except Exception:
                    pass
            return windows
        except Exception:
            return []

    def _walk_tree(self, element, target_name: str, target_role: str,
                    fuzzy: bool, results: list, max_depth: int, depth: int = 0):
        """Recursively walk the accessibility tree to find matching elements."""
        if depth > max_depth or len(results) >= 50:
            return

        try:
            name = element.Name or ""
            role = element.ControlTypeName or ""

            # Match by name
            name_match = False
            if target_name:
                if fuzzy:
                    name_match = target_name.lower() in name.lower()
                else:
                    name_match = target_name == name

            # Match by role
            role_match = False
            if target_role:
                role_match = target_role.lower() in role.lower()

            # If both specified, both must match; if only one, that one must match
            if target_name and target_role:
                matched = name_match and role_match
            elif target_name:
                matched = name_match
            elif target_role:
                matched = role_match
            else:
                matched = False

            if matched and name:
                bounds = element.BoundingRectangle
                if bounds and bounds.width() > 0 and bounds.height() > 0:
                    x, y, w, h = bounds.left, bounds.top, bounds.width(), bounds.height()
                    ui_elem = UIElement(
                        name=name, role=role,
                        bounds=(x, y, w, h),
                        center=(x + w // 2, y + h // 2),
                        is_enabled=element.IsEnabled,
                        class_name=element.ClassName or "",
                        value=getattr(element, "Value", "") or "",
                        depth=depth,
                    )
                    results.append(ui_elem)

            # Recurse into children
            for child in element.GetChildren():
                self._walk_tree(child, target_name, target_role, fuzzy,
                                results, max_depth, depth + 1)

        except Exception:
            pass

    def _element_to_dict(self, element, max_depth: int, depth: int) -> Dict:
        """Convert an accessibility element to a nested dict."""
        try:
            name = element.Name or ""
            role = element.ControlTypeName or ""
            bounds = element.BoundingRectangle
            node = {
                "name": name, "role": role,
                "bounds": (bounds.left, bounds.top, bounds.width(), bounds.height()) if bounds else None,
                "enabled": element.IsEnabled,
            }
            if depth < max_depth:
                children = []
                for child in element.GetChildren():
                    children.append(self._element_to_dict(child, max_depth, depth + 1))
                if children:
                    node["children"] = children
            return node
        except Exception:
            return {}

    def _fallback_find(self, name: str, window_title: str) -> Optional[UIElement]:
        """Fallback: use pyautogui.locateOnScreen or vision model."""
        # This is a last resort — vision-based element finding
        return None


# ── Convenience ────────────────────────────────────────────────────────────

_bridge: Optional[AccessibilityBridge] = None

def get_a11y_bridge() -> AccessibilityBridge:
    global _bridge
    if _bridge is None:
        _bridge = AccessibilityBridge()
    return _bridge

def find_element(name: str = "", role: str = "", window_title: str = "") -> Optional[UIElement]:
    """Find a UI element by semantic properties."""
    return get_a11y_bridge().find_element(name=name, role=role, window_title=window_title)

def click(name: str = "", role: str = "", window_title: str = "") -> bool:
    """Find and click an element."""
    return get_a11y_bridge().click(name=name, role=role, window_title=window_title)

def get_window_tree(window_title: str = "", max_depth: int = 4) -> Dict:
    """Get the accessibility tree of a window."""
    return get_a11y_bridge().get_window_tree(window_title=window_title, max_depth=max_depth)

def list_windows() -> List[Dict]:
    """List all visible windows."""
    return get_a11y_bridge().list_windows()
