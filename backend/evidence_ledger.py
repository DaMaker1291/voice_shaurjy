"""JARVIS Per-Mission Evidence Ledger.

Aggregates actions, observations, sources, and verification results
into a single browsable record per mission.

This is the "mission activity log" that replaces raw chain-of-thought
exposure. Users see what JARVIS did and why, not internal reasoning.

Every entry is clickable and links to its evidence.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

log = logging.getLogger("evidence_ledger")


@dataclass
class ActionRecord:
    """A single action taken during mission execution."""
    id: str
    timestamp: float
    sequence: int
    action_type: str  # "web_search", "open_browser", "extract_price", "verify", etc.
    description: str  # Human-readable: "Opened supplier website"
    agent_id: str = ""
    agent_role: str = ""
    tool_used: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ObservationRecord:
    """A real-world observation after an action."""
    id: str
    timestamp: float
    sequence: int
    action_id: str  # Which action produced this observation
    observation_type: str  # "screenshot", "dom_content", "price_displayed", "file_created", etc.
    description: str  # "Price displayed: £1,287"
    data: Dict[str, Any] = field(default_factory=dict)
    source_url: str = ""
    screenshot_path: str = ""
    verified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VerificationRecord:
    """Verification that an action produced the expected result."""
    id: str
    timestamp: float
    sequence: int
    action_id: str
    observation_id: str
    expected: str  # What was expected
    actual: str    # What actually happened
    passed: bool
    method: str    # "screenshot_ocr", "dom_check", "file_exists", "price_match", etc.
    confidence: float = 1.0
    details: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TimelineEvent:
    """A single event in the mission timeline."""
    timestamp: float
    sequence: int
    event_type: str  # "action", "observation", "verification", "error", "recovery", "agent_created"
    summary: str     # "19:43 — 14 sources found"
    detail: str = ""
    linked_evidence: List[str] = field(default_factory=list)  # IDs of related records

    def to_dict(self) -> dict:
        return asdict(self)


class EvidenceLedger:
    """Per-mission evidence aggregation and timeline.

    Maintains a complete, browsable record of everything JARVIS did
    during a mission. Each number in the UI is clickable and links
    to its evidence.
    """

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.actions: List[ActionRecord] = []
        self.observations: List[ObservationRecord] = []
        self.verifications: List[VerificationRecord] = []
        self.timeline: List[TimelineEvent] = []
        self._sequence = 0
        self._action_counter = 0
        self._obs_counter = 0
        self._ver_counter = 0

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence

    def _timestamp_ms(self) -> float:
        return time.time() * 1000

    def record_action(self, action_type: str, description: str,
                      agent_id: str = "", agent_role: str = "",
                      tool_used: str = "", params: Dict[str, Any] = None,
                      result: Dict[str, Any] = None,
                      duration_ms: float = 0, success: bool = True,
                      error: str = "") -> ActionRecord:
        """Record an action taken by an agent."""
        self._action_counter += 1
        seq = self._next_seq()
        action = ActionRecord(
            id=f"a_{self.mission_id}_{self._action_counter}",
            timestamp=time.time(),
            sequence=seq,
            action_type=action_type,
            description=description,
            agent_id=agent_id,
            agent_role=agent_role,
            tool_used=tool_used,
            params=params or {},
            result=result or {},
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self.actions.append(action)

        # Add to timeline
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            sequence=seq,
            event_type="action",
            summary=description,
            detail=f"Agent: {agent_role or 'JARVIS'} | Tool: {tool_used or action_type}",
            linked_evidence=[action.id],
        ))

        log.debug(f"[EVIDENCE] Action #{seq}: {description}")
        return action

    def record_observation(self, action_id: str, observation_type: str,
                           description: str, data: Dict[str, Any] = None,
                           source_url: str = "",
                           screenshot_path: str = "") -> ObservationRecord:
        """Record a real-world observation after an action."""
        self._obs_counter += 1
        seq = self._next_seq()
        obs = ObservationRecord(
            id=f"o_{self.mission_id}_{self._obs_counter}",
            timestamp=time.time(),
            sequence=seq,
            action_id=action_id,
            observation_type=observation_type,
            description=description,
            data=data or {},
            source_url=source_url,
            screenshot_path=screenshot_path,
        )
        self.observations.append(obs)

        # Add to timeline
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            sequence=seq,
            event_type="observation",
            summary=description,
            detail=f"Type: {observation_type}",
            linked_evidence=[action_id, obs.id],
        ))

        log.debug(f"[EVIDENCE] Observation #{seq}: {description}")
        return obs

    def record_verification(self, action_id: str, observation_id: str,
                           expected: str, actual: str, passed: bool,
                           method: str = "", confidence: float = 1.0,
                           details: str = "") -> VerificationRecord:
        """Record a verification check."""
        self._ver_counter += 1
        seq = self._next_seq()
        ver = VerificationRecord(
            id=f"v_{self.mission_id}_{self._ver_counter}",
            timestamp=time.time(),
            sequence=seq,
            action_id=action_id,
            observation_id=observation_id,
            expected=expected,
            actual=actual,
            passed=passed,
            method=method,
            confidence=confidence,
            details=details,
        )
        self.verifications.append(ver)

        # Add to timeline
        status = "PASSED" if passed else "FAILED"
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            sequence=seq,
            event_type="verification",
            summary=f"Verification {status}: {expected}",
            detail=f"Expected: {expected} | Actual: {actual} | Method: {method}",
            linked_evidence=[action_id, observation_id, ver.id],
        ))

        log.debug(f"[EVIDENCE] Verification #{seq}: {status}")
        return ver

    def record_error(self, error: str, context: str = "",
                     agent_id: str = "", recovery_attempt: int = 0):
        """Record an error event."""
        seq = self._next_seq()
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            sequence=seq,
            event_type="error",
            summary=f"Error: {error[:80]}",
            detail=f"Context: {context} | Recovery attempt: {recovery_attempt}",
        ))

    def record_recovery(self, strategy: str, success: bool,
                       details: str = ""):
        """Record a recovery attempt."""
        seq = self._next_seq()
        status = "succeeded" if success else "failed"
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            sequence=seq,
            event_type="recovery",
            summary=f"Recovery {status}: {strategy}",
            detail=details,
        ))

    def record_agent_created(self, agent_id: str, role: str,
                            objective: str):
        """Record agent creation."""
        seq = self._next_seq()
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            sequence=seq,
            event_type="agent_created",
            summary=f"Created {role} agent: {objective[:60]}",
            detail=f"Agent ID: {agent_id}",
        ))

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the mission timeline for UI display."""
        events = self.timeline[-limit:]
        result = []
        for e in events:
            # Format timestamp as HH:MM
            t = time.localtime(e.timestamp)
            time_str = time.strftime("%H:%M", t)
            result.append({
                "time": time_str,
                "sequence": e.sequence,
                "type": e.event_type,
                "summary": e.summary,
                "detail": e.detail,
                "evidence_ids": e.linked_evidence,
            })
        return result

    def get_evidence_for_click(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Get evidence details when user clicks a number in the UI."""
        # Search actions
        for a in self.actions:
            if a.id == evidence_id:
                return {"type": "action", "data": a.to_dict()}
        # Search observations
        for o in self.observations:
            if o.id == evidence_id:
                return {"type": "observation", "data": o.to_dict()}
        # Search verifications
        for v in self.verifications:
            if v.id == evidence_id:
                return {"type": "verification", "data": v.to_dict()}
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get evidence statistics for the mission."""
        total_actions = len(self.actions)
        successful_actions = sum(1 for a in self.actions if a.success)
        total_verifications = len(self.verifications)
        passed_verifications = sum(1 for v in self.verifications if v.passed)
        total_observations = len(self.observations)
        unique_sources = len(set(
            o.source_url for o in self.observations if o.source_url
        ))

        return {
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "failed_actions": total_actions - successful_actions,
            "total_observations": total_observations,
            "total_verifications": total_verifications,
            "passed_verifications": passed_verifications,
            "failed_verifications": total_verifications - passed_verifications,
            "unique_sources": unique_sources,
            "timeline_events": len(self.timeline),
            "success_rate": f"{(successful_actions / total_actions * 100):.0f}%" if total_actions else "N/A",
            "verification_rate": f"{(passed_verifications / total_verifications * 100):.0f}%" if total_verifications else "N/A",
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export full evidence ledger."""
        return {
            "mission_id": self.mission_id,
            "actions": [a.to_dict() for a in self.actions],
            "observations": [o.to_dict() for o in self.observations],
            "verifications": [v.to_dict() for v in self.verifications],
            "timeline": [e.to_dict() for e in self.timeline],
            "stats": self.get_stats(),
        }


# ── Global registry (one ledger per mission) ──
_ledgers: Dict[str, EvidenceLedger] = {}


def get_evidence_ledger(mission_id: str) -> EvidenceLedger:
    """Get or create the evidence ledger for a mission."""
    if mission_id not in _ledgers:
        _ledgers[mission_id] = EvidenceLedger(mission_id)
    return _ledgers[mission_id]


def list_ledgers() -> List[str]:
    """List all active mission IDs with evidence ledgers."""
    return list(_ledgers.keys())
