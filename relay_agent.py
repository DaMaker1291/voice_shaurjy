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
import ssl

# SSL context — try certifi first, fall back to unverified
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()
    try:
        _SSL_CTX.load_default_certs()
    except:
        _SSL_CTX = ssl._create_unverified_context()

def _urlopen(req_or_url, **kwargs):
    kwargs.setdefault("context", _SSL_CTX)
    kwargs.setdefault("timeout", 30)
    return urllib.request.urlopen(req_or_url, **kwargs)

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-jarvis-ai-brain.hf.space").rstrip("/")


def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with _urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get(url):
    with _urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def get_text(url):
    with _urlopen(url, timeout=20) as r:
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
        "notify_persistent": lambda: _notify_window(params),
        "notify_center": lambda: _notify_window(params),
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

        # Network & Smart Home
        "network_scan_quick": lambda: run("arp -a"),
        "network_scan_deep": lambda: run("nmap -sn -T4 --host-timeout 5 $(ipconfig getifaddr en0 2>/dev/null | awk -F. '{print $1\".\"$2\".\"$3\".0/24\"}') 2>/dev/null | grep -E 'Nmap|Host|MAC' | head -60"),
        "wake_on_lan": lambda: _send_wol(params),
        "smart_home_discover": lambda: _sh_discover(),
        "smart_home_control": lambda: _sh_control(params),
        "camera_snap": lambda: run("which imagesnap && imagesnap -w 1 ~/Desktop/jarvis_cam.jpg 2>/dev/null || ffmpeg -f avfoundation -framerate 1 -video_size 640x480 -i '0' -frames:v 1 ~/Desktop/jarvis_cam.jpg -y 2>/dev/null; echo 'Photo taken'"),
        "phone_notify": lambda: _phone_notify(params),
        "who_is_online": lambda: run("arp -a | grep -v incomplete | head -20"),
        "system_load": lambda: run("top -l 1 -n 0 -nocolor 2>/dev/null | head -10; echo '---'; df -h /; echo '---'; uptime"),

        # ── UI Automation (Computer Vision + Mouse/Keyboard) ──
        "ui_screenshot": lambda: run("screencapture -x /tmp/jv_screen.png && echo '/tmp/jv_screen.png'"),
        "ui_get_text": lambda: _ui_get_text(),
        "ui_find": lambda: _ui_find(params),
        "ui_click": lambda: _ui_click(params),
        "ui_type": lambda: run(f"osascript -e 'tell application \"System Events\" to keystroke \"{params[:300].replace(chr(34),chr(39))}\"' 2>/dev/null"),
        "ui_click_text": lambda: _ui_click_text(params),
        "ui_handwrite": lambda: _ui_handwrite(params),
        "ui_drag": lambda: _ui_drag(params),
        "ui_open_app": lambda: _mac_open_app(params),
        "ui_activate_app": lambda: run(f"osascript -e 'tell application \"{params}\" to activate' 2>/dev/null"),
        "ui_app_running": lambda: run(f"osascript -e 'tell application \"System Events\" to exists process \"{params}\"' 2>/dev/null"),

        # ── Phone Bridge (ADB over WiFi) ──
        "phone_adb_connect": lambda: _phone_adb_connect(params),
        "phone_read_sms": lambda: _phone_adb("content query --uri content://sms/inbox --projection address,body,date --sort date DESC --limit 10 2>/dev/null"),
        "phone_get_notifications": lambda: _phone_adb("dumpsys notification --naked 2>/dev/null | grep -A 5 'tickerText=|title=|text=' | head -60"),
        "phone_call_log": lambda: _phone_adb("content query --uri content://call_log/calls --projection number,type,duration,date --sort date DESC --limit 10 2>/dev/null"),
        "phone_battery": lambda: _phone_adb("shell dumpsys battery 2>/dev/null | grep -E 'level|status|powered'"),

        # ── Home Assistant Integration ──
        "ha_discover": lambda: _ha_discover(),
        "ha_status": lambda: _ha_api("", "GET"),
        "ha_control": lambda: _ha_control(params),
        "ha_sensors": lambda: _ha_api("states", "GET"),

        # ── Cognitive Surveillance ──
        "cognitive_scan": lambda: _cognitive_scan(),
        "cognitive_insight": lambda: _cognitive_insight(),
    }

def _send_wol(mac: str) -> str:
    import socket as _s, struct as _st
    mac = mac.replace(":", "").replace("-", "")
    if len(mac) != 12: return f"Invalid MAC: {mac}"
    packet = b"\xff" * 6 + bytes.fromhex(mac) * 16
    try:
        with _s.socket(_s.AF_INET, _s.SOCK_DGRAM) as s:
            s.setsockopt(_s.SOL_SOCKET, _s.SO_BROADCAST, 1)
            s.sendto(packet, ("255.255.255.255", 9))
        return f"WoL sent to {mac}"
    except Exception as e:
        return f"WoL error: {e}"

