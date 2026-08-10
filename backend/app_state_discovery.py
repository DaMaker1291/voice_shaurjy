"""
JARVIS App State Discovery — Find signed-in state for EVERY desktop app.

Scans:
- Browsers: Chrome, Edge, Firefox profiles (cookies, sessions, tokens)
- Email clients: Outlook, Thunderbird, Mail app
- Chat apps: Discord, Slack, Teams, Telegram, WhatsApp
- Dev tools: VS Code (extensions, settings), Git (credentials), SSH keys
- Cloud apps: Dropbox, OneDrive, Google Drive configs
- Media: Spotify, Netflix, Steam credentials
- Office: Microsoft 365, Google Workspace sessions
"""
import os
import sys
import json
import sqlite3
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("app_state_discovery")


@dataclass
class AppSession:
    """Detected signed-in session for an app."""
    app_name: str
    app_category: str  # browser, email, chat, dev, cloud, media, office
    signed_in: bool
    username: str = ""
    email: str = ""
    profile_path: str = ""
    session_data: dict = field(default_factory=dict)
    install_path: str = ""
    version: str = ""
    platform: str = sys.platform


@dataclass
class AppStateReport:
    """Full report of all discovered app states."""
    timestamp: float = 0.0
    sessions: list = field(default_factory=list)
    missing_apps: list = field(default_factory=list)
    installable_apps: list = field(default_factory=list)
    total_scanned: int = 0
    total_signed_in: int = 0


