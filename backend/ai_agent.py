"""Groq-powered AI agent — replaces local LLM with ultra-fast Groq API. Sassy, instant, no 2GB RAM used."""

from groq_agent import generate, generate_plan, clear_history, get_history

# Kept for backward compatibility with existing code
_MODEL = "groq"
_TOKENIZER = None
MODEL_ID = "groq-llama3-70b"

def _load():
    """No-op — Groq has no model to load."""
    pass

def generate_response(user_id: str, user_text: str, tier: str = "free") -> dict:
    from backend.actions import detect_action, execute_action, _ACTION_LABELS
    from backend.orchestrator import start_task
    from backend.rag_engine import query_context, has_documents

    text = user_text.strip().lower()

    # Fast action path: check for cross-app commands
    action = detect_action(user_text)
    if action:
        result = execute_action(action, user_text)
        label = _ACTION_LABELS.get(action, "")
        return {"text": f"{label}\n{result}", "action": action}

    # Complex task detection — route to orchestrator
    triggers = ["book", "plan", "organize", "arrange", "find me", "help me",
                "i want to", "could you", "can you", "i need to", "create a",
                "make a", "set up", "research", "compare", "look for", "search for"]
    words = text.split()
    is_complex = len(words) >= 4 and any(t in text for t in triggers)
    if is_complex:
        result = start_task(user_id, user_text)
        return {"text": result.get("text") or result.get("question", ""), "task": result}

    # Groq for everything else
    reply = generate(user_text, user_id)
    return {"text": reply}