def _sh_discover() -> str:
    ips = run("arp -a | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -20")
    if not ips: return "No devices on LAN"
    found = []
    for ip in ips.split():
        for port, name in [(80,"HTTP"),(443,"HTTPS"),(8123,"HomeAssistant"),(6053,"ESPHome"),(9999,"Kasa")]:
            r = run(f"curl -s --max-time 2 http://{ip}:{port}/ 2>/dev/null | head -1")
            if r:
                found.append(f"{ip}:{port} ({name})")
                break
    if found: return "Smart devices:\n" + "\n".join(found)
    return f"Scanned {len(ips.split())} hosts. No smart services found.\n{ips}"

def _sh_control(params: str) -> str:
    parts = params.split()
    if len(parts) < 2: return "Usage: ip on|off|toggle|status"
    ip, action = parts[0], parts[1].lower()
    results = []
    if action in ("on", "off"):
        state = "true" if action == "on" else "false"
        r1 = run(f"curl -s --max-time 2 -H 'Content-Type: application/json' -d '{{\"on\":{state}}}' http://{ip}/json/state 2>/dev/null")
        r2 = run(f"curl -s --max-time 2 -X PUT -H 'Content-Type: application/json' -d '{{\"on\":{state}}}' http://{ip}/api/newdeveloper/groups/0/action 2>/dev/null")
        results.append(f"{action.capitalize()}")
    elif action == "toggle":
        r = run(f"curl -s --max-time 2 http://{ip}/toggle 2>/dev/null")
        results.append("Toggled")
    elif action == "status":
        st = run(f"curl -s --max-time 2 http://{ip}/json/info 2>/dev/null | head -10")
        results.append(f"Status:\n{st[:500]}")
    return "\n".join(results) if results else f"No response from {ip}"

def _phone_notify(msg: str) -> str:
    topic = f"jarvis_{platform.node().split('.')[0]}"
    run(f'curl -s -d "{msg[:500].replace(chr(34),chr(39))}" "https://ntfy.sh/{topic}" 2>/dev/null')
    return f"Notification sent to ntfy.sh/{topic}. Subscribe on your phone!"

def _notify_window(msg: str) -> str:
    """Show a persistent floating notification window (centre-screen, always-on-top, draggable)."""
    np_path = os.path.join(os.path.dirname(__file__), "backend", "notification_window.py")
    if not os.path.isfile(np_path):
        return f"Notification window script not found at {np_path}"
    escaped = msg[:500].replace("'", "'\\''")
    run(f"python3 '{np_path}' '{escaped}' &", timeout=2)
    return f"Notification window: '{msg[:60]}'"

