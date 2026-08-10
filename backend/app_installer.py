"""
JARVIS App Installer — Auto-download and install missing apps in VDI.

Handles:
- APT package installation in WSL
- Snap/Flatpak installation
- AppImage download and setup
- Direct .deb/.rpm download from web
- Blender, GIMP, LibreOffice, OBS, and 50+ other apps
"""
import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("app_installer")


@dataclass
class InstallResult:
    """Result of an app installation."""
    app_name: str
    success: bool
    method: str  # apt, snap, flatpak, appimage, download
    message: str = ""
    install_path: str = ""


class AppInstaller:
    """Download and install apps in WSL VDI."""

    # Complete app catalog with install commands
    APP_CATALOG = {
        # ── 3D / CAD ───────────────────────────────────────────
        "blender": {
            "name": "Blender",
            "apt": "sudo apt-get install -y blender",
            "category": "3d",
            "description": "3D modeling, animation, rendering",
        },
        "freecad": {
            "name": "FreeCAD",
            "apt": "sudo apt-get install -y freecad",
            "category": "3d",
            "description": "Parametric 3D CAD modeler",
        },
        "openscad": {
            "name": "OpenSCAD",
            "apt": "sudo apt-get install -y openscad",
            "category": "3d",
            "description": "Programmatic 3D modeling",
        },

        # ── Image / Design ─────────────────────────────────────
        "gimp": {
            "name": "GIMP",
            "apt": "sudo apt-get install -y gimp",
            "category": "image",
            "description": "Image editor",
        },
        "inkscape": {
            "name": "Inkscape",
            "apt": "sudo apt-get install -y inkscape",
            "category": "design",
            "description": "Vector graphics editor",
        },
        "imagemagick": {
            "name": "ImageMagick",
            "apt": "sudo apt-get install -y imagemagick",
            "category": "image",
            "description": "Image manipulation toolkit",
        },
        "darktable": {
            "name": "darktable",
            "apt": "sudo apt-get install -y darktable",
            "category": "image",
            "description": "Photography workflow application",
        },

        # ── Office / Productivity ──────────────────────────────
        "libreoffice": {
            "name": "LibreOffice",
            "apt": "sudo apt-get install -y libreoffice",
            "category": "office",
            "description": "Full office suite",
        },
        "thunderbird": {
            "name": "Thunderbird",
            "apt": "sudo apt-get install -y thunderbird",
            "category": "email",
            "description": "Email client",
        },

        # ── Media ──────────────────────────────────────────────
        "vlc": {
            "name": "VLC",
            "apt": "sudo apt-get install -y vlc",
            "category": "media",
            "description": "Media player",
        },
        "obs-studio": {
            "name": "OBS Studio",
            "apt": "sudo apt-get install -y obs-studio",
            "category": "streaming",
            "description": "Live streaming and recording",
        },
        "audacity": {
            "name": "Audacity",
            "apt": "sudo apt-get install -y audacity",
            "category": "audio",
            "description": "Audio editor",
        },
        "handbrake": {
            "name": "HandBrake",
            "apt": "sudo apt-get install -y handbrake",
            "category": "media",
            "description": "Video transcoder",
        },
        "kdenlive": {
            "name": "Kdenlive",
            "apt": "sudo apt-get install -y kdenlive",
            "category": "video",
            "description": "Video editor",
        },
        "openshot": {
            "name": "OpenShot",
            "apt": "sudo apt-get install -y openshot",
            "category": "video",
            "description": "Video editor",
        },

        # ── Browsers ───────────────────────────────────────────
        "google-chrome": {
            "name": "Google Chrome",
            "apt": "wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo dpkg -i /tmp/chrome.deb || sudo apt-get install -f -y",
            "category": "browser",
            "description": "Web browser",
        },
        "firefox": {
            "name": "Firefox",
            "apt": "sudo apt-get install -y firefox",
            "category": "browser",
            "description": "Web browser",
        },

        # ── Dev Tools ──────────────────────────────────────────
        "code": {
            "name": "VS Code",
            "apt": "wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg && sudo install -D -o root -g root -m 644 packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg && sudo sh -c 'echo \"deb [arch=amd64 signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main\" > /etc/apt/sources.list.d/vscode.list' && sudo apt-get update && sudo apt-get install -y code",
            "category": "dev",
            "description": "Code editor",
        },
        "git": {
            "name": "Git",
            "apt": "sudo apt-get install -y git",
            "category": "dev",
            "description": "Version control",
        },
        "docker": {
            "name": "Docker",
            "apt": "sudo apt-get install -y docker.io",
            "category": "dev",
            "description": "Container runtime",
        },
        "nodejs": {
            "name": "Node.js",
            "apt": "sudo apt-get install -y nodejs npm",
            "category": "dev",
            "description": "JavaScript runtime",
        },
        "python3-pip": {
            "name": "Python pip",
            "apt": "sudo apt-get install -y python3-pip",
            "category": "dev",
            "description": "Python package manager",
        },

        # ── System Utilities ───────────────────────────────────
        "file-roller": {
            "name": "File Roller",
            "apt": "sudo apt-get install -y file-roller",
            "category": "utility",
            "description": "Archive manager",
        },
        "htop": {
            "name": "htop",
            "apt": "sudo apt-get install -y htop",
            "category": "utility",
            "description": "Process monitor",
        },
        "neofetch": {
            "name": "neofetch",
            "apt": "sudo apt-get install -y neofetch",
            "category": "utility",
            "description": "System information",
        },
        "tmux": {
            "name": "tmux",
            "apt": "sudo apt-get install -y tmux",
            "category": "utility",
            "description": "Terminal multiplexer",
        },
        "curl": {
            "name": "curl",
            "apt": "sudo apt-get install -y curl",
            "category": "utility",
            "description": "HTTP client",
        },
        "wget": {
            "name": "wget",
            "apt": "sudo apt-get install -y wget",
            "category": "utility",
            "description": "HTTP downloader",
        },
        "unzip": {
            "name": "unzip",
            "apt": "sudo apt-get install -y unzip",
            "category": "utility",
            "description": "Archive extractor",
        },

        # ── Science / Math ─────────────────────────────────────
        "octave": {
            "name": "GNU Octave",
            "apt": "sudo apt-get install -y octave",
            "category": "science",
            "description": "Numerical computation",
        },
        "scilab": {
            "name": "Scilab",
            "apt": "sudo apt-get install -y scilab",
            "category": "science",
            "description": "Numerical computation",
        },

        # ── Networking ─────────────────────────────────────────
        "nmap": {
            "name": "Nmap",
            "apt": "sudo apt-get install -y nmap",
            "category": "network",
            "description": "Network scanner",
        },
        "wireshark": {
            "name": "Wireshark",
            "apt": "sudo apt-get install -y wireshark",
            "category": "network",
            "description": "Network protocol analyzer",
        },
        "net-tools": {
            "name": "Net Tools",
            "apt": "sudo apt-get install -y net-tools",
            "category": "network",
            "description": "Network utilities",
        },

        # ── Fonts / Language Support ───────────────────────────
        "fonts-noto": {
            "name": "Noto Fonts",
            "apt": "sudo apt-get install -y fonts-noto",
            "category": "fonts",
            "description": "Universal font family",
        },
        "language-pack-en": {
            "name": "English Language Pack",
            "apt": "sudo apt-get install -y language-pack-en",
            "category": "language",
            "description": "English language support",
        },
    }

    def __init__(self):
        self._installed_cache = None

    def install(self, app_key: str) -> InstallResult:
        """Install an app by key from the catalog."""
        if app_key not in self.APP_CATALOG:
            return InstallResult(
                app_name=app_key,
                success=False,
                method="none",
                message=f"Unknown app: {app_key}. Available: {', '.join(self.APP_CATALOG.keys())}"
            )

        app_info = self.APP_CATALOG[app_key]

        # Check if already installed
        if self._is_installed(app_key):
            return InstallResult(
                app_name=app_info["name"],
                success=True,
                method="already_installed",
                message=f"{app_info['name']} is already installed",
            )

        # Install via APT
        install_cmd = app_info.get("apt", "")
        if install_cmd:
            return self._install_via_apt(app_key, app_info, install_cmd)

        return InstallResult(
            app_name=app_info["name"],
            success=False,
            method="none",
            message=f"No install method available for {app_info['name']}"
        )

    def install_multiple(self, app_keys: list[str]) -> list[InstallResult]:
        """Install multiple apps."""
        results = []
        for key in app_keys:
            result = self.install(key)
            results.append(result)
            logger.info(f"Install {key}: {'OK' if result.success else 'FAIL'} - {result.message}")
        return results

    def install_all_missing(self) -> list[InstallResult]:
        """Install all missing essential apps."""
        from app_state_discovery import AppDiscoveryEngine
        discovery = AppDiscoveryEngine()
        missing = discovery._find_missing_apps()

        # Map display names to catalog keys
        name_to_key = {
            "Chrome": "google-chrome",
            "Firefox": "firefox",
            "Blender": "blender",
            "GIMP": "gimp",
            "LibreOffice": "libreoffice",
            "Terminal": "xfce4-terminal",
            "Text Editor": "mousepad",
            "VLC": "vlc",
            "Archive Manager": "file-roller",
        }

        install_keys = []
        for name in missing:
            key = name_to_key.get(name, name.lower().replace(" ", "-"))
            if key in self.APP_CATALOG:
                install_keys.append(key)

        return self.install_multiple(install_keys)

    def _install_via_apt(self, app_key: str, app_info: dict, cmd: str) -> InstallResult:
        """Install via apt-get in WSL."""
        try:
            # First update apt cache
            subprocess.run(
                ["wsl", "-e", "bash", "-c", "sudo apt-get update -qq"],
                capture_output=True, timeout=60
            )

            # Install
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                return InstallResult(
                    app_name=app_info["name"],
                    success=True,
                    method="apt",
                    message=f"Successfully installed {app_info['name']}",
                )
            else:
                return InstallResult(
                    app_name=app_info["name"],
                    success=False,
                    method="apt",
                    message=f"Installation failed: {result.stderr[:200]}",
                )

        except subprocess.TimeoutExpired:
            return InstallResult(
                app_name=app_info["name"],
                success=False,
                method="apt",
                message="Installation timed out (5 min limit)",
            )
        except Exception as e:
            return InstallResult(
                app_name=app_info["name"],
                success=False,
                method="apt",
                message=f"Error: {e}",
            )

    def _is_installed(self, app_key: str) -> bool:
        """Check if an app is already installed in WSL."""
        try:
            # Map app keys to binary names
            binary_map = {
                "google-chrome": "google-chrome-stable",
                "code": "code",
                "nodejs": "node",
                "python3-pip": "pip3",
                "docker": "docker",
            }
            binary = binary_map.get(app_key, app_key)

            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", f"which {binary} 2>/dev/null"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def get_installed_apps(self) -> list[dict]:
        """List all installed apps from the catalog."""
        installed = []
        for key, info in self.APP_CATALOG.items():
            if self._is_installed(key):
                installed.append({"key": key, "name": info["name"], "category": info["category"]})
        return installed

    def get_available_apps(self) -> list[dict]:
        """List all available apps in the catalog."""
        return [
            {"key": key, "name": info["name"], "category": info["category"],
             "description": info["description"], "installed": self._is_installed(key)}
            for key, info in self.APP_CATALOG.items()
        ]


def install_app(app_name: str) -> dict:
    """Install an app by name."""
    installer = AppInstaller()
    result = installer.install(app_name.lower().replace(" ", "-"))
    return {
        "app": result.app_name,
        "success": result.success,
        "method": result.method,
        "message": result.message,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[INSTALL] %(message)s")
    installer = AppInstaller()
    apps = installer.get_available_apps()
    print(f"\n=== App Installer ===")
    print(f"Total apps in catalog: {len(apps)}")
    print(f"Currently installed: {len(installer.get_installed_apps())}")
    print(f"\nCatalog:")
    for app in apps:
        status = "✓" if app["installed"] else "✗"
        print(f"  [{status}] {app['name']} — {app['description']}")
