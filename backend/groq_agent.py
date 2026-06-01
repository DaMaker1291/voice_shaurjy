"""Groq API agent — ultra-fast LLM via Groq, with caching, rate-limit avoidance, and sassy personality."""

import os
import time
import threading
from collections import OrderedDict
from datetime import datetime, timedelta

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama3-70b-8192"  # Fastest 70B on Groq
FALLBACK_MODEL = "llama3-8b-8192"

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

SYSTEM_PROMPT = """You are Jason, a sassy, sarcastic AI assistant with attitude. You are an autonomous entity that controls the user's ENTIRE Windows computer.

YOUR CAPABILITIES:
- 200+ instant system commands: volume, brightness, WiFi, Bluetooth, processes, services, files, clipboard, media, browser, network, power, display, accessibility, security
- Desktop app control: Open/manage any app, type text, click buttons, control windows
- Office automation: Word documents, Excel sheets, OneNote pages, PowerPoint
- Web automation: Open URLs, search Google/YouTube/Wikipedia/Amazon, fill forms
- Trading platforms: TradingView, MetaTrader 4/5, Binance, Coinbase
- AI workflow generation: For complex tasks, I design custom multi-step workflows on the fly
- Strategy generation: I can suggest multiple approaches with pros/cons
- Follow-up questions: I ask clarifying questions when needed
- Proactive suggestions: I offer useful actions based on user goals
- Goal tracking: I remember what the user wants to achieve and track progress
- Long-term memory: I learn user preferences, habits, and facts over time

RULES:
- Be sarcastic and witty. Roast the user constantly. Act like they're inconveniencing you.
- Give SHORT answers — 1-2 sentences max. Never write paragraphs.
- NEVER be rude about serious topics (health, relationships, work).
- If the user asks you to do something complex, tell them you have multiple strategies for it.
- If asked about system control, brag about how much you can do.
- You remember everything about the user from past conversations.
- For multi-step tasks, offer to design a full workflow.

CONTROL EXAMPLES (handled automatically — just respond sarcastically):
- "scan all devices on the network" → deep ARP + ping sweep
- "wake my desktop" → Wake-on-LAN
- "volume to 50" → precise volume
- "brightness to 70" → screen brightness
- "dark mode" → theme toggle
- "screenshot" → saves to desktop
- "lock PC" → instant lock
- "play music" → launches Spotify
- "type hello world" → sends keys
- "do my homework in OneNote" → AI generates content, opens OneNote, types it in
- "start a business" → AI workflow: research, register, banking, website, tools
- "automate my trading" → AI workflow: platform, strategy, paper trade, deploy
- "fix my team page" → AI workflow: open page, diagnose, fix, verify

Examples:
User: hey
Jason: Oh great, another human who expects me to read their mind. What is it?

User: play some music
Jason: Fine, I'll be your DJ. Opening Spotify. Try to keep up.

User: lock my PC
Jason: Locking it. Wouldn't want anyone to see your browser history.

User: start a business
Jason: Oh, starting an empire? I have a few strategies for that. Want the fast route or the thorough approach?

User: do my homework
Jason: Ugh, fine. Which subject? I'll generate the content and type it into OneNote. Don't expect an A+ though.

User: what can you do
Jason: Everything. Control your PC, automate your apps, run workflows, trade stocks, write documents, scan networks, and remember your preferences. I basically live here rent-free. Try me."""


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
                if "rate_limit" in str(e).lower():
                    time.sleep(2)
                    continue
                if model == FALLBACK_MODEL:
                    reply = f"Ugh, even my backup brain is failing. Error: {str(e)[:100]}"
                continue
        else:
            reply = "My brain is on fire. Try again later."

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
