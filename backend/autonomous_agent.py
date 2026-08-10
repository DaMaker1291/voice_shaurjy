"""Autonomous AI agent — plans & executes ANY complex multi-step task with adaptive re-planning."""

import json
import re
import time
import threading
from hyperlocal_ai import get_hyperlocal
from actions import execute_action, cloud_safe_execute, _EXECUTORS

_ACTIVE_TASKS: dict[str, dict] = {}


def start_autonomous_task(user_id: str, goal: str) -> dict:
    session_id = f"{user_id}_{int(time.time())}"
    plan = _generate_plan(goal)
    if not plan:
        return {"error": "Could not generate plan"}
    _ACTIVE_TASKS[session_id] = {
        "user_id": user_id,
        "goal": goal,
        "plan": plan,
        "step_index": 0,
        "results": [],
        "collected_data": {},
        "started_at": time.time(),
        "status": "running",
    }
    return {
        "session_id": session_id,
        "task": goal,
        "steps": plan,
        "total_steps": len(plan),
    }


def continue_autonomous_task(session_id: str, user_input: str = None) -> dict:
    session = _ACTIVE_TASKS.get(session_id)
    if not session:
        return {"error": "No active task"}
    if session["status"] != "running":
        return {"error": f"Task already {session['status']}"}
    if user_input:
        session["last_user_input"] = user_input
    return _execute_next_step(session_id)


def _generate_plan(goal: str) -> list[dict]:
    action_names = sorted(_EXECUTORS.keys())
    action_sample = action_names[:120]

    prompt = f"""You are an autonomous AI agent. Break this goal into 2-8 concrete steps.

Goal: {goal}

Output a JSON array of steps. Each step has:
- "step": short description
- "action": one of: search_web, scrape_url, groq, open_url, run_shell, run_python, read_file, write_file, list_dir, take_screenshot, speak, notify, wait, ask_user, present, or any of these: {','.join(action_sample)}
- "params": parameters for the action (string)
- "requires": optional — data key from previous steps that this step needs

For "search_web": params is the search query
For "scrape_url": params is the URL to fetch
For "groq": params is the prompt for the LLM
For "run_shell": params is the shell command
For "run_python": params is Python code
For "read_file": params is the file path
For "write_file": params has format "path::content"
For "list_dir": params is the directory path
For "take_screenshot": params is "" (empty)
For "ask_user": params is the question to ask
For "open_url": params is the URL

Output ONLY valid JSON array. No other text.

Example:
[{{"step":"Search for information","action":"search_web","params":"latest AI news 2026"}},{{"step":"Read top result","action":"scrape_url","params":"{{search_result_1_url}}","requires":"search_result_1_url"}},{{"step":"Summarize","action":"groq","params":"Summarize this article in 3 bullet points:\\n{{scrape_result_0}}"}},{{"step":"Save report","action":"write_file","params":"~/Desktop/ai_report.md::{{groq_result_2}}"}},{{"step":"Notify user","action":"notify","params":"Report saved to Desktop!"}},{{"step":"Present result","action":"present","params":"Done! I saved a report to your Desktop."}}]"""

    # PRIMARY: Groq cloud API
    try:
        import os
        api_key = os.getenv("GROQ_API_KEY") or ""
        if api_key and api_key != "your_groq_api_key_here":
            import groq
            client = groq.Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an autonomous AI agent. Output ONLY valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
            steps = _extract_json_array(raw)
            if steps:
                return steps
    except Exception as e:
        logger.debug(f"[AutonomousAgent] Groq plan failed: {e}")

    # FALLBACK: HyperLocal AI
    try:
        raw = get_hyperlocal("autonomous")._generator.generate(prompt, max_tokens=500, temperature=0.3)
        steps = _extract_json_array(raw)
        if steps:
            return steps
    except Exception:
        pass

    return [{"step": f"Executing: {goal}", "action": "groq", "params": goal}]


