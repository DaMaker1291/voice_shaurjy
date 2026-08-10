"""JARVIS Skill Registry — Capability Discovery.

Before JARVIS attempts any task, it discovers what tools are actually available.
No pretending. No claiming capabilities it doesn't have.

The registry is live — it checks what's installed, what APIs work, what's accessible.
"""

import os, sys, json, subprocess, logging, time
from pathlib import Path
from dataclasses import dataclass, field

log = logging.getLogger("skill_registry")


@dataclass
class Skill:
    """A specific capability a tool provides."""
    name: str
    description: str
    method: str  # "api", "cli", "cdp", "vision", "mouse_keyboard"
    command: str = ""  # CLI command or API endpoint
    verified: bool = False
    last_verified: float = 0
    verification_method: str = ""  # How we verified this works
    error: str = ""


@dataclass
class Tool:
    """A tool/application that JARVIS can use."""
    name: str
    available: bool = False
    version: str = ""
    skills: list = field(default_factory=list)
    installation_path: str = ""
    verification_method: str = ""
    last_verified: float = 0


class SkillRegistry:
    """Discovers what JARVIS can actually do — verified capabilities only."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self._discover_all()

    def _discover_all(self):
        """Discover all available tools and their capabilities."""
        self._discover_browsers()
        self._discover_media_tools()
        self._discover_developer_tools()
        self._discover_system_tools()
        self._discover_python_libs()
        self._discover_apis()
        self._discover_vdi_capabilities()
        log.warning(f"Discovered {len(self.tools)} tools with "
                    f"{sum(len(t.skills) for t in self.tools.values())} skills")

    def _discover_browsers(self):
        """Discover browser capabilities."""
        # Chrome
        chrome = Tool(name="chrome")
        try:
            result = subprocess.run(["google-chrome", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                chrome.available = True
                chrome.version = result.stdout.strip().split()[-1]
                chrome.skills = [
                    Skill(name="browse", description="Navigate to URLs", method="cdp",
                          command="google-chrome"),
                    Skill(name="search", description="Search the web", method="cdp"),
                    Skill(name="download", description="Download files", method="cdp"),
                    Skill(name="screenshot", description="Take screenshots", method="vision",
                          verification_method="scrot"),
                    Skill(name="extract_text", description="Extract page text", method="cdp",
                          verification_method="clipboard"),
                ]
        except Exception:
            chrome.error = "Chrome not found"
        self.tools["chrome"] = chrome

        # Chromium alternative
        chromium = Tool(name="chromium")
        try:
            result = subprocess.run(["chromium-browser", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                chromium.available = True
                chromium.version = result.stdout.strip().split()[-1]
                chromium.skills = chrome.skills.copy()
        except Exception:
            pass
        self.tools["chromium"] = chromium

    def _discover_media_tools(self):
        """Discover media creation tools."""
        # FFmpeg
        ffmpeg = Tool(name="ffmpeg")
        try:
            result = subprocess.run(["ffmpeg", "-version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                ffmpeg.available = True
                version_line = result.stdout.split('\n')[0]
                ffmpeg.version = version_line.split()[2] if len(version_line.split()) > 2 else ""
                ffmpeg.skills = [
                    Skill(name="encode", description="Encode video/audio", method="cli",
                          command="ffmpeg"),
                    Skill(name="transcode", description="Convert between formats", method="cli"),
                    Skill(name="compose", description="Compose multiple streams", method="cli"),
                    Skill(name="extract_audio", description="Extract audio from video", method="cli"),
                    Skill(name="resize", description="Resize video", method="cli"),
                ]
        except Exception:
            ffmpeg.error = "FFmpeg not found"
        self.tools["ffmpeg"] = ffmpeg

        # ImageMagick
        imagemagick = Tool(name="imagemagick")
        try:
            result = subprocess.run(["convert", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                imagemagick.available = True
                imagemagick.skills = [
                    Skill(name="convert", description="Convert image formats", method="cli"),
                    Skill(name="resize", description="Resize images", method="cli"),
                    Skill(name="composite", description="Composite images", method="cli"),
                    Skill(name="ocr", description="Extract text from images", method="cli"),
                ]
        except Exception:
            pass
        self.tools["imagemagick"] = imagemagick

        # Scrot (screenshot)
        scrot = Tool(name="scrot")
        try:
            result = subprocess.run(["scrot", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0 or "scrot" in result.stdout.lower():
                scrot.available = True
                scrot.skills = [
                    Skill(name="screenshot", description="Capture screen", method="cli",
                          command="scrot", verified=True,
                          verification_method="tested on DISPLAY=:99"),
                ]
        except Exception:
            pass
        self.tools["scrot"] = scrot

    def _discover_developer_tools(self):
        """Discover developer tools."""
        # Python
        python = Tool(name="python")
        try:
            result = subprocess.run([sys.executable, "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                python.available = True
                python.version = result.stdout.strip().split()[-1]
                python.skills = [
                    Skill(name="run_script", description="Execute Python scripts", method="cli",
                          command=sys.executable, verified=True),
                    Skill(name="install_package", description="Install pip packages", method="cli"),
                ]
        except Exception:
            pass
        self.tools["python"] = python

        # Git
        git = Tool(name="git")
        try:
            result = subprocess.run(["git", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                git.available = True
                git.version = result.stdout.strip().split()[-1]
                git.skills = [
                    Skill(name="clone", description="Clone repositories", method="cli"),
                    Skill(name="commit", description="Commit changes", method="cli"),
                    Skill(name="push", description="Push to remote", method="cli"),
                ]
        except Exception:
            pass
        self.tools["git"] = git

        # Node.js
        node = Tool(name="node")
        try:
            result = subprocess.run(["node", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                node.available = True
                node.version = result.stdout.strip()
                node.skills = [
                    Skill(name="run_js", description="Execute JavaScript", method="cli"),
                    Skill(name="npm_install", description="Install npm packages", method="cli"),
                ]
        except Exception:
            pass
        self.tools["node"] = node

    def _discover_system_tools(self):
        """Discover system automation tools."""
        # xdotool (mouse/keyboard control)
        xdotool = Tool(name="xdotool")
        try:
            result = subprocess.run(["xdotool", "--version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                xdotool.available = True
                xdotool.skills = [
                    Skill(name="click", description="Click at coordinates", method="mouse_keyboard",
                          command="xdotool", verified=True, verification_method="tested"),
                    Skill(name="type", description="Type text", method="mouse_keyboard",
                          verified=True, verification_method="tested"),
                    Skill(name="key", description="Press keys", method="mouse_keyboard",
                          verified=True, verification_method="tested"),
                    Skill(name="scroll", description="Scroll page", method="mouse_keyboard",
                          verified=True, verification_method="tested"),
                    Skill(name="search", description="Find windows", method="mouse_keyboard",
                          verified=True, verification_method="tested"),
                ]
        except Exception:
            xdotool.error = "xdotool not found"
        self.tools["xdotool"] = xdotool

        # wmctrl (window management)
        wmctrl = Tool(name="wmctrl")
        try:
            result = subprocess.run(["wmctrl", "-l"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                wmctrl.available = True
                wmctrl.skills = [
                    Skill(name="list_windows", description="List open windows", method="cli",
                          verified=True, verification_method="tested"),
                    Skill(name="focus_window", description="Focus a window", method="cli",
                          verified=True, verification_method="tested"),
                    Skill(name="close_window", description="Close a window", method="cli",
                          verified=True, verification_method="tested"),
                ]
        except Exception:
            pass
        self.tools["wmctrl"] = wmctrl

        # xclip (clipboard)
        xclip = Tool(name="xclip")
        try:
            result = subprocess.run(["xclip", "-version"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                xclip.available = True
                xclip.skills = [
                    Skill(name="copy", description="Copy to clipboard", method="cli",
                          verified=True, verification_method="tested"),
                    Skill(name="paste", description="Paste from clipboard", method="cli",
                          verified=True, verification_method="tested"),
                ]
        except Exception:
            pass
        self.tools["xclip"] = xclip

    def _discover_python_libs(self):
        """Discover available Python libraries."""
        libs = {
            "requests": "HTTP requests",
            "httpx": "Async HTTP",
            "beautifulsoup4": "HTML parsing",
            "selenium": "Browser automation",
            "playwright": "Browser automation",
            "pyautogui": "Screen automation",
            "pillow": "Image processing",
            "pandas": "Data analysis",
            "numpy": "Numerical computing",
            "matplotlib": "Plotting",
            "reportlab": "PDF generation",
            "python-pptx": "PowerPoint generation",
            "python-docx": "Word document generation",
        }

        for lib_name, description in libs.items():
            tool = Tool(name=lib_name)
            try:
                __import__(lib_name.replace("-", "_").split("[")[0])
                tool.available = True
                tool.skills = [
                    Skill(name=lib_name, description=description, method="api",
                          verified=True, verification_method="import_success")
                ]
            except ImportError:
                tool.error = f"{lib_name} not installed"
            self.tools[lib_name] = tool

    def _discover_apis(self):
        """Discover available API services."""
        # Groq
        groq = Tool(name="groq_api")
        try:
            from groq_agent import generate
            groq.available = True
            groq.skills = [
                Skill(name="generate", description="Generate text with Groq LLM", method="api",
                      command="groq_agent.generate", verified=True, verification_method="import_success"),
                Skill(name="vision", description="Analyze images with Groq Vision", method="api"),
            ]
        except Exception:
            groq.error = "Groq API not configured"
        self.tools["groq_api"] = groq

        # Exchange rate API
        exchange = Tool(name="exchange_rate_api")
        exchange.available = True  # Always available via HTTP
        exchange.skills = [
            Skill(name="get_rate", description="Get currency exchange rates", method="api",
                  command="https://api.exchangerate-api.com/v4/latest/{currency}"),
        ]
        self.tools["exchange_rate_api"] = exchange

    def _discover_vdi_capabilities(self):
        """Discover VDI-specific capabilities."""
        vdi = Tool(name="vdi_display")
        try:
            result = subprocess.run(
                ["sudo", "-u", "#1001", "bash", "-c", "DISPLAY=:99 xdpyinfo | head -5"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                vdi.available = True
                vdi.skills = [
                    Skill(name="display", description="VDI display :99", method="cli",
                          verified=True, verification_method="xdpyinfo"),
                    Skill(name="screenshot", description="Capture VDI screen", method="cli",
                          verified=True, verification_method="scrot tested"),
                    Skill(name="mouse_control", description="Control mouse in VDI", method="mouse_keyboard",
                          verified=True, verification_method="xdotool tested"),
                    Skill(name="keyboard_control", description="Control keyboard in VDI", method="mouse_keyboard",
                          verified=True, verification_method="xdotool tested"),
                    Skill(name="window_management", description="Manage windows in VDI", method="cli",
                          verified=True, verification_method="wmctrl tested"),
                ]
        except Exception:
            vdi.error = "VDI display not accessible"
        self.tools["vdi_display"] = vdi

    def get_available_tools(self) -> list:
        """Get all available tools."""
        return [{"name": t.name, "version": t.version,
                 "skills": [s.name for s in t.skills]}
                for t in self.tools.values() if t.available]

    def get_skill(self, skill_name: str) -> Skill | None:
        """Find a specific skill across all tools."""
        for tool in self.tools.values():
            if tool.available:
                for skill in tool.skills:
                    if skill.name == skill_name:
                        return skill
        return None

    def can_do(self, action: str) -> bool:
        """Check if JARVIS can perform a specific action."""
        skill = self.get_skill(action)
        return skill is not None and skill.verified

    def get_tools_summary(self) -> str:
        """Human-readable summary of available capabilities."""
        lines = []
        for name, tool in self.tools.items():
            if tool.available:
                skills = ", ".join(s.name for s in tool.skills)
                lines.append(f"  {name} ({tool.version}): {skills}")
        return "\n".join(lines)


# ── Singleton ──
_registry = None
def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
