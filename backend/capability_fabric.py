"""JARVIS Capability Fabric — Universal Abstraction Layer.

This is the heart of the system.

The AI never cares whether the underlying computer is:
  - Windows, Linux, macOS
  - WSL, a VM, a container, a remote computer
  - A local app, a browser tab, a CLI tool

It asks the Capability Fabric:

    fabric.computer.click(x, y)
    fabric.computer.type("hello")
    fabric.computer.screenshot()
    fabric.browser.navigate(url)
    fabric.browser.extract_text()
    fabric.app.launch("Blender")
    fabric.app.execute("python script.py")

The Fabric routes to the correct adapter automatically.

ARCHITECTURE:

    JARVIS Mission Engine
            │
            ▼
    ┌──────────────────┐
    │ CAPABILITY FABRIC│
    └────────┬─────────┘
             │
    ┌────────┼────────────────┐
    │        │                │
    ▼        ▼                ▼
 COMPUTER  BROWSER      APPLICATION
 ADAPTER    ADAPTER       ADAPTER
    │        │                │
    ▼        ▼                ▼
 Win32     CDP/DOM         APIs
 UIA       Vision          CLI
 macOS     OCR             Python
 Linux     Mouse/KB        Scripting
 Shell                     UI Automation

EXTERNAL DEPENDENCIES:
  - AI Provider (API #1) — for reasoning
  - Browser CDP (API #2) — for web access
  - Optional Cloud (API #3) — for sync/auth

EVERYTHING ELSE IS LOCAL.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

log = logging.getLogger("capability_fabric")


# ══════════════════════════════════════════════════════════════
#  RESULT TYPES
# ══════════════════════════════════════════════════════════════

@dataclass
class FabricResult:
    """Universal result from any capability."""
    ok: bool
    data: Any = None
    error: str = ""
    method: str = ""
    duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "method": self.method,
            "duration_ms": self.duration_ms,
        }


@dataclass
class WindowInfo:
    """Information about an open window."""
    id: str
    title: str
    app: str = ""
    pid: int = 0
    focused: bool = False
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class ScreenState:
    """Current state of the screen."""
    screenshot_bytes: bytes = b""
    width: int = 0
    height: int = 0
    cursor_x: int = 0
    cursor_y: int = 0
    focused_window: Optional[WindowInfo] = None
    all_windows: List[WindowInfo] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
#  COMPUTER ADAPTER — OS-Level Control
# ══════════════════════════════════════════════════════════════

class ComputerAdapter(ABC):
    """Abstract interface for OS-level computer control.

    Implementations:
      - WindowsComputerAdapter (Win32, UIA, PowerShell)
      - MacOsComputerAdapter (AppleScript, AXUIElement, screencapture)
      - LinuxComputerAdapter (X11, xdotool, shell)
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this adapter works on the current system."""
        ...

    @abstractmethod
    def screenshot(self) -> FabricResult:
        """Capture the screen. Returns JPEG bytes in data."""
        ...

    @abstractmethod
    def click(self, x: int, y: int, button: str = "left") -> FabricResult:
        """Click at coordinates."""
        ...

    @abstractmethod
    def type_text(self, text: str) -> FabricResult:
        """Type text."""
        ...

    @abstractmethod
    def press_key(self, key: str) -> FabricResult:
        """Press a key or key combination."""
        ...

    @abstractmethod
    def move_mouse(self, x: int, y: int) -> FabricResult:
        """Move the mouse cursor."""
        ...

    @abstractmethod
    def launch_app(self, name: str, args: List[str] = None) -> FabricResult:
        """Launch an application."""
        ...

    @abstractmethod
    def close_app(self, name: str) -> FabricResult:
        """Close an application."""
        ...

    @abstractmethod
    def list_windows(self) -> FabricResult:
        """List open windows. Returns List[WindowInfo] in data."""
        ...

    @abstractmethod
    def focus_window(self, title: str) -> FabricResult:
        """Focus a window by title."""
        ...

    @abstractmethod
    def get_screen_state(self) -> ScreenState:
        """Get the full current screen state."""
        ...

    @abstractmethod
    def execute_command(self, cmd: str, timeout: int = 30) -> FabricResult:
        """Execute a shell command."""
        ...

    @abstractmethod
    def read_file(self, path: str) -> FabricResult:
        """Read a file from the filesystem."""
        ...

    @abstractmethod
    def write_file(self, path: str, content: str) -> FabricResult:
        """Write to a file."""
        ...

    @abstractmethod
    def list_directory(self, path: str) -> FabricResult:
        """List directory contents."""
        ...


# ══════════════════════════════════════════════════════════════
#  BROWSER ADAPTER — Web Access
# ══════════════════════════════════════════════════════════════

class BrowserAdapter(ABC):
    """Abstract interface for browser control.

    Implementations:
      - CdpBrowserAdapter (Chrome DevTools Protocol)
      - PlaywrightBrowserAdapter (Playwright)
      - FallbackBrowserAdapter (selenium or subprocess)

    The browser is API #2 — it replaces the need for individual
    website APIs (Booking, Amazon, Spotify, etc.)
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if browser control is available."""
        ...

    @abstractmethod
    def start(self, headless: bool = True) -> FabricResult:
        """Start a browser instance."""
        ...

    @abstractmethod
    def stop(self) -> FabricResult:
        """Stop the browser."""
        ...

    @abstractmethod
    def navigate(self, url: str) -> FabricResult:
        """Navigate to a URL."""
        ...

    @abstractmethod
    def get_url(self) -> str:
        """Get the current URL."""
        ...

    @abstractmethod
    def get_title(self) -> str:
        """Get the current page title."""
        ...

    @abstractmethod
    def screenshot(self) -> FabricResult:
        """Screenshot the current page. Returns JPEG bytes in data."""
        ...

    @abstractmethod
    def get_dom(self) -> FabricResult:
        """Get the current DOM content."""
        ...

    @abstractmethod
    def get_text(self) -> FabricResult:
        """Extract all visible text from the page."""
        ...

    @abstractmethod
    def click_element(self, selector: str) -> FabricResult:
        """Click an element by CSS selector."""
        ...

    @abstractmethod
    def click_text(self, text: str) -> FabricResult:
        """Click an element containing the given text."""
        ...

    @abstractmethod
    def type_into(self, selector: str, text: str) -> FabricResult:
        """Type text into an input field."""
        ...

    @abstractmethod
    def select_option(self, selector: str, value: str) -> FabricResult:
        """Select an option in a dropdown."""
        ...

    @abstractmethod
    def scroll(self, direction: str = "down", amount: int = 3) -> FabricResult:
        """Scroll the page."""
        ...

    @abstractmethod
    def execute_js(self, script: str) -> FabricResult:
        """Execute JavaScript in the page context."""
        ...

    @abstractmethod
    def wait_for(self, selector: str, timeout: int = 10) -> FabricResult:
        """Wait for an element to appear."""
        ...

    @abstractmethod
    def search(self, query: str, engine: str = "google") -> FabricResult:
        """Search using a search engine."""
        ...

    @abstractmethod
    def extract_links(self) -> FabricResult:
        """Extract all links from the page."""
        ...

    @abstractmethod
    def extract_structured(self, schema: str = "") -> FabricResult:
        """Extract structured data from the page."""
        ...


# ══════════════════════════════════════════════════════════════
#  APPLICATION ADAPTER — App Control
# ══════════════════════════════════════════════════════════════

class ApplicationAdapter(ABC):
    """Abstract interface for application control.

    Implementations:
      - LocalApplicationAdapter (CLI, Python, scripting)
      - BlenderApplicationAdapter
      - OfficeApplicationAdapter
      - GenericApplicationAdapter (accessibility + vision)

    This replaces individual API integrations for apps like
    Blender, Office, Git, FFmpeg, etc.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this adapter can handle the app."""
        ...

    @abstractmethod
    def can_handle(self, app_name: str) -> bool:
        """Check if this adapter can control a specific app."""
        ...

    @abstractmethod
    def launch(self, app_name: str, args: List[str] = None) -> FabricResult:
        """Launch an application."""
        ...

    @abstractmethod
    def execute_in_app(self, app_name: str, command: str) -> FabricResult:
        """Execute a command within a running application."""
        ...

    @abstractmethod
    def get_app_state(self, app_name: str) -> FabricResult:
        """Get the current state of an application."""
        ...

    @abstractmethod
    def close(self, app_name: str) -> FabricResult:
        """Close an application."""
        ...


# ══════════════════════════════════════════════════════════════
#  CAPABILITY FABRIC — The Unified Interface
# ══════════════════════════════════════════════════════════════

class CapabilityFabric:
    """The unified interface for all JARVIS capabilities.

    MISSION ENGINE sees only this interface.
    ADAPTERS handle the actual execution.

    Usage:
        fabric = get_capability_fabric()

        # Computer control
        fabric.computer.screenshot()
        fabric.computer.click(100, 200)
        fabric.computer.type_text("hello")

        # Browser control
        fabric.browser.navigate("https://example.com")
        fabric.browser.get_text()
        fabric.browser.click_text("Submit")

        # Application control
        fabric.app.launch("Blender")
        fabric.app.execute_in_app("Blender", "create_scene()")
    """

    def __init__(self):
        self._computer: Optional[ComputerAdapter] = None
        self._browser: Optional[BrowserAdapter] = None
        self._app_adapters: List[ApplicationAdapter] = []
        self._initialized = False

    def _init_adapters(self):
        """Auto-detect and initialize the best adapters."""
        if self._initialized:
            return
        self._initialized = True

        # Initialize Computer Adapter (platform-specific)
        self._computer = self._detect_computer_adapter()
        if self._computer:
            log.info(f"[FABRIC] Computer adapter: {type(self._computer).__name__}")
        else:
            log.warning("[FABRIC] No computer adapter available")

        # Initialize Browser Adapter
        self._browser = self._detect_browser_adapter()
        if self._browser:
            log.info(f"[FABRIC] Browser adapter: {type(self._browser).__name__}")
        else:
            log.warning("[FABRIC] No browser adapter available")

        # Initialize Application Adapters
        self._app_adapters = self._detect_app_adapters()
        log.info(f"[FABRIC] {len(self._app_adapters)} application adapters loaded")

    def _detect_computer_adapter(self) -> Optional[ComputerAdapter]:
        """Detect and return the best computer adapter for this platform."""
        adapters_to_try = []

        if sys.platform == "win32":
            adapters_to_try.append("win32")
        elif sys.platform == "darwin":
            adapters_to_try.append("macos")
        elif sys.platform == "linux":
            adapters_to_try.append("linux")

        for adapter_name in adapters_to_try:
            try:
                if adapter_name == "win32":
                    from adapters.win32_computer import Win32ComputerAdapter
                    adapter = Win32ComputerAdapter()
                    if adapter.is_available():
                        return adapter
                elif adapter_name == "macos":
                    from adapters.macos_computer import MacOsComputerAdapter
                    adapter = MacOsComputerAdapter()
                    if adapter.is_available():
                        return adapter
                elif adapter_name == "linux":
                    from adapters.linux_computer import LinuxComputerAdapter
                    adapter = LinuxComputerAdapter()
                    if adapter.is_available():
                        return adapter
            except ImportError as e:
                log.debug(f"[FABRIC] {adapter_name} adapter not available: {e}")

        return None

    def _detect_browser_adapter(self) -> Optional[BrowserAdapter]:
        """Detect and return the best browser adapter."""
        # Try CDP first (best for Chrome/Edge)
        try:
            from adapters.cdp_browser import CdpBrowserAdapter
            adapter = CdpBrowserAdapter()
            if adapter.is_available():
                return adapter
        except ImportError:
            pass

        # Try Playwright
        try:
            from adapters.playwright_browser import PlaywrightBrowserAdapter
            adapter = PlaywrightBrowserAdapter()
            if adapter.is_available():
                return adapter
        except ImportError:
            pass

        return None

    def _detect_app_adapters(self) -> List[ApplicationAdapter]:
        """Detect all available application adapters."""
        adapters = []

        # Always include generic CLI adapter
        try:
            from adapters.cli_app import CliApplicationAdapter
            adapters.append(CliApplicationAdapter())
        except ImportError:
            pass

        # Try Python script adapter
        try:
            from adapters.python_app import PythonApplicationAdapter
            adapters.append(PythonApplicationAdapter())
        except ImportError:
            pass

        # Try Blender adapter
        try:
            from adapters.blender_app import BlenderApplicationAdapter
            a = BlenderApplicationAdapter()
            if a.is_available():
                adapters.append(a)
        except ImportError:
            pass

        # Try Office adapter
        try:
            from adapters.office_app import OfficeApplicationAdapter
            a = OfficeApplicationAdapter()
            if a.is_available():
                adapters.append(a)
        except ImportError:
            pass

        return adapters

    @property
    def computer(self) -> ComputerAdapter:
        """Access computer control (OS-level)."""
        self._init_adapters()
        if not self._computer:
            raise RuntimeError("No computer adapter available. Check platform support.")
        return self._computer

    @property
    def browser(self) -> BrowserAdapter:
        """Access browser control (web)."""
        self._init_adapters()
        if not self._browser:
            raise RuntimeError("No browser adapter available. Install Chrome or Playwright.")
        return self._browser

    def get_app_adapter(self, app_name: str) -> Optional[ApplicationAdapter]:
        """Get the best adapter for a specific application."""
        self._init_adapters()
        for adapter in self._app_adapters:
            if adapter.can_handle(app_name):
                return adapter
        return None

    @property
    def app(self) -> "AppProxy":
        """Access application control."""
        self._init_adapters()
        return AppProxy(self)

    # ── High-level convenience methods ──

    def screenshot(self) -> FabricResult:
        """Take a screenshot using the best available method."""
        self._init_adapters()
        if self._computer:
            return self._computer.screenshot()
        return FabricResult(ok=False, error="No computer adapter")

    def click(self, x: int, y: int, button: str = "left") -> FabricResult:
        """Click at coordinates."""
        self._init_adapters()
        if self._computer:
            return self._computer.click(x, y, button)
        return FabricResult(ok=False, error="No computer adapter")

    def type_text(self, text: str) -> FabricResult:
        """Type text."""
        self._init_adapters()
        if self._computer:
            return self._computer.type_text(text)
        return FabricResult(ok=False, error="No computer adapter")

    def execute(self, cmd: str) -> FabricResult:
        """Execute a shell command."""
        self._init_adapters()
        if self._computer:
            return self._computer.execute_command(cmd)
        return FabricResult(ok=False, error="No computer adapter")

    def web_search(self, query: str) -> FabricResult:
        """Search the web using the browser."""
        self._init_adapters()
        if self._browser:
            return self._browser.search(query)
        return FabricResult(ok=False, error="No browser adapter")

    def web_navigate(self, url: str) -> FabricResult:
        """Navigate to a URL."""
        self._init_adapters()
        if self._browser:
            return self._browser.navigate(url)
        return FabricResult(ok=False, error="No browser adapter")

    def web_extract(self) -> FabricResult:
        """Extract text from the current page."""
        self._init_adapters()
        if self._browser:
            return self._browser.get_text()
        return FabricResult(ok=False, error="No browser adapter")

    def get_status(self) -> Dict[str, Any]:
        """Get the status of all adapters."""
        self._init_adapters()
        return {
            "computer": type(self._computer).__name__ if self._computer else "none",
            "computer_available": self._computer.is_available() if self._computer else False,
            "browser": type(self._browser).__name__ if self._browser else "none",
            "browser_available": self._browser.is_available() if self._browser else False,
            "app_adapters": [type(a).__name__ for a in self._app_adapters],
            "platform": sys.platform,
        }


class AppProxy:
    """Proxy for application control methods."""

    def __init__(self, fabric: CapabilityFabric):
        self._fabric = fabric

    def launch(self, app_name: str, args: List[str] = None) -> FabricResult:
        """Launch an application."""
        # Try app-specific adapter first
        adapter = self._fabric.get_app_adapter(app_name)
        if adapter:
            return adapter.launch(app_name, args)

        # Fallback to computer adapter
        if self._fabric._computer:
            return self._fabric._computer.launch_app(app_name, args)

        return FabricResult(ok=False, error="No adapter available")

    def execute_in_app(self, app_name: str, command: str) -> FabricResult:
        """Execute a command within a running application."""
        adapter = self._fabric.get_app_adapter(app_name)
        if adapter:
            return adapter.execute_in_app(app_name, command)
        return FabricResult(ok=False, error=f"No adapter for {app_name}")

    def close(self, app_name: str) -> FabricResult:
        """Close an application."""
        adapter = self._fabric.get_app_adapter(app_name)
        if adapter:
            return adapter.close(app_name)
        if self._fabric._computer:
            return self._fabric._computer.close_app(app_name)
        return FabricResult(ok=False, error="No adapter available")


# ══════════════════════════════════════════════════════════════
#  UNIVERSAL EXECUTION LADDER
# ══════════════════════════════════════════════════════════════

EXECUTION_LADDER = [
    "native_api",       # 1. Direct application API
    "official_api",     # 2. Official REST/SDK API
    "cli",              # 3. Command-line interface
    "dom_cdp",          # 4. Browser DOM / Chrome DevTools Protocol
    "accessibility",    # 5. OS accessibility APIs (UIA, AXUIElement)
    "app_scripting",    # 6. Application scripting (AppleScript, VBA)
    "os_automation",    # 7. OS-level automation (PowerShell, Automator)
    "visual_cv",        # 8. Visual computer-use (screenshot + CV)
    "mouse_keyboard",   # 9. Raw mouse/keyboard (last resort)
]


def select_best_method(action: str, available_methods: List[str]) -> Optional[str]:
    """Select the best method from available options using the execution ladder.

    Always uses the highest-priority (lowest number) method available.
    Never uses coordinate clicking if a reliable semantic interface exists.
    """
    for method in EXECUTION_LADDER:
        if method in available_methods:
            return method
    return None


# ══════════════════════════════════════════════════════════════
#  SINGLETON
# ══════════════════════════════════════════════════════════════

_fabric: Optional[CapabilityFabric] = None


def get_capability_fabric() -> CapabilityFabric:
    """Get the global Capability Fabric instance."""
    global _fabric
    if _fabric is None:
        _fabric = CapabilityFabric()
    return _fabric


# ── Convenience aliases for workspace_manager compatibility ──

def get_workspace_fabric():
    """Get the capability fabric for workspace operations.

    This is the main entry point for workspace_manager.py.
    """
    return get_capability_fabric()
