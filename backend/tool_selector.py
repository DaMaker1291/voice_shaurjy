"""JARVIS Tool Selection Hierarchy — Universal Execution Ladder.

Follows the Capability Fabric's execution ladder:

  1. Native Application API
  2. Official API
  3. CLI
  4. Browser DOM/CDP
  5. Accessibility API
  6. Application Scripting
  7. OS Automation
  8. Visual Computer-Use Interaction
  9. Mouse/Keyboard Fallback

Never use coordinate clicking if a reliable semantic interface exists.
The system dynamically discovers available capabilities and picks the best.

This module wraps the Capability Fabric's execution ladder
for backward compatibility with existing code.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

log = logging.getLogger("tool_selector")


class ControlMethod(IntEnum):
    """Priority ranking — lower number = always preferred."""
    NATIVE_API = 1        # Direct application API
    OFFICIAL_API = 2      # Official REST/SDK API
    CLI = 3               # Command-line interface
    DOM_CDP = 4           # Browser DOM / Chrome DevTools Protocol
    ACCESSIBILITY = 5     # OS accessibility APIs (UIA, AXUIElement)
    APP_SCRIPTING = 6     # Application scripting (AppleScript, VBA, AutoHotkey)
    OS_AUTOMATION = 7     # OS-level automation (PowerShell, Automator)
    VISUAL_CV = 8         # Visual computer-use (screenshot + CV + click)
    MOUSE_KEYBOARD = 9    # Raw mouse/keyboard (last resort)


@dataclass
class ToolCapability:
    """A discovered tool capability with its control method."""
    name: str
    method: ControlMethod
    tool_name: str
    command: str = ""
    verified: bool = False
    confidence: float = 1.0
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "method": self.method.name,
            "method_priority": int(self.method),
            "tool_name": self.tool_name,
            "command": self.command,
            "verified": self.verified,
            "confidence": self.confidence,
        }


@dataclass
class ToolRecommendation:
    """A recommended tool for a specific action."""
    action: str
    recommended_tool: ToolCapability
    alternatives: List[ToolCapability] = field(default_factory=list)
    reasoning: str = ""
    fallback_chain: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "recommended": self.recommended_tool.to_dict(),
            "alternatives": [t.to_dict() for t in self.alternatives],
            "reasoning": self.reasoning,
            "fallback_chain": self.fallback_chain,
        }


# ══════════════════════════════════════════════════════════════
#  ACTION-TO-METHOD MAPPING
# ══════════════════════════════════════════════════════════════

# For each action type, define which control methods are applicable
# and in what priority order.
ACTION_METHOD_MAP: Dict[str, List[ControlMethod]] = {
    "launch_app": [
        ControlMethod.CLI,
        ControlMethod.OS_AUTOMATION,
        ControlMethod.APP_SCRIPTING,
        ControlMethod.ACCESSIBILITY,
    ],
    "close_app": [
        ControlMethod.CLI,
        ControlMethod.OS_AUTOMATION,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "click": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.APP_SCRIPTING,
        ControlMethod.VISUAL_CV,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "type_text": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.APP_SCRIPTING,
        ControlMethod.CLI,
        ControlMethod.VISUAL_CV,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "press_key": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.APP_SCRIPTING,
        ControlMethod.CLI,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "navigate_web": [
        ControlMethod.DOM_CDP,
        ControlMethod.CLI,
        ControlMethod.VISUAL_CV,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "web_search": [
        ControlMethod.OFFICIAL_API,
        ControlMethod.DOM_CDP,
        ControlMethod.CLI,
    ],
    "web_scrape": [
        ControlMethod.DOM_CDP,
        ControlMethod.OFFICIAL_API,
        ControlMethod.CLI,
        ControlMethod.VISUAL_CV,
    ],
    "read_file": [
        ControlMethod.CLI,
        ControlMethod.NATIVE_API,
        ControlMethod.OS_AUTOMATION,
    ],
    "write_file": [
        ControlMethod.CLI,
        ControlMethod.NATIVE_API,
        ControlMethod.OS_AUTOMATION,
    ],
    "screenshot": [
        ControlMethod.NATIVE_API,
        ControlMethod.CLI,
        ControlMethod.VISUAL_CV,
    ],
    "extract_text": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.VISUAL_CV,
    ],
    "scroll": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "select_option": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "upload_file": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.CLI,
    ],
    "download_file": [
        ControlMethod.DOM_CDP,
        ControlMethod.CLI,
    ],
    "fill_form": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.VISUAL_CV,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "wait_for_element": [
        ControlMethod.DOM_CDP,
        ControlMethod.ACCESSIBILITY,
        ControlMethod.VISUAL_CV,
    ],
    "list_windows": [
        ControlMethod.ACCESSIBILITY,
        ControlMethod.OS_AUTOMATION,
        ControlMethod.CLI,
    ],
    "focus_window": [
        ControlMethod.ACCESSIBILITY,
        ControlMethod.OS_AUTOMATION,
        ControlMethod.CLI,
        ControlMethod.MOUSE_KEYBOARD,
    ],
    "run_command": [
        ControlMethod.CLI,
        ControlMethod.OS_AUTOMATION,
    ],
    "send_notification": [
        ControlMethod.NATIVE_API,
        ControlMethod.OS_AUTOMATION,
        ControlMethod.CLI,
    ],
}


class ToolSelector:
    """Selects the best available tool for a given action.

    Discovers capabilities at init, then recommends the highest-priority
    available method for each action.
    """

    def __init__(self):
        self._capabilities: Dict[str, List[ToolCapability]] = {}
        self._discover_capabilities()

    def _discover_capabilities(self):
        """Discover all available tool capabilities.

        Uses both the legacy skill registry and the new Capability Fabric.
        """
        # Register capabilities from Capability Fabric (primary source)
        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            status = fabric.get_status()

            if status.get("computer_available"):
                # Computer adapter provides these capabilities
                for action in ["click", "type_text", "press_key", "screenshot",
                               "launch_app", "close_app", "list_windows", "focus_window",
                               "execute_command", "read_file", "write_file"]:
                    cap = ToolCapability(
                        name=action, method=ControlMethod.NATIVE_API,
                        tool_name="capability_fabric", verified=True,
                    )
                    self._register_cap(action, cap)

            if status.get("browser_available"):
                # Browser adapter provides these capabilities
                for action in ["navigate_web", "web_search", "web_scrape", "click",
                               "type_text", "extract_text", "screenshot", "scroll",
                               "fill_form", "upload_file", "download_file"]:
                    cap = ToolCapability(
                        name=action, method=ControlMethod.DOM_CDP,
                        tool_name="capability_fabric_browser", verified=True,
                    )
                    self._register_cap(action, cap)

        except ImportError:
            log.debug("Capability Fabric not available, falling back to skill registry")

        # Register capabilities from skill registry (legacy fallback)
        try:
            from skill_registry import get_skill_registry
            registry = get_skill_registry()

            for tool_name, tool in registry.tools.items():
                if not tool.available:
                    continue
                for skill in tool.skills:
                    method = self._skill_method_to_control(skill.method)
                    if method:
                        cap = ToolCapability(
                            name=skill.name,
                            method=method,
                            tool_name=tool_name,
                            command=skill.command,
                            verified=skill.verified,
                        )
                        self._register_cap(skill.name, cap)
        except Exception as e:
            log.debug(f"Skill registry discovery failed: {e}")

        # Register built-in capabilities
        self._register_builtin_capabilities()
        log.info(f"ToolSelector discovered {sum(len(v) for v in self._capabilities.values())} capabilities")

    def _skill_method_to_control(self, method_str: str) -> Optional[ControlMethod]:
        """Map skill registry method string to ControlMethod."""
        mapping = {
            "api": ControlMethod.OFFICIAL_API,
            "cli": ControlMethod.CLI,
            "cdp": ControlMethod.DOM_CDP,
            "vision": ControlMethod.VISUAL_CV,
            "mouse_keyboard": ControlMethod.MOUSE_KEYBOARD,
            "accessibility": ControlMethod.ACCESSIBILITY,
            "native_api": ControlMethod.NATIVE_API,
            "scripting": ControlMethod.APP_SCRIPTING,
            "os_automation": ControlMethod.OS_AUTOMATION,
        }
        return mapping.get(method_str)

    def _register_cap(self, action_name: str, cap: ToolCapability):
        """Register a capability for an action."""
        if action_name not in self._capabilities:
            self._capabilities[action_name] = []
        # Deduplicate
        for existing in self._capabilities[action_name]:
            if existing.method == cap.method and existing.tool_name == cap.tool_name:
                return
        self._capabilities[action_name].append(cap)

    def _register_builtin_capabilities(self):
        """Register built-in capabilities that are always available."""
        import sys
        import subprocess

        # CLI is always available
        cli_cap = ToolCapability(
            name="shell", method=ControlMethod.CLI,
            tool_name="system", verified=True,
        )

        # Register for all CLI-capable actions
        for action in ["run_command", "read_file", "write_file", "launch_app",
                       "close_app", "list_windows"]:
            self._register_cap(action, cli_cap)

        # OS-specific capabilities
        if sys.platform == "win32":
            ps_cap = ToolCapability(
                name="powershell", method=ControlMethod.OS_AUTOMATION,
                tool_name="powershell", verified=True,
            )
            for action in ["launch_app", "close_app", "list_windows", "focus_window"]:
                self._register_cap(action, ps_cap)

            # Windows Accessibility (UIA)
            uia_cap = ToolCapability(
                name="windows_uia", method=ControlMethod.ACCESSIBILITY,
                tool_name="uiautomation", verified=self._check_import("uiautomation"),
            )
            for action in ["click", "type_text", "extract_text", "list_windows"]:
                self._register_cap(action, uia_cap)

        elif sys.platform == "darwin":
            # macOS AppleScript
            script_cap = ToolCapability(
                name="applescript", method=ControlMethod.APP_SCRIPTING,
                tool_name="osascript", verified=True,
            )
            for action in ["launch_app", "close_app", "list_windows", "focus_window"]:
                self._register_cap(action, script_cap)

            # macOS Accessibility (AXUIElement)
            ax_cap = ToolCapability(
                name="axuielement", method=ControlMethod.ACCESSIBILITY,
                tool_name="AXUIElement", verified=self._check_import("ApplicationServices"),
            )
            for action in ["click", "type_text", "extract_text"]:
                self._register_cap(action, ax_cap)

        elif sys.platform == "linux":
            # xdotool
            try:
                subprocess.run(["xdotool", "--version"], capture_output=True, timeout=2)
                xdotool_cap = ToolCapability(
                    name="xdotool", method=ControlMethod.MOUSE_KEYBOARD,
                    tool_name="xdotool", verified=True,
                )
                for action in ["click", "type_text", "press_key", "focus_window"]:
                    self._register_cap(action, xdotool_cap)
            except Exception:
                pass

            # wmctrl
            try:
                subprocess.run(["wmctrl", "-l"], capture_output=True, timeout=2)
                wmctrl_cap = ToolCapability(
                    name="wmctrl", method=ControlMethod.OS_AUTOMATION,
                    tool_name="wmctrl", verified=True,
                )
                for action in ["list_windows", "focus_window"]:
                    self._register_cap(action, wmctrl_cap)
            except Exception:
                pass

        # Browser CDP (if available)
        try:
            from cdp_browser import CdpBrowser
            cdp_cap = ToolCapability(
                name="cdp_browser", method=ControlMethod.DOM_CDP,
                tool_name="cdp_browser", verified=True,
            )
            for action in ["navigate_web", "click", "type_text", "extract_text",
                           "web_scrape", "screenshot", "scroll", "fill_form"]:
                self._register_cap(action, cdp_cap)
        except ImportError:
            pass

        # Playwright (if available)
        try:
            import playwright
            pw_cap = ToolCapability(
                name="playwright", method=ControlMethod.DOM_CDP,
                tool_name="playwright", verified=True,
            )
            for action in ["navigate_web", "click", "type_text", "extract_text",
                           "web_scrape", "screenshot", "scroll", "fill_form",
                           "upload_file", "download_file", "wait_for_element"]:
                self._register_cap(action, pw_cap)
        except ImportError:
            pass

    def _check_import(self, module_name: str) -> bool:
        """Check if a module can be imported."""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    def recommend(self, action: str) -> Optional[ToolRecommendation]:
        """Recommend the best tool for a given action.

        Returns the highest-priority available tool, plus alternatives.
        """
        # Get the priority order for this action
        priority_order = ACTION_METHOD_MAP.get(action, [
            ControlMethod.CLI,
            ControlMethod.DOM_CDP,
            ControlMethod.ACCESSIBILITY,
            ControlMethod.VISUAL_CV,
            ControlMethod.MOUSE_KEYBOARD,
        ])

        # Get available capabilities for this action
        available = self._capabilities.get(action, [])
        if not available:
            # Try to find capabilities that match via action name fuzzy matching
            for cap_action, caps in self._capabilities.items():
                if action in cap_action or cap_action in action:
                    available.extend(caps)

        if not available:
            log.warning(f"No capabilities found for action: {action}")
            return None

        # Sort by priority order
        def sort_key(cap: ToolCapability) -> int:
            try:
                return priority_order.index(cap.method)
            except ValueError:
                return 999  # Unknown method = lowest priority

        available.sort(key=sort_key)

        # Pick the best
        best = available[0]
        alternatives = available[1:4]  # Top 3 alternatives

        # Build fallback chain
        fallback_chain = [cap.tool_name for cap in available]

        reasoning = f"Selected {best.method.name} ({best.tool_name}) over {len(alternatives)} alternatives"

        return ToolRecommendation(
            action=action,
            recommended_tool=best,
            alternatives=alternatives,
            reasoning=reasoning,
            fallback_chain=fallback_chain,
        )

    def recommend_with_fallback(self, action: str,
                                failed_method: Optional[ControlMethod] = None
                               ) -> Optional[ToolCapability]:
        """Recommend the next best tool, excluding a failed method."""
        available = self._capabilities.get(action, [])
        if not available:
            return None

        # Filter out the failed method
        if failed_method:
            available = [c for c in available if c.method != failed_method]

        if not available:
            return None

        # Return the first available
        return available[0]

    def get_available_for_action(self, action: str) -> List[ToolCapability]:
        """Get all available capabilities for an action."""
        return self._capabilities.get(action, [])

    def get_all_capabilities(self) -> Dict[str, List[Dict]]:
        """Get all discovered capabilities (for debugging/display)."""
        result = {}
        for action, caps in self._capabilities.items():
            result[action] = [c.to_dict() for c in caps]
        return result

    def can_perform(self, action: str) -> bool:
        """Check if any tool can perform this action."""
        return len(self._capabilities.get(action, [])) > 0


# ── Singleton ──
_selector: Optional[ToolSelector] = None


def get_tool_selector() -> ToolSelector:
    global _selector
    if _selector is None:
        _selector = ToolSelector()
    return _selector
