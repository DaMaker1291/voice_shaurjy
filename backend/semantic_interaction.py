"""JARVIS Semantic Interaction — Find, Click, Type by Meaning.

Instead of:
    mousemove(814, 492)
    click()

Do:
    find(role="button", text="Export")
    click(target)

The system searches DOM, accessibility, and OCR to find the element,
then clicks its center. No fragile coordinates.
"""

import os, sys, json, time, logging, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

log = logging.getLogger("semantic_interaction")


@dataclass
class InteractionTarget:
    """A semantic target for interaction."""
    role: str = ""
    text: str = ""
    text_contains: str = ""
    text_regex: str = ""
    region: tuple = None  # (x, y, w, h) — optional search region
    index: int = 0  # which match if multiple
    min_confidence: float = 0.5


class SemanticInteraction:
    """Find UI elements by meaning, not coordinates."""

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self._perception = None

    def _get_perception(self):
        if self._perception is None:
            from perception_engine import get_perception_engine
            self._perception = get_perception_engine(self.user_id)
        return self._perception

    # ── Find Elements ─────────────────────────────────────────────

    def find(self, role: str = "", text: str = "", text_contains: str = "",
             text_regex: str = "", index: int = 0) -> Optional[dict]:
        """Find a UI element by semantic properties.

        Returns: {"x": center_x, "y": center_y, "text": "...", "role": "...", "source": "..."}
        or None if not found.
        """
        perception = self._get_perception()

        # Try DOM first (most reliable for web)
        elements = perception.get_dom_elements()
        match = self._match_elements(elements, role, text, text_contains, text_regex, index)
        if match:
            return match

        # Try clipboard method (for web: Ctrl+A → Ctrl+C → extract prices/text)
        # This is already handled by VDI agent

        # Try OCR (for non-web apps)
        elements = perception.ocr_screenshot()
        match = self._match_elements(elements, role, text, text_contains, text_regex, index)
        if match:
            return match

        return None

    def find_all(self, role: str = "", text: str = "", text_contains: str = "",
                 text_regex: str = "") -> list[dict]:
        """Find all matching UI elements."""
        perception = self._get_perception()
        elements = perception.get_dom_elements()
        return self._match_all(elements, role, text, text_contains, text_regex)

    def _match_elements(self, elements, role, text, text_contains, text_regex, index):
        """Match elements against criteria, return nth match."""
        matches = self._match_all(elements, role, text, text_contains, text_regex)
        if index < len(matches):
            return matches[index]
        return None

    def _match_all(self, elements, role, text, text_contains, text_regex) -> list[dict]:
        """Match all elements against criteria."""
        results = []
        for el in elements:
            if role and el.role.lower() != role.lower():
                # Fuzzy role matching
                if role.lower() not in el.role.lower():
                    continue
            if text and el.text.strip().lower() != text.strip().lower():
                continue
            if text_contains and text_contains.lower() not in el.text.lower():
                continue
            if text_regex and not re.search(text_regex, el.text, re.IGNORECASE):
                continue
            results.append(el.to_dict())
        return results

    # ── Semantic Actions ──────────────────────────────────────────

    def click(self, role: str = "", text: str = "", text_contains: str = "",
              text_regex: str = "", index: int = 0) -> dict:
        """Click an element found by semantic properties."""
        target = self.find(role=role, text=text, text_contains=text_contains,
                          text_regex=text_regex, index=index)
        if not target:
            return {"success": False, "error": f"Element not found: role={role} text={text}"}

        x, y = target.get("center", (0, 0))
        if x == 0 and y == 0:
            return {"success": False, "error": "Element has no click target"}

        # Click via xdotool
        try:
            import subprocess
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool mousemove --sync {x} {y}'"],
                timeout=3
            )
            time.sleep(0.1)
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool click 1'"],
                timeout=3
            )
            return {"success": True, "clicked": target, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def double_click(self, role: str = "", text: str = "", text_contains: str = "",
                     index: int = 0) -> dict:
        """Double-click an element."""
        target = self.find(role=role, text=text, text_contains=text_contains, index=index)
        if not target:
            return {"success": False, "error": "Element not found"}

        x, y = target.get("center", (0, 0))
        try:
            import subprocess
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool mousemove --sync {x} {y}'"],
                timeout=3
            )
            time.sleep(0.1)
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool click --repeat 2 1'"],
                timeout=3
            )
            return {"success": True, "double_clicked": target}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def right_click(self, role: str = "", text: str = "", text_contains: str = "",
                    index: int = 0) -> dict:
        """Right-click an element (context menu)."""
        target = self.find(role=role, text=text, text_contains=text_contains, index=index)
        if not target:
            return {"success": False, "error": "Element not found"}

        x, y = target.get("center", (0, 0))
        try:
            import subprocess
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool mousemove --sync {x} {y}'"],
                timeout=3
            )
            time.sleep(0.1)
            subprocess.run(
                ["bash", "-c",
                 f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool click 3'"],
                timeout=3
            )
            return {"success": True, "right_clicked": target}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_in(self, text: str, role: str = "", text_contains: str = "",
                clear_first: bool = True) -> dict:
        """Find a text field and type into it."""
        # First find and click the field
        click_result = self.click(role=role, text_contains=text_contains)
        if not click_result.get("success"):
            # Fallback: just type (assume focus is correct)
            pass

        time.sleep(0.2)

        try:
            import subprocess
            if clear_first:
                subprocess.run(
                    ["bash", "-c",
                     "sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool key ctrl+a'"],
                    timeout=3
                )
                time.sleep(0.1)

            # Type using xdotool
            escaped = text.replace("'", "'\\''")
            subprocess.run(
                ["bash", "-c",
                  f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool type --delay 0 -- {escaped}'"],
                timeout=5
            )
            return {"success": True, "typed": text[:50]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def press_key(self, *keys: str) -> dict:
        """Press keyboard shortcut(s)."""
        try:
            import subprocess
            combo = "+".join(keys)
            subprocess.run(
                ["bash", "-c",
                  f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool key {combo}'"],
                timeout=3
            )
            return {"success": True, "pressed": combo}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hotkey(self, *keys: str) -> dict:
        """Press a keyboard shortcut (e.g., ctrl+c, alt+tab)."""
        try:
            import subprocess
            combo = "+".join(keys)
            subprocess.run(
                ["bash", "-c",
                  f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool key {combo}'"],
                timeout=3
            )
            return {"success": True, "hotkey": combo}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scroll(self, direction: str = "down", amount: int = 3) -> dict:
        """Scroll the page."""
        try:
            import subprocess
            button = 5 if direction == "down" else 4
            for _ in range(amount):
                subprocess.run(
                    ["bash", "-c",
                      f"sudo -u workuser bash -c 'DISPLAY=:99 XAUTHORITY=/root/.Xauthority xdotool click {button}'"],
                    timeout=2
                )
                time.sleep(0.05)
            return {"success": True, "scrolled": f"{direction} {amount}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── High-Level Semantic Operations ────────────────────────────

    def search_on_page(self, query: str) -> dict:
        """Use Ctrl+F to search on current page."""
        self.hotkey("ctrl", "f")
        time.sleep(0.5)
        self.type_in(query)
        self.press_key("Return")
        return {"success": True, "searched": query}

    def open_new_tab(self, url: str = "") -> dict:
        """Open a new browser tab."""
        self.hotkey("ctrl", "t")
        time.sleep(0.5)
        if url:
            self.type_in(url)
            self.press_key("Return")
        return {"success": True, "url": url}

    def switch_tab(self, index: int) -> dict:
        """Switch to a browser tab by index."""
        self.hotkey("ctrl", str(index))
        time.sleep(0.3)
        return {"success": True, "tab": index}

    def close_tab(self) -> dict:
        """Close current tab."""
        self.hotkey("ctrl", "w")
        return {"success": True}

    def go_back(self) -> dict:
        """Navigate back."""
        self.hotkey("alt", "Left")
        return {"success": True}

    def go_forward(self) -> dict:
        """Navigate forward."""
        self.hotkey("alt", "Right")
        return {"success": True}

    def select_all(self) -> dict:
        """Select all text."""
        self.hotkey("ctrl", "a")
        return {"success": True}

    def copy(self) -> dict:
        """Copy selection."""
        self.hotkey("ctrl", "c")
        return {"success": True}

    def paste(self) -> dict:
        """Paste from clipboard."""
        self.hotkey("ctrl", "v")
        return {"success": True}


# ── Singleton ──
_interaction: Optional[SemanticInteraction] = None

def get_semantic_interaction(user_id: str = "local") -> SemanticInteraction:
    global _interaction
    if _interaction is None:
        _interaction = SemanticInteraction(user_id)
    return _interaction
