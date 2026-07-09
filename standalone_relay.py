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

    # Map common names to actual macOS app names
    APP_MAP = {
        "vs code": "Visual Studio Code", "vscode": "Visual Studio Code", "visual studio code": "Visual Studio Code",
        "appcleaner": "AppCleaner", "app cleaner": "AppCleaner",
        "spotify": "Spotify", "chrome": "Google Chrome", "firefox": "Firefox",
        "safari": "Safari", "terminal": "Terminal", "iterm": "iTerm2", "iterm2": "iTerm2",
        "slack": "Slack", "discord": "Discord", "zoom": "zoom.us",
        "figma": "Figma", "notion": "Notion", "obsidian": "Obsidian",
        "finder": "Finder", "preview": "Preview", "calculator": "Calculator",
        "textedit": "TextEdit", "pages": "Pages", "numbers": "Numbers", "keynote": "Keynote",
        "xcode": "Xcode", "android studio": "Android Studio", "intellij": "IntelliJ IDEA",
        "pycharm": "PyCharm", "webstorm": "WebStorm", "sublime": "Sublime Text",
        "word": "Microsoft Word", "excel": "Microsoft Excel", "powerpoint": "Microsoft PowerPoint",
        "outlook": "Microsoft Outlook", "teams": "Microsoft Teams",
        "photoshop": "Adobe Photoshop 2024", "illustrator": "Adobe Illustrator 2024",
        "lightroom": "Adobe Lightroom Classic", "premiere": "Adobe Premiere Pro 2024",
    }

    name_lower = name.lower().strip()
    resolved = APP_MAP.get(name_lower, name)

    # Try the resolved name first
    result = run(f'open -a "{resolved}"', timeout=10)
    if "Unable to find" in result or "does not exist" in result:
        # Try original name
        result = run(f'open -a "{name}"', timeout=10)
    if "Unable to find" in result or "does not exist" in result:
        # Try opening as a URL/file
        result = run(f'open "{name}"', timeout=10)

    return f"Opened {resolved}"

def _send_wol(mac):
    mac = mac.replace(":","").replace("-","")
    if len(mac) != 12: return f"Invalid MAC: {mac}"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.sendto(b"\xff"*6 + bytes.fromhex(mac)*16, ("255.255.255.255", 9))
    s.close()
    return f"WoL sent to {mac}"

# ── Universal Device Discovery & Control ─────────────────────────────

def _universal_scan():
    """Scan entire WiFi network for ALL devices — no login needed."""
    devices = []

    # Phase 1: ARP table (instant)
    arp = run("arp -a", timeout=10)
    for line in arp.split("\n"):
        ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
        mac_match = re.search(r'([0-9a-fA-F:]{17})', line)
        if ip_match:
            ip = ip_match.group(1)
            mac = mac_match.group(1) if mac_match else ""
            name = _identify_device_by_mac(mac) if mac else f"Device ({ip})"
            devices.append({"ip": ip, "name": name, "mac": mac, "type": _type_by_mac(mac)})

    # Phase 2: Probe alive devices
    for dev in devices:
        ip = dev["ip"]
        # Check HTTP
        for port in [80, 8080, 443]:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                conn = http.client.HTTPSConnection(ip, port, timeout=2, context=ctx) if port == 443 else http.client.HTTPConnection(ip, port, timeout=2)
                conn.request("GET", "/")
                resp = conn.getresponse()
                body = resp.read(1000).decode(errors="ignore").lower()
                server = resp.getheader("Server", "").lower()
                if "esphome" in body: dev["type"] = "ESPHOME"; dev["name"] = f"ESPHome ({ip})"
                elif "wled" in body: dev["type"] = "WLED"; dev["name"] = f"WLED Strip ({ip})"
                elif "tapo" in body or "tp-link" in body: dev["type"] = "TAPO"; dev["name"] = f"Tapo ({ip})"
                elif "hue" in body or "philips" in body: dev["type"] = "HUE"; dev["name"] = f"Hue Bridge ({ip})"
                elif "tuya" in body: dev["type"] = "TUYA"; dev["name"] = f"Tuya ({ip})"
                elif "sonos" in body: dev["type"] = "SONOS"; dev["name"] = f"Sonos ({ip})"
                elif "<html" in body: dev["type"] = "HTTP_DEVICE"; dev["name"] = f"Web Device ({ip})"
                conn.close()
                break
            except:
                pass

        # Check MQTT
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            if s.connect_ex((ip, 1883)) == 0:
                dev["type"] = "MQTT_BROKER"; dev["name"] = f"MQTT ({ip})"
            s.close()
        except:
            pass

    # Phase 3: Quick subnet scan for missed devices
    try:
        local_ip = run("ipconfig getifaddr en0 2>/dev/null || ip -4 addr show | grep -oP '(?<=inet )\\d+\\.\\d+\\.\\d+\\.\\d+'")
        subnet = ".".join(local_ip.strip().split(".")[:3]) if local_ip.strip() else "192.168.0"
        # Quick port check on common IPs
        for i in [1, 2, 100, 101, 200, 254]:
            ip = f"{subnet}.{i}"
            if not any(d["ip"] == ip for d in devices):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.3)
                    if s.connect_ex((ip, 80)) == 0 or s.connect_ex((ip, 443)) == 0:
                        devices.append({"ip": ip, "name": f"Device ({ip})", "type": "UNKNOWN"})
                    s.close()
                except:
                    pass
    except:
        pass

    return json.dumps({"devices": devices, "count": len(devices), "scan": "full"})

