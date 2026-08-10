"""
JARVIS Workspace Cloner — Clone host browser profiles into WSL VDI.

Extends profile_cloner.py to:
1. Copy Chrome/Edge/Firefox profiles from Windows to WSL VDI (~/JARVIS_Vault/VDI_Profile/)
2. Sync session cookies, LocalStorage, extensions, logged-in tokens
3. Clone system env vars, shell configs
4. Initialize XFCE desktop on DISPLAY=:99 matching host resolution
"""
import os
import sys
import json
import shutil
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("workspace_cloner")

HOME = Path.home()
VDI_VAULT = Path(os.environ.get("JARVIS_VDI_DIR",
                Path(__file__).parent / "data" / "vdi_workspace"))
WSL_VDI_VAULT = Path("/opt/jarvis/vdi_profile")


class WorkspaceCloner:
    """Clones host browser sessions and environment into WSL VDI."""

    def __init__(self, wsl_vdi_dir: str = None):
        self.wsl_vdi = Path(wsl_vdi_dir) if wsl_vdi_dir else WSL_VDI_VAULT
        self.host_vault = VDI_VAULT
        self.host_vault.mkdir(parents=True, exist_ok=True)

    # ── Windows Host Profile Paths ────────────────────────────────────────
    def _get_host_chrome_path(self) -> Optional[Path]:
        """Get Windows Chrome profile path."""
        appdata = HOME / "AppData/Local"
        path = appdata / "Google/Chrome/User Data/Default"
        return path if path.exists() else None

    def _get_host_edge_path(self) -> Optional[Path]:
        """Get Windows Edge profile path."""
        appdata = HOME / "AppData/Local"
        path = appdata / "Microsoft/Edge/User Data/Default"
        return path if path.exists() else None

    def _get_host_firefox_path(self) -> Optional[Path]:
        """Get Windows Firefox profile path."""
        appdata = HOME / "AppData/Roaming"
        path = appdata / "Mozilla/Firefox/Profiles"
        return path if path.exists() else None

    # ── Core Clone Operations ─────────────────────────────────────────────
    def clone_browser_profiles(self) -> dict[str, dict]:
        """Clone all browser profiles from Windows host to local vault."""
        results = {}
        total_start = time.time()

        browsers = {
            "chrome": {
                "src": self._get_host_chrome_path(),
                "dest": self.host_vault / "chrome_profile",
                "exclude": ["Cache", "Code Cache", "Service Worker",
                            "GPUCache", "Session Storage", "TransportSecurity",
                            "BudgetDatabase", "databases", "blob_storage"],
            },
            "edge": {
                "src": self._get_host_edge_path(),
                "dest": self.host_vault / "edge_profile",
                "exclude": ["Cache", "Code Cache", "Service Worker",
                            "GPUCache", "Session Storage", "TransportSecurity"],
            },
            "firefox": {
                "src": self._get_host_firefox_path(),
                "dest": self.host_vault / "firefox_profile",
                "exclude": ["cache2", "startupCache", "thumbnails"],
            },
        }

        for name, info in browsers.items():
            src = info["src"]
            dest = info["dest"]
            if not src:
                results[name] = {"success": False, "reason": "not found on host"}
                continue

            start = time.time()
            try:
                dest.mkdir(parents=True, exist_ok=True)
                self._smart_copy(src, dest, info.get("exclude", []))
                elapsed = round(time.time() - start, 2)
                size_mb = round(sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 1048576, 1)
                results[name] = {"success": True, "size_mb": size_mb, "seconds": elapsed}
                logger.info(f"Cloned {name}: {size_mb}MB in {elapsed}s")
            except Exception as e:
                results[name] = {"success": False, "error": str(e)}
                logger.warning(f"Failed to clone {name}: {e}")

        elapsed = round(time.time() - total_start, 2)
        results["_total"] = {"seconds": elapsed, "browsers_cloned": sum(1 for v in results.values() if isinstance(v, dict) and v.get("success"))}
        return results

    def _smart_copy(self, src: Path, dest: Path, exclude: list[str] = None):
        """Intelligent copy — skip excluded dirs, handle locked files."""
        exclude = [e.lower() for e in (exclude or [])]
        for item in src.iterdir():
            if any(ex in item.name.lower() for ex in exclude):
                continue
            try:
                if item.is_dir():
                    dest_item = dest / item.name
                    if not dest_item.exists():
                        shutil.copytree(item, dest_item, dirs_exist_ok=True,
                                        ignore=shutil.ignore_patterns(*exclude))
                else:
                    shutil.copy2(item, dest / item.name)
            except (PermissionError, OSError):
                pass  # Skip locked files

    def clone_session_tokens(self) -> dict:
        """Extract and clone session cookies/tokens specifically."""
        tokens = {}

        # Chrome cookies
        chrome_profile = self.host_vault / "chrome_profile"
        cookies_file = chrome_profile / "Cookies"
        if cookies_file.exists():
            tokens["chrome_cookies"] = str(cookies_file)

        # Chrome login data
        login_data = chrome_profile / "Login Data"
        if login_data.exists():
            tokens["chrome_logins"] = str(login_data)

        # Chrome local storage
        local_storage = chrome_profile / "Local Storage/leveldb"
        if local_storage.exists():
            tokens["chrome_local_storage"] = str(local_storage)

        # Edge tokens
        edge_profile = self.host_vault / "edge_profile"
        edge_cookies = edge_profile / "Cookies"
        if edge_cookies.exists():
            tokens["edge_cookies"] = str(edge_cookies)

        return tokens

    def clone_environment(self) -> dict:
        """Clone system environment variables and shell configs."""
        env_data = {
            "variables": dict(os.environ),
            "path": os.environ.get("PATH", ""),
            "home": str(HOME),
            "user": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        }

        # Save shell configs
        shell_configs = {
            ".bashrc": HOME / ".bashrc",
            ".profile": HOME / ".profile",
            ".bash_aliases": HOME / ".bash_aliases",
        }

        saved = {}
        for name, path in shell_configs.items():
            if path.exists():
                dest = self.host_vault / "shell_configs" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                saved[name] = str(dest)

        env_data["shell_configs"] = saved
        return env_data

    # ── WSL Transfer ──────────────────────────────────────────────────────
    def transfer_to_wsl(self) -> dict:
        """Transfer cloned profiles from Windows vault to WSL VDI."""
        if not self.host_vault.exists():
            return {"success": False, "error": "No host vault to transfer"}

        start = time.time()
        try:
            # Ensure WSL VDI directory exists
            self._wsl_exec(f"mkdir -p {self.wsl_vdi}")

            # Transfer each profile
            results = {}
            for profile_dir in self.host_vault.iterdir():
                if profile_dir.is_dir():
                    wsl_dest = self.wsl_vdi / profile_dir.name
                    self._wsl_exec(f"mkdir -p {wsl_dest}")

                    # Use tar for fast transfer through WSL pipe
                    tar_cmd = f"tar -cf - -C '{self.host_vault}' '{profile_dir.name}' | tar -xf - -C '{self.wsl_vdi}'"
                    self._wsl_exec(tar_cmd)
                    results[profile_dir.name] = True

            elapsed = round(time.time() - start, 2)
            return {"success": True, "transferred": results, "seconds": elapsed}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _wsl_exec(self, cmd: str) -> str:
        """Execute a command in WSL."""
        try:
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout
        except Exception as e:
            logger.warning(f"WSL exec failed: {e}")
            return ""

    # ── VDI Desktop Init ──────────────────────────────────────────────────
    def init_vdi_desktop(self, width: int = 1920, height: int = 1080) -> dict:
        """Initialize XFCE desktop on WSL VDI with cloned profiles."""
        display = ":99"

        # Check if Xvfb is already running
        check = self._wsl_exec(f"ps aux | grep 'Xvfb {display}' | grep -v grep")
        if "Xvfb" in check:
            logger.info(f"Xvfb already running on {display}")
        else:
            # Start Xvfb
            self._wsl_exec(
                f"Xvfb {display} -screen 0 {width}x{height}x24 -ac +extension GLX +render -noreset -nolisten tcp &"
            )
            time.sleep(2)

        # Set environment for the VDI session
        env_setup = f"""
            export DISPLAY={display}
            export GNOME_KEYRING_CONTROL=
            export GTK_IM_MODULE=xim
        """

        # Launch XFCE session if not running
        xfce_check = self._wsl_exec(f"DISPLAY={display} pgrep -u workuser xfce4-session")
        if not xfce_check.strip():
            self._wsl_exec(
                f"su - workuser -c 'DISPLAY={display} xfce4-session &'"
            )
            time.sleep(3)

        return {
            "success": True,
            "display": display,
            "resolution": f"{width}x{height}",
            "xfce_running": bool(xfce_check.strip()),
        }

    # ── Launch Cloned Browsers in VDI ─────────────────────────────────────
    def launch_cloned_browser(self, browser: str = "chrome", url: str = "") -> dict:
        """Launch a browser in VDI using cloned profile."""
        profile_map = {
            "chrome": ("google-chrome-stable", "chrome_profile"),
            "edge": ("microsoft-edge-stable", "edge_profile"),
            "firefox": ("firefox", "firefox_profile"),
        }

        if browser not in profile_map:
            return {"success": False, "error": f"Unknown browser: {browser}"}

        cmd, profile_dir = profile_map[browser]
        profile_path = self.wsl_vdi / profile_dir

        # Check if Edge is installed, fallback to Chrome
        if browser == "edge":
            check = self._wsl_exec(f"which {cmd} 2>/dev/null || echo MISSING")
            if "MISSING" in check:
                cmd = "google-chrome-stable"
                profile_path = self.wsl_vdi / "chrome_profile"
                browser = "chrome (edge not installed)"

        if not profile_path.exists():
            return {"success": False, "error": f"Profile not found: {profile_path}"}

        # Build launch command
        args = [
            cmd,
            f"--user-data-dir={profile_path}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Keychain",
            "--password-store=basic",
        ]
        if url:
            args.append(url)

        launch_cmd = f"DISPLAY=:99 {' '.join(args)} &"
        self._wsl_exec(launch_cmd)

        return {
            "success": True,
            "browser": browser,
            "profile": str(profile_path),
            "display": ":99",
        }

    # ── Status ────────────────────────────────────────────────────────────
    def get_status(self) -> dict:
        """Get cloner status."""
        profiles = {}
        for name in ["chrome_profile", "edge_profile", "firefox_profile"]:
            path = self.host_vault / name
            profiles[name] = {
                "exists": path.exists(),
                "size_mb": round(sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1048576, 1) if path.exists() else 0,
            }

        return {
            "host_vault": str(self.host_vault),
            "wsl_vdi": str(self.wsl_vdi),
            "profiles": profiles,
        }


# ── Convenience Functions ──────────────────────────────────────────────────

def quick_clone_to_wsl(browser: str = "chrome", url: str = "") -> dict:
    """One-shot: clone profiles + init VDI + launch browser."""
    cloner = WorkspaceCloner()

    # Step 1: Clone host profiles
    clone_result = cloner.clone_browser_profiles()

    # Step 2: Init VDI desktop
    vdi_result = cloner.init_vdi_desktop()

    # Step 3: Launch browser with cloned profile
    launch_result = cloner.launch_cloned_browser(browser, url)

    return {
        "clone": clone_result,
        "vdi": vdi_result,
        "launch": launch_result,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[WS] %(message)s")
    cloner = WorkspaceCloner()
    print("=== Workspace Cloner Status ===")
    status = cloner.get_status()
    for k, v in status.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")

    print("\n=== Cloning Host Profiles ===")
    results = cloner.clone_browser_profiles()
    for k, v in results.items():
        if isinstance(v, dict):
            status = "OK" if v.get("success") else "SKIP"
            print(f"  {status:4s} {k}: {v}")
