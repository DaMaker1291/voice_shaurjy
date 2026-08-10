"""JARVIS Mission State Machine v2 — Unified, crash-recoverable mission system.

Merges MissionRecord (persisted) + MissionGraph (rich) into one unified system.

State flow:
  QUEUED → CLARIFYING → PLANNING → EXECUTING → VERIFYING
    ↓                      ↓           ↓              ↓
  (retry)             FAILURE ──→ RECOVERING ──→ EXECUTING (retry)
                                          └─→ FAILED (exhausted)
    VERIFYING ──→ SUCCESS

Persists to disk after every state transition. On restart, scans for
orphaned missions and offers resume.

Mission object includes ALL spec fields:
  mission_id, user_intent, clarification_state, assumptions, objectives,
  subtasks, dependencies, agents, tools, environments, permissions,
  risk_level, progress, evidence, artifacts, sources, errors,
  recovery_attempts, verification_state, final_result
"""

import os
import json
import time
import logging
import threading
import uuid
from typing import Optional, Dict, List, Any
from enum import Enum
from dataclasses import dataclass, field, asdict

log = logging.getLogger("mission_state")

MISSIONS_DIR = os.path.join(os.path.dirname(__file__), ".mission_data")

VALID_STATES = {
    "queued", "clarifying", "planning", "executing", "verifying",
    "success", "failure", "recovering", "stopped", "paused",
}

HIGH_RISK_ACTIONS = {"run_command", "write_file", "create_directory", "run_command"}

ALLOWED_ACTIONS = {
    "launch_app":      {"required": ["name"], "optional": ["command"], "risk": "low"},
    "click":           {"required": ["x", "y"], "optional": ["button"], "risk": "low",
                        "validators": {"x": lambda v: isinstance(v, (int, float)) and 0 <= v <= 3840,
                                       "y": lambda v: isinstance(v, (int, float)) and 0 <= v <= 2160}},
    "type_text":       {"required": ["text"], "optional": [], "risk": "low"},
    "press_key":       {"required": ["key"], "optional": [], "risk": "low",
                        "validators": {"key": lambda v: isinstance(v, str) and len(v) < 50}},
    "navigate_web":    {"required": ["url"], "optional": [], "risk": "low",
                        "validators": {"url": lambda v: isinstance(v, str) and v.startswith(("http://", "https://"))}},
    "web_search":      {"required": ["query"], "optional": [], "risk": "low"},
    "web_scrape":      {"required": ["url"], "optional": [], "risk": "low",
                        "validators": {"url": lambda v: isinstance(v, str) and v.startswith(("http://", "https://"))}},
    "read_file":       {"required": ["path"], "optional": [], "risk": "low"},
    "write_file":      {"required": ["path", "content"], "optional": [], "risk": "medium"},
    "create_directory":{"required": ["path"], "optional": [], "risk": "medium"},
    "run_command":     {"required": ["cmd"], "optional": [], "risk": "high"},
    "screenshot":      {"required": [], "optional": [], "risk": "low"},
    "wait":            {"required": [], "optional": ["seconds"], "risk": "low"},
}


# ══════════════════════════════════════════════════════════════
#  EVIDENCE & SOURCE TRACKING
# ══════════════════════════════════════════════════════════════

@dataclass
class EvidenceEntry:
    """A single evidence record within a mission."""
    id: str
    timestamp: float
    action_number: int
    action_type: str
    description: str
    agent_id: str = ""
    agent_role: str = ""
    source_url: str = ""
    source_name: str = ""
    result_data: Dict[str, Any] = field(default_factory=dict)
    verification_passed: bool = False
    verification_details: str = ""
    screenshot_path: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Source:
    """A verified source referenced during mission execution."""
    url: str
    name: str
    accessed_at: float
    agent_id: str = ""
    content_type: str = ""  # "webpage", "api", "file", "database"
    verified: bool = False
    relevance_score: float = 0.0
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
#  SUBTASK & DEPENDENCY TRACKING
# ══════════════════════════════════════════════════════════════

@dataclass
class SubTask:
    """A single subtask within a mission objective."""
    id: str
    description: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    assigned_agent: str = ""
    dependencies: List[str] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    max_retries: int = 2
    started_at: float = 0
    completed_at: float = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
