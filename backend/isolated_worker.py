"""
Isolated Worker — Spawns worker_desktop.py on a HIDDEN desktop.

The user's display NEVER changes.
The worker process creates its own desktop, does work, saves results, exits.
"""
import subprocess
import os
import sys
import time
import json
import threading
from typing import Optional
from dataclasses import dataclass

WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker_desktop.py")
RESULT_DIR = os.path.join(os.path.expanduser("~"), ".jarvis", "isolated_results")


@dataclass
class IsolatedTask:
    task_id: str
    status: str = "pending"
    result: str = ""
    error: str = ""
    pid: int = 0
    start_time: float = 0
    end_time: float = 0

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "pid": self.pid,
            "duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else 0,
        }


class IsolatedWorker:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()
        self._counter = 0
        os.makedirs(RESULT_DIR, exist_ok=True)

    def _next_id(self):
        self._counter += 1
        return "iso_" + str(self._counter) + "_" + str(int(time.time()))

    def _spawn(self, task_data):
        task_id = task_data["task_id"]
        task_file = os.path.join(RESULT_DIR, task_id + "_input.json")
        with open(task_file, "w") as f:
            json.dump(task_data, f)

        proc = subprocess.Popen(
            [sys.executable, WORKER_SCRIPT, task_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return proc

    def _monitor(self, task, proc):
        proc.wait()
        task.end_time = time.time()
        result_file = os.path.join(RESULT_DIR, task.task_id + ".json")
        if os.path.exists(result_file):
            with open(result_file) as f:
                r = json.load(f)
            task.status = r.get("status", "done")
            task.result = r.get("result", "")
            task.error = r.get("error", "")
        else:
            task.status = "done"

    def run_app(self, app_name, args=None, timeout=60):
        task = IsolatedTask(task_id=self._next_id(), status="running", start_time=time.time())
        proc = self._spawn({"task_id": task.task_id, "type": "app", "app": app_name, "args": args or [], "timeout": timeout})
        task.pid = proc.pid
        with self._lock:
            self._tasks[task.task_id] = task
        threading.Thread(target=self._monitor, args=(task, proc), daemon=True).start()
        return task

    def run_python(self, code, timeout=120):
        task = IsolatedTask(task_id=self._next_id(), status="running", start_time=time.time())
        proc = self._spawn({"task_id": task.task_id, "type": "python", "command": code, "timeout": timeout})
        task.pid = proc.pid
        with self._lock:
            self._tasks[task.task_id] = task
        threading.Thread(target=self._monitor, args=(task, proc), daemon=True).start()
        return task

    def run_blender(self, code, timeout=300):
        task = IsolatedTask(task_id=self._next_id(), status="running", start_time=time.time())
        proc = self._spawn({"task_id": task.task_id, "type": "blender", "command": code, "timeout": timeout})
        task.pid = proc.pid
        with self._lock:
            self._tasks[task.task_id] = task
        threading.Thread(target=self._monitor, args=(task, proc), daemon=True).start()
        return task

    def get_task(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self):
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def wait_for_task(self, task_id, timeout=120):
        start = time.time()
        while time.time() - start < timeout:
            task = self.get_task(task_id)
            if task and task.status in ("done", "failed", "error"):
                return task
            time.sleep(0.5)
        return self.get_task(task_id)


_worker = None

def get_isolated_worker():
    global _worker
    if _worker is None:
        _worker = IsolatedWorker()
    return _worker
