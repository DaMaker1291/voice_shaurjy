"""AI Task Orchestrator - plans and executes ANY multi-step task via LLM with strategies, follow-ups, and workflows."""

import json
import re
import time
from groq_agent import generate as groq_generate

_SESSIONS: dict[str, dict] = {}


def start_task(session_id: str, user_input: str) -> dict:
    from actions import get_all_actions
    all_actions = get_all_actions()
    actions_list = "\n".join(f"  - {k}: {v['tip']}" for k, v in sorted(all_actions.items()) if v['tip'])

    instructions = f"""You are a task planning AI. Break down the user's request into steps.

Available actions you can use:
{actions_list}

For each step, output an action from: ask (for user info), open (URL), search (web search), present (show results),
groq (generate content with LLM), type (type text), run (run command/app), wait (pause),
workflow (AI generates a multi-step workflow for ANY complex sub-task)

Output ONLY valid JSON. No other text.

Examples:
User: book a holiday to Paris
{{"task":"book a holiday to Paris","steps":[{{"id":1,"action":"ask","question":"What dates?","field":"dates"}},{{"id":2,"action":"ask","question":"Budget?","field":"budget"}},{{"id":3,"action":"open","url":"https://google.com/travel","note":"Search flights"}},{{"id":4,"action":"present","note":"Here is your plan"}}],"follow_up_question":"What dates?"}}

User: do my homework in onenote
{{"task":"Homework in OneNote","steps":[{{"id":1,"action":"workflow","note":"AI will generate steps for this"}}],"follow_up_question":"Starting workflow..."}}"""

    reply = groq_generate(f"{instructions}\n\nUser: {user_input}", task_id="__orchestrator__")
    plan = _extract_json(reply)

    if not plan or "steps" not in plan:
        return {"type": "error", "text": "I couldn't plan that task. Try being more specific."}

    _SESSIONS[session_id] = {
        "plan": plan, "step_index": 0, "collected": {},
        "task": plan.get("task", user_input),
        "workflow_execution_id": None,
    }
    return _process_current_step(session_id)


def continue_task(session_id: str, user_response: str) -> dict:
    session = _SESSIONS.get(session_id)
    if not session:
        return {"type": "error", "text": "No active task. Start a new one."}

    steps = session["plan"]["steps"]
    idx = session["step_index"]

    if idx > 0:
        prev = steps[idx - 1]
        field = prev.get("field")
        if field:
            session["collected"][field] = user_response

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
        question = step.get("question", "")
        for k, v in collected.items():
            question = question.replace("{" + k + "}", v)
        return {
            "type": "ask", "question": question, "field": step.get("field"),
            "step": idx + 1, "total": len(steps), "task": session["task"],
            "session_id": session_id,
        }

    elif action == "open":
        url = step.get("url", "")
        for k, v in collected.items():
            url = url.replace("{" + k + "}", v.replace(" ", "+"))
        note = step.get("note", "")
        _open_url(url)
        return {
            "type": "notify", "text": f"Opened: {note}",
            "step": idx + 1, "total": len(steps), "task": session["task"],
        }

    elif action == "search":
        query = step.get("query", step.get("note", ""))
        for k, v in collected.items():
            query = query.replace("{" + k + "}", v)
        _open_search(query)
        return {
            "type": "notify", "text": f"Searched: {query}",
            "step": idx + 1, "total": len(steps), "task": session["task"],
        }

    elif action == "groq":
        prompt_template = step.get("prompt", step.get("note", ""))
        for k, v in collected.items():
            prompt_template = prompt_template.replace("{" + k + "}", v)
        result = groq_generate(prompt_template, task_id="__step__")
        return {
            "type": "notify", "text": result,
            "step": idx + 1, "total": len(steps), "task": session["task"],
        }

    elif action == "type":
        text = step.get("text", step.get("note", ""))
        for k, v in collected.items():
            text = text.replace("{" + k + "}", v)
        _type_text(text)
        return {
            "type": "notify", "text": f"Typed: {text[:50]}...",
            "step": idx + 1, "total": len(steps), "task": session["task"],
        }

    elif action == "run":
        cmd = step.get("command", step.get("note", ""))
        for k, v in collected.items():
            cmd = cmd.replace("{" + k + "}", v)
        _run_command(cmd)
        return {
            "type": "notify", "text": f"Ran: {cmd}",
            "step": idx + 1, "total": len(steps), "task": session["task"],
        }

    elif action == "workflow":
        from workflow_engine import get_engine
        from entity_engine import get_entity
        engine = get_engine()
        wf_input = step.get("note", session["task"])
        entity = get_entity(session_id)
        context = {
            "active_goals": entity.memory.get_active_goals(),
            "memory_summary": entity.memory.get_summary(),
            **collected,
            "query": session["task"],
        }
        execution = engine.create_workflow(wf_input, context)
        session["workflow_execution_id"] = execution.execution_id
        result = engine.advance(execution.execution_id, action_executor=_exec_action)
        return {
            "type": "workflow", "text": f"AI generated workflow: {execution.workflow.name} ({len(execution.workflow.steps)} steps)",
            "execution_id": execution.execution_id,
            "step": idx + 1, "total": len(steps), "task": session["task"],
            "workflow_result": result,
        }

    elif action == "present":
        return _finalize_task(session_id)

    else:
        result = _exec_action(action, str(step))
        return {
            "type": "notify", "text": str(result)[:200],
            "step": idx + 1, "total": len(steps), "task": session["task"],
        }


def _exec_action(action: str, params: str = "") -> str:
    try:
        from actions import execute_action, detect_action
        detected = detect_action(action) or action
        return execute_action(detected, params)
    except Exception as e:
        return f"Error: {e}"


def _open_url(url: str):
    import subprocess
    try:
        subprocess.Popen(["powershell", "-Command", f'Start-Process "{url}"'], shell=True)
    except:
        pass


def _open_search(query: str):
    import urllib.parse
    _open_url(f"https://google.com/search?q={urllib.parse.quote(query)}")


def _type_text(text: str):
    try:
        from actions import _ps
        escaped = text[:200].replace('"', '"')
        _ps(f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{escaped}")')
    except:
        pass


def _run_command(cmd: str):
    try:
        from actions import _ps
        _ps(f'Start-Process "{cmd}"')
    except:
        pass


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except:
            pass
    return None


def _finalize_task(session_id: str) -> dict:
    session = _SESSIONS.get(session_id)
    if not session:
        return {"type": "error", "text": "No active task."}

    collected = session["collected"]
    task = session["task"]
    details = "\n".join(f"  - {k}: {v}" for k, v in collected.items())
    summary = f"Task: {task}\n\nCollected Info:\n{details}\n\nAll steps completed."

    session["step_index"] = len(session["plan"]["steps"])

    return {
        "type": "complete", "text": summary,
        "collected": collected, "task": task,
    }


def get_session(session_id: str) -> dict | None:
    return _SESSIONS.get(session_id)


def cancel_task(session_id: str) -> bool:
    return _SESSIONS.pop(session_id, None) is not None

def continue_workflow(session_id: str, execution_id: str, user_input: str = None) -> dict:
    from workflow_engine import get_engine
    engine = get_engine()
    result = engine.advance(execution_id, user_input, action_executor=_exec_action)
    return result