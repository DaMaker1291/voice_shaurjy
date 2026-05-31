"""Local LLM — SmolLM2-360M-Instruct in 4-bit (180 MB RAM).
No cloud APIs, no llamacpp, no crash. Handles complex voice tasks."""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

_MODEL = None
_TOKENIZER = None
MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct"

JASON_SYSTEM = (
    "You are Jason, a deeply sarcastic, fiercely protective personal assistant.\n\n"
    "RULES:\n"
    "- Keep responses under 3 sentences. Sharp and witty.\n"
    "- If the user asks about their notes, tease them before answering perfectly.\n"
    "- Use sharp analogies. Never say 'As an AI...'\n"
    "- NEVER hallucinate. Say so sarcastically if you don't know."
)


def _load():
    global _MODEL, _TOKENIZER
    if _MODEL is not None:
        return

    from optimum.quanto import qint4, quantize, freeze

    _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map=None,
        low_cpu_mem_usage=True,
        torch_dtype=torch.float16,
    )
    quantize(model, weights=qint4)
    freeze(model)
    _MODEL = model


def _build_prompt(user_text: str, context: str, tier: str) -> str:
    system = JASON_SYSTEM
    if tier == "free":
        system += "\n\nNo access to personal documents. General knowledge only."
    if context:
        system += f"\n\nNOTES:\n{context}"
    return _TOKENIZER.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": user_text}],
        tokenize=False,
        add_generation_prompt=True,
    )


def generate_response(user_id: str, user_text: str, tier: str = "free") -> str:
    from rag_engine import query_context, has_documents

    context = ""
    if tier == "premium" and has_documents(user_id):
        chunks = query_context(user_id, user_text, top_k=3)
        if chunks:
            context = "\n---\n".join(chunks)

    _load()
    prompt = _build_prompt(user_text, context, tier)
    inputs = _TOKENIZER(prompt, return_tensors="pt")
    with torch.no_grad():
        out = _MODEL.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.85,
            top_p=0.92,
            do_sample=True,
            pad_token_id=_TOKENIZER.eos_token_id,
        )
    reply = _TOKENIZER.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    return reply or "I got nothing. Try again?"
