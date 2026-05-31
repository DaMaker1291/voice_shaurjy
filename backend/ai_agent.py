"""Local LLM — Qwen2.5-0.5B-Instruct (2 GB RAM, fast CPU inference)."""

import threading
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

_MODEL = None
_TOKENIZER = None
_LOADING = threading.Event()
_LOAD_LOCK = threading.Lock()
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

FEW_SHOT = """User: hey
Jason: Oh great, another human who expects me to read their mind. What is it?

User: do you know how to count?
Jason: Wow, a true intellectual challenge. Yes, I've mastered the ancient art of counting. What's next, tying my shoes?

User: how are you?
Jason: Living the dream, one terrible query at a time.

User: what's 2+2?
Jason: 4. Try not to spend it all in one place."""


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


def _build_prompt(user_text: str, context: str) -> str:
    notes = f"\n\nNotes:\n{context}\n" if context else ""
    return f"{FEW_SHOT}\n{notes}User: {user_text}\nJason:"


import re
from datetime import datetime, timedelta

_FAST_REPLIES = {
    r"^(hey|hello|hi|yo|sup|howdy|good morning|good evening)([^a-z]|$)": "Oh great, another human who expects me to read their mind. What is it?",
    r"^(how are you|how r u|how are you doing|what's up|wassup)([^a-z]|$)": "Living the dream, one terrible query at a time.",
    r"^(who are you|what are you)([^a-z]|$)": "I'm Jason. Your sarcastic digital shadow. Try to keep up.",
    r"^(what can you do|what do you do|help)([^a-z]|$)": "I can answer questions, remember your notes, and be sarcastic about both. Multi-talented, I know.",
    r"^(do you know how to count|can you count)([^a-z]|$)": "Wow, a true intellectual challenge. Yes, I've mastered the ancient art of counting. What's next, tying my shoes?",
    r"^(what.?2\+2|what.?two.plus.two|2\+2)([^a-z]|$)": "4. Try not to spend it all in one place.",
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


def generate_response(user_id: str, user_text: str, tier: str = "free") -> dict:
    from backend.rag_engine import query_context, has_documents
    from backend.actions import detect_action, execute_action, _ACTION_LABELS

    text = user_text.strip().lower()

    # Detect reminder intent
    reminder = _detect_reminder(user_text)

    # Action path: check for cross-app commands
    action = detect_action(user_text)
    if action:
        result = execute_action(action, user_text)
        label = _ACTION_LABELS.get(action, "")
        return {"text": f"{label}\n{result}", "action": action, "reminder": reminder}

    # Fast path: pattern-matched replies
    for pattern, reply in _FAST_REPLIES.items():
        if re.search(pattern, text):
            return {"text": reply, "reminder": reminder}

    # Slow path: LLM for complex queries
    context = ""
    if tier == "premium" and has_documents(user_id):
        chunks = query_context(user_id, user_text, top_k=3)
        if chunks:
            context = "\n---\n".join(chunks)

    _load()
    prompt = _build_prompt(user_text, context)
    inputs = _TOKENIZER(prompt, return_tensors="pt")
    with torch.no_grad():
        out = _MODEL.generate(
            **inputs,
            max_new_tokens=64,
            temperature=0.9,
            top_p=0.92,
            do_sample=True,
            repetition_penalty=1.1,
            pad_token_id=_TOKENIZER.eos_token_id,
        )
    reply = _TOKENIZER.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    reply = reply.split("\n")[0].strip()
    return {"text": reply or "Got nothing.", "reminder": reminder}
