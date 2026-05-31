"""Local LLM — Qwen2.5-0.5B-Instruct (2 GB RAM, fast CPU inference)."""

import threading
from collections import OrderedDict
import torch
import os
from transformers import AutoModelForCausalLM, AutoTokenizer

# Maximize CPU threads for inference
torch.set_num_threads(min(8, os.cpu_count() or 4))

_MODEL = None
_TOKENIZER = None
_LOADING = threading.Event()
_LOAD_LOCK = threading.Lock()
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

# Response cache: LRU with max 64 entries
_CACHE = OrderedDict()
_CACHE_MAX = 64
_CACHE_LOCK = threading.Lock()

# Conversation history per user (last 20 turns)
_HISTORY: dict[str, list[dict]] = {}
_HISTORY_MAX = 20
_HISTORY_LOCK = threading.Lock()

FEW_SHOT = """User: what is the capital of France?
Jason: The capital of France is Paris.

User: who wrote Romeo and Juliet?
Jason: Romeo and Juliet was written by William Shakespeare.

User: what is 2+2?
Jason: 4

User: how does photosynthesis work?
Jason: Plants use sunlight, water and carbon dioxide to produce glucose and oxygen. The chlorophyll in leaves absorbs sunlight and converts it into chemical energy.

User: tell me a joke
Jason: Why did the scarecrow win an award? Because he was outstanding in his field.

User: what is machine learning?
Jason: Machine learning is a branch of AI where computers learn patterns from data without being explicitly programmed for every rule."""


def _load():
    global _MODEL, _TOKENIZER
    if _MODEL is not None:
        return

    if not _LOAD_LOCK.acquire(blocking=False):
        _LOADING.wait()
        return

    try:
        _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID)
        _MODEL = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            device_map=None,
            low_cpu_mem_usage=True,
            torch_dtype=torch.float32,
        )
        _MODEL.eval()
    finally:
        _LOADING.set()
        _LOAD_LOCK.release()


def _cache_key(user_id: str, user_text: str, tier: str) -> str:
    return f"{user_id}::{user_text.lower().strip()}::{tier}"

def _cache_get(key: str) -> dict | None:
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    return None

def _cache_set(key: str, val: dict):
    with _CACHE_LOCK:
        _CACHE[key] = val
        _CACHE.move_to_end(key)
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)


def _get_history(user_id: str) -> list[dict]:
    with _HISTORY_LOCK:
        return list(_HISTORY.get(user_id, []))

def _add_to_history(user_id: str, entry: dict):
    with _HISTORY_LOCK:
        if user_id not in _HISTORY:
            _HISTORY[user_id] = []
        _HISTORY[user_id].append(entry)
        if len(_HISTORY[user_id]) > _HISTORY_MAX:
            _HISTORY[user_id] = _HISTORY[user_id][-_HISTORY_MAX:]

def _clear_history(user_id: str):
    with _HISTORY_LOCK:
        _HISTORY.pop(user_id, None)


_DEVICE_INFO: dict | None = None
_DEVICE_LOCK = threading.Lock()

def _get_device_context() -> str:
    """Get formatted device information for the system prompt."""
    global _DEVICE_INFO
    if _DEVICE_INFO is None:
        with _DEVICE_LOCK:
            if _DEVICE_INFO is None:
                try:
                    from device_scanner import scan_device
                    _DEVICE_INFO = scan_device("local")
                except:
                    _DEVICE_INFO = {}
        # Merge device data into profile
        if _DEVICE_INFO:
            try:
                from user_profile import load_profile, save_profile, merge_device_data
                p = load_profile("local")
                merge_device_data(p, _DEVICE_INFO)
                save_profile("local", p)
            except:
                pass
    return ""

def _get_profile_summary(user_id: str) -> str:
    try:
        from user_profile import generate_summary
        return generate_summary(user_id)
    except:
        return ""


def _build_prompt(user_text: str, context: str, history: list[dict] | None = None, user_id: str = "local") -> str:
    system = "You are Jason, a helpful AI assistant. You give concise, accurate answers. Never be rude or sarcastic."
    if context:
        system += f"\n\nRelevant notes:\n{context}"
    _get_device_context()
    profile = _get_profile_summary(user_id)
    if profile:
        system += f"\n\n{profile}"
    messages = [{"role": "system", "content": system}]
    # Add conversation history
    if history:
        for h in history:
            messages.append(h)
    messages.append({"role": "user", "content": user_text})
    return _TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


import re
from datetime import datetime, timedelta

def _eval_math(expr: str) -> str:
    try:
        import operator
        ops = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
        expr = expr.strip()
        for op_sym in ops:
            if op_sym in expr:
                parts = expr.split(op_sym)
                if len(parts) == 2:
                    a, b = float(parts[0].strip()), float(parts[1].strip())
                    result = ops[op_sym](a, b)
                    return str(int(result) if result == int(result) else result)
    except:
        pass
    return "I'm a language model, not a calculator."

