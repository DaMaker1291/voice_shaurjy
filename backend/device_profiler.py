"""Device Profiler — explores the user's machine to build a complete profile.

Runs on the RELAY side (user's actual machine) to discover:
- OS, hardware, CPU, RAM, disk
- Installed applications (with categories)
- Running processes
- Network interfaces, WiFi SSID
- User identity (username, home dir, shell)
- Browser history / bookmarks (optional)
- Recent files
- System preferences

The profile is sent to HF Space on each registration/heartbeat,
so JARVIS always knows what the user's machine can do.
"""

import json
import os
import platform
import subprocess
import socket
import time
import re
from pathlib import Path


def _run(cmd, timeout=15):
    """Run a shell command via ExecutionVault sandbox."""
    try:
        from execution_vault import vaulted_run
        vr = vaulted_run(cmd, timeout=timeout)
        if vr.blocked:
            return f"BLOCKED: {vr.block_reason}"
        return (vr.stdout or vr.stderr or "").strip()
    except Exception:
        return ""


def _get_hw_info():
    """Get hardware specs."""
    info = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
    }

    # CPU cores
    try:
        import multiprocessing
        info["cpu_cores"] = multiprocessing.cpu_count()
    except Exception:
        pass

    # RAM
    try:
        if platform.system() == "Darwin":
            out = _run("sysctl -n hw.memsize")
            if out.isdigit():
                info["ram_bytes"] = int(out)
                info["ram_gb"] = round(int(out) / (1024**3), 1)
        elif platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        info["ram_bytes"] = kb * 1024
                        info["ram_gb"] = round(kb / (1024**2), 1)
                        break
        elif platform.system() == "Windows":
            out = _run("powershell -c \"(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory\"")
            if out.isdigit():
                info["ram_bytes"] = int(out)
                info["ram_gb"] = round(int(out) / (1024**3), 1)
    except Exception:
        pass

    # Disk
    try:
        st = os.statvfs("/")
        info["disk_total_gb"] = round((st.f_blocks * st.f_frsize) / (1024**3), 1)
        info["disk_free_gb"] = round((st.f_bavail * st.f_frsize) / (1024**3), 1)
    except Exception:
        pass

    # Battery
    try:
        if platform.system() == "Darwin":
            out = _run("pmset -g batt")
            pct_match = re.search(r'(\d+)%', out)
            if pct_match:
                info["battery"] = int(pct_match.group(1))
                info["charging"] = "charging" in out.lower()
        elif platform.system() == "Windows":
            out = _run("powershell -c \"(Get-CimInstance Win32_Battery).EstimatedChargeRemaining\"")
            if out.isdigit():
                info["battery"] = int(out)
    except Exception:
        pass

    return info


def _get_user_info():
    """Get current user identity."""
    info = {}
    try:
        info["username"] = os.getenv("USER") or os.getenv("USERNAME") or _run("whoami")
        info["home"] = str(Path.home())
        info["shell"] = os.getenv("SHELL", "")
        info["uid"] = os.getuid() if hasattr(os, "getuid") else ""
    except Exception:
        pass

    # Full name (macOS)
    try:
        if platform.system() == "Darwin":
            out = _run("id -F")
            if out:
                info["full_name"] = out
    except Exception:
        pass

    return info


def _get_installed_apps():
    """Get installed applications — cross-platform."""
    apps = []

    try:
        if platform.system() == "Darwin":
            # macOS — scan /Applications
            app_dir = Path("/Applications")
            if app_dir.exists():
                for item in sorted(app_dir.iterdir()):
                    if item.suffix == ".app":
                        apps.append({
                            "name": item.stem,
                            "path": str(item),
                            "category": _categorize_app(item.stem),
                        })

        elif platform.system() == "Windows":
            # Windows — registry
            try:
                import winreg
                keys = [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ]
                for key_path in keys:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                        i = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                subkey = winreg.OpenKey(key, subkey_name)
                                try:
                                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    loc = ""
                                    try:
                                        loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                    except Exception:
                                        pass
                                    apps.append({
                                        "name": name,
                                        "path": loc,
                                        "category": _categorize_app(name),
                                    })
                                except Exception:
                                    pass
                                winreg.CloseKey(subkey)
                                i += 1
                            except OSError:
                                break
                        winreg.CloseKey(key)
                    except Exception:
                        pass
            except ImportError:
                pass

        elif platform.system() == "Linux":
            # Linux — /usr/share/applications
            desktop_dir = Path("/usr/share/applications")
            if desktop_dir.exists():
                for f in desktop_dir.glob("*.desktop"):
                    try:
                        with open(f) as fh:
                            for line in fh:
                                if line.startswith("Name="):
                                    apps.append({
                                        "name": line.strip().split("=", 1)[1],
                                        "path": str(f),
                                        "category": _categorize_app(line.strip().split("=", 1)[1]),
                                    })
                                    break
                    except Exception:
                        pass
    except Exception:
        pass

    # Deduplicate by name
    seen = set()
    unique = []
    for a in apps:
        if a["name"] not in seen:
            seen.add(a["name"])
            unique.append(a)

    return unique[:200]  # cap at 200


