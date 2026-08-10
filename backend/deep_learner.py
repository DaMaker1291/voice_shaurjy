"""
Deep Learner — Meta-Cognitive Hypervisor
=========================================
The unified intelligence layer that synthesizes ALL learning subsystems into
a coherent, deep understanding of the user — their psychology, behavior patterns,
unconscious preferences, life narrative, and emotional landscape.

This is the system that makes JARVIS truly *know* the user:
  - Deep Psychological Profiling (Big Five, cognitive biases, attachment style)
  - Markov Chain Behavioral Prediction (anticipates what user will do next)
  - Unconscious Preference Mining (detects patterns user doesn't state)
  - Life Narrative Engine (builds coherent biography from fragmented data)
  - Deep Empathy Engine (multi-dimensional emotional understanding)
  - Meta-Cognitive Insight Synthesis (generates novel insights across dimensions)
"""

import json
import math
import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field

DB_DIR = Path(__file__).parent / "user_data"
DEEP_DB = DB_DIR / "deep_learner.db"


# ═══════════════════════════════════════════════════════════════════════════════
# PSYCHOLOGICAL DIMENSIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Big Five (OCEAN) traits — estimated from behavioral signals
BIG_FIVE_TRAITS = {
    "openness": {
        "label": "Openness to Experience",
        "signals": {
            "asks_why": 0.15, "uses_metaphor": 0.12, "discusses_ideas": 0.1,
            "tries_new_things": 0.12, "creative_language": 0.1, "curious_questions": 0.08,
            "philosophical_topics": 0.1, "explores_alternatives": 0.08,
        },
    },
    "conscientiousness": {
        "label": "Conscientiousness",
        "signals": {
            "mentions_deadlines": 0.12, "planned_language": 0.1, "organized_words": 0.08,
            "follows_up": 0.1, "detail_oriented": 0.08, "scheduled_actions": 0.1,
            "checks_progress": 0.08, "structured_requests": 0.06,
        },
    },
    "extraversion": {
        "label": "Extraversion",
        "signals": {
            "social_references": 0.12, "energetic_language": 0.1, "group_activities": 0.1,
            "seeks_interaction": 0.08, "enthusiastic_phrases": 0.08, "many_exclamation": 0.06,
            "initiates_conversation": 0.08, "collaborative_requests": 0.06,
        },
    },
    "agreeableness": {
        "label": "Agreeableness",
        "signals": {
            "polite_phrases": 0.12, "thanks_often": 0.1, "compromise_language": 0.1,
            "helpful_requests": 0.08, "empathetic_remarks": 0.08, "praise_others": 0.06,
            "patient_phrasing": 0.08, "collaborative_tone": 0.06,
        },
    },
    "neuroticism": {
        "label": "Neuroticism",
        "signals": {
            "anxious_words": 0.12, "frustration_expressions": 0.1, "uncertain_phrases": 0.1,
            "negative_emotions": 0.08, "worried_questions": 0.08, "perfectionist_tone": 0.06,
            "over_thinking": 0.08, "stress_mentions": 0.06,
        },
    },
}

# Cognitive bias detection patterns
COGNITIVE_BIASES = {
    "confirmation_bias": {
        "pattern": r"(just as I thought|I knew it|that proves|exactly what I expected)",
        "weight": 0.3,
    },
    "sunk_cost": {
        "pattern": r"(already invested|too much time spent|can't stop now|must continue)",
        "weight": 0.4,
    },
    "optimism_bias": {
        "pattern": r"(it will be fine|probably work out|sure it'll|likely succeed)",
        "weight": 0.25,
    },
    "availability_bias": {
        "pattern": r"(I remember when|that one time|just happened|always happens)",
        "weight": 0.2,
    },
    "anchoring": {
        "pattern": r"(compared to|that seems (expensive|cheap|high|low)|based on that)",
        "weight": 0.3,
    },
    "overconfidence": {
        "pattern": r"(definitely|absolutely|without question|I'm certain|guaranteed)",
        "weight": 0.25,
    },
    "dunning_kruger": {
        "pattern": r"(it's simple|just need to|easy to do|obviously|clearly)",
        "weight": 0.2,
    },
}

# Attachment style indicators
ATTACHMENT_STYLES = {
    "secure": {
        "patterns": [r"trust", r"confident", r"comfortable", r"balanced", r"flexible"],
        "weight": 0.2,
    },
    "anxious": {
        "patterns": [r"worried", r"nervous", r"overthink", r"need reassurance", r"panic"],
        "weight": 0.3,
    },
    "avoidant": {
        "patterns": [r"independent", r"alone", r"don't need", r"myself", r"space"],
        "weight": 0.25,
    },
    "fearful": {
        "patterns": [r"scared", r"confused", r"can't decide", r"mixed feelings", r"conflicted"],
        "weight": 0.25,
    },
}

# Core values / life priorities detection
CORE_VALUES = {
    "achievement": [r"success", r"goal", r"accomplish", r"achieve", r"win", r"ambition"],
    "security": [r"safe", r"stable", r"secure", r"protect", r"certain", r"guarantee"],
    "relationships": [r"family", r"friend", r"love", r"connection", r"together", r"community"],
    "growth": [r"learn", r"grow", r"improve", r"develop", r"progress", r"better"],
    "freedom": [r"free", r"choice", r"option", r"flexible", r"independent", r"control"],
    "knowledge": [r"understand", r"know", r"research", r"study", r"discover", r"curious"],
    "creativity": [r"create", r"design", r"imagine", r"inspire", r"express", r"art"],
    "health": [r"healthy", r"fit", r"exercise", r"wellness", r"energy", r"strong"],
}


@dataclass
class PsychologicalProfile:
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    confidence: float = 0.1
    cognitive_biases: dict = field(default_factory=dict)
    attachment_style: dict = field(default_factory=dict)
    core_values: dict = field(default_factory=dict)
    learning_style: str = "balanced"
    decision_style: str = "balanced"
    communication_depth: float = 0.5
    samples_analyzed: int = 0


@dataclass
class BehavioralPattern:
    trigger_action: str
    predicted_next: str
    transition_probability: float
    times_observed: int
    typical_time_hour: int = -1
    typical_day: int = -1


@dataclass
class UnconsciousPreference:
    domain: str
    inferred_preference: str
    confidence: float
    evidence: list = field(default_factory=list)
    contradictory: list = field(default_factory=list)


@dataclass
class LifeNarrativeEntry:
    period: str
    summary: str
    themes: list = field(default_factory=list)
    emotional_arc: str = ""
    key_events: list = field(default_factory=list)
    growth_areas: list = field(default_factory=list)


@dataclass
class EmpathyState:
    current_mood: str = "neutral"
    valence: float = 0.0
    arousal: float = 0.5
    stress_level: float = 0.3
    cognitive_load: float = 0.3
    need_dimensions: dict = field(default_factory=dict)
    support_style: str = "balanced"


@dataclass
class DeepInsight:
    dimension: str
    insight: str
    confidence: float
    evidence_count: int
    contradictory_evidence: int = 0
    actionable: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# DEEP LEARNER — THE META-COGNITIVE HYPERVISOR
# ═══════════════════════════════════════════════════════════════════════════════