_FAST_REPLIES = {
    r"^(hey|hello|hi|yo|sup|howdy|good morning|good evening)([^a-z]|$)": "Oh great, another human who expects me to read their mind. What is it?",
    r"^(how are you|how r u|how are you doing|what's up|wassup)([^a-z]|$)": "Living the dream, one terrible query at a time.",
    r"^(who are you|what are you)([^a-z]|$)": "I'm Jason. Your sarcastic digital shadow. Try to keep up.",
    r"^(what can you do|what do you do|help)([^a-z]|$)": "I can answer questions, remember your notes, and be sarcastic about both. Multi-talented, I know.",
    r"^(do you know how to count|can you count)([^a-z]|$)": "Wow, a true intellectual challenge. Yes, I've mastered the ancient art of counting. What's next, tying my shoes?",
    r"^(what.?2\+2|what.?two.plus.two|2\+2)([^a-z]|$)": "4. Try not to spend it all in one place.",
    r"^(?:what\s*(?:is|are|'s|s)\s*)?(\d+\s*[\+\-\*\/]\s*\d+)\s*[?.!]*$": lambda m: _eval_math(m.group(1)),
    r"^(thank you|thanks|ty)([^a-z]|$)": "Don't mention it. Seriously, don't. It'll go to my head.",
    r"^(goodbye|bye|see you|later|gotta go)([^a-z]|$)": "Finally, some peace and quiet. Don't let the door hit you.",
}


_REMINDER_PATTERNS = [
    (r"remind me to (.+?)(?: (tomorrow|next week|next month|on \w+ \d+))?$", 1),
    (r"remind me that (.+?)(?: (tomorrow|next week|next month))?$", 1),
    (r"don.*t forget to (.+?)(?: (tomorrow|next week))?$", 1),
    (r"(?:i need to|i have to|i must) (.+?)(?: (tomorrow|next week|next month|on \w+ \d+))?$", 1),
    (r"remember that (.+?)$", 1),
    (r"set.*reminder.*for (.+?)(?: (tomorrow|next week|next month|on \w+ \d+))?$", 1),
]

_DATE_MAP = {
    "tomorrow": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
    "next week": (datetime.now() + timedelta(weeks=1)).strftime("%Y-%m-%d"),
    "next month": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
}


def _detect_reminder(text: str) -> dict | None:
    lower = text.lower().strip()
    for pat, group in _REMINDER_PATTERNS:
        m = re.search(pat, lower)
        if m:
            title = m.group(1).strip().rstrip(".,!?").capitalize()
            date_str = m.group(2).strip() if m.lastindex and m.group(2) else ""
            due = _DATE_MAP.get(date_str, "")
            return {"title": title, "due_date": due, "description": text}
    return None


_TASK_TRIGGERS = [
    "book", "plan", "organize", "arrange", "find me", "help me", "i want to",
    "could you", "can you", "i need to", "create a", "make a", "set up",
    "research", "compare", "look for", "search for", "find the best",
]


def _is_complex_task(text: str) -> bool:
    lower = text.lower().strip()
    # Check if it's a short query first
    if len(lower.split()) < 4:
        return False
    for trigger in _TASK_TRIGGERS:
        if trigger in lower:
            return True
    return False


def generate_response(user_id: str, user_text: str, tier: str = "free") -> dict:
    from backend.rag_engine import query_context, has_documents
    from backend.actions import detect_action, execute_action, _ACTION_LABELS
    from backend.orchestrator import start_task

    text = user_text.strip().lower()

    # Detect reminder intent
    reminder = _detect_reminder(user_text)

    # Complex task detection — route to orchestrator
    if _is_complex_task(user_text):
        result = start_task(user_id, user_text)
        return {"text": result.get("text") or result.get("question", ""), "task": result, "reminder": reminder}

    # Action path: check for cross-app commands
    action = detect_action(user_text)
    if action:
        result = execute_action(action, user_text)
        label = _ACTION_LABELS.get(action, "")
        return {"text": f"{label}\n{result}", "action": action, "reminder": reminder}

    # Fast path: pattern-matched replies
    for pattern, reply in _FAST_REPLIES.items():
        m = re.search(pattern, text)
        if m:
            result = reply(m) if callable(reply) else reply
            return {"text": result, "reminder": reminder}

    # Slow path: LLM for complex queries
    cache_key = _cache_key(user_id, user_text, tier)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    context = ""
    if tier == "premium" and has_documents(user_id):
        chunks = query_context(user_id, user_text, top_k=3)
        if chunks:
            context = "\n---\n".join(chunks)

    _load()
    history = _get_history(user_id)
    prompt = _build_prompt(user_text, context, history, user_id)
    inputs = _TOKENIZER(prompt, return_tensors="pt")
    word_count = len(user_text.split())
    max_new_tokens = 96 if word_count > 8 else 64
    with torch.no_grad():
        out = _MODEL.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.5,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=_TOKENIZER.eos_token_id,
        )
    reply = _TOKENIZER.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    result = {"text": reply or "I don't have an answer for that.", "reminder": reminder}

    # Store in history
    _add_to_history(user_id, {"role": "user", "content": user_text})
    _add_to_history(user_id, {"role": "assistant", "content": reply})

    # Update user profile in background
    try:
        from user_profile import load_profile, save_profile, update_from_conversation
        p = load_profile(user_id)
        update_from_conversation(p, user_text, reply)
        save_profile(user_id, p)
    except:
        pass

    _cache_set(cache_key, result)
    return result
