"""JARVIS Mission Engine — Mission Graph with Dynamic Decomposition.

Missions are not flat lists of steps.
They are directed graphs where:
- Steps have dependencies (B can't run until A finishes)
- Steps can be parallelized if no dependency
- Agent Factory creates specialists per subgraph
- Verification Engine checks each step result
- Failure triggers repair subgraph

Graph:
    PLAN → (RESEARCH, BROWSER) → CODE → VERIFY → DEPLOY
                                        ↓ FAIL
                                     REPAIR → VERIFY
"""

import os
import json
import time
import uuid
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple

from agent_factory import AgentFactory, AgentSpec, get_agent_factory, reset_factory
from verification_engine import VerificationEngine, VerificationResult, get_verification_engine
from task_router import route_and_execute
from workspace_manager import get_workspace_manager

log = logging.getLogger("mission_engine")


# ══════════════════════════════════════════════════════════════
#  MISSION GRAPH NODE
# ══════════════════════════════════════════════════════════════

@dataclass
class GraphNode:
    """A single node in the mission graph."""
    id: str
    action: str
    description: str
    params: dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Node IDs that must complete first
    agent_role: str = ""        # Which agent factory role handles this
    status: str = "pending"     # pending, ready, running, completed, failed, repairing
    result: dict = field(default_factory=dict)
    verification: Optional[dict] = None
    retries: int = 0
    max_retries: int = 2
    started_at: float = 0
    completed_at: float = 0

    def to_dict(self):
        return {
            "id": self.id, "action": self.action, "description": self.description,
            "params": self.params, "dependencies": self.dependencies,
            "agent_role": self.agent_role, "status": self.status,
            "result": self.result, "verification": self.verification,
            "retries": self.retries,
            "started_at": self.started_at, "completed_at": self.completed_at,
        }


@dataclass
class MissionGraph:
    """Complete mission graph — the full plan."""
    id: str
    objective: str
    workspace_id: str
    status: str = "planning"     # planning, running, paused, completed, failed
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    agent_team: List[dict] = field(default_factory=list)
    progress: float = 0.0
    current_action: str = ""
    created_at: float = 0
    started_at: float = 0
    completed_at: float = 0
    error: str = ""

    def to_dict(self):
        return {
            "id": self.id, "objective": self.objective,
            "workspace_id": self.workspace_id, "status": self.status,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "agent_team": self.agent_team, "progress": self.progress,
            "current_action": self.current_action,
            "created_at": self.created_at, "started_at": self.started_at,
            "completed_at": self.completed_at, "error": self.error,
        }

    def get_ready_nodes(self) -> List[GraphNode]:
        """Get nodes whose dependencies are all completed."""
        ready = []
        for node in self.nodes.values():
            if node.status != "pending":
                continue
            deps_met = all(
                self.nodes.get(dep, GraphNode("", "", "")).status == "completed"
                for dep in node.dependencies
            )
            if deps_met:
                ready.append(node)
        return ready

    def compute_progress(self) -> float:
        if not self.nodes:
            return 0.0
        completed = sum(1 for n in self.nodes.values() if n.status == "completed")
        return completed / len(self.nodes)


# ══════════════════════════════════════════════════════════════
#  MISSION ENGINE
# ══════════════════════════════════════════════════════════════

