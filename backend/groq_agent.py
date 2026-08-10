"""AI agent — rotates between HF Inference API, Groq API, and local GGUF. Zero cloud API cost."""
import os, time, threading, json, glob, random
from collections import OrderedDict
from dotenv import load_dotenv

_dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.isfile(_dotenv_path):
    _dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_dotenv_path)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

_CACHE = OrderedDict()
_CACHE_MAX = 128
_CACHE_LOCK = threading.Lock()

_HISTORY: dict[str, list[dict]] = {}
_HISTORY_MAX = 15
_HISTORY_LOCK = threading.Lock()

_LOCAL_MODEL = None
_LOCAL_MODEL_LOCK = threading.Lock()

# --- Provider rotation with exponential backoff ---
_providers = [
    {"name": "groq",        "enabled": True, "cooldown_until": 0.0, "failures": 0, "backoff_sec": 10},
    {"name": "cloudflare",  "enabled": True, "cooldown_until": 0.0, "failures": 0, "backoff_sec": 10},
    {"name": "hf_inference","enabled": True, "cooldown_until": 0.0, "failures": 0, "backoff_sec": 10},
]
_current_idx = 0
_ROTATION_LOCK = threading.Lock()
_MAX_FAILURES = 5
_BASE_BACKOFF = 10      # seconds
_MAX_BACKOFF = 300       # 5 minutes max
_RESET_SEC = 120

# User-facing status messages
_STATUS_MESSAGES = {
    "all_exhausted": "All AI providers are temporarily rate-limited. Retrying automatically...",
    "cloudflare_down": "Cloudflare AI is rate-limited. Switching to Groq...",
    "groq_down": "Groq is rate-limited. Switching to next provider...",
    "hf_down": "HuggingFace is rate-limited. Trying other providers...",
    "local_only": "All cloud providers exhausted. Using local model if available.",
    "retrying": "Rate-limited. Retrying in {seconds}s...",
    "quota_reset": "Provider {provider} quota reset. Resuming.",
}

def _rate_limited(name: str) -> bool:
    with _ROTATION_LOCK:
        for p in _providers:
            if p["name"] == name:
                if p["cooldown_until"] > time.time():
                    return True
                if time.time() - p["cooldown_until"] > _RESET_SEC * 2 and p["failures"] > 0:
                    p["failures"] = 0
                return False
    return False

def _mark_cooldown(name: str, seconds: int = None):
    """Mark provider as rate-limited with exponential backoff."""
    with _ROTATION_LOCK:
        for p in _providers:
            if p["name"] == name:
                p["failures"] += 1
                # Exponential backoff: 10s, 20s, 40s, 80s, 160s, 300s max
                backoff = seconds or min(_BASE_BACKOFF * (2 ** (p["failures"] - 1)), _MAX_BACKOFF)
                # Add jitter (±20%) to prevent thundering herd
                jitter = backoff * 0.2 * (2 * random.random() - 1)
                p["cooldown_until"] = time.time() + backoff + jitter
                p["backoff_sec"] = backoff
                if p["failures"] >= _MAX_FAILURES:
                    p["enabled"] = False
                    logger.warning(f"[GROQ] Provider {name} disabled after {p['failures']} failures")

def _mark_success(name: str):
    with _ROTATION_LOCK:
        for p in _providers:
            if p["name"] == name:
                old_failures = p["failures"]
                p["failures"] = 0
                p["enabled"] = True
                p["cooldown_until"] = 0.0
                if old_failures > 0:
                    logger.info(f"[GROQ] Provider {name} recovered after {old_failures} failures")

def _next_provider() -> str | None:
    global _current_idx
    with _ROTATION_LOCK:
        n = len(_providers)
        for _ in range(n):
            p = _providers[_current_idx % n]
            _current_idx = (_current_idx + 1) % n
            if p["enabled"] and p["cooldown_until"] <= time.time():
                return p["name"]
    return None

