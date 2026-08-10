"""CLI Application Adapter — Shell/CLI control for any application.

Uses command-line interfaces to control applications.
This is the universal fallback when no API or accessibility is available.

Execution ladder position: #3 (CLI)
"""

from __future__ import annotations

import os
import subprocess
import logging
from typing import Optional, List

log = logging.getLogger("adapter.cli")


class CliApplicationAdapter:
    """Control applications via their CLI interfaces."""

    # Known CLI commands for common apps
    CLI_COMMANDS = {
        "git": {"binary": "git", "version_cmd": ["git", "--version"]},
        "python": {"binary": "python3", "alt_binary": "python", "version_cmd": ["python3", "--version"]},
        "node": {"binary": "node", "version_cmd": ["node", "--version"]},
        "npm": {"binary": "npm", "version_cmd": ["npm", "--version"]},
        "ffmpeg": {"binary": "ffmpeg", "version_cmd": ["ffmpeg", "-version"]},
        "docker": {"binary": "docker", "version_cmd": ["docker", "--version"]},
        "code": {"binary": "code", "version_cmd": ["code", "--version"]},
    }

    def __init__(self):
        self._available = {}
        self._discover()

    def _discover(self):
        """Discover which CLI tools are available."""
        for name, config in self.CLI_COMMANDS.items():
            try:
                result = subprocess.run(
                    config["version_cmd"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self._available[name] = config
            except Exception:
                # Try alt binary
                if "alt_binary" in config:
                    try:
                        result = subprocess.run(
                            [config["alt_binary"], "--version"],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            self._available[name] = config
                    except Exception:
                        pass

    def is_available(self) -> bool:
        """CLI is always available."""
        return True

    def can_handle(self, app_name: str) -> bool:
        """Check if we have a CLI for this app."""
        return app_name.lower() in self._available

    def launch(self, app_name: str, args: List[str] = None):
        """Launch via CLI."""
        from capability_fabric import FabricResult
        config = self._available.get(app_name.lower())
        if not config:
            return FabricResult(ok=False, error=f"No CLI for {app_name}")
        try:
            cmd = [config["binary"]] + (args or [])
            subprocess.Popen(cmd)
            return FabricResult(ok=True, method="cli", output=f"Launched {app_name}")
        except Exception as e:
            return FabricResult(ok=False, error=str(e))

    def execute_in_app(self, app_name: str, command: str):
        """Execute a CLI command for an app."""
        from capability_fabric import FabricResult
        config = self._available.get(app_name.lower())
        if not config:
            return FabricResult(ok=False, error=f"No CLI for {app_name}")
        try:
            result = subprocess.run(
                [config["binary"]] + command.split(),
                capture_output=True, text=True, timeout=30
            )
            return FabricResult(
                ok=result.returncode == 0,
                data=result.stdout,
                error=result.stderr,
                method="cli",
            )
        except Exception as e:
            return FabricResult(ok=False, error=str(e))

    def get_app_state(self, app_name: str):
        """Get app state via CLI (e.g., git status)."""
        from capability_fabric import FabricResult
        if app_name.lower() == "git":
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, timeout=5
                )
                return FabricResult(ok=True, data=result.stdout, method="git_cli")
            except Exception as e:
                return FabricResult(ok=False, error=str(e))
        return FabricResult(ok=False, error=f"No state command for {app_name}")

    def close(self, app_name: str):
        """Close via CLI (best effort)."""
        from capability_fabric import FabricResult
        try:
            subprocess.run(["pkill", app_name], capture_output=True, timeout=5)
            return FabricResult(ok=True, method="pkill")
        except Exception as e:
            return FabricResult(ok=False, error=str(e))

    def run_shell(self, command: str, timeout: int = 30):
        """Run an arbitrary shell command."""
        from capability_fabric import FabricResult
        try:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=timeout
            )
            return FabricResult(
                ok=result.returncode == 0,
                data=result.stdout,
                error=result.stderr,
                method="shell",
            )
        except Exception as e:
            return FabricResult(ok=False, error=str(e))
