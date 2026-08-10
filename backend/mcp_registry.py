"""
JARVIS MCP Server Registry + System Capability Auto-Discovery

Discovers installed MCP servers, CLI tools, system capabilities,
and available applications — so the AI knows what it can use at runtime.
"""
import json
import os
import subprocess
import sys
import shutil
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

log = logging.getLogger("jarvis-mcp-registry")


# ── Well-known MCP servers ──────────────────────────────────────────────
# Python-based servers (no Node.js required)
# Only include servers that are actually installed
KNOWN_MCP_SERVERS = {}

def _init_known_servers():
    """Initialize known servers based on what's actually installed."""
    import importlib

    # Check and add each server
    servers_to_check = [
        ("fetch", ["-m", "mcp_server_fetch"], ["web", "http"], "HTTP fetch and web scraping"),
        ("git", ["-m", "mcp_server_git"], ["git", "code"], "Git repository operations"),
        ("sqlite", ["-c", "from mcp_server_sqlite.server import main; main()"], ["database", "sql"], "SQLite database access"),
    ]

    for name, args, tags, desc in servers_to_check:
        try:
            importlib.import_module(f"mcp_server_{name}" if name != "sqlite" else "mcp_server_sqlite")
            KNOWN_MCP_SERVERS[name] = {
                "command": sys.executable,
                "args": args,
                "description": desc,
                "tags": tags,
            }
        except ImportError:
            pass

    # Filesystem needs special handling
    try:
        importlib.import_module("mcp_server_filesystem")
        KNOWN_MCP_SERVERS["filesystem"] = {
            "command": sys.executable,
            "args": ["-m", "mcp_server_filesystem", os.path.expanduser("~")],
            "description": "Local filesystem access",
            "tags": ["files", "local"],
        }
    except ImportError:
        pass

_init_known_servers()

# Servers requiring API keys — only include if keys are set
def _add_key_servers():
    """Add servers that need API keys only if keys exist."""
    if os.environ.get("GITHUB_TOKEN"):
        KNOWN_MCP_SERVERS["github"] = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            "description": "GitHub API integration",
            "tags": ["git", "code", "remote"],
        }
    if os.environ.get("BRAVE_API_KEY"):
        KNOWN_MCP_SERVERS["brave-search"] = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
            "description": "Brave Search API",
            "tags": ["search", "web"],
        }

_add_key_servers()


