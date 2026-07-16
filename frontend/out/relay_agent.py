"""
JARVIS Sovereign Relay Agent — runs on your local machine.
Polls the Hugging Face Space for actions, executes them locally,
and reports results back.

USAGE (Windows PowerShell):
  curl.exe -sL 'https://dgfhgjhj-jarvis-ai-brain.hf.space/relay' -o $env:TEMP\relay.py; python $env:TEMP\relay.py --user local

USAGE (macOS/Linux):
  curl -sL 'https://dgfhgjhj-jarvis-ai-brain.hf.space/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user local
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import ssl
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# ── SSL ───────────────────────────────────────────────────────────────────
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[Relay] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("jarvis-relay")

# ── Config ────────────────────────────────────────────────────────────────
HF_API = os.environ.get(
    "HF_API_URL",
    "https://dgfhgjhj-jarvis-ai-brain.hf.space",
).rstrip("/")

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# ── HTTP helpers ──────────────────────────────────────────────────────────
def _urlopen(req_or_url, **kwargs):
    kwargs.setdefault("context", _SSL_CTX)
    kwargs.setdefault("timeout", 20)
    return urllib.request.urlopen(req_or_url, **kwargs)

def post(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _urlopen(req) as r:
        return json.loads(r.read())

def get(url: str) -> dict:
    with _urlopen(url) as r:
        return json.loads(r.read())

# ── System info ───────────────────────────────────────────────────────────
def get_system_info() -> dict:
    """Gather basic system information."""
    import shutil
    ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else 0
    if IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            ram = mem.ullTotalPhys
        except Exception:
            pass
    try:
        usage = shutil.disk_usage("/")
        disk_total, disk_free = usage.total, usage.free
    except Exception:
        disk_total = disk_free = 0
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "unknown",
        "hostname": socket.gethostname(),
        "ram_bytes": ram,
        "disk_total": disk_total,
        "disk_free": disk_free,
        "python": platform.python_version(),
        "user": os.getenv("USERNAME") or os.getenv("USER") or "unknown",
    }

# ── Device discovery ─────────────────────────────────────────────────────
def discover_devices() -> list:
    """Discover local network devices via ARP table."""
    devices = []
    try:
        if IS_WINDOWS:
            out = subprocess.check_output(["arp", "-a"], text=True, timeout=10, creationflags=0x08000000)
        else:
            out = subprocess.check_output(["arp", "-a"], text=True, timeout=10)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[0].strip("()")
                mac = parts[1] if len(parts) > 1 else ""
                if mac and mac != "(incomplete)" and ":" in mac:
                    devices.append({"ip": ip, "mac": mac})
    except Exception as e:
        log.warning(f"ARP scan failed: {e}")
    return devices

# ── Action executor ──────────────────────────────────────────────────────
def execute_action(action: str, params: str = "") -> str:
    """Execute an action locally on this machine."""
    if isinstance(params, str):
        try:
            params = json.loads(params) if params else {}
        except (json.JSONDecodeError, TypeError):
            params = {"raw": params}
    if not isinstance(params, dict):
        params = {"raw": str(params)}

    # ── System info ──
    if action == "system_info":
        return json.dumps(get_system_info())

    # ── Device discovery ──
    if action == "discover_devices":
        return json.dumps(discover_devices())

    # ── Screenshot ──
    if action == "take_screenshot":
        return _take_screenshot(params)

    # ── Open app ──
    if action in ("open_app", "launch_app"):
        app = params.get("app", params.get("raw", ""))
        return _open_app(app)

    # ── Volume ──
    if action == "set_volume":
        level = params.get("level", params.get("raw", "50"))
        return _set_volume(int(str(level).replace("%", "")))

    # ── WiFi ──
    if action == "wifi_scan":
        return _wifi_scan()
    if action == "wifi_connect":
        ssid = params.get("ssid", "")
        password = params.get("password", "")
        return _wifi_connect(ssid, password)

    # ── Process ──
    if action == "list_processes":
        return _list_processes()
    if action == "kill_process":
        name = params.get("name", params.get("raw", ""))
        return _kill_process(name)

    # ── Disk cleanup ──
    if action == "disk_scan":
        return _disk_scan()
    if action == "disk_clean":
        return _disk_clean(params)

    # ── Shell command ──
    if action in ("run_command", "shell_command", "execute"):
        cmd = params.get("command", params.get("raw", ""))
        return _run_command(cmd)

    # ── Mouse/keyboard ──
    if action == "mouse_click":
        return _mouse_click(params.get("x", 0), params.get("y", 0))
    if action == "keyboard_type":
        return _keyboard_type(params.get("text", params.get("raw", "")))
    if action == "keyboard_shortcut":
        return _keyboard_shortcut(params.get("keys", params.get("raw", "")))

    return json.dumps({"error": f"Unknown action: {action}"})


# ── Platform-specific executors ──────────────────────────────────────────
def _take_screenshot(params: dict) -> str:
    out = params.get("output", os.path.join(os.path.expanduser("~"), "jarvis_screenshot.png"))
    try:
        if IS_MACOS:
            subprocess.check_call(["screencapture", "-x", out], timeout=10)
        elif IS_WINDOWS:
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(out)
            except ImportError:
                powershell = (
                    "Add-Type -Assembly System.Windows.Forms;"
                    "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds | ForEach-Object {"
                    "  $bmp = New-Object System.Drawing.Bitmap($_.Width, $_.Height);"
                    "  $gfx = [System.Drawing.Graphics]::FromImage($bmp);"
                    "  $gfx.CopyFromScreen($_.Location, [System.Drawing.Point]::Empty, $_.Size);"
                    f"  $bmp.Save('{out}');"
                    "}"
                )
                subprocess.check_call(["powershell", "-Command", powershell], timeout=15, creationflags=0x08000000)
        else:
            subprocess.check_call(["import", "-window", "root", out], timeout=10)
        return json.dumps({"status": "ok", "path": out})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _open_app(app: str) -> str:
    app = app.strip()
    if not app:
        return json.dumps({"error": "No app specified"})
    try:
        if IS_MACOS:
            subprocess.Popen(["open", "-a", app])
        elif IS_WINDOWS:
            # Try common Windows apps
            win_apps = {
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "edge": "msedge.exe",
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "explorer": "explorer.exe",
                "cmd": "cmd.exe",
                "terminal": "wt.exe",
                "vscode": "code",
                "spotify": "spotify.exe",
                "outlook": "outlook.exe",
                "word": "winword.exe",
                "excel": "excel.exe",
                "powerpoint": "powerpnt.exe",
            }
            exe = win_apps.get(app.lower(), app)
            subprocess.Popen(["cmd", "/c", "start", "", exe], shell=False)
        else:
            subprocess.Popen([app])
        return json.dumps({"status": "ok", "app": app})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _set_volume(level: int) -> str:
    level = max(0, min(100, level))
    try:
        if IS_MACOS:
            subprocess.check_call(["osascript", "-e", f"set volume output volume {level}"], timeout=5)
        elif IS_WINDOWS:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = iface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        else:
            subprocess.check_call(["amixer", "set", "Master", f"{level}%"], timeout=5)
        return json.dumps({"status": "ok", "volume": level})
    except ImportError:
        return json.dumps({"error": "pycaw not installed (pip install pycaw)"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _wifi_scan() -> str:
    try:
        if IS_MACOS:
            out = subprocess.check_output(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "scan"],
                text=True, timeout=15,
            )
            networks = []
            for line in out.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    networks.append({"ssid": parts[0], "signal": parts[2]})
            return json.dumps(networks)
        elif IS_WINDOWS:
            out = subprocess.check_output(["netsh", "wlan", "show", "networks", "mode=bssid"], text=True, timeout=15)
            networks = []
            current = {}
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("SSID") and "BSSID" not in line:
                    if current:
                        networks.append(current)
                    current = {"ssid": line.split(":", 1)[-1].strip()}
                elif "Signal" in line:
                    current["signal"] = line.split(":", 1)[-1].strip()
            if current:
                networks.append(current)
            return json.dumps(networks)
        else:
            out = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi"], text=True, timeout=15)
            networks = []
            for line in out.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 2:
                    networks.append({"ssid": parts[0], "signal": parts[1]})
            return json.dumps(networks)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _wifi_connect(ssid: str, password: str) -> str:
    if not ssid:
        return json.dumps({"error": "No SSID provided"})
    try:
        if IS_MACOS:
            subprocess.check_call(
                ["networksetup", "-setairportnetwork", "en0", ssid, password], timeout=30,
            )
        elif IS_WINDOWS:
            profile = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <MSM><security>
    <authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption></authEncryption>
    <sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>{password}</keyMaterial></sharedKey>
  </security></MSM>
</WLANProfile>"""
            profile_path = os.path.join(os.environ.get("TEMP", "."), "wifi_temp.xml")
            with open(profile_path, "w") as f:
                f.write(profile)
            subprocess.check_call(["netsh", "wlan", "add", "profile", f"filename={profile_path}"], timeout=10)
            subprocess.check_call(["netsh", "wlan", "connect", f"name={ssid}"], timeout=15)
            os.remove(profile_path)
        else:
            subprocess.check_call(
                ["nmcli", "dev", "wifi", "connect", ssid, "password", password], timeout=30,
            )
        return json.dumps({"status": "ok", "ssid": ssid})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _list_processes() -> str:
    try:
        if IS_WINDOWS:
            out = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"], text=True, timeout=10, creationflags=0x08000000,
            )
            procs = []
            for line in out.strip().split("\n"):
                parts = line.strip().strip('"').split('","')
                if len(parts) >= 2:
                    procs.append({"name": parts[0], "pid": parts[1]})
            return json.dumps(procs[:30])
        else:
            out = subprocess.check_output(["ps", "aux", "--sort=-pcpu"], text=True, timeout=10)
            lines = out.strip().split("\n")[1:21]
            procs = []
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    procs.append({"user": parts[0], "cpu": parts[2], "mem": parts[3], "name": parts[10]})
            return json.dumps(procs)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _kill_process(name: str) -> str:
    if not name:
        return json.dumps({"error": "No process name"})
    try:
        if IS_WINDOWS:
            subprocess.check_call(["taskkill", "/F", "/IM", f"{name}.exe"], timeout=10, creationflags=0x08000000)
        else:
            subprocess.check_call(["pkill", "-f", name], timeout=10)
        return json.dumps({"status": "ok", "killed": name})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _disk_scan() -> str:
    """Scan disk for cleanable files."""
    import time as _time
    now = _time.time()
    results = {"categories": {}, "total_bytes": 0}

    # Browser caches (cross-platform)
    browser_cache_dirs = {}
    if IS_MACOS:
        browser_cache_dirs = {
            "~/Library/Caches/Google/Chrome": "Chrome Cache",
            "~/Library/Caches/Firefox": "Firefox Cache",
            "~/Library/Caches/com.apple.Safari": "Safari Cache",
            "~/Library/Caches/com.microsoft.edgemac": "Edge Cache",
        }
    elif IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        browser_cache_dirs = {
            f"{local}/Google/Chrome/User Data/Default/Cache": "Chrome Cache",
            f"{local}/Mozilla/Firefox/Profiles": "Firefox Cache",
            f"{local}/Microsoft/Edge/User Data/Default/Cache": "Edge Cache",
        }
    else:
        home = os.path.expanduser("~")
        browser_cache_dirs = {
            f"{home}/.cache/google-chrome": "Chrome Cache",
            f"{home}/.cache/mozilla/firefox": "Firefox Cache",
            f"{home}/.cache/microsoft-edge": "Edge Cache",
        }

    for path_template, label in browser_cache_dirs.items():
        path = os.path.expanduser(path_template)
        if os.path.exists(path):
            try:
                size = _get_dir_size(path)
                if size > 0:
                    results["categories"][label] = {"path": path, "bytes": size, "human": _human_size(size)}
                    results["total_bytes"] += size
            except (OSError, PermissionError):
                pass

    # System temp
    temp_dirs = ["/tmp", os.path.expanduser("~/Library/TemporaryFiles")]
    if IS_WINDOWS:
        temp_dirs.append(os.environ.get("TEMP", ""))
    temp_total = 0
    for td in temp_dirs:
        if not td or not os.path.exists(td):
            continue
        try:
            for entry in os.scandir(td):
                if entry.is_file():
                    try:
                        age_days = (now - entry.stat().st_mtime) / 86400
                        if age_days > 1:
                            size = entry.stat().st_size
                            temp_total += size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
    if temp_total > 0:
        results["categories"]["Temp Files (>1 day)"] = {"bytes": temp_total, "human": _human_size(temp_total)}
        results["total_bytes"] += temp_total

    # npm/pip/yarn caches
    cache_dirs = {}
    home = os.path.expanduser("~")
    cache_dirs[f"{home}/.npm/_cacache"] = "npm Cache"
    cache_dirs[f"{home}/.cache/pip"] = "pip Cache"
    cache_dirs[f"{home}/.yarn/cache"] = "Yarn Cache"
    for path, label in cache_dirs.items():
        if os.path.exists(path):
            try:
                size = _get_dir_size(path)
                if size > 0:
                    results["categories"][label] = {"path": path, "bytes": size, "human": _human_size(size)}
                    results["total_bytes"] += size
            except (OSError, PermissionError):
                pass

    results["total_human"] = _human_size(results["total_bytes"])
    return json.dumps(results)


