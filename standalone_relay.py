"""
J.A.R.V.I.S. Relay Agent — standalone single-file version.
No project files needed. Just Python 3 stdlib.

Usage:
  curl -sSL https://dgfhgjhj-jarvis-ai-brain.hf.space/relay.py -o relay.py
  python3 relay.py --user yourname
"""

import argparse, json, os, platform, socket, subprocess, sys, threading, time, urllib.request, urllib.error, ssl, re, datetime

_SSL_CTX = ssl.create_default_context()
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    try: _SSL_CTX.load_default_certs()
    except: _SSL_CTX = ssl._create_unverified_context()

def _urlopen(req_or_url, **kwargs):
    kwargs.setdefault("context", _SSL_CTX)
    kwargs.setdefault("timeout", 30)
    return urllib.request.urlopen(req_or_url, **kwargs)

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-jarvis-ai-brain.hf.space").rstrip("/")

def post(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"}, method="POST")
    with _urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def get(url):
    with _urlopen(url, timeout=20) as r:
        return json.loads(r.read())

def get_text(url):
    with _urlopen(url, timeout=20) as r:
        return r.read().decode()

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr or f"Exit {r.returncode}").strip()
    except subprocess.TimeoutExpired: return "(timed out)"
    except Exception as e: return f"Error: {e}"

_is_mac = platform.system() == "Darwin"
_is_win = platform.system() == "Windows"

def _speak(text):
    if not text: return ""
    try:
        subprocess.run(["say", "-v", "Samantha"], input=text[:200].encode("utf-8"), timeout=30)
        return f'Speaking: "{text[:60]}..."'
    except: return "Speak unavailable"

def _mac_search(query, base_url):
    q = query.replace("search","").replace("youtube","").replace("wikipedia","").strip() or query
    run(f"open '{base_url}{urllib.parse.quote(q)}'")
    return f"Searching \"{q}\"..."

def _open_app(name):
    if _is_win:
        return run(f"start \"\" \"{name}\"")
    run(f'open -a "{name}"', timeout=10)
    return f"Opened {name}"

def _send_wol(mac):
    mac = mac.replace(":","").replace("-","")
    if len(mac) != 12: return f"Invalid MAC: {mac}"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.sendto(b"\xff"*6 + bytes.fromhex(mac)*16, ("255.255.255.255", 9))
    s.close()
    return f"WoL sent to {mac}"

