"""AI Entity Agent — routes through Entity Engine for memory, goals, strategies, follow-ups, and autonomous tasks."""

from groq_agent import generate

_MODEL = "groq"
MODEL_ID = "groq-llama3-70b"


def generate_response(user_id: str, user_text: str, tier: str = "free") -> dict:
    from entity_engine import get_entity
    from actions import detect_action, cloud_safe_execute, _ACTION_LABELS

    entity = get_entity(user_id)

    def route_action(text: str) -> dict | None:
        action = detect_action(text)
        if action:
            result = cloud_safe_execute(action, text, user_id=user_id)
            label = _ACTION_LABELS.get(action, "")
            response_text = f"{label}\n{result}" if label else result
            if result.startswith("__RELAY__:"):
                parts = result.split(":", 2)
                relay_id = parts[1] if len(parts) > 1 else ""
                return {"text": response_text, "action": action, "async": True, "relay_id": relay_id}
            if result.startswith("__QR__:"):
                return {"text": "Scan this QR code with your phone to link WhatsApp Web:", "action": action, "qr_image": result[7:]}
            if result.startswith("__SCREENSHOT__:"):
                return {"text": "Screenshot captured:", "action": action, "image": result[15:]}
            return {"text": response_text, "action": action}
        return None

    def route_task(text: str) -> dict | None:
        from autonomous_agent import start_autonomous_task
        result = start_autonomous_task(user_id, text)
        if "error" not in result:
            return {
                "text": f"I've planned {result['total_steps']} steps for this:\n" +
                        "\n".join(f"  {i+1}. {s['step']}" for i, s in enumerate(result["steps"])),
                "autonomous_session": result["session_id"],
                "autonomous_plan": result["steps"],
            }
        return None

    result = entity.process(
        user_input=user_text,
        route_action=route_action,
        route_task=route_task,
        route_groq=lambda u: generate(u, user_id),
    )

    result["entity_state"] = entity.get_state()
    return result