def _disk_clean(params: dict) -> str:
    """Clean specified disk categories. Requires confirm=true."""
    if not params.get("confirm"):
        return json.dumps({"error": "Set confirm=true to proceed with cleaning"})
    # Actual cleaning delegated to the backend via the action system
    return json.dumps({"status": "delegated_to_backend"})


def _run_command(cmd: str) -> str:
    if not cmd:
        return json.dumps({"error": "No command"})
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
            creationflags=0x08000000 if IS_WINDOWS else 0,
        )
        return json.dumps({
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "code": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Command timed out"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _mouse_click(x: int, y: int) -> str:
    try:
        if IS_WINDOWS:
            import ctypes
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
        elif IS_MACOS:
            subprocess.check_call(["cliclick", f"c:{x},{y}"], timeout=5)
        else:
            subprocess.check_call(["xdotool", "mousemove", str(x), str(y), "click", "1"], timeout=5)
        return json.dumps({"status": "ok", "x": x, "y": y})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _keyboard_type(text: str) -> str:
    try:
        if IS_WINDOWS:
            import ctypes
            for ch in text:
                ctypes.windll.user32.keybd_event(ord(ch), 0, 0, 0)
                ctypes.windll.user32.keybd_event(ord(ch), 0, 0x0002, 0)
        elif IS_MACOS:
            subprocess.check_call(["cliclick", f"t:{text}"], timeout=10)
        else:
            subprocess.check_call(["xdotool", "type", "--clearmodifiers", text], timeout=10)
        return json.dumps({"status": "ok", "typed": len(text)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _keyboard_shortcut(keys: str) -> str:
    try:
        if IS_WINDOWS:
            import ctypes
            modifier_map = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}
            parts = [k.strip().lower() for k in keys.split("+")]
            vk_codes = []
            for p in parts:
                if p in modifier_map:
                    vk_codes.append(modifier_map[p])
                elif len(p) == 1:
                    vk_codes.append(ord(p.upper()))
            for vk in vk_codes:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            for vk in reversed(vk_codes):
                ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)
        elif IS_MACOS:
            subprocess.check_call(["cliclick", f"kd:cmd,t:{keys},ku:cmd"], timeout=5)
        else:
            subprocess.check_call(["xdotool", "key", keys], timeout=5)
        return json.dumps({"status": "ok", "shortcut": keys})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Helpers ───────────────────────────────────────────────────────────────
def _get_dir_size(path: str) -> int:
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += _get_dir_size(entry.path)
    except (OSError, PermissionError):
        pass
    return total


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


# ── Main loop ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="JARVIS Sovereign Relay Agent")
    parser.add_argument("--user", default="local", help="Your user ID")
    parser.add_argument("--install", action="store_true", help="Install dependencies and exit")
    parser.add_argument("--discover", action="store_true", help="Discover devices and exit")
    args = parser.parse_args()
    user_id = args.user

    if args.install:
        log.info("Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "fastapi", "uvicorn", "python-dotenv", "pydantic",
                        "psutil", "websocket-client", "certifi", "Pillow"])
        if IS_WINDOWS:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pywin32", "pycaw"])
        log.info("Dependencies installed.")
        return

    if args.discover:
        log.info("Discovering devices...")
        devices = discover_devices()
        for d in devices:
            log.info(f"  {d['ip']} — {d['mac']}")
        log.info(f"Found {len(devices)} devices.")
        return

    # DNS check
    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
    except socket.gaierror:
        log.error(f"DNS failed for {hostname}. Check URL: {HF_API}")
        return

    log.info(f"Connected to {HF_API} as user '{user_id}'")
    log.info(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    log.info("Polling every 0.5s...")

    # Immediate registration with system info
    try:
        info = get_system_info()
        devices = discover_devices()
        post(f"{HF_API}/api/relay/register", {
            "user_id": user_id,
            "system_info": info,
            "devices": devices,
        })
        log.info(f"Registered: {info['hostname']} ({info['platform']})")
    except Exception as e:
        log.warning(f"Registration failed: {e}")

    while True:
        try:
            resp = get(f"{HF_API}/api/relay/pending?user_id={user_id}")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                log.info(f"Executing: {act}")
                try:
                    result = execute_action(act, params)
                    post(f"{HF_API}/api/relay/result", {
                        "relay_id": rid,
                        "result": result,
                        "success": True,
                    })
                    log.info(f"Done: {act}")
                except Exception as e:
                    post(f"{HF_API}/api/relay/result", {
                        "relay_id": rid,
                        "result": f"Error: {e}",
                        "success": False,
                    })
                    log.error(f"Failed: {act} — {e}")

            # Heartbeat
            try:
                post(f"{HF_API}/api/relay/heartbeat", {"user_id": user_id})
            except Exception:
                pass

        except urllib.error.HTTPError as e:
            log.warning(f"Backend returned {e.code}: {e.reason}")
        except Exception:
            pass

        time.sleep(0.5)


if __name__ == "__main__":
    main()