def _categorize_app(name):
    """Categorize an app by name heuristics."""
    nl = name.lower()
    cats = {
        "browser": ["chrome", "firefox", "safari", "edge", "opera", "brave", "vivaldi"],
        "communication": ["slack", "discord", "teams", "zoom", "skype", "whatsapp", "telegram", "facetime"],
        "email": ["outlook", "mail", "thunderbird", "spark", "airmail"],
        "development": ["code", "visual studio", "xcode", "android studio", "intellij", "pycharm", "sublime", "atom", "vim", "nano", "terminal", "iterm", "hyper", "git", "docker"],
        "media": ["spotify", "vlc", "itunes", "music", "youtube", "netflix", "plex", "obs", "audacity"],
        "productivity": ["notion", "obsidian", "evernote", "todoist", "things", "omnifocus", "trello", "asana"],
        "creative": ["photoshop", "illustrator", "figma", "sketch", "blender", "maya", "lightroom", "premiere", "after effects", "canva"],
        "office": ["word", "excel", "powerpoint", "pages", "numbers", "keynote", "libreoffice", "openoffice", "onenote"],
        "gaming": ["steam", "epic", "origin", "battle.net", "uplay", "gog"],
        "utilities": ["1password", "bitwarden", "dropbox", "google drive", "onedrive", "icloud", "bettertouchtrap", "alfred", "raycast"],
        "security": ["wireshark", "nmap", "burp", "metasploit", "kali"],
    }
    for cat, keywords in cats.items():
        if any(kw in nl for kw in keywords):
            return cat
    return "other"


def _get_running_processes():
    """Get top running processes by memory."""
    procs = []
    try:
        if platform.system() == "Darwin" or platform.system() == "Linux":
            out = _run("ps aux --sort=-%mem | head -15")
            for line in out.splitlines()[1:]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    procs.append({
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": parts[10][:100],
                    })
        elif platform.system() == "Windows":
            out = _run("powershell -c \"Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Name,Id,CPU,WorkingSet | ConvertTo-Json\"")
            if out:
                try:
                    data = json.loads(out)
                    if isinstance(data, list):
                        for p in data:
                            procs.append({
                                "name": p.get("Name", ""),
                                "pid": p.get("Id", 0),
                                "mem_mb": round(p.get("WorkingSet", 0) / (1024*1024), 1),
                            })
                except Exception:
                    pass
    except Exception:
        pass
    return procs


def _get_network_info():
    """Get network interfaces and WiFi SSID."""
    info = {}

    # WiFi SSID
    try:
        if platform.system() == "Darwin":
            out = _run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I")
            ssid_match = re.search(r'ssid:\s*(.+)', out)
            if ssid_match:
                info["wifi_ssid"] = ssid_match.group(1).strip()
        elif platform.system() == "Windows":
            out = _run("netsh wlan show interfaces")
            ssid_match = re.search(r'SSID:\s*(.+)', out)
            if ssid_match:
                info["wifi_ssid"] = ssid_match.group(1).strip()
    except Exception:
        pass

    # Local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    return info


def _get_recent_files():
    """Get recently modified files in common directories."""
    recent = []
    try:
        home = Path.home()
        for dirname in ["Documents", "Desktop", "Downloads"]:
            d = home / dirname
            if d.exists():
                files = sorted(d.iterdir(), key=lambda f: f.stat().st_mtime if f.exists() else 0, reverse=True)
                for f in files[:5]:
                    if f.is_file():
                        recent.append({
                            "name": f.name,
                            "dir": dirname,
                            "modified": int(f.stat().st_mtime),
                            "size_mb": round(f.stat().st_size / (1024*1024), 2),
                        })
    except Exception:
        pass
    return recent[:15]


