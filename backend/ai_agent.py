"""AI Entity Agent — routes through Entity Engine for memory, goals, strategies, follow-ups, and autonomous tasks."""

def generate_response(user_id: str, user_text: str, tier: str = "free") -> dict:
    from entity_engine import get_entity

    entity = get_entity(user_id)

    result = entity.process(user_input=user_text)

    result["entity_state"] = entity.get_state()
    return result