def _universal_control(params):
    """Control any device using every known protocol."""
    parts = params.split(" ", 2)
    if len(parts) < 2:
        return "Usage: <ip> <action> [params]"
    ip = parts[0]
    action = parts[1].lower()
    extra = parts[2] if len(parts) > 2 else ""

    protocols_tried = []

    # 1. Try HTTP REST
    http_result = _try_http(ip, action)
    if http_result: return f"[HTTP] {http_result}"
    protocols_tried.append("http")

    # 2. Try ESPHome
    esphome_result = _try_esphome(ip, action)
    if esphome_result: return f"[ESPHOME] {esphome_result}"
    protocols_tried.append("esphome")

    # 3. Try WLED
    wled_result = _try_wled(ip, action)
    if wled_result: return f"[WLED] {wled_result}"
    protocols_tried.append("wled")

    # 4. Try Tapo with defaults
    tapo_result = _try_tapo_defaults(ip, action)
    if tapo_result: return f"[TAPO] {tapo_result}"
    protocols_tried.append("tapo")

    # 5. Try UPnP
    upnp_result = _try_upnp(ip, action)
    if upnp_result: return f"[UPNP] {upnp_result}"
    protocols_tried.append("upnp")

    return f"No supported protocol found at {ip}. Tried: {', '.join(protocols_tried)}"

def _try_http(ip, action):
    """Try HTTP control endpoints."""
    endpoints = {
        "on": ["/relay?state=on", "/control?state=on", "/api/relay/on", "/cm?cmnd=Power1%20ON", "/switch/relay/turn_on"],
        "off": ["/relay?state=off", "/control?state=off", "/api/relay/off", "/cm?cmnd=Power1%20OFF", "/switch/relay/turn_off"],
        "toggle": ["/relay?state=toggle", "/toggle", "/api/relay/toggle", "/switch/relay/toggle"],
        "status": ["/status", "/api/status", "/cm?cmnd=Status", "/switch/relay"],
    }
    for ep in endpoints.get(action, []):
        for port in [80, 8080, 8443]:
            try:
                conn = http.client.HTTPConnection(ip, port, timeout=2)
                conn.request("GET", ep)
                r = conn.getresponse()
                if r.status in (200, 201, 202, 204):
                    return r.read().decode(errors="ignore")
                conn.close()
            except:
                pass
    return None

def _try_esphome(ip, action):
    """Try ESPHome native API."""
    try:
        endpoints = {"on": "/switch/relay/turn_on", "off": "/switch/relay/turn_off", "toggle": "/switch/relay/toggle"}
        conn = http.client.HTTPConnection(ip, 80, timeout=2)
        conn.request("GET", endpoints.get(action, "/"))
        r = conn.getresponse()
        if r.status in (200, 201, 202):
            return r.read().decode(errors="ignore")
        conn.close()
    except:
        pass
    return None

