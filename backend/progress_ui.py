"""
Progress UI — Real-time task progress overlay.

Shows a floating HTML dashboard in the browser that updates live:
- Task list with status (running, done, failed)
- Progress bars
- Live log output
- Current step description
- Estimated time remaining

Uses a local HTTP server + WebSocket for real-time updates.
"""

import json
import os
import time
import logging
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger("jarvis-progress")

try:
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False


# ═══════════════════════════════════════════════════════════════════════════
# TASK STATE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TaskStep:
    id: str
    name: str
    status: str = "pending"  # pending, running, done, failed, skipped
    progress: int = 0        # 0-100
    message: str = ""
    started_at: float = 0
    finished_at: float = 0
    result: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "duration": round(time.time() - self.started_at, 1) if self.started_at else 0,
            "result": self.result[:200],
        }


@dataclass
class TaskState:
    task_id: str
    title: str
    status: str = "running"  # running, done, failed
    steps: List[TaskStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    logs: List[str] = field(default_factory=list)
    current_step: str = ""
    total_progress: int = 0

    def to_dict(self):
        elapsed = time.time() - self.created_at
        done = sum(1 for s in self.steps if s.status == "done")
        total = len(self.steps) or 1
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "progress": int(done / total * 100),
            "steps": [s.to_dict() for s in self.steps],
            "elapsed": round(elapsed, 1),
            "current_step": self.current_step,
            "logs": self.logs[-50:],
            "created_at": datetime.fromtimestamp(self.created_at).strftime("%H:%M:%S"),
        }


# ═══════════════════════════════════════════════════════════════════════════
# PROGRESS TRACKER
# ═══════════════════════════════════════════════════════════════════════════

