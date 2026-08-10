"""JARVIS GUI Agent — Vision → Action → Verification.

The GUI Agent allows JARVIS to interact with ANY graphical
application by:
1. Taking a screenshot
2. Finding UI elements (OCR, accessibility, visual detection)
3. Performing actions (click, type, keyboard)
4. Verifying the result

This is the "visual last resort" when no API or CLI exists.

ARCHITECTURE:

    SCREENSHOT → UI ANALYSIS → ACTION → VERIFY
         │            │           │         │
         ├── OCR      ├── Text    ├── Click  ├── Screenshot diff
         ├── CV       ├── Icons   ├── Type   ├── OCR comparison
         └── A11y     ├── Buttons ├── Keys   └── Element check
                      └── Menus   └── Drag
"""

import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

log = logging.getLogger("gui_agent")


@dataclass
class UIElement:
    """A detected UI element."""
    id: str
    type: str  # "button", "text_field", "menu", "icon", "link", "tab", "label"
    text: str
    x: int
    y: int
    width: int = 0
    height: int = 0
    confidence: float = 0
    source: str = ""  # "ocr", "accessibility", "visual"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass
class GUIState:
    """Current state of the GUI."""
    screenshot_path: str = ""
    elements: List[UIElement] = field(default_factory=list)
    text_content: str = ""
    focused_element: Optional[UIElement] = None
    timestamp: float = 0
    window_title: str = ""
    window_bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def to_dict(self) -> dict:
        return {
            "screenshot_path": self.screenshot_path,
            "elements": [e.to_dict() for e in self.elements],
            "text_content": self.text_content,
            "focused_element": self.focused_element.to_dict() if self.focused_element else None,
            "timestamp": self.timestamp,
            "window_title": self.window_title,
        }