def _try_wled(ip, action):
    """Try WLED JSON API."""
    try:
        payloads = {"on": '{"on":true}', "off": '{"on":false}', "toggle": '{"on":true,"bri":255}'}
        if action in payloads:
            conn = http.client.HTTPConnection(ip, 80, timeout=2)
            conn.request("POST", "/json", body=payloads[action], headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            if r.status in (200, 201, 202):
                return r.read().decode(errors="ignore")
            conn.close()
    except:
        pass
    return None

def _try_tapo_defaults(ip, action):
    """Try Tapo with common default credentials."""
    defaults = [("admin", "admin"), ("admin", "password"), ("admin", "1234"), ("tplink", "tplink")]
    for user, pwd in defaults:
        try:
            os.environ["TAPO_USERNAME"] = user
            os.environ["TAPO_PASSWORD"] = pwd
            from tapo_client import TapoClient
            c = TapoClient()
            c.set_credentials(user, pwd)
            if action == "on": r = c.turn_on(ip)
            elif action == "off": r = c.turn_off(ip)
            elif action == "toggle": r = c.toggle(ip)
            else: r = c.get_device_info(ip)
            if r and r.get("success"):
                return f"Tapo ({user}): {r}"
        except:
            pass
    return None

def _try_upnp(ip, action):
    """Try UPnP/SOAP control."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ip, 49152))
        s.send(f"GET /rootDesc.xml HTTP/1.1\r\nHost: {ip}:49152\r\n\r\n".encode())
        resp = s.recv(4096).decode(errors="ignore")
        s.close()
        if "xml" in resp.lower():
            return f"UPnP device found at {ip}"
    except:
        pass
    return None

def _identify_device_by_mac(mac):
    """Identify device by MAC OUI."""
    mac = mac.lower().replace(":", "")[:6]
    oui = {
        "f0272d": "Amazon Echo", "f0f0a4": "Amazon Echo", "443583": "Amazon Echo",
        "b04e26": "TP-Link", "50c7bf": "TP-Link", "14cc20": "TP-Link",
        "001a2b": "Google", "3c5ab4": "Google",
        "dca632": "Raspberry Pi", "b827eb": "Raspberry Pi",
        "001132": "Sonos", "b8e937": "Sonos",
        "0024d7": "Philips Hue", "ecb5fa": "Philips Hue",
        "30b5c2": "TP-Link Tapo",
    }
    for prefix, name in oui.items():
        if mac.startswith(prefix): return name
    return "Network Device"

def _type_by_mac(mac):
    name = _identify_device_by_mac(mac)
    if "Echo" in name: return "ALEXA"
    if "TP-Link" in name: return "TAPO_PLUG"
    if "Sonos" in name: return "SONOS"
    if "Philips" in name: return "HUE_BRIDGE"
    if "Raspberry" in name: return "RASPBERRY_PI"
    return "UNKNOWN"

# ── Alexa WiFi Controller ───────────────────────────────────────────

def _alexa_discover():
    """Discover Echo devices on local network."""
    devices = []

    # Method 1: ARP scan for Amazon devices
    amazon_ouis = ["f0:27:2d", "f0:f0:a4", "44:35:83", "ac:63:be", "84:d6:db",
                   "fc:65:de", "a0:02:dc", "3c:aa:8f", "74:c2:46", "e8:48:b8",
                   "0c:47:3d", "88:71:b1", "d8:72:5a", "e4:7a:2c", "fc:15:b4"]
    arp = run("arp -a", timeout=10)
    for line in arp.split("\n"):
        for oui in amazon_ouis:
            if oui.lower() in line.lower():
                ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                if ip_match:
                    ip = ip_match.group(1)
                    mac = line.split()[3] if len(line.split()) > 3 else ""
                    devices.append({"ip": ip, "name": f"Echo ({ip})", "type": "ALEXA", "mac": mac})
                break

    # Method 2: Check common Echo ports
    if not devices:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet = ".".join(local_ip.split(".")[:3])
            for i in range(1, 255):
                ip = f"{subnet}.{i}"
                # Check if Echo port is open
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.3)
                result = sock.connect_ex((ip, 443))
                if result == 0:
                    # Check if it's an Amazon device
                    try:
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        conn = http.client.HTTPSConnection(ip, 443, timeout=2, context=ctx)
                        conn.request("GET", "/")
                        resp = conn.getresponse()
                        server = resp.getheader("Server", "")
                        if "amazon" in server.lower() or "echo" in server.lower() or "alexa" in server.lower():
                            devices.append({"ip": ip, "name": f"Echo ({ip})", "type": "ALEXA"})
                        conn.close()
                    except:
                        pass
                sock.close()
        except:
            pass

    return json.dumps({"devices": devices, "count": len(devices)})

def _alexa_send_command(ip, endpoint):
    """Send HTTP command to Echo device."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection(ip, 443, timeout=5, context=ctx)
        paths = [f"/api/{endpoint}", f"/{endpoint}", f"/v2/{endpoint}"]
        for path in paths:
            try:
                conn.request("GET", path)
                resp = conn.getresponse()
                if resp.status in (200, 201, 202):
                    return resp.read().decode()
            except:
                continue
        conn.close()
    except:
        pass
    # Fallback to curl
    return run(f'curl -s -k -m 5 "https://{ip}/api/{endpoint}" 2>/dev/null')

def _alexa_speak(params):
    """Make Echo speak text."""
    parts = params.split(" ", 1)
    ip = parts[0] if len(parts) > 1 else ""
    text = parts[1] if len(parts) > 1 else params
    if not ip:
        # Try to find any Echo device
        try:
            result = json.loads(_alexa_discover())
            if result.get("devices"):
                ip = result["devices"][0]["ip"]
        except:
            pass
    if not ip:
        return "No Echo device found. Run alexa_discover first."
    encoded = urllib.parse.quote(text)
    return _alexa_send_command(ip, f"speak/{encoded}") or f"Sent speak command to {ip}"

def _alexa_volume(params):
    """Set Echo volume."""
    parts = params.split()
    ip = parts[0] if len(parts) > 1 else ""
    level = parts[1] if len(parts) > 1 else parts[0]
    if not ip or not level.isdigit():
        return "Usage: alexa_volume <ip> <0-100>"
    alexa_level = int(int(level) * 40 / 100)
    return _alexa_send_command(ip, f"volume/{alexa_level}") or f"Volume set on {ip}"

def _alexa_playback(params, action):
    """Control Echo playback."""
    ip = params.strip()
    if not ip:
        try:
            result = json.loads(_alexa_discover())
            if result.get("devices"):
                ip = result["devices"][0]["ip"]
        except:
            pass
    if not ip:
        return "No Echo device found."
    return _alexa_send_command(ip, f"player/{action}") or f"{action} sent to {ip}"

def _alexa_timer(params):
    """Set a timer on Echo."""
    parts = params.split(" ", 1)
    ip = parts[0] if len(parts) > 1 else ""
    duration = parts[1] if len(parts) > 1 else params
    if not ip:
        try:
            result = json.loads(_alexa_discover())
            if result.get("devices"):
                ip = result["devices"][0]["ip"]
        except:
            pass
    if not ip:
        return "No Echo device found."
    encoded = urllib.parse.quote(duration)
    return _alexa_send_command(ip, f"timer/{encoded}") or f"Timer set on {ip}"

def _alexa_routine(params):
    """Trigger an Alexa routine."""
    parts = params.split(" ", 1)
    ip = parts[0] if len(parts) > 1 else ""
    name = parts[1] if len(parts) > 1 else params
    if not ip:
        try:
            result = json.loads(_alexa_discover())
            if result.get("devices"):
                ip = result["devices"][0]["ip"]
        except:
            pass
    if not ip:
        return "No Echo device found."
    encoded = urllib.parse.quote(name)
    return _alexa_send_command(ip, f"routine/{encoded}") or f"Routine '{name}' triggered on {ip}"

def _alexa_dnd(params):
    """Set Do Not Disturb on Echo."""
    state = "on" if "on" in params.lower() else "off"
    ip = params.replace("on", "").replace("off", "").strip()
    if not ip:
        try:
            result = json.loads(_alexa_discover())
            if result.get("devices"):
                ip = result["devices"][0]["ip"]
        except:
            pass
    if not ip:
        return "No Echo device found."
    return _alexa_send_command(ip, f"dnd/{state}") or f"DND {state} on {ip}"

# ── Autonomous Task Engine ───────────────────────────────────────────

def _get_active_browser():
    result = run("osascript -e 'tell application \"System Events\" to get name of first application process whose frontmost is true'")
    if "Safari" in result: return "Safari"
    if "Chrome" in result: return "Google Chrome"
    if "Firefox" in result: return "Firefox"
    return "Safari"

def _browser_open(url):
    """Open URL in the active browser."""
    b = _get_active_browser()
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    if b == "Safari":
        run(f"osascript -e 'tell application \"Safari\" to activate' -e 'tell application \"Safari\" to set URL of front document to \"{url}\"'")
    elif b == "Google Chrome":
        run(f"osascript -e 'tell application \"Google Chrome\" to activate' -e 'tell application \"Google Chrome\" to set URL of active tab of front window to \"{url}\"'")
    else:
        run(f'open -a "{b}" "{url}"')
    time.sleep(2)
    return f"Opened {url}"

def _browser_get_text():
    """Get text from the active browser tab."""
    b = _get_active_browser()
    if b == "Safari":
        return run('osascript -e \'tell application "Safari" to get text of front document\'', timeout=10)
    elif b == "Google Chrome":
        return run("""osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "document.body.innerText"'""", timeout=10)
    return ""

def _scan_emails_flights():
    """Open Gmail and scan for flight-related emails."""
    _browser_open("https://mail.google.com")
    time.sleep(5)
    text = _browser_get_text()
    flight_kw = ["flight", "boarding", "check-in", "check in", "itinerary", "booking", "airline", "departure", "reservation"]
    matches = [line.strip() for line in text.split("\n") if any(kw in line.lower() for kw in flight_kw)]
    return json.dumps({"found": len(matches) > 0, "items": matches[:10], "preview": text[:500]})

def _scan_photos_passport():
    """Open Google Photos and look for passport/ID photos."""
    _browser_open("https://photos.google.com")
    time.sleep(5)
    text = _browser_get_text()
    kw = ["passport", "id card", "identification", "photo id", "visa"]
    matches = [line.strip() for line in text.split("\n") if any(k in line.lower() for k in kw)]
    return json.dumps({"found": len(matches) > 0, "matches": matches[:10]})

def _ai_computer_task(text):
    """Handle complex autonomous tasks using browser + screen."""
    lower = text.lower()

    # ── Direct app opening (catch "go to outlook", "open VS Code", etc) ──
    go_match = re.match(r'^(?:go\s+to|open|launch|start)\s+(?:the\s+|app\s+)?(.+?)$', lower.strip())
    if go_match:
        app_name = go_match.group(1).strip()
        # Check if it's a website
        sites = {
            "gmail": "https://mail.google.com", "google": "https://google.com",
            "youtube": "https://youtube.com", "outlook": "https://outlook.live.com",
            "photos": "https://photos.google.com", "drive": "https://drive.google.com",
            "calendar": "https://calendar.google.com", "maps": "https://maps.google.com",
            "github": "https://github.com", "twitter": "https://x.com",
            "linkedin": "https://linkedin.com", "facebook": "https://facebook.com",
            "reddit": "https://reddit.com", "netflix": "https://netflix.com",
            "amazon": "https://amazon.com", "apple": "https://apple.com",
            "microsoft": "https://microsoft.com",
        }
        if app_name in sites:
            return _browser_open(sites[app_name])
        # Otherwise try to open as a macOS app
        return _open_app(app_name)

    # Flight/check-in tasks
    if any(kw in lower for kw in ["check in", "check-in", "flight", "boarding", "airline"]):
        if any(kw in lower for kw in ["scan", "email", "find", "search", "look"]):
            return _scan_emails_flights()
        # Full check-in flow — open email first
        result = _scan_emails_flights()
        data = json.loads(result) if isinstance(result, str) else result
        if data.get("found"):
            return f"Found flight emails:\n{json.dumps(data['items'][:5], indent=2)}\n\nI'll now open the airline site. Which airline?"
        return "No flight emails found. Provide the airline website and booking ref, or I'll scan your inbox."

    # Passport/ID photo tasks
    if any(kw in lower for kw in ["passport", "id photo", "identification", "visa photo"]):
        return _scan_photos_passport()

    # Email tasks
    if any(kw in lower for kw in ["check email", "scan email", "read email", "inbox", "any emails"]):
        return _scan_emails_flights()

    # Browser navigation
    if any(kw in lower for kw in ["go to", "open website", "navigate", "browse to"]):
        url_match = re.search(r'https?://\S+', text)
        if url_match:
            return _browser_open(url_match.group())
        site_match = re.search(r'(?:go to|open|navigate to|browse to)\s+(.+?)(?:\s+and|\s+then|$)', lower)
        if site_match:
            site = site_match.group(1).strip()
            sites = {
                "gmail": "https://mail.google.com", "google": "https://google.com",
                "youtube": "https://youtube.com", "outlook": "https://outlook.live.com",
                "photos": "https://photos.google.com", "drive": "https://drive.google.com",
                "calendar": "https://calendar.google.com", "maps": "https://maps.google.com",
                "github": "https://github.com", "twitter": "https://x.com",
                "linkedin": "https://linkedin.com", "facebook": "https://facebook.com",
                "reddit": "https://reddit.com", "netflix": "https://netflix.com",
                "amazon": "https://amazon.com",
            }
            url = sites.get(site, f"https://{site}.com")
            return _browser_open(url)
        return "Where should I navigate?"

    # Screenshot/analysis
    if any(kw in lower for kw in ["screenshot", "what's on screen", "what do you see"]):
        path = "/tmp/jarvis_screen.png"
        run(f"screencapture -x {path}")
        return f"Screenshot saved to {path}"

    # Default: try to navigate to what they mentioned
    _browser_open(text)
    return f"Navigating to: {text}"

def _screen_analyze(text):
    """Capture screen and describe what's visible."""
    path = "/tmp/jarvis_screen.png"
    run(f"screencapture -x {path}")
    return f"Screenshot captured at {path}. Analyzing: {text}"

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
        "device_scan": lambda: _universal_scan(),
        "universal_scan": lambda: _universal_scan(),
        "device_control": lambda: _universal_control(params),
        "wake_on_lan": lambda: _send_wol(params),
        "camera_snap": lambda: run("which imagesnap && imagesnap -w 1 ~/Desktop/jarvis_cam.jpg 2>/dev/null || ffmpeg -f avfoundation -framerate 1 -video_size 640x480 -i '0' -frames:v 1 ~/Desktop/jarvis_cam.jpg -y 2>/dev/null; echo 'Photo taken'"),
        "who_is_online": lambda: run("arp -a | grep -v incomplete | head -20"),
        "system_load": lambda: run("top -l 1 -n 0 -nocolor 2>/dev/null | head -10; echo '---'; df -h /; echo '---'; uptime"),
        "ui_screenshot": lambda: run("screencapture -x /tmp/jv_screen.png && echo '/tmp/jv_screen.png'"),
        "ui_type": lambda: run(f"osascript -e 'tell app \"System Events\" to keystroke \"{params[:300]}\"' 2>/dev/null"),
        "ui_click": lambda: _ui_click(params),
        "ui_open_app": lambda: _open_app(params),
        "ui_activate_app": lambda: run(f"osascript -e 'tell app \"{params}\" to activate' 2>/dev/null"),
        "alexa_discover": lambda: _alexa_discover(),
        "alexa_speak": lambda: _alexa_speak(params),
        "alexa_volume": lambda: _alexa_volume(params),
        "alexa_play": lambda: _alexa_playback(params, "play"),
        "alexa_pause": lambda: _alexa_playback(params, "pause"),
        "alexa_stop": lambda: _alexa_playback(params, "pause"),
        "alexa_next": lambda: _alexa_playback(params, "next"),
        "alexa_prev": lambda: _alexa_playback(params, "previous"),
        "alexa_timer": lambda: _alexa_timer(params),
        "alexa_routine": lambda: _alexa_routine(params),
        "alexa_dnd": lambda: _alexa_dnd(params),
        "ai_computer_task": lambda: _ai_computer_task(params),
        "screen_analyze": lambda: _screen_analyze(params),
        "browser_open": lambda: _browser_open(params),
        "browser_text": lambda: _browser_get_text(),
        "email_scan_flights": lambda: _scan_emails_flights(),
        "photo_scan_passport": lambda: _scan_photos_passport(),
        "cognitive_scan": lambda: _cognitive_scan(),
    }
    fn = actions.get(action)
    if fn:
        try: return str(fn())
        except Exception as e: return f"Action error: {e}"
    return None

