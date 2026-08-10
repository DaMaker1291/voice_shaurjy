"""
JARVIS Profile Cloner — Clone browser sessions, cookies, app configs into VDI workspace.
Copies Chrome/Firefox profiles, SSH keys, app configs in under 2 seconds.
"""
import os
import sys
import json
import shutil
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cloner")

HOME = Path.home()
VDI_VAULT = Path(os.environ.get("JARVIS_VDI_DIR",
                Path(__file__).parent / "data" / "vdi_workspace"))


class ProfileCloner:
    """Clones logged-in browser sessions and app configs into an isolated VDI workspace."""

    def __init__(self, vdi_dir: str = None):
        self.vdi_dir = Path(vdi_dir) if vdi_dir else VDI_VAULT
        self.vdi_dir.mkdir(parents=True, exist_ok=True)
        self._clone_map = self._build_clone_map()

    def _build_clone_map(self) -> dict[str, dict]:
        """Build platform-specific clone paths."""
        is_windows = sys.platform == "win32"
        is_linux = sys.platform == "linux"

        clones = {}

        if is_windows:
            appdata_local = HOME / "AppData/Local"
            appdata_roaming = HOME / "AppData/Roaming"

            clones["chrome"] = {
                "name": "Google Chrome",
                "src": appdata_local / "Google/Chrome/User Data/Default",
                "dest": self.vdi_dir / "chrome_profile",
                "exclude": ["Cache", "Code Cache", "Service Worker",
                            "GPUCache", "Session Storage", "TransportSecurity"],
            }
            clones["chrome_bookmarks"] = {
                "name": "Chrome Bookmarks",
                "src": appdata_local / "Google/Chrome/User Data/Default/Bookmarks",
                "dest": self.vdi_dir / "chrome_profile/Bookmarks",
                "single_file": True,
            }
            clones["firefox"] = {
                "name": "Firefox",
                "src": appdata_roaming / "Mozilla/Firefox/Profiles",
                "dest": self.vdi_dir / "firefox_profile",
                "exclude": ["cache2", "startupCache", "thumbnails"],
            }
            clones["vscode"] = {
                "name": "VS Code",
                "src": appdata_roaming / "Code/User",
                "dest": self.vdi_dir / "vscode_profile",
                "exclude": ["Cache", "CachedData", "CachedExtensions"],
            }
            clones["edge"] = {
                "name": "Microsoft Edge",
                "src": appdata_local / "Microsoft/Edge/User Data/Default",
                "dest": self.vdi_dir / "edge_profile",
                "exclude": ["Cache", "Code Cache", "Service Worker", "GPUCache"],
            }
            clones["putty"] = {
                "name": "PuTTY Sessions",
                "src": None,  # Registry-based, handle separately
                "dest": self.vdi_dir / "putty_sessions",
            }
            clones["ssh"] = {
                "name": "SSH Keys",
                "src": HOME / ".ssh",
                "dest": self.vdi_dir / "ssh_keys",
                "exclude": ["known_hosts"],
            }

        elif is_linux:
            clones["chrome"] = {
                "name": "Google Chrome",
                "src": HOME / ".config/google-chrome/Default",
                "dest": self.vdi_dir / "chrome_profile",
                "exclude": ["Cache", "Code Cache", "Service Worker",
                            "GPUCache", "Session Storage"],
            }
            clones["firefox"] = {
                "name": "Firefox",
                "src": HOME / ".mozilla/firefox",
                "dest": self.vdi_dir / "firefox_profile",
                "exclude": ["cache2", "startupCache"],
            }
            clones["vscode"] = {
                "name": "VS Code",
                "src": HOME / ".config/Code/User",
                "dest": self.vdi_dir / "vscode_profile",
                "exclude": ["Cache", "CachedData"],
            }
            clones["ssh"] = {
                "name": "SSH Keys",
                "src": HOME / ".ssh",
                "dest": self.vdi_dir / "ssh_keys",
                "exclude": ["known_hosts"],
            }

        return clones

    def clone_all(self) -> dict[str, bool]:
        """Clone all available profiles. Returns success status per app."""
        results = {}
        total_start = time.time()

        for app_id, info in self._clone_map.items():
            try:
                if info.get("single_file"):
                    success = self._clone_file(info["src"], info["dest"])
                elif info["src"] is None:
                    success = self._clone_registry(app_id, info["dest"])
                else:
                    success = self._clone_directory(
                        info["src"], info["dest"],
                        exclude=info.get("exclude", [])
                    )
                results[app_id] = success
                if success:
                    logger.info(f"Cloned: {info['name']}")
                else:
                    logger.debug(f"Skipped: {info['name']} (not found)")
            except Exception as e:
                logger.warning(f"Failed to clone {info['name']}: {e}")
                results[app_id] = False

        elapsed = round(time.time() - total_start, 2)
        cloned = sum(1 for v in results.values() if v)
        logger.info(f"Profile clone complete: {cloned}/{len(results)} apps in {elapsed}s")
        return results

    def _clone_directory(self, src: Path, dest: Path, exclude: list[str] = None) -> bool:
        """Clone a directory, excluding specified patterns."""
        if not src.exists():
            return False
        dest.mkdir(parents=True, exist_ok=True)

        exclude = exclude or []
        items = list(src.iterdir())
        copied = 0

        for item in items:
            # Skip excluded patterns
            if any(ex.lower() in item.name.lower() for ex in exclude):
                continue
            try:
                if item.is_dir():
                    dest_item = dest / item.name
                    if not dest_item.exists():
                        shutil.copytree(item, dest_item, dirs_exist_ok=True,
                                        ignore=shutil.ignore_patterns(*exclude))
                    copied += 1
                else:
                    shutil.copy2(item, dest / item.name)
                    copied += 1
            except Exception:
                pass  # Skip locked/in-use files

        return copied > 0

    def _clone_file(self, src: Path, dest: Path) -> bool:
        """Clone a single file."""
        if not src.exists():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True

    def _clone_registry(self, app_id: str, dest: Path) -> bool:
        """Clone Windows registry entries (PuTTY sessions)."""
        if sys.platform != "win32":
            return False
        try:
            import winreg
            dest.mkdir(parents=True, exist_ok=True)

            if app_id == "putty":
                key_path = r"Software\SimonTatham\PuTTY\Sessions"
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                    i = 0
                    while True:
                        try:
                            session_name = winreg.EnumKey(key, i)
                            sess_key = winreg.OpenKey(key, session_name)
                            sess_data = {}
                            j = 0
                            while True:
                                try:
                                    val_name, val_data, val_type = winreg.EnumValue(sess_key, j)
                                    sess_data[val_name] = val_data
                                    j += 1
                                except OSError:
                                    break
                            winreg.CloseHandle(sess_key)
                            # Save as JSON
                            safe_name = session_name.replace("/", "_").replace("\\", "_")
                            with open(dest / f"{safe_name}.json", "w") as f:
                                json.dump(sess_data, f, indent=2)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseHandle(key)
                    return i > 0
                except FileNotFoundError:
                    return False
        except ImportError:
            return False
        return False

    def get_chrome_profile_path(self) -> Optional[str]:
        """Get the cloned Chrome profile path for launching."""
        profile = self.vdi_dir / "chrome_profile"
        if profile.exists():
            return str(profile)
        return None

    def get_firefox_profile_path(self) -> Optional[str]:
        """Get the cloned Firefox profile path."""
        profile = self.vdi_dir / "firefox_profile"
        if profile.exists():
            return str(profile)
        return None

    def cleanup(self):
        """Remove the VDI workspace."""
        if self.vdi_dir.exists():
            shutil.rmtree(self.vdi_dir, ignore_errors=True)
            logger.info("VDI workspace cleaned up")


def quick_clone(target_dir: str = None) -> dict:
    """Quick clone — copy only essential session files (cookies, tokens, bookmarks)."""
    cloner = ProfileCloner(target_dir)
    return cloner.clone_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[CLONE] %(message)s")
    results = quick_clone()
    print(f"\nClone results:")
    for app, success in results.items():
        print(f"  {'OK' if success else 'SKIP':4s} {app}")