def macos_exec(action, params=""):
    if _is_win: return _win_exec(action, params)
    import urllib.parse
    actions = {
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
        "system_info": lambda: run("sw_vers") + "\n" + run("uname -a"),
        "battery_status": lambda: run("pmset -g batt 2>/dev/null || echo 'No battery'"),
        "disk_info": lambda: run("df -h /"),
        "memory_info": lambda: run("vm_stat | head -10"),
        "process_list": lambda: run("ps aux --sort=-%cpu | head -20"),
        "wifi_list": lambda: run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s 2>/dev/null || echo 'airport not found'"),
        "network_info": lambda: run("ifconfig en0 2>/dev/null || ifconfig en1 2>/dev/null || networksetup -getinfo Wi-Fi"),
        "speak": lambda: _speak(params[:200]),
        "notify": lambda: run(f"osascript -e 'display notification \"{params[:200]}\" with title \"J.A.R.V.I.S.\" 2>/dev/null'"),
        "lock": lambda: run("""osascript -e 'tell application "System Events" to keystroke "q" using {command down, control down}' 2>/dev/null || pmset displaysleepnow 2>/dev/null || echo 'Lock not supported'"""),
        "volume_set": lambda: run(f"osascript -e 'set volume output volume {params}'"),
        "volume_up": lambda: run("osascript -e 'set volume output volume (output volume of (get volume settings) + 10)'"),
        "volume_down": lambda: run("osascript -e 'set volume output volume (output volume of (get volume settings) - 10)'"),
        "volume_mute": lambda: run("osascript -e 'set volume output muted true'"),
        "brightness_set": lambda: run(f"osascript -e 'tell app \"System Events\" to set brightness of first display to {params}' 2>/dev/null || echo 'n/a'"),
        "public_ip": lambda: get_text("https://api.ipify.org"),
        "time": lambda: datetime.datetime.now().strftime("%A, %B %d, %Y — %I:%M %p"),
        "weather": lambda: run("curl -s 'wttr.in?format=%C+%t+%w' 2>/dev/null || echo 'n/a'"),
        "open_app": lambda: _open_app(params),
        "finder_open": lambda: run(f"open '{params}'") if params else "Open what?",
        "network_scan_quick": lambda: run("arp -a"),
        "network_scan_deep": lambda: _net_scan_deep(),
        "wake_on_lan": lambda: _send_wol(params),
        "camera_snap": lambda: run("which imagesnap && imagesnap -w 1 ~/Desktop/jarvis_cam.jpg 2>/dev/null || ffmpeg -f avfoundation -framerate 1 -video_size 640x480 -i '0' -frames:v 1 ~/Desktop/jarvis_cam.jpg -y 2>/dev/null; echo 'Photo taken'"),
        "who_is_online": lambda: run("arp -a | grep -v incomplete | head -20"),
        "system_load": lambda: run("top -l 1 -n 0 -nocolor 2>/dev/null | head -10; echo '---'; df -h /; echo '---'; uptime"),
        "ui_screenshot": lambda: run("screencapture -x /tmp/jv_screen.png && echo '/tmp/jv_screen.png'"),
        "ui_type": lambda: run(f"osascript -e 'tell app \"System Events\" to keystroke \"{params[:300]}\"' 2>/dev/null"),
        "ui_click": lambda: _ui_click(params),
        "ui_open_app": lambda: _open_app(params),
        "ui_activate_app": lambda: run(f"osascript -e 'tell app \"{params}\" to activate' 2>/dev/null"),
        "cognitive_scan": lambda: _cognitive_scan(),
    }
    fn = actions.get(action)
    if fn:
        try: return str(fn())
        except Exception as e: return f"Action error: {e}"
    return None

def _win_exec(action, params=""):
    actions = {
        "screenshot": lambda: run("powershell -Command \"Add-Type -AssemblyName System.Windows.Forms; $s=[Windows.Forms.Screen]::PrimaryScreen.Bounds; $b=New-Object Drawing.Bitmap $s.Width,$s.Height; $g=[Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$s.Size); $b.Save('$env:USERPROFILE\\Desktop\\jarvis_screenshot.png')\""),
        "whoami": lambda: run("whoami"),
        "uptime": lambda: run("net statistics workstation | find 'since'"),
        "system_info": lambda: run("systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\" /C:\"System Type\""),
        "public_ip": lambda: get_text("https://api.ipify.org"),
        "time": lambda: datetime.datetime.now().strftime("%A, %B %d, %Y — %I:%M %p"),
        "open_app": lambda: run(f"start \"\" \"{params}\""),
        "network_scan_quick": lambda: run("arp -a"),
        "volume_set": lambda: run(f"powershell -Command \"(New-Object -ComObject WScript.Shell).SendKeys([char]175)\""),
        "volume_mute": lambda: run("powershell -Command \"(New-Object -ComObject WScript.Shell).SendKeys([char]173)\""),
        "lock": lambda: run("rundll32.exe user32.dll,LockWorkStation"),
    }
    fn = actions.get(action)
    if fn:
        try: return str(fn())
        except Exception as e: return f"Win action error: {e}"
    return None

def _ui_click(params):
    parts = params.split()
    if len(parts) < 2: return "Usage: ui_click x y [button]"
    x, y = parts[0], parts[1]
    if _is_mac:
        run(f"osascript -e 'tell app \"System Events\" to click at {{{x},{y}}}' 2>/dev/null")
    elif _is_win:
        run(f"powershell -Command \"Add-Type -AssemblyName System.Windows.Forms; [Windows.Forms.Cursor]::Position = New-Object Drawing.Point {x},{y}; [Windows.Forms.SendKeys]::SendWait('{chr(123)}')\"")
    return f"Clicked ({x},{y})"

