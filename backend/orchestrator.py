"""AI Task Orchestrator — plans and executes ANY multi-step task via LLM."""

import json
import re
import backend.ai_agent as llm


_SESSIONS: dict[str, dict] = {}


def _llm_generate(user_input: str, max_tokens: int = 256) -> str:
    """Generate using proper Qwen2.5 chat template."""
    llm._load()
    system = "You are a task planning AI. Break down user requests into steps. Output ONLY valid JSON. No other text."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_input},
    ]
    prompt = llm._TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = llm._TOKENIZER(prompt, return_tensors="pt")
    import torch
    with torch.no_grad():
        out = llm._MODEL.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.3,
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.1,
            pad_token_id=llm._TOKENIZER.eos_token_id,
        )
    reply = llm._TOKENIZER.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    return reply


def _extract_json(text: str) -> dict | None:
    # Try to find JSON block in the output
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def start_task(session_id: str, user_input: str) -> dict:
    # Load available actions so the LLM knows what it can do
    from actions import get_all_actions
    all_actions = get_all_actions()
    actions_list = "\n".join(f"  - {k}: {v['tip']}" for k, v in sorted(all_actions.items()) if v['tip'])

    instructions = f"""You are a task planning AI. Break down the user's request into steps.

Available actions you can use:
{actions_list}

For each step, output an action from the list above, or use: ask (for user info), open (URL), search (web search), present (show results).

Output ONLY valid JSON. No other text.

Examples:
User: book a holiday to Paris
{{"task":"book a holiday to Paris","steps":[{{"id":1,"action":"ask","question":"What dates?","field":"dates"}},{{"id":2,"action":"ask","question":"Budget?","field":"budget"}},{{"id":3,"action":"open","url":"https://google.com/travel","note":"Flights"}},{{"id":4,"action":"present","note":"Plan"}}],"follow_up_question":"What dates?"}}"""
    reply = _llm_generate(f"{instructions}\n\nUser: {user_input}", max_tokens=300)
    plan = _extract_json(reply)

    if not plan or "steps" not in plan:
        return {
            "type": "error",
            "text": "I couldn't plan that task. Try being more specific.",
        }

    # Store session
    _SESSIONS[session_id] = {
        "plan": plan,
        "step_index": 0,
        "collected": {},
        "task": plan.get("task", user_input),
    }

    return _process_current_step(session_id)


def continue_task(session_id: str, user_response: str) -> dict:
    session = _SESSIONS.get(session_id)
    if not session:
        return {"type": "error", "text": "No active task. Start a new one."}

    steps = session["plan"]["steps"]
    idx = session["step_index"]

    # Store the response for the previous step
    if idx > 0:
        prev = steps[idx - 1]
        field = prev.get("field")
        if field:
            session["collected"][field] = user_response

    # Move to next step
    session["step_index"] = idx + 1
    return _process_current_step(session_id)


def _process_current_step(session_id: str) -> dict:
    session = _SESSIONS[session_id]
    steps = session["plan"]["steps"]
    idx = session["step_index"]

    if idx >= len(steps):
        return _finalize_task(session_id)

    step = steps[idx]
    action = step.get("action")
    collected = session["collected"]

    if action == "ask":
        # Fill in template variables from collected data
        question = step.get("question", "")
        for k, v in collected.items():
            question = question.replace("{" + k + "}", v)
        return {
            "type": "ask",
            "question": question,
            "field": step.get("field"),
            "step": idx + 1,
            "total": len(steps),
            "task": session["task"],
        }

    elif action == "open":
        url = step.get("url", "")
        for k, v in collected.items():
            url = url.replace("{" + k + "}", v.replace(" ", "+"))
        note = step.get("note", "")
        _open_url(url)
        return {
            "type": "notify",
            "text": f"Opened: {note}",
            "step": idx + 1,
            "total": len(steps),
            "task": session["task"],
            "next_action": _process_current_step(session_id)["type"] == "ask",
        }

    elif action == "search":
        query = step.get("query", "")
        for k, v in collected.items():
            query = query.replace("{" + k + "}", v)
        _open_search(query)
        return {
            "type": "notify",
            "text": f"Searched: {query}",
            "step": idx + 1,
            "total": len(steps),
            "task": session["task"],
        }

    elif action == "present":
        return _finalize_task(session_id)

    else:
        # Try executing as a system action
        try:
            from actions import execute_action, detect_action
            detected = detect_action(action) or action
            result = execute_action(detected, action)
            return {
                "type": "notify",
                "text": result,
                "step": idx + 1,
                "total": len(steps),
                "task": session["task"],
            }
        except Exception:
            return {"type": "notify", "text": f"Executing step {idx + 1}...", "step": idx + 1, "total": len(steps), "task": session["task"]}


def _open_urls(urls: list[str]):
    """Open all URLs in a single Edge window (multi-tab)."""
    import subprocess
    if not urls:
        return
    try:
        arglist = ", ".join(f'"{u}"' for u in urls)
        cmd = f"Start-Process msedge -ArgumentList {arglist}"
        subprocess.Popen(["powershell", "-Command", cmd], shell=True)
    except:
        pass


def _open_url(url: str):
    _open_urls([url])


def _open_search(query: str):
    import urllib.parse
    _open_url(f"https://google.com/search?q={urllib.parse.quote(query)}")


def _finalize_task(session_id: str) -> dict:
    session = _SESSIONS.get(session_id)
    if not session:
        return {"type": "error", "text": "No active task."}

    collected = session["collected"]
    plan = session["plan"]
    task = session["task"]

    # Build summary
    details = "\n".join(f"  • {k}: {v}" for k, v in collected.items())
    summary = f"Task: {task}\n\nCollected Info:\n{details}\n\nAll steps completed."

    # Auto-present - open a summary page
    _open_url(f"https://google.com/search?q={__import__('urllib').parse.quote(task + ' ' + ' '.join(collected.values()))}")

    del _SESSIONS[session_id]

    return {
        "type": "complete",
        "text": summary,
        "collected": collected,
        "task": task,
    }


def get_session(session_id: str) -> dict | None:
    return _SESSIONS.get(session_id)


def cancel_task(session_id: str) -> bool:
    return _SESSIONS.pop(session_id, None) is not None