def _get_browser_bookmarks():
    """Try to read browser bookmark titles (Chrome/Edge)."""
    bookmarks = []
    try:
        if platform.system() == "Darwin":
            paths = [
                Path.home() / "Library/Application Support/Google/Chrome/Default/Bookmarks",
                Path.home() / "Library/Application Support/Microsoft Edge/Default/Bookmarks",
            ]
        elif platform.system() == "Windows":
            paths = [
                Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Bookmarks",
                Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Bookmarks",
            ]
        elif platform.system() == "Linux":
            paths = [
                Path.home() / ".config/google-chrome/Default/Bookmarks",
                Path.home() / ".config/microsoft-edge/Default/Bookmarks",
            ]
        else:
            paths = []

        for bp in paths:
            if bp.exists():
                with open(bp) as f:
                    data = json.load(f)
                _extract_bookmark_urls(data.get("roots", {}), bookmarks, max_depth=3)
                if bookmarks:
                    break
    except Exception:
        pass
    return bookmarks[:30]


def _extract_bookmark_urls(node, out, max_depth=3, depth=0):
    """Recursively extract bookmark URLs."""
    if depth > max_depth:
        return
    if isinstance(node, dict):
        if node.get("type") == "url":
            out.append({"name": node.get("name", ""), "url": node.get("url", "")[:200]})
        for v in node.values():
            _extract_bookmark_urls(v, out, max_depth, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _extract_bookmark_urls(item, out, max_depth, depth + 1)


def _get_system_preferences():
    """Get key system preferences."""
    prefs = {}
    try:
        if platform.system() == "Darwin":
            # Dark mode
            out = _run("defaults read -g AppleInterfaceStyle 2>/dev/null")
            prefs["dark_mode"] = out.lower() == "dark"
            # Default browser
            out = _run("defaults read com.apple.LaunchServices/com.apple.launchservices.secure LSHandlers 2>/dev/null | grep -B1 'https' | grep 'LSHandlerRoleAll' | head -1")
            if "chrome" in out.lower():
                prefs["default_browser"] = "Chrome"
            elif "safari" in out.lower():
                prefs["default_browser"] = "Safari"
            elif "firefox" in out.lower():
                prefs["default_browser"] = "Firefox"
            elif "edge" in out.lower():
                prefs["default_browser"] = "Edge"
        elif platform.system() == "Windows":
            # Default browser via registry
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice")
                prog_id = winreg.QueryValueEx(key, "ProgID")[0]
                prefs["default_browser"] = prog_id
                winreg.CloseKey(key)
            except Exception:
                pass
    except Exception:
        pass
    return prefs


def build_full_profile():
    """Build a complete device profile."""
    t0 = time.time()
    profile = {
        "timestamp": time.time(),
        "hardware": _get_hw_info(),
        "user": _get_user_info(),
        "apps": _get_installed_apps(),
        "processes": _get_running_processes(),
        "network": _get_network_info(),
        "recent_files": _get_recent_files(),
        "preferences": _get_system_preferences(),
        "bookmarks": _get_browser_bookmarks(),
    }
    profile["profile_time_ms"] = round((time.time() - t0) * 1000)
    return profile


def get_profile_summary(profile):
    """Build a natural language summary of the device for JARVIS."""
    hw = profile.get("hardware", {})
    user = profile.get("user", {})
    apps = profile.get("apps", [])
    net = profile.get("network", {})
    procs = profile.get("processes", [])

    parts = []
    parts.append(f"User: {user.get('full_name') or user.get('username', 'unknown')}")
    parts.append(f"OS: {hw.get('system', '?')} {hw.get('release', '?')} ({hw.get('machine', '?')})")
    if hw.get("ram_gb"):
        parts.append(f"RAM: {hw['ram_gb']}GB")
    if hw.get("cpu_cores"):
        parts.append(f"CPU cores: {hw['cpu_cores']}")
    if hw.get("disk_free_gb"):
        parts.append(f"Disk free: {hw['disk_free_gb']}GB / {hw.get('disk_total_gb', '?')}GB")
    if hw.get("battery") is not None:
        parts.append(f"Battery: {hw['battery']}%")
    if net.get("wifi_ssid"):
        parts.append(f"WiFi: {net['wifi_ssid']}")
    if net.get("local_ip"):
        parts.append(f"Local IP: {net['local_ip']}")

    # Top app categories
    cats = {}
    for app in apps:
        cat = app.get("category", "other")
        cats[cat] = cats.get(cat, 0) + 1
    if cats:
        top_cats = sorted(cats.items(), key=lambda x: -x[1])[:5]
        parts.append(f"App categories: {', '.join(f'{c}({n})' for c, n in top_cats)}")

    # Notable apps
    notable = [a["name"] for a in apps if a.get("category") in ("development", "creative", "gaming", "security")][:10]
    if notable:
        parts.append(f"Notable apps: {', '.join(notable)}")

    # Running top processes
    if procs:
        top_procs = [p.get("name") or p.get("command", "")[:30] for p in procs[:5]]
        parts.append(f"Top running: {', '.join(top_procs)}")

    return "\n".join(parts)
