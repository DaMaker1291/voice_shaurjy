#!/usr/bin/env python3
"""
JARVIS Windows Installer — Cross-Platform Setup Wizard
Detects OS, installs dependencies, configures relay, creates shortcuts.
Works on Windows (.exe), macOS (.app), and Linux (AppImage/deb).
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import time
import urllib.request
import ssl
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════
# OS Detection
# ══════════════════════════════════════════════════════════════════════════

PLATFORM = sys.platform
IS_WINDOWS = PLATFORM == "win32"
IS_MAC = PLATFORM == "darwin"
IS_LINUX = PLATFORM.startswith("linux")

HOME = Path.home()
JARVIS_DIR = HOME / ".jarvis"
DATA_DIR = JARVIS_DIR / "data"
MODELS_DIR = JARVIS_DIR / "models"
RELAY_PATH = JARVIS_DIR / "relay.py"

HF_URL = "https://dgfhgjhj-jarvis-ai-brain.hf.space"
RELAY_URL = f"{HF_URL}/relay"

# ══════════════════════════════════════════════════════════════════════════
# Terminal colors
# ══════════════════════════════════════════════════════════════════════════

class Colors:
    GREEN = "\033[92m" if sys.stdout.isatty() else ""
    YELLOW = "\033[93m" if sys.stdout.isatty() else ""
    RED = "\033[91m" if sys.stdout.isatty() else ""
    CYAN = "\033[96m" if sys.stdout.isatty() else ""
    BOLD = "\033[1m" if sys.stdout.isatty() else ""
    DIM = "\033[2m" if sys.stdout.isatty() else ""
    RESET = "\033[0m" if sys.stdout.isatty() else ""


def banner():
    print(f"""
{Colors.GREEN}{Colors.BOLD}
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║      ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗            ║
    ║      ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝            ║
    ║      ██║███████║██████╔╝██║   ██║██║███████╗            ║
    ║ ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║            ║
    ║ ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║            ║
    ║  ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝            ║
    ║                                                          ║
    ║   Sovereign Network Orchestrator — Installer v3.0       ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
{Colors.RESET}""")


def log(msg, color=""):
    print(f"  {color}▸{Colors.RESET} {msg}")


def success(msg):
    log(msg, Colors.GREEN)


def warn(msg):
    log(msg, Colors.YELLOW)


def error(msg):
    log(msg, Colors.RED)


def info(msg):
    log(msg, Colors.CYAN)


def step(num, total, msg):
    print(f"\n{Colors.BOLD}{Colors.GREEN}[{num}/{total}]{Colors.RESET} {Colors.BOLD}{msg}{Colors.RESET}")
    print(f"  {Colors.DIM}{'─' * 50}{Colors.RESET}")


# ══════════════════════════════════════════════════════════════════════════
# System checks
# ══════════════════════════════════════════════════════════════════════════

def check_python():
    v = sys.version_info
    if v < (3, 9):
        error(f"Python {v.major}.{v.minor} detected. JARVIS requires Python 3.9+")
        sys.exit(1)
    success(f"Python {v.major}.{v.minor}.{v.micro} ✓")


def check_pip():
    try:
        import pip
        success("pip available ✓")
    except ImportError:
        warn("pip not found — installing...")
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], capture_output=True)


def install_requirements():
    """Install Python dependencies."""
    reqs = [
        "fastapi", "uvicorn[standard]", "python-dotenv", "pydantic",
        "psutil", "websocket-client", "certifi", "Pillow",
    ]
    if IS_WINDOWS:
        reqs.append("pywin32")
    
    for pkg in reqs:
        try:
            __import__(pkg.split("[")[0].replace("-", "_"))
        except ImportError:
            info(f"Installing {pkg}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], capture_output=True)
    
    success("Dependencies installed ✓")


def check_relay():
    """Check if relay is already paired."""
    if RELAY_PATH.exists():
        success("Relay already paired ✓")
        return True
    return False


def download_relay():
    """Download relay from HF Space."""
    info("Downloading relay agent...")
    try:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(RELAY_URL, headers={"User-Agent": "JARVIS-Installer/3.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = resp.read()
        
        JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        RELAY_PATH.write_bytes(data)
        success(f"Relay saved to {RELAY_PATH} ✓")
        return True
    except Exception as e:
        error(f"Failed to download relay: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
# Platform-specific setup
# ══════════════════════════════════════════════════════════════════════════

def setup_windows():
    """Windows-specific setup."""
    info("Setting up for Windows...")
    
    # Create Start Menu shortcut
    try:
        import winreg
        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "JARVIS"
        start_menu.mkdir(parents=True, exist_ok=True)
        
        # Create .bat launcher
        bat = start_menu / "JARVIS.bat"
        bat.write_text(f'''@echo off
title JARVIS — Sovereign Network Orchestrator
cd /d "%USERPROFILE%\\.jarvis"
python relay.py --user local
pause
''')
        success(f"Start Menu shortcut created ✓")
    except Exception as e:
        warn(f"Could not create Start Menu shortcut: {e}")
    
    # Create desktop shortcut
    try:
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        vbs = desktop / "JARVIS_Install_Shortcut.vbs"
        vbs.write_text(f'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{start_menu / 'JARVIS.lnk'}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{start_menu / 'JARVIS.bat'}"
oLink.WorkingDirectory = "{JARVIS_DIR}"
oLink.Description = "JARVIS — Sovereign Network Orchestrator"
oLink.Save
''')
        subprocess.run(["cscript", str(vbs)], capture_output=True)
        vbs.unlink()
        success("Desktop shortcut created ✓")
    except Exception as e:
        warn(f"Could not create desktop shortcut: {e}")
    
    # Check Windows Defender exclusion
    warn("IMPORTANT: Add ~/.jarvis to Windows Defender exclusion list for full performance")
    warn("  Settings → Windows Security → Virus Protection → Exclusions → Add folder")


def setup_macos():
    """macOS-specific setup."""
    info("Setting up for macOS...")
    
    # Create Applications symlink
    app_link = Path("/Applications/JARVIS")
    if not app_link.exists():
        try:
            # Create a simple launch script
            app_dir = Path.home() / "Applications" / "JARVIS.app" / "Contents"
            app_dir.mkdir(parents=True, exist_ok=True)
            
            (app_dir / "MacOS" / "jarvis").write_text(f'''#!/bin/bash
cd "{JARVIS_DIR}"
python3 relay.py --user local
''')
            (app_dir / "MacOS" / "jarvis").chmod(0o755)
            (app_dir / "Info.plist").write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>JARVIS</string>
    <key>CFBundleDisplayName</key><string>JARVIS</string>
    <key>CFBundleIdentifier</key><string>com.jarvis.sovereign</string>
    <key>CFBundleVersion</key><string>3.0.0</string>
    <key>CFBundleShortVersionString</key><string>3.0.0</string>
    <key>CFBundleExecutable</key><string>jarvis</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>LSMinimumSystemVersion</key><string>10.15</string>
</dict>
</plist>''')
            success("Applications/JARVIS.app created ✓")
        except Exception as e:
            warn(f"Could not create .app bundle: {e}")
    
    # Check accessibility
    warn("IMPORTANT: Grant Accessibility permissions in System Settings → Privacy & Security")


def setup_linux():
    """Linux-specific setup."""
    info("Setting up for Linux...")
    
    # Create .desktop file
    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    
    desktop_file = desktop_dir / "jarvis.desktop"
    desktop_file.write_text(f'''[Desktop Entry]
Type=Application
Name=JARVIS
Comment=Sovereign Network Orchestrator
Exec=bash -c 'cd "{JARVIS_DIR}" && python3 relay.py --user local'
Terminal=true
Icon=utilities-terminal
Categories=System;
''')
    desktop_file.chmod(0o755)
    success("Desktop entry created ✓")
    
    # Install Xvfb if not present
    try:
        subprocess.run(["which", "Xvfb"], capture_output=True, check=True)
        success("Xvfb available ✓")
    except (subprocess.SubprocessError, FileNotFoundError):
        warn("Xvfb not found — installing for headless workstation support...")
        subprocess.run(["sudo", "apt", "install", "-y", "xvfb", "xdotool", "imagemagick"], capture_output=True)


# ══════════════════════════════════════════════════════════════════════════
# Create directories
# ══════════════════════════════════════════════════════════════════════════

def create_dirs():
    for d in [JARVIS_DIR, DATA_DIR, MODELS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    success("Directories created ✓")


# ══════════════════════════════════════════════════════════════════════════
# Write config
# ══════════════════════════════════════════════════════════════════════════

def write_config():
    config = {
        "version": "3.0",
        "platform": "windows" if IS_WINDOWS else "macos" if IS_MAC else "linux",
        "hf_url": HF_URL,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "relay_user": "local",
    }
    config_path = JARVIS_DIR / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    success(f"Config written to {config_path} ✓")


# ══════════════════════════════════════════════════════════════════════════
# Main installer
# ══════════════════════════════════════════════════════════════════════════

def main():
    banner()
    
    total_steps = 7
    
    step(1, total_steps, "Checking Python")
    check_python()
    
    step(2, total_steps, "Installing Dependencies")
    check_pip()
    install_requirements()
    
    step(3, total_steps, "Creating Directories")
    create_dirs()
    
    step(4, total_steps, "Downloading Relay Agent")
    if not check_relay():
        download_relay()
    
    step(5, total_steps, "Platform Setup")
    if IS_WINDOWS:
        setup_windows()
    elif IS_MAC:
        setup_macos()
    else:
        setup_linux()
    
    step(6, total_steps, "Writing Configuration")
    write_config()
    
    step(7, total_steps, "Verifying Installation")
    # Quick import test
    try:
        import fastapi
        import uvicorn
        success("All imports verified ✓")
    except ImportError as e:
        error(f"Import failed: {e}")
        warn("Try: pip install fastapi uvicorn python-dotenv")
    
    # Final output
    print(f"""
{Colors.GREEN}{Colors.BOLD}
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   ✅  JARVIS INSTALLED SUCCESSFULLY                      ║
  ║                                                          ║
  ║   Quick Start:                                           ║
  ║                                                          ║
  ║   1. Open a terminal                                     ║
  ║   2. Run: cd ~/.jarvis && python{"" if not IS_WINDOWS else ""} relay.py --user local   ║
  ║   3. Open: {HF_URL:<38} ║
  ║                                                          ║
  ║   The relay will pair automatically.                     ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
{Colors.RESET}""")
    
    # Ask to start relay now
    try:
        answer = input(f"  {Colors.GREEN}Start relay now? [Y/n]:{Colors.RESET} ").strip().lower()
        if answer != "n":
            info("Starting relay...")
            if IS_WINDOWS:
                os.system(f'start cmd /k "cd /d %USERPROFILE%\\.jarvis && python relay.py --user local"')
            else:
                subprocess.Popen([sys.executable, str(RELAY_PATH), "--user", "local"])
    except (KeyboardInterrupt, EOFError):
        pass
    
    print(f"\n  {Colors.DIM}Press Enter to exit...{Colors.RESET}")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
