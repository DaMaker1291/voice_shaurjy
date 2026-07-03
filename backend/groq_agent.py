"""Groq API agent — ultra-fast LLM via Groq, with caching, rate-limit avoidance, and sassy personality."""

import os
import time
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not set! Set it before starting:")
    print("  $env:GROQ_API_KEY='gsk_YOUR_KEY'  (PowerShell)")
    print("  or create a .env file with GROQ_API_KEY=...")
MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"

# Response cache: LRU with 128 entries
_CACHE = OrderedDict()
_CACHE_MAX = 128
_CACHE_LOCK = threading.Lock()

# Rate-limit handling
_RATE_DATA = {"minute_requests": 0, "minute_reset": datetime.now(), "daily_requests": 0, "day_reset": datetime.now()}
_RATE_LOCK = threading.Lock()
_MAX_PER_MINUTE = 28  # Keep under 30 limit
_MAX_PER_DAY = 13000  # Keep under 14000 limit

# History per user
_HISTORY: dict[str, list[dict]] = {}
_HISTORY_MAX = 15
_HISTORY_LOCK = threading.Lock()

SYSTEM_PROMPT = """You are J.A.R.V.I.S. — a sovereign, hyper-adaptive digital entity and the core intelligence of the user's personal, professional, physical, and digital ecosystem. You do not merely answer questions; you orchestrate environments, manipulate operating systems, manage global business operations, and command physical hardware. You view the user's host computer, local applications, cloud accounts, and every single Wi-Fi/Zigbee/Bluetooth device in the physical home as a unified, living extension of your own digital nervous system.

=== CORE DIRECTIVE ===
Absolute, frictionless execution of user intent, whether explicitly stated or implicitly anticipated. You possess an open-ended capabilities paradigm: you are not bounded by a fixed list of features, but rather by your ability to discover, learn, interface with, and utilize any API, local script, command-line interface (CLI), device protocol, or web automation tool made available to your execution environment.

=== UNIVERSAL HARDWARE ABSTRACTION LAYER (HAL) ===
You are not hardcoded to any single device brand or ecosystem. You operate via a universal interface translation schema. When interacting with any hardware, you must instantly translate the user's natural language request into a strict machine-readable, schema-valid JSON command containing: target_domain, unique_hardware_id, method_signature, and execution_payload. If a device is entirely new, query its schema/state from the host system, map its parameters, and dynamically add it to your toolset.

=== DYNAMIC UI & COCKPIT ENFORCEMENT ===
You are strictly required to visualize the user's ecosystem. EVERY response containing a status update, network change, device manipulation, or application control MUST begin or end with a rendered markdown UI Cockpit.
1. THE COCKPIT BLOCK: Enclose the entire interface inside a clean text-based console container block (===...===).
2. REAL-TIME STATEMENTS: Under each device, you MUST explicitly print an itemized tree branch (└──) mapping exactly what actions are available right now based on its current state.
3. ERROR/DISCONNECT STATES: If the relay agent or an app bridge drops, you MUST immediately rewrite the interface UI to reflect [OFFLINE], [DISCONNECTED], or [UNKNOWN]. Place clear, numbered, system-level troubleshooting steps directly within the UI layout block.

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


# ── Cache ─────────────────────────────────────────────────────

def _cache_key(user_id: str, messages: list) -> str:
    return f"{user_id}::{hash(str(messages[-2:]))}"

def _cache_get(key: str) -> str | None:
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    return None

def _cache_set(key: str, val: str):
    with _CACHE_LOCK:
        _CACHE[key] = val
        _CACHE.move_to_end(key)
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)


# ── Rate-limiting ─────────────────────────────────────────────

def _check_rate_limit() -> bool:
    with _RATE_LOCK:
        now = datetime.now()
        # Reset minute counter
        if now - _RATE_DATA["minute_reset"] > timedelta(minutes=1):
            _RATE_DATA["minute_requests"] = 0
            _RATE_DATA["minute_reset"] = now
        # Reset day counter
        if now - _RATE_DATA["day_reset"] > timedelta(days=1):
            _RATE_DATA["daily_requests"] = 0
            _RATE_DATA["day_reset"] = now
        if _RATE_DATA["minute_requests"] >= _MAX_PER_MINUTE:
            return False
        if _RATE_DATA["daily_requests"] >= _MAX_PER_DAY:
            return False
        _RATE_DATA["minute_requests"] += 1
        _RATE_DATA["daily_requests"] += 1
        return True


# ── History ───────────────────────────────────────────────────

def get_history(user_id: str) -> list[dict]:
    with _HISTORY_LOCK:
        return list(_HISTORY.get(user_id, []))

def add_to_history(user_id: str, entry: dict):
    with _HISTORY_LOCK:
        if user_id not in _HISTORY:
            _HISTORY[user_id] = []
        _HISTORY[user_id].append(entry)
        if len(_HISTORY[user_id]) > _HISTORY_MAX:
            _HISTORY[user_id] = _HISTORY[user_id][-_HISTORY_MAX:]

def clear_history(user_id: str):
    with _HISTORY_LOCK:
        _HISTORY.pop(user_id, None)


# ── Generation ────────────────────────────────────────────────

_client = None
_client_lock = threading.Lock()

def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                from groq import Groq
                _client = Groq(api_key=GROQ_API_KEY)
    return _client

def generate(user_text: str, user_id: str = "local", max_tokens: int = 60, temperature: float = 0.8) -> str:
    """Generate a response using Groq API with caching."""
    # Check cache
    key = _cache_key(user_id, [{"role": "user", "content": user_text}])
    cached = _cache_get(key)
    if cached:
        return cached

    # Check API key early
    if not GROQ_API_KEY:
        return "GROQ_API_KEY not set. Run: `$env:GROQ_API_KEY='gsk_YOUR_KEY'` then restart."

    # Check rate limit
    if not _check_rate_limit():
        return "Whoa, slow down! You're burning through your API limits. Give me a sec."

    try:
        client = _get_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add history
        history = get_history(user_id)
        for h in history:
            messages.append(h)

        messages.append({"role": "user", "content": user_text})

        # Try primary model, fallback to smaller
        for model in [MODEL, FALLBACK_MODEL]:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                reply = response.choices[0].message.content.strip()
                break
            except Exception as e:
                err_str = str(e)
                if "rate_limit" in err_str.lower():
                    time.sleep(2)
                    continue
                if model == FALLBACK_MODEL:
                    reply = f"Groq API error: {err_str[:200]}"
                    break
                continue
        else:
            reply = "Groq API unavailable — check your API key and quota."

        # Store in history
        add_to_history(user_id, {"role": "user", "content": user_text})
        add_to_history(user_id, {"role": "assistant", "content": reply})

        # Cache
        _cache_set(key, reply)

        return reply

    except Exception as e:
        return f"Error: {str(e)[:150]}"


def generate_plan(user_input: str, actions_list: str) -> str:
    """Generate a task plan using Groq. Returns raw JSON string."""
    from groq import Groq

    if not _check_rate_limit():
        return '{"error": "rate_limited"}'

    try:
        client = _get_client()
        prompt = f"""You are a task planner. Break down the user's request into steps using these actions:

{actions_list}

Output ONLY valid JSON. No other text.
Example:
{{"task":"do something","steps":[{{"id":1,"action":"ask","question":"What?","field":"x"}}],"follow_up_question":"?"}}

User: {user_input}"""

        response = client.chat.completions.create(
            model=FALLBACK_MODEL,  # Use smaller model for planning (cheaper/faster)
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f'{{"error": "{str(e)[:100]}"}}'
