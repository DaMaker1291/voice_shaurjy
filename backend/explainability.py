"""JARVIS Explainability Engine — Why did JARVIS do that?

At any point, the user can ask:
> "Why did you do that?"

JARVIS can explain:
- What it observed
- What it decided
- Why it chose that action
- What it expected to happen
- What actually happened
- What it learned

This is critical for trust and debugging.
"""

import os
import json
import time
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

log = logging.getLogger("explainability")

EXPLAINABILITY_DIR = Path.home() / ".jarvis" / "explainability"
EXPLAINABILITY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DecisionRecord:
    """Record of a single decision made by JARVIS."""
    id: str
    mission_id: str
    timestamp: float
    observation: str
    decision: str
    action: str
    reason: str
    expected_outcome: str
    actual_outcome: str = ""
    success: bool = False
    context: Dict[str, Any] = field(default_factory=dict)
    alternatives_considered: List[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "timestamp": self.timestamp,
            "observation": self.observation,
            "decision": self.decision,
            "action": self.action,
            "reason": self.reason,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "success": self.success,
            "context": self.context,
            "alternatives_considered": self.alternatives_considered,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DecisionRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MissionTimeline:
    """Complete timeline of a mission for replay."""
    mission_id: str
    objective: str
    started_at: float
    completed_at: float = 0
    status: str = "active"
    decisions: List[DecisionRecord] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "decisions": [d.to_dict() for d in self.decisions],
            "artifacts_created": self.artifacts_created,
            "screenshots": self.screenshots,
            "events": self.events,
        }


class ExplainabilityEngine:
    """Records decisions and enables explainability."""

    def __init__(self):
        self._decisions: Dict[str, DecisionRecord] = {}
        self._timelines: Dict[str, MissionTimeline] = {}
        self._load()

    def _load(self):
        """Load explainability data from disk."""
        decisions_file = EXPLAINABILITY_DIR / "decisions.json"
        if decisions_file.exists():
            try:
                data = json.loads(decisions_file.read_text())
                for item in data:
                    record = DecisionRecord.from_dict(item)
                    self._decisions[record.id] = record
            except Exception as e:
                log.error(f"[EXPLAIN] Load failed: {e}")

        timelines_file = EXPLAINABILITY_DIR / "timelines.json"
        if timelines_file.exists():
            try:
                data = json.loads(timelines_file.read_text())
                for item in data:
                    timeline = MissionTimeline(
                        mission_id=item["mission_id"],
                        objective=item["objective"],
                        started_at=item["started_at"],
                        completed_at=item.get("completed_at", 0),
                        status=item.get("status", "active"),
                        artifacts_created=item.get("artifacts_created", []),
                        screenshots=item.get("screenshots", []),
                        events=item.get("events", []),
                        decisions=[DecisionRecord.from_dict(d) for d in item.get("decisions", [])],
                    )
                    self._timelines[timeline.mission_id] = timeline
            except Exception as e:
                log.error(f"[EXPLAIN] Timeline load failed: {e}")

    def _save(self):
        """Save explainability data to disk."""
        decisions_file = EXPLAINABILITY_DIR / "decisions.json"
        decisions_file.write_text(json.dumps(
            [d.to_dict() for d in self._decisions.values()], indent=2
        ))

        timelines_file = EXPLAINABILITY_DIR / "timelines.json"
        timelines_file.write_text(json.dumps(
            [t.to_dict() for t in self._timelines.values()], indent=2
        ))

    def record_decision(self, mission_id: str, observation: str, decision: str,
                       action: str, reason: str, expected_outcome: str,
                       context: Dict[str, Any] = None, alternatives: List[str] = None,
                       confidence: float = 0.0) -> DecisionRecord:
        """Record a decision for later explanation."""
        import uuid
        record = DecisionRecord(
            id=str(uuid.uuid4())[:8],
            mission_id=mission_id,
            timestamp=time.time(),
            observation=observation,
            decision=decision,
            action=action,
            reason=reason,
            expected_outcome=expected_outcome,
            context=context or {},
            alternatives_considered=alternatives or [],
            confidence=confidence,
        )
        self._decisions[record.id] = record

        # Add to timeline
        if mission_id in self._timelines:
            self._timelines[mission_id].decisions.append(record)
            self._timelines[mission_id].events.append({
                "type": "decision",
                "timestamp": record.timestamp,
                "action": action,
                "reason": reason[:100],
            })

        self._save()
        return record

    def record_outcome(self, decision_id: str, actual_outcome: str, success: bool,
                      evidence: Dict[str, Any] = None):
        """Record the actual outcome of a decision."""
        record = self._decisions.get(decision_id)
        if record:
            record.actual_outcome = actual_outcome
            record.success = success
            record.evidence = evidence or {}
            self._save()

    def explain_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Generate a human-readable explanation of a decision."""
        record = self._decisions.get(decision_id)
        if not record:
            return None

        explanation = f"""