class GUIAgent:
    """Vision-based GUI interaction agent.

    Enables JARVIS to interact with any graphical application
    by understanding what's on screen and taking appropriate actions.
    """

    def __init__(self, perception=None, action_fabric=None, adapter=None):
        self._perception = perception
        self._fabric = action_fabric
        self._adapter = adapter  # Computer adapter for screenshots/clicks
        self._state_history: List[GUIState] = []
        self._element_cache: Dict[str, UIElement] = {}

    async def observe(self) -> GUIState:
        """Take a screenshot and analyze the current GUI state."""
        state = GUIState(timestamp=time.time())

        # Take screenshot
        if self._adapter:
            try:
                screenshot_path = await self._adapter.screenshot()
                state.screenshot_path = screenshot_path
            except Exception as e:
                log.warning(f"[GUI] Screenshot failed: {e}")

        # Get UI elements via accessibility
        if self._perception:
            try:
                elements = await self._perception.get_ui_elements()
                state.elements = elements
            except Exception as e:
                log.warning(f"[GUI] UI element detection failed: {e}")

        # Get window info
        if self._adapter:
            try:
                windows = await self._adapter.list_windows()
                if windows:
                    focused = windows[0]
                    state.window_title = focused.get("title", "")
                    state.window_bounds = (
                        focused.get("x", 0),
                        focused.get("y", 0),
                        focused.get("width", 0),
                        focused.get("height", 0),
                    )
            except Exception:
                pass

        # Cache elements
        for elem in state.elements:
            self._element_cache[elem.id] = elem

        self._state_history.append(state)
        if len(self._state_history) > 20:
            self._state_history = self._state_history[-20:]

        log.info(f"[GUI] Observed: {len(state.elements)} elements, "
                f"window: {state.window_title[:40]}")
        return state

    async def find_element(self, query: str,
                          state: GUIState = None) -> Optional[UIElement]:
        """Find a UI element matching the query."""
        if state is None:
            state = await self.observe()

        query_lower = query.lower()

        # Score elements by relevance
        scored = []
        for elem in state.elements:
            score = 0
            if query_lower in elem.text.lower():
                score += 10
            if query_lower in elem.type.lower():
                score += 5
            if elem.confidence > 0.8:
                score += 2
            if score > 0:
                scored.append((score, elem))

        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            return scored[0][1]

        log.warning(f"[GUI] No element found for: {query}")
        return None

    async def click_element(self, element: UIElement) -> bool:
        """Click on a UI element."""
        x, y = element.center
        log.info(f"[GUI] Clicking '{element.text}' at ({x}, {y})")

        try:
            if self._adapter:
                await self._adapter.click(x, y)
                return True
            elif self._fabric:
                await self._fabric.execute("click", element=element)
                return True
        except Exception as e:
            log.error(f"[GUI] Click failed: {e}")
            return False

        return False

    async def type_text(self, text: str, element: UIElement = None) -> bool:
        """Type text, optionally into a specific element."""
        if element:
            # Click element first
            await self.click_element(element)
            time.sleep(0.2)

        log.info(f"[GUI] Typing: {text[:30]}...")

        try:
            if self._adapter:
                await self._adapter.type(text)
                return True
            elif self._fabric:
                await self._fabric.execute("type", text=text)
                return True
        except Exception as e:
            log.error(f"[GUI] Type failed: {e}")
            return False

        return False

    async def press_key(self, key: str) -> bool:
        """Press a keyboard shortcut."""
        log.info(f"[GUI] Pressing key: {key}")

        try:
            if self._adapter:
                await self._adapter.key(key)
                return True
        except Exception as e:
            log.error(f"[GUI] Key press failed: {e}")
            return False

        return False

    async def drag(self, start: Tuple[int, int],
                  end: Tuple[int, int]) -> bool:
        """Drag from start to end."""
        log.info(f"[GUI] Dragging from {start} to {end}")

        try:
            if self._adapter:
                await self._adapter.drag(start[0], start[1], end[0], end[1])
                return True
        except Exception as e:
            log.error(f"[GUI] Drag failed: {e}")
            return False

        return False

    async def verify_action(self, expected: str,
                           before_state: GUIState = None) -> bool:
        """Verify an action had the expected effect."""
        if before_state is None and self._state_history:
            before_state = self._state_history[-1]

        after_state = await self.observe()

        # Compare states
        if before_state:
            # Check if new elements appeared
            before_texts = {e.text.lower() for e in before_state.elements}
            after_texts = {e.text.lower() for e in after_state.elements}
            new_texts = after_texts - before_texts

            if expected.lower() in " ".join(new_texts):
                log.info(f"[GUI] Verification passed: '{expected}' appeared")
                return True

            # Check if window changed
            if before_state.window_title != after_state.window_title:
                log.info(f"[GUI] Window changed: {after_state.window_title}")
                return True

        # Check if expected text is visible
        for elem in after_state.elements:
            if expected.lower() in elem.text.lower():
                log.info(f"[GUI] Verification passed: found '{expected}'")
                return True

        log.warning(f"[GUI] Verification failed: '{expected}' not found")
        return False

    async def perform_task(self, task: str) -> Dict[str, Any]:
        """Autonomously perform a GUI task.

        High-level: describes what to do, agent figures out how.
        """
        log.info(f"[GUI] Performing task: {task[:80]}...")

        # Observe current state
        state = await self.observe()

        # Simple task decomposition
        task_lower = task.lower()
        result = {"success": False, "actions": []}

        if "click" in task_lower or "press" in task_lower:
            # Find the element to click
            element_name = task_lower.replace("click", "").replace("press", "").strip()
            element = await self.find_element(element_name, state)
            if element:
                success = await self.click_element(element)
                result["success"] = success
                result["actions"].append({"action": "click", "element": element.text})
            else:
                result["error"] = f"Could not find element: {element_name}"

        elif "type" in task_lower or "enter" in task_lower:
            # Type text
            text = task_lower.replace("type", "").replace("enter", "").strip()
            success = await self.type_text(text)
            result["success"] = success
            result["actions"].append({"action": "type", "text": text})

        elif "find" in task_lower or "look for" in task_lower:
            query = task_lower.replace("find", "").replace("look for", "").strip()
            element = await self.find_element(query, state)
            result["success"] = element is not None
            if element:
                result["element"] = element.to_dict()

        else:
            # Generic: observe and report
            result["success"] = True
            result["state"] = state.to_dict()

        return result

    def get_state_history(self) -> List[GUIState]:
        """Get recent GUI state history."""
        return self._state_history

    def get_cached_element(self, element_id: str) -> Optional[UIElement]:
        """Get a cached UI element."""
        return self._element_cache.get(element_id)


# ── Singleton ──
_gui_agent: Optional[GUIAgent] = None


def get_gui_agent(perception=None, action_fabric=None, adapter=None) -> GUIAgent:
    global _gui_agent
    if _gui_agent is None:
        _gui_agent = GUIAgent(perception, action_fabric, adapter)
    return _gui_agent
