"""
Context Injector.
Reads the learned UserProfile + FeedbackTracker + PersonalityMirror + SemanticMemory
and injects personalized directives into LLM prompts, system contexts, and routing decisions.
"""
from typing import Optional
from datetime import datetime

from user_profile import UserProfile, get_profile
from feedback_tracker import FeedbackTracker, get_tracker


class ContextInjector:
    def __init__(self, profile: Optional[UserProfile] = None, tracker: Optional[FeedbackTracker] = None,
                 user_id: str = "local"):
        self._profile = profile
        self._tracker = tracker
        self._user_id = user_id
        self._mirror = None
        self._memory = None
        self._memory_attempted = False

    @property
    def profile(self) -> UserProfile:
        if self._profile is None:
            self._profile = get_profile()
        return self._profile

    @property
    def tracker(self) -> FeedbackTracker:
        if self._tracker is None:
            self._tracker = get_tracker()
        return self._tracker

    @property
    def mirror(self):
        if self._mirror is None:
            try:
                from personality_mirror import get_mirror
                self._mirror = get_mirror(self._user_id)
            except Exception:
                self._mirror = None
        return self._mirror

    @property
    def memory(self):
        if self._memory is None and not self._memory_attempted:
            self._memory_attempted = True
            try:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
                with ThreadPoolExecutor(1) as pool:
                    future = pool.submit(self._load_memory)
                    self._memory = future.result(timeout=3)
            except Exception:
                self._memory = None
        return self._memory

    def _load_memory(self):
        from local_memory_engine import get_memory
        return get_memory(self._user_id)

    def build_system_prompt_suffix(self) -> str:
        c = self.profile.get_communication_style()
        trust = self.profile.get_trust_summary()
        now = datetime.now()

        lines = ["\n===== USER LEARNING CONTEXT ====="]

        # Inject deep learner context
        try:
            from deep_learner import get_deep_learner
            dl = get_deep_learner(self._user_id)
            deep_ctx = dl.build_deep_context()
            if deep_ctx:
                lines.append(deep_ctx)
        except Exception:
            pass

        directives = []
        if c.brevity > 0.6:
            directives.append("Keep responses concise and to the point.")
        elif c.brevity < 0.3:
            directives.append("Provide detailed, thorough responses.")
        if c.formality > 0.6:
            directives.append("Use formal language.")
        elif c.formality < 0.3:
            directives.append("Use casual, friendly language.")
        if c.preferred_response_format == "bullet":
            directives.append("Format responses as bullet points when listing information.")
        if c.email_signoff:
            directives.append(f"Default email sign-off: {c.email_signoff}")
        if c.default_channel:
            directives.append(f"Preferred communication channel: {c.default_channel}")

        if directives:
            lines.append("Communication preferences:")
            for d in directives:
                lines.append(f"  - {d}")

        rel = self.profile.get_relationship_summary()
        if rel:
            lines.append(f"Known relationships:\n{rel}")

        high_trust = {k: v for k, v in trust.items() if v["mode"] == "silent"}
        low_trust = {k: v for k, v in trust.items() if v["mode"] == "confirm" and v["total"] > 3}
        medium_trust = {k: v for k, v in trust.items() if v["mode"] == "notify"}

        if high_trust:
            lines.append("Fully trusted actions (execute silently, no confirmation needed):")
            for k in high_trust:
                lines.append(f"  - {k}")
        if medium_trust:
            lines.append("Semi-trusted actions (execute but notify user):")
            for k in medium_trust:
                lines.append(f"  - {k}")
        if low_trust:
            lines.append("Low-trust actions (ALWAYS ask user before executing):")
            for k in low_trust:
                lines.append(f"  - {k}")

        routines = self.profile.get_routines()
        if routines:
            active = [r for r in routines if r.confidence > 0.3]
            if active:
                lines.append("Learned routines (user typically does these at this time):")
                for r in active[:3]:
                    if r.trigger_hour == now.hour:
                        lines.append(f"  - {r.action_summary} (now)")

        if self.profile.profile.facts:
            recent = self.profile.profile.facts[-5:]
            lines.append("Learned user facts:")
            for f in recent:
                lines.append(f"  - {f['fact']}")

        # Personality mirror context
        if self.mirror:
            try:
                mirror_ctx = self.mirror.get_mirror_context()
                if mirror_ctx:
                    lines.append(mirror_ctx)
            except Exception:
                pass

        lines.append("===== END USER LEARNING CONTEXT =====")
        return "\n".join(lines)

    def build_semantic_context(self, query: str) -> str:
        """Add relevant past memories retrieved by semantic search. Skipped if memory is slow to load."""
        if self._memory is None and self._memory_attempted:
            return ""
        if self.memory:
            try:
                return self.memory.build_relevant_context(query, max_entries=4)
            except Exception:
                pass
        return ""

    def inject_into_prompt(self, base_prompt: str, query: str = "") -> str:
        parts = [base_prompt]
        suffix = self.build_system_prompt_suffix()
        parts.append(suffix)
        if query:
            semantic_ctx = self.build_semantic_context(query)
            if semantic_ctx:
                parts.append(f"\n{semantic_ctx}")
        return "\n".join(parts)

    def store_interaction_memory(self, user_input: str, response: str, success: bool = True):
        """Store an interaction in semantic memory for future recall."""
        if self.memory:
            try:
                self.memory.store("interaction",
                    f"User said: {user_input[:300]} | JARVIS responded with: {response[:200]}",
                    metadata={"success": success, "full_input": user_input[:500]})
            except Exception:
                pass

    def observe_user_text(self, text: str):
        """Feed user text to personality mirror and feedback tracker."""
        from feedback_tracker import get_tracker
        try:
            tracker = get_tracker(self._user_id)
            tracker.learn_from_user_text(text)
        except Exception:
            pass
        if self.mirror:
            try:
                self.mirror.observe_text(text)
            except Exception:
                pass

    def should_auto_execute(self, action_key: str) -> str:
        trust = self.profile.get_automation_trust(action_key)
        return trust.execution_mode

    def get_preferred_channel_for(self, entity: str) -> Optional[str]:
        rel = self.profile.get_relationship(entity)
        if rel and rel.preferred_channel:
            return rel.preferred_channel
        return self.profile.get_communication_style().default_channel or None

    def personalize_goal(self, goal: str) -> str:
        c = self.profile.get_communication_style()
        enhanced = goal
        if c.formality < 0.3 and not any(w in goal.lower() for w in ["formal", "professional"]):
            pass
        if c.brevity > 0.7:
            enhanced = f"{goal} (keep it short)"
        return enhanced

    def should_suggest_proactive(self) -> list[dict]:
        now = datetime.now()
        routines = self.profile.get_routines()
        suggestions = []
        for r in routines:
            if r.confidence > 0.4 and r.trigger_hour == now.hour:
                minutes_diff = abs(r.trigger_minute - now.minute)
                if minutes_diff <= 15:
                    suggestions.append({
                        "action": r.action_summary,
                        "confidence": r.confidence,
                        "trigger": f"{r.trigger_hour:02d}:{r.trigger_minute:02d}",
                    })
        return suggestions

    def get_learning_summary(self) -> dict:
        """Get a comprehensive summary of everything the system knows about the user."""
        result = {
            "profile": {
                "communication": {
                    "brevity": self.profile.get_communication_style().brevity,
                    "formality": self.profile.get_communication_style().formality,
                    "default_channel": self.profile.get_communication_style().default_channel,
                    "email_signoff": self.profile.get_communication_style().email_signoff,
                    "response_format": self.profile.get_communication_style().preferred_response_format,
                },
                "relationships": [
                    {"entity": r.entity, "relation": r.relation, "channel": r.preferred_channel}
                    for r in self.profile.profile.relationships
                ],
                "automation_trust": self.profile.get_trust_summary(),
                "facts": self.profile.profile.facts[-10:],
                "preferences": self.profile.profile.preferences,
                "routine_count": len(self.profile.get_routines()),
            }
        }
        if self.mirror:
            try:
                result["personality"] = self.mirror.get_stats()
            except Exception:
                pass
        if self.memory:
            try:
                result["memory"] = self.memory.get_memory_stats()
            except Exception:
                pass
        return result


# ── Singleton ──────────────────────────────────────────────────────
_injector_store: dict[str, ContextInjector] = {}

def get_injector(user_id: str = "local") -> ContextInjector:
    if user_id not in _injector_store:
        _injector_store[user_id] = ContextInjector(user_id=user_id)
    return _injector_store[user_id]