def _win_exec(action, params=""):
    # Windows app name resolver — maps common names to actual executables
    WIN_APP_MAP = {
        "vs code": "code", "vscode": "code", "visual studio code": "code",
        "chrome": "chrome", "google chrome": "chrome",
        "firefox": "firefox", "edge": "msedge", "microsoft edge": "msedge",
        "outlook": "outlook", "microsoft outlook": "outlook",
        "teams": "ms-teams", "microsoft teams": "ms-teams",
        "word": "winword", "microsoft word": "winword",
        "excel": "excel", "microsoft excel": "excel",
        "powerpoint": "powerpnt", "microsoft powerpoint": "powerpnt",
        "notepad": "notepad", "notepad++": "notepad++",
        "terminal": "wt", "windows terminal": "wt",
        "powershell": "pwsh", "cmd": "cmd",
        "file explorer": "explorer", "explorer": "explorer",
        "spotify": "spotify", "discord": "discord",
        "slack": "slack", "zoom": "zoom",
        "1password": "1password", "bitwarden": "bitwarden",
        "photoshop": "photoshop", "illustrator": "illustrator",
        "blender": "blender", "figma": "figma",
        "obsidian": "obsidian", "notion": "notion",
        "calculator": "calc", "paint": "mspaint",
        "snipping tool": "snippingtool",
        "task manager": "taskmgr",
        "control panel": "control",
        "settings": "ms-settings:",
    }

    def _open_app_win(name):
        name_lower = name.lower().strip()
        resolved = WIN_APP_MAP.get(name_lower, name)
        # Try Start-Process first (works for most apps)
        r = run(f'powershell -Command "Start-Process \'{resolved}\' -ErrorAction SilentlyContinue"')
        if "error" not in r.lower() and r.strip():
            return f"Opened {name}"
        # Fallback: use start command
        r2 = run(f'start "" "{resolved}"')
        if r2.strip():
            return f"Opened {name}"
        # Last resort: try the original name
        r3 = run(f'start "" "{name}"')
        return f"Attempted to open {name}"

    actions = {
        "screenshot": lambda: run("powershell -Command \"Add-Type -AssemblyName System.Windows.Forms; $s=[Windows.Forms.Screen]::PrimaryScreen.Bounds; $b=New-Object Drawing.Bitmap $s.Width,$s.Height; $g=[Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$s.Size); $b.Save('$env:USERPROFILE\\Desktop\\jarvis_screenshot.png')\""),
        "whoami": lambda: run("whoami"),
        "uptime": lambda: run("net statistics workstation | find 'since'"),
        "system_info": lambda: run("systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\" /C:\"System Type\""),
        "public_ip": lambda: get_text("https://api.ipify.org"),
        "time": lambda: datetime.datetime.now().strftime("%A, %B %d, %Y — %I:%M %p"),
        "open_app": lambda: _open_app_win(params),
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

    # ── System Control (Keyboard/Mouse/Desktop) ──────────────────────
    if device_type == "SYSTEM":
        try:
            if action == "type_text":
                text = params.get("text", "")
                subprocess.run(["osascript", "-e", f'tell application "System Events" to keystroke "{text}"'], timeout=10)
                return {"success": True, "action": "typed", "length": len(text)}

            elif action == "hotkey":
                keys = params.get("keys", [])
                if len(keys) == 2:
                    # Build AppleScript for modifier+key
                    mod_map = {"cmd": "command down", "shift": "shift down", "ctrl": "control down", "alt": "option down"}
                    mod = mod_map.get(keys[0], "")
                    key = keys[1]
                    if mod:
                        script = f'tell application "System Events" to keystroke "{key}" using {mod}'
                    else:
                        script = f'tell application "System Events" to keystroke "{key}"'
                    subprocess.run(["osascript", "-e", script], timeout=10)
                    return {"success": True, "action": "hotkey", "keys": keys}

            elif action == "press_key":
                key = params.get("key", "return")
                key_map = {"return": "return", "enter": "return", "tab": "tab", "escape": "escape",
                           "delete": "delete", "backspace": "delete", "space": "space",
                           "up": "up arrow", "down": "down arrow", "left": "left arrow", "right": "right arrow"}
                mapped = key_map.get(key.lower(), key)
                script = f'tell application "System Events" to key code {mapped}'
                subprocess.run(["osascript", "-e", script], timeout=10)
                return {"success": True, "action": "pressed", "key": key}

            elif action == "launch_app":
                app = params.get("app", "")
                subprocess.run(["open", "-a", app], timeout=10)
                return {"success": True, "action": "launched", "app": app}

            elif action == "quit_app":
                app = params.get("app", "")
                subprocess.run(["osascript", "-e", f'tell application "{app}" to quit'], timeout=10)
                return {"success": True, "action": "quit", "app": app}

            elif action == "frontmost_app":
                result = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
                                       capture_output=True, text=True, timeout=10)
                return {"success": True, "app": result.stdout.strip()}

            elif action == "running_apps":
                result = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every application process'],
                                       capture_output=True, text=True, timeout=10)
                apps = [a.strip() for a in result.stdout.split(",") if a.strip()]
                return {"success": True, "apps": apps}

            elif action == "clipboard_get":
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=10)
                return {"success": True, "content": result.stdout}

            elif action == "clipboard_set":
                text = params.get("text", "")
                proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return {"success": True, "action": "clipboard_set", "length": len(text)}

            elif action == "copy_paste":
                text = params.get("text", "")
                proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                time.sleep(0.1)
                subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'], timeout=10)
                return {"success": True, "action": "paste", "length": len(text)}

            elif action == "screenshot":
                path = params.get("path", f"/tmp/jarvis_screenshot_{int(time.time())}.png")
                subprocess.run(["screencapture", path], timeout=10)
                return {"success": True, "action": "screenshot", "path": path}

            elif action == "mouse_move":
                x, y = params.get("x", 0), params.get("y", 0)
                script = f'tell application "System Events" to set position of mouse to {{{x}, {y}}}'
                subprocess.run(["osascript", "-e", script], timeout=10)
                return {"success": True, "action": "mouse_moved", "x": x, "y": y}

            elif action == "mouse_click":
                x, y = params.get("x", 0), params.get("y", 0)
                # Use cliclick if available, otherwise osascript
                try:
                    subprocess.run(["cliclick", f"c:{x},{y}"], timeout=5)
                except FileNotFoundError:
                    script = f'tell application "System Events" to click at {{{x}, {y}}}'
                    subprocess.run(["osascript", "-e", script], timeout=10)
                return {"success": True, "action": "clicked", "x": x, "y": y}

            elif action == "get_screen_size":
                result = subprocess.run(["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
                                       capture_output=True, text=True, timeout=10)
                return {"success": True, "bounds": result.stdout.strip()}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Screen Perception ─────────────────────────────────────────────
    if device_type == "SCREEN":
        try:
            if action == "screenshot":
                path = params.get("path", f"/tmp/jarvis_screen_{int(time.time())}.png")
                subprocess.run(["screencapture", "-x", path], timeout=10)
                return {"success": True, "path": path}

            elif action == "ocr":
                path = params.get("path", f"/tmp/jarvis_screen_{int(time.time())}.png")
                subprocess.run(["screencapture", "-x", path], timeout=10)
                try:
                    # Copy to local for tesseract path handling
                    local_path = f"/tmp/jarvis_ocr_{os.getpid()}.png"
                    import shutil
                    shutil.copy2(path, local_path)
                    result = subprocess.run(
                        ["tesseract", local_path, "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
                        capture_output=True, text=True, timeout=30, cwd="/tmp"
                    )
                    elements = []
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 12:
                            try:
                                conf = float(parts[10])
                                if conf < 30:
                                    continue
                                text = parts[11].strip()
                                if text and len(text) >= 2:
                                    elements.append({
                                        "text": text,
                                        "x": int(parts[6]), "y": int(parts[7]),
                                        "w": int(parts[8]), "h": int(parts[9]),
                                        "center_x": int(parts[6]) + int(parts[8]) // 2,
                                        "center_y": int(parts[7]) + int(parts[9]) // 2,
                                    })
                            except:
                                continue
                    return {"success": True, "elements": elements, "count": len(elements), "screenshot": path}
                except FileNotFoundError:
                    return {"success": False, "error": "tesseract not installed. Run: brew install tesseract"}

            elif action == "find":
                text = params.get("text", "")
                path = f"/tmp/jarvis_screen_{int(time.time())}.png"
                subprocess.run(["screencapture", "-x", path], timeout=10)
                try:
                    local_path = f"/tmp/jarvis_ocr_{os.getpid()}.png"
                    import shutil
                    shutil.copy2(path, local_path)
                    result = subprocess.run(
                        ["tesseract", local_path, "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
                        capture_output=True, text=True, timeout=30, cwd="/tmp"
                    )
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 12:
                            elem_text = parts[11].strip().lower()
                            if text.lower() in elem_text:
                                return {"success": True, "found": True, "text": parts[11].strip(),
                                        "center_x": int(parts[6]) + int(parts[8]) // 2,
                                        "center_y": int(parts[7]) + int(parts[9]) // 2}
                    return {"success": True, "found": False, "searched": text}
                except FileNotFoundError:
                    return {"success": False, "error": "tesseract not installed"}

            elif action == "find_click":
                text = params.get("text", "")
                path = f"/tmp/jarvis_screen_{int(time.time())}.png"
                subprocess.run(["screencapture", "-x", path], timeout=10)
                try:
                    local_path = f"/tmp/jarvis_ocr_{os.getpid()}.png"
                    import shutil
                    shutil.copy2(path, local_path)
                    result = subprocess.run(
                        ["tesseract", local_path, "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
                        capture_output=True, text=True, timeout=30, cwd="/tmp"
                    )
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 12:
                            elem_text = parts[11].strip().lower()
                            if text.lower() in elem_text:
                                cx = int(parts[6]) + int(parts[8]) // 2
                                cy = int(parts[7]) + int(parts[9]) // 2
                                # Use cliclick or osascript to click
                                try:
                                    subprocess.run(["cliclick", f"c:{cx},{cy}"], timeout=5)
                                except FileNotFoundError:
                                    script = f'tell application "System Events" to click at {{{cx}, {cy}}}'
                                    subprocess.run(["osascript", "-e", script], timeout=10)
                                return {"success": True, "clicked": text, "x": cx, "y": cy}
                    return {"success": True, "found": False, "searched": text, "error": "Not found on screen"}
                except FileNotFoundError:
                    return {"success": False, "error": "tesseract not installed"}

            elif action == "see":
                path = f"/tmp/jarvis_screen_{int(time.time())}.png"
                subprocess.run(["screencapture", "-x", path], timeout=10)
                try:
                    local_path = f"/tmp/jarvis_ocr_{os.getpid()}.png"
                    import shutil
                    shutil.copy2(path, local_path)
                    result = subprocess.run(
                        ["tesseract", local_path, "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
                        capture_output=True, text=True, timeout=30, cwd="/tmp"
                    )
                    elements = []
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 12:
                            try:
                                conf = float(parts[10])
                                if conf >= 30 and parts[11].strip():
                                    elements.append(parts[11].strip())
                            except:
                                continue
                    return {"success": True, "visible_text": elements, "screenshot": path}
                except FileNotFoundError:
                    return {"success": True, "screenshot": path, "visible_text": [], "note": "Install tesseract for OCR"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Disk Cleaner ──────────────────────────────────────────────────
    if device_type == "DISK":
        try:
            if action == "usage":
                result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=10)
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    return {"success": True, "filesystem": parts[0], "size": parts[1], "used": parts[2], "available": parts[3], "percent": parts[4]}
                return {"success": False, "error": "Could not parse df output"}

            elif action == "scan_cache":
                cache_dirs = [
                    os.path.expanduser("~/Library/Caches"),
                    os.path.expanduser("~/.cache"),
                    os.path.expanduser("~/.npm/_cacache"),
                ]
                results = []
                for d in cache_dirs:
                    if os.path.exists(d):
                        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(d) for f in fn)
                        results.append({"path": d, "size_mb": round(size / (1024 * 1024), 1)})
                return {"success": True, "caches": results}

            elif action == "scan_logs":
                log_dirs = [
                    os.path.expanduser("~/Library/Logs"),
                    os.path.expanduser("~/.npm/_logs"),
                ]
                results = []
                for d in log_dirs:
                    if os.path.exists(d):
                        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(d) for f in fn)
                        results.append({"path": d, "size_mb": round(size / (1024 * 1024), 1)})
                return {"success": True, "logs": results}

            elif action == "scan_downloads":
                downloads = os.path.expanduser("~/Downloads")
                large = []
                if os.path.exists(downloads):
                    for f in os.listdir(downloads):
                        fp = os.path.join(downloads, f)
                        if os.path.isfile(fp):
                            size = os.path.getsize(fp)
                            if size > 100 * 1024 * 1024:  # > 100MB
                                large.append({"name": f, "size_mb": round(size / (1024 * 1024), 1)})
                large.sort(key=lambda x: x["size_mb"], reverse=True)
                return {"success": True, "large_files": large[:20]}

            elif action == "clean":
                # Requires explicit confirm
                if not params.get("confirm"):
                    return {"success": False, "error": "Set confirm=true to proceed with cleaning"}
                path = params.get("path", "")
                if not path or not os.path.exists(path):
                    return {"success": False, "error": "Path not found"}
                import shutil
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    os.remove(path)
                elif os.path.isdir(path):
                    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(path) for f in fn)
                    shutil.rmtree(path)
                else:
                    return {"success": False, "error": "Unknown path type"}
                return {"success": True, "action": "cleaned", "path": path, "freed_mb": round(size / (1024 * 1024), 1)}

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

    # System Resource Assessment
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_count = psutil.cpu_count(logical=True)
        ram_gb = mem.total / (1024 ** 3)

        if ram_gb >= 32: tier = "ultra"; max_agents = 5
        elif ram_gb >= 16: tier = "high"; max_agents = 3
        elif ram_gb >= 8: tier = "mid"; max_agents = 2
        elif ram_gb >= 4: tier = "low"; max_agents = 1
        else: tier = "potato"; max_agents = 0

        print(f"[Relay] System: {ram_gb:.0f}GB RAM, {cpu_count} cores → Tier: {tier.upper()} (max {max_agents} parallel agents)")
        if tier == "potato":
            print("[Relay] WARNING: Very low RAM — chat/device control only, no headless browser")
        elif tier == "low":
            print("[Relay] Low RAM — single agent only, browser will auto-kill after 2min idle")
    except ImportError:
        print("[Relay] psutil not installed — skipping resource assessment")
        tier = "mid"

    device_info = startup_scan(args.user)
    try:
        post(f"{HF_API}/api/relay/register", {"user_id": args.user, "hostname": socket.gethostname(), "platform": platform.platform(), "info": device_info})
        print(f"[Relay] Registered: {device_info.get('whoami', '?')}")
    except Exception as e:
        print(f"[Relay] Registration failed: {e} (continuing...)")

    # Run device profiler on startup — send full profile to HF Space
    try:
        sys.path.insert(0, os.path.join(_script_dir, "backend"))
        from device_profiler import build_full_profile, get_profile_summary
        profile = build_full_profile()
        post(f"{HF_API}/api/device/profile", {"user_id": args.user, "profile": profile})
        summary = get_profile_summary(profile)
        print(f"[Relay] Device profile sent: {len(profile.get('apps', []))} apps, {profile.get('hardware', {}).get('ram_gb', '?')}GB RAM")
        print(f"[Relay] Profile: {summary[:200]}")
    except Exception as e:
        print(f"[Relay] Device profiling failed: {e}")

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

                # Extract clean params for macos_exec (avoid passing dict as string)
                if isinstance(params, dict):
                    clean_params = params.get("raw", params.get("text", str(params)))
                else:
                    clean_params = str(params)

                if target:
                    print(f"[Relay] Local route: {target} ({routing.get('confidence', 0):.0%}) | {intent_text[:50]}")

                print(f"[Relay] Executing: {act} ({str(params)[:50]})")

                # Check if this is a device command
                if act == "device_scan":
                    real_devices = _discover_real_devices()
                    _push_devices_to_hf(real_devices)
                    result = {"success": True, "devices_found": len(real_devices), "devices": real_devices}
                elif act == "system_explore":
                    # Full device exploration — run profiler and send profile to HF
                    try:
                        sys.path.insert(0, os.path.join(_script_dir, "backend"))
                        from device_profiler import build_full_profile, get_profile_summary
                        profile = build_full_profile()
                        # Send profile to HF Space
                        post(f"{HF_API}/api/device/profile", {"user_id": args.user, "profile": profile})
                        summary = get_profile_summary(profile)
                        result = {"success": True, "profile": profile, "summary": summary}
                        print(f"[Relay] Device profile: {len(profile.get('apps', []))} apps, {profile.get('hardware', {}).get('ram_gb', '?')}GB RAM")
                    except Exception as e:
                        result = {"success": False, "error": str(e)}
                elif act.startswith("device_") or (isinstance(params, dict) and params.get("device_type")):
                    result = _execute_device_command(act.replace("device_", ""), params)
                elif target == "OS_AGENT" or target == "HAL_AGENT":
                    # Local execution for OS/HAL tasks
                    result = macos_exec(act, clean_params)
                elif _is_mac or _is_win:
                    result = macos_exec(act, clean_params)
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