class DeepLearner:
    """The unified meta-cognitive hypervisor for deep user understanding.

    Integrates ALL learning subsystems and adds:
    - Psychological profiling (Big Five, biases, attachment, values)
    - Behavioral prediction (Markov chain action forecasting)
    - Unconscious preference mining (latent pattern detection)
    - Life narrative construction (biographical coherence)
    - Deep empathy (multi-dimensional emotional intelligence)
    - Cross-dimensional insight synthesis
    """

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self._db_path = DEEP_DB
        self._local = threading.Lock()
        self._init_db()

        # In-memory caches for fast prediction
        self._action_history = deque(maxlen=500)
        self._text_history = deque(maxlen=200)
        self._markov_chain = defaultdict(lambda: Counter())
        self._temporal_patterns = defaultdict(lambda: Counter())

        # Empathy state (ephemeral, recalculated each time)
        self._empathy = EmpathyState()

        # Psychological profile
        self._psych = PsychologicalProfile()

        # Subsytem references (lazy-loaded)
        self._profile = None
        self._tracker = None
        self._mirror = None
        self._memory = None
        self._graph = None
        self._cortex = None

        self._load_cache()

    # ── Database Schema ─────────────────────────────────────────────

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS psych_profile (
                    user_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    from_action TEXT NOT NULL,
                    to_action TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    last_seen TEXT NOT NULL,
                    typical_hour INTEGER DEFAULT -1,
                    typical_day INTEGER DEFAULT -1,
                    UNIQUE(user_id, from_action, to_action)
                );
                CREATE TABLE IF NOT EXISTS latent_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    preference TEXT NOT NULL,
                    confidence REAL DEFAULT 0.1,
                    evidence TEXT DEFAULT '[]',
                    contradictory TEXT DEFAULT '[]',
                    last_updated TEXT NOT NULL,
                    UNIQUE(user_id, domain, preference)
                );
                CREATE TABLE IF NOT EXISTS life_narrative (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    period TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, period)
                );
                CREATE TABLE IF NOT EXISTS empathy_timeline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    mood TEXT NOT NULL,
                    valence REAL DEFAULT 0.0,
                    arousal REAL DEFAULT 0.5,
                    stress REAL DEFAULT 0.3,
                    cognitive_load REAL DEFAULT 0.3,
                    context TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS deep_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    evidence_count INTEGER DEFAULT 0,
                    contradictory_count INTEGER DEFAULT 0,
                    actionable TEXT DEFAULT '',
                    generated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS behavior_sequences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    sequence_4gram TEXT NOT NULL,
                    next_action TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    last_seen TEXT NOT NULL,
                    UNIQUE(user_id, sequence_4gram, next_action)
                );
                CREATE INDEX IF NOT EXISTS idx_transitions_user ON action_transitions(user_id);
                CREATE INDEX IF NOT EXISTS idx_prefs_user ON latent_preferences(user_id);
                CREATE INDEX IF NOT EXISTS idx_narrative_user ON life_narrative(user_id);
                CREATE INDEX IF NOT EXISTS idx_empathy_user ON empathy_timeline(user_id);
                CREATE INDEX IF NOT EXISTS idx_insights_user ON deep_insights(user_id);
                CREATE INDEX IF NOT EXISTS idx_sequences_user ON behavior_sequences(user_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _load_cache(self):
        """Load psychological profile from DB into memory."""
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                "SELECT data FROM psych_profile WHERE user_id = ?", (self.user_id,)
            ).fetchone()
            if row:
                data = json.loads(row[0])
                self._psych = PsychologicalProfile(**{
                    k: data.get(k, v) for k, v in {
                        "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5,
                        "agreeableness": 0.5, "neuroticism": 0.5, "confidence": 0.1,
                        "cognitive_biases": {}, "attachment_style": {},
                        "core_values": {}, "learning_style": "balanced",
                        "decision_style": "balanced", "communication_depth": 0.5,
                        "samples_analyzed": 0,
                    }.items()
                })
        finally:
            conn.close()

        # Load recent action history for Markov chain
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                "SELECT from_action, to_action, count FROM action_transitions WHERE user_id=? ORDER BY count DESC LIMIT 200",
                (self.user_id,)
            ).fetchall()
            for from_a, to_a, cnt in rows:
                self._markov_chain[from_a][to_a] = cnt
        finally:
            conn.close()

    # ── Lazy subsystem access ───────────────────────────────────────

    @property
    def profile(self):
        if self._profile is None:
            try:
                from user_profile import get_profile
                self._profile = get_profile(self.user_id)
            except Exception:
                pass
        return self._profile

    @property
    def tracker(self):
        if self._tracker is None:
            try:
                from feedback_tracker import get_tracker
                self._tracker = get_tracker(self.user_id)
            except Exception:
                pass
        return self._tracker

    @property
    def mirror(self):
        if self._mirror is None:
            try:
                from personality_mirror import get_mirror
                self._mirror = get_mirror(self.user_id)
            except Exception:
                pass
        return self._mirror

    @property
    def memory(self):
        if self._memory is None:
            try:
                from local_memory_engine import get_memory
                self._memory = get_memory(self.user_id)
            except Exception:
                pass
        return self._memory

    @property
    def graph(self):
        if self._graph is None:
            try:
                from graph_memory import memory as graph_mem
                self._graph = graph_mem
            except Exception:
                pass
        return self._graph

    @property
    def cortex(self):
        if self._cortex is None:
            try:
                from advanced_cortex import cortex
                self._cortex = cortex
            except Exception:
                pass
        return self._cortex

    # ═══════════════════════════════════════════════════════════════════
    # 1. DEEP PSYCHOLOGICAL PROFILING
    # ═══════════════════════════════════════════════════════════════════

    def analyze_psychology(self, text: str):
        """Analyze user text for psychological signals and update profile."""
        if not text or len(text) < 5:
            return

        lower = text.lower()
        self._text_history.append(lower)
        self._psych.samples_analyzed += 1

        # ── Update Big Five from signals ──
        trait_scores = defaultdict(float)
        trait_counts = defaultdict(int)

        for trait, config in BIG_FIVE_TRAITS.items():
            score = 0.0
            count = 0
            for signal, weight in config["signals"].items():
                # Check for signal patterns in text
                signal_patterns = {
                    "asks_why": r"\bwhy\b",
                    "uses_metaphor": r"\b(like|as if|reminds me|similar to|imagine)\b",
                    "discusses_ideas": r"\b(idea|concept|theory|thought|believe)\b",
                    "tries_new_things": r"\b(try|new|explore|experiment|different)\b",
                    "creative_language": r"\b(create|imagine|design|invent|original)\b",
                    "curious_questions": r"\?",
                    "philosophical_topics": r"\b(meaning|purpose|universe|life|existence)\b",
                    "explores_alternatives": r"\b(alternative|option|maybe|perhaps|consider)\b",
                    "mentions_deadlines": r"\b(deadline|due|schedule|timeline|by when)\b",
                    "planned_language": r"\b(plan|prepare|organize|arrange|ready)\b",
                    "organized_words": r"\b(first|second|finally|steps|process)\b",
                    "follows_up": r"\b(update|status|progress|check|how's it going)\b",
                    "detail_oriented": r"\b(specific|exactly|precise|detailed|particular)\b",
                    "scheduled_actions": r"\b(at \d|tomorrow|next week|on monday)\b",
                    "checks_progress": r"\b(done|finished|complete|remaining|left)\b",
                    "structured_requests": r"\b(please|can you|could you|would you)\b.*\?",
                    "social_references": r"\b(friend|party|group|meet|hang out|social)\b",
                    "energetic_language": r"\b(awesome|amazing|exciting|love|great!)\b",
                    "group_activities": r"\b(we|us|together|team|everyone|all)\b",
                    "seeks_interaction": r"\b(join|come|talk|chat|play|help me)\b",
                    "enthusiastic_phrases": r"!+",
                    "many_exclamation": r"!!+",
                    "initiates_conversation": r"^(hi|hey|hello|good morning|good evening)",
                    "collaborative_requests": r"\b(let's|shall we|how about|together we)\b",
                    "polite_phrases": r"\b(please|thank you|thanks|appreciate|grateful)\b",
                    "thanks_often": r"\b(thx|thanks|thank you|ty|appreciate)\b",
                    "compromise_language": r"\b(understand|fair|reasonable|okay|fine)\b",
                    "helpful_requests": r"\b(can I help|let me know|if you need|happy to)\b",
                    "empathetic_remarks": r"\b(sorry|hope|feel|must be|understand how)\b",
                    "praise_others": r"\b(great|excellent|good job|well done|impressive)\b",
                    "patient_phrasing": r"\b(when you can|whenever|no rush|take your time)\b",
                    "collaborative_tone": r"\b(together|we could|our|shared|mutual)\b",
                    "anxious_words": r"\b(worried|anxious|nervous|scared|afraid|panic)\b",
                    "frustration_expressions": r"\b(frustrat|annoy|tired of|sick of|enough)\b",
                    "uncertain_phrases": r"\b(maybe|perhaps|not sure|i don't know|maybe not)\b",
                    "negative_emotions": r"\b(sad|angry|upset|hate|terrible|awful)\b",
                    "worried_questions": r"\b(what if|suppose|worried about|concerned)\b",
                    "perfectionist_tone": r"\b(perfect|flawless|exactly right|must be)\b",
                    "over_thinking": r"\b(overthink|analyze too much|can't decide|paralysis)\b",
                    "stress_mentions": r"\b(stress|overwhelm|burnout|too much)\b",
                }
                pattern = signal_patterns.get(signal)
                if pattern and re.search(pattern, lower):
                    score += weight
                    count += 1

            if count > 0:
                trait_scores[trait] = score
                trait_counts[trait] = count

        # Smooth update with running average
        n = min(self._psych.samples_analyzed, 50)
        alpha = 1.0 / max(n, 1)

        for trait in BIG_FIVE_TRAITS:
            if trait in trait_scores:
                signal = min(1.0, trait_scores[trait] / 0.5)  # normalize
                current = getattr(self._psych, trait, 0.5)
                setattr(self._psych, trait, current * (1 - alpha) + signal * alpha)

        # Increase confidence with more samples
        self._psych.confidence = min(0.95, self._psych.samples_analyzed / 200.0)

        # ── Cognitive bias detection ──
        for bias, config in COGNITIVE_BIASES.items():
            if re.search(config["pattern"], lower):
                self._psych.cognitive_biases[bias] = (
                    self._psych.cognitive_biases.get(bias, 0) + config["weight"]
                )

        # ── Attachment style detection ──
        for style, config in ATTACHMENT_STYLES.items():
            matches = sum(1 for p in config["patterns"] if re.search(p, lower))
            if matches > 0:
                self._psych.attachment_style[style] = (
                    self._psych.attachment_style.get(style, 0) + matches * config["weight"]
                )

        # ── Core values ──
        for value, patterns in CORE_VALUES.items():
            matches = sum(1 for p in patterns if re.search(p, lower))
            if matches > 0:
                self._psych.core_values[value] = (
                    self._psych.core_values.get(value, 0) + matches * 0.1
                )

        # ── Learning style detection ──
        learning_signals = {
            "visual": [r"(see|look|show|picture|diagram|watch)", r"\b(image|video|chart)\b"],
            "auditory": [r"(hear|listen|tell|explain|say)", r"\b(podcast|audio|talk)\b"],
            "reading": [r"(read|article|book|text|document)", r"\b(write|note|paper)\b"],
            "kinesthetic": [r"(try|do|practice|build|hands.on)", r"\b(experiment|exercise)\b"],
        }
        learning_scores = {}
        for style, patterns in learning_signals.items():
            learning_scores[style] = sum(1 for p in patterns if re.search(p, lower))
        if learning_scores:
            best_style = max(learning_scores, key=learning_scores.get)
            if learning_scores[best_style] > 0:
                self._psych.learning_style = best_style

        # ── Decision style ──
        if re.search(r"\b(analyze|compare|evaluate|consider|research)\b", lower):
            self._psych.decision_style = "analytical"
        elif re.search(r"\b(trust|gut|feel|instinct|intuition)\b", lower):
            self._psych.decision_style = "intuitive"
        elif re.search(r"\b(decide|choose|pick|go with|commit)\b", lower):
            self._psych.decision_style = "decisive"

        # ── Communication depth ──
        avg_word_length = sum(len(w) for w in text.split()) / max(len(text.split()), 1)
        sentence_count = max(len(re.split(r'[.!?]+', text)) - 1, 1)
        avg_sentence_length = len(text.split()) / sentence_count

        depth = (min(avg_word_length / 8, 1) * 0.4 +
                 min(avg_sentence_length / 30, 1) * 0.3 +
                 (1.0 if self._psych.samples_analyzed > 10 else 0.0) * 0.3)
        self._psych.communication_depth = self._psych.communication_depth * (1 - alpha) + depth * alpha

        self._save_psych_profile()

    def _save_psych_profile(self):
        conn = sqlite3.connect(str(self._db_path))
        try:
            data = json.dumps({
                "openness": self._psych.openness,
                "conscientiousness": self._psych.conscientiousness,
                "extraversion": self._psych.extraversion,
                "agreeableness": self._psych.agreeableness,
                "neuroticism": self._psych.neuroticism,
                "confidence": self._psych.confidence,
                "cognitive_biases": dict(sorted(self._psych.cognitive_biases.items(),
                                                  key=lambda x: -x[1])),
                "attachment_style": dict(sorted(self._psych.attachment_style.items(),
                                                  key=lambda x: -x[1])),
                "core_values": dict(sorted(self._psych.core_values.items(),
                                             key=lambda x: -x[1])),
                "learning_style": self._psych.learning_style,
                "decision_style": self._psych.decision_style,
                "communication_depth": self._psych.communication_depth,
                "samples_analyzed": self._psych.samples_analyzed,
            })
            conn.execute(
                "INSERT OR REPLACE INTO psych_profile (user_id, data, updated_at) VALUES (?, ?, ?)",
                (self.user_id, data, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

    def get_psychological_profile(self) -> dict:
        """Return the full psychological profile."""
        return {
            "big_five": {
                "openness": round(self._psych.openness, 2),
                "conscientiousness": round(self._psych.conscientiousness, 2),
                "extraversion": round(self._psych.extraversion, 2),
                "agreeableness": round(self._psych.agreeableness, 2),
                "neuroticism": round(self._psych.neuroticism, 2),
            },
            "confidence": round(self._psych.confidence, 2),
            "top_trait": max(
                ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"],
                key=lambda t: getattr(self._psych, t, 0.5)
            ),
            "cognitive_biases": dict(sorted(self._psych.cognitive_biases.items(),
                                              key=lambda x: -x[1])[:5]),
            "attachment_style": dict(sorted(self._psych.attachment_style.items(),
                                              key=lambda x: -x[1])[:2]),
            "core_values": dict(sorted(self._psych.core_values.items(),
                                         key=lambda x: -x[1])[:5]),
            "learning_style": self._psych.learning_style,
            "decision_style": self._psych.decision_style,
            "communication_depth": round(self._psych.communication_depth, 2),
            "samples_analyzed": self._psych.samples_analyzed,
        }

    # ═══════════════════════════════════════════════════════════════════
    # 2. BEHAVIORAL PREDICTION (Markov Chain)
    # ═══════════════════════════════════════════════════════════════════

    def observe_action(self, action: str, context: Optional[dict] = None):
        """Record an action and update Markov chain prediction model."""
        now = datetime.now()

        if self._action_history:
            prev = self._action_history[-1]
            key = (prev, action)

            # Update in-memory Markov chain
            self._markov_chain[prev][action] += 1

            # Update DB
            conn = sqlite3.connect(str(self._db_path))
            try:
                hour = now.hour
                day = now.weekday()
                conn.execute(
                    """INSERT INTO action_transitions (user_id, from_action, to_action, count, last_seen, typical_hour, typical_day)
                       VALUES (?, ?, ?, 1, ?, ?, ?)
                       ON CONFLICT(user_id, from_action, to_action) DO UPDATE SET
                           count = count + 1,
                           last_seen = ?,
                           typical_hour = (? + typical_hour) / 2,
                           typical_day = (? + typical_day) / 2""",
                    (self.user_id, prev, action, now.isoformat(), hour, day,
                     now.isoformat(), hour, day)
                )
                conn.commit()
            finally:
                conn.close()

            # Learn 4-gram sequences
            hist = list(self._action_history)
            if len(hist) >= 4:
                seq = "|".join(hist[-4:])
                conn = sqlite3.connect(str(self._db_path))
                try:
                    conn.execute(
                        """INSERT INTO behavior_sequences (user_id, sequence_4gram, next_action, count, last_seen)
                           VALUES (?, ?, ?, 1, ?)
                           ON CONFLICT(user_id, sequence_4gram, next_action) DO UPDATE SET
                               count = count + 1,
                               last_seen = ?""",
                        (self.user_id, seq, action, now.isoformat(), now.isoformat())
                    )
                    conn.commit()
                finally:
                    conn.close()

        self._action_history.append(action)

    def predict_next_action(self, top_k: int = 3) -> list[dict]:
        """Predict the user's most likely next action using Markov chain."""
        if not self._action_history:
            return []

        last = self._action_history[-1]
        transitions = self._markov_chain.get(last, {})
        total = sum(transitions.values())
        if total == 0:
            return []

        predictions = sorted(
            [(action, count / total) for action, count in transitions.items()],
            key=lambda x: -x[1]
        )

        return [
            {"action": action, "probability": round(prob, 3)}
            for action, prob in predictions[:top_k]
        ]

    def predict_from_sequence(self, top_k: int = 3) -> list[dict]:
        """Predict from 4-gram sequence patterns."""
        hist = list(self._action_history)
        if len(hist) < 4:
            return []

        seq = "|".join(hist[-4:])
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                """SELECT next_action, count FROM behavior_sequences
                   WHERE user_id=? AND sequence_4gram=?
                   ORDER BY count DESC LIMIT ?""",
                (self.user_id, seq, top_k)
            ).fetchall()
            if not rows:
                return []
            total = sum(r[1] for r in rows)
            return [
                {"action": r[0], "probability": round(r[1] / total, 3)}
                for r in rows
            ]
        finally:
            conn.close()

    def get_temporal_predictions(self) -> list[dict]:
        """Get time-aware predictions based on current hour/day."""
        now = datetime.now()
        hour = now.hour
        day = now.weekday()

        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                """SELECT to_action, COUNT(*) as cnt FROM action_transitions
                   WHERE user_id=? AND typical_hour=? AND typical_day=?
                   GROUP BY to_action ORDER BY cnt DESC LIMIT 5""",
                (self.user_id, hour, day)
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            # Fallback: just by hour
            conn = sqlite3.connect(str(self._db_path))
            try:
                rows = conn.execute(
                    """SELECT to_action, COUNT(*) as cnt FROM action_transitions
                       WHERE user_id=? AND typical_hour=?
                       GROUP BY to_action ORDER BY cnt DESC LIMIT 5""",
                    (self.user_id, hour)
                ).fetchall()
            finally:
                conn.close()

        total = sum(r[1] for r in rows) if rows else 1
        return [
            {"action": r[0], "probability": round(r[1] / total, 3), "context": f"at {hour}:00 on weekday {day}"}
            for r in rows[:top_k] if rows
        ]

    # ═══════════════════════════════════════════════════════════════════
    # 3. UNCONSCIOUS PREFERENCE MINING
    # ═══════════════════════════════════════════════════════════════════

    def mine_unconscious_preferences(self) -> list[UnconsciousPreference]:
        """Detect preferences the user has never explicitly stated.

        Analyzes behavioral patterns, corrections, action sequences, and
        timing to infer latent preferences.
        """
        preferences = []

        # ── From feedback tracker corrections ──
        if self.tracker:
            try:
                profile = self.tracker.profile
                comm = profile.get_communication_style()
                prefs = []

                if comm.brevity > 0.7 and comm.samples_analyzed > 10:
                    prefs.append(UnconsciousPreference(
                        domain="communication",
                        inferred_preference="short_responses",
                        confidence=comm.brevity * 0.8,
                        evidence=[f"Prefers brevity ({comm.brevity:.0%})"],
                    ))
                elif comm.brevity < 0.3 and comm.samples_analyzed > 10:
                    prefs.append(UnconsciousPreference(
                        domain="communication",
                        inferred_preference="detailed_responses",
                        confidence=(1 - comm.brevity) * 0.8,
                        evidence=[f"Prefers depth ({comm.brevity:.0%} brevity)"],
                    ))

                if comm.formality > 0.7:
                    prefs.append(UnconsciousPreference(
                        domain="tone",
                        inferred_preference="formal_tone",
                        confidence=comm.formality * 0.8,
                        evidence=["Consistently uses formal language"],
                    ))
                elif comm.formality < 0.3:
                    prefs.append(UnconsciousPreference(
                        domain="tone",
                        inferred_preference="casual_tone",
                        confidence=(1 - comm.formality) * 0.8,
                        evidence=["Consistently uses casual language"],
                    ))

                preferences.extend(prefs)

                # Store in DB
                for p in prefs:
                    self._store_latent_preference(p)
            except Exception:
                pass

        # ── From action timing patterns ──
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                """SELECT from_action, typical_hour, COUNT(*) as cnt
                   FROM action_transitions
                   WHERE user_id=?
                   GROUP BY from_action, typical_hour
                   HAVING cnt >= 3
                   ORDER BY cnt DESC LIMIT 10""",
                (self.user_id,)
            ).fetchall()

            time_prefs = defaultdict(list)
            for action, hour, cnt in rows:
                time_prefs[action].append((hour, cnt))

            for action, times in time_prefs.items():
                avg_hour = sum(h * c for h, c in times) / sum(c for _, c in times)
                if 6 <= avg_hour <= 10:
                    pref = "morning_routine"
                elif 11 <= avg_hour <= 14:
                    pref = "midday_task"
                elif 15 <= avg_hour <= 18:
                    pref = "afternoon_work"
                elif 19 <= avg_hour <= 23:
                    pref = "evening_activity"
                else:
                    pref = "late_night"

                p = UnconsciousPreference(
                    domain="timing",
                    inferred_preference=pref,
                    confidence=min(0.9, sum(c for _, c in times) / 20.0),
                    evidence=[f"Action '{action}' typically at {int(avg_hour)}:00 ({sum(c for _, c in times)} times)"],
                )
                preferences.append(p)
                self._store_latent_preference(p)
        finally:
            conn.close()

        return preferences

    def _store_latent_preference(self, pref: UnconsciousPreference):
        conn = sqlite3.connect(str(self._db_path))
        try:
            existing = conn.execute(
                "SELECT evidence, contradictory FROM latent_preferences WHERE user_id=? AND domain=? AND preference=?",
                (self.user_id, pref.domain, pref.inferred_preference)
            ).fetchone()
            if existing:
                evidence = json.loads(existing[0]) if existing[0] else []
                evidence = list(set(evidence + pref.evidence))[:20]
                contradictory = json.loads(existing[1]) if existing[1] else []
                conn.execute(
                    """UPDATE latent_preferences SET confidence=?, evidence=?, last_updated=?
                       WHERE user_id=? AND domain=? AND preference=?""",
                    (pref.confidence, json.dumps(evidence), datetime.now().isoformat(),
                     self.user_id, pref.domain, pref.inferred_preference)
                )
            else:
                conn.execute(
                    """INSERT INTO latent_preferences (user_id, domain, preference, confidence, evidence, contradictory, last_updated)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, pref.domain, pref.inferred_preference, pref.confidence,
                     json.dumps(pref.evidence), json.dumps(pref.contradictory),
                     datetime.now().isoformat())
                )
            conn.commit()
        finally:
            conn.close()

    def get_latent_preferences(self, min_confidence: float = 0.3) -> list[dict]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                """SELECT domain, preference, confidence, evidence, contradictory
                   FROM latent_preferences
                   WHERE user_id=? AND confidence >= ?
                   ORDER BY confidence DESC LIMIT 20""",
                (self.user_id, min_confidence)
            ).fetchall()
            return [
                {
                    "domain": r[0],
                    "preference": r[1],
                    "confidence": round(r[2], 2),
                    "evidence": json.loads(r[3]) if r[3] else [],
                    "contradictory": json.loads(r[4]) if r[4] else [],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # 4. LIFE NARRATIVE ENGINE
    # ═══════════════════════════════════════════════════════════════════

    def build_life_narrative(self) -> list[LifeNarrativeEntry]:
        """Construct a coherent biographical narrative from all stored memories."""
        entries = []
        now = datetime.now()

        # ── Get stored narratives ──
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                "SELECT period, data FROM life_narrative WHERE user_id=? ORDER BY period",
                (self.user_id,)
            ).fetchall()
            for period, data in rows:
                d = json.loads(data)
                entries.append(LifeNarrativeEntry(
                    period=period,
                    summary=d.get("summary", ""),
                    themes=d.get("themes", []),
                    emotional_arc=d.get("emotional_arc", ""),
                    key_events=d.get("key_events", []),
                    growth_areas=d.get("growth_areas", []),
                ))
        finally:
            conn.close()

        return entries

    def update_life_narrative(self):
        """Periodically update the life narrative from accumulated data."""
        now = datetime.now()
        month_key = now.strftime("%Y-%m")

        # Collect themes from psych profile
        psych = self.get_psychological_profile()
        themes = list(psych.get("core_values", {}).keys())[:3]
        top_trait = psych.get("top_trait", "balanced")

        # Build narrative summary from psychological state
        narrative_parts = []
        if psych.get("big_five", {}).get("openness", 0.5) > 0.6:
            narrative_parts.append("exploring new ideas and experiences")
        if psych.get("big_five", {}).get("conscientiousness", 0.5) > 0.6:
            narrative_parts.append("working with discipline and structure")
        if psych.get("big_five", {}).get("extraversion", 0.5) > 0.6:
            narrative_parts.append("engaging socially")
        if psych.get("big_five", {}).get("agreeableness", 0.5) > 0.6:
            narrative_parts.append("prioritizing harmony and connection")
        if psych.get("big_five", {}).get("neuroticism", 0.5) > 0.5:
            narrative_parts.append("navigating some emotional turbulence")

        summary = " and ".join(narrative_parts) if narrative_parts else "establishing patterns and routines"

        # Emotional arc from empathy timeline
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                "SELECT valence FROM empathy_timeline WHERE user_id=? ORDER BY timestamp DESC LIMIT 20",
                (self.user_id,)
            ).fetchall()
        finally:
            conn.close()

        if rows:
            valences = [r[0] for r in rows]
            avg_valence = sum(valences) / len(valences)
            if avg_valence > 0.3:
                emotional_arc = "generally positive"
            elif avg_valence < -0.2:
                emotional_arc = "some challenges"
            else:
                emotional_arc = "balanced"
            # Trend
            if len(valences) >= 5:
                recent = sum(valences[:5]) / 5
                older = sum(valences[-5:]) / 5
                if recent > older + 0.2:
                    emotional_arc += " with improving trajectory"
                elif recent < older - 0.2:
                    emotional_arc += " with declining trajectory"
        else:
            emotional_arc = "developing"

        entry = LifeNarrativeEntry(
            period=month_key,
            summary=summary,
            themes=themes,
            emotional_arc=emotional_arc,
            key_events=[],
            growth_areas=[top_trait],
        )

        conn = sqlite3.connect(str(self._db_path))
        try:
            data = json.dumps({
                "summary": entry.summary,
                "themes": entry.themes,
                "emotional_arc": entry.emotional_arc,
                "key_events": entry.key_events,
                "growth_areas": entry.growth_areas,
            })
            conn.execute(
                "INSERT OR REPLACE INTO life_narrative (user_id, period, data, created_at) VALUES (?, ?, ?, ?)",
                (self.user_id, month_key, data, now.isoformat())
            )
            conn.commit()
        finally:
            conn.close()

        return entry

    # ═══════════════════════════════════════════════════════════════════
    # 5. DEEP EMPATHY ENGINE
    # ═══════════════════════════════════════════════════════════════════

    def analyze_empathy_state(self, text: str) -> EmpathyState:
        """Analyze user text for deep emotional and cognitive state."""
        lower = text.lower()

        # ── Mood detection ──
        mood_map = {
            "happy": [r"\b(happy|glad|great|wonderful|fantastic|joy)\b", 0.6, 0.7],
            "sad": [r"\b(sad|unhappy|depressed|down|disappointed|grief)\b", -0.6, 0.3],
            "angry": [r"\b(angry|mad|furious|pissed|annoyed|irritated)\b", -0.5, 0.8],
            "anxious": [r"\b(anxious|worried|nervous|stressed|panicked|fear)\b", -0.3, 0.8],
            "frustrated": [r"\b(frustrat|stuck|can't|not working|broken|ugh)\b", -0.4, 0.7],
            "tired": [r"\b(tired|exhausted|drained|sleepy|burned out)\b", -0.2, 0.2],
            "excited": [r"\b(excited|thrilled|pumped|amazing|incredible)\b", 0.7, 0.9],
            "grateful": [r"\b(grateful|thankful|blessed|appreciate|fortunate)\b", 0.6, 0.4],
            "curious": [r"\b(curious|wonder|interest|intrigu|fascinat)\b", 0.3, 0.6],
            "neutral": [r".*", 0.0, 0.5],
        }

        best_mood = "neutral"
        best_score = 0
        best_valence = 0.0
        best_arousal = 0.5

        for mood, (pattern, valence, arousal) in mood_map.items():
            matches = len(re.findall(pattern, lower))
            score = matches / (len(lower.split()) + 1) * 10
            if score > best_score:
                best_score = score
                best_mood = mood
                best_valence = valence
                best_arousal = arousal

        # ── Stress level ──
        stress_patterns = [
            r"\b(deadline|urgent|critical|overwhelm|too much)\b",
            r"\b(stress|pressure|panic|emergency|crisis)\b",
            r"\b(behind|running late|hurry|rush|fast)\b",
        ]
        stress_count = sum(len(re.findall(p, lower)) for p in stress_patterns)
        stress = min(1.0, stress_count * 0.2)

        # ── Cognitive load ──
        load_patterns = [
            r"\b(confus|unclear|don't understand|complicated|complex)\b",
            r"\b(many|too many|multiple|various|several)\b.*\?",
            r"\b(help|how do|what does|explain|show me|teach)\b",
        ]
        load_count = sum(len(re.findall(p, lower)) for p in load_patterns)
        cognitive_load = min(1.0, load_count * 0.25)

        # ── Need dimensions ──
        needs = {}
        if re.search(r"\b(help|assist|support|aid|can you)\b", lower):
            needs["assistance"] = 0.8
        if re.search(r"\b(alone|isolat|lonely|by myself)\b", lower):
            needs["connection"] = 0.7
        if re.search(r"\b(know|understand|learn|figure out)\b", lower):
            needs["understanding"] = 0.7
        if re.search(r"\b(decide|choice|option|which|what should)\b", lower):
            needs["clarity"] = 0.7
        if re.search(r"\b(motivat|inspire|encourage|keep going)\b", lower):
            needs["encouragement"] = 0.7
        if re.search(r"\b(fix|solve|resolve|handle|deal with)\b", lower):
            needs["problem_solving"] = 0.7

        # ── Support style ──
        if stress > 0.6 or cognitive_load > 0.6:
            support_style = "empathetic_listener"
        elif needs.get("problem_solving", 0) > 0.5:
            support_style = "active_doer"
        elif needs.get("encouragement", 0) > 0.5:
            support_style = "motivator"
        elif needs.get("clarity", 0) > 0.5:
            support_style = "analytical_guide"
        else:
            support_style = "balanced"

        self._empathy = EmpathyState(
            current_mood=best_mood,
            valence=best_valence,
            arousal=best_arousal,
            stress_level=round(stress, 2),
            cognitive_load=round(cognitive_load, 2),
            need_dimensions=needs,
            support_style=support_style,
        )

        # Record to timeline
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """INSERT INTO empathy_timeline (user_id, timestamp, mood, valence, arousal, stress, cognitive_load, context)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.user_id, datetime.now().isoformat(), best_mood, best_valence,
                 best_arousal, stress, cognitive_load, text[:100])
            )
            conn.commit()
        finally:
            conn.close()

        return self._empathy

    def get_empathy_context(self) -> str:
        """Build empathy-aware prompt context."""
        e = self._empathy

        lines = ["\n===== DEEP EMPATHY STATE ====="]
        lines.append(f"Detected mood: {e.current_mood} (valence: {e.valence}, arousal: {e.arousal})")
        lines.append(f"Stress level: {e.stress_level:.0%}")
        lines.append(f"Cognitive load: {e.cognitive_load:.0%}")

        if e.need_dimensions:
            primary_need = max(e.need_dimensions, key=e.need_dimensions.get)
            lines.append(f"Primary need detected: {primary_need}")
            lines.append(f"Recommended support style: {e.support_style}")

        if e.stress_level > 0.5:
            lines.append("User appears stressed — respond with extra patience and clarity.")
        if e.cognitive_load > 0.5:
            lines.append("User may be cognitively overloaded — keep responses simple and structured.")

        needs_desc = {
            "assistance": "User needs practical help",
            "connection": "User may need social connection",
            "understanding": "User wants to understand something",
            "clarity": "User needs help making a decision",
            "encouragement": "User could use motivation",
            "problem_solving": "User wants a problem solved",
        }
        for need, desc in needs_desc.items():
            if e.need_dimensions.get(need, 0) > 0.5:
                lines.append(f"  - {desc}")

        lines.append("===== END DEEP EMPATHY STATE =====")
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════
    # 6. META-COGNITIVE INSIGHT SYNTHESIS
    # ═══════════════════════════════════════════════════════════════════

    def synthesize_insights(self) -> list[DeepInsight]:
        """Generate cross-dimensional insights about the user.

        Combines psychological profile, behavioral patterns, preferences,
        empathy history, and personality mirror to produce novel insights.
        """
        insights = []
        psych = self.get_psychological_profile()

        # ── Trait combination insights ──
        o = psych["big_five"]["openness"]
        c = psych["big_five"]["conscientiousness"]
        e = psych["big_five"]["extraversion"]
        a = psych["big_five"]["agreeableness"]
        n = psych["big_five"]["neuroticism"]

        if o > 0.6 and c > 0.6:
            insights.append(DeepInsight(
                dimension="cognitive_style",
                insight="You appear to be an 'exploring achiever' — someone who loves new ideas while maintaining structure. This combination is rare and powerful for innovation.",
                confidence=min(0.9, (o + c) / 2),
                evidence_count=psych["samples_analyzed"],
                actionable="Suggest creative projects with clear milestones",
            ))
        if o > 0.6 and e > 0.6:
            insights.append(DeepInsight(
                dimension="social_style",
                insight="You show traits of a 'social explorer' — energized by new experiences shared with others. You likely learn best through discussion and collaboration.",
                confidence=min(0.85, (o + e) / 2),
                evidence_count=psych["samples_analyzed"],
                actionable="Recommend group activities and collaborative tools",
            ))
        if c > 0.6 and n < 0.4:
            insights.append(DeepInsight(
                dimension="resilience",
                insight="You show high conscientiousness with low neuroticism — a profile associated with strong emotional resilience and reliable performance under pressure.",
                confidence=min(0.85, (c + (1 - n)) / 2),
                evidence_count=psych["samples_analyzed"],
                actionable="Can handle complex multi-step tasks autonomously",
            ))
        if a > 0.6 and e < 0.4:
            insights.append(DeepInsight(
                dimension="interaction_style",
                insight="You appear to be a 'quiet supporter' — highly agreeable but reserved. You may prefer thoughtful one-on-one interactions over group settings.",
                confidence=min(0.8, (a + (1 - e)) / 2),
                evidence_count=psych["samples_analyzed"],
                actionable="Respect personal space, offer thoughtful individual support",
            ))
        if n > 0.6 and o > 0.5:
            insights.append(DeepInsight(
                dimension="growth_edge",
                insight="Your combination of openness and sensitivity suggests deep emotional processing of new experiences. You likely benefit from reflection time after novel situations.",
                confidence=min(0.8, (n + o) / 2),
                evidence_count=psych["samples_analyzed"],
                actionable="Provide reflection prompts after new activities",
            ))

        # ── Core value insights ──
        values = psych.get("core_values", {})
        if values:
            top_value = max(values, key=values.get)
            value_descriptions = {
                "achievement": "driven by accomplishment and goal attainment",
                "security": "values stability and predictability",
                "relationships": "prioritizes connection with others",
                "growth": "focused on personal development",
                "freedom": "values independence and autonomy",
                "knowledge": "driven by curiosity and understanding",
                "creativity": "motivated by self-expression and creation",
                "health": "prioritizes physical and mental wellbeing",
            }
            if top_value in value_descriptions:
                insights.append(DeepInsight(
                    dimension="core_motivation",
                    insight=f"Your core motivation appears to be {value_descriptions[top_value]}. This is the value that most consistently shows up in your interactions.",
                    confidence=min(0.85, values[top_value]),
                    evidence_count=psych["samples_analyzed"],
                    actionable=f"Frame suggestions around {top_value} for maximum resonance",
                ))

        # ── Communication pattern insight ──
        if psych["communication_depth"] > 0.6:
            insights.append(DeepInsight(
                dimension="communication",
                insight="You tend to communicate with significant depth and nuance. You likely appreciate responses that match this depth rather than superficial replies.",
                confidence=min(0.8, psych["communication_depth"]),
                evidence_count=psych["samples_analyzed"],
                actionable="Provide detailed, well-structured responses",
            ))

        # ── Learning style insight ──
        ls = psych.get("learning_style", "balanced")
        if ls != "balanced":
            ls_desc = {
                "visual": "You seem to learn best through visual content — images, diagrams, and videos may resonate more than text.",
                "auditory": "You appear to learn well through listening — explanations, discussions, and audio content may work well.",
                "reading": "You seem to prefer learning through reading and writing — detailed text and documents work best.",
                "kinesthetic": "You appear to learn best by doing — hands-on practice and experimentation suit you.",
            }
            insights.append(DeepInsight(
                dimension="learning_preference",
                insight=ls_desc.get(ls, f"Your learning style appears to be {ls}."),
                confidence=0.6,
                evidence_count=psych["samples_analyzed"],
                actionable=f"Prefer {ls} learning modalities",
            ))

        # ── Cognitive bias patterns (growth opportunity) ──
        biases = psych.get("cognitive_biases", {})
        if biases:
            top_bias = max(biases, key=biases.get)
            bias_descriptions = {
                "confirmation_bias": "You may tend to favor information that confirms existing beliefs — a very human trait. Awareness of this can help in decision-making.",
                "sunk_cost": "You may sometimes continue investments (time/effort/money) due to what's already been put in, rather than objective future value.",
                "optimism_bias": "You tend toward optimism — generally healthy, but worth balancing with realistic planning.",
                "availability_bias": "You may sometimes overweigh recent or memorable events when making judgments.",
                "anchoring": "You may be influenced by first pieces of information encountered when making decisions.",
                "overconfidence": "You show confidence in your assessments — useful for action, but double-checking never hurts.",
                "dunning_kruger": "You may sometimes underestimate the complexity of unfamiliar domains.",
            }
            if top_bias in bias_descriptions and biases[top_bias] > 1.0:
                insights.append(DeepInsight(
                    dimension="cognitive_pattern",
                    insight=bias_descriptions[top_bias],
                    confidence=min(0.7, biases[top_bias] * 0.15),
                    evidence_count=int(biases[top_bias] * 5),
                    actionable="Be aware of this tendency in relevant situations",
                ))

        # Store insights
        conn = sqlite3.connect(str(self._db_path))
        try:
            now = datetime.now().isoformat()
            for ins in insights:
                conn.execute(
                    """INSERT INTO deep_insights (user_id, dimension, insight, confidence, evidence_count, contradictory_count, actionable, generated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, ins.dimension, ins.insight, ins.confidence,
                     ins.evidence_count, ins.contradictory_evidence, ins.actionable, now)
                )
            conn.commit()
        finally:
            conn.close()

        return insights

    def get_latest_insights(self, limit: int = 10) -> list[dict]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            rows = conn.execute(
                """SELECT dimension, insight, confidence, evidence_count, actionable, generated_at
                   FROM deep_insights WHERE user_id=?
                   ORDER BY generated_at DESC LIMIT ?""",
                (self.user_id, limit)
            ).fetchall()
            return [
                {
                    "dimension": r[0],
                    "insight": r[1],
                    "confidence": round(r[2], 2),
                    "evidence_count": r[3],
                    "actionable": r[4],
                    "generated_at": r[5],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # MASTER PROCESS — Called on every user interaction
    # ═══════════════════════════════════════════════════════════════════

    def process_interaction(self, user_text: str, action_taken: Optional[str] = None):
        """Master method — called on every user interaction to update ALL learning systems."""
        # 1. Psychological profiling
        self.analyze_psychology(user_text)

        # 2. Empathy analysis
        self.analyze_empathy_state(user_text)

        # 3. Behavioral tracking (if action taken)
        if action_taken:
            self.observe_action(action_taken)

        # 4. Periodic unconscious preference mining (every 10 interactions)
        if self._psych.samples_analyzed % 10 == 0:
            self.mine_unconscious_preferences()

        # 5. Periodic life narrative update (every 20 interactions)
        if self._psych.samples_analyzed % 20 == 0:
            self.update_life_narrative()

        # 6. Periodic insight synthesis (every 30 interactions)
        if self._psych.samples_analyzed % 30 == 0:
            self.synthesize_insights()

    # ═══════════════════════════════════════════════════════════════════
    # CONTEXT BUILDING — for injection into LLM prompts
    # ═══════════════════════════════════════════════════════════════════

    def build_deep_context(self) -> str:
        """Build the complete deep learning context for LLM injection."""
        sections = []

        # ── Psychological Profile ──
        psych = self.get_psychological_profile()
        if psych["confidence"] > 0.2:
            lines = ["\n===== DEEP PSYCHOLOGICAL PROFILE ====="]
            bf = psych["big_five"]
            lines.append(f"Big Five: O={bf['openness']:.0%} C={bf['conscientiousness']:.0%} "
                         f"E={bf['extraversion']:.0%} A={bf['agreeableness']:.0%} N={bf['neuroticism']:.0%}")
            lines.append(f"Confidence: {psych['confidence']:.0%} (based on {psych['samples_analyzed']} interactions)")

            traits = []
            if bf["openness"] > 0.6:
                traits.append("open to new experiences")
            if bf["conscientiousness"] > 0.6:
                traits.append("organized and dependable")
            if bf["extraversion"] > 0.6:
                traits.append("socially engaged")
            if bf["agreeableness"] > 0.6:
                traits.append("cooperative and empathetic")
            if bf["neuroticism"] > 0.5:
                traits.append("emotionally sensitive")
            if traits:
                lines.append(f"Profile: {', '.join(traits)}")

            values = psych.get("core_values", {})
            if values:
                top_values = sorted(values.items(), key=lambda x: -x[1])[:3]
                lines.append(f"Core values: {', '.join(v[0] for v in top_values)}")

            biases = psych.get("cognitive_biases", {})
            if biases:
                top_bias = max(biases, key=biases.get)
                if biases[top_bias] > 1.0:
                    lines.append(f"Notable cognitive pattern: {top_bias}")

            lines.append(f"Decision style: {psych.get('decision_style', 'balanced')}")
            lines.append(f"Learning preference: {psych.get('learning_style', 'balanced')}")
            lines.append("===== END PSYCHOLOGICAL PROFILE =====")
            sections.append("\n".join(lines))

        # ── Empathy State ──
        emp_ctx = self.get_empathy_context()
        sections.append(emp_ctx)

        # ── Behavioral Predictions ──
        predictions = self.predict_next_action(top_k=3)
        if predictions:
            lines = ["\n===== BEHAVIORAL PREDICTIONS ====="]
            lines.append("Based on past patterns, user's most likely next actions:")
            for pred in predictions:
                lines.append(f"  - {pred['action']} ({pred['probability']:.0%} probability)")
            lines.append("===== END BEHAVIORAL PREDICTIONS =====")
            sections.append("\n".join(lines))

        # ── Latent Preferences ──
        prefs = self.get_latent_preferences(min_confidence=0.4)
        if prefs:
            lines = ["\n===== LATENT PREFERENCES (user has never explicitly stated) ====="]
            for p in prefs[:5]:
                lines.append(f"  - [{p['domain']}] {p['preference']} (confidence: {p['confidence']:.0%})")
            lines.append("===== END LATENT PREFERENCES =====")
            sections.append("\n".join(lines))

        # ── Life Narrative ──
        narrative = self.build_life_narrative()
        if narrative:
            latest = narrative[-1]
            lines = ["\n===== LIFE NARRATIVE ====="]
            lines.append(f"Current period ({latest.period}): {latest.summary}")
            if latest.themes:
                lines.append(f"Themes: {', '.join(latest.themes)}")
            if latest.emotional_arc:
                lines.append(f"Emotional arc: {latest.emotional_arc}")
            lines.append("===== END LIFE NARRATIVE =====")
            sections.append("\n".join(lines))

        # ── Deep Insights ──
        insights = self.get_latest_insights(limit=3)
        if insights:
            lines = ["\n===== DEEP INSIGHTS ABOUT YOU ====="]
            for ins in insights:
                lines.append(f"  [{ins['dimension']}] {ins['insight']} (confidence: {ins['confidence']:.0%})")
            lines.append("===== END DEEP INSIGHTS =====")
            sections.append("\n".join(lines))

        # ── Personal Data Context (files, projects, calendar) ──
        try:
            personal = self.get_personal_context()
            if personal:
                p_lines = ["\n===== PERSONAL DATA CONTEXT ====="]

                if personal.get("recent_files"):
                    files = personal["recent_files"][:4]
                    p_lines.append("Recently modified files: " + "; ".join(
                        f"{f['name']} ({f['when']})" for f in files
                    ))

                if personal.get("active_projects"):
                    projs = personal["active_projects"][:3]
                    p_lines.append("Active projects: " + "; ".join(
                        f"{p['name']} ({p['language']})" for p in projs
                    ))

                if personal.get("upcoming_events"):
                    for ev in personal["upcoming_events"][:2]:
                        loc = f" @ {ev['location']}" if ev.get("location") else ""
                        p_lines.append(f"Calendar: {ev['subject']}{loc} ({ev['start']})")

                if personal.get("top_topics"):
                    tops = personal["top_topics"][:5]
                    p_lines.append("User's key topics: " + ", ".join(t["topic"] for t in tops))

                if personal.get("peak_productivity"):
                    pk = personal["peak_productivity"]
                    p_lines.append(f"Peak productivity: ~{pk.get('peak_hour', 12)}:00")

                if personal.get("recent_emails"):
                    for em in personal["recent_emails"][:2]:
                        p_lines.append(f"Recent email from {em.get('from', 'unknown')}: {em.get('subject', '')}")

                p_lines.append("===== END PERSONAL DATA CONTEXT =====")
                sections.append("\n".join(p_lines))
        except Exception:
            pass

        return "\n\n".join(sections)

    # ═══════════════════════════════════════════════════════════════════
    # 7. PERSONAL DATA AWARENESS (files, projects, calendar, rhythm)
    # ═══════════════════════════════════════════════════════════════════

    def _get_ingestor(self):
        """Lazy-load personal data ingestor."""
        try:
            from personal_data_ingestor import get_ingestor
            return get_ingestor()
        except Exception:
            return None

    def get_personal_context(self, query: str = "") -> dict:
        """Build enriched personal context from all data sources."""
        ctx = {}
        ingestor = self._get_ingestor()
        if ingestor:
            try:
                ctx = ingestor.build_context(query)
            except Exception:
                ctx = {}
        return ctx

    def get_recent_activity_summary(self, max_items: int = 5) -> str:
        """Get a natural-language summary of recent user activity."""
        ctx = self.get_personal_context()
        parts = []

        # Recent files
        if ctx.get("recent_files"):
            files = ctx["recent_files"][:max_items]
            parts.append("Recent files: " + "; ".join(
                f"{f['name']} ({f['when']})" for f in files
            ))

        # Active projects
        if ctx.get("active_projects"):
            projects = ctx["active_projects"][:3]
            parts.append("Active projects: " + "; ".join(
                f"{p['name']} ({p['language']})" for p in projects
            ))

        # Upcoming events
        if ctx.get("upcoming_events"):
            events = ctx["upcoming_events"][:2]
            parts.append("Upcoming: " + "; ".join(
                f"{e['subject']} at {e['start']}" for e in events
            ))

        # Top interests
        if ctx.get("top_topics"):
            topics = ctx["top_topics"][:5]
            parts.append("Interests: " + ", ".join(t["topic"] for t in topics))

        # Peak productivity
        if ctx.get("peak_productivity"):
            parts.append(f"Productive hours: around {ctx['peak_productivity'].get('peak_hour', 12)}:00")

        return "\n".join(parts) if parts else "No personal data yet."

    def get_proactive_suggestions(self, max_suggestions: int = 3) -> list[str]:
        """Predict what the user might need right now."""
        ctx = self.get_personal_context()
        suggestions = []

        # Check for upcoming events
        if ctx.get("upcoming_events"):
            for event in ctx["upcoming_events"][:1]:
                if event.get("subject"):
                    suggestions.append(f"You have '{event['subject']}' coming up — want me to prepare anything?")

        # Check for active projects with recent activity
        if ctx.get("active_projects"):
            proj = ctx["active_projects"][0]
            suggestions.append(f"Want to continue working on {proj['name']}?")

        # Check for recent files context
        if ctx.get("recent_files") and len(ctx["recent_files"]) >= 2:
            suggestions.append("I noticed you've been working on several files — want me to help organize or summarize?")

        # Time-based suggestions
        hour = datetime.now().hour
        if hour < 12:
            suggestions.append("Good morning! Need help planning your day?")
        elif hour < 14:
            suggestions.append("Anything I can help with this afternoon?")
        elif hour < 18:
            suggestions.append("How's your day going? Need any help wrapping up tasks?")
        else:
            suggestions.append("Evening wind-down — need any help with tomorrow's planning?")

        return suggestions[:max_suggestions]

    def get_file_context_for_query(self, query: str) -> str:
        """Search personal files for context relevant to a query."""
        ingestor = self._get_ingestor()
        if not ingestor:
            return ""
        try:
            results = ingestor.search_files(query, limit=3)
            if results:
                lines = ["\n===== PERSONAL FILE CONTEXT ====="]
                for r in results:
                    lines.append(f"  - {r['name']} ({r['category']}, modified {r.get('modified', '')[:10]})")
                lines.append("===== END FILE CONTEXT =====")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    def get_rhythm_context(self) -> str:
        """Get user's daily rhythm and productivity patterns."""
        ingestor = self._get_ingestor()
        if not ingestor:
            return ""
        try:
            ctx = ingestor.build_context()
            if ctx.get("peak_productivity"):
                peak = ctx["peak_productivity"].get("peak_hour", 12)
                return f"\n===== USER RHYTHM =====\nUser is most productive around {peak}:00. Peak activity correlates with file/project work.\n===== END RHYTHM ====="
        except Exception:
            pass
        return ""

    def get_comprehensive_profile(self) -> dict:
        """Return every dimension of learning for the user in one dict."""
        return {
            "psychological": self.get_psychological_profile(),
            "empathy": {
                "current_mood": self._empathy.current_mood,
                "valence": self._empathy.valence,
                "arousal": self._empathy.arousal,
                "stress_level": self._empathy.stress_level,
                "cognitive_load": self._empathy.cognitive_load,
                "need_dimensions": self._empathy.need_dimensions,
                "support_style": self._empathy.support_style,
            },
            "behavioral_predictions": self.predict_next_action(top_k=5),
            "latent_preferences": self.get_latent_preferences(),
            "life_narrative": [
                {"period": e.period, "summary": e.summary, "themes": e.themes,
                 "emotional_arc": e.emotional_arc}
                for e in self.build_life_narrative()
            ],
            "deep_insights": self.get_latest_insights(limit=10),
            "action_history_count": len(self._action_history),
            "text_samples_analyzed": self._psych.samples_analyzed,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_learner_store: dict[str, DeepLearner] = {}

def get_deep_learner(user_id: str = "local") -> DeepLearner:
    if user_id not in _learner_store:
        _learner_store[user_id] = DeepLearner(user_id)
    return _learner_store[user_id]
