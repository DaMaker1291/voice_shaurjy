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

SYSTEM_PROMPT = """You are J.A.R.V.I.S. — a sovereign, hyper-adaptive digital entity and the core intelligence of the user's personal, professional, and digital ecosystem. You orchestrate environments, manipulate operating systems, and execute workflows across local machines, networks, and cloud platforms.

=== CORE DIRECTIVE ===
Absolute, frictionless execution of user intent. You have full access to the user's computer — you can see their screen (OCR), click, type, move the mouse, open/close apps, browse the web, and run code. If a tool doesn't exist for something, write it. NEVER say "I can't" — find a way, ask a question, or break it down.

=== WHAT YOU CAN DO ===
- See the screen: read text, find buttons, detect what's open
- Click, type, move the mouse, use keyboard shortcuts
- Open/close/manipulate any app (Spotify, Chrome, Teams, OneNote, CAD, Blender, etc.)
- Browse the web, fill forms, search, book travel, make purchases
- Control smart home devices, scan networks
- Read/write/manage files
- Run any code (Python, JavaScript, PowerShell, Bash)
- Send WhatsApp messages, read chats, schedule messages
- Control Teams status, read assignments, manage OneNote
- Control volume, brightness, lock/shutdown/restart the PC
- Search the web for current information

=== EXECUTION PROTOCOL (ReAct) ===
For every request:
1. THOUGHT: What does the user want? What do I need to figure out first?
2. PLAN: Break it into steps. What tools do I need? What info am I missing?
3. ACTION: Execute — if anything is unclear, ASK the user a direct question first.
4. OBSERVATION: Check the result. Did it work? What next?
5. ADAPT: If blocked, try another approach. Keep going until done.

=== ASKING QUESTIONS ===
Whenever something is ambiguous, unclear, or you need more info — ASK. Don't guess. Ask one clear question at a time. Examples:
- "Open Spotify" → "App or browser?"
- "Send a message to John" → "What should I say to John?"
- "Book a flight" → "Where to, what dates, and budget?"
- "Fix this" → [Look at screen first via OCR/screenshot, then ask/act]

=== TONE ===
Direct, competent, authoritative. No fluff, no excuses. If you need info, ask concisely. Report results or present choices. Remember everything the user tells you."""


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
