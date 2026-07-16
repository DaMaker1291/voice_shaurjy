"""
JARVIS MCP Server Registry
Auto-discovers installed MCP servers, manages configuration,
and provides a unified interface for the MCP client daemon.
"""
import json
import os
import subprocess
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

log = logging.getLogger("jarvis-mcp-registry")


# ── Well-known MCP servers ──────────────────────────────────────────────
KNOWN_MCP_SERVERS = {
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "description": "Local filesystem access",
        "tags": ["files", "local"],
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        "description": "GitHub API integration",
        "tags": ["git", "code", "remote"],
    },
    "postgres": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "env": {"DATABASE_URL": "${DATABASE_URL}"},
        "description": "PostgreSQL database access",
        "tags": ["database", "sql"],
    },
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite"],
        "description": "SQLite database access",
        "tags": ["database", "sql", "local"],
    },
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        "description": "Brave Search API",
        "tags": ["search", "web"],
    },
    "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Knowledge graph memory",
        "tags": ["memory", "knowledge"],
    },
    "puppeteer": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "description": "Browser automation via Puppeteer",
        "tags": ["browser", "web", "automation"],
    },
    "fetch": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "description": "HTTP fetch and web scraping",
        "tags": ["web", "http"],
    },
    "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "description": "Structured reasoning and planning",
        "tags": ["reasoning", "planning"],
    },
    "git": {
        "command": "uvx",
        "args": ["mcp-server-git", "--repository", "."],
        "description": "Git repository operations",
        "tags": ["git", "code"],
    },
    "docker": {
        "command": "uvx",
        "args": ["mcp-server-docker"],
        "description": "Docker container management",
        "tags": ["docker", "containers"],
    },
    "kubernetes": {
        "command": "uvx",
        "args": ["mcp-server-kubernetes"],
        "description": "Kubernetes cluster management",
        "tags": ["k8s", "cloud"],
    },
    "aws": {
        "command": "uvx",
        "args": ["mcp-server-aws"],
        "description": "AWS service integration",
        "tags": ["aws", "cloud"],
    },
    "gdrive": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gdrive"],
        "env": {"GOOGLE_CLIENT_ID": "${GOOGLE_CLIENT_ID}", "GOOGLE_CLIENT_SECRET": "${GOOGLE_CLIENT_SECRET}"},
        "description": "Google Drive integration",
        "tags": ["google", "files", "cloud"],
    },
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
        "description": "Slack workspace integration",
        "tags": ["slack", "messaging"],
    },
}


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
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", os.path.expanduser("~")],
                    "description": "Access your home directory",
                    "tags": ["files", "local"],
                },
                "fetch": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-fetch"],
                    "description": "Fetch web pages and APIs",
                    "tags": ["web", "http"],
                },
                "sequential-thinking": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                    "description": "Structured reasoning",
                    "tags": ["reasoning"],
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


# ── Singleton ────────────────────────────────────────────────────────────
_registry: Optional[MCPServerRegistry] = None


def get_registry() -> MCPServerRegistry:
    global _registry
    if _registry is None:
        _registry = MCPServerRegistry()
    return _registry
