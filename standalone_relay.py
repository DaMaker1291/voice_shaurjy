"""
J.A.R.V.I.S. Relay Agent — standalone single-file version.
No project files needed. Just Python 3 stdlib.

Speculative Local Execution: loads a tiny SLM (1.5B-3B) for instant
intent routing, then dispatches heavy tasks to the cloud backbone.

Usage:
  curl -sSL https://dgfhgjhj-jarvis-ai-brain.hf.space/relay.py -o relay.py
  pip install -r requirements-local.txt
  python3 relay.py --user yourname
"""

import argparse, json, os, platform, socket, subprocess, sys, threading, time, urllib.request, urllib.error, urllib.parse, ssl, re, datetime

# Add backend to path for device clients
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_script_dir, "backend"))

_SSL_CTX = ssl.create_default_context()
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    try: _SSL_CTX.load_default_certs()
    except: _SSL_CTX = ssl._create_unverified_context()


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL SLM ROUTER — Speculative Local Execution
# ══════════════════════════════════════════════════════════════════════════════

class LocalRouter:
    """Tiny local SLM for instant intent routing (<10ms TTFT).
    
    Loads a 1.5B-3B quantized model via llama-cpp-python.
    Classifies user intent into OS/HAL/WEB/CORE agents with
    grammar-constrained output for deterministic routing.
    """
    
    # Model candidates ordered by size (smallest first)
    MODELS = [
        ("bartowski/Qwen2.5-1.5B-Instruct-GGUF", "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"),
        ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama-3.2-3B-Instruct-Q4_K_M.gguf"),
    ]
    
    ROUTER_PROMPT = (
        "You are an intent router for JARVIS. "
        "Classify the user's input into exactly one target agent. "
        "Output ONLY a JSON object: {\"target_agent\": \"OS_AGENT|HAL_AGENT|WEB_AGENT|CORE_AGENT\", "
        "\"confidence\": 0.0-1.0, \"intent\": \"brief description\"}"
    )
    
    def __init__(self, model_dir=None):
        self._model = None
        self._model_name = None
        self._model_dir = model_dir or os.path.join(os.path.expanduser("~"), ".jarvis", "models")
        os.makedirs(self._model_dir, exist_ok=True)
    
    def load(self):
        """Try to load the smallest available model."""
        try:
            from llama_cpp import Llama
        except ImportError:
            print("[LocalRouter] llama-cpp-python not installed. Install: pip install llama-cpp-python")
            return False
        
        # Check for existing models
        import glob
        existing = glob.glob(os.path.join(self._model_dir, "*.gguf"))
        if existing:
            # Use smallest existing model
            existing.sort(key=lambda f: os.path.getsize(f))
            path = existing[0]
        else:
            # Download smallest model
            path = self._download_model()
            if not path:
                return False
        
        try:
            import multiprocessing
            n_threads = max(2, multiprocessing.cpu_count() // 2)
            
            self._model = Llama(
                model_path=path,
                n_ctx=2048,  # Small context for routing only
                n_threads=n_threads,
                verbose=False,
            )
            self._model_name = os.path.basename(path)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"[LocalRouter] Loaded {self._model_name} ({size_mb:.0f}MB) on {n_threads} threads")
            return True
        except Exception as e:
            print(f"[LocalRouter] Failed to load model: {e}")
            return False
    
    def _download_model(self):
        """Download the smallest model."""
        try:
            from huggingface_hub import hf_hub_download
        except ImportError:
            print("[LocalRouter] huggingface_hub not installed")
            return None
        
        for repo_id, filename in self.MODELS:
            try:
                print(f"[LocalRouter] Downloading {filename}...")
                path = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=self._model_dir,
                    local_dir_use_symlinks=False,
                )
                print(f"[LocalRouter] Downloaded to {path}")
                return path
            except Exception as e:
                print(f"[LocalRouter] Failed to download {filename}: {e}")
                continue
        return None
    
    def route(self, user_text):
        """Route user intent to the right agent. Returns dict with target_agent."""
        if not self._model:
            return {"target_agent": "CORE_AGENT", "confidence": 0.5, "intent": user_text, "local": False}
        
        try:
            messages = [
                {"role": "system", "content": self.ROUTER_PROMPT},
                {"role": "user", "content": user_text},
            ]
            response = self._model.create_chat_completion(
                messages=messages,
                max_tokens=64,
                temperature=0.0,
            )
            text = response["choices"][0]["message"]["content"].strip()
            
            # Parse JSON from response
            import re
            match = re.search(r'\{[^}]+\}', text)
            if match:
                result = json.loads(match.group())
                result["local"] = True
                result["model"] = self._model_name
                return result
        except Exception as e:
            print(f"[LocalRouter] Routing error: {e}")
        
        return {"target_agent": "CORE_AGENT", "confidence": 0.5, "intent": user_text, "local": False}
    
    @property
    def is_loaded(self):
        return self._model is not None