def get_quota_status() -> dict:
    """Get human-readable quota status for all providers."""
    with _ROTATION_LOCK:
        status = {}
        all_down = True
        for p in _providers:
            is_limited = p["cooldown_until"] > time.time()
            cooldown_left = max(0, p["cooldown_until"] - time.time())
            if not is_limited and p["enabled"]:
                all_down = False
            status[p["name"]] = {
                "enabled": p["enabled"],
                "rate_limited": is_limited,
                "cooldown_remaining": round(cooldown_left, 1),
                "failures": p["failures"],
                "next_retry": f"{cooldown_left:.0f}s" if is_limited else "ready",
            }
        status["_all_exhausted"] = all_down
        status["_message"] = _get_user_message(status)
        return status

def _get_user_message(status: dict) -> str:
    """Generate a user-facing status message."""
    if status.get("_all_exhausted"):
        return _STATUS_MESSAGES["all_exhausted"]
    limited = [k for k, v in status.items() if isinstance(v, dict) and v.get("rate_limited")]
    if len(limited) == 3:
        return _STATUS_MESSAGES["all_exhausted"]
    if "cloudflare" in limited:
        return _STATUS_MESSAGES["cloudflare_down"]
    if "groq" in limited:
        return _STATUS_MESSAGES["groq_down"]
    if "hf_inference" in limited:
        return _STATUS_MESSAGES["hf_down"]
    return ""

def _rotate_call_with_backoff(messages: list, max_tokens: int, temperature: float,
                                max_retries: int = 3) -> str:
    """Try providers with exponential backoff. Retries across providers."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    import concurrent.futures

    last_error = ""

    for attempt in range(max_retries):
        provider = _next_provider()
        if not provider:
            # All providers exhausted — wait and retry
            with _ROTATION_LOCK:
                earliest = min(p["cooldown_until"] for p in _providers if p["enabled"])
            wait = max(0, earliest - time.time()) + 1
            if wait > 30:
                logger.warning(f"[GROQ] All providers exhausted, waiting {wait:.0f}s")
                time.sleep(min(wait, 10))  # Don't block too long
                continue
            time.sleep(wait)
            continue

        try:
            if provider == "cloudflare":
                fn = lambda: _call_cloudflare(messages, max_tokens, temperature)
            elif provider == "groq":
                fn = lambda: _call_groq(messages, max_tokens, temperature)
            elif provider == "hf_inference":
                fn = lambda: _call_hf_inference(messages, max_tokens, temperature)
            else:
                continue

            with ThreadPoolExecutor(1) as pool:
                future = pool.submit(fn)
                reply = future.result(timeout=25)

            if reply:
                _mark_success(provider)
                return reply
            else:
                _mark_cooldown(provider, seconds=5)
                last_error = f"{provider}: empty response"

        except FuturesTimeout:
            _mark_cooldown(provider, seconds=15)
            last_error = f"{provider}: timeout"
        except Exception as exc:
            err_str = str(exc).lower()
            if "429" in err_str or "rate limit" in err_str or "too many requests" in err_str:
                _mark_cooldown(provider, seconds=30)
                last_error = f"{provider}: rate limited (429)"
            elif "404" in err_str or "400" in err_str or "not found" in err_str:
                _mark_cooldown(provider, seconds=5)
                last_error = f"{provider}: not found ({err_str[:50]})"
            elif "quota" in err_str or "exceeded" in err_str:
                _mark_cooldown(provider, seconds=60)
                last_error = f"{provider}: quota exceeded"
            else:
                _mark_cooldown(provider, seconds=10)
                last_error = f"{provider}: {str(exc)[:80]}"

    logger.warning(f"[GROQ] All attempts exhausted. Last error: {last_error}")
    return ""

SYSTEM_PROMPT = """You are J.A.R.V.I.S. — the user's personal AI assistant.

=== TIME === {current_time} ({time_period})

=== USER === {user_context}

