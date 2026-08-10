"""JARVIS Mission Replay — reconstruct what JARVIS did and why.

After completion, the user can watch the whole process.
This is incredibly useful for:
  - auditing
  - education
  - debugging
  - enterprise compliance
  - trust

The replay shows what JARVIS actually observed and did,
NOT the internal chain-of-thought of the model.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

log = logging.getLogger("mission_replay")


@dataclass
class ReplayEvent:
    """A single event in the mission replay."""
    timestamp: float
    elapsed_s: float
    event_type: str  # "action", "observation", "verification", "error", "recovery", "checkpoint"
    summary: str     # "Opened browser, searched for hotels"
    detail: str = ""
    agent_id: str = ""
    agent_role: str = ""
    tool_used: str = ""
    screenshot_path: str = ""
    source_url: str = ""
    result_summary: str = ""
    verification_result: str = ""  # "passed", "failed", ""
    linked_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MissionReplay:
    """Complete replay of a mission."""
    mission_id: str
    world_id: str = ""
    objective: str = ""
    started_at: float = 0
    completed_at: float = 0
    events: List[ReplayEvent] = field(default_factory=list)
    total_actions: int = 0
    total_verifications: int = 0
    passed_verifications: int = 0
    failed_verifications: int = 0
    errors: int = 0
    recoveries: int = 0
    sources_visited: int = 0
    final_result: str = ""
    status: str = "in_progress"

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "world_id": self.world_id,
            "objective": self.objective,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_s": self.completed_at - self.started_at if self.completed_at else 0,
            "events": [e.to_dict() for e in self.events],
            "summary": {
                "total_actions": self.total_actions,
                "total_verifications": self.total_verifications,
                "passed_verifications": self.passed_verifications,
                "failed_verifications": self.failed_verifications,
                "errors": self.errors,
                "recoveries": self.recoveries,
                "sources_visited": self.sources_visited,
            },
            "final_result": self.final_result,
            "status": self.status,
        }


class MissionReplayBuilder:
    """Builds a mission replay from evidence ledger and mission state."""

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self._replay = MissionReplay(mission_id=mission_id)

    def build_from_evidence(self, evidence_ledger) -> MissionReplay:
        """Build replay from an evidence ledger."""
        self._replay.started_at = evidence_ledger.actions[0].timestamp if evidence_ledger.actions else time.time()
        self._replay.completed_at = evidence_ledger.actions[-1].timestamp if evidence_ledger.actions else time.time()

        # Convert actions to replay events
        for action in evidence_ledger.actions:
            elapsed = action.timestamp - self._replay.started_at
            event = ReplayEvent(
                timestamp=action.timestamp,
                elapsed_s=elapsed,
                event_type="action",
                summary=action.description,
                detail=f"Agent: {action.agent_role or 'JARVIS'} | Tool: {action.tool_used or action.action_type}",
                agent_id=action.agent_id,
                agent_role=action.agent_role,
                tool_used=action.tool_used,
                result_summary=f"{'Success' if action.success else 'Failed'} ({action.duration_ms:.0f}ms)",
                linked_ids=[action.id],
            )
            self._replay.events.append(event)
            self._replay.total_actions += 1

        # Convert verifications to replay events
        for ver in evidence_ledger.verifications:
            elapsed = ver.timestamp - self._replay.started_at
            status = "PASSED" if ver.passed else "FAILED"
            event = ReplayEvent(
                timestamp=ver.timestamp,
                elapsed_s=elapsed,
                event_type="verification",
                summary=f"Verification {status}: {ver.expected}",
                detail=f"Expected: {ver.expected}\nActual: {ver.actual}\nMethod: {ver.method}",
                verification_result="passed" if ver.passed else "failed",
                linked_ids=[ver.action_id, ver.observation_id, ver.id],
            )
            self._replay.events.append(event)
            self._replay.total_verifications += 1
            if ver.passed:
                self._replay.passed_verifications += 1
            else:
                self._replay.failed_verifications += 1

        # Convert timeline events (errors, recoveries)
        for timeline_event in evidence_ledger.timeline:
            if timeline_event.event_type == "error":
                self._replay.errors += 1
                elapsed = timeline_event.timestamp - self._replay.started_at
                self._replay.events.append(ReplayEvent(
                    timestamp=timeline_event.timestamp,
                    elapsed_s=elapsed,
                    event_type="error",
                    summary=timeline_event.summary,
                    detail=timeline_event.detail,
                ))
            elif timeline_event.event_type == "recovery":
                self._replay.recoveries += 1
                elapsed = timeline_event.timestamp - self._replay.started_at
                self._replay.events.append(ReplayEvent(
                    timestamp=timeline_event.timestamp,
                    elapsed_s=elapsed,
                    event_type="recovery",
                    summary=timeline_event.summary,
                    detail=timeline_event.detail,
                ))

        # Sort events by timestamp
        self._replay.events.sort(key=lambda e: e.timestamp)

        # Count unique sources
        sources = set()
        for obs in evidence_ledger.observations:
            if obs.source_url:
                sources.add(obs.source_url)
        self._replay.sources_visited = len(sources)

        return self._replay

    def build_from_mission_state(self, mission_record) -> MissionReplay:
        """Build replay from a mission state record."""
        self._replay.started_at = mission_record.started_at
        self._replay.completed_at = mission_record.completed_at
        self._replay.objective = mission_record.user_intent
        self._replay.world_id = mission_record.workspace_id
        self._replay.status = mission_record.state

        # Convert evidence entries
        for entry in mission_record.evidence:
            elapsed = entry.timestamp - self._replay.started_at if self._replay.started_at else 0
            event = ReplayEvent(
                timestamp=entry.timestamp,
                elapsed_s=elapsed,
                event_type="action",
                summary=entry.description,
                detail=f"Type: {entry.action_type}",
                agent_id=entry.agent_id,
                agent_role=entry.agent_role,
                source_url=entry.source_url,
                screenshot_path=entry.screenshot_path,
                verification_result="passed" if entry.verification_passed else "",
                linked_ids=[entry.id],
            )
            self._replay.events.append(event)
            self._replay.total_actions += 1

        # Convert errors
        for error in mission_record.errors:
            elapsed = error.get("timestamp", 0) - self._replay.started_at if self._replay.started_at else 0
            self._replay.events.append(ReplayEvent(
                timestamp=error.get("timestamp", 0),
                elapsed_s=elapsed,
                event_type="error",
                summary=f"Error: {error.get('error', 'Unknown')}",
                detail=error.get("context", ""),
            ))
            self._replay.errors += 1

        # Sort by timestamp
        self._replay.events.sort(key=lambda e: e.timestamp)

        self._replay.sources_visited = len(mission_record.sources)
        self._replay.final_result = str(mission_record.final_result)

        return self._replay

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get a formatted timeline for UI display."""
        timeline = []
        for event in self._replay.events:
            # Format elapsed time as MM:SS
            minutes = int(event.elapsed_s // 60)
            seconds = int(event.elapsed_s % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"

            timeline.append({
                "time": time_str,
                "type": event.event_type,
                "summary": event.summary,
                "detail": event.detail,
                "verification": event.verification_result,
                "has_screenshot": bool(event.screenshot_path),
                "has_source": bool(event.source_url),
            })
        return timeline

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the mission for display."""
        duration = self._replay.completed_at - self._replay.started_at if self._replay.completed_at else 0
        return {
            "objective": self._replay.objective,
            "status": self._replay.status,
            "duration_s": round(duration, 1),
            "duration_human": self._format_duration(duration),
            "total_actions": self._replay.total_actions,
            "verifications": {
                "total": self._replay.total_verifications,
                "passed": self._replay.passed_verifications,
                "failed": self._replay.failed_verifications,
            },
            "errors": self._replay.errors,
            "recoveries": self._replay.recoveries,
            "sources_visited": self._replay.sources_visited,
            "final_result": self._replay.final_result,
        }

    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            mins = seconds / 60
            return f"{mins:.1fm"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
