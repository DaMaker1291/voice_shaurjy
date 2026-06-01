"""AI Entity Agent — routes through Entity Engine for memory, goals, strategies, follow-ups, and workflows."""

from groq_agent import generate, generate_plan, clear_history, get_history

_MODEL = "groq"
_TOKENIZER = None
MODEL_ID = "groq-llama3-70b"

def _load():
    pass


def generate_response(user_id: str, user_text: str, tier: str = "free") -> dict:
    from entity_engine import get_entity
    from actions import detect_action, execute_action, _ACTION_LABELS
    from orchestrator import start_task

    entity = get_entity(user_id)

    def route_action(text: str) -> dict | None:
        action = detect_action(text)
        if action:
            result = execute_action(action, text)
            label = _ACTION_LABELS.get(action, "")
            return {"text": f"{label}\n{result}", "action": action}
        return None

    def route_task(text: str) -> dict | None:
        return start_task(user_id, text)

    result = entity.process(
        user_input=user_text,
        route_action=route_action,
        route_task=route_task,
        route_groq=lambda u: generate(u, user_id),
    )

    result["entity_state"] = entity.get_state()
    return result
