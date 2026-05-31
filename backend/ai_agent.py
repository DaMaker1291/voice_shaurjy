"""Local LLM — Qwen2.5-0.5B-Instruct (2 GB RAM, fast CPU inference)."""

import threading
from collections import OrderedDict
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

_MODEL = None
_TOKENIZER = None
_LOADING = threading.Event()
_LOAD_LOCK = threading.Lock()
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

# Response cache: LRU with max 64 entries
_CACHE = OrderedDict()
_CACHE_MAX = 64
_CACHE_LOCK = threading.Lock()

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
        # Dynamic quantization: 2-3x speedup on CPU, no C++ compiler needed
        _MODEL = torch.quantization.quantize_dynamic(
            _MODEL, {torch.nn.Linear}, dtype=torch.qint8
        )
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


def _build_prompt(user_text: str, context: str) -> str:
    notes = f"\n\nNotes:\n{context}\n" if context else ""
    return f"{FEW_SHOT}\n{notes}User: {user_text}\nJason:"


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
    prompt = _build_prompt(user_text, context)
    inputs = _TOKENIZER(prompt, return_tensors="pt")
    word_count = len(user_text.split())
    max_new_tokens = 64 if word_count > 8 else 48
    with torch.no_grad():
        out = _MODEL.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.3,
            top_p=0.85,
            repetition_penalty=1.15,
            pad_token_id=_TOKENIZER.eos_token_id,
        )
    reply = _TOKENIZER.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    reply = reply.split("\n")[0].strip()
    result = {"text": reply or "Got nothing.", "reminder": reminder}
    _cache_set(cache_key, result)
    return result