class ProgressTracker:
    """Singleton that tracks all active tasks and broadcasts updates."""

    def __init__(self):
        self._tasks: Dict[str, TaskState] = {}
        self._listeners: List = []
        self._lock = threading.Lock()

    def start_task(self, task_id: str, title: str, steps: List[str] = None) -> TaskState:
        with self._lock:
            task = TaskState(task_id=task_id, title=title)
            for i, step_name in enumerate(steps or []):
                task.steps.append(TaskStep(id=str(i), name=step_name))
            self._tasks[task_id] = task
            self._broadcast()
            return task

    def update_step(self, task_id: str, step_id: str, status: str = None,
                    progress: int = None, message: str = None, result: str = None):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            for step in task.steps:
                if step.id == step_id:
                    if status:
                        step.status = status
                        if status == "running" and not step.started_at:
                            step.started_at = time.time()
                        elif status in ("done", "failed"):
                            step.finished_at = time.time()
                    if progress is not None:
                        step.progress = progress
                    if message:
                        step.message = message
                        task.current_step = message
                    if result:
                        step.result = result
                    break
            self._broadcast()

    def log(self, task_id: str, message: str):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                ts = datetime.now().strftime("%H:%M:%S")
                task.logs.append("[" + ts + "] " + message)
                if len(task.logs) > 200:
                    task.logs = task.logs[-200:]
                self._broadcast()

    def finish_task(self, task_id: str, status: str = "done"):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = status
                self._broadcast()

    def get_task(self, task_id: str) -> Optional[Dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.to_dict() if task else None

    def get_all_tasks(self) -> List[Dict]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def add_listener(self, callback):
        self._listeners.append(callback)

    def _broadcast(self):
        data = self.get_all_tasks()
        for listener in self._listeners[:]:
            try:
                listener(data)
            except Exception:
                self._listeners.remove(listener)


# Singleton
_tracker = None

def get_tracker() -> ProgressTracker:
    global _tracker
    if _tracker is None:
        _tracker = ProgressTracker()
    return _tracker


# ═══════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS Task Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0e1a; color: #e2e8f0; min-height: 100vh; }

.header { background: linear-gradient(135deg, #1a1f35, #0d1025); padding: 16px 24px; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid #1e293b; }
.header h1 { font-size: 1.4em; color: #60a5fa; }
.header .status { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.header .dot { width: 10px; height: 10px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.tasks-container { padding: 20px; display: flex; flex-direction: column; gap: 16px; max-width: 1200px; margin: 0 auto; }

.task-card { background: #111827; border-radius: 12px; border: 1px solid #1e293b; overflow: hidden; transition: all 0.3s; }
.task-card:hover { border-color: #3b82f6; }
.task-card.done { border-color: #22c55e; }
.task-card.failed { border-color: #ef4444; }

.task-header { padding: 16px 20px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #1e293b; }
.task-title { font-size: 1.1em; font-weight: 600; }
.task-badge { padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 500; }
.badge-running { background: #1e3a5f; color: #60a5fa; }
.badge-done { background: #14532d; color: #22c55e; }
.badge-failed { background: #450a0a; color: #ef4444; }
.task-time { margin-left: auto; color: #64748b; font-size: 0.85em; }

.task-progress { padding: 0 20px; }
.progress-bar-bg { height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; margin-top: 8px; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 3px; transition: width 0.5s ease; }
.progress-bar.done { background: linear-gradient(90deg, #22c55e, #4ade80); }
.progress-text { font-size: 0.8em; color: #94a3b8; margin-top: 4px; }

.steps { padding: 12px 20px; }
.step { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #0f172a; }
.step:last-child { border: none; }
.step-icon { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.7em; flex-shrink: 0; }
.step-pending { background: #1e293b; color: #64748b; }
.step-running { background: #1e3a5f; color: #60a5fa; animation: pulse 1.5s infinite; }
.step-done { background: #14532d; color: #22c55e; }
.step-failed { background: #450a0a; color: #ef4444; }
.step-name { flex: 1; font-size: 0.9em; }
.step-msg { color: #64748b; font-size: 0.8em; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-dur { color: #475569; font-size: 0.75em; min-width: 50px; text-align: right; }

.logs { padding: 12px 20px; max-height: 200px; overflow-y: auto; background: #0a0e1a; border-top: 1px solid #1e293b; }
.log-line { font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.75em; color: #94a3b8; padding: 2px 0; }
.log-line:nth-child(odd) { color: #64748b; }

.empty { text-align: center; padding: 60px; color: #475569; }
.empty h2 { color: #64748b; margin-bottom: 8px; }
</style>
</head>
<body>
<div class="header">
    <div class="dot"></div>
    <h1>JARVIS Task Dashboard</h1>
    <div class="status">
        <span id="taskCount">0 tasks</span>
    </div>
</div>
<div class="tasks-container" id="tasks"></div>

<script>
let ws;
const tasksEl = document.getElementById('tasks');
const countEl = document.getElementById('taskCount');

function connect() {
    var wsPort = location.port || '7890';
    ws = new WebSocket('ws://localhost:' + wsPort + '/tasks/ws');
    ws.onmessage = (e) => {
        const tasks = JSON.parse(e.data);
        render(tasks);
    };
    ws.onclose = () => setTimeout(connect, 2000);
    ws.onerror = () => {};
}

function render(tasks) {
    countEl.textContent = tasks.length + ' task' + (tasks.length !== 1 ? 's' : '');
    if (!tasks.length) {
        tasksEl.innerHTML = '<div class="empty"><h2>No active tasks</h2><p>JARVIS will show progress here</p></div>';
        return;
    }
    tasksEl.innerHTML = tasks.map(t => {
        const badge = t.status === 'done' ? 'badge-done' : t.status === 'failed' ? 'badge-failed' : 'badge-running';
        const stepsHtml = t.steps.map(s => {
            const icon = s.status === 'done' ? '\u2713' : s.status === 'failed' ? '\u2717' : s.status === 'running' ? '\u25b6' : '\u25cb';
            return '<div class="step"><div class="step-icon step-' + s.status + '">' + icon + '</div><span class="step-name">' + s.name + '</span><span class="step-msg">' + (s.message || '') + '</span><span class="step-dur">' + (s.duration ? s.duration + 's' : '') + '</span></div>';
        }).join('');
        const logsHtml = t.logs.slice(-20).map(l => '<div class="log-line">' + l + '</div>').join('');
        return '<div class="task-card ' + t.status + '"><div class="task-header"><span class="task-title">' + t.title + '</span><span class="task-badge ' + badge + '">' + t.status + '</span><span class="task-time">' + t.created_at + ' | ' + t.elapsed + 's</span></div><div class="task-progress"><div class="progress-bar-bg"><div class="progress-bar ' + (t.status === 'done' ? 'done' : '') + '" style="width:' + t.progress + '%"></div></div><div class="progress-text">' + (t.current_step || t.status) + '</div></div><div class="steps">' + stepsHtml + '</div>' + (logsHtml ? '<div class="logs">' + logsHtml + '</div>' : '') + '</div>';
    }).join('');
}

connect();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI SERVER
# ═══════════════════════════════════════════════════════════════════════════

def start_progress_server(port: int = 8899) -> Optional[object]:
    """Start the progress dashboard server."""
    if not _HAS_FASTAPI:
        log.warning("FastAPI not available for progress UI")
        return None

    app = FastAPI()
    tracker = get_tracker()
    connected_clients = []

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html = DASHBOARD_HTML.replace("PORT", str(port))
        return html

    @app.get("/api/tasks")
    async def get_tasks():
        return tracker.get_all_tasks()

    @app.get("/api/task/{task_id}")
    async def get_task(task_id: str):
        return tracker.get_task(task_id)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        connected_clients.append(websocket)

        def on_update(data):
            try:
                threading.Thread(
                    target=lambda: websocket.send_json(data),
                    daemon=True,
                ).start()
            except Exception:
                pass

        tracker.add_listener(on_update)

        try:
            while True:
                await websocket.receive_text()
        except Exception:
            connected_clients.remove(websocket)

    # Run server in background thread
    def run():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    log.info("[PROGRESS] Dashboard server ready on port " + str(port))
    return app


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

_server_started = False

def ensure_server(port: int = 8899):
    global _server_started
    if not _server_started:
        start_progress_server(port)
        _server_started = True
        time.sleep(1)


def track_task(task_id: str, title: str, steps: List[str] = None) -> TaskState:
    """Start tracking a task."""
    ensure_server()
    return get_tracker().start_task(task_id, title, steps)


def update_step(task_id: str, step_id: str, **kwargs):
    get_tracker().update_step(task_id, step_id, **kwargs)


def log_task(task_id: str, message: str):
    get_tracker().log(task_id, message)


def finish_task(task_id: str, status: str = "done"):
    get_tracker().finish_task(task_id, status)