class MissionEngine:
    """Orchestrates mission execution using agent factory + verification."""

    def __init__(self):
        self._missions: Dict[str, MissionGraph] = {}
        self._running: Dict[str, bool] = {}

    def create_mission(self, objective: str, workspace_id: str) -> MissionGraph:
        """Create a new mission graph."""
        mid = str(uuid.uuid8())[:8] if hasattr(uuid, "uuid8") else str(uuid.uuid4())[:8]
        mid = f"m_{mid}"
        graph = MissionGraph(
            id=mid, objective=objective, workspace_id=workspace_id,
            created_at=time.time(),
        )
        self._missions[mid] = graph
        log.info(f"[MISSION] Created {mid}: {objective}")
        return graph

    def plan_mission(self, mission_id: str) -> MissionGraph:
        """Plan a mission — build the graph from the objective."""
        graph = self._missions.get(mission_id)
        if not graph:
            raise ValueError(f"Mission {mission_id} not found")

        # Reset and create fresh factory
        reset_factory()
        factory = get_agent_factory(workspace_id=graph.workspace_id)

        # Build agent team
        team = factory.build_team(graph.objective)
        graph.agent_team = [a.to_dict() for a in team]

        # Build the execution graph based on agent roles
        nodes: Dict[str, GraphNode] = {}
        prev_id = None

        for agent in team:
            node_id = agent.id
            node = GraphNode(
                id=node_id,
                action=self._role_to_action(agent.role),
                description=agent.objective,
                params={"role": agent.role, "objective": agent.objective},
                dependencies=[prev_id] if prev_id else [],
                agent_role=agent.role,
            )
            nodes[node_id] = node
            prev_id = node_id

        graph.nodes = nodes
        graph.status = "planned"
        log.info(f"[MISSION] Planned {mission_id}: {len(nodes)} nodes, {len(team)} agents")
        return graph

    def _role_to_action(self, role: str) -> str:
        """Map agent role to default action type."""
        mapping = {
            "research": "web_search",
            "code": "write_file",
            "browser": "navigate_web",
            "design": "write_file",
            "verify": "run_command",
            "deploy": "run_command",
            "file": "write_file",
            "data": "run_command",
            "media": "run_command",
            "communication": "navigate_web",
        }
        return mapping.get(role, "run_command")

    def start_mission(self, mission_id: str) -> MissionGraph:
        """Start executing the mission graph."""
        graph = self._missions.get(mission_id)
        if not graph:
            raise ValueError(f"Mission {mission_id} not found")

        graph.status = "running"
        graph.started_at = time.time()
        self._running[mission_id] = True

        # Start execution in background
        import threading
        t = threading.Thread(target=self._execute_graph, args=(mission_id,), daemon=True)
        t.start()
        return graph

    def _execute_graph(self, mission_id: str):
        """Execute the mission graph — runs in background thread."""
        graph = self._missions.get(mission_id)
        if not graph:
            return

        workspace_id = graph.workspace_id
        wm = get_workspace_manager()
        verifier = get_verification_engine(
            workspace_dir=os.path.expanduser(f"~/.jarvis/workspaces/{workspace_id}/files")
        )

        try:
            while self._running.get(mission_id, False):
                ready = graph.get_ready_nodes()
                if not ready:
                    all_done = all(n.status in ("completed", "failed") for n in graph.nodes.values())
                    if all_done:
                        failed = any(n.status == "failed" for n in graph.nodes.values())
                        graph.status = "failed" if failed else "completed"
                        graph.completed_at = time.time()
                        log.info(f"[MISSION] {mission_id}: {graph.status}")
                        break
                    time.sleep(1)
                    continue

                for node in ready:
                    if not self._running.get(mission_id, False):
                        break
                    node.status = "running"
                    node.started_at = time.time()
                    graph.current_action = node.description
                    wm.update_action(workspace_id, node.description, "working")

                    # Agent thinks: decide specific action + params
                    action, params = self._agent_think(node, graph)

                    # Execute via task router
                    result = route_and_execute(
                        action, params, workspace_id,
                        risk_level="low", objective=graph.objective,
                    )
                    node.result = result.to_dict()

                    # Verify
                    verification = verifier.verify(action, params, result.to_dict())
                    node.verification = verification.to_dict()

                    if verification.success:
                        node.status = "completed"
                        node.completed_at = time.time()
                        log.info(f"[MISSION] {mission_id}: {node.id} ✓")
                    elif node.retries < node.max_retries and verification.retry_approved:
                        node.retries += 1
                        node.status = "pending"
                        log.warning(f"[MISSION] {mission_id}: {node.id} retry {node.retries}")
                    else:
                        node.status = "failed"
                        log.error(f"[MISSION] {mission_id}: {node.id} failed: {node.result.get('error', '')}")

                    graph.progress = graph.compute_progress()

                time.sleep(0.5)

        except Exception as e:
            graph.status = "failed"
            graph.error = str(e)
            log.error(f"[MISSION] {mission_id} crashed: {e}")
        finally:
            self._running.pop(mission_id, None)
            graph.completed_at = time.time()

    def _agent_think(self, node: GraphNode, graph: MissionGraph) -> Tuple[str, dict]:
        """Agent decides what specific action to take.
        
        Uses LLM to translate a high-level objective into a concrete
        action + params that the task router can execute.
        """
        role = node.agent_role
        objective = node.description

        # Build context from completed dependency nodes
        context_parts = []
        for dep_id in node.dependencies:
            dep_node = graph.nodes.get(dep_id)
            if dep_node and dep_node.result:
                context_parts.append(f"{dep_node.agent_role}: {dep_node.result.get('output', '')[:200]}")
        context = "\n".join(context_parts) if context_parts else "No prior results."

        prompt = f"""You are a {role} agent in JARVIS. Your objective: {objective}

Previous work:
{context}

Decide the single best action to take NOW. Respond with ONLY a JSON object:
{{"action": "<action_type>", "params": {{<params>}}}}

Available actions and their params:
- write_file: {{"path": "<relative_path>", "content": "<full file content>"}}
- run_command: {{"cmd": "<shell command>"}}
- web_search: {{"query": "<search query>"}}
- web_scrape: {{"url": "<url>"}}
- navigate_web: {{"url": "<url>"}}
- create_directory: {{"path": "<dir_path>"}}
- read_file: {{"path": "<file_path>"}}
- wait: {{"seconds": 1}}

Make it concrete and useful. Create real files with real content."""

        try:
            from groq_agent import call_llm
            response = call_llm(prompt, max_tokens=800)
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                action = parsed.get("action", node.action)
                params = parsed.get("params", {})
                log.info(f"[AGENT] {node.id} chose: {action}")
                return action, params
        except Exception as e:
            log.warning(f"[AGENT] {node.id} think failed: {e}, using defaults")

        # Fallback: use the default action with basic params
        if node.action == "write_file":
            return "write_file", {"path": "output.txt", "content": f"# {objective}\n\nGenerated by JARVIS {node.agent_role} agent."}
        elif node.action == "navigate_web":
            return "navigate_web", {"url": "https://www.google.com"}
        elif node.action == "run_command":
            return "run_command", {"cmd": f"echo JARVIS {node.agent_role} agent working"}
        else:
            return node.action, node.params

    def pause_mission(self, mission_id: str):
        self._running[mission_id] = False
        graph = self._missions.get(mission_id)
        if graph:
            graph.status = "paused"

    def resume_mission(self, mission_id: str):
        graph = self._missions.get(mission_id)
        if graph and graph.status == "paused":
            self.start_mission(mission_id)

    def stop_mission(self, mission_id: str):
        self._running[mission_id] = False
        graph = self._missions.get(mission_id)
        if graph:
            graph.status = "stopped"

    def get_mission(self, mission_id: str) -> Optional[MissionGraph]:
        graph = self._missions.get(mission_id)
        if graph:
            graph.progress = graph.compute_progress()
        return graph

    def list_missions(self) -> List[MissionGraph]:
        return list(self._missions.values())


# ══════════════════════════════════════════════════════════════
#  SINGLETON
# ══════════════════════════════════════════════════════════════

_engine: Optional[MissionEngine] = None


def get_mission_engine() -> MissionEngine:
    global _engine
    if _engine is None:
        _engine = MissionEngine()
    return _engine