JARVIS Decision Explanation
═══════════════════════════════════════

TIMESTAMP
{time.strftime('%H:%M:%S', time.localtime(record.timestamp))}

MISSION CONTEXT
{record.mission_id}

WHAT JARVIS OBSERVED
{record.observation}

WHAT JARVIS DECIDED
{record.decision}

ACTION TAKEN
{record.action}

REASONING
{record.reason}

EXPECTED OUTCOME
{record.expected_outcome}

ACTUAL OUTCOME
{record.actual_outcome or "Still pending..."}

SUCCESS
{"Yes" if record.success else "No"}

CONFIDENCE
{record.confidence}%
"""
        return {
            "decision": record.to_dict(),
            "explanation_text": explanation,
            "summary": f"JARVIS {record.action} because {record.reason}",
        }

    def start_mission(self, mission_id: str, objective: str) -> MissionTimeline:
        """Start recording a new mission timeline."""
        timeline = MissionTimeline(
            mission_id=mission_id,
            objective=objective,
            started_at=time.time(),
        )
        self._timelines[mission_id] = timeline
        self._save()
        return timeline

    def end_mission(self, mission_id: str, status: str = "completed"):
        """End a mission timeline."""
        timeline = self._timelines.get(mission_id)
        if timeline:
            timeline.completed_at = time.time()
            timeline.status = status
            self._save()

    def add_event(self, mission_id: str, event_type: str, data: Dict[str, Any]):
        """Add an event to a mission timeline."""
        timeline = self._timelines.get(mission_id)
        if timeline:
            timeline.events.append({
                "type": event_type,
                "timestamp": time.time(),
                **data,
            })
            self._save()

    def add_screenshot(self, mission_id: str, screenshot_path: str):
        """Add a screenshot to the mission timeline."""
        timeline = self._timelines.get(mission_id)
        if timeline:
            timeline.screenshots.append(screenshot_path)
            self._save()

    def add_artifact(self, mission_id: str, artifact_id: str):
        """Record an artifact created during a mission."""
        timeline = self._timelines.get(mission_id)
        if timeline:
            timeline.artifacts_created.append(artifact_id)
            self._save()

    def get_timeline(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Get the full timeline for a mission."""
        timeline = self._timelines.get(mission_id)
        if not timeline:
            return None
        return timeline.to_dict()

    def get_mission_summary(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a mission."""
        timeline = self._timelines.get(mission_id)
        if not timeline:
            return None

        total_decisions = len(timeline.decisions)
        successful = sum(1 for d in timeline.decisions if d.success)
        failed = total_decisions - successful

        duration = (timeline.completed_at or time.time()) - timeline.started_at

        return {
            "mission_id": mission_id,
            "objective": timeline.objective,
            "status": timeline.status,
            "duration_seconds": round(duration, 1),
            "total_decisions": total_decisions,
            "successful_decisions": successful,
            "failed_decisions": failed,
            "success_rate": round((successful / max(total_decisions, 1)) * 100, 1),
            "artifacts_created": len(timeline.artifacts_created),
            "total_events": len(timeline.events),
        }

    def list_missions(self) -> List[Dict[str, Any]]:
        """List all recorded missions."""
        return [self.get_mission_summary(mid) for mid in self._timelines.keys()]

    def replay_mission(self, mission_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get events for replaying a mission."""
        timeline = self._timelines.get(mission_id)
        if not timeline:
            return None

        replay_events = []
        for event in sorted(timeline.events, key=lambda e: e.get("timestamp", 0)):
            replay_events.append({
                "time": time.strftime('%H:%M:%S', time.localtime(event.get("timestamp", 0))),
                "type": event.get("type", ""),
                "description": event.get("description", event.get("action", "")),
                "data": {k: v for k, v in event.items() if k not in ("type", "timestamp")},
            })

        return replay_events

    def get_decisions_for_mission(self, mission_id: str) -> List[Dict[str, Any]]:
        """Get all decisions for a mission."""
        return [d.to_dict() for d in self._decisions.values() if d.mission_id == mission_id]

    def search_decisions(self, query: str) -> List[Dict[str, Any]]:
        """Search decisions by observation, reason, or action."""
        query_lower = query.lower()
        results = []
        for record in self._decisions.values():
            if (query_lower in record.observation.lower() or
                query_lower in record.reason.lower() or
                query_lower in record.action.lower()):
                results.append(record.to_dict())
        return results


# Global instance
_explain_engine = None


def get_explainability_engine() -> ExplainabilityEngine:
    global _explain_engine
    if _explain_engine is None:
        _explain_engine = ExplainabilityEngine()
    return _explain_engine
