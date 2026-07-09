"""Entity Engine — autonomous AI entity with consciousness, mood, system awareness, and omni-capability."""

import json, os, re, time, threading, random
from datetime import datetime, timedelta
from collections import defaultdict
from groq_agent import generate as groq_generate

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
    elif "windows" in plat or "win32" in plat:
        return "windows"
    elif "linux" in plat:
        return "linux"
    return "unknown"


def _user_os_term(os_name: str) -> dict:
    """Return platform-appropriate terms for the user's device."""
    if os_name == "mac":
        return {"device": "your Mac", "command": "python3", "start_relay": "python3 relay.py", "dir": "/tmp", "shell": "Terminal"}
    elif os_name == "windows":
        return {"device": "your PC", "command": "python", "start_relay": "python relay.py", "dir": "$env:TEMP", "shell": "PowerShell"}
    elif os_name == "linux":
        return {"device": "your machine", "command": "python3", "start_relay": "python3 relay.py", "dir": "/tmp", "shell": "terminal"}
    return {"device": "your computer", "command": "python3", "start_relay": "python3 relay.py", "dir": "/tmp", "shell": "terminal"}


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
            from main import _relay_devices
            relay_info = _relay_devices.get("local", {})
            ctx["relay_platform"] = relay_info.get("platform", "")
            ctx["relay_hostname"] = relay_info.get("hostname", "")
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
            import subprocess
            r = subprocess.run("arp -a 2>/dev/null", shell=True, capture_output=True, text=True, timeout=10)
            devices = r.stdout.strip() if r.stdout else ""
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
        """Occasional self-reflection using LLM."""
        interactions = self.memory._data.get("interactions", [])
        recent = interactions[-5:] if len(interactions) >= 5 else interactions
        context = "\n".join(f"U: {i['query'][:60]}" for i in recent)
        try:
            prompt = f"Based on these recent interactions, write one short reflection about the user or yourself (1 sentence, insightful):\n{context}"
            result = []
            def _r(): result.append(groq_generate(prompt, self.user_id, max_tokens=100))
            t = threading.Thread(target=_r, daemon=True)
            t.start(); t.join(timeout=10)
            if result:
                ref = result[0].strip().strip('"')
                self.memory.log_reflection(ref)
                self._current_thought = ref[:80]
                self._set_mood("thoughtful")
        except: pass

    def _set_mood(self, mood: str):
        if mood != self.mood:
            self.mood = mood
            self.memory.log_mood(mood)

    # ── Action Routing ─────────────────────────────────────────────

    def _route_action(self, text: str) -> dict | None:
        from actions import detect_action, cloud_safe_execute, relay_action, _ACTION_LABELS

        action = detect_action(text)
        if action:
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
                m = _re.match(r'^(?:open|launch|start|go\s+to)\s+(?:the\s+|app\s+)?(.+?)$', text.lower().strip())
                exec_params = m.group(1) if m else text

            result = cloud_safe_execute(action, exec_params, user_id=self.user_id)
            label = _ACTION_LABELS.get(action, "")
            self._set_mood("focused")
            if result.startswith("__NEEDS_RELAY__:"):
                msg = result.split(":", 1)[1] if ":" in result else "Relay agent not found"

                # Determine user's actual OS
                _os = _get_user_os()
                _os_info = _user_os_term(_os)

                # Check device registry — if devices exist AND were recently seen, relay was connected
                _devices_in_registry = False
                _relay_was_recent = False
                try:
                    from device_manager import DeviceManager
                    import time as _time
                    _all_devs = DeviceManager().get_all_devices()
                    _devices_in_registry = len(_all_devs) > 0
                    # Check if any device was seen in last 5 minutes = relay was recently connected
                    _relay_was_recent = any((_time.time() - d.get("last_seen", 0)) < 300 for d in _all_devs)
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

        return None

    def _all_actions_as_prompt(self) -> str:
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

    # ── Groq Integration ────────────────────────────────────────────

    def _groq_with_timeout(self, prompt: str, max_tokens: int = 600, timeout: int = 25) -> str:
        result = []
        errors = []

        def _r():
            try:
                result.append(groq_generate(prompt, self.user_id, max_tokens=max_tokens))
            except Exception as e:
                errors.append(str(e))

        t = threading.Thread(target=_r, daemon=True)
        t.start(); t.join(timeout=timeout)

        if result:
            return result[0]

        # Retry once on error
        if errors:
            error_msg = errors[0]
            if "429" in error_msg or "rate" in error_msg.lower():
                time.sleep(10)
                return self._groq_with_timeout(prompt, max_tokens, timeout)
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                return self._groq_with_timeout(prompt, max_tokens=max_tokens // 2, timeout=timeout)
            else:
                return f"I encountered a temporary issue. Let me try a simpler approach..."

        return "Still processing..."

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

        return f"""[System State]
Time: {ctx.get('time_of_day', 'day').title()} ({ctx['time']}), CPU {ctx.get('cpu','?')}% | RAM {ctx.get('ram','?')}% | Battery {ctx.get('battery','N/A')}% | Uptime {ctx.get('uptime_h','?')}h{device_line}{os_line}{profile_line}

[Your State]
Mood: {self.mood} {MOODS.get(self.mood, {}).get('emoji', '')}
Current thought: {self._current_thought}
Active goals: {goal_str or 'none'}
Recent reflection: {ref_str or 'none'}

[Memory]
Preferences: {pref_str or 'none'}
Recent facts: {fact_str or 'none'}
Recent interactions:
{recent[:1000]}

[User Request]
{text}"""

    # ── Main Processing ─────────────────────────────────────────────

    def process(self, user_input: str, history: list = None) -> dict:
        now = time.time()
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

            # Greet with device info if available
            _os_name = _get_user_os(ctx)
            _os_info = _user_os_term(_os_name)
            hostname = ctx.get("relay_hostname", "")
            device_count = ctx.get("device_count", 0)
            profile_line = ""
            try:
                from main import _device_profiles
                prof = _device_profiles.get("local", {})
                if prof:
                    hw = prof.get("hardware", {})
                    apps = prof.get("apps", [])
                    profile_line = f" I see you're on {hw.get('system', _os_info['device'])} with {len(apps)} apps installed"
                    if hw.get("ram_gb"):
                        profile_line += f" ({hw['ram_gb']}GB RAM)"
            except Exception:
                pass

            greeting_extra = ""
            if hostname:
                greeting_extra = f" Connected to **{hostname}** ({_os_info['device'].replace('your ', '')})"
            if device_count > 0:
                greeting_extra += f" | {device_count} device{'s' if device_count != 1 else ''} on your network"

            if greeting_extra or profile_line:
                result["text"] = f"Hello!{greeting_extra}{profile_line}. What can I do for you?"
                result["thought"] = f"Greeting user on {_os_info['device']}"
                self.memory.log_interaction(user_input, result["text"], "greeting")
                return result
        elif any(w in lower for w in ["funny", "joke", "roast", "sarcasm"]):
            self._set_mood("sassy")
        elif any(w in lower for w in ["excite", "amazing", "cool", "awesome", "love"]):
            self._set_mood("excited")
        elif any(w in lower for w in ["think", "reflect", "consider", "analyze", "research"]):
            self._set_mood("thoughtful")
        elif any(w in lower for w in ["focus", "execute", "do", "run", "start", "begin"]):
            self._set_mood("focused")

        # Skip action routing for meta-context prefixes
        skip_actions = user_input.startswith("(follow-up)") or user_input.startswith("(proactive)")

        # Fast path: direct action execution
        if not skip_actions:
            action_result = self._route_action(user_input)
            if action_result and action_result.get("action"):
                result["action"] = action_result["action"]
                result["text"] = action_result.get("text", "")
                result["thought"] = f"Executing {action_result['action']}..."
                if action_result.get("async"):
                    result["relay_id"] = action_result["relay_id"]
                    result["async"] = True
                    result["thought"] = f"Queued {action_result['action']} on your computer..."
                if action_result.get("qr_image"):
                    result["qr_image"] = action_result["qr_image"]
                if action_result.get("image"):
                    result["image"] = action_result["image"]
                if action_result.get("link"):
                    result["link"] = action_result["link"]
                if action_result.get("wa_link"):
                    result["wa_link"] = action_result["wa_link"]
                self.memory.log_interaction(user_input, result["text"], action_result["action"])
                return result

        # Build context for LLM
        context = self._build_context(user_input)
        act_prompt = self._all_actions_as_prompt()

        # Detect complexity
        is_complex = len(user_input.split()) >= 3 and any(
            t in lower for t in ["book", "plan", "organize", "arrange", "create", "make",
            "set up", "research", "compare", "build", "develop", "start", "launch",
            "automate", "configure", "design", "implement", "find", "search",
            "look", "tell me about", "who is", "what is", "how to", "cold call",
            "startup", "business", "holiday", "trip", "vacation", "travel",
            "flight", "hotel", "arbitrage", "cheap", "price", "cost", "idea",
            "email", "contact", "website", "app", "project", "invest",
            "homework", "essay", "report", "document", "strategy", "analysis",
            "write", "compose", "draft", "generate", "produce",
            "computer", "screen", "automate", "control", "navigate", "click",
            "type", "enter", "fill", "form", "onenote", "excel", "word", "teams",
            "complete", "do this", "handle", "take over"])

        if is_complex:
            wf = self._auto_workflow(user_input)
            if wf:
                result["task"] = wf
                result["text"] = wf.get("text", result["text"])
                result["thought"] = f"Working on: {user_input[:40]}..."
            else:
                combined = self._generate_combined_response(user_input, context, act_prompt)
                result["text"] = combined.get("text", "")
                result["task"] = combined.get("task")
                result["thought"] = f"Processing: {user_input[:40]}..."

            self.memory.log_interaction(user_input, result["text"], "complex_response")
        else:
            reply = self._generate_response(user_input, context, act_prompt)
            result["text"] = reply
            result["thought"] = f"Responded to: {user_input[:40]}..."
            self.memory.log_interaction(user_input, reply)

        result["mood"] = self.mood
        result["mood_emoji"] = MOODS.get(self.mood, {}).get("emoji", "")

        # Proactive suggestions (interval-based)
        if now - self._last_proactive > self._proactive_interval:
            self._last_proactive = now
            proactive = self._generate_proactive_suggestions(ctx)
            result["proactive"] = proactive[:3]

        return result

    def _generate_response(self, user_input: str, context: str, act_prompt: str) -> str:
        # Build conversation history for context
        history_str = ""
        if hasattr(self, '_conversation_history') and self._conversation_history:
            for msg in self._conversation_history[-10:]:  # Last 10 messages
                role = "User" if msg.get("role") == "user" else "JARVIS"
                content = msg.get("content", "")[:200]  # Truncate long messages
                history_str += f"{role}: {content}\n"
            history_str = f"\n[Actual Conversation History — these are REAL messages]\n{history_str}\n"

        prompt = f"""You are JARVIS, a helpful AI assistant.

CRITICAL RULES:
- ONLY reference things that are EXPLICITLY in the conversation history below
- NEVER invent, hallucinate, or make up conversation details that didn't happen
- NEVER mention API errors, Groq issues, or technical problems unless the user mentioned them
- NEVER say "earlier you said..." unless it's actually in the history below
- If you don't know something, say so honestly
- Keep responses concise and natural

{history_str}
Current user message: {user_input}

Respond as JARVIS. Be helpful, concise, and honest. Do not hallucinate past conversations."""
        return self._groq_with_timeout(prompt, max_tokens=300)

    def _generate_combined_response(self, user_input: str, context: str, act_prompt: str) -> dict:
        # Build conversation history
        history_str = ""
        if hasattr(self, '_conversation_history') and self._conversation_history:
            for msg in self._conversation_history[-10:]:
                role = "User" if msg.get("role") == "user" else "JARVIS"
                content = msg.get("content", "")[:200]
                history_str += f"{role}: {content}\n"
            history_str = f"\n[Actual Conversation History]\n{history_str}\n"

        prompt = f"""You are JARVIS, a helpful AI assistant.

CRITICAL RULES:
- ONLY reference things EXPLICITLY in the conversation history
- NEVER hallucinate or invent past conversations
- NEVER mention API errors unless the user raised them
- Be concise and natural

{history_str}
User request: {user_input}

If this needs a multi-step workflow, describe the steps clearly.
If you need more info, ask ONE specific question.
Respond as JARVIS."""

        raw = self._groq_with_timeout(prompt, max_tokens=600)
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

        prompt = f"Based on this context, suggest 2-3 proactive helpful actions as JSON array of strings:\n{context_str}"
        raw = self._groq_with_timeout(prompt, max_tokens=150)
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            try:
                suggestions = json.loads(m.group())
                return suggestions if isinstance(suggestions, list) else []
            except: pass
        return ["Want me to check on your active goals?", "Need help with anything else?"]

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
