"""Autonomous task agent — plans & executes ANY complex task, streaming real-time progress + visual scenes."""

import json, re, time, threading
from hyperlocal_ai import get_hyperlocal
from actions import detect_action, execute_action, _EXECUTORS

_TASK_CATEGORIES = {
    "travel":    ["holiday","vacation","trip","travel","flight","destination","tour","visit","journey","cruise","road trip"],
    "document":  ["essay","document","word","report","write","type","draft","compose","paper","article","letter","memo","thesis"],
    "network":   ["network","scan","router","wifi","device","port","share","server","topology","infrastructure"],
    "system":    ["install","setup","configure","settings","change","update","optimize","clean","backup","defrag"],
    "research":  ["research","find","search","look up","investigate","study","learn about","analyze"],
    "media":     ["playlist","music","video","movie","edit","create","record","stream"],
    "file":      ["file","folder","organize","sort","archive","compress","extract","backup","sync"],
}


def _categorize(task: str) -> str:
    lower = task.lower()
    for cat, kws in _TASK_CATEGORIES.items():
        for kw in kws:
            if kw in lower: return cat
    return "system"


def _plan_task(task: str) -> list[dict]:
    """Break a task into steps using Groq. Returns list of {step, action, params}."""
    prompt = f"""Break this task into 3-8 concrete steps I can execute on Windows.
Task: {task}

For each step, specify:
- step: short description (1 sentence)
- action: one of [{','.join(sorted(_EXECUTORS.keys())[:80])}] or "type_keys", "open_url", "search_google", "click", "wait", "none"
- params: parameters for the action (or empty string)

Output ONLY valid JSON array. No other text. Example:
[{{"step":"Opening Word","action":"run_dialog","params":"winword"}},{{"step":"Typing content","action":"type_keys","params":"Hello world"}}]"""
    raw = get_hyperlocal("task")._generator.generate(prompt + " _RESPOND_ONLY_JSON_ARRAY", max_tokens=300)
    raw = raw.strip()
    # Extract JSON array
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        try:
            steps = json.loads(m.group())
            return steps if isinstance(steps, list) else []
        except: pass
    return [{"step": f"Executing: {task}", "action": "none", "params": task}]


def _extract_scene_params(task: str, steps: list) -> dict:
    """Extract rich scene parameters from the task for visual simulation."""
    lower = task.lower()
    cat = _categorize(task)
    scene = {"type": cat, "title": task, "progress": 0, "subtitle": "", "details": {}}

    if cat == "travel":
        # Extract origin/destination from task
        words = lower.split()
        destinations = []
        for w in words:
            if w[0].isupper() and len(w) > 2 and w not in ["The","My","I","A","An","In","On","At","To","For","With","By"]:
                if words.index(w) > 0:
                    destinations.append(w)
        scene["details"] = {
            "origin": "Your Location",
            "destinations": destinations[:5] or ["Destination"],
            "flight_paths": [[i*0.2, (i+1)*0.2] for i in range(len(destinations) or 1)],
        }
    elif cat == "document":
        # Extract topic from task
        topic = task
        for prefix in ["write","type","draft","compose","create"]:
            if task.lower().startswith(prefix):
                topic = task[len(prefix):].strip().lstrip("a an the ").strip()
                break
        scene["details"] = {
            "title": topic or "Document",
            "word_count": max(200, len(topic) * 5),
            "has_formatting": True,
            "has_sources": True,
        }
    elif cat == "network":
        scene["details"] = {
            "devices": 5,
            "connections": 8,
            "status": "scanning",
        }
    elif cat == "system":
        scene["details"] = {"action": "configuring", "target": task}
    elif cat == "research":
        scene["details"] = {"query": task, "sources": 5}
    elif cat == "media":
        scene["details"] = {"type": "playlist", "count": 10}
    elif cat == "file":
        scene["details"] = {"action": "organizing", "files": 20}
    return scene


def execute_task(task: str):
    """Execute a complex task, yielding progress updates for SSE streaming + visual simulation."""
    steps = _plan_task(task)
    scene = _extract_scene_params(task, steps)
    total = len(steps)

    yield {"type": "scene_init", "scene": scene}
    yield {"type": "plan", "steps": [s["step"] for s in steps]}
    yield {"type": "status", "text": f"Planning {total} steps...", "progress": 0}

    for i, step in enumerate(steps):
        step_name = step.get("step", f"Step {i+1}")
        action = step.get("action", "none")
        params = step.get("params", "")

        # Update scene progress
        scene["progress"] = int((i / total) * 100)
        scene["subtitle"] = step_name
        yield {"type": "scene_update", "scene": scene}
        yield {"type": "status", "text": f"[{i+1}/{total}] {step_name}", "progress": int((i / total) * 100)}

        # Execute the action
        if action in _EXECUTORS:
            result = execute_action(action, params)
            yield {"type": "result", "step": step_name, "result": result}
        elif action == "type_keys":
            from actions import _ps
            _ps(f'$k=(New-Object -ComObject WScript.Shell); Start-Sleep 0.5; $k.SendKeys("{params[:200]}")')
            yield {"type": "result", "step": step_name, "result": "Typed."}
        elif action == "open_url":
            from actions import _ps
            _ps(f'Start-Process "{params}"')
            yield {"type": "result", "step": step_name, "result": f"Opened {params}."}
        elif action == "search_google":
            from urllib.parse import quote
            from actions import _ps
            _ps(f'Start-Process "https://google.com/search?q={quote(params)}"')
            yield {"type": "result", "step": step_name, "result": f"Searched {params}."}
        elif action == "click":
            from actions import _ps
            _ps(f'$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("{{ENTER}}")')
            yield {"type": "result", "step": step_name, "result": "Clicked."}
        elif action == "wait":
            time.sleep(1)
            yield {"type": "result", "step": step_name, "result": "Waiting..."}
        else:
            # Try Groq for freeform generation
            if params and len(params) > 5:
                reply = get_hyperlocal("task")._generator.generate(f"Execute this step concisely: {step_name}. Context: {params}", max_tokens=200)
                yield {"type": "result", "step": step_name, "result": reply}
            else:
                yield {"type": "result", "step": step_name, "result": "Done."}

        time.sleep(0.3)  # Small delay so simulation is visible

    scene["progress"] = 100
    scene["subtitle"] = "Complete!"
    yield {"type": "scene_update", "scene": scene}
    yield {"type": "complete", "text": "All steps finished."}