class MCPServerRegistry:
    """
    Discovers and manages MCP server configurations.
    
    Sources:
    1. Well-known servers (built-in list)
    2. Claude Desktop config (~/.claude/claude_desktop_config.json)
    3. VS Code MCP config (.vscode/mcp.json)
    4. Custom JARVIS config (~/.jarvis/mcp.json)
    """

    def __init__(self):
        self.configs: Dict[str, Dict[str, Any]] = {}
        self._discover()

    def _discover(self):
        """Discover MCP servers from all known sources."""
        # 1. Claude Desktop config
        self._load_claude_desktop()

        # 2. VS Code MCP config
        self._load_vscode()

        # 3. JARVIS custom config
        self._load_jarvis_config()

        log.info(f"Discovered {len(self.configs)} MCP server configurations")

    def _load_claude_desktop(self):
        """Load from Claude Desktop's config file."""
        if os.name == "nt":
            config_path = os.path.expandvars(
                r"%APPDATA%\Claude\claude_desktop_config.json"
            )
        else:
            config_path = os.path.expanduser(
                "~/Library/Application Support/Claude/claude_desktop_config.json"
            )

        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            for name, server in data.get("mcpServers", {}).items():
                if name not in self.configs:
                    self.configs[name] = {
                        "source": "claude-desktop",
                        "transport": "stdio",
                        "command": server.get("command"),
                        "args": server.get("args", []),
                        "env": server.get("env"),
                        "cwd": server.get("cwd"),
                    }
                    log.info(f"Loaded MCP server from Claude Desktop: {name}")
        except Exception as e:
            log.warning(f"Failed to load Claude Desktop config: {e}")

    def _load_vscode(self):
        """Load from VS Code's MCP config."""
        vscode_paths = [
            ".vscode/mcp.json",
            os.path.expanduser("~/.config/Code/User/mcp.json"),
        ]

        for config_path in vscode_paths:
            if not os.path.exists(config_path):
                continue

            try:
                with open(config_path, "r") as f:
                    data = json.load(f)

                for name, server in data.get("servers", {}).items():
                    if name not in self.configs:
                        self.configs[name] = {
                            "source": "vscode",
                            "transport": server.get("type", "stdio"),
                            "command": server.get("command"),
                            "args": server.get("args", []),
                            "env": server.get("env"),
                            "url": server.get("url"),
                        }
                        log.info(f"Loaded MCP server from VS Code: {name}")
            except Exception as e:
                log.warning(f"Failed to load VS Code config: {e}")

    def _load_jarvis_config(self):
        """Load from JARVIS's own MCP config."""
        config_path = os.path.join(
            os.path.expanduser("~"), ".jarvis", "mcp.json"
        )

        if not os.path.exists(config_path):
            # Create default config
            self._create_default_config(config_path)
            return

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            for name, server in data.get("mcpServers", {}).items():
                if name not in self.configs:
                    self.configs[name] = {
                        "source": "jarvis",
                        "transport": server.get("transport", "stdio"),
                        "command": server.get("command"),
                        "args": server.get("args", []),
                        "env": server.get("env"),
                        "url": server.get("url"),
                        "description": server.get("description", ""),
                        "tags": server.get("tags", []),
                    }
                    log.info(f"Loaded MCP server from JARVIS config: {name}")
        except Exception as e:
            log.warning(f"Failed to load JARVIS config: {e}")

    def _create_default_config(self, config_path: str):
        """Create a default JARVIS MCP config with useful servers."""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        default = {
            "mcpServers": {
                "fetch": {
                    "command": sys.executable,
                    "args": ["-m", "mcp_server_fetch"],
                    "description": "Fetch web pages and APIs",
                    "tags": ["web", "http"],
                },
                "git": {
                    "command": sys.executable,
                    "args": ["-m", "mcp_server_git"],
                    "description": "Git operations",
                    "tags": ["git", "code"],
                },
                "sqlite": {
                    "command": sys.executable,
                    "args": ["-c", "from mcp_server_sqlite.server import main; main()"],
                    "description": "SQLite database",
                    "tags": ["database", "sql"],
                },
            }
        }
        with open(config_path, "w") as f:
            json.dump(default, f, indent=2)
        log.info(f"Created default MCP config: {config_path}")

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Return all discovered server configurations."""
        return self.configs

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self.configs.get(name)

    def add_server(self, name: str, config: Dict[str, Any]):
        """Add a custom MCP server configuration."""
        self.configs[name] = config

        # Persist to JARVIS config
        config_path = os.path.join(
            os.path.expanduser("~"), ".jarvis", "mcp.json"
        )
        existing = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                existing = json.load(f)

        existing.setdefault("mcpServers", {})[name] = config
        with open(config_path, "w") as f:
            json.dump(existing, f, indent=2)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search servers by name, description, or tags."""
        results = []
        query_lower = query.lower()
        for name, config in self.configs.items():
            if (
                query_lower in name.lower()
                or query_lower in config.get("description", "").lower()
                or any(query_lower in tag for tag in config.get("tags", []))
            ):
                results.append({"name": name, **config})
        return results

    def get_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Get all servers with a specific tag."""
        return [
            {"name": name, **config}
            for name, config in self.configs.items()
            if tag in config.get("tags", [])
        ]

    def get_working(self) -> Dict[str, Dict[str, Any]]:
        """Return only servers whose commands are actually available."""
        import shutil
        working = {}
        for name, config in self.configs.items():
            cmd = config.get("command", "")
            # Check if command exists
            if cmd == sys.executable or cmd.endswith("python") or cmd.endswith("python3"):
                working[name] = config  # Python is always available
            elif shutil.which(cmd):
                working[name] = config
            else:
                log.debug(f"[MCP] Skipping {name}: command '{cmd}' not found")
        return working


# ── Singleton ────────────────────────────────────────────────────────────
_registry: Optional[MCPServerRegistry] = None


def get_registry() -> MCPServerRegistry:
    global _registry
    if _registry is None:
        _registry = MCPServerRegistry()
    return _registry


# ════════════════════════════════════════════════════════════════════════════
# System Capability Auto-Discovery
# ════════════════════════════════════════════════════════════════════════════

# CLI tools and what they can do
KNOWN_TOOLS = {
    "ffmpeg": {"tags": ["video", "audio", "media"], "desc": "Video/audio encoding, conversion, effects"},
    "blender": {"tags": ["3d", "cad", "animation", "render"], "desc": "3D modeling, animation, rendering"},
    "git": {"tags": ["git", "code", "version"], "desc": "Git version control"},
    "node": {"tags": ["javascript", "npm", "web"], "desc": "Node.js runtime"},
    "npx": {"tags": ["npm", "packages"], "desc": "Run npm packages"},
    "python": {"tags": ["python", "scripting"], "desc": "Python interpreter"},
    "pip": {"tags": ["python", "packages"], "desc": "Python package manager"},
    "choco": {"tags": ["windows", "packages"], "desc": "Chocolatey package manager"},
    "winget": {"tags": ["windows", "packages"], "desc": "Windows Package Manager"},
    "curl": {"tags": ["web", "http"], "desc": "HTTP requests"},
    "wget": {"tags": ["web", "download"], "desc": "File download"},
    "docker": {"tags": ["containers", "devops"], "desc": "Container management"},
    "ssh": {"tags": ["remote", "server"], "desc": "SSH remote access"},
    "rsync": {"tags": ["sync", "files"], "desc": "File synchronization"},
    "magick": {"tags": ["image", "convert"], "desc": "ImageMagick image processing"},
    "convert": {"tags": ["image", "convert"], "desc": "ImageMagick image conversion"},
    "tesseract": {"tags": ["ocr", "text"], "desc": "Tesseract OCR engine"},
    "pandoc": {"tags": ["document", "convert"], "desc": "Document format conversion"},
}

# Applications with COM automation or CLI interfaces
KNOWN_APPS = {
    "chrome": {"clsid": "Chrome.Application", "cli": ["chrome.exe"], "tags": ["browser", "web"]},
    "firefox": {"cli": ["firefox.exe"], "tags": ["browser", "web"]},
    "code": {"clsid": None, "cli": ["code.exe"], "tags": ["editor", "ide"]},
    "notepad": {"cli": ["notepad.exe"], "tags": ["editor", "text"]},
    "excel": {"clsid": "Excel.Application", "cli": ["excel.exe"], "tags": ["spreadsheet", "data"]},
    "winword": {"clsid": "Word.Application", "cli": ["winword.exe"], "tags": ["document", "word"]},
    "powerpnt": {"clsid": "PowerPoint.Application", "cli": ["powerpnt.exe"], "tags": ["presentation", "slides"]},
    "outlook": {"clsid": "Outlook.Application", "cli": ["outlook.exe"], "tags": ["email", "calendar"]},
    "onenote": {"clsid": "OneNote.Application", "cli": ["onenote.exe"], "tags": ["notes", "onenote"]},
    "explorer": {"cli": ["explorer.exe"], "tags": ["files", "explorer"]},
    "mspaint": {"cli": ["mspaint.exe"], "tags": ["image", "paint"]},
    "calc": {"cli": ["calc.exe"], "tags": ["calculator"]},
    "teams": {"cli": ["Teams.exe"], "tags": ["chat", "meeting"]},
    "whatsapp": {"cli": [], "tags": ["messaging", "chat"]},
    "spotify": {"cli": ["Spotify.exe"], "tags": ["music", "audio"]},
    "obs": {"cli": ["obs64.exe", "obs32.exe"], "tags": ["streaming", "recording"]},
    "capcut": {"cli": ["CapCut.exe"], "tags": ["video", "editing"]},
    "davinciresolve": {"cli": ["DaVinciResolve.exe"], "tags": ["video", "editing", "color"]},
    "blender": {"cli": ["blender.exe"], "tags": ["3d", "animation", "render"]},
    "fusion360": {"cli": ["Fusion360.exe"], "tags": ["cad", "3d", "engineering"]},
    "gimp": {"cli": ["gimp.exe"], "tags": ["image", "editing"]},
    "inkscape": {"cli": ["inkscape.exe"], "tags": ["vector", "svg"]},
}


class SystemCapabilityDiscovery:
    """Auto-discovers available tools, apps, and capabilities at boot.
    
    Scans PATH for CLI tools, checks for installed apps via registry/shortcuts,
    and reports what the AI can use for any task.
    """

    def __init__(self):
        self._tools: Dict[str, Dict] = {}
        self._apps: Dict[str, Dict] = {}
        self._python_modules: Dict[str, bool] = {}
        self._discovered = False

    def discover(self) -> Dict:
        """Run full discovery. Returns summary of available capabilities."""
        if self._discovered:
            return self.get_summary()

        # Discover CLI tools
        for tool, info in KNOWN_TOOLS.items():
            path = shutil.which(tool)
            if path:
                self._tools[tool] = {"path": path, **info}

        # Discover installed apps
        for app, info in KNOWN_APPS.items():
            found = False
            for cli in info.get("cli", []):
                if shutil.which(cli) or self._app_running(cli):
                    found = True
                    break
            if found:
                self._apps[app] = info

        # Discover Python modules
        important_modules = [
            "pyautogui", "pyperclip", "uiautomation", "cv2", "numpy",
            "pandas", "yfinance", "requests", "flask", "fastapi",
            "pyttsx3", "speech_recognition", "openai", "groq",
            "bs4", "selenium", "playwright", "mss", "PIL",
            "pptx", "openpyxl", "docx", "fitz", "csv",
            "webbrowser", "smtplib", "imaplib", "email",
            "psutil", "socket", "http.server", "xmlrpc",
        ]
        for mod in important_modules:
            try:
                __import__(mod)
                self._python_modules[mod] = True
            except ImportError:
                self._python_modules[mod] = False

        self._discovered = True
        return self.get_summary()

    def get_summary(self) -> Dict:
        """Get a summary of all discovered capabilities."""
        return {
            "tools": {k: v for k, v in self._tools.items()},
            "apps": {k: v for k, v in self._apps.items()},
            "python_modules": {k: v for k, v in self._python_modules.items() if v},
            "tool_count": len(self._tools),
            "app_count": len(self._apps),
            "module_count": sum(1 for v in self._python_modules.values() if v),
        }

    def can_do(self, capability: str) -> Dict:
        """Check if a specific capability is available.
        
        Args:
            capability: Tag like "video", "3d", "email", "ocr", etc.
        
        Returns:
            Dict with available tools/apps/modules for that capability.
        """
        if not self._discovered:
            self.discover()

        result = {"tools": [], "apps": [], "modules": []}

        for name, info in self._tools.items():
            if capability in info.get("tags", []):
                result["tools"].append(name)

        for name, info in self._apps.items():
            if capability in info.get("tags", []):
                result["apps"].append(name)

        for mod, available in self._python_modules.items():
            if available and capability in mod.lower():
                result["modules"].append(mod)

        return result

    def get_for_task(self, task_description: str) -> Dict:
        """Given a task description, report what's available to accomplish it.
        
        Uses simple keyword matching to determine relevant capabilities.
        """
        if not self._discovered:
            self.discover()

        task_lower = task_description.lower()
        relevant = {"tools": [], "apps": [], "modules": [], "suggestions": []}

        # Match task keywords to capabilities
        keyword_map = {
            "video": ["ffmpeg", "capcut", "davinciresolve", "obs"],
            "3d": ["blender", "fusion360"],
            "animation": ["blender", "ffmpeg"],
            "render": ["blender", "ffmpeg"],
            "image": ["magick", "convert", "gimp", "inkscape", "mspaint", "cv2", "PIL"],
            "document": ["pandoc", "winword", "powerpnt", "docx", "pptx"],
            "email": ["outlook", "smtplib", "imaplib"],
            "browser": ["chrome", "firefox", "selenium", "playwright"],
            "code": ["git", "node", "python", "code"],
            "data": ["python", "excel", "pandas", "csv"],
            "ocr": ["tesseract", "cv2"],
            "audio": ["ffmpeg", "spotify", "pyttsx3"],
            "messaging": ["whatsapp", "teams"],
            "files": ["explorer", "rsync"],
            "web": ["curl", "wget", "requests", "bs4", "selenium", "playwright"],
        }

        for keyword, capabilities in keyword_map.items():
            if keyword in task_lower:
                for cap in capabilities:
                    if cap in self._tools:
                        relevant["tools"].append(cap)
                    if cap in self._apps:
                        relevant["apps"].append(cap)
                    for mod in self._python_modules:
                        if cap in mod and self._python_modules[mod]:
                            relevant["modules"].append(mod)

        return relevant

    def _app_running(self, process_name: str) -> bool:
        """Check if an app is currently running."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                capture_output=True, text=True, timeout=3
            )
            return process_name.lower() in result.stdout.lower()
        except Exception:
            return False


# ── Singleton ────────────────────────────────────────────────────────────
_system: Optional[SystemCapabilityDiscovery] = None

def get_system() -> SystemCapabilityDiscovery:
    global _system
    if _system is None:
        _system = SystemCapabilityDiscovery()
    return _system

def discover_system() -> Dict:
    """One-call: discover all system capabilities."""
    return get_system().discover()

def can_do(capability: str) -> Dict:
    """Check what's available for a capability."""
    return get_system().can_do(capability)

def get_for_task(task: str) -> Dict:
    """Get available tools/apps for a specific task."""
    return get_system().get_for_task(task)