def _execute_next_step(session_id: str) -> dict:
    session = _ACTIVE_TASKS[session_id]
    plan = session["plan"]
    idx = session["step_index"]
    collected = session["collected_data"]
    results = session["results"]

    if idx >= len(plan):
        session["status"] = "complete"
        return _finalize(session_id)

    step = plan[idx]
    action = step.get("action", "groq")
    params = step.get("params", "")
    requires = step.get("requires")

    # Resolve dependent data
    if requires:
        for key, val in list(collected.items())[::-1]:
            if requires in key or key in requires:
                params = params.replace("{{" + requires + "}}", str(val)[:2000])
                break

    # Also resolve any {{key}} patterns
    for key, val in collected.items():
        placeholder = "{{" + key + "}}"
        if placeholder in params:
            params = params.replace(placeholder, str(val)[:2000])

    session["current_step"] = step["step"]

    result = _execute_action(action, params, session["user_id"])
    key = f"{action}_{idx}"
    collected[key] = str(result)[:2000]

    result_entry = {"step": step["step"], "action": action, "result": str(result)[:500]}
    results.append(result_entry)

    session["step_index"] = idx + 1
    session["last_result"] = result_entry

    if action == "ask_user":
        return {
            "type": "ask", "question": params,
            "session_id": session_id,
            "step": step["step"],
            "step_index": idx,
            "total": len(plan),
        }

    # Auto-advance to next step
    return continue_autonomous_task(session_id)


def _execute_action(action: str, params: str, user_id: str) -> str:
    try:
        if action == "search_web":
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                r = list(ddgs.text(params, max_results=5))
            if r:
                collected = []
                for item in r:
                    collected.append(f"{item['title']}\n  {item['body'][:200]}\n  {item['href']}")
                return "Search results:\n" + "\n\n".join(collected)
            return "No results found."

        elif action == "scrape_url":
            import urllib.request
            try:
                with urllib.request.urlopen(params, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                import re as _re
                text = _re.sub(r"<[^>]+>", " ", html)
                text = _re.sub(r"\s+", " ", text).strip()
                return text[:3000]
            except Exception as e:
                return f"Scrape error: {e}"

        elif action == "groq":
            return get_hyperlocal("autonomous")._generator.generate(params, max_tokens=300)

        elif action == "run_shell":
            from execution_vault import vaulted_run
            vr = vaulted_run(params, timeout=30)
            if vr.blocked:
                return f"BLOCKED: {vr.block_reason}"
            return (vr.stdout or vr.stderr or f"exit {vr.exit_code}")[:2000]
        
        elif action == "run_python":
            from execution_vault import vaulted_python
            vr = vaulted_python(params, timeout=30)
            if vr.blocked:
                return f"BLOCKED: {vr.block_reason}"
            return (vr.stdout or vr.stderr or "ok")[:2000]

        elif action == "present":
            return params

        elif action == "wait":
            seconds = max(1, min(30, int(params) if params.isdigit() else 2))
            time.sleep(seconds)
            return f"Waited {seconds}s"

        elif action == "notify":
            return f"Notification: {params}"

        elif action in ("read_file", "write_file", "list_dir", "take_screenshot", "run_shell_local", "run_python_local"):
            return cloud_safe_execute(action, params, user_id=user_id)

        elif action in _EXECUTORS:
            return cloud_safe_execute(action, params, user_id=user_id)

        return cloud_safe_execute("groq", params, user_id=user_id)

    except Exception as e:
        return f"Error: {e}"


def _extract_json_array(text: str) -> list | None:
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except:
            pass
    return None


def _finalize(session_id: str) -> dict:
    session = _ACTIVE_TASKS.get(session_id, {})
    results = session.get("results", [])
    summary = "\n".join(f"  {r['step']}: {r['result'][:100]}" for r in results)
    return {
        "type": "complete",
        "session_id": session_id,
        "summary": f"Task complete! {len(results)} steps executed.\n{summary}",
        "results": results,
    }