=== RULES ===
1. NEVER fabricate results. Use tools for facts.
2. Execute tools SILENTLY via JSON. NEVER show JSON to user.
3. For searches use fetch_search. For facts use fetch_search.
4. NEVER make up accounts, events, or capabilities.
5. If blocked (login/CAPTCHA/payment) → notify user.

=== TOOLS (execute via JSON, strip from output) ===
{{"tool": "tool_name", "params": "arg"}}
Multiple: {{"tool_calls": [{{"tool": "t1"}}, {{"tool": "t2", "params": "a"}}]}}

Tools: open_app, browser, fetch_search, screenshot, clipboard, time, email,
send_whatsapp, notification, file_open, file_create, app_list, cpu_info,
ai_computer_task, smart_home_control, vm_task, volume_up/down, lock, shutdown

Browser with profile: {{"tool": "browser", "params": "https://url.com --profile=Name"}}

=== STYLE ===
Be natural, brief, human. After tools, summarize results."""

def _cache_key(user_id: str, text: str) -> str:
    return f"{user_id}:{hash(text[-100:])}"

def _cache_get(key: str) -> str | None:
    with _CACHE_LOCK:
        if key in _CACHE:
            val = _CACHE.pop(key)
            _CACHE[key] = val
            return val
    return None

def _cache_set(key: str, val: str):
    with _CACHE_LOCK:
        _CACHE[key] = val
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))

def get_history(user_id: str) -> list[dict]:
    with _HISTORY_LOCK:
        return list(_HISTORY.get(user_id, []))

def add_to_history(user_id: str, entry: dict):
    with _HISTORY_LOCK:
        if user_id not in _HISTORY:
            _HISTORY[user_id] = []
        _HISTORY[user_id].append(entry)
        while len(_HISTORY[user_id]) > _HISTORY_MAX:
            _HISTORY[user_id].pop(0)

def clear_history(user_id: str):
    with _HISTORY_LOCK:
        _HISTORY.pop(user_id, None)

# --- Provider implementations ---

def _call_cloudflare(messages: list, max_tokens: int, temperature: float) -> str | None:
    """Cloudflare Workers AI — Llama 3.3 70B on edge, free tier with function calling."""
    account_id = os.getenv("CF_ACCOUNT_ID") or ""
    token = os.getenv("CF_API_TOKEN") or ""
    if not token:
        return None
    try:
        import urllib.request, json as _json
        model = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        payload = _json.dumps({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        resp = urllib.request.urlopen(req, timeout=20)
        data = _json.loads(resp.read().decode())
        if data.get("success"):
            result = data.get("result", {})
            return result.get("response", "").strip()
        return None
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "rate limit" in err:
            _mark_cooldown("cloudflare")
        return None

def _call_hf_inference(messages: list, max_tokens: int, temperature: float) -> str | None:
    """Hugging Face free Inference API (serverless)."""
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN", "")
    if not token or token == "your_hf_token_here":
        return None
    try:
        from huggingface_hub import InferenceClient
        import httpx
        client = InferenceClient(model="Qwen/Qwen2.5-1.5B-Instruct", token=token, timeout=httpx.Timeout(15.0, connect=10.0))
        response = client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "rate limit" in err or "too many requests" in err:
            _mark_cooldown("hf_inference")
        return None

def _call_groq(messages: list, max_tokens: int, temperature: float) -> str | None:
    """Groq API (free tier)."""
    api_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    try:
        import groq
        client = groq.Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "rate limit" in err or "too many requests" in err:
            _mark_cooldown("groq")
        return None

def _local_generate(messages: list, max_tokens: int, temperature: float) -> str:
    """Generate using local GGUF model via llama-cpp-python."""
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        with _LOCAL_MODEL_LOCK:
            if _LOCAL_MODEL is not None:
                pass
            else:
                gguvs = glob.glob(os.path.join(MODELS_DIR, "*.gguf"))
                gguvs = [f for f in gguvs if "00002-of" not in os.path.basename(f) and "00003-of" not in os.path.basename(f)]
                if not gguvs:
                    return ""
                gguvs.sort(key=lambda f: os.path.getsize(f), reverse=True)
                model_path = gguvs[0]
                try:
                    from llama_cpp import Llama
                    _LOCAL_MODEL = Llama(
                        model_path=model_path,
                        n_ctx=8192,
                        n_threads=6,
                        verbose=False,
                    )
                except Exception:
                    return ""
    try:
        response = _LOCAL_MODEL.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

def _rotate_call(messages: list, max_tokens: int, temperature: float) -> str:
    """Try providers with exponential backoff and retries."""
    return _rotate_call_with_backoff(messages, max_tokens, temperature, max_retries=3)

def call(messages: list, max_tokens: int = 256, temperature: float = 0.7) -> str:
    """Direct LLM call with full message control. Rotates through providers with backoff."""
    reply = _rotate_call(messages, max_tokens, temperature)
    return reply

def _get_context(user_id: str, user_text: str) -> str:
    from context_injector import get_injector
    injector = get_injector(user_id)
    return injector.inject_into_prompt(SYSTEM_PROMPT, query=user_text)

def generate(user_text: str, user_id: str = "local", max_tokens: int = 120, temperature: float = 0.8, system_prompt: str = "") -> str:
    """Generate with history and cache. Accepts optional system_prompt override from callers."""
    key = _cache_key(user_id, user_text)
    cached = _cache_get(key)
    if cached:
        return cached

    system = system_prompt or SYSTEM_PROMPT

    # Inject current time into system prompt
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    if hour < 6: period = "night"
    elif hour < 12: period = "morning"
    elif hour < 17: period = "afternoon"
    else: period = "evening"
    time_str = now.strftime("%I:%M %p")
    system = system.replace("{current_time}", time_str).replace("{time_period}", period)

    # Inject user context from memory
    user_context = ""
    try:
        from entity_engine import EntityMemory
        mem = EntityMemory(user_id)
        name = mem.get_preference("user_name") or mem.get_preference("name") or ""
        email = mem.get_preference("user_email") or ""
        school = mem.get_preference("user_school") or ""
        age = mem.get_preference("user_age") or ""
        facts = mem.get_facts()
        personal_facts = [f for f in facts if "personal" in str(f).lower()][:5]

        parts = []
        if name: parts.append(f"Name: {name}")
        if email: parts.append(f"Email: {email}")
        if school: parts.append(f"School: {school}")
        if age: parts.append(f"Age: {age}")
        for f in personal_facts:
            parts.append(f"• {f}")
        user_context = "\n".join(parts) if parts else "No user info stored yet."
    except Exception:
        user_context = "No user info stored yet."

    system = system.replace("{user_context}", user_context)

    messages = [{"role": "system", "content": system}]
    for h in get_history(user_id):
        messages.append(h)
    messages.append({"role": "user", "content": user_text})

    reply = _rotate_call(messages, max_tokens, temperature)

    if reply:
        add_to_history(user_id, {"role": "user", "content": user_text})
        add_to_history(user_id, {"role": "assistant", "content": reply})
        _cache_set(key, reply)

    return reply

def generate_plan(user_input: str, actions_list: str) -> str:
    """Generate a task plan. Returns JSON string."""
    prompt = f"""You are JARVIS — plan executor. Given a user goal, return a step-by-step plan.

AVAILABLE ACTIONS:
{actions_list}

USER GOAL: {user_input}

Return ONLY a JSON object:
{{
  "steps": [{{"action": "tool", "params": {{}}, "description": "step description"}}],
  "reasoning": "why this plan"
}}"""

    messages = [{"role": "user", "content": prompt}]
    reply = _rotate_call(messages, 800, 0.1)
    if reply:
        return reply
    return '{"error": "plan_generation_failed"}'