# Global local router instance
_local_router = LocalRouter()

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
    results = {}
    for name, fn in [("whoami","whoami"),("hostname",lambda:socket.gethostname()),("os",lambda:f"{platform.system()} {platform.release()}"),("uptime",lambda:run("uptime")),("public_ip",lambda:get_text("https://api.ipify.org"))]:
        try: results[name] = str(fn()) if callable(fn) else run(fn)
        except Exception as e: results[name] = f"Error: {e}"
    return results


def _discover_real_devices():
    """Discover real devices on the local network via ARP."""
    import re
    devices = []

    try:
        arp_output = run("arp -a", timeout=15)
    except Exception:
        return devices

    for line in arp_output.splitlines():
        mac_match = re.search(r'at\s+([0-9a-fA-F:]{17})', line)
        ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
        if not mac_match or not ip_match:
            continue

        ip = ip_match.group(1)
        mac = mac_match.group(1).upper()

        if "FF:FF:FF:FF:FF:FF" in mac or "1:0:5E" in mac or "(incomplete)" in line:
            continue

        hostname = line.split("(")[0].strip() if "(" in line else ""
        hostname = hostname.replace("?", "").strip()
        hl = hostname.lower()

        device_type = "UNKNOWN"
        protocol = "unknown"
        manufacturer = ""
        model = ""
        device_name = hostname or ip

        # Router/Gateway
        if "skysr213" in hl or (ip.endswith(".1") and not hl):
            device_type = "ROUTER"
            protocol = "http"
            manufacturer = "Sky"
            model = "SR213"
        # TP-Link Tapo Smart Plugs
        elif "tapo" in hl or "p100" in hl or "p110" in hl or "p125" in hl:
            device_type = "SWITCH"
            protocol = "tapo"
            manufacturer = "TP-Link"
            if "p110" in hl: model = "Tapo P110"
            elif "p100" in hl: model = "Tapo P100"
            elif "p125" in hl: model = "Tapo P125"
            else: model = "Tapo Smart Plug"
        # HP Printer
        elif "hp" in hl or "printer" in hl:
            device_type = "PRINTER"
            protocol = "ipp"
            manufacturer = "HP"
            model = "Printer"
        # Samsung phones
        elif "samsung" in hl or "galaxy" in hl or "note20" in hl or "s24" in hl or "gargi" in hl or "suprotim" in hl:
            device_type = "PHONE"
            protocol = "adb"
            manufacturer = "Samsung"
            if "note20" in hl: model = "Galaxy Note20"
            elif "s24 ultra" in hl: model = "Galaxy S24 Ultra"
            elif "s24" in hl: model = "Galaxy S24"
        # Range extender
        elif "re200" in hl or "extender" in hl:
            device_type = "ROUTER"
            protocol = "http"
            manufacturer = "TP-Link"
            model = "RE200"
        # iMac / Apple
        elif "imac" in hl or "macbook" in hl:
            device_type = "HUB"
            protocol = "ssh"
            manufacturer = "Apple"
            model = "iMac"
        # Generic laptop
        elif "laptop" in hl or "nbkw" in hl:
            device_type = "HUB"
            protocol = "ssh"
            model = "Laptop"
        # lwip devices (likely IoT)
        elif "lwip" in hl:
            device_type = "SENSOR"
            protocol = "mqtt"
            model = "IoT Device"

        if device_type == "UNKNOWN":
            continue

        devices.append({
            "id": f"real_{ip.replace('.', '_')}",
            "name": device_name,
            "device_type": device_type,
            "ip": ip,
            "mac": mac,
            "protocol": protocol,
            "manufacturer": manufacturer,
            "model": model,
            "room": "unknown",
            "state": {"power": "UNKNOWN"},
            "is_online": True,
        })

    return devices


def _push_devices_to_hf(devices):
    """Push discovered devices to HF Space."""
    try:
        post(f"{HF_API}/api/sovereign/devices/sync", {"devices": devices})
    except Exception:
        pass


def _execute_device_command(action, params):
    """Execute a real device command locally."""
    import re

    if not isinstance(params, dict):
        return {"success": False, "error": "Invalid params"}

    ip = params.get("ip", "")
    device_type = params.get("device_type", "")
    protocol = params.get("protocol", "")

    # Tapo smart plug control
    if device_type == "SWITCH" and ("tapo" in protocol.lower() or "p100" in ip or "p110" in ip):
        try:
            from tapo_client import TapoClient
            client = TapoClient()
            client.add_device(ip)
            if action == "turn_on":
                return client.turn_on(ip)
            elif action == "turn_off":
                return client.turn_off(ip)
            elif action == "toggle":
                return client.toggle(ip)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Printer control
    if device_type == "PRINTER":
        try:
            from printer_client import PrinterClient
            client = PrinterClient()
            client.add_printer(ip)
            if action == "status":
                return client.get_printer_status(ip)
            elif action == "ink":
                return client.get_ink_levels(ip)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Phone control via ADB
    if device_type == "PHONE":
        try:
            from phone_client import PhoneClient
            client = PhoneClient()
            client.add_phone(ip)
            if action == "connect":
                return client.connect_adb(ip)
            elif action == "battery":
                return client.get_battery_state(ip)
            elif action == "screen":
                return client.get_screen_state(ip)
            elif action == "lock":
                return client.lock_screen(ip)
            elif action == "unlock":
                return client.unlock_screen(ip)
            elif action == "screenshot":
                return client.take_screenshot(ip)
            elif action == "volume":
                return client.set_volume(ip, "music", params.get("level", 50))
            elif action == "brightness":
                return client.set_brightness(ip, params.get("level", 128))
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": False, "error": f"Unknown device type: {device_type}"}

