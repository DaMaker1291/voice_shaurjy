"""
JARVIS Agent Pool — Multi-Agent Orchestration Engine
=====================================================
Spawns, manages, and coordinates multiple concurrent agents.
Each agent has isolated context, memory, tools, and lifecycle.
"""

import os
import json
import time
import uuid
import threading
import traceback
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, Future


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    OS = "os"
    HAL = "hal"
    WEB = "web"
    CHAT = "chat"
    DEVICE = "device"
    MONITOR = "monitor"
    CUSTOM = "custom"


@dataclass
class AgentTask:
    id: str
    agent_id: str
    command: str
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Agent:
    id: str
    name: str
    agent_type: str
    status: str = AgentStatus.IDLE
    user_id: str = "local"
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    task_history: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    error_count: int = 0
    total_tasks: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class AgentPool:
    """Multi-agent orchestration engine with concurrent execution."""

    def __init__(self, max_concurrent: int = 10):
        self._agents: Dict[str, Agent] = {}
        self._tasks: Dict[str, AgentTask] = {}
        self._task_results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._futures: Dict[str, Future] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._max_concurrent = max_concurrent
        self._event_log: List[Dict[str, Any]] = []
        self._max_log = 500

    def spawn(
        self,
        name: str,
        agent_type: str = AgentType.CHAT,
        user_id: str = "local",
        config: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Agent:
        """Spawn a new agent into the pool."""
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        agent = Agent(
            id=agent_id,
            name=name,
            agent_type=agent_type,
            user_id=user_id,
            config=config or {},
            capabilities=capabilities or [],
            tags=tags or [],
        )
        with self._lock:
            self._agents[agent_id] = agent
        self._log_event("agent_spawned", {"agent_id": agent_id, "name": name, "type": agent_type})
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(
        self,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Agent]:
        with self._lock:
            agents = list(self._agents.values())
        if status:
            agents = [a for a in agents if a.status == status]
        if agent_type:
            agents = [a for a in agents if a.agent_type == agent_type]
        if user_id:
            agents = [a for a in agents if a.user_id == user_id]
        return agents

    def kill(self, agent_id: str) -> bool:
        """Kill an agent and cancel its current task."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            if agent.current_task and agent.current_task in self._futures:
                future = self._futures.get(agent.current_task)
                if future and not future.done():
                    future.cancel()
            agent.status = AgentStatus.CANCELLED
            agent.last_active = time.time()
        self._log_event("agent_killed", {"agent_id": agent_id})
        return True

    def pause(self, agent_id: str) -> bool:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent and agent.status == AgentStatus.RUNNING:
                agent.status = AgentStatus.PAUSED
                return True
        return False

    def resume(self, agent_id: str) -> bool:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent and agent.status == AgentStatus.PAUSED:
                agent.status = AgentStatus.RUNNING
                return True
        return False

    def submit_task(
        self,
        agent_id: str,
        command: str,
        handler: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentTask]:
        """Submit a task to an agent for execution."""
        agent = self.get_agent(agent_id)
        if not agent:
            return None

        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = AgentTask(
            id=task_id,
            agent_id=agent_id,
            command=command,
            metadata=metadata or {},
        )

        with self._lock:
            self._tasks[task_id] = task
            agent.current_task = task_id
            agent.status = AgentStatus.RUNNING
            agent.last_active = time.time()
            agent.total_tasks += 1
            agent.task_history.append(task_id)

        if handler:
            task.status = "running"
            task.started_at = time.time()
            future = self._executor.submit(self._run_task, task, handler)
            with self._lock:
                self._futures[task_id] = future
        else:
            task.status = "completed"
            task.completed_at = time.time()
            task.result = {"status": "no_handler", "command": command}

        self._log_event("task_submitted", {"agent_id": agent_id, "task_id": task_id, "command": command[:100]})
        return task

    def _run_task(self, task: AgentTask, handler: Callable):
        """Execute a task handler in the thread pool."""
        try:
            result = handler(task.command, task.metadata)
            task.result = result
            task.status = "completed"
        except Exception as e:
            task.result = {"error": str(e), "traceback": traceback.format_exc()}
            task.status = "failed"
            with self._lock:
                agent = self._agents.get(task.agent_id)
                if agent:
                    agent.error_count += 1
        finally:
            task.completed_at = time.time()
            with self._lock:
                agent = self._agents.get(task.agent_id)
                if agent:
                    agent.current_task = None
                    agent.status = AgentStatus.IDLE
                    agent.last_active = time.time()
            self._log_event("task_completed", {
                "agent_id": task.agent_id,
                "task_id": task.id,
                "status": task.status,
                "duration_ms": int((task.completed_at - task.started_at) * 1000) if task.started_at else 0,
            })

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_agent_tasks(self, agent_id: str, limit: int = 20) -> List[AgentTask]:
        with self._lock:
            tasks = [t for t in self._tasks.values() if t.agent_id == agent_id]
        tasks.sort(key=lambda t: t.started_at or 0, reverse=True)
        return tasks[:limit]

    def get_pool_stats(self) -> Dict[str, Any]:
        with self._lock:
            agents = list(self._agents.values())
            tasks = list(self._tasks.values())
        running = sum(1 for a in agents if a.status == AgentStatus.RUNNING)
        return {
            "total_agents": len(agents),
            "running": running,
            "idle": sum(1 for a in agents if a.status == AgentStatus.IDLE),
            "failed": sum(1 for a in agents if a.status == AgentStatus.FAILED),
            "total_tasks": len(tasks),
            "completed_tasks": sum(1 for t in tasks if t.status == "completed"),
            "failed_tasks": sum(1 for t in tasks if t.status == "failed"),
            "active_tasks": sum(1 for t in tasks if t.status == "running"),
            "max_concurrent": self._max_concurrent,
            "utilization": f"{running}/{self._max_concurrent}",
        }

    def get_event_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._event_log[-limit:]

    def _log_event(self, event_type: str, data: Dict[str, Any]):
        entry = {"type": event_type, "time": time.time(), **data}
        with self._lock:
            self._event_log.append(entry)
            if len(self._event_log) > self._max_log:
                self._event_log = self._event_log[-self._max_log:]

    def cleanup_stale(self, max_idle_seconds: int = 3600):
        """Remove agents idle for too long."""
        now = time.time()
        stale = []
        with self._lock:
            for aid, agent in self._agents.items():
                if agent.status == AgentStatus.IDLE and (now - agent.last_active) > max_idle_seconds:
                    stale.append(aid)
            for aid in stale:
                del self._agents[aid]
        return len(stale)


_pool: Optional[AgentPool] = None
_pool_lock = threading.Lock()


def get_pool() -> AgentPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = AgentPool(max_concurrent=10)
    return _pool
