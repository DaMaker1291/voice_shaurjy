"""
Relay agent — runs on macOS/Windows, polls HF Space for actions, executes locally.
Now with autonomous startup scan + macOS support.

USAGE:
  python relay_agent.py --user <user_id>
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

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-jarvis-ai-brain.hf.space").rstrip("/")


def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def get_text(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read().decode()


def run(cmd: str, timeout=15) -> str:
    """Run a shell command and return output."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            return out
        return err or f"Exit code {r.returncode}"
    except subprocess.TimeoutExpired:
        return "(timed out)"
    except Exception as e:
        return f"Error: {e}"


def macos_exec(action: str, params: str = "") -> str:
    """Execute macOS-specific actions using osascript/open/shell."""
    p = platform.system()
    if p != "Darwin":
        return f"Not available on {p}"

    actions: dict[str, callable] = {
        "screenshot": lambda: run("screencapture -x ~/Desktop/jarvis_screenshot.png 2>/dev/null; echo 'Saved to Desktop'"),
        "open_url": lambda: run(f"open '{params}'") if params else "Open what?",
        "search": lambda: _mac_search(params, "https://google.com/search?q="),
        "search_youtube": lambda: _mac_search(params, "https://youtube.com/results?search_query="),
        "search_wiki": lambda: _mac_search(params, "https://en.wikipedia.org/wiki/"),
        "search_amazon": lambda: _mac_search(params, "https://amazon.com/s?k="),
        "search_news": lambda: _mac_search(params, "https://news.google.com/search?q="),
        "search_maps": lambda: _mac_search(params, "https://maps.google.com/maps?q="),
        "whoami": lambda: run("whoami"),
        "uptime": lambda: run("uptime"),
        "system_info": lambda: (
            run("sw_vers") + "\n" + run("uname -a") + "\n" + run("sysctl -n hw.memsize hw.ncpu 2>/dev/null")
        ),
        "battery_status": lambda: run("pmset -g batt 2>/dev/null || echo 'No battery'"),
        "disk_info": lambda: run("df -h /"),
        "memory_info": lambda: run("vm_stat | head -10"),
        "process_list": lambda: run("ps aux --sort=-%cpu | head -20"),
        "wifi_list": lambda: run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s 2>/dev/null || echo 'airport not found'"),
        "network_info": lambda: run("ifconfig en0 2>/dev/null || ifconfig en1 2>/dev/null || networksetup -getinfo Wi-Fi"),
        "speak": lambda: run(f"say '{params[:200].replace(chr(39), '')}'"),
        "notify": lambda: run(f"osascript -e 'display notification \"{params[:200].replace(chr(34), '')}\" with title \"J.A.R.V.I.S.\" 2>/dev/null'"),
        "lock_screen": lambda: run("/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend 2>/dev/null || echo 'Lock not supported'"),
        "volume_set": lambda: run(f"osascript -e 'set volume output volume {params}'"),
        "volume_up": lambda: run("osascript -e 'set volume output volume (output volume of (get volume settings) + 10)'"),
        "volume_down": lambda: run("osascript -e 'set volume output volume (output volume of (get volume settings) - 10)'"),
        "volume_mute": lambda: run("osascript -e 'set volume output muted true'"),
        "brightness_set": lambda: run(f"osascript -e 'tell application \"System Events\" to set brightness of first display to {params}' 2>/dev/null || echo 'brightness not available'"),
        "public_ip": lambda: get_text("https://api.ipify.org"),
        "time": lambda: __import__("datetime").datetime.now().strftime("%A, %B %d, %Y — %I:%M %p"),
        "weather": lambda: run("curl -s 'wttr.in?format=%C+%t+%w' 2>/dev/null || echo 'Weather unavailable'"),
        "open_app": lambda: _mac_open_app(params),
        "finder_open": lambda: run(f"open '{params}'") if params else "Open what?",
    }

    fn = actions.get(action)
    if fn:
        try:
            return str(fn())
        except Exception as e:
            return f"macOS action error: {e}"
    return None


