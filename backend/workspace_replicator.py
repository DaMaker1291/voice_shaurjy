"""JARVIS Workspace Replicator - Scans user computer and syncs to workspace.

On first setup, scans installed applications, browser profiles, documents,
preferences, extensions, fonts, dev tools, and configuration. Builds a
replication profile that the workspace uses to mirror the user's environment.

After initial setup, detects new installs and syncs changes.
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict

log = logging.getLogger("workspace_replicator")

REPLICATOR_DIR = Path(os.path.expanduser("~/.jarvis/replicator"))
REPLICATOR_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class InstalledApp:
    name: str
    command: str
    path: str = ""
    version: str = ""
    category: str = "unknown"
    auth_type: str = "none"
    auth_survives_clone: bool = False
    detected_at: float = 0

    def to_dict(self):
        return {
            "name": self.name, "command": self.command, "path": self.path,
            "version": self.version, "category": self.category,
            "auth_type": self.auth_type, "auth_survives_clone": self.auth_survives_clone,
        }


@dataclass
class UserProfile:
    browser_profiles: List[dict] = field(default_factory=list)
    documents_path: str = ""
    desktop_path: str = ""
    downloads_path: str = ""
    app_settings: Dict[str, dict] = field(default_factory=dict)
    extensions: List[dict] = field(default_factory=list)
    fonts: List[str] = field(default_factory=list)
    dev_tools: List[dict] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)
    shell_config: str = ""
    git_config: Dict[str, str] = field(default_factory=dict)
    installed_apps: List[InstalledApp] = field(default_factory=list)
    scanned_at: float = 0

    def to_dict(self):
        return {
            "browser_profiles": self.browser_profiles,
            "documents_path": self.documents_path,
            "desktop_path": self.desktop_path,
            "downloads_path": self.downloads_path,
            "app_settings": self.app_settings,
            "extensions": self.extensions,
            "fonts": self.fonts,
            "dev_tools": self.dev_tools,
            "env_vars": self.env_vars,
            "shell_config": self.shell_config,
            "git_config": self.git_config,
            "installed_apps": [a.to_dict() for a in self.installed_apps],
            "scanned_at": self.scanned_at,
        }


# Apps whose authentication does NOT survive cloning
AUTH_SENSITIVE_APPS = {
    "chrome", "edge", "firefox", "brave", "opera", "vivaldi",
    "outlook", "thundermail", "slack", "discord", "teams",
    "1password", "bitwarden", "lastpass", "dashlane",
    "dropbox", "onedrive", "google drive", "icloud",
    "visual studio code", "github desktop",
}

# Apps whose authentication typically survives cloning
AUTH_ROBUST_APPS = {
    "notepad++", "sublime text", "vim", "neovim",
    "7zip", "winrar", "vlc", "mpv",
    "blender", "gimp", "inkscape", "krita",
    "autoCAD", "solidworks", "fusion360",
    "python", "node", "java", "git", "docker",
}


class WorkspaceReplicator:
    """Scans user's computer and builds replication profiles for workspaces."""

    def __init__(self):
        self._profile: Optional[UserProfile] = None
        self._lock = threading.Lock()
        self._profile_file = REPLICATOR_DIR / "user_profile.json"
        self._load_profile()

    def _load_profile(self):
        if self._profile_file.exists():
            try:
                with open(self._profile_file) as f:
                    data = json.load(f)
                self._profile = UserProfile(
                    browser_profiles=data.get("browser_profiles", []),
                    documents_path=data.get("documents_path", ""),
                    desktop_path=data.get("desktop_path", ""),
                    downloads_path=data.get("downloads_path", ""),
                    app_settings=data.get("app_settings", {}),
                    extensions=data.get("extensions", []),
                    fonts=data.get("fonts", []),
                    dev_tools=data.get("dev_tools", []),
                    env_vars=data.get("env_vars", {}),
                    shell_config=data.get("shell_config", ""),
                    git_config=data.get("git_config", {}),
                    scanned_at=data.get("scanned_at", 0),
                )
                for a in data.get("installed_apps", []):
                    self._profile.installed_apps.append(InstalledApp(**a))
            except Exception as e:
                log.error(f"[REPLICATOR] Failed to load profile: {e}")
                self._profile = UserProfile()
        else:
            self._profile = UserProfile()

    def _save_profile(self):
        REPLICATOR_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._profile_file, "w") as f:
            json.dump(self._profile.to_dict(), f, indent=2)

    def scan_all(self) -> dict:
        """Full system scan. Returns summary of what was found."""
        profile = UserProfile(scanned_at=time.time())

        log.info("[REPLICATOR] Starting full system scan...")

        profile.installed_apps = self._scan_installed_apps()
        log.info(f"[REPLICATOR] Found {len(profile.installed_apps)} installed apps")

        profile.browser_profiles = self._scan_browser_profiles()
        log.info(f"[REPLICATOR] Found {len(profile.browser_profiles)} browser profiles")

        profile.documents_path = self._find_documents_path()
        profile.desktop_path = self._find_desktop_path()
        profile.downloads_path = self._find_downloads_path()

        profile.extensions = self._scan_extensions()
        log.info(f"[REPLICATOR] Found {len(profile.extensions)} extensions")

        profile.fonts = self._scan_fonts()
        log.info(f"[REPLICATOR] Found {len(profile.fonts)} fonts")

        profile.dev_tools = self._scan_dev_tools()
        log.info(f"[REPLICATOR] Found {len(profile.dev_tools)} dev tools")

        profile.git_config = self._scan_git_config()
        profile.env_vars = self._scan_env_vars()

        with self._lock:
            self._profile = profile
            self._save_profile()

        log.info("[REPLICATOR] Scan complete")
        return {
            "ok": True,
            "apps": len(profile.installed_apps),
            "browsers": len(profile.browser_profiles),
            "extensions": len(profile.extensions),
            "fonts": len(profile.fonts),
            "dev_tools": len(profile.dev_tools),
            "scanned_at": profile.scanned_at,
        }

    def _scan_installed_apps(self) -> List[InstalledApp]:
        """Scan for installed applications."""
        apps = []
        seen = set()

        if sys.platform == "win32":
            apps.extend(self._scan_windows_apps(seen))
        else:
            apps.extend(self._scan_linux_apps(seen))

        apps.extend(self._scan_common_paths(seen))
        return apps

    def _scan_windows_apps(self, seen: set) -> List[InstalledApp]:
        """Scan Windows installed apps via registry and Start Menu."""
        apps = []
        try:
            import winreg
            uninstall_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hkey, subkey in uninstall_keys:
                try:
                    key = winreg.OpenKey(hkey, subkey)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            sub = winreg.OpenKey(key, subkey_name)
                            try:
                                name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                if name in seen:
                                    i += 1
                                    continue
                                seen.add(name)
                                cmd = ""
                                try:
                                    cmd = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                except FileNotFoundError:
                                    pass
                                version = ""
                                try:
                                    version = winreg.QueryValueEx(sub, "DisplayVersion")[0]
                                except FileNotFoundError:
                                    pass
                                auth_type = "device_bound" if name.lower() in AUTH_SENSITIVE_APPS else "token"
                                auth_survives = name.lower() in AUTH_ROBUST_APPS
                                apps.append(InstalledApp(
                                    name=name, command=cmd, version=version,
                                    category="windows_registry",
                                    auth_type=auth_type,
                                    auth_survives_clone=auth_survives,
                                    detected_at=time.time(),
                                ))
                            except FileNotFoundError:
                                pass
                            winreg.CloseKey(sub)
                        except OSError:
                            break
                        i += 1
                    winreg.CloseKey(key)
                except OSError:
                    pass
        except ImportError:
            pass

        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
        if start_menu.exists():
            for lnk in start_menu.rglob("*.lnk"):
                name = lnk.stem
                if name not in seen:
                    seen.add(name)
                    apps.append(InstalledApp(
                        name=name, command=str(lnk),
                        category="start_menu",
                        detected_at=time.time(),
                    ))
        return apps

    def _scan_linux_apps(self, seen: set) -> List[InstalledApp]:
        """Scan Linux installed apps via which/dpkg/flatpak."""
        apps = []
        common_bins = [
            "google-chrome", "firefox", "code", "vim", "neovim", "git",
            "docker", "python3", "node", "npm", "gcc", "make", "cmake",
            "blender", "gimp", "inkscape", "vlc", "mpv", "ffmpeg",
            " libreoffice", "thunderbird", "slack", "discord",
        ]
        for b in common_bins:
            try:
                result = subprocess.run(["which", b], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and b not in seen:
                    seen.add(b)
                    apps.append(InstalledApp(
                        name=b, command=result.stdout.strip(),
                        category="linux_binary",
                        detected_at=time.time(),
                    ))
            except Exception:
                pass
        return apps

    def _scan_common_paths(self, seen: set) -> List[InstalledApp]:
        """Scan common installation directories."""
        apps = []
        if sys.platform == "win32":
            scan_dirs = [
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")),
                Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")),
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            ]
        else:
            scan_dirs = [Path("/usr/bin"), Path("/usr/local/bin"), Path.home() / ".local/bin"]

        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            try:
                for item in scan_dir.iterdir():
                    if item.is_file() and item.suffix in (".exe", ".app", ""):
                        name = item.stem if item.suffix else item.name
                        if name.lower() not in seen and not name.startswith("."):
                            seen.add(name.lower())
                            apps.append(InstalledApp(
                                name=name, command=str(item),
                                path=str(item.parent),
                                category="common_path",
                                detected_at=time.time(),
                            ))
            except PermissionError:
                pass
        return apps

    def _scan_browser_profiles(self) -> List[dict]:
        """Scan for browser profiles."""
        profiles = []
        home = Path.home()

        browser_paths = {
            "Chrome": home / ".config/google-chrome/Default",
            "Chrome (Windows)": Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default",
            "Edge": Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default",
            "Firefox": home / ".mozilla/firefox",
            "Brave": Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware/Brave-Browser/User Data/Default",
        }

        for name, path in browser_paths.items():
            if path.exists():
                profiles.append({
                    "browser": name,
                    "profile_path": str(path),
                    "has_data": True,
                    "auth_survives_clone": False,
                })
        return profiles

    def _find_documents_path(self) -> str:
        if sys.platform == "win32":
            return str(Path.home() / "Documents")
        return str(Path.home() / "Documents")

    def _find_desktop_path(self) -> str:
        if sys.platform == "win32":
            return str(Path.home() / "Desktop")
        return str(Path.home() / "Desktop")

    def _find_downloads_path(self) -> str:
        if sys.platform == "win32":
            return str(Path.home() / "Downloads")
        return str(Path.home() / "Downloads")

    def _scan_extensions(self) -> List[dict]:
        """Scan for browser extensions."""
        extensions = []
        home = Path.home()
        ext_dir = home / ".config/google-chrome/Default/Extensions"
        if not ext_dir.exists():
            ext_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Extensions"
        if ext_dir.exists():
            try:
                for ext_id in ext_dir.iterdir():
                    if ext_id.is_dir() and len(ext_id.name) == 32:
                        manifest = ext_id / "0.0.0" / "manifest.json"
                        if manifest.exists():
                            try:
                                with open(manifest) as f:
                                    data = json.load(f)
                                extensions.append({
                                    "id": ext_id.name,
                                    "name": data.get("name", "Unknown"),
                                    "version": data.get("version", ""),
                                    "browser": "chrome",
                                })
                            except Exception:
                                pass
            except PermissionError:
                pass
        return extensions

    def _scan_fonts(self) -> List[str]:
        """Scan installed fonts."""
        fonts = []
        if sys.platform == "win32":
            font_dir = Path("C:/Windows/Fonts")
        else:
            font_dir = Path("/usr/share/fonts")
        if font_dir.exists():
            try:
                for f in font_dir.iterdir():
                    if f.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2"):
                        fonts.append(f.stem)
            except PermissionError:
                pass
        return fonts[:200]

    def _scan_dev_tools(self) -> List[dict]:
        """Scan for development tools."""
        tools = []
        checks = [
            ("python3", "Python", ["python3", "--version"]),
            ("python", "Python", ["python", "--version"]),
            ("node", "Node.js", ["node", "--version"]),
            ("npm", "npm", ["npm", "--version"]),
            ("git", "Git", ["git", "--version"]),
            ("docker", "Docker", ["docker", "--version"]),
            ("gcc", "GCC", ["gcc", "--version"]),
            ("java", "Java", ["java", "--version"]),
            ("cargo", "Rust", ["cargo", "--version"]),
            ("go", "Go", ["go", "version"]),
        ]
        for key, name, cmd in checks:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.strip().split("\n")[0]
                    tools.append({"name": name, "version": version, "command": cmd[0]})
            except Exception:
                pass
        return tools

    def _scan_git_config(self) -> Dict[str, str]:
        """Scan git configuration."""
        config = {}
        try:
            result = subprocess.run(
                ["git", "config", "--global", "--list"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if "=" in line:
                        k, v = line.split("=", 1)
                        config[k.strip()] = v.strip()
        except Exception:
            pass
        return config

    def _scan_env_vars(self) -> Dict[str, str]:
        """Capture relevant environment variables."""
        relevant = {}
        capture_keys = [
            "PATH", "HOME", "USER", "SHELL", "EDITOR",
            "JAVA_HOME", "PYTHON_PATH", "NODE_PATH",
            "GOPATH", "CARGO_HOME", "DOTNET_ROOT",
        ]
        for k in capture_keys:
            v = os.environ.get(k)
            if v:
                relevant[k] = v[:500]
        return relevant

    def get_profile(self) -> Optional[UserProfile]:
        with self._lock:
            return self._profile

    def get_profile_dict(self) -> dict:
        with self._lock:
            return self._profile.to_dict() if self._profile else {}

    def get_auth_needing_apps(self) -> List[dict]:
        """Return apps that will need re-authentication in the workspace."""
        if not self._profile:
            return []
        return [
            a.to_dict() for a in self._profile.installed_apps
            if not a.auth_survives_clone
        ]

    def get_workspace_app_manifest(self) -> List[dict]:
        """Generate the app manifest for workspace provisioning."""
        if not self._profile:
            return []
        manifest = []
        for app in self._profile.installed_apps:
            manifest.append({
                "name": app.name,
                "command": app.command,
                "category": app.category,
                "auth_type": app.auth_type,
                "auth_survives_clone": app.auth_survives_clone,
                "provisioning": "clone" if app.auth_survives_clone else "install_and_auth",
            })
        return manifest

    def needs_rescan(self, max_age_hours: int = 24) -> bool:
        """Check if a rescan is needed."""
        if not self._profile or not self._profile.scanned_at:
            return True
        age_hours = (time.time() - self._profile.scanned_at) / 3600
        return age_hours > max_age_hours


_replicator = None

def get_workspace_replicator() -> WorkspaceReplicator:
    global _replicator
    if _replicator is None:
        _replicator = WorkspaceReplicator()
    return _replicator
