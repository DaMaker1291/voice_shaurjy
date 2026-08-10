"""
Feedback & Behavior Tracker.
Captures implicit signals: text corrections, cancellations, daily routines,
explicit feedback. Feeds into the UserProfile to evolve trust scores and
communication style automatically.
"""
import difflib
import json
import re
import statistics
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from user_profile import UserProfile, get_profile


@dataclass
class CorrectionEvent:
    original_text: str
    corrected_text: str
    similarity_ratio: float
    action_type: str
    timestamp: str
    inferred_preferences: dict = field(default_factory=dict)


@dataclass
class RoutineObservation:
    hour: int
    minute: int
    weekday: int
    action_summary: str
    context_snapshot: dict = field(default_factory=dict)


class FeedbackTracker:
    def __init__(self, profile: Optional[UserProfile] = None):
        self._profile = profile
        self._recent_actions: list[dict] = []
        self._max_recent = 100

    @property
    def profile(self) -> UserProfile:
        if self._profile is None:
            self._profile = get_profile()
        return self._profile

    # ── Correction Analysis ────────────────────────────────────────

    def analyze_correction(self, original: str, corrected: str, action_type: str = "") -> CorrectionEvent:
        similarity = difflib.SequenceMatcher(None, original, corrected).ratio()
        prefs = self._infer_preferences_from_diff(original, corrected, similarity)

        event = CorrectionEvent(
            original_text=original,
            corrected_text=corrected,
            similarity_ratio=similarity,
            action_type=action_type or "unknown",
            timestamp=datetime.now().isoformat(),
            inferred_preferences=prefs,
        )

        self._apply_correction_preferences(prefs)
        self.profile.record_feedback_signal("correction", action_type, {
            "similarity": similarity, "preferences": prefs
        })

        if action_type:
            self.profile.record_action_outcome(action_type, success=True, user_corrected=True)

        return event

    def _infer_preferences_from_diff(self, original: str, corrected: str, similarity: float) -> dict:
        prefs = {}
        orig_lower = original.lower()
        corr_lower = corrected.lower()

        brevity_change = len(corrected) / max(len(original), 1)
        if brevity_change < 0.7:
            prefs["brevity_delta"] = 0.05
        elif brevity_change > 1.3:
            prefs["brevity_delta"] = -0.05

        # Formality signals
        formal_words = {"regards", "sincerely", "respectfully", "please", "kindly", "appreciate"}
        casual_words = {"hey", "yo", "sup", "cool", "awesome", "btw", "thx", "np"}
        orig_formal = sum(1 for w in formal_words if w in orig_lower)
        orig_casual = sum(1 for w in casual_words if w in orig_lower)
        corr_formal = sum(1 for w in formal_words if w in corr_lower)
        corr_casual = sum(1 for w in casual_words if w in corr_lower)

        formal_delta = corr_formal - orig_formal
        casual_delta = corr_casual - orig_casual
        if formal_delta > 0:
            prefs["formality_delta"] = 0.03 * formal_delta
        elif casual_delta > 0:
            prefs["formality_delta"] = -0.03 * casual_delta

        # Bullet/preference detection
        if "•" in corrected or "- " in corrected or "* " in corrected:
            prefs["preferred_response_format"] = "bullet"

        signoff_match = re.search(r'(?<=\n)(Best|Cheers|Regards|Sincerely|Thanks|Thx|Love|—?\w+),?\s*\w*$', corrected, re.MULTILINE)
        if signoff_match:
            prefs["email_signoff"] = signoff_match.group(0).strip()

        return prefs

    def _apply_correction_preferences(self, prefs: dict):
        comm = self.profile.get_communication_style()
        changed = False

        if "brevity_delta" in prefs:
            comm.brevity = max(0.0, min(1.0, comm.brevity + prefs["brevity_delta"]))
            changed = True
        if "formality_delta" in prefs:
            comm.formality = max(0.0, min(1.0, comm.formality + prefs["formality_delta"]))
            changed = True
        if "preferred_response_format" in prefs:
            comm.preferred_response_format = prefs["preferred_response_format"]
            self.profile.set_preference("response_format", prefs["preferred_response_format"])
            changed = True
        if "email_signoff" in prefs:
            comm.email_signoff = prefs["email_signoff"]
            changed = True

        if changed:
            self.profile.update_communication_style(
                brevity=comm.brevity,
                formality=comm.formality,
                preferred_response_format=comm.preferred_response_format,
                email_signoff=comm.email_signoff,
            )

    # ── Cancellation Tracking ──────────────────────────────────────

    def track_cancellation(self, action_type: str, context: str = ""):
        self.profile.record_action_outcome(action_type, success=False)
        self.profile.record_feedback_signal("cancellation", context, {
            "action_type": action_type
        })

    # ── Routine Detection ──────────────────────────────────────────

    def observe_action(self, action_type: str, params: Optional[dict] = None):
        now = datetime.now()
        obs = {
            "hour": now.hour,
            "minute": now.minute,
            "weekday": now.weekday(),
            "action": action_type,
            "params": params or {},
            "timestamp": now.isoformat(),
        }
        self._recent_actions.append(obs)
        if len(self._recent_actions) > self._max_recent:
            self._recent_actions = self._recent_actions[-self._max_recent:]
        self._detect_routines()

        # Also feed into deep learner
        try:
            from deep_user_learner import get_learner
            learner = get_learner()
            learner._learn_time_pattern(action_type, json.dumps(params or {}))
            learner._learn_app_usage(action_type, 0)
        except Exception:
            pass

    def _detect_routines(self):
        if len(self._recent_actions) < 5:
            return
        from collections import Counter
        time_slots = Counter()
        for a in self._recent_actions[-50:]:
            key = (a["hour"], a["minute"] // 15, a["action"])
            time_slots[key] += 1

        for (hour, quarter, action), count in time_slots.most_common(10):
            if count >= 3:
                days_seen = set()
                for a in self._recent_actions:
                    if a["hour"] == hour and (a["minute"] // 15) == quarter and a["action"] == action:
                        days_seen.add(a["weekday"])
                self.profile.learn_routine(hour, quarter * 15, sorted(days_seen), action)

    # ── Explicit Feedback ──────────────────────────────────────────

    def record_feedback(self, rating: int, action_type: str = "", comment: str = ""):
        if rating >= 4:
            self.profile.record_action_outcome(action_type, success=True)
            self.profile.record_feedback_signal("positive_feedback", action_type, {
                "rating": rating, "comment": comment
            })
        elif rating <= 2:
            self.profile.record_action_outcome(action_type, success=False)
            self.profile.record_feedback_signal("negative_feedback", action_type, {
                "rating": rating, "comment": comment
            })
        else:
            self.profile.record_feedback_signal("neutral_feedback", action_type, {
                "rating": rating, "comment": comment
            })

    # ── Communication Style Learning ───────────────────────────────

    def learn_from_user_text(self, text: str):
        text_lower = text.lower()
        comm = self.profile.get_communication_style()

        # Learn from how the user speaks to JARVIS
        brevity_words = len(text.split())
        if brevity_words <= 3:
            comm.brevity = min(1.0, comm.brevity + 0.02)
        elif brevity_words >= 50:
            comm.brevity = max(0.0, comm.brevity - 0.02)

        casual_markers = ["hey", "hi", "yo", "sup", "cool", "awesome", "lol", "idk", "btw", "thx", "np", "gonna", "wanna"]
        formal_markers = ["please", "kindly", "would you", "could you", "i would like", "i appreciate", "regards"]

        casual_count = sum(1 for m in casual_markers if m in text_lower)
        formal_count = sum(1 for m in formal_markers if m in text_lower)

        if casual_count > formal_count:
            comm.formality = max(0.0, comm.formality - 0.01)
        elif formal_count > casual_count:
            comm.formality = min(1.0, comm.formality + 0.01)

        # Relationship / entity extraction
        name_patterns = [
            r'(?:my|talk to|message|email|call)\s+(\w+(?:\s+\w+)?)(?:\s+is|\s+about|$)',
            r'(?:with|to)\s+(\w+(?:\s+\w+)?)(?:\s+on\s+|\s+about)',
        ]
        for pat in name_patterns:
            matches = re.findall(pat, text_lower)
            for m in matches:
                name = m.strip().title()
                if name.lower() not in ("me", "you", "my", "i", "the", "a", "an", "it"):
                    self.profile.upsert_relationship(name)

        self.profile.update_communication_style(
            brevity=comm.brevity,
            formality=comm.formality,
        )

    def get_personalization_summary(self) -> str:
        profile = self.profile.get_summary_for_prompt()
        recent_actions = self._recent_actions[-10:] if self._recent_actions else []
        if recent_actions:
            acts = ", ".join(a["action"] for a in recent_actions)
            profile += f"\nRecent actions: {acts}"
        return profile


# ── Singleton ──────────────────────────────────────────────────────
_tracker_store: dict[str, FeedbackTracker] = {}

def get_tracker(user_id: str = "local") -> FeedbackTracker:
    if user_id not in _tracker_store:
        _tracker_store[user_id] = FeedbackTracker()
    return _tracker_store[user_id]
