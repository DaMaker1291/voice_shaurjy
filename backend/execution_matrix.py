"""Execution Matrix — persistent state management with crash recovery for multi-step workflows."""

import json
import os
import time
import threading

_MATRIX_DIR = os.path.join(os.path.dirname(__file__), "..", "execution_state")
_MATRIX_FILE = os.path.join(_MATRIX_DIR, "execution_matrix.json")
_LOCK = threading.Lock()


def _ensure_dir():
    os.makedirs(_MATRIX_DIR, exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if os.path.isfile(_MATRIX_FILE):
        try:
            with open(_MATRIX_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"workflows": [], "active": None, "history": [], "resilience_log": []}


def _save(data: dict):
    _ensure_dir()
    with open(_MATRIX_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_state(workflow_id: str = None) -> dict:
    with _LOCK:
        data = _load()
        if workflow_id:
            for wf in data["workflows"]:
                if wf.get("id") == workflow_id:
                    return wf
            return {}
        return data


def create_workflow(name: str, steps: list[dict], context: dict = None) -> str:
    """Create a new workflow and return its ID."""
    wf_id = f"wf_{int(time.time())}_{name[:10].replace(' ','_')}"
    entry = {
        "id": wf_id,
        "name": name,
        "created_at": time.time(),
        "updated_at": time.time(),
        "status": "initialized",
        "current_step": 0,
        "total_steps": len(steps),
        "steps": steps,
        "results": [],
        "context": context or {},
        "error": None,
    }
    with _LOCK:
        data = _load()
        data["workflows"].append(entry)
        data["active"] = wf_id
        _save(data)
    return wf_id


def update_step(workflow_id: str, step_index: int, status: str, result: str = None):
    """Update a step's status and set it as current position."""
    with _LOCK:
        data = _load()
        for wf in data["workflows"]:
            if wf.get("id") == workflow_id:
                wf["current_step"] = step_index
                wf["updated_at"] = time.time()
                wf["status"] = status
                if result is not None:
                    step_data = {"index": step_index, "status": status, "result": str(result)[:500], "time": time.time()}
                    while len(wf["results"]) <= step_index:
                        wf["results"].append({})
                    wf["results"][step_index] = step_data
                _save(data)
                return True
    return False


def complete_workflow(workflow_id: str, result: str = "Complete"):
    """Mark a workflow as complete."""
    with _LOCK:
        data = _load()
        for wf in data["workflows"]:
            if wf.get("id") == workflow_id:
                wf["status"] = "complete"
                wf["updated_at"] = time.time()
                wf["results"].append({"index": "final", "status": "complete", "result": str(result)[:500], "time": time.time()})
                data["active"] = None
                data["history"].append({"id": workflow_id, "name": wf["name"], "completed_at": time.time()})
                _save(data)
                return True
    return False


def fail_workflow(workflow_id: str, error: str):
    """Mark a workflow as failed with error details."""
    with _LOCK:
        data = _load()
        for wf in data["workflows"]:
            if wf.get("id") == workflow_id:
                wf["status"] = "failed"
                wf["error"] = str(error)[:500]
                wf["updated_at"] = time.time()
                data["active"] = None
                _save(data)
                log_resilience(workflow_id, f"FAILED: {error[:200]}")
                return True
    return False


def resume_failed(workflow_id: str) -> dict | None:
    """Resume a failed workflow. Returns the step state to resume from."""
    with _LOCK:
        data = _load()
        for wf in data["workflows"]:
            if wf.get("id") == workflow_id and wf["status"] in ("failed", "interrupted"):
                wf["status"] = "resumed"
                wf["updated_at"] = time.time()
                data["active"] = workflow_id
                _save(data)
                return {
                    "workflow_id": workflow_id,
                    "name": wf["name"],
                    "resume_from": wf["current_step"],
                    "steps_remaining": wf["total_steps"] - wf["current_step"],
                    "steps": wf["steps"][wf["current_step"]:],
                    "context": wf["context"],
                    "results_so_far": wf["results"],
                }
    return None


def log_resilience(workflow_id: str, event: str):
    """Log a resilience event (crash, interruption, recovery)."""
    with _LOCK:
        data = _load()
        data["resilience_log"].append({
            "time": time.time(),
            "workflow_id": workflow_id,
            "event": str(event)[:300],
        })
        if len(data["resilience_log"]) > 100:
            data["resilience_log"] = data["resilience_log"][-100:]
        _save(data)


def check_and_recover() -> dict | None:
    """On startup, check for interrupted workflows and return the one to resume."""
    with _LOCK:
        data = _load()
        for wf in data["workflows"]:
            if wf["status"] in ("running", "initialized"):
                wf["status"] = "interrupted"
                wf["updated_at"] = time.time()
                log_resilience(wf["id"], "System interruption detected — marking for recovery")
                _save(data)
                return {
                    "workflow_id": wf["id"],
                    "name": wf["name"],
                    "interrupted_at_step": wf["current_step"],
                    "total_steps": wf["total_steps"],
                    "steps": wf["steps"],
                    "context": wf["context"],
                    "results_so_far": wf["results"],
                }
    return None


def get_active_workflow() -> dict | None:
    """Get the currently active workflow."""
    with _LOCK:
        data = _load()
        if data.get("active"):
            for wf in data["workflows"]:
                if wf.get("id") == data["active"]:
                    return wf
    return None


def all_workflows() -> list[dict]:
    with _LOCK:
        return _load().get("workflows", [])


def health() -> dict:
    with _LOCK:
        data = _load()
        active = data.get("active")
        active_wf = None
        if active:
            for wf in data["workflows"]:
                if wf.get("id") == active:
                    active_wf = wf
                    break
        return {
            "active_workflow": active_wf,
            "total_workflows": len(data["workflows"]),
            "recent_resilience": data["resilience_log"][-5:] if data["resilience_log"] else [],
            "recent_history": data["history"][-5:] if data["history"] else [],
        }