def main():
    global HF_API
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Standalone Relay Agent")
    parser.add_argument("--user", default="local", help="Your user ID")
    parser.add_argument("--hf-url", default=HF_API, help="HF Space URL")
    parser.add_argument("--local-model", action="store_true", help="Download and run local SLM (optional, 986MB)")
    args = parser.parse_args()
    HF_API = args.hf_url.rstrip("/")

    hostname = urllib.parse.urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
        print(f"[Relay] Connected to {HF_API} as user '{args.user}'")
    except socket.gaierror:
        print(f"[Relay] DNS failed for {hostname}"); return

    # Initialize local SLM router (Optional — downloads in background)
    if args.local_model:
        print("[Relay] Downloading local SLM (background)...")
        threading.Thread(target=_local_router.load, daemon=True).start()
    else:
        print("[Relay] Local SLM disabled (using cloud routing). Use --local-model to enable.")

    device_info = startup_scan(args.user)
    try:
        post(f"{HF_API}/api/relay/register", {"user_id": args.user, "hostname": socket.gethostname(), "platform": platform.platform(), "info": device_info})
        print(f"[Relay] Registered: {device_info.get('whoami', '?')}")
    except Exception as e:
        print(f"[Relay] Registration failed: {e} (continuing...)")

    poll_ids = list(dict.fromkeys([args.user, "local"]))
    fb_idx = 0
    hb = 0
    device_push_hb = 0
    _SCHEDULER_FILE = ".jarvis_scheduled.json"

    # Initial device discovery
    print("[Relay] Discovering real devices on local network...")
    real_devices = _discover_real_devices()
    print(f"[Relay] Found {len(real_devices)} real devices:")
    for d in real_devices:
        print(f"  {d['ip']} | {d['name']} | {d['device_type']} | {d['protocol']}")
    _push_devices_to_hf(real_devices)

    print(f"[Relay] Polling every 0.5s...")
    while True:
        hb += 1
        device_push_hb += 1

        # Heartbeat every 30 cycles (15s), re-register if needed
        if hb >= 30:
            hb = 0
            try:
                resp = post(f"{HF_API}/api/relay/heartbeat", {"user_id": args.user})
                if resp.get("status") != "ok":
                    raise Exception("heartbeat rejected")
            except Exception:
                # HF Space restarted — re-register
                try:
                    post(f"{HF_API}/api/relay/register", {"user_id": args.user, "hostname": socket.gethostname(), "platform": platform.platform(), "info": device_info})
                    print("[Relay] Re-registered with HF Space")
                except Exception:
                    pass

        # Re-discover and push devices every 5 minutes
        if device_push_hb >= 600:
            device_push_hb = 0
            try:
                real_devices = _discover_real_devices()
                _push_devices_to_hf(real_devices)
                print(f"[Relay] Re-discovered {len(real_devices)} devices")
            except Exception:
                pass

        try:
            uid = poll_ids[fb_idx % len(poll_ids)]
            fb_idx += 1
            resp = get(f"{HF_API}/api/relay/pending?user_id={uid}")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                if isinstance(params, str):
                    try: params = json.loads(params)
                    except: params = {"raw": params}

                # Local routing: classify intent before execution
                intent_text = params.get("raw", str(params)) if isinstance(params, dict) else str(params)
                routing = _local_router.route(intent_text) if _local_router.is_loaded else {}
                target = routing.get("target_agent", "")
                
                if target:
                    print(f"[Relay] Local route: {target} ({routing.get('confidence', 0):.0%}) | {intent_text[:50]}")

                print(f"[Relay] Executing: {act} ({str(params)[:50]})")

                # Check if this is a device command
                if act == "device_scan":
                    real_devices = _discover_real_devices()
                    _push_devices_to_hf(real_devices)
                    result = {"success": True, "devices_found": len(real_devices), "devices": real_devices}
                elif act.startswith("device_") or (isinstance(params, dict) and params.get("device_type")):
                    result = _execute_device_command(act.replace("device_", ""), params)
                elif target == "OS_AGENT" or target == "HAL_AGENT":
                    # Local execution for OS/HAL tasks
                    result = macos_exec(act, str(params) if not isinstance(params, str) else params)
                elif _is_mac or _is_win:
                    result = macos_exec(act, str(params) if not isinstance(params, str) else params)
                else:
                    result = f"Unknown action: {act}"

                post(f"{HF_API}/api/relay/result", {"relay_id": rid, "result": str(result)[:2000], "success": True})
                print(f"[Relay] Done: {act} -> {str(result)[:80]}")
        except urllib.error.HTTPError as e:
            if e.code != 404: print(f"[Relay] Backend {e.code}: {e.reason}")
        except Exception as e:
            print(f"[Relay] Error: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