def _ui_get_text() -> str:
    """OCR the screen and return all text."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
        from ui_automation import get_screen_text
        return get_screen_text()
    except: pass
    return run("screencapture -x /tmp/jv_screen.png 2>/dev/null && which tesseract && tesseract /tmp/jv_screen.png stdout 2>/dev/null || echo 'OCR not available'")

def _ui_find(text: str) -> str:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
        from ui_automation import find_text_on_screen
        el = find_text_on_screen(text)
        if el: return f"Found '{el['text']}' at ({el['x']},{el['y']}) size {el['width']}x{el['height']}"
        return f"'{text}' not found on screen"
    except: return f"UI find error"

def _ui_click(params: str) -> str:
    """Click at x,y coordinates. Format: 'x y' or 'x y button' (button: left/right/double)."""
    parts = params.split()
    if len(parts) < 2: return "Usage: ui_click x y [button]"
    x, y = parts[0], parts[1]
    btn = parts[2].lower() if len(parts) > 2 else "left"
    if btn == "right":
        run(f"osascript -e 'tell application \"System Events\" to click at {{{x},{y}}}' 2>/dev/null")
    elif btn == "double":
        run(f"osascript -e 'tell application \"System Events\" to double click at {{{x},{y}}}' 2>/dev/null")
    else:
        run(f"osascript -e 'tell application \"System Events\" to click at {{{x},{y}}}' 2>/dev/null")
    return f"Clicked ({x},{y})"

def _ui_click_text(text: str) -> str:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
        from ui_automation import click_text
        found = click_text(text, timeout=5)
        return f"Clicked '{text}'" if found else f"'{text}' not found"
    except: return f"Click text error"

def _ui_handwrite(params: str) -> str:
    """Handwrite text on screen. Format: 'text|start_x|start_y' or 'text' (uses center)."""
    parts = params.split("|")
    text = parts[0]
    x = int(parts[1]) if len(parts) > 1 else 400
    y = int(parts[2]) if len(parts) > 2 else 400
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
        from ui_automation import handwrite_text
        handwrite_text(text, x, y)
        return f"Handwriting: '{text[:50]}' at ({x},{y})"
    except Exception as e:
        return f"Handwriting error: {e}"

def _ui_drag(params: str) -> str:
    """Drag from (x1,y1) to (x2,y2). Format: 'x1 y1 x2 y2'."""
    parts = params.split()
    if len(parts) < 4: return "Usage: ui_drag x1 y1 x2 y2"
    x1, y1, x2, y2 = parts[:4]
    run(f"osascript -e 'tell application \"System Events\" to drag from {{{x1},{y1}}} to {{{x2},{y2}}}' 2>/dev/null")
    return f"Dragged ({x1},{y1}) -> ({x2},{y2})"

def _phone_adb(cmd: str) -> str:
    """Execute an ADB command (requires WiFi ADB connected)."""
    r = run(f"adb shell {cmd} 2>/dev/null", timeout=15)
    return r if r else "ADB not available. Connect phone: adb connect <phone_ip>:5555"

def _phone_adb_connect(phone_ip: str) -> str:
    if not phone_ip: return "Usage: phone_adb_connect <phone_ip>"
    r = run(f"adb connect {phone_ip}:5555 2>/dev/null", timeout=10)
    return f"ADB connect: {r}" if r else "ADB not installed"

def _ha_discover() -> str:
    ips = run("arp -a | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -20")
    for ip in (ips or "").split():
        r = run(f"curl -s --max-time 2 http://{ip}:8123/api/ 2>/dev/null")
        if r and "message" in r.lower() or "api" in r.lower() or "config" in r.lower():
            return f"Home Assistant found at {ip}:8123"
        r2 = run(f"curl -s --max-time 2 http://{ip}:8123/ 2>/dev/null | head -1")
        if r2 and "home" in r2.lower():
            return f"Home Assistant found at {ip}:8123"
    return "No Home Assistant instance found on LAN"

def _ha_api(endpoint: str, method: str = "GET") -> str:
    token = os.environ.get("HA_TOKEN", "")
    host = os.environ.get("HA_HOST", "")
    if not host:
        ips = run("arp -a | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -20")
        for ip in (ips or "").split():
            r = run(f"curl -s --max-time 2 http://{ip}:8123/api/ 2>/dev/null")
            if r:
                host = f"http://{ip}:8123"
                break
    if not host: return "Home Assistant not found"
    url = f"{host}/api/{endpoint}" if endpoint else host + "/api/"
    headers = f'-H "Authorization: Bearer {token}"' if token else ""
    r = run(f"curl -s --max-time 5 {headers} '{url}' 2>/dev/null | head -50")
    return r or f"No response from {url}"

def _ha_control(params: str) -> str:
    """Control Home Assistant entity. Format: 'entity_id state' or 'entity_id attribute value'."""
    parts = params.split()
    if len(parts) < 2: return "Usage: ha_control entity_id state [attributes...]"
    entity, state = parts[0], parts[1]
    data = json.dumps({"state": state})
    token = os.environ.get("HA_TOKEN", "")
    host = os.environ.get("HA_HOST", "http://localhost:8123")
    headers = f'-H "Authorization: Bearer {token}" -H "Content-Type: application/json"' if token else '-H "Content-Type: application/json"'
    r = run(f"curl -s --max-time 5 -X POST {headers} -d '{data}' '{host}/api/states/{entity}' 2>/dev/null")
    return f"HA: {entity} -> {state}" if r else f"HA control failed for {entity}"

def _cognitive_scan() -> str:
    """Scan environment: check windows, doors, lights, network, system."""
    lines = []
    lines.append("=== COGNITIVE ENVIRONMENT SCAN ===")
    lines.append(f"Time: {run('date')}")
    lines.append(f"System: {run('uptime')}")
    lines.append(f"Network: {run('arp -a')}")
    lines.append(f"Active users: {run('who')}")
    _wincmd = """osascript -e 'tell application "System Events" to get name of every process whose visible is true' 2>/dev/null"""
    lines.append(f"Open windows: {run(_wincmd)}")
    lines.append(f"WiFi: {run('/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null | grep -E \"SSID|agrCtlRSSI|state\"')}")
    lines.append(f"Battery: {run('pmset -g batt 2>/dev/null')}")
    lines.append(f"Disk: {run('df -h / | tail -1')}")
    return "\n".join(lines)

def _cognitive_insight() -> str:
    """Generate a synthesized insight about the user's environment."""
    scan = _cognitive_scan()
    try:
        import urllib.request
        payload = json.dumps({"text": f"Analyze this environment scan and produce ONE concise, useful insight (1 sentence):\n{scan[:800]}", "user_id": "jarvis", "tier": "free"}).encode()
        req = urllib.request.Request(f"{HF_API}/api/text/chat", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with _urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            return f"[INSIGHT] {resp.get('text', 'Analysis complete')[:300]}"
    except:
        return "[INSIGHT] Environment scanned. All systems nominal."

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