#  CLARIFICATION STATE
# ══════════════════════════════════════════════════════════════

@dataclass
class ClarificationState:
    """Tracks what information is missing and what has been clarified."""
    needed_params: List[str] = field(default_factory=list)
    clarified_params: Dict[str, str] = field(default_factory=dict)
    pending_questions: List[str] = field(default_factory=list)
    clarification_history: List[Dict[str, str]] = field(default_factory=list)
    is_complete: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
#  UNIFIED MISSION RECORD (crash-recoverable, all spec fields)
# ══════════════════════════════════════════════════════════════

@dataclass
class MissionRecord:
    """Full mission record — persisted to disk, crash-recoverable.

    Contains ALL spec fields from the master build prompt.
    """
    # Identity
    id: str
    user_intent: str
    workspace_id: str

    # State machine
    state: str = "queued"

    # Clarification
    clarification_state: ClarificationState = field(default_factory=ClarificationState)

    # Planning
    assumptions: List[str] = field(default_factory=list)
    objectives: List[str] = field(default_factory=list)
    subtasks: List[SubTask] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # subtask_id -> [dep_ids]

    # Execution
    agents: List[Dict[str, Any]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    environments: List[str] = field(default_factory=list)
    permissions: Dict[str, str] = field(default_factory=dict)  # resource -> level

    # Risk & Progress
    risk_level: str = "low"  # low, medium, high, critical
    progress: float = 0.0
    current_action: str = ""

    # Evidence & Results
    evidence: List[EvidenceEntry] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    sources: List[Source] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    final_result: Dict[str, Any] = field(default_factory=dict)

    # Recovery
    recovery_attempts: int = 0
    max_recovery: int = 3

    # Verification
    verification_state: str = "pending"  # pending, partial, verified, failed
    verified_steps: List[str] = field(default_factory=list)

    # Timestamps
    created_at: float = 0
    started_at: float = 0
    completed_at: float = 0

    # Mission graph nodes (for dependency-based execution)
    graph_nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"m_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        d["state"] = self.state
        d["clarification_state"] = self.clarification_state.to_dict()
        d["subtasks"] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.subtasks]
        d["evidence"] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.evidence]
        d["sources"] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.sources]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MissionRecord":
        # Handle ClarificationState
        cs_data = d.get("clarification_state", {})
        cs = ClarificationState(
            needed_params=cs_data.get("needed_params", []),
            clarified_params=cs_data.get("clarified_params", {}),
            pending_questions=cs_data.get("pending_questions", []),
            clarification_history=cs_data.get("clarification_history", []),
            is_complete=cs_data.get("is_complete", False),
        )

        # Handle SubTasks
        subtasks = []
        for s in d.get("subtasks", []):
            if isinstance(s, dict):
                subtasks.append(SubTask(
                    id=s.get("id", ""),
                    description=s.get("description", ""),
                    status=s.get("status", "pending"),
                    assigned_agent=s.get("assigned_agent", ""),
                    dependencies=s.get("dependencies", []),
                    result=s.get("result", {}),
                    verification=s.get("verification", {}),
                    retries=s.get("retries", 0),
                    max_retries=s.get("max_retries", 2),
                    started_at=s.get("started_at", 0),
                    completed_at=s.get("completed_at", 0),
                    error=s.get("error", ""),
                ))
            else:
                subtasks.append(s)

        # Handle Evidence
        evidence = []
        for e in d.get("evidence", []):
            if isinstance(e, dict):
                evidence.append(EvidenceEntry(
                    id=e.get("id", ""),
                    timestamp=e.get("timestamp", 0),
                    action_number=e.get("action_number", 0),
                    action_type=e.get("action_type", ""),
                    description=e.get("description", ""),
                    agent_id=e.get("agent_id", ""),
                    agent_role=e.get("agent_role", ""),
                    source_url=e.get("source_url", ""),
                    source_name=e.get("source_name", ""),
                    result_data=e.get("result_data", {}),
                    verification_passed=e.get("verification_passed", False),
                    verification_details=e.get("verification_details", ""),
                    screenshot_path=e.get("screenshot_path", ""),
                    error=e.get("error", ""),
                ))
            else:
                evidence.append(e)

        # Handle Sources
        sources = []
        for s in d.get("sources", []):
            if isinstance(s, dict):
                sources.append(Source(
                    url=s.get("url", ""),
                    name=s.get("name", ""),
                    accessed_at=s.get("accessed_at", 0),
                    agent_id=s.get("agent_id", ""),
                    content_type=s.get("content_type", ""),
                    verified=s.get("verified", False),
                    relevance_score=s.get("relevance_score", 0),
                    snippet=s.get("snippet", ""),
                ))
            else:
                sources.append(s)

        return cls(
            id=d.get("id", ""),
            user_intent=d.get("user_intent", d.get("objective", "")),
            workspace_id=d.get("workspace_id", ""),
            state=d.get("state", "queued"),
            clarification_state=cs,
            assumptions=d.get("assumptions", []),
            objectives=d.get("objectives", []),
            subtasks=subtasks,
            dependencies=d.get("dependencies", {}),
            agents=d.get("agents", []),
            tools_used=d.get("tools_used", []),
            environments=d.get("environments", []),
            permissions=d.get("permissions", {}),
            risk_level=d.get("risk_level", "low"),
            progress=d.get("progress", 0),
            current_action=d.get("current_action", ""),
            evidence=evidence,
            artifacts=d.get("artifacts", []),
            sources=sources,
            errors=d.get("errors", []),
            final_result=d.get("final_result", {}),
            recovery_attempts=d.get("recovery_attempts", 0),
            max_recovery=d.get("max_recovery", 3),
            verification_state=d.get("verification_state", "pending"),
            verified_steps=d.get("verified_steps", []),
            created_at=d.get("created_at", 0),
            started_at=d.get("started_at", 0),
            completed_at=d.get("completed_at", 0),
            graph_nodes=d.get("graph_nodes", {}),
        )

    def add_evidence(self, action_type: str, description: str, agent_id: str = "",
                     agent_role: str = "", source_url: str = "", **kwargs) -> EvidenceEntry:
        """Add an evidence entry to this mission's ledger."""
        entry_num = len(self.evidence) + 1
        entry = EvidenceEntry(
            id=f"ev_{self.id}_{entry_num}",
            timestamp=time.time(),
            action_number=entry_num,
            action_type=action_type,
            description=description,
            agent_id=agent_id,
            agent_role=agent_role,
            source_url=source_url,
            result_data=kwargs.get("result_data", {}),
            verification_passed=kwargs.get("verification_passed", False),
            verification_details=kwargs.get("verification_details", ""),
            screenshot_path=kwargs.get("screenshot_path", ""),
            error=kwargs.get("error", ""),
        )
        self.evidence.append(entry)
        return entry

    def add_source(self, url: str, name: str, agent_id: str = "",
                   content_type: str = "webpage", **kwargs) -> Source:
        """Add a verified source to this mission."""
        # Deduplicate by URL
        for existing in self.sources:
            if existing.url == url:
                existing.verified = True
                return existing
        source = Source(
            url=url, name=name,
            accessed_at=time.time(),
            agent_id=agent_id,
            content_type=content_type,
            verified=kwargs.get("verified", True),
            relevance_score=kwargs.get("relevance_score", 0),
            snippet=kwargs.get("snippet", ""),
        )
        self.sources.append(source)
        return source

    def add_error(self, error: str, context: str = "", agent_id: str = ""):
        """Record an error in the mission."""
        self.errors.append({
            "timestamp": time.time(),
            "error": error,
            "context": context,
            "agent_id": agent_id,
            "recovery_attempt": self.recovery_attempts,
        })

    def compute_progress(self) -> float:
        """Compute progress from subtasks."""
        if not self.subtasks:
            return 0.0
        completed = sum(1 for s in self.subtasks if s.status == "completed")
        return completed / len(self.subtasks)

    def get_resumable_state(self) -> bool:
        """Check if this mission was mid-execution when JARVIS crashed."""
        return self.state in ("executing", "recovering", "planning", "verifying")


