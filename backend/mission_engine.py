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
        """Plan a mission — LLM-driven decomposition into a real DAG.

        Uses goal_planner to decompose the objective into subtasks with
        dependency relationships, then builds a proper execution graph
        with parallel branches where possible.
        """
        graph = self._missions.get(mission_id)
        if not graph:
            raise ValueError(f"Mission {mission_id} not found")

        # ── Step 1: LLM-driven goal decomposition ──
        sub_goals = self._decompose_goal(graph.objective)

        # ── Step 2: Build execution graph (DAG, not linear) ──
        nodes: Dict[str, GraphNode] = {}
        role_agents = {}

        for sg in sub_goals:
            role = self._infer_role(sg.get("action", ""), sg.get("description", ""))
            agent_id = f"a_{mission_id}_{sg['id']}"
            node = GraphNode(
                id=agent_id,
                action=sg.get("action", "run_command"),
                description=sg.get("description", sg.get("objective", "")),
                params=sg.get("params", {}),
                dependencies=[],  # Will be resolved below
                agent_role=role,
            )
            nodes[agent_id] = node
            role_agents[sg["id"]] = agent_id

            # Create agent for evidence tracking
            from evidence_ledger import get_evidence_ledger
            ledger = get_evidence_ledger(mission_id)
            ledger.record_agent_created(agent_id, role, sg.get("description", ""))

        # ── Step 3: Resolve dependencies (real DAG) ──
        for sg in sub_goals:
            agent_id = role_agents[sg["id"]]
            deps = sg.get("depends_on", [])
            resolved_deps = []
            for dep_id in deps:
                if dep_id in role_agents:
                    resolved_deps.append(role_agents[dep_id])
            nodes[agent_id].dependencies = resolved_deps

        # ── Step 4: Assign agent team for workspace ──
        reset_factory()
        factory = get_agent_factory(workspace_id=graph.workspace_id)
        team = factory.build_team(graph.objective)
        graph.agent_team = [a.to_dict() for a in team]

        graph.nodes = nodes
        graph.status = "planned"
        graph.progress = 0.0
        log.info(f"[MISSION] Planned {mission_id}: {len(nodes)} nodes (DAG), {len(team)} agents")
        return graph

    def _decompose_goal(self, objective: str) -> list:
        """Use LLM to decompose an objective into subtasks with dependencies.

        Returns a list of dicts: [{"id": "1", "description": "...", "action": "...",
        "params": {...}, "depends_on": ["0"], "priority": 1}, ...]
        """
        # Try goal_planner first
        try:
            from goal_planner import get_planner
            planner = get_planner()
            plan = planner.plan(objective)
            if plan and plan.sub_goals:
                result = []
                for i, sg in enumerate(plan.sub_goals):
                    result.append({
                        "id": sg.id or str(i),
                        "description": sg.description,
                        "action": sg.action,
                        "params": sg.params,
                        "depends_on": sg.depends_on,
                        "priority": sg.priority,
                    })
                return result
        except Exception as e:
            log.warning(f"[MISSION] goal_planner failed: {e}")

        # Fallback: LLM decomposition
        try:
            from groq_agent import call_llm
            prompt = f"""Decompose this objective into 2-6 subtasks with dependencies.

OBJECTIVE: {objective}

Return a JSON array of subtasks. Each subtask has:
- id: string (sequential, starting from "1")
- description: what this subtask does
- action: one of: write_file, run_command, web_search, web_scrape, navigate_web, create_directory, read_file, wait
- params: action-specific parameters
- depends_on: list of subtask IDs this depends on (empty if independent)
- priority: 1 (critical) to 5 (nice-to-have)

Return ONLY the JSON array, no explanation."""

            response = call_llm(prompt, max_tokens=1500)
            import re, json
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
        except Exception as e:
            log.warning(f"[MISSION] LLM decomposition failed: {e}")

        # Final fallback: single-step plan
        return [{"id": "1", "description": objective, "action": "run_command",
                 "params": {"cmd": f"echo 'Executing: {objective}'},
                 "depends_on": [], "priority": 1}]

    def _infer_role(self, action: str, description: str) -> str:
        """Infer agent role from action type and description."""
        desc_lower = description.lower()
        if action in ("web_search", "web_scrape", "navigate_web") or "search" in desc_lower or "research" in desc_lower:
            return "research"
        elif action == "write_file" or "create" in desc_lower or "write" in desc_lower:
            return "code"
        elif "screenshot" in desc_lower or "capture" in desc_lower:
            return "browser"
        elif "verify" in desc_lower or "test" in desc_lower:
            return "verify"
        elif "file" in desc_lower or "organize" in desc_lower:
            return "file"
        elif "data" in desc_lower or "parse" in desc_lower:
            return "data"
        return "research"

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
        """Execute the mission graph — runs in background thread.

        Follows the vision pipeline: OBSERVE → PLAN → ACT → VERIFY → EVIDENCE
        Each step is recorded in the evidence ledger for auditability.
        """
        graph = self._missions.get(mission_id)
        if not graph:
            return

        workspace_id = graph.workspace_id
        wm = get_workspace_manager()
        verifier = get_verification_engine(
            workspace_dir=os.path.expanduser(f"~/.jarvis/workspaces/{workspace_id}/files")
        )

        # ── Evidence ledger integration ──
        from evidence_ledger import get_evidence_ledger
        ledger = get_evidence_ledger(mission_id)

        try:
            while self._running.get(mission_id, False):
                ready = graph.get_ready_nodes()
                if not ready:
                    all_done = all(n.status in ("completed", "failed") for n in graph.nodes.values())
                    if all_done:
                        failed = any(n.status == "failed" for n in graph.nodes.values())
                        graph.status = "failed" if failed else "completed"
                        graph.completed_at = time.time()

                        # Record final mission outcome
                        stats = ledger.get_stats()
                        ledger.record_action(
                            action_type="mission_complete",
                            description=f"Mission {graph.status}: {graph.objective[:80]}",
                            agent_id="mission_engine",
                            agent_role="orchestrator",
                            result={"status": graph.status, "stats": stats},
                        )
                        log.info(f"[MISSION] {mission_id}: {graph.status}")
                        break
                    time.sleep(1)
                    continue

                # ── Parallel execution of ready nodes ──
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(ready), 4)) as pool:
                    futures = {}
                    for node in ready:
                        if not self._running.get(mission_id, False):
                            break
                        futures[pool.submit(self._execute_node, mission_id, node, graph, wm, verifier, ledger)] = node

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            node = futures[future]
                            node.status = "failed"
                            ledger.record_error(str(e), context=f"Node {node.id}")

                graph.progress = graph.compute_progress()
                time.sleep(0.5)

        except Exception as e:
            graph.status = "failed"
            graph.error = str(e)
            log.error(f"[MISSION] {mission_id} crashed: {e}")
        finally:
            self._running.pop(mission_id, None)
            graph.completed_at = time.time()

    def _execute_node(self, mission_id: str, node: GraphNode, graph: MissionGraph,
                      wm, verifier, ledger):
        """Execute a single node with OBSERVE → ACT → VERIFY → EVIDENCE."""
        node.status = "running"
        node.started_at = time.time()
        graph.current_action = node.description
        wm.update_action(graph.workspace_id, node.description, "working")

        # ── OBSERVE: Record what we see before acting ──
        observe_action = ledger.record_action(
            action_type="observe",
            description=f"Observing workspace before: {node.description[:60]}",
            agent_id=node.id,
            agent_role=node.agent_role,
        )

        # ── ACT: Decide and execute ──
        action, params = self._agent_think(node, graph)
        start_time = time.time()

        action_record = ledger.record_action(
            action_type=action,
            description=node.description,
            agent_id=node.id,
            agent_role=node.agent_role,
            tool_used=action,
            params=params,
        )

        result = route_and_execute(
            action, params, graph.workspace_id,
            risk_level="low", objective=graph.objective,
        )
        node.result = result.to_dict()

        duration_ms = (time.time() - start_time) * 1000
        action_record.duration_ms = duration_ms
        action_record.result = result.to_dict()
        action_record.success = result.ok

        # ── VERIFY: Check the result ──
        verification = verifier.verify(action, params, result.to_dict())
        node.verification = verification.to_dict()

        # Record observation
        obs = ledger.record_observation(
            action_id=action_record.id,
            observation_type="action_result",
            description=f"Action {action} {'succeeded' if result.ok else 'failed'}",
            data=result.to_dict(),
        )

        # Record verification
        ledger.record_verification(
            action_id=action_record.id,
            observation_id=obs.id,
            expected=f"{action} should succeed",
            actual=f"Result: {'ok' if result.ok else result.error}",
            passed=verification.success,
            method=verification.method if hasattr(verification, 'method') else "result_check",
        )

        if verification.success:
            node.status = "completed"
            node.completed_at = time.time()
            log.info(f"[MISSION] {mission_id}: {node.id} ✓")
        elif node.retries < node.max_retries and verification.retry_approved:
            node.retries += 1
            node.status = "pending"
            ledger.record_recovery(f"retry_{node.retries}", success=False,
                                   details=f"Retrying {node.id}")
            log.warning(f"[MISSION] {mission_id}: {node.id} retry {node.retries}")
        else:
            node.status = "failed"
            ledger.record_error(node.result.get('error', ''), context=f"Node {node.id}")
            log.error(f"[MISSION] {mission_id}: {node.id} failed")

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