def _net_scan_deep():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except: ip = ""
    if not ip: return "No network. Ensure Wi-Fi/Ethernet is connected."
    base = ".".join(ip.split(".")[:3]) + ".0/24"
    if _is_mac:
        r = run(f"arp -a | grep -oE '\\b([0-9]{{1,3}}\\.){{3}}[0-9]{{1,3}}\\b' | sort -u", timeout=15)
    elif _is_win:
        r = run("arp -a", timeout=15)
    else:
        r = run("arp -n 2>/dev/null || arp -a", timeout=15)
    return f"Network scan of {base}:\n{r}" if r else f"No hosts found on {base}"

def _cognitive_scan():
    lines = [ "=== COGNITIVE ENVIRONMENT SCAN ===", f"Time: {run('date')}", f"System: {run('uptime')}", f"Network: {run('arp -a')}", f"Active users: {run('who')}" ]
    if _is_mac:
        osascript_cmd = "osascript -e 'tell app \"System Events\" to get name of every process whose visible is true' 2>/dev/null"
        lines.append(f"Open windows: {run(osascript_cmd)}")
        wifi_cmd = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null | grep -E 'SSID|agrCtlRSSI|state'"
        lines.append(f"WiFi: {run(wifi_cmd)}")
        lines.append(f"Battery: {run('pmset -g batt 2>/dev/null')}")
    lines.append(f"Disk: {run('df -h / | tail -1')}")
    return "\n".join(lines)

def startup_scan(user_id):
    print("[Relay] Running startup scan...")
    import urllib.parse
    results = {}
    for name, fn in [("whoami","whoami"),("hostname",lambda:socket.gethostname()),("os",lambda:f"{platform.system()} {platform.release()}"),("uptime",lambda:run("uptime")),("public_ip",lambda:get_text("https://api.ipify.org"))]:
        try: results[name] = str(fn()) if callable(fn) else run(fn)
        except Exception as e: results[name] = f"Error: {e}"
    return results

def main():
    global HF_API
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Standalone Relay Agent")
    parser.add_argument("--user", default="local", help="Your user ID")
    parser.add_argument("--hf-url", default=HF_API, help="HF Space URL")
    args = parser.parse_args()
    HF_API = args.hf_url.rstrip("/")

    hostname = urllib.parse.urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
        print(f"[Relay] Connected to {HF_API} as user '{args.user}'")
    except socket.gaierror:
        print(f"[Relay] DNS failed for {hostname}"); return

    import urllib.parse
    device_info = startup_scan(args.user)
    try:
        post(f"{HF_API}/api/relay/register", {"user_id": args.user, "hostname": socket.gethostname(), "platform": platform.platform(), "info": device_info})
        print(f"[Relay] Registered: {device_info.get('whoami', '?')}")
    except Exception as e:
        print(f"[Relay] Registration failed: {e} (continuing...)")

    poll_ids = list(dict.fromkeys([args.user, "local"]))
    fb_idx = 0
    hb = 0
    _SCHEDULER_FILE = ".jarvis_scheduled.json"
    print(f"[Relay] Polling every 0.5s...")
    while True:
        hb += 1
        if hb >= 30:
            hb = 0
            try: post(f"{HF_API}/api/relay/heartbeat", {"user_id": args.user})
            except: pass
        try:
            uid = poll_ids[fb_idx % len(poll_ids)]
            fb_idx += 1
            resp = get(f"{HF_API}/api/relay/pending?user_id={uid}")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                print(f"[Relay] Executing: {act} ({str(params)[:50]})")
                result = None
                if _is_mac or _is_win:
                    result = macos_exec(act, params)
                if result is None:
                    if _is_mac: result = run(f"open '{params}'") if params else f"Unknown: {act}"
                    else: result = f"Unknown action: {act}"
                post(f"{HF_API}/api/relay/result", {"relay_id": rid, "result": str(result)[:2000], "success": True})
                print(f"[Relay] Done: {act} -> {str(result)[:80]}")
        except urllib.error.HTTPError as e:
            if e.code != 404: print(f"[Relay] Backend {e.code}: {e.reason}")
        except Exception as e:
            print(f"[Relay] Error: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