def _mac_search(query: str, base_url: str) -> str:
    q = query.replace("search", "").replace("youtube", "").replace("wikipedia", "").strip()
    if not q:
        q = query
    import urllib.parse
    run(f"open '{base_url}{urllib.parse.quote(q)}'")
    return f"Searching for \"{q}\"..."


def _mac_open_app(name: str) -> str:
    """Open a macOS app by name."""
    name = name.lower().strip()
    apps = {
        "safari": "Safari", "chrome": "Google Chrome", "firefox": "Firefox",
        "terminal": "Terminal", "vs code": "Visual Studio Code",
        "code": "Visual Studio Code", "finder": "Finder",
        "spotify": "Spotify", "music": "Music", "photos": "Photos",
        "settings": "System Settings", "system settings": "System Settings",
        "notes": "Notes", "calendar": "Calendar", "mail": "Mail",
        "messages": "Messages", "maps": "Maps", "facetime": "FaceTime",
    }
    app_name = apps.get(name, name)
    r = run(f'open -a "{app_name}"', timeout=10)
    return f"Opened {app_name}" if r else f"Could not open {app_name}"


def startup_scan(user_id: str) -> dict:
    """Run initial device scan and return results."""
    print("[Relay] Running startup device scan...")
    results = {}
    checks = [
        ("whoami", "whoami"),
        ("hostname", lambda: socket.gethostname()),
        ("os", lambda: f"{platform.system()} {platform.release()} ({platform.version()})"),
        ("uptime", lambda: run("uptime")),
        ("public_ip", lambda: get_text("https://api.ipify.org")),
    ]
    for name, fn in checks:
        try:
            results[name] = str(fn()) if callable(fn) else run(fn)
        except Exception as e:
            results[name] = f"Error: {e}"
    return results


def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Relay Agent")
    parser.add_argument("--user", default="local", help="Your user ID")
    args = parser.parse_args()
    user_id = args.user

    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
        print(f"[Relay] Connected to {HF_API} as user '{user_id}'")
    except socket.gaierror:
        print(f"[Relay] DNS failed for {hostname}")
        return

    # Run startup scan and register device
    device_info = startup_scan(user_id)
    try:
        post(f"{HF_API}/api/relay/register", {
            "user_id": user_id,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "info": device_info,
        })
        print(f"[Relay] Device registered: {device_info.get('hostname', '?')}")
    except Exception as e:
        print(f"[Relay] Registration failed: {e} (continuing...)")

    # Try to import backend actions for full action support
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    has_actions = False
    if os.path.isdir(backend_dir) and os.path.isfile(os.path.join(backend_dir, "actions.py")):
        sys.path.insert(0, backend_dir)
        has_actions = True

    print(f"[Relay] Polling every 0.5s for user '{user_id}'...")
    while True:
        try:
            resp = get(f"{HF_API}/api/relay/pending?user_id={user_id}")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                print(f"[Relay] Executing: {act} ({params[:50] if params else ''})")

                result = None

                # 1. Try macOS native executors first
                if platform.system() == "Darwin":
                    result = macos_exec(act, params)

                # 2. Try backend actions (import from actions.py)
                if result is None and has_actions:
                    try:
                        from actions import execute_action
                        result = execute_action(act, params or act)
                    except Exception as e:
                        result = f"Action error: {e}"

                # 3. Fallback: try shell
                if result is None:
                    if platform.system() == "Darwin":
                        result = run(f"open '{params}'") if params else f"Unknown action: {act}"
                    else:
                        result = f"Unknown action: {act}"

                post(f"{HF_API}/api/relay/result",
                     {"relay_id": rid, "result": str(result)[:2000], "success": True})
                print(f"[Relay] Done: {act} -> {str(result)[:80]}")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[Relay] Backend returned {e.code}: {e.reason}")
        except Exception as e:
            print(f"[Relay] Error: {e}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