class AppDiscoveryEngine:
    """Discover signed-in states for all desktop applications."""

    def __init__(self):
        self._cache = {}
        self._wsl_user = self._get_wsl_user()

    def _get_wsl_user(self) -> str:
        """Get WSL username."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", "whoami"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return "workuser"

    def discover_all(self) -> AppStateReport:
        """Scan ALL desktop apps for signed-in states."""
        report = AppStateReport(timestamp=datetime.now().timestamp())

        scanners = [
            self._scan_browsers,
            self._scan_email_clients,
            self._scan_chat_apps,
            self._scan_dev_tools,
            self._scan_cloud_apps,
            self._scan_media_apps,
            self._scan_office_apps,
            self._scan_wsl_apps,
        ]

        for scanner in scanners:
            try:
                sessions = scanner()
                report.sessions.extend(sessions)
            except Exception as e:
                logger.warning(f"Scanner failed: {e}")

        report.total_scanned = len(report.sessions)
        report.total_signed_in = len([s for s in report.sessions if s.signed_in])
        report.missing_apps = self._find_missing_apps()
        report.installable_apps = self._get_installable_apps()

        return report

    # ── Browser Scanners ───────────────────────────────────────────────

    def _scan_browsers(self) -> list[AppSession]:
        """Scan all browsers for signed-in profiles."""
        sessions = []
        sessions.extend(self._scan_chrome_profiles())
        sessions.extend(self._scan_edge_profiles())
        sessions.extend(self._scan_firefox_profiles())
        return sessions

    def _scan_chrome_profiles(self) -> list[AppSession]:
        """Scan Chrome profiles for signed-in state."""
        sessions = []
        chrome_paths = self._get_chrome_paths()

        for chrome_path in chrome_paths:
            if not os.path.exists(chrome_path):
                continue

            profiles_dir = chrome_path / "Default"
            if not profiles_dir.exists():
                # Check for multiple profiles
                for item in chrome_path.iterdir():
                    if item.name.startswith("Profile"):
                        profiles_dir = item
                        break

            if profiles_dir.exists():
                session = self._check_chrome_profile(profiles_dir, "Chrome")
                if session:
                    sessions.append(session)

        return sessions

    def _check_chrome_profile(self, profile_dir: Path, browser: str) -> Optional[AppSession]:
        """Check if a Chrome/Edge profile is signed in."""
        try:
            # Check Login Data file for passwords (indicates signed-in)
            login_data = profile_dir / "Login Data"
            cookies_file = profile_dir / "Cookies"

            signed_in = False
            username = ""
            email = ""

            if login_data.exists():
                # Check file size - non-empty means saved passwords
                if login_data.stat().st_size > 100:
                    signed_in = True

            if cookies_file.exists():
                # Check for Google auth cookies
                try:
                    # Copy to temp to avoid lock issues
                    temp_db = profile_dir / "Cookies_temp.db"
                    shutil.copy2(cookies_file, temp_db)

                    conn = sqlite3.connect(str(temp_db))
                    cursor = conn.cursor()

                    # Check for GAIA auth cookie (Google account)
                    cursor.execute("""
                        SELECT name, value FROM cookies
                        WHERE name IN ('__Secure-1PSID', '__Secure-3PSID', 'SSID', 'HSID', 'SID')
                        AND value != ''
                    """)
                    auth_cookies = cursor.fetchall()
                    conn.close()
                    temp_db.unlink(missing_ok=True)

                    if len(auth_cookies) >= 2:
                        signed_in = True

                    # Try to extract email from preferences
                    prefs_file = profile_dir / "Preferences"
                    if prefs_file.exists():
                        try:
                            prefs = json.loads(prefs_file.read_text())
                            account_info = prefs.get("account_info", [])
                            if account_info:
                                email = account_info[0].get("email", "")
                                username = email.split("@")[0] if email else ""
                        except Exception:
                            pass

                except Exception as e:
                    logger.debug(f"Cookie scan failed: {e}")

            if signed_in:
                install_path = ""
                for p in self._get_chrome_paths():
                    if p.exists():
                        install_path = str(p.parent)
                        break

                return AppSession(
                    app_name=browser,
                    app_category="browser",
                    signed_in=True,
                    username=username,
                    email=email,
                    profile_path=str(profile_dir),
                    install_path=install_path,
                )

        except Exception as e:
            logger.debug(f"Chrome profile check failed: {e}")

        return None

    def _scan_edge_profiles(self) -> list[AppSession]:
        """Scan Edge profiles for signed-in state."""
        sessions = []
        edge_paths = self._get_edge_paths()

        for edge_path in edge_paths:
            if not os.path.exists(edge_path):
                continue

            profiles_dir = edge_path / "Default"
            if not profiles_dir.exists():
                for item in edge_path.iterdir():
                    if item.name.startswith("Profile"):
                        profiles_dir = item
                        break

            if profiles_dir.exists():
                session = self._check_chrome_profile(profiles_dir, "Edge")
                if session:
                    sessions.append(session)

        return sessions

    def _scan_firefox_profiles(self) -> list[AppSession]:
        """Scan Firefox profiles for signed-in state."""
        sessions = []

        firefox_paths = [
            Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles",
            Path.home() / ".mozilla" / "firefox",
        ]

        for profiles_root in firefox_paths:
            if not profiles_root.exists():
                continue

            for profile_dir in profiles_root.iterdir():
                if not profile_dir.is_dir():
                    continue

                # Firefox profiles have cookies.sqlite
                cookies_db = profile_dir / "cookies.sqlite"
                logins_json = profile_dir / "logins.json"

                signed_in = False
                username = ""

                if logins_json.exists():
                    try:
                        logins = json.loads(logins_json.read_text())
                        if logins.get("logins"):
                            signed_in = True
                    except Exception:
                        pass

                if cookies_db.exists():
                    try:
                        temp_db = profile_dir / "cookies_temp.db"
                        shutil.copy2(cookies_db, temp_db)
                        conn = sqlite3.connect(str(temp_db))
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT name FROM moz_cookies
                            WHERE name LIKE '%auth%' OR name LIKE '%session%'
                            OR name LIKE '%login%' OR name LIKE '%token%'
                        """)
                        if cursor.fetchall():
                            signed_in = True
                        conn.close()
                        temp_db.unlink(missing_ok=True)
                    except Exception:
                        pass

                if signed_in:
                    sessions.append(AppSession(
                        app_name="Firefox",
                        app_category="browser",
                        signed_in=True,
                        username=username,
                        profile_path=str(profile_dir),
                    ))

        return sessions

    # ── Email Client Scanners ──────────────────────────────────────────

    def _scan_email_clients(self) -> list[AppSession]:
        """Scan email clients for configured accounts."""
        sessions = []

        # Windows Mail / Outlook
        outlook_path = Path.home() / "AppData" / "Local" / "Microsoft" / "Outlook"
        if outlook_path.exists():
            for ost_file in outlook_path.glob("*.ost"):
                sessions.append(AppSession(
                    app_name="Outlook",
                    app_category="email",
                    signed_in=True,
                    profile_path=str(outlook_path),
                ))

        # Thunderbird
        thunderbird_path = Path.home() / "AppData" / "Roaming" / "Thunderbird" / "Profiles"
        if thunderbird_path.exists():
            for profile in thunderbird_path.iterdir():
                if profile.is_dir():
                    logins = profile / "logins.json"
                    if logins.exists():
                        sessions.append(AppSession(
                            app_name="Thunderbird",
                            app_category="email",
                            signed_in=True,
                            profile_path=str(profile),
                        ))

        return sessions

    # ── Chat App Scanners ──────────────────────────────────────────────

    def _scan_chat_apps(self) -> list[AppSession]:
        """Scan chat apps for signed-in state."""
        sessions = []

        # Discord
        discord_path = Path.home() / "AppData" / "Roaming" / "discord" / "Local Storage"
        if discord_path.exists():
            sessions.append(AppSession(
                app_name="Discord",
                app_category="chat",
                signed_in=True,
                profile_path=str(discord_path),
            ))

        # Slack
        slack_path = Path.home() / "AppData" / "Roaming" / "Slack" / "Local Storage"
        if slack_path.exists():
            sessions.append(AppSession(
                app_name="Slack",
                app_category="chat",
                signed_in=True,
                profile_path=str(slack_path),
            ))

        # Telegram
        telegram_path = Path.home() / "AppData" / "Roaming" / "Telegram Desktop" / "tdata"
        if telegram_path.exists():
            sessions.append(AppSession(
                app_name="Telegram",
                app_category="chat",
                signed_in=True,
                profile_path=str(telegram_path),
            ))

        # WhatsApp Desktop
        whatsapp_path = Path.home() / "AppData" / "Roaming" / "WhatsApp" / "Local Storage"
        if whatsapp_path.exists():
            sessions.append(AppSession(
                app_name="WhatsApp",
                app_category="chat",
                signed_in=True,
                profile_path=str(whatsapp_path),
            ))

        # Teams
        teams_path = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Teams"
        if teams_path.exists():
            sessions.append(AppSession(
                app_name="Teams",
                app_category="chat",
                signed_in=True,
                profile_path=str(teams_path),
            ))

        return sessions

    # ── Dev Tool Scanners ──────────────────────────────────────────────

    def _scan_dev_tools(self) -> list[AppSession]:
        """Scan developer tools for signed-in state."""
        sessions = []

        # VS Code
        vscode_path = Path.home() / "AppData" / "Roaming" / "Code" / "User"
        if vscode_path.exists():
            settings = vscode_path / "settings.json"
            if settings.exists():
                sessions.append(AppSession(
                    app_name="VS Code",
                    app_category="dev",
                    signed_in=True,
                    profile_path=str(vscode_path),
                ))

        # Git credentials
        git_cred = Path.home() / ".git-credentials"
        git_config = Path.home() / ".gitconfig"
        if git_cred.exists() or git_config.exists():
            sessions.append(AppSession(
                app_name="Git",
                app_category="dev",
                signed_in=True,
                profile_path=str(Path.home()),
            ))

        # SSH keys
        ssh_dir = Path.home() / ".ssh"
        if ssh_dir.exists():
            has_keys = any(ssh_dir.glob("id_*"))
            if has_keys:
                sessions.append(AppSession(
                    app_name="SSH",
                    app_category="dev",
                    signed_in=True,
                    profile_path=str(ssh_dir),
                ))

        return sessions

    # ── Cloud App Scanners ─────────────────────────────────────────────

    def _scan_cloud_apps(self) -> list[AppSession]:
        """Scan cloud storage apps for signed-in state."""
        sessions = []

        # OneDrive
        onedrive_path = Path.home() / "AppData" / "Local" / "Microsoft" / "OneDrive" / "settings"
        if onedrive_path.exists():
            sessions.append(AppSession(
                app_name="OneDrive",
                app_category="cloud",
                signed_in=True,
                profile_path=str(onedrive_path),
            ))

        # Dropbox
        dropbox_path = Path.home() / "AppData" / "Local" / "Dropbox" / "info.json"
        if dropbox_path.exists():
            sessions.append(AppSession(
                app_name="Dropbox",
                app_category="cloud",
                signed_in=True,
                profile_path=str(dropbox_path),
            ))

        # Google Drive
        gdrive_path = Path.home() / "AppData" / "Local" / "Google" / "DriveFS"
        if gdrive_path.exists():
            sessions.append(AppSession(
                app_name="Google Drive",
                app_category="cloud",
                signed_in=True,
                profile_path=str(gdrive_path),
            ))

        return sessions

    # ── Media App Scanners ─────────────────────────────────────────────

    def _scan_media_apps(self) -> list[AppSession]:
        """Scan media apps for signed-in state."""
        sessions = []

        # Spotify
        spotify_path = Path.home() / "AppData" / "Roaming" / "Spotify" / "Users"
        if spotify_path.exists():
            for user_dir in spotify_path.iterdir():
                if user_dir.is_dir():
                    sessions.append(AppSession(
                        app_name="Spotify",
                        app_category="media",
                        signed_in=True,
                        username=user_dir.name,
                        profile_path=str(user_dir),
                    ))

        # Steam
        steam_path = Path.home() / "AppData" / "Local" / "Steam" / "config" / "config.vdf"
        if steam_path.exists():
            sessions.append(AppSession(
                app_name="Steam",
                app_category="media",
                signed_in=True,
                profile_path=str(steam_path),
            ))

        return sessions

    # ── Office App Scanners ────────────────────────────────────────────

    def _scan_office_apps(self) -> list[AppSession]:
        """Scan Microsoft Office for signed-in state."""
        sessions = []

        # Office license/token cache
        office_path = Path.home() / "AppData" / "Local" / "Microsoft" / "Office" / "16.0" / "Wef"
        if office_path.exists():
            sessions.append(AppSession(
                app_name="Microsoft 365",
                app_category="office",
                signed_in=True,
                profile_path=str(office_path),
            ))

        return sessions

    # ── WSL App Scanners ───────────────────────────────────────────────

    def _scan_wsl_apps(self) -> list[AppSession]:
        """Scan WSL installed apps."""
        sessions = []

        wsl_apps = {
            "google-chrome-stable": "Chrome (WSL)",
            "firefox": "Firefox (WSL)",
            "code": "VS Code (WSL)",
            "git": "Git (WSL)",
            "docker": "Docker (WSL)",
            "python3": "Python (WSL)",
            "node": "Node.js (WSL)",
        }

        for cmd, name in wsl_apps.items():
            try:
                result = subprocess.run(
                    ["wsl", "-e", "bash", "-c", f"which {cmd} 2>/dev/null"],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout.strip():
                    sessions.append(AppSession(
                        app_name=name,
                        app_category="wsl",
                        signed_in=True,
                        install_path=result.stdout.strip(),
                    ))
            except Exception:
                pass

        return sessions

    # ── Missing App Detection ──────────────────────────────────────────

    def _find_missing_apps(self) -> list[str]:
        """Find apps that should be installed but aren't."""
        missing = []

        essential_apps = {
            "google-chrome-stable": "Chrome",
            "blender": "Blender",
            "gimp": "GIMP",
            "libreoffice": "LibreOffice",
            "xfce4-terminal": "Terminal",
            "mousepad": "Text Editor",
            "vlc": "VLC Media Player",
            "file-roller": "Archive Manager",
        }

        for cmd, name in essential_apps.items():
            try:
                result = subprocess.run(
                    ["wsl", "-e", "bash", "-c", f"which {cmd} 2>/dev/null"],
                    capture_output=True, text=True, timeout=5
                )
                if not result.stdout.strip():
                    missing.append(name)
            except Exception:
                missing.append(name)

        return missing

    def _get_installable_apps(self) -> list[dict]:
        """Get list of apps that can be auto-installed."""
        return [
            {"name": "Blender", "cmd": "sudo apt-get install -y blender", "category": "3d"},
            {"name": "GIMP", "cmd": "sudo apt-get install -y gimp", "category": "image"},
            {"name": "LibreOffice", "cmd": "sudo apt-get install -y libreoffice", "category": "office"},
            {"name": "VLC", "cmd": "sudo apt-get install -y vlc", "category": "media"},
            {"name": "File Roller", "cmd": "sudo apt-get install -y file-roller", "category": "utility"},
            {"name": "Inkscape", "cmd": "sudo apt-get install -y inkscape", "category": "design"},
            {"name": "Audacity", "cmd": "sudo apt-get install -y audacity", "category": "audio"},
            {"name": "OBS Studio", "cmd": "sudo apt-get install -y obs-studio", "category": "streaming"},
            {"name": "Thunderbird", "cmd": "sudo apt-get install -y thunderbird", "category": "email"},
            {"name": "Steam", "cmd": "sudo apt-get install -y steam-installer", "category": "gaming"},
        ]

    # ── Path Helpers ───────────────────────────────────────────────────

    def _get_chrome_paths(self) -> list[Path]:
        """Get Chrome user data paths."""
        return [
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
            Path.home() / ".config" / "google-chrome",
            Path.home() / ".config" / "chromium",
        ]

    def _get_edge_paths(self) -> list[Path]:
        """Get Edge user data paths."""
        return [
            Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data",
            Path.home() / ".config" / "microsoft-edge",
        ]


def discover_app_states() -> dict:
    """Discover all app states and return as dict."""
    engine = AppDiscoveryEngine()
    report = engine.discover_all()

    return {
        "timestamp": report.timestamp,
        "total_scanned": report.total_scanned,
        "total_signed_in": report.total_signed_in,
        "sessions": [
            {
                "app": s.app_name,
                "category": s.app_category,
                "signed_in": s.signed_in,
                "username": s.username,
                "email": s.email,
                "profile_path": s.profile_path,
            }
            for s in report.sessions
        ],
        "missing_apps": report.missing_apps,
        "installable_apps": report.installable_apps,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[DISCOVERY] %(message)s")
    report = discover_app_states()
    print(f"\n=== App State Discovery ===")
    print(f"Scanned: {report['total_scanned']} apps")
    print(f"Signed in: {report['total_signed_in']} apps")
    print(f"\nSigned-in sessions:")
    for s in report["sessions"]:
        if s["signed_in"]:
            print(f"  [{s['category']}] {s['app']} — {s['email'] or s['username'] or 'signed in'}")
    print(f"\nMissing apps: {', '.join(report['missing_apps']) or 'None'}")
    print(f"\nInstallable: {len(report['installable_apps'])} apps available")
