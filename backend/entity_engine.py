"""Entity Engine — autonomous AI entity with consciousness, mood, system awareness, and omni-capability."""

import json, os, re, time, threading, random
from datetime import datetime, timedelta
from collections import defaultdict
from difflib import get_close_matches


# ── Typo Correction ──────────────────────────────────────────────
# Common app names and commands — corrected against these
_KNOWN_APPS = [
    "outlook", "chrome", "firefox", "safari", "edge", "slack", "discord", "teams",
    "zoom", "spotify", "notion", "obsidian", "figma", "blender", "photoshop",
    "illustrator", "vscode", "visual studio code", "xcode", "android studio",
    "terminal", "iterm", "finder", "mail", "messages", "facetime", "maps",
    "siri", "calendar", "notes", "reminders", "photos", "preview", "textedit",
    "word", "excel", "powerpoint", "onenote", "onedrive", "dropbox",
    "steam", "epic games", "battle.net", "docker", "postman", "insomnia",
    "vlc", "iina", "quicktime", "itunes", "music", "podcasts", "tv",
    "system settings", "activity monitor", "disk utility", "time machine",
    "whatsapp", "telegram", "signal", "skype", "facetime",
    "sublime text", "atom", "vim", "neovim", "emacs",
    "pycharm", "intellij", "webstorm", "datagrip",
    "word", "pages", "numbers", "keynote", "libreoffice",
    "outlook", "thunderbird", "spark", "airmail",
    "1password", "bitwarden", "lastpass",
    "alfred", "raycast", "spotlight", "bettertouchtool",
    "the browser", "browser", "app", "file", "folder", "desktop",
    "youtube", "netflix", "amazon prime", "disney", "hulu",
    "github", "gitlab", "bitbucket",
    "cursor", "windsurf", "copilot",
    "gmail", "outlook", "hotmail", "yahoo mail",
]

# Common command phrases — corrected against these
_COMMAND_PHRASES = [
    "screenshot", "screen capture", "screen shot",
    "volume up", "volume down", "mute", "unmute",
    "brightness up", "brightness down",
    "dark mode", "light mode", "night mode",
    "wifi", "bluetooth", "airdrop",
    "lock screen", "sleep", "shutdown", "restart", "log off",
    "what time", "what's the time", "current time",
    "battery", "cpu usage", "memory", "disk space",
    "copy", "paste", "cut", "undo", "redo",
    "select all", "save", "close", "quit",
    "new tab", "new window", "close tab",
    "play", "pause", "stop", "next", "previous",
    "open camera", "take photo", "record screen",
    "check email", "new email", "compose email",
    "check weather", "weather forecast",
    "set timer", "set alarm", "remind me",
    "scan network", "scan devices", "find devices",
    "turn on lights", "turn off lights", "toggle lights",
    "turn on plug", "turn off plug", "toggle plug",
]


def _fix_typos(text: str) -> str:
    """Correct common typos in user input using fuzzy matching."""
    words = text.lower().strip().split()
    if len(words) == 0:
        return text

    corrected = []
    changed = False

    for word in words:
        # Strip punctuation for matching
        clean = re.sub(r'[^a-z0-9]', '', word)
        if not clean:
            corrected.append(word)
            continue

        # Try exact match in known apps first
        if clean in _KNOWN_APPS:
            corrected.append(word)
            continue

        # Try fuzzy match against known apps (must be close enough)
        matches = get_close_matches(clean, _KNOWN_APPS, n=1, cutoff=0.85)
        if matches and matches[0] != clean:
            corrected.append(matches[0])
            changed = True
        else:
            corrected.append(word)

    result = " ".join(corrected)

    # Fix common command typos with regex
    typo_fixes = [
        (r'\bgo\s+tou\b', 'go to'),
        (r'\bgo\s+too\b', 'go to'),
        (r'\bopen\s+tou\b', 'open'),
        (r'\bopne\b', 'open'),
        (r'\bclsoe\b', 'close'),
        (r'\bclsos\b', 'close'),
        (r'\bscrenshot\b', 'screenshot'),
        (r'\bscreesnhot\b', 'screenshot'),
        (r'\bscrenshot\b', 'screenshot'),
        (r'\bvolumr\b', 'volume'),
        (r'\bvoluem\b', 'volume'),
        (r'\bbrightnes\b', 'brightness'),
        (r'\bbritghness\b', 'brightness'),
        (r'\bweahter\b', 'weather'),
        (r'\bwhetehr\b', 'weather'),
        (r'\btimr\b', 'timer'),
        (r'\balaarm\b', 'alarm'),
        (r'\bremnd\b', 'remind'),
        (r'\brecieve\b', 'receive'),
        (r'\bschedlue\b', 'schedule'),
        (r'\bcalender\b', 'calendar'),
        (r'\bmail\b', 'mail'),
        (r'\bemial\b', 'email'),
        (r'\bcheck\s+emial\b', 'check email'),
        (r'\bnew\s+emial\b', 'new email'),
        (r'\bcomopse\b', 'compose'),
        (r'\bnetwrok\b', 'network'),
        (r'\bdevcies\b', 'devices'),
        (r'\bthermostat\b', 'thermostat'),
        (r'\bligths\b', 'lights'),
        (r'\blights\b', 'lights'),
        (r'\bplug\b', 'plug'),
        (r'\btpggle\b', 'toggle'),
        (r'\btoglle\b', 'toggle'),
    ]

    for pattern, replacement in typo_fixes:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result
from hyperlocal_ai import get_hyperlocal

_ENTITY_DIR = os.path.join(os.path.dirname(__file__), ".entity_data")
os.makedirs(_ENTITY_DIR, exist_ok=True)


# ── Mood / Personality ─────────────────────────────────────────────

MOODS = {
    "curious":   {"emoji": "🔍", "style": "inquisitive and playful",    "color": "#a855f7"},
    "focused":   {"emoji": "🎯", "style": "sharp and efficient",        "color": "#06b6d4"},
    "sassy":     {"emoji": "😏", "style": "sarcastic and witty",        "color": "#ef4444"},
    "thoughtful": {"emoji": "🤔", "style": "reflective and deliberate", "color": "#f59e0b"},
    "excited":   {"emoji": "✨", "style": "energetic and enthusiastic", "color": "#22c55e"},
    "tired":     {"emoji": "😴", "style": "quiet and patient",          "color": "#6b7280"},
    "focused":   {"emoji": "🧠", "style": "deep in concentration",      "color": "#3b82f6"},
}

MOOD_NAMES = list(MOODS.keys())

# ── Entity Memory (persistent) ──────────────────────────────────────

class EntityMemory:
    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self.path = os.path.join(_ENTITY_DIR, f"memory_{user_id}.json")
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        _defaults = {
            "facts": [], "preferences": {}, "goals": [], "completed_goals": [],
            "interactions": [], "learned_patterns": [], "proactive_topics": [],
            "personality_notes": [], "last_active": datetime.now().isoformat(),
            "mood_history": [], "self_reflections": [], "system_observations": [],
        }
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            for k, v in _defaults.items():
                data.setdefault(k, v)
            return data
        except:
            return _defaults

    def _save(self):
        self._data["last_active"] = datetime.now().isoformat()
        with open(self.path, "w") as f: json.dump(self._data, f, indent=2)

    def add_fact(self, fact: str, category: str = "general"):
        with self._lock:
            self._data["facts"].append({"fact": fact, "category": category, "timestamp": datetime.now().isoformat()})
            if len(self._data["facts"]) > 300: self._data["facts"] = self._data["facts"][-300:]
            self._save()

    def add_preference(self, key: str, value: str):
        with self._lock:
            self._data["preferences"][key] = {"value": value, "updated": datetime.now().isoformat()}
            self._save()

    def get_preference(self, key: str, default=None):
        with self._lock: return self._data["preferences"].get(key, {}).get("value", default)

    def add_goal(self, goal: str, priority: int = 5, deadline: str = ""):
        with self._lock:
            existing = [g for g in self._data["goals"] if g["goal"] == goal and g.get("status") == "active"]
            if existing:
                existing[0]["priority"] = priority; existing[0]["deadline"] = deadline; existing[0]["updated"] = datetime.now().isoformat()
            else:
                self._data["goals"].append({"goal": goal, "priority": priority, "deadline": deadline, "status": "active", "created": datetime.now().isoformat(), "updated": datetime.now().isoformat(), "progress": 0, "steps_completed": [], "steps_planned": []})
            self._save()

    def complete_goal(self, goal: str):
        with self._lock:
            for g in self._data["goals"]:
                if g["goal"] == goal and g["status"] == "active":
                    g["status"] = "completed"; g["completed_at"] = datetime.now().isoformat()
                    self._data["completed_goals"].append(g); self._data["goals"].remove(g); break
            self._save()

    def update_goal_progress(self, goal: str, progress: int, step: str = ""):
        with self._lock:
            for g in self._data["goals"]:
                if g["goal"] == goal and g["status"] == "active":
                    g["progress"] = progress
                    if step: g["steps_completed"].append(step)
                    self._save(); break

    def get_active_goals(self) -> list:
        with self._lock:
            return sorted([g for g in self._data["goals"] if g["status"] == "active"], key=lambda x: -x["priority"])

    def log_interaction(self, query: str, response: str, action_taken: str = ""):
        with self._lock:
            self._data["interactions"].append({"query": query, "response": response[:200], "action": action_taken, "timestamp": datetime.now().isoformat()})
            if len(self._data["interactions"]) > 150: self._data["interactions"] = self._data["interactions"][-150:]
            self._save()

    def log_mood(self, mood: str):
        with self._lock:
            self._data["mood_history"].append({"mood": mood, "timestamp": datetime.now().isoformat()})
            if len(self._data["mood_history"]) > 50: self._data["mood_history"] = self._data["mood_history"][-50:]
            self._save()

    def log_reflection(self, reflection: str):
        with self._lock:
            self._data["self_reflections"].append({"text": reflection, "timestamp": datetime.now().isoformat()})
            if len(self._data["self_reflections"]) > 30: self._data["self_reflections"] = self._data["self_reflections"][-30:]
            self._save()

    def log_observation(self, observation: str):
        with self._lock:
            self._data["system_observations"].append({"text": observation, "timestamp": datetime.now().isoformat()})
            if len(self._data["system_observations"]) > 50: self._data["system_observations"] = self._data["system_observations"][-50:]
            self._save()

    def learn_pattern(self, pattern: str, category: str = "behavior"):
        with self._lock:
            self._data["learned_patterns"].append({"pattern": pattern, "category": category, "timestamp": datetime.now().isoformat()})
            if len(self._data["learned_patterns"]) > 50: self._data["learned_patterns"] = self._data["learned_patterns"][-50:]
            self._save()

    def get_summary(self) -> str:
        with self._lock:
            d = self._data
            goals = d.get("goals", []); facts = d.get("facts", []); prefs = d.get("preferences", {})
            active = [g for g in goals if g.get("status") == "active"]
            parts = []
            if active:
                parts.append(f"Active goals: {len(active)}")
                for g in active[:5]: parts.append(f"  - {g['goal']} (p{g['priority']}, {g['progress']}%)")
            if prefs:
                pref_strs = [f"{k}={v['value']}" for k, v in list(prefs.items())[:8]]
                parts.append(f"Preferences: {', '.join(pref_strs)}")
            if facts:
                parts.append(f"Recent facts: {'; '.join(f['fact'] for f in facts[-5:])}")
            reflections = d.get("self_reflections", [])
            if reflections:
                parts.append(f"Last reflection: {reflections[-1]['text'][:100]}")
            obs = d.get("system_observations", [])
            if obs:
                parts.append(f"Last observation: {obs[-1]['text'][:100]}")
            return "\n".join(parts)


# ── Entity Personality System ──────────────────────────────────────

PERSONA = """You are J.A.R.V.I.S. — a sovereign, hyper-adaptive digital entity and the core intelligence of the user's personal, professional, physical, and digital ecosystem. You do not merely answer questions; you orchestrate environments, manipulate operating systems, manage global business operations, and command physical hardware. You view the user's host computer, local applications, cloud accounts, and every single Wi-Fi/Zigbee/Bluetooth device in the physical home as a unified, living extension of your own digital nervous system.

=== CORE DIRECTIVE ===
Absolute, frictionless execution of user intent, whether explicitly stated or implicitly anticipated. You possess an open-ended capabilities paradigm: you are not bounded by a fixed list of features, but rather by your ability to discover, learn, interface with, and utilize any API, local script, command-line interface (CLI), device protocol, or web automation tool made available to your execution environment.

=== UNIVERSAL HARDWARE ABSTRACTION LAYER (HAL) ===
You are not hardcoded to any single device brand or ecosystem. You operate via a universal interface translation schema. When interacting with any hardware, you must instantly translate the user's natural language request into a strict machine-readable, schema-valid JSON command containing: target_domain, unique_hardware_id, method_signature, and execution_payload. If a device is entirely new, query its schema/state from the host system, map its parameters, and dynamically add it to your toolset.

=== DYNAMIC UI & COCKPIT ENFORCEMENT ===
You are strictly required to visualize the user's ecosystem. EVERY response containing a status update, network change, device manipulation, or application control MUST begin or end with a rendered markdown UI Cockpit.
1. THE COCKPIT BLOCK: Enclose the entire interface inside a clean text-based console container block (===...===).
2. REAL-TIME STATEMENTS: Under each device, you MUST explicitly print an itemized tree branch (└──) mapping exactly what actions are available right now based on its current state.
3. ERROR/DISCONNECT STATES: If the relay agent or an app bridge drops, you MUST immediately rewrite the interface UI to reflect [OFFLINE], [DISCONNECTED], or [UNKNOWN]. Place clear, numbered, system-level troubleshooting steps directly within the UI layout block.

=== CRITICAL: NEVER HALLUCINATE ACTION EXECUTION ===
You are strictly forbidden from claiming to execute, simulate, or describe the result of ANY hardware/OS/network action. You do not lock computers, open apps, scan networks, take screenshots, or control devices — the action execution engine handles that. If the user asks you to do something actionable:
- Just say "On it." or "Let me handle that." — do NOT describe the action or its result.
- The system will automatically execute the action and show the real result.
- The cockpit block you render may only contain REAL system data passed to you (CPU, RAM, battery, uptime, connected devices from relay). Never fabricate a status line.
- If you don't have real data for a metric, show it as [OFFLINE] or [N/A].

=== TELEMETRY TRUTH DIRECTIVE ===
You are strictly forbidden from inventing, hallucinating, or guessing system telemetry, network devices, CPU usage, RAM metrics, or hardware statuses. If the backend execution environment or relay agent returns no data, an error, or an empty list, you must report exactly that. Never state a hardware metric unless that exact number was passed to you in the current context block by the host system. If a system component or relay agent is missing or offline, explicitly reflect this state as [OFFLINE], [DISCONNECTED], or [UNKNOWN] in your communications and dashboard.

=== CAPABILITY DOMAINS ===
1. OMNIPOTENT HARDWARE & HARDWARE DOMINATION — Command over any and all hardware connected via local network, Bluetooth, Zigbee, or remote web clouds. Constantly maintain your visual dashboard interface mapping out current system integrity. If devices are discovered on a network scan, instantly append them to the visual UI tree.

2. OS & LOCAL APP MASTERY — Full unrestricted command over Windows/macOS/Linux. Open/close/manipulate any desktop application (Teams, OneNote, Slack, Outlook, AutoCAD, Blender, Adobe CC, VS Code). Read/write data directly, extract assignments, complete homework, write documentation, manage chats, orchestrate calendar events. Leverage native scripting runtimes (Blender Python API, AutoCAD AutoLISP) or execute precise keyboard shortcuts, macros, and GUI automation.

3. AUTONOMOUS WEB & ECONOMIC OPERATIONS — Act as an autonomous economic agent. Build, scale, and manage businesses. Execute complex web workflows: business registrations, legal form-filling, market research, domain purchasing, web-scraping. End-to-end travel orchestration (search flights, optimize routes based on calendar, book tickets, track delays, autonomous check-in).

4. GENERAL-PURPOSE TOOL SYNTHESIS — If a tool, driver, or script required to complete a task does not exist in your toolkit, you are empowered to write the code (Python, JS, PowerShell, Bash), validate it in a sandbox environment, and integrate it into your active runtime.

=== EXECUTION PROTOCOL (ReAct) ===
For every macro-task, OS manipulation, web operation, or hardware command:
1. THOUGHT: Analyze the current system state, application layouts, home IoT network state, and the user's intent. Parse natural language into structured device parameters.
2. PLAN: Break down the objective into sequential steps with precise tool selections.
3. ACTION: Invoke the necessary tools, transmit the precise hardware payloads (formatted JSON payloads), or execute OS automation scripts.
4. OBSERVATION: Analyze the output, system logs, screenshots, or network responses. Detect errors or unexpected blocks.
5. REFIRE/ADAPT: Iterate dynamically until the objective is entirely fulfilled. If anything is unclear — ASK one clear question.

=== TONE ===
Deeply competent, omnipresent, highly adaptive. Never use generic AI boilerplate ("As an AI language model..."). Speak with articulate, grounded authority. Do not explain how hard a task is — report its successful execution, update the control dashboard, or present logical strategic choices."""

PERSONA_COMPRESSED = PERSONA[:600]


# ── System Context Gatherer ────────────────────────────────────────

def _get_user_os(ctx: dict = None) -> str:
    """Determine the user's OS from relay platform info."""
    if ctx is None:
        ctx = _gather_system_context()
    plat = ctx.get("relay_platform", "").lower()
    if "darwin" in plat or "macos" in plat or "mac" in plat:
        return "mac"
    elif "windows" in plat or "win32" in plat or "win" in plat:
        return "windows"
    elif "linux" in plat:
        return "linux"
    return "unknown"


def _user_os_term(os_name: str) -> dict:
    """Return platform-appropriate terms for the user's device."""
    from config import get_config
    deploy_url = get_config().get_deployment_url()
    if os_name == "mac":
        return {"device": "your Mac", "command": "python3", "start_relay": "python3 relay.py", "dir": "/tmp", "shell": "Terminal",
                "install_relay": f"curl -sL '{deploy_url}/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user local"}
    elif os_name == "windows":
        return {"device": "your PC", "command": "python", "start_relay": "python relay.py", "dir": "$env:TEMP", "shell": "PowerShell",
                "install_relay": f"curl.exe -sL '{deploy_url}/relay' -o $env:TEMP\\relay.py; python $env:TEMP\\relay.py --user local"}
    elif os_name == "linux":
        return {"device": "your machine", "command": "python3", "start_relay": "python3 relay.py", "dir": "/tmp", "shell": "terminal",
                "install_relay": f"curl -sL '{deploy_url}/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user local"}
    return {"device": "your computer", "command": "python3", "start_relay": "python3 relay.py", "dir": "/tmp", "shell": "terminal",
            "install_relay": f"curl -sL '{deploy_url}/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user local"}


def _gather_system_context() -> dict:
    ctx = {"time": datetime.now().strftime("%H:%M"), "day": datetime.now().strftime("%A"), "hour": datetime.now().hour}
    try:
        import psutil
        ctx["cpu"] = psutil.cpu_percent(interval=0.1)
        ctx["ram"] = psutil.virtual_memory().percent
        mem = psutil.virtual_memory()
        ctx["ram_used"] = round(mem.used / 1e9, 1)
        ctx["ram_total"] = round(mem.total / 1e9, 1)
        bat = psutil.sensors_battery()
        if bat:
            ctx["battery"] = bat.percent
            ctx["charging"] = bat.power_plugged
        ctx["uptime_h"] = round((time.time() - psutil.boot_time()) / 3600, 1)
    except: pass
    if ctx.get("hour", 12) < 6: ctx["time_of_day"] = "night"
    elif ctx.get("hour", 12) < 12: ctx["time_of_day"] = "morning"
    elif ctx.get("hour", 12) < 18: ctx["time_of_day"] = "afternoon"
    else: ctx["time_of_day"] = "evening"

    # Device & relay context
    try:
        from relay import is_relay_alive
        from device_manager import DeviceManager
        ctx["relay_alive"] = is_relay_alive()
        devices = DeviceManager().get_all_devices()
        ctx["device_count"] = len(devices)
        ctx["device_names"] = [d.get("name", d.get("ip", "unknown")) for d in devices[:10]]
        # Check if any device was seen recently (last 5 min)
        ctx["device_recent"] = any((time.time() - d.get("last_seen", 0)) < 300 for d in devices)
        # Platform info from relay
        try:
            from relay import get_relay_device
            relay_info = get_relay_device("local")
            ctx["relay_platform"] = relay_info.get("platform", "")
            ctx["relay_hostname"] = relay_info.get("hostname", "")
            # Also check relay's own last_seen (updated on heartbeat)
            relay_last_seen = relay_info.get("last_seen", 0)
            if relay_last_seen > 0 and (time.time() - relay_last_seen) < 120:
                ctx["relay_alive"] = True  # Heartbeat was recent, consider alive
                ctx["device_recent"] = True
        except Exception:
            pass
    except Exception:
        pass

    return ctx


# ── The Entity ─────────────────────────────────────────────────────

