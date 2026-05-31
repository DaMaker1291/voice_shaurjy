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


def generate_response(user_id: str, user_text: str, tier: str = "free") -> str:
    from backend.rag_engine import query_context, has_documents

    text = user_text.strip().lower()

    # Fast path: pattern-matched replies
    for pattern, reply in _FAST_REPLIES.items():
        if re.search(pattern, text):
            return reply

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
    return reply or "Got nothing."