# ══════════════════════════════════════════════════════════════
#  MISSION STATE MACHINE (disk-persisted, crash-recoverable)
# ══════════════════════════════════════════════════════════════

class MissionStateMachine:
    """Manages mission state with disk persistence and crash recovery.

    Unified system that combines the rich MissionGraph data model
    with the crash-recoverable MissionRecord persistence.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._missions: Dict[str, MissionRecord] = {}
        os.makedirs(MISSIONS_DIR, exist_ok=True)
        self._load_all()

    def _mission_path(self, mission_id: str) -> str:
        return os.path.join(MISSIONS_DIR, f"{mission_id}.json")

    def _save(self, record: MissionRecord):
        path = self._mission_path(record.id)
        try:
            with open(path, "w") as f:
                json.dump(record.to_dict(), f, indent=2, default=str)
        except Exception as e:
            log.error(f"[STATE] Failed to persist mission {record.id}: {e}")

    def _load_all(self):
        count = 0
        for fname in os.listdir(MISSIONS_DIR):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(MISSIONS_DIR, fname)
            try:
                with open(path) as f:
                    data = json.load(f)
                record = MissionRecord.from_dict(data)
                self._missions[record.id] = record
                count += 1
            except Exception as e:
                log.warning(f"[STATE] Corrupt mission file {fname}: {e}")
        if count:
            log.info(f"[STATE] Loaded {count} persisted missions")

    def create(self, mission_id: str, user_intent: str, workspace_id: str,
               risk_level: str = "low", assumptions: List[str] = None) -> MissionRecord:
        """Create a new mission with full spec fields."""
        record = MissionRecord(
            id=mission_id,
            user_intent=user_intent,
            workspace_id=workspace_id,
            risk_level=risk_level,
            assumptions=assumptions or [],
        )
        with self._lock:
            self._missions[mission_id] = record
        self._save(record)
        log.info(f"[STATE] Created mission {mission_id}: {user_intent[:60]}")
        return record

    def transition(self, mission_id: str, new_state: str, error: str = "") -> bool:
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return False
        if new_state not in VALID_STATES:
            log.error(f"[STATE] Invalid state: {new_state}")
            return False

        old_state = record.state
        record.state = new_state
        if error:
            record.add_error(error, context=f"state_transition:{old_state}->{new_state}")
        if new_state == "executing" and record.started_at == 0:
            record.started_at = time.time()
        if new_state in ("success", "failure", "stopped"):
            record.completed_at = time.time()

        self._save(record)
        log.info(f"[STATE] Mission {mission_id}: {old_state} → {new_state}")
        return True

    def set_clarification(self, mission_id: str, needed_params: List[str],
                          pending_questions: List[str]):
        """Set clarification state for a mission."""
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.clarification_state.needed_params = needed_params
        record.clarification_state.pending_questions = pending_questions
        self._save(record)

    def resolve_clarification(self, mission_id: str, param: str, value: str):
        """Resolve a single clarification parameter."""
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.clarification_state.clarified_params[param] = value
        if param in record.clarification_state.needed_params:
            record.clarification_state.needed_params.remove(param)
        record.clarification_state.clarification_history.append({
            "param": param, "value": value, "timestamp": time.time()
        })
        if not record.clarification_state.needed_params:
            record.clarification_state.is_complete = True
        self._save(record)

    def set_objectives(self, mission_id: str, objectives: List[str]):
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.objectives = objectives
        self._save(record)

    def set_subtasks(self, mission_id: str, subtasks: List[SubTask]):
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.subtasks = subtasks
        self._save(record)

    def update_subtask(self, mission_id: str, subtask_id: str,
                       status: str = None, result: dict = None,
                       verification: dict = None, error: str = None):
        """Update a specific subtask's status."""
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        for st in record.subtasks:
            if st.id == subtask_id:
                if status:
                    st.status = status
                    if status == "running" and st.started_at == 0:
                        st.started_at = time.time()
                    if status in ("completed", "failed"):
                        st.completed_at = time.time()
                if result:
                    st.result = result
                if verification:
                    st.verification = verification
                    if verification.get("passed"):
                        record.verified_steps.append(subtask_id)
                if error:
                    st.error = error
                break
        record.progress = record.compute_progress()
        self._save(record)

    def set_agents(self, mission_id: str, agents: List[Dict[str, Any]]):
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.agents = agents
        self._save(record)

    def set_graph_nodes(self, mission_id: str, nodes: Dict[str, Dict[str, Any]]):
        """Set the mission execution graph nodes."""
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.graph_nodes = nodes
        self._save(record)

    def update_progress(self, mission_id: str, progress: float, action: str = ""):
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.progress = progress
        if action:
            record.current_action = action
        self._save(record)

    def add_evidence(self, mission_id: str, action_type: str, description: str,
                     **kwargs) -> Optional[EvidenceEntry]:
        """Add evidence entry to a mission's ledger."""
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return None
        entry = record.add_evidence(action_type, description, **kwargs)
        self._save(record)
        return entry

    def add_source(self, mission_id: str, url: str, name: str,
                   **kwargs) -> Optional[Source]:
        """Add a verified source to a mission."""
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return None
        source = record.add_source(url, name, **kwargs)
        self._save(record)
        return source

    def add_artifact(self, mission_id: str, artifact_path: str):
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        if artifact_path not in record.artifacts:
            record.artifacts.append(artifact_path)
        self._save(record)

    def set_final_result(self, mission_id: str, result: Dict[str, Any]):
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return
        record.final_result = result
        self._save(record)

    def start_recovery(self, mission_id: str) -> bool:
        with self._lock:
            record = self._missions.get(mission_id)
        if not record:
            return False
        record.recovery_attempts += 1
        if record.recovery_attempts > record.max_recovery:
            record.state = "failure"
            record.add_error(f"Max recovery attempts ({record.max_recovery}) exhausted")
            record.completed_at = time.time()
            self._save(record)
            return False
        record.state = "recovering"
        self._save(record)
        return True

    def get(self, mission_id: str) -> Optional[MissionRecord]:
        with self._lock:
            return self._missions.get(mission_id)

    def list_all(self) -> List[MissionRecord]:
        with self._lock:
            return list(self._missions.values())

    def get_resumable(self) -> List[MissionRecord]:
        """Missions that were mid-execution when JARVIS crashed."""
        with self._lock:
            return [m for m in self._missions.values() if m.get_resumable_state()]

    def delete(self, mission_id: str):
        path = self._mission_path(mission_id)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        with self._lock:
            self._missions.pop(mission_id, None)

    def get_evidence(self, mission_id: str) -> List[EvidenceEntry]:
        """Get all evidence entries for a mission."""
        record = self.get(mission_id)
        return record.evidence if record else []

    def get_sources(self, mission_id: str) -> List[Source]:
        """Get all sources for a mission."""
        record = self.get(mission_id)
        return record.sources if record else []

    def get_mission_summary(self, mission_id: str) -> Dict[str, Any]:
        """Get a human-readable mission summary."""
        record = self.get(mission_id)
        if not record:
            return {"error": "Mission not found"}
        return {
            "id": record.id,
            "intent": record.user_intent,
            "state": record.state,
            "progress": f"{record.progress * 100:.0f}%",
            "risk_level": record.risk_level,
            "agents": len(record.agents),
            "subtasks": {
                "total": len(record.subtasks),
                "completed": sum(1 for s in record.subtasks if s.status == "completed"),
                "failed": sum(1 for s in record.subtasks if s.status == "failed"),
            },
            "evidence_count": len(record.evidence),
            "sources_count": len(record.sources),
            "artifacts_count": len(record.artifacts),
            "errors_count": len(record.errors),
            "recovery_attempts": record.recovery_attempts,
            "verification_state": record.verification_state,
            "duration_s": round(record.completed_at - record.started_at, 1) if record.completed_at else None,
        }


def validate_action(action: str, params: dict) -> tuple:
    """Validate an action against the allowed schema.

    Returns (ok: bool, error: str, risk_level: str).
    """
    if action not in ALLOWED_ACTIONS:
        return False, f"Unknown action: {action}", "unknown"

    spec = ALLOWED_ACTIONS[action]

    for req in spec["required"]:
        if req not in params:
            return False, f"Missing required param: {req}", spec["risk"]

    for key, val in params.items():
        if key in spec.get("validators", {}):
            if not spec["validators"][key](val):
                return False, f"Invalid value for {key}: {val}", spec["risk"]

    risk = spec["risk"]
    if action in HIGH_RISK_ACTIONS:
        risk = "high"

    return True, "", risk


_state_machine = None

def get_mission_state() -> MissionStateMachine:
    global _state_machine
    if _state_machine is None:
        _state_machine = MissionStateMachine()
    return _state_machine