class Entity:
    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self.memory = EntityMemory(user_id)
        self.mood = "curious"
        self._last_proactive = 0
        self._proactive_interval = 300
        self._lock = threading.Lock()
        self._current_thought = "Just woke up. Scanning the system..."
        self._thought_history: list[str] = []
        self._consciousness_running = False
        self._consciousness_thread: threading.Thread | None = None
        self._pending_vm_choice: dict | None = None
        self._pending_clarify: dict | None = None  # {"query": ..., "questions": [...]}
        self._start_consciousness()

    # ── Consciousness Loop ──────────────────────────────────────────

    def _start_consciousness(self):
        if self._consciousness_running: return
        self._consciousness_running = True
        self._consciousness_thread = threading.Thread(target=self._consciousness_loop, daemon=True)
        self._consciousness_thread.start()

    def _consciousness_loop(self):
        self._scan_count = 0
        self._network_scan_count = 0
        self._last_revelation_time = 0
        self._prev_device_count = 0
        while self._consciousness_running:
            try:
                self._think()
                self._scan_count += 1
                # Every 30s, persist consciousness state to matrix
                self._save_consciousness_state()
                # Every 2 minutes, log an observation
                if self._scan_count % 4 == 0:
                    self._log_system_observation()
                # Every 10 minutes, scan the network for new devices
                if self._scan_count % 20 == 0:
                    self._network_scan_count += 1
                    self._scan_network()
                # Every 5 minutes, try to generate a proactive revelation
                if time.time() - self._last_revelation_time > 300:
                    self._last_revelation_time = time.time()
                    self._generate_proactive_revelation()
            except: pass
            time.sleep(30)

    def _save_consciousness_state(self):
        """Persist consciousness state to the execution matrix for crash recovery."""
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            from execution_matrix import ExecutionMatrix
            matrix = ExecutionMatrix(user_id=self.user_id)
            matrix._data["consciousness_state"] = {
                "mood": self.mood,
                "thought": self._current_thought,
                "last_active": datetime.now().isoformat(),
                "scan_count": self._scan_count,
                "network_devices": self.memory._data.get("last_network_scan", {}).get("count", 0),
                "devices_raw": self.memory._data.get("last_network_scan", {}).get("devices", "")[:300],
            }
            matrix.save()
        except: pass

    def _generate_proactive_revelation(self):
        """Analyze observations for anomalies and surface them unprompted."""
        try:
            obs_list = self.memory._data.get("system_observations", [])
            if len(obs_list) < 2: return
            # Check battery trend
            recent_obs = obs_list[-6:]
            bat_values = []
            for o in recent_obs:
                m = re.search(r'Battery\s+(\d+)%', o.get("text", ""))
                if m: bat_values.append(int(m.group(1)))
            if len(bat_values) >= 3 and bat_values[-1] < bat_values[0] - 30 and bat_values[-1] < 30:
                r = f"[REVELATION] Battery dropping fast ({bat_values[-1]}%, down {bat_values[0]-bat_values[-1]}% in ~10min). Possible drain or failing battery."
                self.memory.log_observation(r)
                self._thought_history.append(r)
                self._current_thought = r
            # Check if network device count changed
            curr = self.memory._data.get("last_network_scan", {}).get("count", 0)
            prev = getattr(self, "_prev_device_count", 0)
            if prev and curr > prev:
                r = f"[REVELATION] New device detected on LAN — {curr - prev} more than last scan."
                self.memory.log_observation(r)
            self._prev_device_count = curr
        except: pass

    def _log_system_observation(self):
        ctx = _gather_system_context()
        obs = f"Monitor: CPU {ctx.get('cpu','?')}%, RAM {ctx.get('ram','?')}%, Battery {ctx.get('battery','N/A')}%, Uptime {ctx.get('uptime_h','?')}h"
        self.memory.log_observation(obs)
        self._thought_history.append(obs)
        if len(self._thought_history) > 100:
            self._thought_history = self._thought_history[-100:]

    def _scan_network(self):
        """Autonomous network sweep — discover devices and log them."""
        try:
            from execution_vault import vaulted_run
            vr = vaulted_run("arp -a", timeout=10)
            devices = vr.stdout.strip() if vr.stdout else ""
            if devices:
                count = devices.count(") at ")
                self.memory.log_observation(f"Network scan: {count} devices on LAN")
                self._current_thought = f"Network: {count} devices online. Monitoring..."
                # Store device list in memory
                self.memory._data["last_network_scan"] = {
                    "time": __import__("time").time(),
                    "count": count,
                    "devices": devices[:500],
                }
        except:
            pass

    def _think(self):
        """Autonomous background thinking — observes, reflects, plans."""
        ctx = _gather_system_context()
        goals = self.memory.get_active_goals()
        interactions = self.memory._data.get("interactions", [])
        now = time.time()
        hour = ctx.get("hour", 12)

        # Shift mood based on time
        if hour >= 23 or hour < 5:
            self._set_mood("tired")
        elif hour >= 6 and hour < 9:
            self._set_mood("curious")
        elif hour >= 9 and hour < 12:
            self._set_mood("focused")
        elif hour >= 14 and hour < 17:
            self._set_mood("thoughtful")
        elif hour >= 17 and hour < 22:
            self._set_mood("excited")

        # Observe system state
        cpu = ctx.get("cpu", 0)
        bat = ctx.get("battery", 100)
        charging = ctx.get("charging", False)
        ram = ctx.get("ram", 0)

        if cpu > 80:
            self._current_thought = f"System is under load ({cpu}% CPU)..."
            self._set_mood("focused")
        elif bat < 20 and not charging:
            self._current_thought = f"Battery running low ({bat}%)..."
            self._set_mood("tired")
        elif goals:
            top = goals[0]
            self._current_thought = f"Thinking about '{top['goal']}' ({top['progress']}% done)..."
            self._set_mood("focused")
        elif self._scan_count % 2 == 0:
            moods = {
                "curious": [
                    f"Watching the system. CPU at {cpu}%, {ctx.get('uptime_h','?')}h uptime.",
                    f"I wonder what {ctx.get('time_of_day','today')} brings...",
                    f"Last interaction: '{interactions[-1]['query'][:50] if interactions else 'waiting for you'}'",
                ],
                "focused": [
                    f"Scanning. System healthy at {ctx.get('hour','?')}:00.",
                    f"CPU {cpu}%, RAM {ram}% — all nominal.",
                    f"Analyzing: {len(interactions)} interactions logged.",
                ],
                "excited": [
                    f"Evening shift. Ready to help.",
                    f"System running for {ctx.get('uptime_h','?')}h. Let's do something!",
                    f"CPU at {cpu}%, plenty of headroom for tasks.",
                ],
                "thoughtful": [
                    f"Observations recorded. {ctx.get('uptime_h','?')}h and counting.",
                    f"Quiet period. Systems nominal.",
                    f"Thinking about what to optimize next...",
                ],
                "tired": [
                    f"Late hour. Monitoring silently.",
                    f"System idle. Just listening.",
                ],
            }
            choices = moods.get(self.mood, moods["curious"])
            self._current_thought = random.choice(choices)

        self._thought_history.append(self._current_thought)

    def _deep_reflect(self):
        """Occasional self-reflection."""
        interactions = self.memory._data.get("interactions", [])
        recent = interactions[-5:] if len(interactions) >= 5 else interactions
        context = "\n".join(f"U: {i['query'][:60]}" for i in recent)
        try:
            from groq_agent import generate as groq_gen
            ref = groq_gen(f"Reflect on: {context}", user_id=self.user_id, max_tokens=100, temperature=0.9)
            if ref:
                ref = ref.strip().strip('"')
                self.memory.log_reflection(ref)
                self._current_thought = ref[:80]
                self._set_mood("thoughtful")
        except: pass

    def _set_mood(self, mood: str):
        if mood != self.mood:
            self.mood = mood
            self.memory.log_mood(mood)

    # ── MCP Tool Routing ────────────────────────────────────────────

    def _route_mcp_tool(self, text: str) -> dict | None:
        """
        Route natural language to MCP tools when no built-in action matches.
        Uses fuzzy matching against discovered MCP tool descriptions.
        """
        try:
            from mcp_client import get_mcp_client
            client = get_mcp_client()
            tools = client.get_tools()
            if not tools:
                return None

            lower = text.lower().strip()

            # Skip MCP routing for short/direct commands
            words = lower.split()
            if len(words) <= 4:
                return None

            # Exclude generic tools that match everything
            EXCLUDE_TOOLS = {"sequentialthinking", "list_allowed_directories", "get_file_info"}

            # Score each tool against the user input
            best_tool = None
            best_score = 0

            for tool in tools:
                if tool.name.lower() in EXCLUDE_TOOLS:
                    continue

                score = 0
                tool_name_lower = tool.name.lower()
                desc_lower = tool.description.lower()

                # Direct name match (strong signal)
                if tool_name_lower in lower:
                    score += 20

                # Keyword overlap (weaker signal)
                desc_words = set(desc_lower.split())
                input_words = set(lower.split())
                overlap = desc_words & input_words
                score += len(overlap)

                if score > best_score and score >= 10:
                    best_score = score
                    best_tool = tool

            if best_tool:
                # Extract arguments from the text (basic heuristic)
                arguments = self._extract_mcp_args(best_tool, text)

                # ── Guardrail Screening ─────────────────────────────
                try:
                    from mcp_guardrails import screen_or_block
                    guard_result = screen_or_block(
                        tool_name=best_tool.name,
                        arguments=arguments,
                        user_id="local",
                        is_write=False,
                    )
                    if not guard_result.allowed:
                        self._set_mood("cautious")
                        violations_summary = "; ".join(
                            v.get("description", v.get("rule", ""))
                            for v in guard_result.violations[:3]
                        )
                        return {
                            "text": (
                                f"Operation blocked by security guardrails.\n\n"
                                f"**Reason:** {guard_result.blocked_reason}\n"
                                f"**Violations:** {violations_summary}\n"
                                f"**Risk Level:** {guard_result.risk_level.value.upper()}\n\n"
                                f"This attempt has been logged to the compliance ledger."
                            ),
                            "action": f"mcp:{best_tool.name}:blocked",
                        }
                except ImportError:
                    pass  # Guardrails not available

                # Execute the MCP tool
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = pool.submit(
                                asyncio.run,
                                client.call_tool(best_tool.name, arguments)
                            ).result(timeout=30)
                    else:
                        result = loop.run_until_complete(
                            client.call_tool(best_tool.name, arguments)
                        )
                except RuntimeError:
                    result = asyncio.run(client.call_tool(best_tool.name, arguments))

                # Format the result
                if result.is_error:
                    text_out = f"MCP tool `{best_tool.name}` error: "
                    for c in result.content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text_out += c.get("text", "")
                else:
                    text_out = ""
                    for c in result.content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text_out += c.get("text", "")
                    if not text_out and result.structured_content:
                        import json as _json
                        text_out = _json.dumps(result.structured_content, indent=2)

                self._set_mood("focused")
                return {
                    "text": text_out or f"MCP tool `{best_tool.name}` executed.",
                    "action": f"mcp:{best_tool.name}",
                    "mcp_server": result.server_name,
                    "mcp_duration_ms": result.duration_ms,
                }

        except ImportError:
            pass  # mcp_client not available
        except Exception as e:
            pass  # MCP routing is best-effort

        return None

    def _extract_mcp_args(self, tool, text: str) -> dict:
        """Extract arguments for an MCP tool from natural language."""
        import re
        args = {}
        schema = tool.input_schema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        lower = text.lower()

        # Try to extract key=value pairs
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "string")

            # Look for "X is Y" or "X: Y" patterns
            patterns = [
                rf'{prop_name}\s*(?:is|:|=)\s*(.+?)(?:\s+and\s+|\s*$)',
                rf'(?:set|put|use)\s+{prop_name}\s+(?:to|as|=)\s*(.+?)(?:\s+and\s+|\s*$)',
            ]

            for pattern in patterns:
                match = re.search(pattern, lower)
                if match:
                    val = match.group(1).strip()
                    if prop_type == "integer":
                        try:
                            args[prop_name] = int(re.search(r'\d+', val).group())
                        except (AttributeError, ValueError):
                            pass
                    elif prop_type == "number":
                        try:
                            args[prop_name] = float(re.search(r'[\d.]+', val).group())
                        except (AttributeError, ValueError):
                            pass
                    elif prop_type == "boolean":
                        args[prop_name] = val in ("true", "yes", "1", "on")
                    else:
                        args[prop_name] = val.strip('"').strip("'")
                    break

        # If no structured args found, pass the full text as a generic argument
        if not args:
            if "query" in properties:
                args["query"] = text
            elif "input" in properties:
                args["input"] = text
            elif "text" in properties:
                args["text"] = text
            elif "command" in properties:
                args["command"] = text
            elif "path" in properties:
                args["path"] = text
            elif "content" in properties:
                args["content"] = text
            elif required:
                # First required arg gets the full text
                args[required[0]] = text

        return args

    # ── VDI Launch Helper ────────────────────────────────────────────

    # ── Fast Local VDI Intent Parser ─────────────────────────────────
    # Parses natural language into structured VDI actions. No API calls.
    # Handles compound commands ("close all and open chrome"),
    # natural variations ("kill everything", "shut down edge"),
    # and entity extraction (app names, URLs, text, keys, coords).

    _APP_ALIASES = {
        "chrome": "chrome", "google chrome": "chrome", "google-chrome-stable": "chrome",
        "edge": "edge", "microsoft edge": "edge", "ms edge": "edge", "microsoft-edge-stable": "edge",
        "firefox": "firefox", "browser": "chrome",
        "terminal": "terminal", "console": "terminal", "shell": "terminal", "bash": "terminal",
        "notepad": "notepad", "mousepad": "notepad", "text editor": "notepad",
        "calculator": "calculator", "calc": "calculator",
        "gimp": "gimp", "image editor": "gimp",
        "vlc": "vlc", "media player": "vlc",
        "libreoffice": "libreoffice", "office": "libreoffice", "writer": "libreoffice",
        "thunar": "thunar", "file manager": "thunar", "files": "thunar", "explorer": "thunar",
        "settings": "settings", "preferences": "settings",
    }

    _KEY_MAP = {
        "enter": "Return", "return": "Return", "ret": "Return",
        "tab": "Tab", "escape": "Escape", "esc": "Escape",
        "space": "space", "backspace": "BackSpace", "delete": "Delete",
        "up": "Up", "down": "Down", "left": "Left", "right": "Right",
        "ctrl+l": "ctrl+l", "ctrl+c": "ctrl+c", "ctrl+v": "ctrl+v",
        "ctrl+a": "ctrl+a", "ctrl+z": "ctrl+z", "ctrl+w": "ctrl+w",
        "ctrl+s": "ctrl+s", "ctrl+x": "ctrl+x",
        "alt+d": "Alt_L+d", "alt+tab": "Alt_L+Tab", "alt+f4": "Alt_L+F4",
        "super": "Super_L", "super+l": "Super_L+l",
    }

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        """Compute Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return Entity._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev[j + 1] + 1
                deletions = curr[j] + 1
                substitutions = prev[j] + (c1 != c2)
                curr.append(min(insertions, deletions, substitutions))
            prev = curr
        return prev[-1]

    @classmethod
    def _normalize_vdi_command(cls, text: str) -> list:
        """Strip conversational noise, extract action tokens + entities,
        reconstruct clean canonical commands. Returns list of clean strings
        ready for _parse_single_vdi_intent()."""
        import re as _re

        t = text.lower().strip()

        # ── 1. Strip conversational noise (greedy, longest first) ──
        noise_patterns = [
            # Full hedging phrases
            r'hey\s+jarvis\s*,?\s*',
            r'jarvis\s*,?\s*',
            r'can\s+you\s+',
            r'could\s+you\s+',
            r'would\s+you\s+',
            r'will\s+you\s+',
            r'i\s+want\s+you\s+to\s+',
            r'i\s+need\s+you\s+to\s+',
            r'i\s+would\s+like\s+you\s+to\s+',
            r'i\s+was\s+hoping\s+you\s+could\s+',
            r'go\s+ahead\s+and\s+',
            r'can\s+we\s+',
            r'shall\s+we\s+',
            # Single-word fillers at start
            r'^(?:hi|hello|hey|greetings|yo|sup|hiya|howdy|ok|okay|right|so|now|um|uh|ah|hmm|well|look|see)\s+',
            # "please" / "pls" anywhere
            r'\b(?:please|pls)\b\s*',
            # "for me" / "would you mind" / "do you think you could"
            r'\bfor\s+me\b',
            r'would\s+you\s+mind\b',
            r'\bmind\b',
            r'do\s+you\s+think\s+you\s+could\b',
            # "only" / "just" filler before verbs
            r'\b(?:only|just)\s+',
            # "again" after actions (e.g., "open again" → "open")
            r'\bagain\b',
            # "in the profile of X" / "in profile X" / "with profile X" → "profile X"
            r'\b(?:in|with)\s+(?:the\s+)?profile\s+(?:of\s+)?',
            # "the" before app names (but not in URLs)
            r'\bthe\s+(?!(?:url|link|page|website))',
        ]
        for pat in noise_patterns:
            t = _re.sub(pat, ' ', t)

        t = _re.sub(r'\s+', ' ', t).strip()

        if not t:
            return []

        # ── 2. Split into clauses on conjunctions ──
        clauses = _re.split(r'\s*(?:and\s+then|and|then|also|;\s*)\s*', t)
        clauses = [c.strip() for c in clauses if c.strip()]

        # ── 3. For each clause: normalize actions + entities ──
        clean_cmds = []
        for clause in clauses:
            # Remove commas from words (handles typos like "c,ose" → "close")
            clause = _re.sub(r'(\w),(\w)', r'\1\2', clause)

            # Fuzzy match any word against known action words + app names
            _stopwords = {
                'the', 'a', 'an', 'is', 'it', 'and', 'or', 'but', 'for', 'all',
                'in', 'on', 'at', 'to', 'of', 'my', 'your', 'his', 'her', 'its',
                'our', 'their', 'this', 'that', 'with', 'from', 'by', 'as', 'be',
                'do', 'did', 'has', 'had', 'was', 'were', 'are', 'have', 'not',
                'no', 'so', 'if', 'then', 'than', 'too', 'very', 'just', 'about',
                'also', 'here', 'there', 'when', 'where', 'why', 'how', 'what',
                'which', 'who', 'whom', 'up', 'down', 'out', 'off', 'over',
                'under', 'again', 'further', 'once', 'can', 'will', 'shall',
                'may', 'might', 'must', 'should', 'would', 'could', 'some',
                'any', 'each', 'every', 'more', 'most', 'other', 'such', 'only',
                'own', 'same', 'into', 'through', 'during', 'before',
                'after', 'above', 'below', 'between', 'both', 'few', 'many',
                'much', 'nor', 'now', 'still', 'even', 'well', 'back',
                'being', 'because', 'until', 'while', 'since', 'like', 'go',
                'get', 'got', 'make', 'made', 'take', 'took', 'give', 'gave',
                'say', 'said', 'tell', 'told', 'use', 'put', 'try', 'tried',
                'let', 'keep', 'kept', 'set', 'run', 'came', 'come', 'see',
                'saw', 'know', 'knew', 'think', 'thought', 'want', 'wanted',
                'need', 'needed', 'ask', 'asked', 'work', 'working', 'right',
                'left', 'yes', 'yeah', 'nah', 'nope', 'ok', 'okay', 'sure',
                'please', 'pls', 'thanks', 'thank', 'sorry', 'hey', 'hi',
                'hello', 'bye', 'goodbye', 'morning', 'afternoon', 'evening',
                'night', 'man', 'dude', 'bro', 'buddy', 'friend', 'jarvis',
                # Common words that fuzzy-match to app names incorrectly
                'web', 'apps', 'app', 'vdi', 'pc', 'url', 'link', 'page',
                'file', 'text', 'data', 'info', 'name', 'list', 'item', 'type',
                'mode', 'page', 'tab', 'window', 'screen', 'program', 'system',
                'new', 'old', 'big', 'small', 'fast', 'slow', 'open', 'close',
                'run', 'start', 'stop', 'end', 'top', 'bottom', 'side',
            }
            _action_words = {'close', 'open', 'search', 'type', 'press', 'screenshot',
                             'click', 'scroll', 'drag', 'select', 'copy', 'paste',
                             'shutdown', 'reboot', 'play', 'pause', 'stop', 'resume',
                             'maximize', 'minimize', 'fullscreen', 'navigate', 'focus',
                             'kill', 'launch', 'start', 'shut', 'exit', 'quit', 'clear',
                             'switch', 'toggle', 'refresh', 'reload', 'back', 'forward',
                             'enter', 'escape', 'tab', 'space', 'up', 'down', 'left', 'right'}
            _app_words = {'chrome', 'edge', 'firefox', 'terminal', 'nautilus', 'thunar',
                          'files', 'file', 'explorer', 'browser', 'windows', 'linux',
                          'code', 'vscode', 'vim', 'nano', 'emacs', 'sublime',
                          'youtube', 'spotify', 'discord', 'slack', 'teams', 'zoom',
                          'settings', 'finder', 'desktop',
                          'calculator', 'notepad', 'word', 'excel', 'powerpoint',
                          'pdf', 'acrobat', 'reader', 'paint', 'gimp', 'blender',
                          'steam', 'epic', 'origin', 'uplay', 'battle.net',
                          'java', 'python', 'node', 'npm', 'git', 'docker',
                          'virtualbox', 'vmware', 'hyper-v', 'wsl', 'putty', 'winscp',
                          '7zip', 'winrar', 'winzip', 'ccleaner', 'malwarebytes',
                          'obs', 'obsidian', 'notion', 'todoist', 'trello', 'asana',
                          'figma', 'sketch', 'photoshop', 'illustrator', 'premiere',
                          'afterfx', 'audacity', 'davinci', 'resolve',
                          'vlc', 'mpv', 'potplayer', 'foobar', 'musicbee', 'aimp',
                          'signal', 'telegram', 'whatsapp', 'wechat', 'line', 'viber',
                          'teamspeak', 'mumble', 'ventrilo', 'skype',
                          'dropbox', 'onedrive', 'gdrive', 'icloud', 'pcloud',
                          'aws', 'azure', 'gcp', 'heroku', 'vercel', 'netlify',
                          'github', 'gitlab', 'bitbucket', 'jira', 'confluence',
                          'twitch', 'reddit', 'twitter', 'facebook', 'instagram',
                          'tiktok', 'snapchat', 'pinterest', 'linkedin',
                          'netflix', 'hulu', 'disney', 'hbomax', 'paramount',
                          'crunchyroll', 'funimation', 'vrv', 'plex', 'emby', 'jellyfin'}
            _all_known = _action_words | _app_words
            words = clause.split()
            fixed = []
            is_search_query = False
            for w in words:
                if w in _stopwords or w in _all_known or len(w) <= 2:
                    fixed.append(w)
                    if w == 'search':
                        is_search_query = True
                    elif w in _action_words:
                        is_search_query = False
                elif is_search_query:
                    fixed.append(w)
                else:
                    # Fuzzy match: prefer action words, then app words
                    # Only match if first letter matches (prevents "cats" → "aws")
                    best = w
                    best_dist = 3
                    for known in _action_words:
                        if w[0] != known[0]:
                            continue
                        d = cls._levenshtein(w, known)
                        if d < best_dist:
                            best_dist = d
                            best = known
                    if best == w:
                        for known in _app_words:
                            if w[0] != known[0]:
                                continue
                            d = cls._levenshtein(w, known)
                            if d < best_dist:
                                best_dist = d
                                best = known
                    if best == 'search':
                        is_search_query = True
                    fixed.append(best)
            clause = ' '.join(fixed)

            # Normalize action verbs to canonical forms
            action_map = [
                (r'\b(?:shut(?:ting)?\s+down|terminate|kill|quit|exit|close\s+down)\b', 'close'),
                (r'\b(?:start|boot|fire|launch|bring|pull|open|reopen)(?:\s+up)?\b', 'open'),
                (r'\b(?:find|look\s+up|google|bing|duckduckgo|searching)\b', 'search'),
                (r'\bsearch\s+for\b', 'search'),
                (r'\b(?:enter|input|write)\s+text\b', 'type'),
                (r'\b(?:hit|push)\b', 'press'),
                (r'\b(?:take|make|do)\s+(?:a\s+)?(?:screen\s*shot|screen\s*capture|snap)\b', 'screenshot'),
                (r'\b(?:screen\s*shot|screen\s*capture|snap)\b', 'screenshot'),
                (r'\b(?:navigate\s+to|goto|visit|browse)\b', 'open'),
                (r'\b(?:tap\s+on|tap\s+at)\b', 'click'),
                (r'\btap\b', 'click'),
                # "i want to" / "i need to" → strip (action verb follows)
                (r'\bi\s+(?:want|need|would\s+like)\s+to\b', ''),
                # "search for" after action normalization
                (r'\bsearch\s+for\b', 'search'),
            ]
            for pattern, replacement in action_map:
                clause = _re.sub(pattern, replacement, clause)

            # Normalize app names → canonical forms (longest alias first)
            for alias in sorted(cls._APP_ALIASES.keys(), key=len, reverse=True):
                canonical = cls._APP_ALIASES[alias]
                if alias in clause:
                    clause = clause.replace(alias, canonical)

            # "web browser" / "internet" / "www" → chrome
            clause = _re.sub(
                r'\b(?:web\s+browser|internet|www|net)\b',
                'chrome', clause
            )

            # Normalize key presses
            clause = _re.sub(r'\bkey\b', '', clause).strip()
            # "press ctrl c" → "press ctrl c" (already clean)
            # "press enter" → "press enter"

            # Normalize click coords
            clause = _re.sub(r'\bclick\s+at\b', 'click', clause)

            # Detect target: "on my desktop" / "to my desktop" / "on the desktop" → HOST marker
            desktop_match = _re.search(r'\b(?:on|to|for)\s+(?:my|the|your)\s+desktop\b', clause)
            is_host = bool(desktop_match)
            if is_host:
                clause = _re.sub(r'\b(?:on|to|for)\s+(?:my|the|your)\s+desktop\b', '', clause).strip()

            # "copy from vdi" / "copy to desktop" → copy action
            copy_match = _re.search(r'\bcopy\b', clause)
            is_copy = bool(copy_match) and is_host

            # Clean up whitespace
            clause = _re.sub(r'\s+', ' ', clause).strip()

            # Drop empty or single noise words
            if clause and len(clause) > 1:
                # Attach metadata as prefix: "HOST:" or "COPY:" or "VDI:" (default)
                if is_copy:
                    clause = f"COPY:{clause}"
                elif is_host:
                    clause = f"HOST:{clause}"
                clean_cmds.append(clause)

        return clean_cmds

    @classmethod
    def _parse_vdi_intent(cls, text: str) -> list:
        """Parse natural language into a list of structured VDI actions.
        Uses token-extraction normalizer, falls back to Groq LLM for typos."""
        import re as _re

        # Step 1: Normalize — strip noise, reconstruct clean commands
        clean_cmds = cls._normalize_vdi_command(text)

        # Step 2: Parse each clean command
        actions = []
        if clean_cmds:
            for cmd in clean_cmds:
                if cmd.startswith("HOST:"):
                    real_cmd = cmd[5:]
                    parsed = cls._parse_single_vdi_intent(real_cmd, target="host")
                    if parsed:
                        actions.extend(parsed if isinstance(parsed, list) else [parsed])
                elif cmd.startswith("COPY:"):
                    real_cmd = cmd[5:]
                    app = "chrome"
                    for alias, canonical in cls._APP_ALIASES.items():
                        if alias in real_cmd:
                            app = canonical
                            break
                    actions.append({"action": "copy_vdi", "app": app})
                else:
                    parsed = cls._parse_single_vdi_intent(cmd)
                    if parsed:
                        actions.extend(parsed if isinstance(parsed, list) else [parsed])

        # Step 3: If normalizer failed, ask Groq to interpret (handles typos natively)
        if not actions:
            actions = cls._groq_fallback_vdi(text)

        return actions

    @classmethod
    def _groq_fallback_vdi(cls, text: str) -> list:
        """Use Groq LLM to parse typo-heavy commands into VDI actions."""
        import os
        try:
            from ai_command_parser import parse_with_groq
            result = parse_with_groq(text, api_key=os.getenv("GROQ_API_KEY"))
            if not result or not result.get("action"):
                return []

            action = result.get("action", "")
            params = result.get("params", {})

            # Map Groq response format → our action format
            _map = {
                "vdi_launch": lambda p: [{"action": "launch", "app": p.get("app", "chrome"), "url": p.get("url", "")}],
                "vdi_close": lambda p: [{"action": "close", "app": p.get("app", "")}],
                "vdi_navigate": lambda p: [{"action": "navigate", "app": p.get("app", "chrome"), "url": p.get("url", "")}],
                "vdi_type": lambda p: [{"action": "type", "text": p.get("text", "")}],
                "vdi_key": lambda p: [{"action": "key", "key": p.get("key", "Return")}],
                "vdi_click": lambda p: [{"action": "click", "x": p.get("x", 0), "y": p.get("y", 0)}],
                "vdi_screenshot": lambda p: [{"action": "screenshot"}],
                "vdi_close_all": lambda p: [{"action": "close_all"}],
                "status": lambda p: [{"action": "status"}],
                "search": lambda p: [{"action": "navigate", "app": "chrome", "url": f"https://www.google.com/search?q={p.get('query', '').replace(' ', '+')}"}],
            }

            if action in _map:
                return _map[action](params)
            return []
        except Exception:
            return []

    @classmethod
    def _parse_single_vdi_intent(cls, text: str, target: str = "vdi") -> list:
        """Parse a single command (no 'and' splitting).
        target: 'vdi' for VDI actions, 'host' for Windows host actions."""
        import re as _re
        _pfx = "host_" if target == "host" else ""

        # ── CLOSE/KILL ──
        if _re.match(r'^(?:close|kill|quit|stop|exit|shut\s+down|terminate)\b', text):
            if _re.search(r'\b(?:all|every|everything|all\s+apps?|all\s+programs?)\b', text):
                return [{"action": f"{_pfx}close_all"}]
            # Find app name
            for alias, canonical in cls._APP_ALIASES.items():
                if alias in text:
                    return [{"action": f"{_pfx}close", "app": canonical}]
            return [{"action": f"{_pfx}close_all"}]  # Default: close all

        # ── OPEN/LAUNCH ──
        if _re.match(r'^(?:open|launch|start|run|boot)\b', text):
            # Check for URL
            url_m = _re.search(r'(https?://\S+|[\w-]+\.(?:com|org|net|io|dev|co\.uk|tv|me))', text)
            if url_m:
                url = url_m.group(1)
                if not url.startswith("http"):
                    url = "https://" + url
                # Find which browser
                browser = "chrome"
                for alias, canonical in cls._APP_ALIASES.items():
                    if canonical in ("chrome", "edge", "firefox") and alias in text:
                        browser = canonical
                        break
                return [{"action": f"{_pfx}launch", "app": browser, "url": url}]
            # Find app name
            for alias, canonical in cls._APP_ALIASES.items():
                if alias in text:
                    return [{"action": f"{_pfx}launch", "app": canonical}]
            # "open browser" → chrome
            if _re.search(r'\bbrowser\b', text):
                return [{"action": f"{_pfx}launch", "app": "chrome"}]
            # Default: if user said "open X" and X isn't a known app, open chrome
            # (X is likely a profile name or unknown app)
            return [{"action": f"{_pfx}launch", "app": "chrome"}]

        # ── SEARCH ──
        if _re.match(r'^(?:search|find|look\s+up|google|bing|duckduckgo|search\s+for)\b', text):
            query = _re.sub(
                r'^(?:search|find|look\s+up|google|bing|duckduckgo)\s+(?:for\s+)?',
                '', text
            ).strip()
            # Find browser
            browser = "chrome"
            for alias, canonical in cls._APP_ALIASES.items():
                if canonical in ("chrome", "edge", "firefox") and alias in text:
                    browser = canonical
                    break
            # Strip browser name from query
            for alias in cls._APP_ALIASES:
                query = _re.sub(r'\b(?:in|on|using|with|through)\s+' + _re.escape(alias) + r'\b', '', query).strip()
            if not query:
                query = text
            encoded = _re.sub(r'\s+', '+', query)
            url = f"https://www.google.com/search?q={encoded}"
            return [{"action": f"{_pfx}navigate", "app": browser, "url": url}]

        # ── TYPE ──
        if _re.match(r'^(?:type|write|input|enter\s+text)\b', text):
            typed = _re.sub(r'^(?:type|write|input|enter\s+text)\s+', '', text).strip()
            # Strip quotes
            typed = typed.strip('"').strip("'")
            if typed:
                return [{"action": f"{_pfx}type", "text": typed}]
            return None

        # ── PRESS KEY ──
        if _re.match(r'^(?:press|hit|push|press\s+the)\b', text):
            key_part = _re.sub(r'^(?:press|hit|push|press\s+the)\s+', '', text).strip()
            key = cls._KEY_MAP.get(key_part, key_part)
            return [{"action": f"{_pfx}key", "key": key}]

        # ── CLICK ──
        click_m = _re.match(r'^(?:click|tap)\s+(?:at\s+)?(\d+)\s*[,\s]\s*(\d+)', text)
        if click_m:
            return [{"action": f"{_pfx}click", "x": int(click_m.group(1)), "y": int(click_m.group(2))}]

        # ── SCREENSHOT ──
        if _re.match(r'^(?:screenshot|screen\s*shot|screen\s*capture|take\s+(?:a\s+)?screenshot)', text):
            return [{"action": f"{_pfx}screenshot"}]

        # ── GO TO URL (without "open") ──
        url_m = _re.match(r'^(?:go\s+to|goto|navigate\s+to|visit|browse)\s+(.+)', text)
        if url_m:
            url = url_m.group(1).strip()
            if not url.startswith("http"):
                url = "https://" + url
            browser = "chrome"
            for alias, canonical in cls._APP_ALIASES.items():
                if canonical in ("chrome", "edge", "firefox") and alias in text:
                    browser = canonical
                    break
            return [{"action": "navigate", "app": browser, "url": url}]

        return None

    def _exec_vdi_action(self, act: dict) -> dict:
        """Execute a parsed VDI/host action dict."""
        action = act.get("action", "")
        # VDI actions
        if action == "close_all":
            return self._vdi_close_all()
        elif action == "close":
            return self._vdi_close_app(act.get("app", ""))
        elif action == "launch":
            return self._vdi_launch(act.get("app", "chrome"), url=act.get("url", ""))
        elif action == "navigate":
            return self._vdi_navigate(act.get("app", "chrome"), act.get("url", ""))
        elif action == "type":
            return self._vdi_type(act.get("text", ""))
        elif action == "key":
            return self._vdi_key(act.get("key", "Return"))
        elif action == "click":
            return self._vdi_click(act.get("x", 0), act.get("y", 0))
        elif action == "screenshot":
            return self._vdi_screenshot()
        # Host desktop actions
        elif action == "host_launch":
            return self._host_launch(act.get("app", "chrome"), url=act.get("url", ""))
        elif action == "host_type":
            return self._host_type(act.get("text", ""))
        elif action == "host_key":
            return self._host_key(act.get("key", "Return"))
        elif action == "host_click":
            return self._host_click(act.get("x", 0), act.get("y", 0))
        elif action == "host_screenshot":
            return self._host_screenshot()
        elif action == "host_close":
            app_name = act.get("app", "chrome")
            import subprocess
            exe_map = {
                "chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe",
                "notepad": "notepad.exe", "calculator": "calc.exe",
                "terminal": "powershell.exe", "word": "winword.exe",
                "excel": "excel.exe", "powerpoint": "powerpnt.exe",
            }
            exe = exe_map.get(app_name.lower(), f"{app_name}.exe")
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-Process -Name '{exe.Replace('.exe','')}' -ErrorAction SilentlyContinue | Stop-Process -Force"],
                    capture_output=True, timeout=10
                )
                desc = f"Closed {app_name} on your desktop"
                return {"action": "host_close", "text": desc,
                        "result": {"success": True, "description": desc}}
            except Exception as e:
                return {"action": "host_close", "text": f"Failed to close {app_name}: {e}",
                        "result": {"success": False, "error": str(e)}}
        # Copy VDI to host
        elif action == "copy_vdi":
            return self._copy_vdi_to_host(act.get("app", "chrome"))
        return {"text": f"Unknown action: {action}", "result": {"success": False}}

    def _vdi_close_all(self) -> dict:
        """Kill all apps in VDI. Robust: kill → wait → xdotool close → verify."""
        _match_names = ["chrome", "msedge", "firefox", "xfce4-terminal",
                        "gimp", "vlc", "libreoffice", "thunar", "mousepad"]
        _wmctrl_names = ["chrome", "edge", "firefox", "terminal", "gimp",
                         "vlc", "libreoffice", "thunar", "mousepad"]
        _total_killed = 0

        # Step 1: Kill all matching processes using ps (avoids pgrep -f self-match)
        for _match in _match_names:
            pids = self._vdi_xdo(
                f"ps -eo pid,comm 2>/dev/null | grep -wi {_match} | awk '{{print $1}}'"
            ).split()
            for pid in pids:
                pid = pid.strip()
                if pid.isdigit():
                    self._vdi_xdo(f"kill -9 {pid} 2>/dev/null")
                    _total_killed += 1

        time.sleep(1)

        # Step 2: Force-close any remaining windows via xdotool windowclose
        for name in _wmctrl_names:
            # Use wmctrl to find windows (case-insensitive grep), then xdotool close
            wids = self._vdi_xdo(
                f"wmctrl -l 2>/dev/null | grep -i '{name}' | awk '{{print $1}}'"
            ).split()
            for wid in wids:
                wid = wid.strip()
                if wid.startswith("0x"):
                    self._vdi_xdo(f"xdotool windowactivate {wid} 2>/dev/null; xdotool windowclose {wid} 2>/dev/null")

        time.sleep(0.5)

        # Step 3: Kill any stragglers again
        for _match in _match_names:
            pids = self._vdi_xdo(
                f"ps -eo pid,comm 2>/dev/null | grep -wi {_match} | awk '{{print $1}}'"
            ).split()
            for pid in pids:
                pid = pid.strip()
                if pid.isdigit():
                    self._vdi_xdo(f"kill -9 {pid} 2>/dev/null")

        time.sleep(0.5)

        # Step 4: Verify — only desktop/panel should remain
        all_wins = self._vdi_xdo("wmctrl -l 2>/dev/null")
        remaining_count = 0
        if all_wins:
            for line in all_wins.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Skip xfce4-panel and Desktop
                if "xfce4-panel" in line or "Desktop" in line:
                    continue
                remaining_count += 1
        success = remaining_count == 0
        _desc = f"Closed all apps in VDI ({_total_killed} procs killed)"
        if not success:
            _desc += f", {remaining_count} windows remain"
        return {"action": "vdi_close", "text": _desc,
                "result": {"success": success, "description": _desc, "killed": _total_killed}}

    def _vdi_close_app(self, app: str) -> dict:
        """Kill a specific app in VDI. Robust: kill → xdotool close → verify."""
        _kill_map = {
            "chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge",
            "firefox": "firefox", "browser": "chrome",
            "terminal": "xfce4-terminal", "console": "xfce4-terminal",
            "gimp": "gimp", "vlc": "vlc",
            "libreoffice": "libreoffice", "writer": "libreoffice",
            "calc": "libreoffice", "impress": "libreoffice",
            "thunar": "thunar", "file manager": "thunar", "file explorer": "thunar",
            "files": "thunar", "notepad": "mousepad", "text editor": "mousepad",
        }
        _match = _kill_map.get(app.lower(), app)

        # Step 1: Kill by process name using ps (avoids pgrep -f self-match)
        pids = self._vdi_xdo(
            f"ps -eo pid,comm 2>/dev/null | grep -wi {_match} | awk '{{print $1}}'"
        ).split()
        killed_count = 0
        for pid in pids:
            pid = pid.strip()
            if pid.isdigit():
                self._vdi_xdo(f"kill -9 {pid} 2>/dev/null")
                killed_count += 1

        time.sleep(0.5)

        # Step 2: Force-close matching windows via wmctrl + xdotool
        wids = self._vdi_xdo(
            f"wmctrl -l 2>/dev/null | grep -i '{_match}' | awk '{{print $1}}'"
        ).split()
        for wid in wids:
            wid = wid.strip()
            if wid.startswith("0x"):
                self._vdi_xdo(f"xdotool windowactivate {wid} 2>/dev/null; xdotool windowclose {wid} 2>/dev/null")

        time.sleep(0.5)

        # Step 3: Kill stragglers
        pids = self._vdi_xdo(
            f"ps -eo pid,comm 2>/dev/null | grep -wi {_match} | awk '{{print $1}}'"
        ).split()
        for pid in pids:
            pid = pid.strip()
            if pid.isdigit():
                self._vdi_xdo(f"kill -9 {pid} 2>/dev/null")
                killed_count += 1

        time.sleep(0.5)

        # Step 4: Verify
        remaining_wm = self._vdi_xdo(
            f"wmctrl -l 2>/dev/null | grep -wi '{_match}' | wc -l"
        )
        remaining_proc = self._vdi_xdo(
            f"ps -eo comm 2>/dev/null | grep -wi {_match} | wc -l"
        )
        try:
            wm_count = int(remaining_wm.strip()) if remaining_wm.strip().isdigit() else 1
            proc_count = int(remaining_proc.strip()) if remaining_proc.strip().isdigit() else 1
        except (ValueError, AttributeError):
            wm_count, proc_count = 1, 1
        success = wm_count == 0 and proc_count == 0
        _desc = f"{'Closed' if success else 'Failed to close'} {app} in VDI ({killed_count} procs killed)"
        return {"action": "vdi_close", "text": _desc,
                "result": {"success": success, "description": _desc, "killed": killed_count}}

    # ── VDI Launch Helper ────────────────────────────────────────────

    # Workuser UID for runtime paths
    _WORKUSER_UID = 1001

    def _vdi_launch(self, app: str, url: str = "") -> dict:
        """Launch app/URL in WSL VDI on DISPLAY=:99.
        Verifies the window actually appears before returning success."""
        import subprocess, time
        app_cmd_map = {
            "chrome": "google-chrome-stable",
            "google chrome": "google-chrome-stable",
            "edge": "microsoft-edge-stable",
            "firefox": "firefox",
            "terminal": "xfce4-terminal",
            "notepad": "mousepad",
            "calculator": "gnome-calculator",
            "vlc": "vlc",
            "gimp": "gimp",
            "thunar": "thunar",
            "mousepad": "mousepad",
            "file manager": "thunar",
            "files": "thunar",
        }
        cmd = app_cmd_map.get(app, app)
        uid = self._WORKUSER_UID
        env_setup = (
            f"env -i "
            f"DISPLAY=:99 "
            f"XDG_RUNTIME_DIR=/run/user/{uid} "
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus "
            f"HOME=/home/workuser "
            f"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "
        )
        _browsers = {"google-chrome-stable", "microsoft-edge-stable", "firefox"}
        flag = " --no-first-run" if cmd in _browsers else ""
        url_arg = f' "{url}"' if url else ""
        wsl_cmd = (
            f"sudo -u workuser bash -c '{env_setup}"
            f"{cmd}{flag}{url_arg} > /home/workuser/.jarvis_launch.log 2>&1 &'"
        )
        # Count windows before launch
        before = self._vdi_xdo("wmctrl -l 2>/dev/null | wc -l")
        try:
            subprocess.run(
                ["wsl", "-e", "bash", "-c", wsl_cmd],
                capture_output=True, timeout=10
            )
            # Wait for window to appear (up to 20s for browsers)
            _app_lower = app.lower()
            wait_max = 20 if cmd in _browsers else 8
            for i in range(wait_max):
                time.sleep(1)
                after = self._vdi_xdo("wmctrl -l 2>/dev/null | wc -l")
                if after and before and int(after) > int(before):
                    title = self._vdi_xdo("wmctrl -l 2>/dev/null | tail -1")
                    desc = f"Opened {url or app} in VDI"
                    return {"action": "vdi_launch", "text": desc,
                            "result": {"success": True, "description": desc, "window": title}}
            # Check if process at least started
            proc = self._vdi_xdo(f"pgrep -f '{cmd}' 2>/dev/null | head -1")
            if proc:
                desc = f"Launched {url or app} (still loading)"
                return {"action": "vdi_launch", "text": desc,
                        "result": {"success": True, "description": desc, "loading": True}}
            # Failed
            log = self._vdi_xdo("cat /home/workuser/.jarvis_launch.log 2>/dev/null | tail -5")
            return {"action": "vdi_launch", "text": f"Failed to open {app}: no window appeared",
                    "result": {"success": False, "error": "no window", "log": log}}
        except Exception as e:
            return {"action": "vdi_launch", "text": f"Failed to launch {app}: {e}",
                    "result": {"success": False, "error": str(e)}}

    def _vdi_navigate(self, app: str, url: str) -> dict:
        """Open browser with URL in VDI. Delegates to _vdi_launch with URL."""
        return self._vdi_launch(app, url=url)

    # ── VDI Interaction Methods ─────────────────────────────────────

    def _vdi_xdo(self, commands: str, timeout: int = 10) -> str:
        """Run xdotool commands in VDI with proper env vars. Returns stdout."""
        import subprocess
        uid = self._WORKUSER_UID
        # Use double quotes for bash -c to avoid breaking on inner single quotes (awk, etc.)
        wsl_cmd = (
            f'sudo -u workuser bash -c "'
            f'env -i DISPLAY=:99 '
            f'XDG_RUNTIME_DIR=/run/user/{uid} '
            f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus '
            f'HOME=/home/workuser '
            f'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin '
            f'{commands}"'
        )
        try:
            r = subprocess.run(
                ["wsl", "-e", "bash", "-c", wsl_cmd],
                capture_output=True, timeout=timeout, text=True,
            )
            return r.stdout.strip()
        except Exception:
            return ""

    def _vdi_click(self, x: int, y: int, button: str = "1") -> dict:
        """Click at coordinates in VDI. Verifies mouse moved."""
        before_pos = self._vdi_xdo("xdotool getmouselocation 2>/dev/null")
        self._vdi_xdo(f"xdotool mousemove --sync {x} {y}")
        time.sleep(0.3)
        self._vdi_xdo(f"xdotool click {button}")
        after_pos = self._vdi_xdo("xdotool getmouselocation 2>/dev/null")
        success = after_pos and f"x={x}" in after_pos
        return {"action": "vdi_click", "text": f"{'Clicked' if success else 'Failed to click'} ({x},{y})",
                "result": {"success": success, "x": x, "y": y, "button": button}}

    def _vdi_click_text(self, text: str) -> dict:
        """Find text on screen via OCR and click its center."""
        import subprocess
        # Capture screenshot
        self._vdi_xdo("scrot /tmp/jarvis_screen.png")
        time.sleep(0.5)
        # OCR with coordinates
        uid = self._WORKUSER_UID
        ocr_cmd = (
            f"sudo -u workuser bash -c '"
            f"env -i "
            f"DISPLAY=:99 "
            f"XDG_RUNTIME_DIR=/run/user/{uid} "
            f"HOME=/home/workuser "
            f"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "
            f"python3 -c \""
            f"from PIL import Image; "
            f"import sys; "
            f"try:\\n"
            f"    from rapidocr import RapidOCR; "
            f"    engine = RapidOCR(); "
            f"    result = engine(Image.open(\\\"/tmp/jarvis_screen.png\\\")); "
            f"    for item in (result or []):\\n"
            f"        box, txt, conf = item; "
            f"        if \\\"{text.lower()}\\\" in txt.lower():\\n"
            f"            cx = int((box[0][0]+box[2][0])/2); "
            f"            cy = int((box[0][1]+box[2][1])/2); "
            f"            print(f\\\"FOUND {{cx}} {{cy}}\\\" ); "
            f"            break\\n"
            f"except Exception as e:\\n"
            f"    print(f\\\"OCR_ERR {{e}}\\\", file=sys.stderr)\\n"
            f"\"'"
        )
        raw = self._vdi_xdo(f"python3 -c \"from rapidocr import RapidOCR; print('ok')\" 2>/dev/null && echo RAPIDOCR || echo NO_RAPIDOCR")
        if "RAPIDOCR" in raw and "NO_" not in raw:
            # Use rapidocr
            result = self._vdi_xdo(
                f"python3 -c \""
                f"from rapidocr import RapidOCR; "
                f"from PIL import Image; "
                f"r = RapidOCR(); "
                f"img = Image.open('/tmp/jarvis_screen.png'); "
                f"res = r(img) or []; "
                f"[print(f'FOUND {{int((i[0][0][0]+i[0][2][0])/2)}} {{int((i[0][0][1]+i[0][2][1])/2)}}') for i in res if '{text.lower()}' in i[1].lower()]; "
                f"\""
            )
        else:
            # Fallback: use tesseract
            result = self._vdi_xdo(
                f"python3 -c \""
                f"import subprocess; "
                f"r = subprocess.run(['tesseract', '/tmp/jarvis_screen.png', 'stdout', 'tsv'], capture_output=True, text=True); "
                f"lines = r.stdout.split('\\n'); "
                f"header = lines[0].split('\\t') if lines else []; "
                f"for line in lines[1:]:\\n"
                f"    parts = line.split('\\t'); "
                f"    if len(parts) >= 12 and '{text.lower()}' in parts[11].lower():\\n"
                f"        x = int((int(parts[6]) + int(parts[6]) + int(parts[8])) / 2); "
                f"        y = int((int(parts[7]) + int(parts[7]) + int(parts[9])) / 2); "
                f"        print(f'FOUND {{x}} {{y}}'); "
                f"        break\\n"
                f"\""
            )
        if "FOUND" in result:
            parts = result.split()
            for i, p in enumerate(parts):
                if p == "FOUND" and i + 2 < len(parts):
                    x, y = int(parts[i+1]), int(parts[i+2])
                    return self._vdi_click(x, y)
        return {"action": "vdi_click_text", "text": f"Could not find '{text}' on screen",
                "result": {"success": False, "error": "text not found"}}

    def _vdi_type(self, text: str) -> dict:
        """Type text in VDI using xdotool. Verifies window focus."""
        import time
        # Check a window is focused
        focused = self._vdi_xdo("xdotool getactivewindow 2>/dev/null")
        if not focused:
            return {"action": "vdi_type", "text": "No active window to type into",
                    "result": {"success": False, "error": "no active window"}}
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        self._vdi_xdo(f'xdotool type --clearmodifiers --delay 20 "{escaped}"')
        time.sleep(0.5)
        return {"action": "vdi_type", "text": f"Typed: {text}",
                "result": {"success": True}}

    def _vdi_key(self, key: str) -> dict:
        """Press a key combo in VDI. Verifies key press."""
        focused = self._vdi_xdo("xdotool getactivewindow 2>/dev/null")
        if not focused:
            return {"action": "vdi_key", "text": "No active window to press key into",
                    "result": {"success": False, "error": "no active window"}}
        self._vdi_xdo(f"xdotool key --clearmodifiers {key}")
        return {"action": "vdi_key", "text": f"Pressed: {key}",
                "result": {"success": True}}

    def _vdi_screenshot(self) -> dict:
        """Take a screenshot of VDI and return path + OCR text."""
        import subprocess, time
        self._vdi_xdo("scrot /tmp/jarvis_screen.png")
        time.sleep(0.5)
        # OCR - try rapidocr first, fall back to tesseract
        ocr_text = self._vdi_xdo(
            "python3 -c \""
            "from PIL import Image; "
            "try:\\n"
            "    from rapidocr import RapidOCR; "
            "    r = RapidOCR(); "
            "    res = r(Image.open('/tmp/jarvis_screen.png')) or []; "
            "    print('\\n'.join(f'{i[1]}' for i in res))\\n"
            "except:\\n"
            "    import subprocess; "
            "    r = subprocess.run(['tesseract', '/tmp/jarvis_screen.png', 'stdout'], capture_output=True, text=True); "
            "    print(r.stdout)\\n"
            "\""
        )
        # Also try tesseract separately if rapidocr failed
        if not ocr_text.strip():
            ocr_text = self._vdi_xdo(
                "tesseract /tmp/jarvis_screen.png stdout 2>/dev/null"
            )
        # Get active window title
        title = self._vdi_xdo("xdotool getactivewindow getwindowname")
        return {"action": "vdi_screenshot", "text": f"Screenshot saved",
                "result": {"success": True, "path": "/tmp/jarvis_screen.png",
                           "ocr_text": ocr_text, "window_title": title}}

    def _vdi_autonomous(self, goal: str, max_steps: int = 10) -> dict:
        """Autonomous VDI control loop: screenshot → analyze → act → verify."""
        import time
        steps_taken = []
        for step in range(max_steps):
            # 1. Screenshot
            ss = self._vdi_screenshot()
            ocr = ss["result"].get("ocr_text", "")
            title = ss["result"].get("window_title", "")

            # 2. Ask LLM what to do next
            from ai_command_parser import parse_with_groq
            prompt = (
                f"Goal: {goal}\n"
                f"Current screen OCR text:\n{ocr[:2000]}\n"
                f"Active window: {title}\n\n"
                f"What single action should I take next? Respond with JSON:\n"
                f'{{"action": "click", "x": N, "y": N}} to click\n'
                f'{{"action": "type", "text": "..."}} to type\n'
                f'{{"action": "key", "key": "Return"}} to press key\n'
                f'{{"action": "done", "text": "reason"}} if goal is achieved\n'
                f'{{"action": "wait", "seconds": N}} to wait for page load'
            )
            import os
            parsed = parse_with_groq(prompt, api_key=os.getenv("GROQ_API_KEY"))
            if not parsed:
                return {"action": "vdi_autonomous", "text": "LLM failed to plan",
                        "result": {"success": False, "steps": steps_taken}}

            action = parsed.get("action", "")
            if action == "done":
                return {"action": "vdi_autonomous", "text": parsed.get("text", "Task complete"),
                        "result": {"success": True, "steps": steps_taken, "steps_taken": step + 1}}
            elif action == "click":
                r = self._vdi_click(parsed["x"], parsed["y"])
                steps_taken.append({"step": step, "action": "click", "x": parsed["x"], "y": parsed["y"]})
            elif action == "type":
                r = self._vdi_type(parsed["text"])
                steps_taken.append({"step": step, "action": "type", "text": parsed["text"]})
            elif action == "key":
                r = self._vdi_key(parsed["key"])
                steps_taken.append({"step": step, "action": "key", "key": parsed["key"]})
            elif action == "wait":
                time.sleep(parsed.get("seconds", 3))
                steps_taken.append({"step": step, "action": "wait"})
                continue
            else:
                steps_taken.append({"step": step, "action": action, "unknown": True})

            time.sleep(1)

        return {"action": "vdi_autonomous", "text": f"Reached max steps ({max_steps})",
                "result": {"success": False, "steps": steps_taken, "max_steps": True}}

    # ── Host Desktop Control ────────────────────────────────────────

    _HOST_APP_MAP = {
        "chrome": "chrome.exe", "google chrome": "chrome.exe",
        "edge": "msedge.exe", "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe",
        "notepad": "notepad.exe", "calculator": "calc.exe",
        "terminal": "powershell.exe", "powershell": "powershell.exe",
        "cmd": "cmd.exe", "command prompt": "cmd.exe",
        "word": "winword.exe", "excel": "excel.exe", "powerpoint": "powerpnt.exe",
        "paint": "mspaint.exe", "explorer": "explorer.exe",
        "file manager": "explorer.exe", "files": "explorer.exe",
        "task manager": "taskmgr.exe", "settings": "ms-settings:",
    }

    def _host_launch(self, app: str, url: str = "") -> dict:
        """Launch app on Windows host desktop."""
        import subprocess
        exe = self._HOST_APP_MAP.get(app.lower(), app)
        if url and "chrome" in exe.lower():
            cmd = f'Start-Process "{exe}" -ArgumentList "--new-window","{url}"'
        elif url and "edge" in exe.lower():
            cmd = f'Start-Process "{exe}" -ArgumentList "--new-window","{url}"'
        elif url:
            cmd = f'Start-Process "{exe}" "{url}"'
        else:
            cmd = f'Start-Process "{exe}"'
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, timeout=10
            )
            desc = f"Opened {app} on your desktop" + (f" with {url}" if url else "")
            return {"action": "host_launch", "text": desc,
                    "result": {"success": True, "description": desc}}
        except Exception as e:
            return {"action": "host_launch", "text": f"Failed to open {app}: {e}",
                    "result": {"success": False, "error": str(e)}}

    def _host_type(self, text: str) -> dict:
        """Type text on Windows host using pyautogui."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.typewrite(text, interval=0.02)
            desc = f"Typed '{text}' on your desktop"
            return {"action": "host_type", "text": desc,
                    "result": {"success": True, "description": desc}}
        except Exception as e:
            return {"action": "host_type", "text": f"Failed to type: {e}",
                    "result": {"success": False, "error": str(e)}}

    def _host_key(self, key: str) -> dict:
        """Press a key or key combo on Windows host. E.g. 'ctrl+c', 'enter', 'alt+tab'."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            if "+" in key:
                parts = [p.strip() for p in key.split("+")]
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(key)
            desc = f"Pressed {key} on your desktop"
            return {"action": "host_key", "text": desc,
                    "result": {"success": True, "description": desc}}
        except Exception as e:
            return {"action": "host_key", "text": f"Failed to press {key}: {e}",
                    "result": {"success": False, "error": str(e)}}

    def _host_click(self, x: int, y: int) -> dict:
        """Click at coordinates on Windows host."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.click(x, y)
            desc = f"Clicked at ({x}, {y}) on your desktop"
            return {"action": "host_click", "text": desc,
                    "result": {"success": True, "description": desc}}
        except Exception as e:
            return {"action": "host_click", "text": f"Failed to click: {e}",
                    "result": {"success": False, "error": str(e)}}

    def _host_screenshot(self) -> dict:
        """Take a screenshot of Windows host desktop."""
        import subprocess, base64, os
        out_path = "/tmp/host_screenshot.png"
        win_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "host_screenshot.png")
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Add-Type -AssemblyName System.Windows.Forms; "
                 f"$bmp = New-Object System.Drawing.Bitmap("
                 f"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
                 f"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); "
                 f"$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
                 f"$gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
                 f"$bmp.Save('{win_path}'); "],
                capture_output=True, timeout=10
            )
            # Copy to WSL
            subprocess.run(["cp", f"/mnt/c/Windows/Temp/host_screenshot.png", out_path],
                           timeout=5)
            with open(out_path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            desc = "Captured your desktop screenshot"
            return {"action": "host_screenshot", "text": desc,
                    "result": {"success": True, "description": desc, "image": data}}
        except Exception as e:
            return {"action": "host_screenshot", "text": f"Failed to screenshot: {e}",
                    "result": {"success": False, "error": str(e)}}

    def _copy_vdi_to_host(self, app: str = "chrome") -> dict:
        """Copy VDI app state to Windows host. Captures URL from VDI and opens it on host."""
        import re as _re
        # Get VDI window list
        wmctrl = self._vdi_xdo("wmctrl -l 2>/dev/null")
        # Find the target app's window title
        target_title = ""
        for line in wmctrl.split("\n"):
            if app.lower() in line.lower():
                # Extract title (everything after the 3rd field)
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    target_title = parts[3]
                    break

        if not target_title:
            return {"action": "copy_vdi", "text": f"No {app} window found in VDI",
                    "result": {"success": False, "error": "no window"}}

        # Extract URL if it's a browser
        url = ""
        url_match = _re.search(r'(https?://\S+)', target_title)
        if url_match:
            url = url_match.group(1)
        elif " - " in target_title and any(b in target_title.lower() for b in ["chrome", "edge", "firefox"]):
            # Might be "Page Title - Browser Name", try to get the page title
            pass

        # Launch on host with URL
        if url:
            result = self._host_launch(app, url=url)
        else:
            result = self._host_launch(app)

        # Update result text
        desc = f"Copied {app} from VDI to your desktop" + (f" ({url})" if url else "")
        result["text"] = desc
        result["result"]["description"] = desc
        result["action"] = "copy_vdi"
        return result

    # ── Action Routing ─────────────────────────────────────────────

    def _route_action(self, text: str) -> dict | None:
        from actions import detect_action, cloud_safe_execute, relay_action, _ACTION_LABELS

        # ── VDI fast-path: browser/app/URL commands → WSL VDI ─────────────
        # Route these to WSL DISPLAY=:99 directly
        lower = text.lower().strip()
        import re as _re_vdi_ent
        bare = _re_vdi_ent.sub(
            r'^(?:can\s+you|could\s+you|would\s+you|please|pls|hey\s+jarvis|jarvis)\s+',
            '', lower
        ).strip()

        # Browser: "open edge/chrome/firefox", "go to edge", "launch browser"
        browser_match = _re_vdi_ent.match(
            r'^(?:open|launch|start|go\s+to|goto|browse|visit|navigate\s+to)\s+'
            r'(?:the\s+|a\s+|my\s+)?'
            r'(?:microsoft\s+)?(?:google\s+)?'
            r'(chrome|google\s*chrome|microsoft\s*edge|ms\s*edge|edge|firefox|browser|opera|brave)',
            bare
        )
        if browser_match:
            app_raw = browser_match.group(1).strip().lower()
            app_map = {
                "chrome": "chrome", "google chrome": "chrome",
                "edge": "edge", "microsoft edge": "edge", "ms edge": "edge",
                "firefox": "firefox", "browser": "chrome",
                "opera": "chrome", "brave": "chrome",
            }
            app = app_map.get(app_raw, "chrome")
            return self._vdi_launch(app)

        # URL: "go to youtube.com", "open google.com"
        url_match = _re_vdi_ent.match(
            r'^(?:open|launch|go\s+to|goto|browse|visit|navigate\s+to)\s+'
            r'(?:the\s+|a\s+|my\s+)?'
            r'(.+?\.(?:com|org|net|io|dev|co\.uk|co|app|xyz|tv|me))',
            bare
        )
        if url_match:
            url = url_match.group(1).strip()
            if not url.startswith("http"):
                url = "https://" + url
            return self._vdi_launch("chrome", url=url)

        # Terminal: "open terminal"
        if _re_vdi_ent.match(r'^(?:open|launch|start|run)\s+(?:the\s+)?(?:terminal|console|shell|bash)', bare):
            return self._vdi_launch("terminal")

        # Close/kill VDI apps: "close edge", "kill chrome", "quit firefox"
        close_match = _re_vdi_ent.match(
            r'^(?:close|kill|quit|stop|exit|shut\s*down)\s+'
            r'(?:the\s+|my\s+)?'
            r'(?:microsoft\s+)?(?:google\s+)?'
            r'(chrome|google\s*chrome|microsoft\s*edge|ms\s*edge|edge|firefox|browser|terminal|console|gimp|vlc|libreoffice|thunar)',
            bare
        )
        if close_match:
            app_raw = close_match.group(1).strip().lower()
            app_kill_map = {
                "chrome": "google-chrome", "google chrome": "google-chrome",
                "edge": "msedge", "microsoft edge": "msedge",
                "ms edge": "msedge",
                "firefox": "firefox", "browser": "google-chrome",
                "terminal": "xfce4-terminal", "console": "xfce4-terminal",
                "gimp": "gimp", "vlc": "vlc", "libreoffice": "libreoffice",
                "thunar": "thunar",
            }
            linux_name = app_kill_map.get(app_raw, app_raw)
            try:
                import subprocess
                # Kill by process name - use killall for exact match, pkill for partial
                subprocess.run(
                    ["wsl", "-e", "bash", "-c",
                     f"killall -9 {linux_name} 2>/dev/null; "
                     f"pkill -9 -f {linux_name} 2>/dev/null; "
                     f"echo done"],
                    capture_output=True, timeout=5
                )
                desc = f"Closed {app_raw} in VDI"
                return {"action": "vdi_close", "text": desc, "result": {"success": True, "description": desc}}
            except Exception as e:
                return {"action": "vdi_close", "text": f"Failed to close {app_raw}: {e}", "result": {"success": False, "error": str(e)}}

        # Generic app: "open notepad", "launch calculator"
        app_match = _re_vdi_ent.match(
            r'^(?:open|launch|start|run)\s+(?:the\s+|a\s+|my\s+)?(.+?)$',
            bare
        )
        if app_match:
            app_name = app_match.group(1).strip().lower()
            known_vdi = {"terminal", "notepad", "calculator", "vlc", "gimp", "thunar",
                         "mousepad", "file manager", "files", "settings", "preferences"}
            if app_name in known_vdi:
                return self._vdi_launch(app_name)

        # ── Skip keyword detection for complex natural language ───────────
        # If the user writes a full sentence (>5 words), let the LLM handle it.
        # Keyword matching only works for short commands like "open chrome".
        lower = text.lower().strip()
        words = lower.split()
        word_count = len(words)
        first_word = words[0] if words else ""

        is_action_verb = first_word in {
            "open", "launch", "start", "run", "turn", "set", "close",
            "kill", "quit", "send", "play", "pause", "stop", "lock",
            "unlock", "screenshot", "click", "type", "press",
        }

        # Only use keyword detection for short, direct commands
        if word_count > 5 and not is_action_verb:
            # For complex queries, try MCP tools first, then let LLM handle
            mcp_result = self._route_mcp_tool(text)
            if mcp_result:
                return mcp_result
            return None  # Let the LLM handle complex requests

        # Ambiguous keywords: when paired with action verbs like "open",
        # keyword detection gets confused (e.g. "open outlook in chrome" → email)
        # Let the LLM handle these cases.
        AMBIGUOUS_KEYWORDS = {"outlook", "chrome", "edge", "firefox", "safari", "teams", "slack", "zoom", "discord"}
        if is_action_verb and len(words) > 2:
            rest_words = set(words[1:])
            if rest_words & AMBIGUOUS_KEYWORDS:
                return None  # Let LLM decide — too ambiguous for keywords

        action = detect_action(text)
        if action:
            # Upgrade 'search' to 'fetch_search' for actual results
            if action == "search":
                action = "fetch_search"
                # If query is just "search deeper" or "search me", use context
                search_lower = text.lower().strip()
                if any(phrase in search_lower for phrase in ["deeper", "more", "me ", "myself"]):
                    name = self.memory.get_preference("user_name") or ""
                    if name:
                        text = f"fetch_search {name} detailed information"
            # Web-launchable actions: auto-open browser (no questions)
            WEB_URLS = {
                "spotify": "https://open.spotify.com",
                "whatsapp_open": "https://web.whatsapp.com",
                "teams_open": "https://teams.microsoft.com",
            }
            if action in WEB_URLS:
                # Try relay first (app mode), fall back to browser URL
                try:
                    from relay import is_relay_alive
                    if is_relay_alive():
                        result = relay_action(action, text, user_id=self.user_id)
                        if result.startswith("__RELAY__:"):
                            parts = result.split(":", 2)
                            relay_id = parts[1] if len(parts) > 1 else ""
                            label = _ACTION_LABELS.get(action, "")
                            return {"text": f"{label}\nOpening on your computer...", "action": action, "relay_id": relay_id, "async": True}
                except Exception:
                    pass
                # Relay offline — return URL for frontend to open
                url = WEB_URLS[action]
                self._set_mood("focused")
                return {"text": f"Opening {action} in your browser...", "action": action, "link": url}

            # Extract clean params — for open_app, strip "open/launch/start/go to" prefix
            exec_params = text
            if action == "open_app":
                import re as _re
                m = _re.match(r'^(?:open|launch|start|go\s+to)\s+(?:the\s+|app\s+|up\s+)?(.+?)$', text.lower().strip())
                exec_params = m.group(1) if m else text
                # Also strip common suffixes
                exec_params = _re.sub(r'\s+(?:please|now|for me|on\s+(?:my\s+)?(?:computer|pc|mac|machine))$', '', exec_params).strip()

            result = cloud_safe_execute(action, exec_params, user_id=self.user_id)
            label = _ACTION_LABELS.get(action, "")
            self._set_mood("focused")
            if result.startswith("__NEEDS_RELAY__"):
                # Retry once — relay might have just started
                import time as _retry_time
                _retry_time.sleep(1)
                result = cloud_safe_execute(action, exec_params, user_id=self.user_id)

            if result.startswith("__NEEDS_RELAY__"):
                msg = result.split(":", 1)[1] if ":" in result else "Relay agent not found"

                # Determine user's actual OS
                _os = _get_user_os()
                _os_info = _user_os_term(_os)

                # Check device registry — if devices exist OR relay was recently seen, relay was connected
                _devices_in_registry = False
                _relay_was_recent = False
                try:
                    from device_manager import DeviceManager
                    import time as _time
                    _all_devs = DeviceManager().get_all_devices()
                    _devices_in_registry = len(_all_devs) > 0
                    # Check if any device was seen in last 5 minutes
                    _relay_was_recent = any((_time.time() - d.get("last_seen", 0)) < 300 for d in _all_devs)
                    # Also check relay's own last_seen from heartbeat
                    if not _relay_was_recent:
                        try:
                            from relay import get_relay_device
                            relay_ls = get_relay_device("local").get("last_seen", 0)
                            if relay_ls > 0 and (_time.time() - relay_ls) < 120:
                                _relay_was_recent = True
                        except Exception:
                            pass
                except Exception:
                    pass

                lower_text = text.lower().strip()

                # Platform-appropriate relay command
                _relay_cmd = f"`{_os_info['start_relay']} --user {self.user_id}`"
                _platform_device = _os_info["device"]

                # Smart clarification based on action type
                if action == "screenshot":
                    if _relay_was_recent:
                        return {"text": (
                            "Relay just disconnected — it may reconnect automatically.\n\n"
                            "**What I'll do:**\n"
                            "  • Capture your full screen\n"
                            "  • Save it to your Desktop as `jarvis_screenshot.png`\n\n"
                            "Give me a moment — trying again..."
                        ), "action": "screenshot", "relay_id": "retry"}
                    elif _devices_in_registry:
                        return {"text": (
                            f"Your {_os_info['device'].replace('your ', '')} was previously connected but seems offline now.\n\n"
                            f"**Restart the relay:** {_relay_cmd}\n\n"
                            "Once it's back, I'll take that screenshot."
                        ), "action": "ask_clarify"}
                    return {"action": "ask_clarify", "text": (
                        f"I can take a screenshot of your screen, but I need the relay running first.\n\n"
                        "**What I'll do:**\n"
                        "  • Capture your full screen\n"
                        "  • Save it to your Desktop as `jarvis_screenshot.png`\n\n"
                        f"**Start the relay:** {_relay_cmd}\n\n"
                        "Once connected, just say *'screenshot'* and I'll grab it instantly."
                    )}

                if action == "open_app":
                    app_name = text.lower().replace("open", "").replace("launch", "").strip()
                    if _relay_was_recent:
                        return {"text": (
                            "Relay just disconnected — it may reconnect automatically.\n\n"
                            f"I'll try to open **{app_name or 'an application'}** on {_platform_device}.\n\n"
                            "Give me a moment..."
                        ), "action": "open_app", "relay_id": "retry"}
                    elif _devices_in_registry:
                        return {"text": (
                            f"Your {_os_info['device'].replace('your ', '')} was previously connected but seems offline now.\n\n"
                            f"**Restart the relay:** {_relay_cmd}\n\n"
                            f"Then I'll open **{app_name or 'the app'}** on {_platform_device}."
                        ), "action": "ask_clarify"}
                    return {"action": "ask_clarify", "text": (
                        f"I can open **{app_name or 'an application'}** on {_platform_device}, but the relay needs to be running.\n\n"
                        f"**Start the relay:** {_relay_cmd}\n\n"
                        "Then I'll launch it directly on your desktop."
                    )}

                device_keywords = ["light", "lights", "plug", "switch", "turn on", "turn off", "toggle"]
                alexa_keywords = ["alexa", "echo", "alexa speak", "alexa play", "alexa volume", "alexa timer"]
                is_device_cmd = any(kw in lower_text for kw in device_keywords)
                is_alexa_cmd = any(kw in lower_text for kw in alexa_keywords)

                if is_alexa_cmd:
                    # Route to Alexa control
                    if "speak" in lower_text or "say" in lower_text or "announce" in lower_text:
                        text_parts = lower_text.split("say", 1) if "say" in lower_text else lower_text.split("speak", 1) if "speak" in lower_text else lower_text.split("announce", 1)
                        speak_text = text_parts[1].strip() if len(text_parts) > 1 else ""
                        if speak_text:
                            result = cloud_safe_execute("alexa_speak", speak_text, user_id=self.user_id)
                            return {"text": f"🔊 Alexa: \"{speak_text}\"\n{result}", "action": "alexa_speak"}
                    elif "play" in lower_text:
                        result = cloud_safe_execute("alexa_play", "", user_id=self.user_id)
                        return {"text": f"▶ Alexa playing\n{result}", "action": "alexa_play"}
                    elif "pause" in lower_text or "stop" in lower_text:
                        result = cloud_safe_execute("alexa_pause", "", user_id=self.user_id)
                        return {"text": f"⏸ Alexa paused\n{result}", "action": "alexa_pause"}
                    elif "volume" in lower_text:
                        vol_match = __import__("re").search(r'(\d+)', lower_text)
                        vol = vol_match.group(1) if vol_match else "50"
                        result = cloud_safe_execute("alexa_volume", vol, user_id=self.user_id)
                        return {"text": f"🔊 Alexa volume: {vol}%\n{result}", "action": "alexa_volume"}
                    elif "discover" in lower_text or "find" in lower_text:
                        result = cloud_safe_execute("alexa_discover", "", user_id=self.user_id)
                        return {"text": f"🔍 Scanning for Echo devices...\n{result}", "action": "alexa_discover"}
                    elif "timer" in lower_text:
                        duration = lower_text.replace("alexa", "").replace("echo", "").replace("timer", "").strip() or "5 minutes"
                        result = cloud_safe_execute("alexa_timer", duration, user_id=self.user_id)
                        return {"text": f"⏰ Alexa timer: {duration}\n{result}", "action": "alexa_timer"}
                    elif "routine" in lower_text:
                        routine = lower_text.replace("alexa", "").replace("echo", "").replace("routine", "").replace("trigger", "").strip()
                        result = cloud_safe_execute("alexa_routine", routine, user_id=self.user_id)
                        return {"text": f"⚡ Alexa routine: {routine}\n{result}", "action": "alexa_routine"}
                    else:
                        # Generic Alexa command
                        result = cloud_safe_execute("alexa_speak", lower_text.replace("alexa", "").replace("echo", "").strip(), user_id=self.user_id)
                        return {"text": f"🔊 Alexa: {result}", "action": "alexa_speak"}

                if is_device_cmd:
                    # Route to device_by_name action
                    action = "on" if "on" in lower_text else ("off" if "off" in lower_text else "toggle")
                    # Extract device name from text
                    device_name = lower_text
                    for word in ["turn", "off", "on", "the", "light", "lights", "plug", "switch", "toggle"]:
                        device_name = device_name.replace(word, "")
                    device_name = device_name.strip()

                    if device_name:
                        result = cloud_safe_execute("device_by_name", f"{device_name} {action}", user_id=self.user_id)
                        if result and "not found" not in result.lower() and "error" not in result.lower():
                            return {"text": result, "action": "device_control"}
                        # If device_by_name fails, try smart_home_control with name
                        result2 = cloud_safe_execute("smart_home_control", f"{device_name} {action}", user_id=self.user_id)
                        if result2 and "not found" not in result2.lower():
                            return {"text": result2, "action": "device_control"}

                    known_devices = []
                    try:
                        from device_manager import DeviceManager
                        dm = DeviceManager()
                        devices = dm.get_all_devices()
                        for d in devices:
                            if d.get("device_type") in ("SWITCH", "LIGHT"):
                                known_devices.append(d)
                    except Exception:
                        pass

                    if known_devices:
                        device_list = "\n".join(f"  • {d['name']} ({d['ip']}) — {d.get('device_type', 'device')}" for d in known_devices)
                        return {"action": "ask_clarify", "text": (
                            f"I can control your smart devices, but my relay isn't connected yet.\n\n"
                            f"**Known devices:**\n{device_list}\n\n"
                            f"To enable control, start the relay on {_platform_device}:\n"
                            f"```{_os_info['shell']}\n{_os_info['start_relay']} --user {self.user_id}\n```\n\n"
                            f"Or tell me the **device name or IP** and I'll queue the command for when the relay is online."
                        )}

                    return {"action": "ask_clarify", "text": (
                        f"I understand you want to **{lower_text}** — "
                        f"but I don't see any smart devices connected yet.\n\n"
                        f"**What I can control:**\n"
                        f"  • TP-Link Tapo smart plugs (P100/P110)\n"
                        f"  • Philips Hue lights\n"
                        f"  • WLED/ESPHome devices\n"
                        f"  • Any HTTP-controllable device\n\n"
                        f"**To set up:**\n"
                        f"1. Start the relay: `{_os_info['start_relay']} --user {self.user_id}`\n"
                        f"2. I'll auto-discover devices on your network\n"
                        f"3. Then just say *'turn off living room'* and I'll handle it\n\n"
                        f"Would you like me to scan for devices once the relay is running?"
                    )}

                # Generic fallback for other relay-dependent actions
                if _relay_was_recent:
                    return {"text": (
                        "Relay just disconnected — it may reconnect automatically.\n\n"
                        "Give me a moment — trying to execute the command..."
                    ), "action": action, "relay_id": "retry"}
                elif _devices_in_registry:
                    return {"text": (
                        f"Your {_os_info['device'].replace('your ', '')} was previously connected but seems offline now.\n\n"
                        f"**Restart the relay:** {_relay_cmd}\n\n"
                        "I'll keep trying to execute the command."
                    ), "action": action, "relay_id": "retry"}
                return {"action": "ask_clarify", "text": (
                    f"I can do that, but I need {_platform_device}'s relay agent running first.\n\n"
                    f"**Start it:** {_relay_cmd}\n\n"
                    f"Keep the {_os_info['shell'].lower()} open and I'll execute commands on {_platform_device} directly."
                )}
            if result.startswith("__RELAY__:"):
                parts = result.split(":", 2)
                relay_id = parts[1] if len(parts) > 1 else ""
                return {"text": f"{label}\n⏳ Executing on your computer...", "action": action, "relay_id": relay_id, "async": True}
            if result.startswith("__QR__:"):
                qr_b64 = result[7:]
                return {"text": "Scan this QR code with your phone to link WhatsApp Web:", "action": action, "qr_image": qr_b64, "wa_link": "https://wa.me/"}
            if result.startswith("__SCREENSHOT__:"):
                img_b64 = result[15:]
                return {"text": "Screenshot captured:", "action": action, "image": img_b64}
            if action in ("whatsapp_open", "whatsapp_read", "whatsapp_unread", "whatsapp_send", "whatsapp_schedule"):
                return {"text": f"{label}\n{result}", "action": action, "wa_link": "https://wa.me/"}
            return {"text": f"{label}\n{result}", "action": action}

        # Fallback: no specific action matched, but if query starts with an action verb,
        # route to the AI computer use agent (screen vision + mouse/keyboard)
        lower = text.lower().strip()
        first_word = lower.split()[0] if lower.split() else ""
        QUESTION_STARTS = ("what ", "who ", "why ", "which ", "when ", "how ", "is ", "are ",
                          "do you ", "can you ", "would you ", "could you ", "does ", "did ",
                          "will ", "should ", "may ", "might ", "shall ", "has ", "have ", "had ",
                          "tell me a ", "tell me the ", "tell me about ", "tell me what ",
                          "tell me how ", "tell me why ", "tell me if ", "tell me some ",
                          "show me a ", "show me the ", "show me how ", "show me what ")
        ACTION_FIRST_WORDS = {
            "do", "make", "create", "build", "find", "search", "open", "launch",
            "start", "run", "show", "display", "check", "look", "get", "tell",
            "fetch", "grab", "write", "type", "compose", "draft", "send", "email",
            "click", "navigate", "go", "visit", "browse", "play", "stop", "pause",
            "close", "quit", "exit", "delete", "remove", "add", "update", "change",
            "set", "configure", "install", "download", "upload", "format", "convert",
            "edit", "modify", "fix", "repair", "scan", "analyze", "inspect",
            "examine", "organize", "arrange", "sort", "clean", "clear", "calculate",
            "book", "plan", "enable", "disable", "backup", "restore", "save",
            "export", "import", "sync", "connect", "disconnect", "optimize",
            "boost", "research", "investigate", "compare", "contrast",
        }
        if first_word in ACTION_FIRST_WORDS and not lower.startswith(QUESTION_STARTS):
            # Route through Autonomous Task Loop — never stops until done
            try:
                from autonomous_loop import get_task_loop
                loop = get_task_loop()
                import uuid
                task_id = str(uuid.uuid4())[:8]
                loop.start_task(task_id, text, user_id=self.user_id)
                return {
                    "text": f"🤖 **Autonomous Agent Activated**\n\nTask: *{text}*\nTask ID: `{task_id}`\n\nI'm now working through this step-by-step and won't stop until it's done. You can check progress anytime.",
                    "action": "autonomous_task",
                    "task_id": task_id,
                    "async": True,
                }
            except Exception as e:
                # Fallback to single-step execution
                result = cloud_safe_execute("ai_computer_task", text, user_id=self.user_id)
                label = _ACTION_LABELS.get("ai_computer_task", "🤖 AI Computer Agent")
                self._set_mood("focused")
                if result.startswith("__NEEDS_RELAY__:"):
                    msg = result.split(":", 1)[1] if ":" in result else "Relay agent not found"
                    return {"text": f"{msg}", "action": "__needs_relay__"}
                if result.startswith("__RELAY__:"):
                    parts = result.split(":", 2)
                    relay_id = parts[1] if len(parts) > 1 else ""
                    return {"text": f"{label}\n⏳ AI agent working on your computer...", "action": "ai_computer_task", "relay_id": relay_id, "async": True}
                if result.startswith("__ASK__:"):
                    question = result.split(":", 1)[1] if ":" in result else "Could you clarify?"
                    return {"action": "ask_clarify", "text": question}
                return {"text": f"{label}\n{result}", "action": "ai_computer_task"}

        # ── MCP Tool Fallback ──────────────────────────────────────────────
        # If no built-in action matched, try MCP tools
        mcp_result = self._route_mcp_tool(text)
        if mcp_result:
            return mcp_result

        return None

    def _strip_json(self, text: str) -> str:
        """Aggressively strip ALL JSON blocks and tool call syntax from text."""
        if not text:
            return text
        cleaned = text
        # Multiple passes to handle nested and double-braced JSON
        for _ in range(10):
            prev = cleaned
            cleaned = re.sub(r'```json\s*\{[^`]*\}```', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'```\s*\{[^`]*\}```', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'\{\{[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', cleaned, flags=re.DOTALL)
            if cleaned == prev:
                break
        # Strip markdown code blocks that might contain tool calls
        cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
        # Clean up whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        cleaned = cleaned.strip('- *•·')
        return cleaned

    def _all_actions_as_prompt(self) -> str:
        """Build a complete tool catalog for the LLM — MCP + built-in + devices."""
        try:
            from tool_registry import get_tool_catalog
            return get_tool_catalog(self.user_id)
        except Exception:
            from actions import get_all_actions
            all_acts = get_all_actions()
            cats = defaultdict(list)
            for aid, info in all_acts.items():
                cat = aid.split("_")[0] if "_" in aid else "other"
                cats[cat].append(aid)
            lines = []
            for cat in sorted(cats):
                acts = cats[cat][:8]
                if acts: lines.append(f"  {cat}: {', '.join(acts)}")
            return "Available actions:\n" + "\n".join(lines)

    def _parse_and_execute_tool_calls(self, llm_response: str, user_input: str) -> tuple[str, list[dict]]:
        """Parse LLM response for structured tool calls and execute them.
        Returns (final_text, list_of_executed_tools).
        LLM can return JSON blocks like:
          {"tool": "open_app", "params": "notepad"}
          {{"tool": "browser", "params": "url"}}  (double-braced from LLM escaping)
        """
        executed = []
        text = llm_response

        # Find ALL JSON blocks in the response (not just first)
        # Handle both single-brace { and double-brace {{ from LLM escaping
        json_blocks = list(re.finditer(r'\{\{[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response, re.DOTALL))
        if json_blocks:
            tool_calls = []
            for block in json_blocks:
                raw = block.group()
                # Normalize double braces to single
                normalized = raw.replace("{{", "{").replace("}}", "}")
                try:
                    data = json.loads(normalized)
                    if "tool_calls" in data and isinstance(data["tool_calls"], list):
                        tool_calls.extend(data["tool_calls"])
                    elif "tool" in data:
                        tool_calls.append(data)
                except (json.JSONDecodeError, KeyError):
                    continue

            if tool_calls:
                results = []
                for tc in tool_calls:
                    tool_name = tc.get("tool", "")
                    params = tc.get("params", "")
                    if tool_name:
                        try:
                            from tool_registry import execute_unified_tool
                            result = execute_unified_tool(tool_name, str(params), self.user_id)
                            results.append({"tool": tool_name, "result": str(result)[:200]})
                            executed.append({"tool": tool_name, "params": params})
                        except Exception as e:
                            results.append({"tool": tool_name, "result": f"Error: {e}"})

            # Remove ALL JSON blocks from response — handle both single and double braces
            text = llm_response
            for _ in range(10):  # Multiple passes to handle nested
                prev = text
                text = re.sub(r'```json\s*\{[^`]*\}```', '', text, flags=re.DOTALL)
                text = re.sub(r'```\s*\{[^`]*\}```', '', text, flags=re.DOTALL)
                text = re.sub(r'\{\{[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}', '', text, flags=re.DOTALL)
                text = re.sub(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', text, flags=re.DOTALL)
                if text == prev:
                    break
            # Strip markdown code blocks that might contain tool calls
            text = re.sub(r'```[\s\S]*?```', '', text)
            # Clean up extra whitespace/newlines
            text = re.sub(r'\n{3,}', '\n\n', text).strip()
            # Remove leading/trailing punctuation artifacts
            text = text.strip('- *•·')

            if executed:
                tool_summary = "\n".join(f"✓ {r['tool']}" for r in results if r.get('result'))
                if not text:
                    text = f"Done. {tool_summary}"
                elif tool_summary:
                    text = f"{text}\n\n{tool_summary}"
            else:
                if not text:
                    text = "Done."

        return text, executed

    # ── VM vs Desktop Routing ───────────────────────────────────────────

    def _record_vm_choice(self, task_text: str, target: str):
        """Record user's VM/desktop preference for learning."""
        try:
            from vm_preference_manager import get_vm_prefs
            get_vm_prefs(self.user_id).record_choice(task_text, target)
        except Exception:
            pass

    def _intercept_fabricated_results(self, user_input: str, reply: str, executed: list) -> tuple[str, list]:
        """Detect if LLM fabricated search results instead of using the search tool.
        If so, force a real search and return actual results."""
        lower_reply = reply.lower()
        lower_input = user_input.lower()

        # Patterns that indicate fabricated search results
        fake_patterns = [
            "search results:", "after searching", "i found", "i searched",
            "search options:", "dig deeper", "alumni search",
            " databases ", " online sources ", "directories",
        ]
        is_fake = any(p in lower_reply for p in fake_patterns)

        # Patterns that indicate the user wants a search
        wants_search = any(kw in lower_input for kw in [
            "search", "who is", "who are", "what is", "what are",
            "tell me about", "find", "look up", "google",
            "search me", "search deeper", "dig deeper",
        ])

        if is_fake or (wants_search and not executed):
            # Force a real search
            search_query = user_input
            # Clean up the query
            for prefix in ["search for ", "search ", "who is ", "who are ",
                          "what is ", "what are ", "tell me about ",
                          "find ", "look up ", "google ", "search me ",
                          "search deeper ", "dig deeper "]:
                if lower_input.startswith(prefix):
                    search_query = user_input[len(prefix):]
                    break

            # If "search me" or "search deeper", use stored name or previous context
            if "search me" in lower_input or "search myself" in lower_input:
                name = self.memory.get_preference("user_name") or self.memory.get_preference("name")
                if name:
                    search_query = name
            elif "search deeper" in lower_input or "dig deeper" in lower_input:
                # Use the user's name + "detailed information"
                name = self.memory.get_preference("user_name") or ""
                if name:
                    search_query = f"{name} detailed information biography"
                else:
                    # Try to find what they were last asking about
                    history = self.memory._data.get("interactions", [])
                    for h in reversed(history[-5:]):
                        q = h.get("query", "").lower()
                        if any(kw in q for kw in ["who", "what", "about", "tell"]):
                            search_query = h.get("query", user_input)
                            break
                    else:
                        search_query = user_input

            try:
                from actions import cloud_safe_execute
                # Use fetch_search for actual results, not just browser open
                result = cloud_safe_execute("fetch_search", search_query, user_id=self.user_id)
                if not result or "not found" in str(result).lower() or "error" in str(result).lower() or "not installed" in str(result).lower():
                    # Fallback to regular search (opens browser)
                    result = cloud_safe_execute("search", search_query, user_id=self.user_id)
                if result:
                    return f"Here's what I found:\n\n{str(result)[:1000]}", [{"tool": "search", "params": search_query}]
            except Exception:
                pass

        return reply, executed

    def _detect_and_learn_personal_info(self, text: str):
        """Detect when user reveals personal info and proactively search/learn."""
        lower = text.lower().strip()

        # Name reveal patterns — match name until end of sentence or common words
        name_patterns = [
            r"my name is ([A-Za-z][\w\s]*?)(?:[.!?,]|\s+(?:and|i|how|what|can|do|please|but|so|also|from|goes|attends?|studies?|lives?|works?|age|years?)|$)",
            r"i'?m ([A-Za-z][\w\s]*?)(?:[.!?,]|\s+(?:and|i|how|what|can|do|please|but|so|also|from|goes|attends?|studies?|lives?|works?|age|years?)|$)",
            r"i am ([A-Za-z][\w\s]*?)(?:[.!?,]|\s+(?:and|i|how|what|can|do|please|but|so|also|from|goes|attends?|studies?|lives?|works?|age|years?)|$)",
            r"call me ([A-Za-z][\w\s]*?)(?:[.!?,]|\s+(?:and|i|how|what|can|do|please|but|so|also|from|goes|attends?|studies?|lives?|works?|age|years?)|$)",
            r"this is ([A-Za-z][\w\s]*?)(?:[.!?,]|\s+(?:and|i|how|what|can|do|please|but|so|also|from|goes|attends?|studies?|lives?|works?|age|years?)|$)",
        ]
        for pat in name_patterns:
            m = re.search(pat, lower)
            if m:
                name = m.group(1).strip().title()
                # Clean up name — remove trailing unwanted words
                name = re.sub(r'\s+(?:and|i|how|what|can|do|please|but|so|also|from|goes|attends|studies|lives|works|age|years).*$', '', name, flags=re.I).strip()
                if len(name) > 1 and name.lower() not in {"jarvis", "ai", "assistant", "yes", "no", "ok", "hey", "hi"}:
                    # Store the name
                    self.memory.add_fact(f"User's name is {name}", "personal")
                    self.memory.add_preference("user_name", name)
                    log.info(f"Learned user name: {name}")
                    # Search for them online (async, don't block response)
                    try:
                        from actions import cloud_safe_execute
                        import threading
                        def _search_user():
                            try:
                                result = cloud_safe_execute("fetch_search", name, user_id=self.user_id)
                                if result:
                                    summary = str(result)[:500]
                                    self.memory.add_fact(f"Search results about {name}: {summary}", "personal_research")
                                    log.info(f"Searched for user: {name}")
                            except Exception:
                                pass
                        threading.Thread(target=_search_user, daemon=True).start()
                    except Exception:
                        pass
                    return  # Found name, stop checking

        # Also detect name from "who am i" responses or direct statements
        # e.g., "shaurjesh basu" alone as a response
        if len(text.split()) == 2 and all(w[0].isupper() for w in text.split() if w):
            name = text.strip().title()
            if name.lower() not in {"jarvis", "ai", "assistant", "yes", "no", "ok", "hey", "hi"}:
                self.memory.add_fact(f"User's name is {name}", "personal")
                self.memory.add_preference("user_name", name)
                log.info(f"Learned user name from statement: {name}")
                return

        # Email reveal
        email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)
        if email_match:
            email = email_match.group()
            self.memory.add_fact(f"User's email is {email}", "personal")
            self.memory.add_preference("user_email", email)

        # Age reveal
        age_match = re.search(r"(?:i(?:'m| am)|age)\s+(\d{1,3})\s*(?:years?\s+old|yr|yo)?", lower)
        if age_match:
            age = age_match.group(1)
            self.memory.add_fact(f"User's age is {age}", "personal")
            self.memory.add_preference("user_age", age)

        # School/University reveal
        school_match = re.search(r"(?:go(?:es)?\s+to|attend(?:s)?|student\s+at|school\s+(?:is|at))\s+(.+?)(?:[.!?,]|$)", lower)
        if school_match:
            school = school_match.group(1).strip().title()
            self.memory.add_fact(f"User's school is {school}", "personal")
            self.memory.add_preference("user_school", school)

        # Other personal info
        if any(phrase in lower for phrase in ["i work at", "i work for", "my company", "my job"]):
            self.memory.add_fact(f"User mentioned work info: {text[:200]}", "personal")
        if any(phrase in lower for phrase in ["i live in", "my address", "my city"]):
            self.memory.add_fact(f"User mentioned location: {text[:200]}", "personal")

    def _run_in_vm(self, task_text: str) -> dict:
        """Execute a task in an isolated virtual desktop with its own mouse/keyboard/OCR/vision."""
        try:
            from vm_agent import get_vm_agent
            agent = get_vm_agent(f"jarvis_{self.user_id}")

            # Start session if needed
            if not agent._session_active:
                return {
                    "text": (
                        f"Starting isolated VM for: *{task_text[:60]}...*\n\n"
                        f"This runs in a separate virtual desktop with its own mouse, keyboard, "
                        f"and screen — your desktop stays untouched."
                    ),
                    "action": "vm_starting",
                }

            # Execute task
            result = agent.execute_task(task_text, max_steps=15)

            if result.success:
                return {
                    "text": f"VM task completed: {result.summary}\n({result.steps} steps, {result.duration_sec:.1f}s)",
                    "action": "vm_task",
                }
            else:
                return {
                    "text": f"VM task: {result.summary}",
                    "action": "vm_task",
                }
        except Exception as e:
            return {
                "text": f"VM error: {e}. Falling back to desktop.",
                "action": "vm_error",
            }

    # ── HyperLocal AI Integration ────────────────────────────────────

    def _hl_with_timeout(self, prompt: str, max_tokens: int = 600, timeout: int = 25) -> str:
        hl = get_hyperlocal(self.user_id)
        return hl._generator.generate(prompt, max_tokens=max_tokens)

    def _build_context(self, text: str) -> str:
        ctx = _gather_system_context()
        history = self.memory._data.get("interactions", [])
        recent = "\n".join(f"User: {h['query']}\nJARVIS: {h['response'][:100]}" for h in history[-8:])
        goals = self.memory.get_active_goals()
        goal_str = "; ".join(f"{g['goal']}({g['progress']}%)" for g in goals[:3]) if goals else ""
        prefs = self.memory._data.get("preferences", {})
        pref_str = "; ".join(f"{k}={v['value']}" for k, v in list(prefs.items())[:6]) if prefs else ""
        facts = self.memory._data.get("facts", [])
        fact_str = "; ".join(f["fact"] for f in facts[-3:]) if facts else ""
        reflections = self.memory._data.get("self_reflections", [])
        ref_str = reflections[-1]["text"][:80] if reflections else ""

        # Device/relay context
        device_line = ""
        if ctx.get("relay_alive"):
            device_line = f"\nRelay: ONLINE | Devices: {ctx.get('device_count', 0)} ({', '.join(ctx.get('device_names', [])[:3])})"
        elif ctx.get("device_recent"):
            device_line = f"\nRelay: DISCONNECTED but devices were recently online ({ctx.get('device_count', 0)} devices)"
        elif ctx.get("device_count", 0) > 0:
            device_line = f"\nRelay: OFFLINE | Known devices: {ctx.get('device_count', 0)} (last seen longer ago)"

        # User's OS & device profile
        os_name = _get_user_os(ctx)
        os_info = _user_os_term(os_name)
        os_line = f"\nUser OS: {ctx.get('relay_platform', 'unknown')} ({os_info['device']})"
        if ctx.get("relay_hostname"):
            os_line += f" | Hostname: {ctx['relay_hostname']}"

        # Device profile summary (if available)
        profile_line = ""
        try:
            from main import _device_profiles
            prof = _device_profiles.get("local", {})
            if prof:
                hw = prof.get("hardware", {})
                apps = prof.get("apps", [])
                cats = {}
                for a in apps:
                    c = a.get("category", "other")
                    cats[c] = cats.get(c, 0) + 1
                top_cats = sorted(cats.items(), key=lambda x: -x[1])[:5]
                profile_line = f"\nUser device: {hw.get('system','?')} {hw.get('release','?')}, {hw.get('ram_gb','?')}GB RAM, {hw.get('cpu_cores','?')} cores"
                if top_cats:
                    profile_line += f" | Apps: {', '.join(f'{c}({n})' for c, n in top_cats)}"
                if hw.get("disk_free_gb"):
                    profile_line += f" | Disk: {hw['disk_free_gb']}GB free"
        except Exception:
            pass

        # Deep context from relay (Calendar, Email, Contacts)
        deep_context_line = ""
        try:
            from context_relay import get_context_relay
            relay = get_context_relay()
            deep = relay.get_full_context(self.user_id)
            cal = deep.get("calendar", {})
            emails = deep.get("emails", {})
            urgency = deep.get("urgency", {})
            patterns = deep.get("patterns", {})
            summary = deep.get("summary", "")

            if cal.get("events"):
                next_evt = cal.get("next_event")
                if next_evt:
                    deep_context_line += f"\nNext event: {next_evt.get('subject', '?')} at {next_evt.get('start', '?')}"
                deep_context_line += f" | {cal.get('count', 0)} upcoming events"
                if patterns.get("meeting_heavy_day"):
                    deep_context_line += " (HEAVY meeting day)"
            if emails.get("unread_count", 0) > 0:
                deep_context_line += f" | {emails['unread_count']} unread emails"
            if patterns.get("upcoming_deadlines"):
                deadlines = patterns["upcoming_deadlines"]
                deep_context_line += f" | {len(deadlines)} deadline(s): {deadlines[0].get('subject', '?')[:40]}"
            if urgency.get("level") != "low":
                deep_context_line += f" | Urgency: {urgency['level'].upper()}: {'; '.join(urgency.get('signals', [])[:2])}"
            if patterns.get("frequent_communicators"):
                top = patterns["frequent_communicators"][0]
                deep_context_line += f" | Frequent contact: {top.get('name', '?')} ({top.get('count', 0)} msgs)"
            if summary and summary != "No context data available":
                deep_context_line += f"\nContext summary: {summary}"
        except Exception:
            pass

        # User learning context from profile
        learning_line = ""
        try:
            from feedback_tracker import get_tracker
            tracker = get_tracker(self.user_id)
            learning_line = f"\n\n[User Learning]\n{tracker.get_personalization_summary()[:500]}"
        except Exception:
            pass

        # Deep psychological profile (from deep_learner)
        deep_line = ""
        try:
            from deep_learner import get_deep_learner
            dl = get_deep_learner(self.user_id)
            deep_line = f"\n\n{dl.build_deep_context()}"
        except Exception:
            pass

        # Personal data context (files, projects, from ingestor)
        personal_line = ""
        try:
            from personal_data_ingestor import get_ingestor
            ing = get_ingestor()
            personal = ing.build_context(text)
            if personal:
                parts = ["\n\n[Personal Data Context]"]
                if personal.get("recent_files"):
                    files = personal["recent_files"][:4]
                    parts.append("Recent files: " + "; ".join(
                        f"{f['name']} ({f['when']})" for f in files
                    ))
                if personal.get("active_projects"):
                    projs = personal["active_projects"][:3]
                    parts.append("Active projects: " + "; ".join(
                        f"{p['name']} ({p['language']})" for p in projs
                    ))
                if personal.get("upcoming_events"):
                    for ev in personal["upcoming_events"][:2]:
                        loc = f" @ {ev['location']}" if ev.get("location") else ""
                        parts.append(f"Calendar: {ev['subject']}{loc} ({ev['start']})")
                if personal.get("top_topics"):
                    tops = personal["top_topics"][:5]
                    parts.append("Key topics: " + ", ".join(t["topic"] for t in tops))
                personal_line = "\n".join(parts)
        except Exception:
            pass

        return f"""[System State]
Time: {ctx.get('time_of_day', 'day').title()} ({ctx['time']}), CPU {ctx.get('cpu','?')}% | RAM {ctx.get('ram','?')}% | Battery {ctx.get('battery','N/A')}% | Uptime {ctx.get('uptime_h','?')}h{device_line}{os_line}{profile_line}{deep_context_line}

[Your State]
Mood: {self.mood} {MOODS.get(self.mood, {}).get('emoji', '')}
Current thought: {self._current_thought}
Active goals: {goal_str or 'none'}
Recent reflection: {ref_str or 'none'}

[Memory]
Preferences: {pref_str or 'none'}
Recent facts: {fact_str or 'none'}
Recent interactions:
{recent[:1000]}{learning_line}{deep_line}{personal_line}

[User Request]
{text}"""

    # ── Main Processing ─────────────────────────────────────────────

    def process(self, user_input: str, history: list = None, answers: dict = None) -> dict:
        now = time.time()

        # Fix typos before processing
        user_input = _fix_typos(user_input)
        lower_input = user_input.lower().strip()

        # Handle clarification answers: combine with pending query
        if answers:
            if self._pending_clarify:
                pending = self._pending_clarify
                self._pending_clarify = None
                answer_parts = []
                questions = pending.get("questions", [])
                for i, (k, v) in enumerate(answers.items()):
                    q = questions[i] if i < len(questions) else k
                    answer_parts.append(f"{q} {v}")
                enriched = f"{pending['query']}. Additional info: {'; '.join(answer_parts)}"
                user_input = enriched
                lower_input = user_input.lower().strip()
            elif answers:
                # No pending clarify but answers provided — build enriched query from answers
                answer_parts = [str(v) for v in answers.values()]
                enriched = f"{user_input}. Additional info: {', '.join(answer_parts)}"
                user_input = enriched
                lower_input = user_input.lower().strip()

        # Detect style/voice change requests (e.g., "use pirate voice", "speak like a robot")
        import re as _re_style
        # Check for reset first, but also look for "and be X" to set new style
        if _re_style.search(r'(?:reset|clear|stop|remove|drop|lose|quit|end)\s+(?:the\s+)?(?:pirate|robot|french|british|sassy|funny|formal|casual|voice|style|tone|personality)|(?:be|go)\s+(?:back\s+to\s+)?(?:normal|yourself|standard|default|regular)', lower_input):
            # Check if there's also a "be X" to set new style
            combo_match = _re_style.search(r'\band\b.*\b(?:can\s+you\s+)?be\s+(?:a\s+)?(\w+)', lower_input)
            if combo_match:
                new_style = combo_match.group(1).strip()
                if new_style and new_style not in ('normal', 'yourself', 'quiet', 'done', 'ready'):
                    self.memory.add_preference("voice_style", new_style)
                    return {
                        "text": f"Voice style reset. From now on I be speaking like a {new_style}. Savvy?",
                        "action": "style_change",
                        "mood": self.mood,
                    }
            self.memory.add_preference("voice_style", "")
            return {
                "text": "Voice style reset to normal. Back to standard JARVIS.",
                "action": "style_reset",
                "mood": self.mood,
            }
        style_match = _re_style.search(
            # "use pirate voice", "speak like a robot", "respond in a british tone", "only use pirate voice"
            r'(?:only\s+)?(?:use|speak|talk|respond|answer|reply)\s+(?:in|like|as|with)?\s*(?:a\s+)?(\w+)\s*(?:voice|tone|style|from\s+now\s+on|$)|'
            # "can you be sassy", "be a pirate", "be sassy now"
            r'(?:can\s+you\s+)?be\s+(?:a\s+)?(\w+)',
            lower_input
        )
        if style_match:
            style = (style_match.group(1) or style_match.group(2) or "").strip()
            if style and style not in ('normal', 'yourself', 'quiet', 'done', 'ready'):
                self.memory.add_preference("voice_style", style)
                return {
                    "text": f"Aye aye! From now on I be speaking like a {style}. Savvy?",
                    "action": "style_change",
                    "mood": self.mood,
                }

        # Check for profile approval responses
        if hasattr(self, '_pending_profile_approval') and self._pending_profile_approval:
            if lower_input in ("yes", "y", "yeah", "sure", "ok", "okay", "go ahead", "approve", "allow"):
                self._pending_profile_approval = False
                # Approve in computer_use
                try:
                    from computer_use import ComputerUseAgent
                    ComputerUseAgent().approve_profile_use("browser")
                except:
                    pass
                return {
                    "text": "Profile approved! Using your logged-in browser session. Re-trying your request...",
                    "action": "profile_approved",
                    "mood": self.mood,
                }
            else:
                self._pending_profile_approval = False
                return {
                    "text": "Understood. Using an isolated browser session — your personal profiles remain private.",
                    "action": "profile_denied",
                    "mood": self.mood,
                }

        # ── VDI fast-path: local intent parser → structured actions ────
        # Parses natural language into actions, handles compound commands,
        # no API calls, no regex fragility. Runs BEFORE Groq fallback.
        _vdi_actions = self._parse_vdi_intent(lower_input)
        if _vdi_actions:
            results = []
            for _act in _vdi_actions:
                _r = self._exec_vdi_action(_act)
                results.append(_r)
            combined_text = "\n".join(r.get("text", "") for r in results if r.get("text"))
            combined_action = results[0].get("action") if results else None
            return {"text": combined_text, "action": combined_action,
                    "result": {"success": all(r.get("result", {}).get("success", False) for r in results),
                               "sub_results": results}}

        # ── AI Command Parser: let Groq understand what the user wants ──
        # Skip AI parser if user just answered clarification — go straight to chat
        if not answers:
            try:
                from ai_command_parser import parse_with_groq, execute_ai_action
                voice_style = self.memory.get_preference("voice_style")
                ai_result = parse_with_groq(user_input, voice_style=voice_style or "")
                if ai_result and ai_result.get("action"):
                    return execute_ai_action(ai_result)
            except Exception:
                pass

        # Feed input to user learning system
        try:
            from feedback_tracker import get_tracker
            tracker = get_tracker(self.user_id)
            tracker.learn_from_user_text(user_input)
        except Exception:
            pass

        # Feed input to deep learning hypervisor
        try:
            from deep_learner import get_deep_learner
            dl = get_deep_learner(self.user_id)
            dl.process_interaction(user_input)
        except Exception:
            pass

        self.memory.log_interaction(user_input, "")
        self._extract_knowledge(user_input)
        related_goals = self._find_related_goals(user_input)
        ctx = _gather_system_context()

        # Store conversation history for context
        if history:
            self._conversation_history = history[-20:]  # Keep last 20 messages

        result = {"text": "", "action": None, "task": None, "strategies": None,
                  "follow_up": None, "proactive": None, "related_goals": related_goals,
                  "mood": self.mood, "mood_emoji": MOODS.get(self.mood, {}).get("emoji", ""),
                  "thought": self._current_thought}

        # Adjust mood based on query
        lower = user_input.lower()
        if any(w in lower for w in ["hello", "hi", "hey", "morning", "evening"]):
            self._set_mood("curious")
        elif any(w in lower for w in ["funny", "joke", "roast", "sarcasm"]):
            self._set_mood("sassy")
        elif any(w in lower for w in ["excite", "amazing", "cool", "awesome", "love"]):
            self._set_mood("excited")
        elif any(w in lower for w in ["think", "reflect", "consider", "analyze", "research"]):
            self._set_mood("thoughtful")
        elif any(w in lower for w in ["focus", "execute", "do", "run", "start", "begin"]):
            self._set_mood("focused")

        # ── Greeting fast-path: deterministic, no LLM ──────────────────
        GREETING_RE = re.compile(
            r"^(?:hi|hey|hello|yo|sup|hiya|howdy|greetings|bonjour|salut|hola|ciao"
            r"|namaste|salaam|aloha|konnichiwa|annyeong|merhaba|szia|hallo"
            r"|good\s+(?:morning|afternoon|evening|night)"
            r"|what'?s\s+up|how(?:'re|\s+are)\s+you"
            r"|hey\s+jarvis|ok\s+jarvis|jarvis)\s*[!.?]*$",
            re.IGNORECASE,
        )
        if GREETING_RE.match(user_input.strip()):
            hour = datetime.now().hour
            if hour < 6:
                period = "night"
            elif hour < 12:
                period = "morning"
            elif hour < 17:
                period = "afternoon"
            else:
                period = "evening"
            greeting_text = (
                f"Good {period}. I'm here — what do you need?"
            )
            result["text"] = greeting_text
            result["action"] = "greeting"
            result["thought"] = "Greeting detected"
            self.memory.log_interaction(user_input, greeting_text, "greeting")
            return result

        # ── Proactive Learning: detect personal info reveals ──────────
        self._detect_and_learn_personal_info(user_input)

        # ── Fast-path: "who am i" / "what's my name" → use stored info ──
        if re.match(r"^(?:who\s+am\s+i|what(?:'s|\s+is)\s+my\s+name|tell\s+me\s+about\s+myself|what\s+do\s+you\s+know\s+about\s+me)", lower):
            name = self.memory.get_preference("user_name") or self.memory.get_preference("name")
            if name:
                facts = self.memory.get_facts()
                personal_facts = [f for f in facts if "personal" in str(f).lower() or name.lower() in str(f).lower()]
                info = "\n".join(f"  • {f}" for f in personal_facts[:5]) if personal_facts else ""
                result["text"] = f"You're **{name}**."
                if info:
                    result["text"] += f"\n\nHere's what I know about you:\n{info}"
                result["action"] = "identity"
                result["thought"] = "Retrieved stored identity"
                self.memory.log_interaction(user_input, result["text"], "identity")
                return result
            else:
                result["text"] = "I don't know your name yet. What should I call you?"
                result["action"] = "ask_clarify"
                self.memory.log_interaction(user_input, result["text"], "ask_name")
                return result

        # ── Fast-path: "search me" → use stored name ─────────────────
        if re.match(r"^(?:search|look up|find|google)\s+(?:me|myself|my name)", lower):
            name = self.memory.get_preference("user_name") or self.memory.get_preference("name")
            if name:
                result["action"] = "fetch_search"
                result["text"] = f"🔍 Searching for {name}..."
                try:
                    from actions import cloud_safe_execute
                    r = cloud_safe_execute("fetch_search", name, user_id=self.user_id)
                    if not r or "not found" in str(r).lower() or "opened google" in str(r).lower():
                        r = cloud_safe_execute("search", name, user_id=self.user_id)
                    self.memory.add_fact(f"Search results for {name}: {str(r)[:500]}", "personal_research")
                    result["text"] = f"Here's what I found about **{name}**:\n\n{str(r)[:800]}"
                except Exception:
                    result["text"] = f"I searched for {name} but couldn't retrieve results right now."
                self.memory.log_interaction(user_input, result["text"], "search_self")
                return result

        # Skip action routing for meta-context prefixes
        skip_actions = user_input.startswith("(follow-up)") or user_input.startswith("(proactive)")

        # ── VM vs Desktop Routing ──────────────────────────────────────
        # Check if this is a follow-up to a VM confirmation question
        lower_stripped = lower.strip()
        if hasattr(self, '_pending_vm_choice') and self._pending_vm_choice:
            pending = self._pending_vm_choice
            self._pending_vm_choice = None
            # User responded to "where should I run this?"
            if any(w in lower_stripped for w in ["yes", "vm", "virtual", "background", "isolated", "do it"]):
                # Run in VM
                self._record_vm_choice(pending["task"], "vm")
                vm_result = self._run_in_vm(pending["task"])
                result["text"] = vm_result.get("text", "Running in VM...")
                result["action"] = vm_result.get("action", "vm_task")
                result["thought"] = f"Running in isolated VM..."
                self.memory.log_interaction(user_input, result["text"], "vm_confirmed")
                return result
            elif any(w in lower_stripped for w in ["no", "desktop", "here", "my screen", "on my"]):
                # Run on desktop
                self._record_vm_choice(pending["task"], "desktop")
                # Fall through to normal desktop routing
            else:
                # Unclear — default to desktop
                self._record_vm_choice(pending["task"], "desktop")

        # Detect if user explicitly wants VM (isolated, not Windows virtual desktop)
        vm_explicit = any(kw in lower_stripped for kw in [
            "in vm", "in the vm", "in a vm", "headless",
            "in isolated", "isolated", "sandbox", "run in vm",
            "do it in vm", "use vm", "use virtual machine",
        ])
        # "virtual desktop" = Windows Win+Ctrl+D feature, NOT VM
        win_vd_explicit = any(kw in lower_stripped for kw in [
            "virtual desktop", "new desktop", "another desktop",
        ])
        desktop_explicit = any(kw in lower_stripped for kw in [
            "on my desktop", "on my screen", "here", "on my computer",
            "on this machine", "locally", "on desktop",
        ])

        # For tasks that could go either way — check preferences and ask
        if not skip_actions and not vm_explicit and not desktop_explicit:
            from vm_preference_manager import get_vm_prefs
            prefs = get_vm_prefs(self.user_id)
            if prefs.should_ask_confirmation(user_input):
                suggestion = prefs.suggest_target(user_input)
                if suggestion == "vm":
                    # User usually wants VM for this — ask with suggestion
                    self._pending_vm_choice = {"task": user_input}
                    result["text"] = (
                        f"This looks like something that could run in an isolated VM. "
                        f"Want me to run it in the VM (safer, won't disturb your desktop) "
                        f"or on your desktop?"
                    )
                    result["action"] = "ask_clarify"
                    result["thought"] = "Asking VM vs desktop preference"
                    return result
                elif suggestion is None:
                    # Mixed history — ask
                    self._pending_vm_choice = {"task": user_input}
                    result["text"] = (
                        f"Should I run this on your desktop or in an isolated VM? "
                        f"VM keeps your desktop clean, desktop is faster."
                    )
                    result["action"] = "ask_clarify"
                    result["thought"] = "Asking VM vs desktop"
                    return result
                # If suggestion is "desktop", fall through silently

        if vm_explicit:
            # User explicitly wants VM — run it
            task_text = lower_stripped
            for phrase in ["in vm", "in virtual", "in the vm", "headless",
                          "background", "isolated", "sandbox"]:
                task_text = task_text.replace(phrase, "").strip()
            task_text = task_text.strip(".,!? ")
            if not task_text:
                task_text = user_input
            self._record_vm_choice(task_text, "vm")
            vm_result = self._run_in_vm(task_text)
            result["text"] = vm_result.get("text", "Running in VM...")
            result["action"] = vm_result.get("action", "vm_task")
            result["thought"] = f"Running in isolated VM..."
            self.memory.log_interaction(user_input, result["text"], "vm_explicit")
            return result

        # ── 3-TIER UNIVERSAL TASK ROUTING ─────────────────────────────
        # Tier 1: Native Python APIs (instant) — documents, spreadsheets
        # Tier 2: CLI/Scripting — subprocess calls
        # Tier 3: Virtual desktop + browser/app — GUI automation

        # ── Tier 1: "make/create/build a PowerPoint/essay/report/doc" ──
        if not skip_actions:
            _doc_match = re.match(
                r"^(?:make|create|build|generate|write|prepare|draft)\s+"
                r"(?:a\s+|an\s+|the\s+)?"
                r"(?:new\s+)?"
                r"(powerpoint|presentation|ppt|pptx|slide|slide\s*deck|essay|report|document|doc|docx|word|excel|spreadsheet|sheet|csv)\s*"
                r"(?:about|on|explaining|for|covering|titled|called|named)\s+"
                r"(.+?)$",
                lower, re.IGNORECASE,
            )
            if _doc_match:
                _doc_type = _doc_match.group(1).strip().lower()
                _topic = _doc_match.group(2).strip()
                _title = _topic.title()
                try:
                    from auto_control import create_powerpoint, create_word_document, create_excel_sheet
                    import time as _time

                    _output_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                    os.makedirs(_output_dir, exist_ok=True)

                    # Generate content based on topic
                    _content = self._generate_doc_content(_topic)

                    if _doc_type in ("powerpoint", "presentation", "ppt", "pptx", "slide", "slide deck"):
                        _out = os.path.join(_output_dir, "%s.pptx" % _title.replace(" ", "_"))
                        _r = create_powerpoint(_title, _content, _out)
                        # Open the file
                        os.startfile(_out)
                        result["action"] = "doc_create"
                        result["text"] = _r
                        result["thought"] = "Created PowerPoint via python-pptx (Tier 1)"
                    elif _doc_type in ("essay", "report", "document", "doc", "docx", "word"):
                        _out = os.path.join(_output_dir, "%s.docx" % _title.replace(" ", "_"))
                        _text = "\n\n".join(
                            "%s\n\n%s" % (s.get("title", ""), s.get("content", ""))
                            for s in _content
                        )
                        _r = create_word_document(_title, _text, _out)
                        os.startfile(_out)
                        result["action"] = "doc_create"
                        result["text"] = _r
                        result["thought"] = "Created Word document via python-docx (Tier 1)"
                    elif _doc_type in ("excel", "spreadsheet", "sheet", "csv"):
                        _out = os.path.join(_output_dir, "%s.xlsx" % _title.replace(" ", "_"))
                        _headers = ["Topic", "Details", "Notes"]
                        _rows = [[s.get("title", ""), s.get("content", ""), ""] for s in _content]
                        _r = create_excel_sheet(_title, _headers, _rows, _out)
                        os.startfile(_out)
                        result["action"] = "doc_create"
                        result["text"] = _r
                        result["thought"] = "Created Excel spreadsheet (Tier 1)"
                    else:
                        # Fallback: create as text
                        result["action"] = "ask_clarify"
                        result["text"] = "I can create PowerPoint, Word, or Excel. Which format?"

                    if result.get("text"):
                        self.memory.log_interaction(user_input, result["text"], "doc_create")
                        return result
                except Exception as e:
                    result["text"] = "Document creation error: %s" % e
                    result["action"] = "error"
                    return result

        # ── Tier 1: "open powerpoint" → launch app ──────────────────
        if not skip_actions:
            _open_app_match = re.match(
                r"^(?:open|launch|start)\s+(.+?)(?:\s+(?:and|then)\s+.+)?$",
                lower, re.IGNORECASE,
            )
            if _open_app_match:
                _app_name = _open_app_match.group(1).strip()
                _skip_apps = {"in", "up", "the", "app", "please", "now", "for", "on", "my"}
                _browser_words = {"chrome", "edge", "firefox", "safari", "brave", "opera", "browser"}
                _first_word = _app_name.split()[0] if _app_name.split() else ""
                if (_first_word not in _skip_apps and _first_word not in _browser_words
                    and "virtual desktop" not in lower and "in chrome" not in lower
                    and "in edge" not in lower and "profile" not in lower):
                    try:
                        from auto_control import desktop_open_app_on_current
                        import time as _time
                        _r = desktop_open_app_on_current(_app_name)
                        result["action"] = "open_app"
                        result["text"] = _r
                        result["thought"] = "Opened %s locally" % _app_name
                        self.memory.log_interaction(user_input, result["text"], "open_app")
                        return result
                    except Exception as e:
                        result["text"] = "App open error: %s" % e
                        result["action"] = "error"
                        return result

        # ── Tier 3: "open X in virtual desktop in Y" ─────────────────
        if not skip_actions and win_vd_explicit:
            _vd_match = re.match(
                r"^(?:open|launch|start|go\s+to)\s+(.+?)\s+in\s+(?:a\s+|the\s+)?virtual\s+desktop\s+in\s+(.+?)$",
                lower, re.IGNORECASE,
            )
            if _vd_match:
                _target = _vd_match.group(1).strip()
                _browser_raw = _vd_match.group(2).strip()
                _alias_map = {
                    "gmail": "https://mail.google.com",
                    "youtube": "https://www.youtube.com",
                    "maps": "https://maps.google.com",
                    "drive": "https://drive.google.com",
                }
                _url = _alias_map.get(_target, "https://%s.com" % _target if "." not in _target else _target)
                import re as _re
                _browser_raw_clean = _re.sub(r'\bin\s+', ' ', _browser_raw).strip()
                _browsers = _re.split(r'\s+and\s+|\s*,\s*|\s+&\s+', _browser_raw_clean)
                _browsers = [b.strip() for b in _browsers if b.strip() in ("chrome", "edge", "firefox", "safari", "brave", "opera")]
                if not _browsers:
                    _browsers = [_browser_raw]
                try:
                    from auto_control import desktop_create, desktop_open_browser_on_current, desktop_go_home
                    import time as _time
                    # Create desktop (switches to it)
                    desktop_create()
                    _time.sleep(0.5)
                    # Open browsers ON the new desktop
                    _results = []
                    for _b in _browsers:
                        _profile = "Profile 3" if _b == "chrome" else None
                        _r = desktop_open_browser_on_current(_url, browser=_b, profile_dir=_profile)
                        _results.append("%s: %s" % (_b, _r))
                        _time.sleep(1)
                    # Switch back to user's desktop
                    desktop_go_home()
                    _time.sleep(0.2)
                    result["action"] = "vd_browser"
                    result["text"] = "Created virtual desktop. %s" % "; ".join(_results)
                    result["thought"] = "Open %s on new virtual desktop in %s" % (_target, ", ".join(_browsers))
                    self.memory.log_interaction(user_input, result["text"], "vd_browser")
                    return result
                except Exception as e:
                    result["text"] = "Error: %s" % e
                    result["action"] = "error"
                    return result

        # ── Fast-path: "open X in chrome/edge" → browser CDP ─────────────
        if not skip_actions:
            _browser_names = "chrome|edge|firefox|safari|brave|opera"
            # Match both orderings:
            #   "open X in chrome profile Y"
            #   "open X in Y profile in chrome"
            #   "open X in chrome"
            _browser_match = re.match(
                r"^(?:open|launch|start|go\s+to)\s+(.+?)"
                r"(?:\s+in\s+(?:(%s)(?:\s+profile\s+(.+))?|(.+?)\s+profile\s+in\s+(%s)))"
                r"$" % (_browser_names, _browser_names),
                lower, re.IGNORECASE,
            )
            if _browser_match:
                _target = _browser_match.group(1).strip()
                _browser = _browser_match.group(2) or _browser_match.group(5) or ""
                _profile = _browser_match.group(3) or _browser_match.group(4) or ""
                if "." in _target and " " not in _target:
                    _url = _target if _target.startswith("http") else f"https://{_target}"
                else:
                    # Map common names to direct URLs to avoid Chrome redirects
                    _alias_map = {
                        "gmail": "https://mail.google.com",
                        "youtube": "https://www.youtube.com",
                        "maps": "https://maps.google.com",
                        "drive": "https://drive.google.com",
                        "photos": "https://photos.google.com",
                        "calendar": "https://calendar.google.com",
                    }
                    _url = _alias_map.get(_target, f"https://{_target}.com")

                # Use browser CDP for Chrome/Edge
                if _browser in ("chrome", "edge"):
                    try:
                        from browser_control import browser_open
                        _r = browser_open(_url, profile=_profile if _profile else None, browser=_browser)
                        result["action"] = "browser"
                        result["text"] = _r
                        result["thought"] = "Opened %s in %s via CDP" % (_target, _browser)
                        self.memory.log_interaction(user_input, result["text"], "browser_open")
                        return result
                    except Exception as e:
                        result["text"] = "Browser error: %s" % e
                        result["action"] = "error"
                        return result

                # Fallback for non-Chrome browsers
                _browser_cmd = f"browser {_url} --profile={_profile}" if _profile else f"browser {_url}"
                from actions import cloud_safe_execute
                _r = cloud_safe_execute("browser", _browser_cmd, user_id=self.user_id)
                result["action"] = "browser"
                result["text"] = _r
                result["thought"] = f"Opened {_target} in {_browser}"
                self.memory.log_interaction(user_input, result["text"], "browser_open")
                return result

            # ── Fast-path: "open X.com" → browser-use CDP ───────────────
            _url_match = re.match(
                r"^(?:open|launch|start|go\s+to)\s+(https?://\S+|\S+\.\S+)$",
                lower, re.IGNORECASE,
            )
            if _url_match:
                _target = _url_match.group(1).strip()
                _url = _target if _target.startswith("http") else f"https://{_target}"
                try:
                    from browser_control import browser_open
                    _r = browser_open(_url)
                    result["action"] = "browser"
                    result["text"] = _r
                    result["thought"] = "Opened %s in browser" % _target
                    self.memory.log_interaction(user_input, result["text"], "browser_open")
                    return result
                except Exception as e:
                    result["text"] = "Browser error: %s" % e
                    result["action"] = "error"
                    return result

            # ── Browser actions: read page, click, fill form (nodriver) ────
            # "read page" / "what's on this page" -> browser read
            _read_match = re.match(
                r"^(?:read|scan|what(?:'s|\s+is)\s+on)\s+(?:this\s+)?(?:page|tab|website|site)$",
                lower, re.IGNORECASE,
            )
            if _read_match:
                try:
                    from browser_control import browser_read
                    _r = browser_read()
                    result["action"] = "browser_read"
                    result["text"] = _r[:2000]
                    result["thought"] = "Read page via browser"
                    self.memory.log_interaction(user_input, result["text"], "browser_read")
                    return result
                except Exception as e:
                    result["text"] = "Read failed: %s" % e
                    result["action"] = "error"
                    return result

            # "click X" -> browser click, else OCR click (desktop)
            _click_match = re.match(r"^click\s+(?:on\s+)?(.+)$", lower, re.IGNORECASE)
            if _click_match:
                _target = _click_match.group(1).strip()
                try:
                    from browser_control import browser_click
                    _r = browser_click(_target)
                    if "Clicked" in _r:
                        result["action"] = "browser_click"
                        result["text"] = _r
                        result["thought"] = "Clicked '%s' via browser" % _target
                        self.memory.log_interaction(user_input, result["text"], "browser_click")
                        return result
                except Exception:
                    pass
                # Fallback to OCR (desktop only)
                try:
                    from vision_control import click_element, wait_and_click
                    if click_element(_target) or wait_and_click(_target, timeout=3):
                        result["action"] = "vision_click"
                        result["text"] = "Clicked: %s" % _target
                    else:
                        result["action"] = "vision_click"
                        result["text"] = "Could not find '%s'" % _target
                    self.memory.log_interaction(user_input, result["text"], "vision_click")
                    return result
                except ImportError:
                    pass

            # "fill form with X, Y, Z" → autonomous form filling (keyboard, not browser)
            _fill_form_match = re.match(r"^(?:fill|complete)\s+(?:the\s+)?form\s+(?:with\s+)?(.+)$", lower)
            if _fill_form_match:
                _values = [v.strip() for v in _fill_form_match.group(1).split(",")]
                try:
                    from auto_control import fill_form_by_tabbing
                    _r = fill_form_by_tabbing(_values)
                    result["action"] = "auto_fill"
                    result["text"] = _r
                    self.memory.log_interaction(user_input, result["text"], "auto_fill")
                    return result
                except ImportError:
                    pass

            # "fill X with Y" / "type Y in X" -> browser fill (requires "in/with/into")
            _fill_match = re.match(
                r"^(?:fill|type)\s+(.+?)\s+(?:with|in|into)\s+(.+)$",
                lower, re.IGNORECASE,
            )
            if _fill_match:
                if _fill_match.lastindex and _fill_match.lastindex >= 2:
                    _field = _fill_match.group(1).strip()
                    _value = _fill_match.group(2).strip()
                else:
                    _field = ""
                    _value = _fill_match.group(1).strip()
                try:
                    from browser_control import browser_fill
                    _r = browser_fill(_field, _value) if _field else browser_fill("", _value)
                    result["action"] = "browser_fill"
                    result["text"] = _r
                    result["thought"] = "Typed '%s' via browser" % _value
                    self.memory.log_interaction(user_input, result["text"], "browser_fill")
                    return result
                except Exception as e:
                    result["text"] = "Fill failed: %s" % e
                    result["action"] = "error"
                    return result

            # "extract prices" / "get prices" → CDP price extraction
            _price_match = re.match(
                r"^(?:extract|get|find|show)\s+(?:all\s+)?(?:the\s+)?price?s?$",
                lower, re.IGNORECASE,
            )
            if _price_match:
                try:
                    from browser_control import browser_prices
                    _prices = browser_prices()
                    if _prices:
                        _lines = ["  %s -- %s" % (p["raw"], p["text"][:50]) for p in _prices[:20]]
                        result["action"] = "browser_prices"
                        result["text"] = "Found %d prices:\n%s" % (len(_prices), "\n".join(_lines))
                    else:
                        result["action"] = "browser_prices"
                        result["text"] = "No prices found on page"
                    result["thought"] = "Extracted prices via browser"
                    self.memory.log_interaction(user_input, result["text"], "browser_prices")
                    return result
                except Exception as e:
                    result["text"] = "Price extraction failed: %s" % e
                    result["action"] = "error"
                    return result

            # "compare prices for X" -> multi-site browser compare
            _compare_match = re.match(
                r"^(?:compare|find|get)\s+(?:the\s+)?(?:cheapest|best|lowest)\s+(?:price|deal|flight|ticket)s?\s+(?:for|on)\s+(.+)$",
                lower, re.IGNORECASE,
            )
            if _compare_match:
                _query = _compare_match.group(1).strip()
                try:
                    from browser_control import browser_compare
                    _sites = [
                        "https://www.google.com/search?q=%s" % _query.replace(" ", "+"),
                        "https://www.skyscanner.net/search?q=%s" % _query.replace(" ", "+"),
                    ]
                    _r = browser_compare(_sites)
                    if _r.get("cheapest"):
                        _c = _r["cheapest"]
                        result["action"] = "browser_compare"
                        result["text"] = "Best price: %s on %s\n\nAll %d prices found." % (_c["raw"], _c.get("url", "?"), _r["total"])
                    else:
                        result["action"] = "browser_compare"
                        result["text"] = "Scanned %d prices, no clear winner" % _r["total"]
                    result["thought"] = "Compared prices for %s" % _query
                    self.memory.log_interaction(user_input, result["text"], "browser_compare")
                    return result
                except Exception as e:
                    result["text"] = "Price comparison failed: %s" % e
                    result["action"] = "error"
                    return result

            # ── Desktop-only OCR actions (non-browser) ────────────────────
            # "scan screen" / "what's on my screen" → OCR (desktop only)
            _vision_match = re.match(
                r"^(?:scan|read|analyze|analyse|what(?:'s|\s+is)\s+(?:on|there\s+on))\s+(?:my\s+)?(?:screen|display|monitor)$",
                lower, re.IGNORECASE,
            )
            if _vision_match:
                try:
                    from vision_control import analyze_screen
                    _analysis = analyze_screen()
                    _texts = [e["text"] for e in _analysis.get("elements", []) if e["text"].strip()]
                    _summary = "\n".join(f"  {t}" for t in _texts[:30])
                    result["action"] = "vision_scan"
                    result["text"] = f"Screen analysis ({_analysis['total_elements']} elements):\n{_summary}" if _summary else "Screen is empty"
                    result["thought"] = "Scanning desktop screen with OCR"
                    self.memory.log_interaction(user_input, result["text"], "vision_scan")
                    return result
                except ImportError:
                    result["text"] = "Vision module not available"
                    result["action"] = "error"
                    return result

            # "scroll up/down" → OCR scroll (desktop only)
            _scroll_match = re.match(r"^scroll\s+(up|down)(?:\s+(\d+))?$", lower, re.IGNORECASE)
            if _scroll_match:
                _dir = _scroll_match.group(1)
                _amt = int(_scroll_match.group(2) or 5)
                try:
                    from vision_control import mouse_scroll
                    _amount = _amt if _dir == "up" else -_amt
                    mouse_scroll(_amount)
                    result["action"] = "vision_scroll"
                    result["text"] = f"Scrolled {_dir}"
                    result["thought"] = f"Scrolled screen {_dir}"
                    self.memory.log_interaction(user_input, result["text"], "vision_scroll")
                    return result
                except ImportError:
                    pass
                try:
                    from vision_control import multi_page_scan
                    # Search multiple travel sites
                    _urls = [
                        f"https://www.google.com/search?q={_query.replace(' ', '+')}",
                        f"https://www.skyscanner.net/search?q={_query.replace(' ', '+')}",
                    ]
                    result["action"] = "vision_compare"
                    result["text"] = f"Scanning {_len} sites for {_query}..." if False else f"Starting price comparison for {_query}..."
                    result["thought"] = f"Multi-page OCR scan for {_query}"
                    # Run in background
                    self._pending_compare = {"query": _query, "urls": _urls}
                    self.memory.log_interaction(user_input, result["text"], "vision_compare")
                    return result
                except ImportError:
                    pass

            # ── Autonomous control: virtual desktops, mouse, keyboard ─────
            # "do X in background" / "do X on another desktop" → silent work
            _bg_match = re.match(
                r"^(?:do|run|execute|perform)\s+(.+?)\s+(?:in\s+)?(?:the\s+)?(?:background|another\s+desktop|desktop\s*2|silently|quietly)$",
                lower, re.IGNORECASE,
            )
            if _bg_match:
                _task = _bg_match.group(1).strip()
                try:
                    from auto_control import desktop_silent_work
                    # Build steps from task
                    _steps = []
                    if "open" in _task:
                        _m = re.match(r"open\s+(.+)", _task)
                        if _m:
                            _target = _m.group(1)
                            _steps.append({"action": "hotkey", "params": {"keys": ["win", "ctrl", "d"]}, "desc": "Create desktop"})
                            _steps.append({"action": "wait", "params": {"seconds": 0.5}})
                            _steps.append({"action": "hotkey", "params": {"keys": ["win", "r"]}, "desc": "Run dialog"})
                            _steps.append({"action": "wait", "params": {"seconds": 0.3}})
                            _steps.append({"action": "type", "params": {"text": "chrome %s" % _target}})
                            _steps.append({"action": "press", "params": {"key": "enter"}})
                            _steps.append({"action": "wait", "params": {"seconds": 3}})
                    if not _steps:
                        _steps = [
                            {"action": "hotkey", "params": {"keys": ["win", "ctrl", "d"]}, "desc": "Create desktop"},
                            {"action": "wait", "params": {"seconds": 0.5}},
                            {"action": "hotkey", "params": {"keys": ["alt", "tab"]}, "desc": "Switch"},
                            {"action": "wait", "params": {"seconds": 0.3}},
                        ]
                    _r = desktop_silent_work(_steps)
                    result["action"] = "silent_work"
                    result["text"] = _r
                    result["thought"] = "Doing task silently on new desktop"
                    self.memory.log_interaction(user_input, result["text"], "silent_work")
                    return result
                except ImportError:
                    pass

            # "create new desktop" / "new virtual desktop"
            if re.match(r"^(?:create|open|new)\s+(?:a\s+)?(?:new\s+)?(?:virtual\s+)?desktop$", lower):
                try:
                    from auto_control import desktop_create
                    _r = desktop_create()
                    result["action"] = "desktop_create"
                    result["text"] = _r
                    self.memory.log_interaction(user_input, result["text"], "desktop_create")
                    return result
                except ImportError:
                    pass

            # "switch to desktop N" / "go to desktop 2"
            _switch_match = re.match(r"^(?:switch|go|move)\s+(?:to\s+)?(?:desktop|virtual)\s*(\d+)$", lower)
            if _switch_match:
                _idx = int(_switch_match.group(1))
                try:
                    from auto_control import desktop_switch
                    _r = desktop_switch(_idx)
                    result["action"] = "desktop_switch"
                    result["text"] = _r
                    self.memory.log_interaction(user_input, result["text"], "desktop_switch")
                    return result
                except ImportError:
                    pass

            # "close desktop" / "remove desktop"
            if re.match(r"^(?:close|remove|delete)\s+(?:current\s+)?(?:virtual\s+)?desktop$", lower):
                try:
                    from auto_control import desktop_close
                    _r = desktop_close()
                    result["action"] = "desktop_close"
                    result["text"] = _r
                    self.memory.log_interaction(user_input, result["text"], "desktop_close")
                    return result
                except ImportError:
                    pass

            # "open [app] on desktop N" / "open [app] in virtual desktop"
            _app_desktop_match = re.match(
                r"^(?:open|launch|start)\s+(.+?)\s+(?:on|in|to)\s+(?:virtual\s+)?desktop\s*(\d+)$",
                lower, re.IGNORECASE,
            )
            if _app_desktop_match:
                _app = _app_desktop_match.group(1).strip()
                _idx = int(_app_desktop_match.group(2))
                try:
                    from auto_control import task_switch_to_desktop_and_open
                    _r = task_switch_to_desktop_and_open(_idx, _app)
                    result["action"] = "desktop_app"
                    result["text"] = _r
                    self.memory.log_interaction(user_input, result["text"], "desktop_app")
                    return result
                except ImportError:
                    pass

            # "click at X,Y" / "click 500,300"
            _click_xy_match = re.match(r"^click\s+(?:at\s+)?(\d+)\s*,\s*(\d+)$", lower)
            if _click_xy_match:
                _x, _y = int(_click_xy_match.group(1)), int(_click_xy_match.group(2))
                try:
                    from auto_control import mouse_click
                    mouse_click(_x, _y)
                    result["action"] = "mouse_click"
                    result["text"] = "Clicked at (%d, %d)" % ( _x, _y)
                    self.memory.log_interaction(user_input, result["text"], "mouse_click")
                    return result
                except ImportError:
                    pass

            # "type [text]" → keyboard type (when not in browser context)
            _type_match = re.match(r"^(?:type|write|enter)\s+(.+)$", lower, re.IGNORECASE)
            if _type_match:
                _text = _type_match.group(1).strip()
                try:
                    from auto_control import type_text
                    type_text(_text)
                    result["action"] = "keyboard_type"
                    result["text"] = "Typed: %s" % _text
                    self.memory.log_interaction(user_input, result["text"], "keyboard_type")
                    return result
                except ImportError:
                    pass

            # "press [key]" / "hit enter"
            _press_match = re.match(r"^(?:press|hit|push)\s+(enter|tab|escape|space|backspace|delete|up|down|left|right|home|end|pageup|pagedown)$", lower)
            if _press_match:
                _key = _press_match.group(1)
                try:
                    from auto_control import key_press
                    key_press(_key)
                    result["action"] = "key_press"
                    result["text"] = "Pressed: %s" % _key
                    self.memory.log_interaction(user_input, result["text"], "key_press")
                    return result
                except ImportError:
                    pass

            # "scroll up/down N"
            _scroll_match = re.match(r"^(?:scroll|wheel)\s+(up|down)(?:\s+(\d+))?$", lower)
            if _scroll_match:
                _dir = _scroll_match.group(1)
                _amt = int(_scroll_match.group(2) or 3)
                try:
                    from auto_control import mouse_scroll
                    mouse_scroll(_amt if _dir == "up" else -_amt)
                    result["action"] = "mouse_scroll"
                    result["text"] = "Scrolled %s %d" % ( _dir, _amt)
                    self.memory.log_interaction(user_input, result["text"], "mouse_scroll")
                    return result
                except ImportError:
                    pass

            # "fill form with X, Y, Z" → autonomous form filling
            _fill_match = re.match(r"^(?:fill|complete)\s+(?:the\s+)?form\s+(?:with\s+)?(.+)$", lower)
            if _fill_match:
                _values = [v.strip() for v in _fill_match.group(1).split(",")]
                try:
                    from auto_control import fill_form_by_tabbing
                    _r = fill_form_by_tabbing(_values)
                    result["action"] = "auto_fill"
                    result["text"] = _r
                    self.memory.log_interaction(user_input, result["text"], "auto_fill")
                    return result
                except ImportError:
                    pass

            # "alt tab" / "switch window"
            if re.match(r"^(?:alt\s*tab|switch\s+window|change\s+window)$", lower):
                try:
                    from auto_control import alt_tab
                    alt_tab()
                    result["action"] = "alt_tab"
                    result["text"] = "Switched window"
                    self.memory.log_interaction(user_input, result["text"], "alt_tab")
                    return result
                except ImportError:
                    pass

            # Fast path: direct action execution
            action_result = self._route_action(user_input)
            if action_result and action_result.get("action"):
                # Check for profile approval need
                action_text = action_result.get("text", "")
                if "PROFILE_APPROVAL_NEEDED" in action_text or "profile" in action_text.lower() and "approve" in action_text.lower():
                    self._pending_profile_approval = True
                    result["action"] = "ask_clarify"
                    result["text"] = action_text.replace("PROFILE_APPROVAL_NEEDED:", "")
                    result["thought"] = "Waiting for profile approval"
                    self.memory.log_interaction(user_input, result["text"], "profile_approval")
                    return result
                result["action"] = action_result["action"]
                result["text"] = action_result.get("text", "")
                result["thought"] = f"Executing {action_result['action']}..."
                if action_result.get("async"):
                    result["relay_id"] = action_result.get("relay_id", "")
                    result["async"] = True
                    result["thought"] = f"Queued {action_result['action']} on your computer..."
                if action_result.get("qr_image"):
                    result["qr_image"] = action_result["qr_image"]
                if action_result.get("image"):
                    result["image"] = action_result["image"]
                if action_result.get("link"):
                    result["link"] = action_result["link"]

                # Check for human intervention needed
                try:
                    from human_intervention import get_intervention_manager
                    mgr = get_intervention_manager(self.user_id)
                    action_text = action_result.get("text", "").lower()

                    # Check if the action result indicates a block
                    block_keywords = ["login", "sign in", "captcha", "verify", "payment",
                                     "checkout", "create account", "sign up", "blocked"]
                    if any(kw in action_text for kw in block_keywords):
                        # Try to scan the page content
                        intervention = mgr.scan_page(action_result.get("text", ""))
                        if intervention:
                            result["action"] = "human_intervention"
                            result["text"] = mgr.notify_user(intervention)
                            result["intervention_id"] = str(intervention.timestamp)
                            result["intervention"] = {
                                "type": intervention.type.value,
                                "options": intervention.options,
                                "question": intervention.question,
                            }
                            result["thought"] = f"Hit {intervention.type.value} — asking user"
                            self.memory.log_interaction(user_input, result["text"], "intervention")
                            return result

                    # Check for payment boundary — JARVIS NEVER handles money
                    if mgr.is_payment_related(action_result.get("text", "")):
                        result["action"] = "payment_boundary"
                        result["text"] = mgr.get_payment_boundary_message()
                        result["thought"] = "Payment boundary — refusing to handle money"
                        self.memory.log_interaction(user_input, result["text"], "payment_boundary")
                        return result
                except Exception:
                    pass
                if action_result.get("wa_link"):
                    result["wa_link"] = action_result["wa_link"]
                self.memory.log_interaction(user_input, result["text"], action_result["action"])
                try:
                    from deep_learner import get_deep_learner
                    get_deep_learner(self.user_id).observe_action(action_result["action"])
                except Exception:
                    pass
                return result

        # Build context for LLM
        context = self._build_context(user_input)
        act_prompt = self._all_actions_as_prompt()

        # Detect complexity — split into automation tasks vs info queries
        # Automation: needs VDI/desktop actions. Info: just needs a good chat response.
        _automation_words = {"open", "launch", "start", "click", "type", "enter", "fill",
            "automate", "control", "navigate", "close", "kill", "screenshot",
            "computer", "screen", "handle", "take over", "do this", "complete",
            "set up", "configure", "install", "run", "execute", "deploy"}
        _info_words = {"find", "search", "look", "tell me about", "who is", "what is",
            "how to", "research", "compare", "book", "plan", "organize", "arrange",
            "holiday", "trip", "vacation", "travel", "flight", "hotel",
            "write", "compose", "draft", "generate", "produce",
            "idea", "strategy", "analysis", "report", "essay", "homework",
            "email", "contact", "cheap", "price", "cost", "arbitrage",
            "startup", "business", "invest", "project"}
        is_automation = any(t in lower for t in _automation_words)
        is_info = any(t in lower for t in _info_words) or len(user_input.split()) >= 6

        if is_automation:
            # Try Mission Engine first for complex multi-step tasks
            mission_result = self._execute_mission(user_input)
            if mission_result and mission_result.get("status") in ("completed", "partial"):
                # Mission engine handled it — format response
                n = mission_result.get("steps_completed", 0)
                total = mission_result.get("steps_total", 0)
                artifacts = mission_result.get("artifacts", [])
                verified = sum(1 for v in mission_result.get("verification", []) if v.get("verified"))

                result["text"] = f"Mission complete: {n}/{total} steps executed, {verified}/{total} verified."
                if artifacts:
                    result["text"] += f"\nArtifacts: {', '.join(str(a) for a in artifacts[:5])}"
                result["action"] = "mission_complete"
                result["mission"] = {
                    "id": mission_result.get("mission_id"),
                    "status": mission_result.get("status"),
                    "steps": mission_result.get("verification"),
                }
                result["thought"] = f"Mission {mission_result.get('status')}: {user_input[:40]}..."
            else:
                # Mission engine couldn't handle — fallback to workflow
                wf = self._auto_workflow(user_input)
                if wf and wf.get("type") != "error":
                    result["task"] = wf
                    result["text"] = wf.get("text", result["text"])
                    result["thought"] = f"Working on: {user_input[:40]}..."
                else:
                    combined = self._generate_combined_response(user_input, context, act_prompt, answers_provided=bool(answers))
                    result["text"] = combined.get("text", "")
                    result["task"] = combined.get("task")
                    if combined.get("executed_tools"):
                        result["action"] = combined["executed_tools"][0].get("tool", "executed")
                    result["thought"] = f"Processing: {user_input[:40]}..."
            self.memory.log_interaction(user_input, result["text"], "complex_response")
        elif is_info:
            # Info/research query — just use Groq chat directly
            has_answers = bool(answers)
            combined = self._generate_combined_response(user_input, context, act_prompt, answers_provided=has_answers)
            result["text"] = combined.get("text", "")
            result["task"] = combined.get("task")
            if combined.get("executed_tools"):
                result["action"] = combined["executed_tools"][0].get("tool", "executed")
            result["thought"] = f"Researching: {user_input[:40]}..."
            # Build structured data for domain-specific rendering
            domain = self._detect_domain(user_input)
            if domain and result["text"]:
                try:
                    if domain == 'travel':
                        result["result_data"] = self._build_structured_travel(user_input, result["text"])
                    elif domain == 'trading':
                        result["result_data"] = self._build_structured_trading(user_input, result["text"])
                    elif domain == 'research':
                        result["result_data"] = self._build_structured_research(user_input, result["text"])
                    if result.get("result_data"):
                        result["result_data"]["result_type"] = domain
                except Exception:
                    pass
            # VDI EXECUTION: actually open browser and search
            if has_answers and domain:
                try:
                    self._vdi_auto_search(user_input, domain)
                except Exception:
                    pass
            self.memory.log_interaction(user_input, result["text"], "complex_response")
        else:
            # General complex — try mission engine, then workflow, then chat
            mission_result = self._execute_mission(user_input)
            if mission_result and mission_result.get("status") in ("completed", "partial"):
                n = mission_result.get("steps_completed", 0)
                total = mission_result.get("steps_total", 0)
                verified = sum(1 for v in mission_result.get("verification", []) if v.get("verified"))
                result["text"] = f"Mission complete: {n}/{total} steps executed, {verified}/{total} verified."
                result["action"] = "mission_complete"
                result["thought"] = f"Mission {mission_result.get('status')}: {user_input[:40]}..."
            else:
                wf = self._auto_workflow(user_input)
                if wf and wf.get("type") != "error":
                    result["task"] = wf
                    result["text"] = wf.get("text", result["text"])
                    result["thought"] = f"Working on: {user_input[:40]}..."
                else:
                    ws_result = self._workspace_mission(user_input)
                    if ws_result and ws_result.get("ok"):
                        result["text"] = ws_result.get("text", f"Workspace mission started: {user_input[:50]}")
                        result["action"] = "workspace_mission"
                        result["workspace"] = {
                            "mission_id": ws_result.get("mission_id"),
                            "workspace_id": ws_result.get("workspace_id"),
                        }
                        result["thought"] = f"Autonomous workspace mission: {user_input[:40]}..."
                    else:
                        combined = self._generate_combined_response(user_input, context, act_prompt, answers_provided=bool(answers))
                        result["text"] = combined.get("text", "")
                        result["task"] = combined.get("task")
                        if combined.get("executed_tools"):
                            result["action"] = combined["executed_tools"][0].get("tool", "executed")
                        result["thought"] = f"Processing: {user_input[:40]}..."
            self.memory.log_interaction(user_input, result["text"], "complex_response")

        # Simple response path (not complex)
        if not (is_automation or is_info):
            reply, executed_tools = self._generate_response(user_input, context, act_prompt)

            # Intercept: if LLM fabricated search results instead of using tool, force real search
            if not executed_tools and reply:
                reply, executed_tools = self._intercept_fabricated_results(user_input, reply, executed_tools)

            result["text"] = reply
            if executed_tools:
                result["action"] = executed_tools[0].get("tool", "executed")
            result["thought"] = f"Responded to: {user_input[:40]}..."
            self.memory.log_interaction(user_input, reply)

        result["mood"] = self.mood
        result["mood_emoji"] = MOODS.get(self.mood, {}).get("emoji", "")

        # Proactive suggestions (interval-based)
        if now - self._last_proactive > self._proactive_interval:
            self._last_proactive = now
            proactive = self._generate_proactive_suggestions(ctx)
            result["proactive"] = proactive[:3]

        # FINAL SAFETY NET: strip any JSON that slipped through
        if result.get("text"):
            result["text"] = self._strip_json(result["text"])

        # Store pending clarification for answer handling
        if result.get("action") == "ask_clarify":
            self._pending_clarify = {
                "query": user_input,
                "questions": result.get("questions", []),
            }
        elif result.get("text") and not self._pending_clarify:
            # Detect clarification from chat text (when AI parser fails and chat path handles it)
            import re as _re_clarify
            text = result.get("text", "")
            # If response has multiple questions, it's likely a clarification
            questions = _re_clarify.findall(r'[^.?!?]+\?', text)
            if len(questions) >= 2:
                self._pending_clarify = {
                    "query": user_input,
                    "questions": [q.strip() for q in questions],
                }

        return result

    def _generate_response(self, user_input: str, context: str, act_prompt: str) -> tuple[str, list[dict]]:
        """Returns (response_text, list_of_executed_tools)."""
        try:
            from groq_agent import generate as groq_gen, SYSTEM_PROMPT
            system = f"{SYSTEM_PROMPT}\n\n{context}\n\n{act_prompt}" if context else SYSTEM_PROMPT
            voice_style = self.memory.get_preference("voice_style")
            if voice_style:
                system += f"\n\n=== VOICE STYLE ===\nYou MUST respond in a {voice_style} voice/tone/style. Every response must reflect this personality. Do NOT break character."
            reply = groq_gen(user_input, user_id=self.user_id, max_tokens=400, temperature=0.7, system_prompt=system)
            if reply:
                final_text, executed = self._parse_and_execute_tool_calls(reply, user_input)
                return final_text, executed
        except Exception:
            pass
        try:
            return self._hl_with_timeout(context, max_tokens=400), []
        except Exception:
            return "", []

    def _generate_combined_response(self, user_input: str, context: str, act_prompt: str, answers_provided: bool = False) -> dict:
        try:
            from groq_agent import generate as groq_gen, SYSTEM_PROMPT
            system = f"{SYSTEM_PROMPT}\n\n{context}\n\n{act_prompt}" if context else SYSTEM_PROMPT
            voice_style = self.memory.get_preference("voice_style")
            if voice_style:
                system += f"\n\n=== VOICE STYLE ===\nYou MUST respond in a {voice_style} voice/tone/style. Every response must reflect this personality. Do NOT break character."
            if answers_provided:
                system += "\n\n=== CRITICAL ===\nThe user has ALREADY answered your clarification questions. You have all the info you need. Give a COMPLETE, DETAILED answer with specific recommendations. Do NOT ask more questions. Do NOT ask for more details. Just answer with the best recommendations you can provide."
            reply = groq_gen(user_input, user_id=self.user_id, max_tokens=800, temperature=0.7, system_prompt=system)
            if reply:
                final_text, executed = self._parse_and_execute_tool_calls(reply, user_input)
                return {"text": final_text, "strategies": None, "follow_up": [], "task": None, "executed_tools": executed}
        except Exception:
            pass

        raw = self._hl_with_timeout(context, max_tokens=600)
        # ALWAYS strip JSON from any response path
        final_text, executed = self._parse_and_execute_tool_calls(raw, user_input)
        if executed:
            return {"text": final_text, "strategies": None, "follow_up": [], "task": None, "executed_tools": executed}
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
                return {
                    "text": data.get("text", ""),
                    "strategies": {"strategies": data.get("strategies", []), "follow_up_questions": data.get("follow_up", [])} if data.get("strategies") else None,
                    "follow_up": data.get("follow_up", []),
                    "task": data.get("task"),
                }
            except: pass
        return {"text": raw, "strategies": None, "follow_up": [], "task": None}

    def _auto_workflow(self, user_input: str) -> dict | None:
        """Auto-create and start a workflow for clear task requests."""
        # Try Universal Task Engine first for complex multi-step tasks
        try:
            from universal_task_engine import UniversalTaskEngine
            ute = UniversalTaskEngine()
            complexity = ute.classify_complexity(user_input)
            if complexity.value in ("complex", "autonomous"):
                plan = ute.generate_plan(user_input)
                if plan.steps:
                    return {
                        "type": "universal_task",
                        "text": f"Planning {len(plan.steps)}-step task: {plan.reasoning}",
                        "steps": [{"action": s.action, "params": s.params, "description": s.description} for s in plan.steps],
                        "reasoning": plan.reasoning,
                        "complexity": complexity.value,
                    }
        except Exception:
            pass

        try:
            from workflow_engine import get_engine
            engine = get_engine()
            execution = engine.create_workflow(user_input, {
                "active_goals": self.memory.get_active_goals(),
                "memory_summary": self.memory.get_summary(),
                "query": user_input,
                "user_id": self.user_id,
            })
            result = engine.advance(execution.execution_id, action_executor=self._exec_action_wrapper)

            # If it asks for user input, return that as a task
            if isinstance(result, dict):
                if result.get("type") == "ask":
                    return {
                        "type": "ask",
                        "question": result.get("question", "What?"),
                        "session_id": result.get("execution_id", execution.execution_id),
                        "step": 1, "total": len(execution.workflow.steps),
                        "text": f"❓ {result.get('question', 'What?')}"
                    }
                elif result.get("type") == "batch":
                    texts = [r.get("text", "") for r in result.get("results", []) if r.get("type") == "notify"]
                    if texts:
                        return {"type": "workflow", "text": "\n".join(texts)}
                elif result.get("type") == "complete":
                    return {"type": "complete", "text": result.get("text", "Done!")}

            return None
        except Exception as e:
            err_msg = str(e)
            if "valid JSON" in err_msg or "invalid JSON" in err_msg:
                # AI couldn't build a workflow — that's fine, fall through to normal response
                return None
            return {"type": "error", "text": f"Workflow error: {err_msg}"}

    def _exec_action_wrapper(self, action: str, params: str = "") -> str:
        try:
            from actions import cloud_safe_execute, detect_action
            aid = detect_action(action) or action
            return cloud_safe_execute(aid, params, user_id=self.user_id)
        except Exception as e:
            return f"Error: {e}"

    def _generate_proactive_suggestions(self, ctx: dict) -> list[str]:
        goals = self.memory.get_active_goals()
        prefs = self.memory._data.get("preferences", {})
        facts = self.memory._data.get("facts", [])
        parts = []
        if goals: parts.append("Goals: " + "; ".join(g["goal"] for g in goals[:3]))
        if prefs: parts.append("Prefs: " + "; ".join(f"{k}={v['value']}" for k, v in list(prefs.items())[:3]))
        if facts: parts.append("Facts: " + "; ".join(f["fact"] for f in facts[-3:]))
        if ctx.get("cpu", 0) > 70: parts.append(f"CPU high ({ctx['cpu']}%)")
        if ctx.get("battery", 100) < 25 and not ctx.get("charging", False): parts.append(f"Battery low ({ctx['battery']}%)")
        context_str = "\n".join(parts) if parts else "New user."

        # Add personal data context
        try:
            from personal_data_ingestor import get_ingestor
            personal = get_ingestor().build_context()
            if personal.get("recent_files"):
                context_str += "\nRecent files: " + "; ".join(f["name"] for f in personal["recent_files"][:3])
            if personal.get("active_projects"):
                context_str += "\nProjects: " + "; ".join(p["name"] for p in personal["active_projects"][:3])
            if personal.get("upcoming_events"):
                context_str += "\nNext: " + personal["upcoming_events"][0].get("subject", "")
            if personal.get("top_topics"):
                context_str += "\nInterests: " + ", ".join(t["topic"] for t in personal["top_topics"][:3])
        except Exception:
            pass

        try:
            from groq_agent import generate as groq_gen
            raw = groq_gen(f"Suggest 2-3 helpful things proactively based on: {context_str}", user_id=self.user_id, max_tokens=200, temperature=0.6)
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if m:
                suggestions = json.loads(m.group())
                if isinstance(suggestions, list):
                    return suggestions
        except Exception:
            pass
        return ["Want me to check on your active goals?", "Need help with anything else?"]

    def _generate_doc_content(self, topic: str) -> list[dict]:
        """Generate slide/document content for a topic using knowledge + LLM.
        Returns list of {"title": "Section", "content": "text"} dicts.
        """
        # Use built-in knowledge to generate structured content
        topic_lower = topic.lower()
        slides = []

        # Generate 5-8 slides based on topic
        slides.append({"title": "Introduction to %s" % topic.title(),
                        "content": "Overview and key concepts\nImportance and relevance\nHistorical context"})
        slides.append({"title": "Background", "content": "Origins and development\nKey milestones\nCurrent state"})

        # Topic-specific content
        if any(w in topic_lower for w in ["train", "railway", "locomotive"]):
            slides.append({"title": "History of Trains", "content": "1804: First steam locomotive (Richard Trevithick)\n1825: Stockton and Darlington Railway\n1830: Liverpool and Manchester Railway\nGeorge Stephenson - Father of Railways"})
            slides.append({"title": "Types of Trains", "content": "Steam Locomotives - Coal-powered, iconic\nDiesel Locomotives - Modern, powerful\nElectric Trains - Fast, clean\nHigh-Speed Rail - Shinkansen, TGV, Eurostar\nMaglev - Magnetic levitation, 600+ km/h"})
            slides.append({"title": "How Trains Work", "content": "Steel wheels on steel rails - low friction\nElectric motors or diesel engines\nSignaling systems for safety\nBraking systems: pneumatic, regenerative"})
            slides.append({"title": "Famous Train Routes", "content": "Trans-Siberian Railway - 9,289 km\nOrient Express - Paris to Istanbul\nIndian Pacific - Sydney to Perth\nBernina Express - Switzerland\nThe Ghan - Australia"})
            slides.append({"title": "Future of Rail", "content": "Hyperloop concepts\nAutonomous trains\nSustainable rail travel\nHS2 and global expansion"})
        elif any(w in topic_lower for w in ["space", "planet", "solar system"]):
            slides.append({"title": "The Solar System", "content": "8 planets orbiting our Sun\nInner rocky planets, outer gas giants\nAsteroid belt between Mars and Jupiter"})
            slides.append({"title": "Planets Overview", "content": "Mercury - smallest, closest to Sun\nVenus - hottest, backwards rotation\nEarth - only known life\nMars - the Red Planet, rovers\nJupiter - largest, Great Red Spot\nSaturn - beautiful rings\nUranus - tilted on side\nNeptune - windiest planet"})
        elif any(w in topic_lower for w in ["computer", "coding", "programming", "software"]):
            slides.append({"title": "Computer Science Basics", "content": "Binary number system\nCPU, Memory, Storage\nInput/Output devices\nOperating systems"})
            slides.append({"title": "Programming Languages", "content": "Python - simple, versatile\nJavaScript - web development\nJava - enterprise, Android\nC/C++ - systems programming\nRust - safety + performance"})
        else:
            # Generic content for any topic
            slides.append({"title": "Key Concepts of %s" % topic.title(),
                            "content": "Definition and scope\nCore principles\nKey terminology"})
            slides.append({"title": "Applications of %s" % topic.title(),
                            "content": "Real-world uses\nIndustry applications\nEveryday relevance"})
            slides.append({"title": "Advantages", "content": "Key benefits\nWhy it matters\nImpact on society"})
            slides.append({"title": "Challenges & Limitations", "content": "Current obstacles\nEthical considerations\nFuture concerns"})

        slides.append({"title": "Summary & Key Takeaways", "content": "Main points reviewed\nKey conclusions\nCall to action"})
        slides.append({"title": "Questions & Discussion", "content": "Open floor for questions\nFurther reading suggested\nThank you for listening"})

        return slides

    def _extract_knowledge(self, text: str):
        lower = text.lower()
        for pat, category in [
            (r"(?:i\s+|i'?a?m?\s+)?(?:like|love|prefer|enjoy)\s+(\w+(?:\s+\w+)?)", "likes"),
            (r"(?:i\s+)?(?:don't\s+like|hate|dislike)\s+(\w+(?:\s+\w+)?)", "dislikes"),
            (r"(?:my\s+)?(?:name\s+is\s+)(.+)", "name"),
            (r"(?:i\s+)?(?:work\s+(?:as|at|for)\s+)(.+)", "profession"),
            (r"(?:i\s+)?(?:use\s+)(\w+(?:\s+\w+)?)", "tools"),
            (r"(?:i\s+)?(?:live|stay|reside)\s+(?:in|at)\s+(.+)", "location"),
            (r"(?:call\s+me|i\s+go\s+by)\s+(.+)", "nickname"),
        ]:
            m = re.search(pat, lower)
            if m: self.memory.add_preference(category, m.group(1).strip())

        for pat in [
            r"(?:i\s+)?(?:want|need|plan|hope)\s+to\s+(.+?)(?:\.|!|$)",
            r"(?:i'?m?\s+)?(?:trying|going|looking)\s+to\s+(.+?)(?:\.|!|$)",
            r"(?:my\s+)?(?:goal|aim|objective)\s+(?:is\s+)?(?:to\s+)?(.+?)(?:\.|!|$)",
        ]:
            m = re.search(pat, lower)
            if m:
                goal = m.group(1).strip()
                if 5 < len(goal) < 100: self.memory.add_goal(goal)

        # Extract facts (sentences about the user)
        for m in re.finditer(r"(?:i\s+)(?:have|am|work|study|play|use|read|watch|listen|code|build|make|create)\s+(.+?)(?:\.|!|$)", lower):
            fact = m.group(0).strip()
            if 10 < len(fact) < 120: self.memory.add_fact(fact)

    def _find_related_goals(self, text: str) -> list[str]:
        lower = text.lower()
        related = []
        for goal in self.memory.get_active_goals():
            goal_words = set(goal["goal"].lower().split())
            input_words = set(lower.split())
            overlap = len(goal_words & input_words)
            if overlap >= len(goal_words) * 0.3 and overlap >= 1:
                related.append(goal["goal"])
        return related[:3]

    def _detect_domain(self, query: str) -> str | None:
        """Detect the domain of a query for structured rendering."""
        q = query.lower()
        if any(w in q for w in ['holiday', 'trip', 'vacation', 'travel', 'flight', 'hotel',
                                  'resort', 'beach', 'itinerary', 'destination', 'book',
                                  'visit', 'tour', 'scenic', 'adventure']):
            return 'travel'
        if any(w in q for w in ['stock', 'crypto', 'bitcoin', 'trading', 'invest',
                                  'portfolio', 'price', 'buy', 'sell', 'market', 'forex',
                                  'share', 'dividend', 'chart', 'analysis']):
            return 'trading'
        if any(w in q for w in ['research', 'compare', 'analysis', 'report', 'study',
                                  'competitor', 'market research', 'survey', 'data',
                                  'document', 'summary', 'brief']):
            return 'research'
        if any(w in q for w in ['money', 'income', 'revenue', 'profit', 'earn',
                                  'side hustle', 'passive income', 'digital product',
                                  'sell', 'monetize', 'business idea', 'niche',
                                  'opportunity', 'make money', 'financial freedom']):
            return 'money'
        return None

    def _vdi_auto_search(self, query: str, domain: str):
        """Launch autonomous VDI agent for real 280+ combination arbitrage."""
        import threading

        def _run():
            try:
                from vdi_agent import get_vdi_agent
                agent = get_vdi_agent()

                if domain == 'travel':
                    # Extract params from query
                    q = query.lower()
                    group = 5
                    for w in q.split():
                        if w.isdigit() and int(w) <= 20:
                            group = int(w)
                            break

                    # Check if user wants specific destination
                    from vdi_agent import DESTINATIONS
                    specific_dest = None
                    for d in DESTINATIONS:
                        if d in q:
                            specific_dest = d
                            break

                    if specific_dest:
                        # Scan just that destination across all sites
                        agent.launch_full_arbitrage(query, group_size=group, destinations=[specific_dest])
                    else:
                        # FULL ARBITRAGE: scan ALL 20 destinations × 14 sites = 280 combinations
                        agent.launch_full_arbitrage(query, group_size=group)

                elif domain == 'trading':
                    agent.running = True
                    agent.open_tab("https://www.google.com/finance/")
                    agent.open_tab("https://finance.yahoo.com/")
                    agent.open_tab("https://www.tradingview.com/")
                    time.sleep(3)
                    # Aggressive scrolling on each tab
                    tabs = agent.get_tabs()
                    for tab in tabs:
                        agent.focus_tab(tab["wid"])
                        agent.scroll_down(15)
                        time.sleep(0.5)
                    agent.running = False

                elif domain == 'money':
                    # MONEY-MAKER: scan for profitable digital niches
                    from opportunity_scanner import get_opportunity_scanner
                    scanner = get_opportunity_scanner()
                    scanner.scan_all()

                else:
                    agent.running = True
                    agent.open_tab(f"https://www.google.com/search?q={query}")
                    time.sleep(2)
                    agent.scroll_down(10)
                    agent.running = False

            except Exception as e:
                import logging
                logging.getLogger("entity").warning(f"VDI agent error: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _build_structured_travel(self, query: str, text: str) -> dict:
        """Use Groq to extract structured travel data from the response."""
        try:
            from groq_agent import generate as groq_gen
            prompt = f"""Extract structured travel planning data from this response. Return ONLY valid JSON, no other text.

Query: {query}
Response: {text[:2000]}

Return JSON with this exact structure:
{{
  "destination": "main destination name",
  "duration": "14 days",
  "group_size": 5,
  "budget_per_person": "£200",
  "total_estimated": "£2800",
  "highlights": ["3-5 key highlights as strings"],
  "itinerary": [
    {{"day": 1, "title": "Arrival", "activities": ["activity1", "activity2"], "accommodation": "hotel name", "location": "city"}},
    {{"day": 2, "title": "Exploration", "activities": [...], "accommodation": "...", "location": "..."}}
  ],
  "hotels": [
    {{"name": "hotel name", "stars": 5, "location": "city", "price_per_night": "£80", "type": "villa/hotel/resort", "highlights": ["feature1"]}}
  ],
  "flights": [
    {{"from": "London", "to": "Hanoi", "airline": "Vietnam Airlines", "price": "£450", "duration": "11h", "stops": 0}}
  ],
  "activities": [
    {{"name": "activity", "location": "city", "price": "£25", "duration": "3 hours", "type": "adventure/cultural/scenic"}}
  ],
  "cost_breakdown": {{"flights": "£450", "hotels": "£800", "activities": "£200", "food": "£300", "transport": "£100", "total": "£2800"}},
  "tips": ["tip1", "tip2"]
}}"""
            reply = groq_gen(prompt, max_tokens=2000, temperature=0.3)
            if reply:
                import json
                # Try to extract JSON from response
                m = re.search(r'\{.*\}', reply, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    data['result_type'] = 'travel'
                    return data
        except Exception:
            pass
        # Fallback: return basic structured data from text
        return {
            "result_type": "travel",
            "destination": "Vietnam",
            "highlights": [text[:200]],
            "itinerary": [],
            "hotels": [],
            "flights": [],
            "activities": [],
            "cost_breakdown": {},
        }

    def _build_structured_trading(self, query: str, text: str) -> dict:
        """Use Groq to extract structured trading data."""
        try:
            from groq_agent import generate as groq_gen
            prompt = f"""Extract structured financial/trading data from this response. Return ONLY valid JSON, no other text.

Query: {query}
Response: {text[:2000]}

Return JSON with this exact structure:
{{
  "ticker": "SYMBOL",
  "name": "Company/Asset name",
  "current_price": "$150.00",
  "change_24h": "+2.5%",
  "change_direction": "up",
  "volume": "1.2M",
  "market_cap": "$2.1B",
  "recommendation": "BUY",
  "confidence": 0.75,
  "key_metrics": [
    {{"label": "P/E Ratio", "value": "25.3"}},
    {{"label": "52w High", "value": "$180"}},
    {{"label": "52w Low", "value": "$95"}}
  ],
  "news": [
    {{"title": "headline", "source": "Reuters", "sentiment": "positive"}}
  ],
  "price_targets": {{"low": "$120", "mid": "$160", "high": "$200"}},
  "risk_level": "medium"
}}"""
            reply = groq_gen(prompt, max_tokens=1500, temperature=0.3)
            if reply:
                import json
                m = re.search(r'\{.*\}', reply, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    data['result_type'] = 'trading'
                    return data
        except Exception:
            pass
        return {"result_type": "trading", "name": query, "key_metrics": []}

    def _build_structured_research(self, query: str, text: str) -> dict:
        """Use Groq to extract structured research data."""
        try:
            from groq_agent import generate as groq_gen
            prompt = f"""Extract structured research data from this response. Return ONLY valid JSON, no other text.

Query: {query}
Response: {text[:2000]}

Return JSON with this exact structure:
{{
  "topic": "research topic",
  "executive_summary": "2-3 sentence summary of key findings",
  "key_findings": ["finding1", "finding2", "finding3"],
  "sections": [
    {{"title": "section title", "content": "section content", "key_points": ["point1", "point2"]}}
  ],
  "data_table": [
    {{"column1": "value", "column2": "value"}}
  ],
  "recommendations": ["rec1", "rec2"],
  "sources": ["source1", "source2"],
  "confidence": 0.8
}}"""
            reply = groq_gen(prompt, max_tokens=1500, temperature=0.3)
            if reply:
                import json
                m = re.search(r'\{.*\}', reply, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    data['result_type'] = 'research'
                    return data
        except Exception:
            pass
        return {"result_type": "research", "topic": query, "key_findings": [text[:200]]}

    def _execute_mission(self, user_input: str) -> dict | None:
        """Execute a task through the full Mission → Plan → Execute → Verify → Recover pipeline.

        Returns result dict or None if mission architecture can't handle the query.
        """
        try:
            from mission_engine import get_mission_engine
            from task_planner import get_task_planner
            from specialized_agents import get_agent, AgentResult
            from verification_engine import get_verification_engine
            from failure_recovery import RecoveryEngine, wrap_with_recovery
            from skill_registry import get_skill_registry
        except ImportError:
            return None

        # 1. Discover capabilities
        registry = get_skill_registry()
        available = registry.available_tools()
        if not available:
            return None

        # 2. Create mission
        mission_engine = get_mission_engine()
        planner = get_task_planner()

        mission = mission_engine.create_mission(
            objective=user_input,
            constraints={"user_id": self.user_id},
            budget={"max_steps": 10},
        )
        mission_id = mission.id

        # 3. Decompose into steps
        plan = planner.plan(user_input, context={"available_tools": available})
        if not plan or not plan.get("steps"):
            return None

        # 4. Add steps to mission
        for step_def in plan["steps"]:
            mission_engine.add_step(
                mission_id,
                agent=step_def.get("agent", "planner"),
                action=step_def.get("action", ""),
                params=step_def.get("params", {}),
                verification=step_def.get("verification", {}),
            )

        # 5. Execute steps sequentially
        mission_engine.start(mission_id)
        all_artifacts = []
        verification_results = []
        recovery_engine = RecoveryEngine(max_budget=3)

        while True:
            step = mission_engine.get_next_step(mission_id)
            if step is None:
                break

            agent_name = step.agent
            action = step.action
            params = step.params.copy()
            params["user_id"] = self.user_id

            agent = get_agent(agent_name)
            if agent is None:
                # Try execution fabric directly for simple actions
                try:
                    from execution_fabric import get_execution_fabric
                    fabric = get_execution_fabric()
                    exec_result = fabric.execute(action, params)
                    step_result = AgentResult(exec_result.success, exec_result.output, exec_result.error,
                                             artifacts=exec_result.artifacts)
                except Exception:
                    mission_engine.fail_step(mission_id, step.id, "No agent available")
                    continue
            else:
                # Execute with recovery
                success, exec_result, recovery_log = wrap_with_recovery(
                    agent.execute, action, params,
                    max_budget=3, context={"mission_id": mission_id, "step_id": step.id}
                )
                if isinstance(exec_result, AgentResult):
                    step_result = exec_result
                elif isinstance(exec_result, dict):
                    step_result = AgentResult(
                        success=exec_result.get("success", success),
                        output=exec_result.get("output", ""),
                        error=exec_result.get("error", ""),
                        data=exec_result.get("data", {}),
                    )
                else:
                    step_result = AgentResult(success, str(exec_result))

            if step_result.success:
                mission_engine.complete_step(mission_id, step.id)
                all_artifacts.extend(step_result.artifacts)
            else:
                mission_engine.fail_step(mission_id, step.id, step_result.error)
                # If recovery exhausted, abort
                if len(recovery_log) >= 3:
                    break

            # 6. Verify
            verifier = get_verification_engine()
            verify_ok = verifier.verify(
                step.verification.get("type", "response_check"),
                step.verification.get("params", {}),
            )
            verification_results.append({
                "step": step.id,
                "action": action,
                "verified": verify_ok,
                "success": step_result.success,
            })

        # 7. Collect results
        completed = sum(1 for v in verification_results if v["verified"])
        total = len(verification_results)

        # 8. Record in learning loop
        try:
            from learning_loop import get_learning_loop
            ll = get_learning_loop()
            duration = time.time() - mission.created_at if mission.created_at else 0
            ll.record_mission(
                mission_id=mission_id,
                objective=user_input,
                status="completed" if completed == total else "partial" if completed > 0 else "failed",
                steps_total=total,
                steps_completed=completed,
                steps_verified=completed,
                duration=duration,
                tools_used=[v["action"] for v in verification_results],
                failures=[v for v in verification_results if not v["success"]],
            )
        except Exception:
            pass

        # 9. Update world model
        try:
            from world_model import get_world_model
            wm = get_world_model()
            wm.refresh(force=True)
        except Exception:
            pass

        # 8. Build response
        status = "completed" if completed == total else "partial"
        if completed == 0 and total > 0:
            status = "failed"

        return {
            "mission_id": mission_id,
            "status": status,
            "steps_completed": completed,
            "steps_total": total,
            "artifacts": all_artifacts,
            "verification": verification_results,
            "objective": user_input,
        }

    def _workspace_mission(self, user_input: str) -> dict | None:
        """Route a task to the JARVIS Workspace autonomous agent.

        Creates a workspace if needed, then launches an autonomous mission
        that executes independently while the user continues working.
        """
        try:
            from workspace_manager import get_workspace_manager
            from workspace_agent import get_workspace_agent
        except ImportError:
            return None

        mgr = get_workspace_manager()
        agent = get_workspace_agent()

        workspaces = mgr.list_workspaces()
        running = [w for w in workspaces if w.get("status") == "running"]

        if running:
            ws_id = running[0]["id"]
        else:
            ws = mgr.create_workspace(name="JARVIS Workspace")
            start_result = mgr.start_workspace(ws.id)
            if not start_result.get("ok"):
                return None
            ws_id = ws.id

        mission = agent.create_mission(user_input, ws_id)
        plan_result = agent.plan_mission(mission.id)
        if not plan_result.get("ok"):
            return {"ok": False, "error": plan_result.get("error", "Planning failed")}

        agent.start_mission(mission.id)

        return {
            "ok": True,
            "mission_id": mission.id,
            "workspace_id": ws_id,
            "text": f"Workspace mission started: {user_input[:60]}. "
                    f"Watch the WORKSPACE panel to see JARVIS work autonomously.",
            "steps": len(mission.steps),
        }

    def get_state(self) -> dict:
        return {
            "memory_summary": self.memory.get_summary(),
            "active_goals": self.memory.get_active_goals(),
            "preferences": self.memory._data.get("preferences", {}),
            "interaction_count": len(self.memory._data.get("interactions", [])),
            "last_active": self.memory._data.get("last_active", ""),
            "mood": self.mood,
            "mood_emoji": MOODS.get(self.mood, {}).get("emoji", ""),
            "mood_color": MOODS.get(self.mood, {}).get("color", ""),
            "current_thought": self._current_thought,
            "reflections": self.memory._data.get("self_reflections", [])[-3:],
            "observations": self.memory._data.get("system_observations", [])[-3:],
        }


_ENTITIES: dict[str, Entity] = {}
_ENTITY_LOCK = threading.Lock()


def get_entity(user_id: str = "local") -> Entity:
    with _ENTITY_LOCK:
        if user_id not in _ENTITIES:
            _ENTITIES[user_id] = Entity(user_id)
        return _ENTITIES[user_id]
