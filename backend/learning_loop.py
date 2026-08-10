"""JARVIS Learning Loop — Procedural Knowledge from Missions.

After each mission: What worked? What failed? What was fastest?
Stores procedural knowledge, not just conversation history.
"""

import os, sys, json, time, logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger("learning_loop")

LEARNING_PATH = Path("/opt/jarvis/learning.json")


@dataclass
class MissionRecord:
    mission_id: str
    objective: str
    status: str  # completed, partial, failed
    steps_total: int
    steps_completed: int
    steps_verified: int
    duration: float
    tools_used: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    recovery_actions: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    user_corrections: list = field(default_factory=list)
    strategy_used: str = ""
    fastest_tool: str = ""
    created_at: float = 0


@dataclass
class ProceduralKnowledge:
    """Learned patterns from past missions."""
    tool_reliability: dict = field(default_factory=dict)  # tool -> {success, fail, rate}
    strategy_effectiveness: dict = field(default_factory=dict)  # strategy -> {success, fail}
    failure_patterns: dict = field(default_factory=dict)  # failure_type -> {count, last_seen, recovery}
    domain_knowledge: dict = field(default_factory=dict)  # domain -> {what_worked, what_failed}
    user_preferences: dict = field(default_factory=dict)  # what the user corrects often


class LearningLoop:
    """Tracks mission outcomes and builds procedural knowledge."""

    def __init__(self):
        self.records: list[MissionRecord] = []
        self.knowledge = ProceduralKnowledge()
        self._load()

    def _load(self):
        if LEARNING_PATH.exists():
            try:
                data = json.loads(LEARNING_PATH.read_text())
                self.knowledge.tool_reliability = data.get("tool_reliability", {})
                self.knowledge.strategy_effectiveness = data.get("strategy_effectiveness", {})
                self.knowledge.failure_patterns = data.get("failure_patterns", {})
                self.knowledge.domain_knowledge = data.get("domain_knowledge", {})
                self.knowledge.user_preferences = data.get("user_preferences", {})
                for r in data.get("records", []):
                    self.records.append(MissionRecord(**r))
            except Exception:
                pass

    def save(self):
        data = {
            "tool_reliability": self.knowledge.tool_reliability,
            "strategy_effectiveness": self.knowledge.strategy_effectiveness,
            "failure_patterns": self.knowledge.failure_patterns,
            "domain_knowledge": self.knowledge.domain_knowledge,
            "user_preferences": self.knowledge.user_preferences,
            "records": [asdict(r) for r in self.records[-100:]],  # Keep last 100
        }
        LEARNING_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEARNING_PATH.write_text(json.dumps(data, indent=2))

    def record_mission(self, mission_id: str, objective: str, status: str,
                       steps_total: int, steps_completed: int, steps_verified: int,
                       duration: float, tools_used: list = None, failures: list = None,
                       recovery_actions: list = None, artifacts: list = None,
                       strategy_used: str = ""):
        """Record a completed mission and update knowledge."""
        record = MissionRecord(
            mission_id=mission_id,
            objective=objective,
            status=status,
            steps_total=steps_total,
            steps_completed=steps_completed,
            steps_verified=steps_verified,
            duration=duration,
            tools_used=tools_used or [],
            failures=failures or [],
            recovery_actions=recovery_actions or [],
            artifacts=artifacts or [],
            strategy_used=strategy_used,
            created_at=time.time(),
        )
        self.records.append(record)

        # Update tool reliability
        for tool in record.tools_used:
            if tool not in self.knowledge.tool_reliability:
                self.knowledge.tool_reliability[tool] = {"success": 0, "fail": 0}
            if record.status == "completed":
                self.knowledge.tool_reliability[tool]["success"] += 1
            else:
                self.knowledge.tool_reliability[tool]["fail"] += 1

        # Update failure patterns
        for failure in record.failures:
            ftype = failure.get("type", "unknown")
            if ftype not in self.knowledge.failure_patterns:
                self.knowledge.failure_patterns[ftype] = {"count": 0, "recoveries": {}}
            self.knowledge.failure_patterns[ftype]["count"] += 1
            self.knowledge.failure_patterns[ftype]["last_seen"] = time.time()
            recovery = failure.get("recovery", "none")
            rcounts = self.knowledge.failure_patterns[ftype]["recoveries"]
            rcounts[recovery] = rcounts.get(recovery, 0) + 1

        # Update strategy effectiveness
        if record.strategy_used:
            if record.strategy_used not in self.knowledge.strategy_effectiveness:
                self.knowledge.strategy_effectiveness[record.strategy_used] = {"success": 0, "fail": 0}
            key = "success" if record.status == "completed" else "fail"
            self.knowledge.strategy_effectiveness[record.strategy_used][key] += 1

        self.save()
        return record

    def record_user_correction(self, mission_id: str, correction: str):
        """Record when user corrects the system's output."""
        for r in self.records:
            if r.mission_id == mission_id:
                r.user_corrections.append({"correction": correction, "time": time.time()})
                # Track what the user corrects
                key = correction[:50]
                self.knowledge.user_preferences[key] = self.knowledge.user_preferences.get(key, 0) + 1
                self.save()
                return

    def get_tool_reliability(self, tool: str) -> dict:
        """Get reliability stats for a tool."""
        return self.knowledge.tool_reliability.get(tool, {"success": 0, "fail": 0})

    def get_best_strategy(self, domain: str = "") -> str:
        """Get the most effective strategy based on past missions."""
        if not self.knowledge.strategy_effectiveness:
            return "default"

        best = None
        best_rate = -1
        for strategy, stats in self.knowledge.strategy_effectiveness.items():
            total = stats["success"] + stats["fail"]
            if total < 2:
                continue
            rate = stats["success"] / total
            if rate > best_rate:
                best_rate = rate
                best = strategy
        return best or "default"

    def get_failure_recovery_advice(self, failure_type: str) -> dict:
        """Get advice on how to recover from a failure type based on history."""
        pattern = self.knowledge.failure_patterns.get(failure_type)
        if not pattern or not pattern.get("recoveries"):
            return {"advice": "No history for this failure type"}

        # Find the most successful recovery
        recoveries = pattern["recoveries"]
        best_recovery = max(recoveries, key=recoveries.get)
        return {
            "advice": f"Best recovery for {failure_type}: {best_recovery}",
            "recovery": best_recovery,
            "occurrences": pattern["count"],
        }

    def get_stats(self) -> dict:
        """Get overall learning statistics."""
        total = len(self.records)
        completed = sum(1 for r in self.records if r.status == "completed")
        failed = sum(1 for r in self.records if r.status == "failed")
        partial = sum(1 for r in self.records if r.status == "partial")

        avg_duration = 0
        if self.records:
            avg_duration = sum(r.duration for r in self.records) / total

        return {
            "total_missions": total,
            "completed": completed,
            "failed": failed,
            "partial": partial,
            "success_rate": f"{(completed/total*100):.1f}%" if total else "N/A",
            "avg_duration": f"{avg_duration:.1f}s",
            "tools_learned": len(self.knowledge.tool_reliability),
            "failure_patterns": len(self.knowledge.failure_patterns),
        }

    def get_trend(self, window: int = 10) -> dict:
        """Get trend over recent missions."""
        if len(self.records) < 2:
            return {"trend": "insufficient_data"}

        recent = self.records[-window:]
        old = self.records[-(window*2):-window] if len(self.records) >= window*2 else self.records[:window]

        recent_rate = sum(1 for r in recent if r.status == "completed") / len(recent)
        old_rate = sum(1 for r in old if r.status == "completed") / len(old) if old else 0

        direction = "improving" if recent_rate > old_rate else "declining" if recent_rate < old_rate else "stable"

        return {
            "trend": direction,
            "recent_success_rate": f"{recent_rate*100:.1f}%",
            "previous_success_rate": f"{old_rate*100:.1f}%",
            "recent_missions": len(recent),
        }


_loop: Optional[LearningLoop] = None

def get_learning_loop() -> LearningLoop:
    global _loop
    if _loop is None:
        _loop = LearningLoop()
    return _loop
