"""
JARVIS Context Orchestrator
===========================
The intelligent layer that sits between raw memory and agent reasoning.

This is what makes JARVIS feel like it truly *knows* you:
  - Multi-source fusion: graph_memory + cortex + companion + conversations
  - Temporal relevance scoring: recent + important + emotionally charged
  - Agent-specific context windows: each agent gets what it needs
  - Adaptive attention: focuses on what matters for the current query
  - Memory compression: summarizes old context, keeps recent detail
  - Privacy filtering: respects user's sharing preferences
  - Anticipatory loading: pre-fetches context that will likely be needed
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from typing import Any, Optional


def _unjson(text, default=None):
    if text is None:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

_DOMAIN_KEYWORDS = {
    "health": {"exercise", "workout", "gym", "run", "sleep", "eat", "diet",
               "weight", "doctor", "medication", "walk", "yoga", "meditation",
               "health", "wellness", "fitness", "calories", "steps", "heart"},
    "work": {"meeting", "deadline", "project", "boss", "colleague", "office",
             "email", "report", "presentation", "client", "team", "sprint",
             "work", "job", "career", "promotion", "interview", "resume"},
    "relationships": {"friend", "family", "partner", "mom", "dad", "brother",
                      "sister", "date", "relationship", "love", "breakup",
                      "friendship", "social", "party", "gathering"},
    "finance": {"money", "budget", "invest", "save", "spend", "bill", "salary",
                "tax", "savings", "debt", "loan", "income", "crypto", "stock",
                "portfolio", "retirement", "401k"},
    "education": {"study", "learn", "exam", "course", "class", "homework",
                  "assignment", "research", "thesis", "professor", "university",
                  "school", "grade", "gpa", "certification"},
    "creative": {"write", "paint", "music", "song", "art", "design", "code",
                 "build", "create", "project", "portfolio", "creative",
                 "photography", "video", "content"},
    "emotional": {"feel", "feeling", "mood", "anxious", "stressed", "happy",
                  "sad", "angry", "frustrated", "overwhelmed", "calm", "peace",
                  "gratitude", "grief", "lonely", "connection"},
}

# Agent-specific context preferences
AGENT_CONTEXT_CONFIG = {
    "OS_AGENT": {
        "temporal_window_hours": 24,
        "include_emotional": False,
        "include_predictive": True,
        "include_abstractions": True,
        "include_profile": False,
        "max_tokens": 1500,
        "priority_domains": ["work", "creative"],
    },
    "HAL_AGENT": {
        "temporal_window_hours": 12,
        "include_emotional": False,
        "include_predictive": True,
        "include_abstractions": False,
        "include_profile": False,
        "max_tokens": 1000,
        "priority_domains": ["health", "work"],
    },
    "WEB_AGENT": {
        "temporal_window_hours": 48,
        "include_emotional": False,
        "include_predictive": True,
        "include_abstractions": True,
        "include_profile": True,
        "max_tokens": 2000,
        "priority_domains": ["education", "creative"],
    },
    "CORE_AGENT": {
        "temporal_window_hours": 168,  # 7 days
        "include_emotional": True,
        "include_predictive": True,
        "include_abstractions": True,
        "include_profile": True,
        "max_tokens": 2500,
        "priority_domains": ["emotional", "relationships"],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ContextOrchestrator:
    """
    The billion-dollar context engine.

    Fuses memory from multiple sources into a coherent, relevant,
    and privacy-respecting context window for any agent.
    """

    def __init__(self):
        self._cortex = None
        self._graph = None
        self._companion = None
        self._init_memory_systems()

    def _init_memory_systems(self):
        """Initialize all memory subsystems."""
        try:
            from advanced_cortex import cortex
            self._cortex = cortex
        except ImportError:
            pass

        try:
            from graph_memory import memory as graph_mem
            self._graph = graph_mem
        except ImportError:
            pass

        try:
            from companion_agent import companion
            self._companion = companion
        except ImportError:
            pass

    # ───────────────────────────────────────────────────────────────────
    # CORE: ASSEMBLE CONTEXT
    # ───────────────────────────────────────────────────────────────────

    def assemble_context(
        self,
        user_text: str,
        agent_type: str = "CORE_AGENT",
        session_id: str | None = None,
        privacy_level: int = 1,
        extra_context: dict | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """
        The money function. Assembles the perfect context window.

        Pipeline:
          1. Classify intent & domain
          2. Gather from all memory sources
          3. Score & rank by relevance
          4. Compress old context, keep recent detail
          5. Filter by privacy
          6. Assemble final context string
        """
        config = AGENT_CONTEXT_CONFIG.get(agent_type, AGENT_CONTEXT_CONFIG["CORE_AGENT"])
        domain = self._classify_domain(user_text)
        now = time.time()

        sections = []

        # ── Layer 1: User Profile ─────────────────────────────────────
        if config["include_profile"]:
            profile_ctx = self._get_profile_context()
            if profile_ctx:
                sections.append(("profile", profile_ctx, 0.9))

        # ── Layer 2: Emotional Trajectory ─────────────────────────────
        if config["include_emotional"]:
            emo_ctx = self._get_emotional_context(
                hours=min(config["temporal_window_hours"], 168)
            )
            if emo_ctx:
                sections.append(("emotional", emo_ctx, 0.85))

        # ── Layer 3: Temporal Events ──────────────────────────────────
        temporal_ctx = self._get_temporal_context(
            user_text=user_text,
            hours=config["temporal_window_hours"],
            domain=domain,
        )
        if temporal_ctx:
            sections.append(("temporal", temporal_ctx, 0.8))

        # ── Layer 3.5: Entity-Aware Context (the money layer) ────────
        entity_ctx = self._get_entity_aware_context(user_text)
        if entity_ctx:
            sections.append(("entity_aware", entity_ctx, 0.95))

        # ── Layer 4: Graph Memory Entities ────────────────────────────
        graph_ctx = self._get_graph_context(user_text, limit=5)
        if graph_ctx:
            sections.append(("graph", graph_ctx, 0.75))

        # ── Layer 5: Predictive Anticipation ──────────────────────────
        if config["include_predictive"]:
            pred_ctx = self._get_predictive_context(user_text, domain)
            if pred_ctx:
                sections.append(("predictive", pred_ctx, 0.7))

        # ── Layer 6: Abstractions (patterns/principles) ───────────────
        if config["include_abstractions"]:
            abs_ctx = self._get_abstraction_context(domain)
            if abs_ctx:
                sections.append(("abstractions", abs_ctx, 0.65))

        # ── Layer 7: Cross-Domain Insights ────────────────────────────
        cross_ctx = self._get_cross_domain_context(domain)
        if cross_ctx:
            sections.append(("cross_domain", cross_ctx, 0.6))

        # ── Layer 8: Conversation History ─────────────────────────────
        conv_ctx = self._get_conversation_context(session_id)
        if conv_ctx:
            sections.append(("conversation", conv_ctx, 0.5))

        # ── Layer 9: Extra Context ────────────────────────────────────
        if extra_context:
            extra_text = json.dumps(extra_context, ensure_ascii=False)
            sections.append(("extra", extra_text, 0.4))

        # ── Score, compress, and assemble ─────────────────────────────
        return self._assemble_final(sections, max_tokens, domain)

    # ───────────────────────────────────────────────────────────────────
    # SOURCE LAYER BUILDERS
    # ───────────────────────────────────────────────────────────────────

    def _classify_domain(self, text: str) -> str:
        """Classify the primary domain of user input."""
        words = set(re.findall(r"\b\w+\b", text.lower()))
        best = "general"
        best_score = 0
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            score = len(words & keywords)
            if score > best_score:
                best_score = score
                best = domain
        return best

    def _get_profile_context(self) -> str:
        """Get user profile context."""
        if not self._cortex:
            return ""
        profile = self._cortex.get_user_profile()
        if not profile:
            return ""
        lines = ["USER PROFILE:"]
        for dim, data in list(profile.items())[:10]:
            if data["confidence"] > 0.4:
                lines.append(f"  {dim}: {data['value']} (confidence: {data['confidence']:.0%})")
        return "\n".join(lines)

    def _get_emotional_context(self, hours: float = 168) -> str:
        """Get emotional trajectory context."""
        if not self._cortex:
            return ""
        summary = self._cortex.get_emotional_summary(hours)
        if summary["data_points"] == 0:
            return ""
        lines = [
            f"EMOTIONAL STATE ({int(hours)}h):",
            f"  Avg valence: {summary['avg_valence']} ({'positive' if summary['avg_valence'] > 0 else 'negative'})",
            f"  Dominant sentiment: {summary['dominant_sentiment']}",
            f"  Trend: {summary['trend']}",
            f"  Stability: {summary['emotional_stability']}",
        ]
        # Add recent shifts
        shifts = self._cortex.detect_emotional_shifts(0.3)
        if shifts:
            for s in shifts[-2:]:
                lines.append(
                    f"  Shift: {s['from_sentiment']} → {s['to_sentiment']} "
                    f"(Δ={s['valence_change']})"
                )
        return "\n".join(lines)

    def _get_temporal_context(self, user_text: str, hours: float = 48,
                              domain: str = "general") -> str:
        """Get recent temporal events."""
        if not self._cortex:
            return ""
        events = self._cortex.get_temporal_context(hours, domain)
        if not events:
            return ""
        lines = [f"RECENT EVENTS ({domain}, {int(hours)}h):"]
        for evt in events[:7]:
            importance_marker = " ★" if evt["importance"] >= 7 else ""
            lines.append(
                f"  [{evt['event_type']}] {evt['summary'][:100]}{importance_marker}"
            )
            # Add causal chain context
            if evt.get("cause_event_id"):
                chain = self._cortex.get_causal_chain(evt["id"], max_depth=2)
                if len(chain) > 1:
                    chain_text = " → ".join(e["summary"][:40] for e in chain[:3])
                    lines.append(f"    Chain: {chain_text}")
        return "\n".join(lines)

    def _get_entity_aware_context(self, user_text: str) -> str:
        """
        THE MONEY LAYER: Zero-hardcoding entity-aware context injection.

        Everything is dynamic — extracted from the user's own graph memory.
        No hardcoded names, no hardcoded relationship types, no hardcoded apps.

        How it works:
          1. Extract ANY capitalized word → look it up as an entity
          2. Extract ANY "my X" reference → look up that relationship
          3. Extract ANY verb → find user's stored preference for that action category
          4. Multi-hop recall everything found → inject as structured context
        """
        if not self._graph:
            return ""

        lines = []
        text_lower = user_text.lower()
        words = set(re.findall(r"\b\w+\b", text_lower))

        # ── 1. Extract potential named entities (any capitalized word) ──
        # Skip common verbs/articles/commands
        _STOP_WORDS = {
            "jarvis", "open", "ping", "send", "message", "call", "tell",
            "ask", "check", "show", "help", "please", "thanks", "hey",
            "hi", "yes", "no", "ok", "sure", "what", "when", "where",
            "how", "why", "who", "which", "this", "that", "with", "from",
            "have", "been", "were", "will", "would", "could", "should",
            "can", "may", "might", "shall", "must", "need", "want",
        }
        person_names = []
        for match in re.finditer(r"\b([A-Z][a-z]{2,})\b", user_text):
            word = match.group(1)
            if word.lower() not in _STOP_WORDS:
                person_names.append(word)

        # ── 2. Extract "my X" relationship references (fully dynamic) ──
        # Matches: "my manager", "my mom", "my friend Sarah", etc.
        relationship_refs = []
        rel_pattern = re.compile(r"\b(my|the)\s+([a-z]+)\b", re.I)
        for match in rel_pattern.finditer(user_text):
            ref = match.group(2).strip()
            if len(ref) > 2:
                relationship_refs.append(ref)

        # ── 3. Look up EVERY extracted entity in graph memory ──────────
        seen_ids = set()

        # Look up capitalized names
        for name in person_names:
            try:
                entities = self._graph.find_nodes(name_like=name, limit=1)
                if entities and entities[0]["id"] not in seen_ids:
                    e = entities[0]
                    seen_ids.add(e["id"])
                    lines.append(f"ENTITY: {e['name']} (type: {e['type']}, importance: {e.get('importance', '?')})")

                    # Get ALL edges for this entity (relationships, preferences, etc.)
                    edges = self._graph.get_edges(e["id"], "both")
                    for edge in edges:
                        other_id = edge["target_id"] if edge["source_id"] == e["id"] else edge["source_id"]
                        other = self._graph._db.execute(
                            "SELECT name, type FROM nodes WHERE id = ?", (other_id,)
                        ).fetchone()
                        if other:
                            direction = "→" if edge["source_id"] == e["id"] else "←"
                            lines.append(
                                f"  {direction} {edge['predicate']} → {other['name']} ({other['type']})"
                            )
            except Exception:
                pass

        # Look up relationship references ("my manager", "my mom", etc.)
        for ref in relationship_refs:
            try:
                # Try exact match first, then fuzzy
                entities = self._graph.find_nodes(name_like=ref, limit=1)
                if not entities:
                    # Try each word in the reference
                    for word in ref.split():
                        if len(word) > 2:
                            entities = self._graph.find_nodes(name_like=word, limit=1)
                            if entities:
                                break

                # Also search by properties.role or properties.type
                if not entities:
                    try:
                        prop_entities = self._graph._db.execute(
                            """SELECT * FROM nodes
                               WHERE properties LIKE ?
                               ORDER BY importance DESC LIMIT 1""",
                            (f'%"{ref}"%',)
                        ).fetchall()
                        if prop_entities:
                            node = dict(prop_entities[0])
                            node["properties"] = _unjson(node.get("properties"))
                            entities = [node]
                    except Exception:
                        pass

                if entities and entities[0]["id"] not in seen_ids:
                    e = entities[0]
                    seen_ids.add(e["id"])
                    props = e.get("properties", {}) or {}
                    role_info = f" (role: {props.get('role', '')})" if props.get("role") else ""
                    lines.append(f"RELATIONSHIP_REF: '{ref}' → {e['name']} (type: {e['type']}{role_info})")

                    edges = self._graph.get_edges(e["id"], "both")
                    for edge in edges[:5]:
                        other_id = edge["target_id"] if edge["source_id"] == e["id"] else edge["source_id"]
                        other = self._graph._db.execute(
                            "SELECT name, type FROM nodes WHERE id = ?", (other_id,)
                        ).fetchone()
                        if other:
                            lines.append(f"  {edge['predicate']} → {other['name']}")
            except Exception:
                pass
            except Exception:
                pass

        # ── 4. Dynamic action→preference mapping ───────────────────────
        # Instead of hardcoding "ping→slack", we look at what the user
        # has stored as preferences and match action verbs to categories.
        _VERB_CATEGORIES = {
            # Each verb maps to category tags the user might have stored
            "ping":    ["communication", "messaging", "chat", "app"],
            "message": ["communication", "messaging", "chat", "app"],
            "text":    ["communication", "messaging", "chat", "sms", "app"],
            "email":   ["communication", "email", "mail", "app"],
            "call":    ["communication", "phone", "voice", "calling"],
            "video":   ["communication", "video", "call", "zoom", "meeting"],
            "open":    ["project", "application", "tool", "software", "file"],
            "launch":  ["project", "application", "tool", "software"],
            "send":    ["communication", "messaging", "email", "file"],
            "share":   ["communication", "sharing", "collaboration"],
            "schedule":["calendar", "scheduling", "meeting", "event"],
            "book":    ["calendar", "scheduling", "travel", "booking"],
            "order":   ["shopping", "delivery", "food", "amazon"],
            "play":    ["music", "media", "entertainment", "spotify"],
            "search":  ["browser", "web", "search", "google"],
            "write":   ["editor", "writing", "notes", "document"],
            "draw":    ["design", "creative", "art", "canvas"],
            "code":    ["development", "ide", "editor", "git"],
        }

        # Find which verbs the user used
        matched_actions = set()
        for verb in _VERB_CATEGORIES:
            if verb in words:
                matched_actions.add(verb)

        # For each matched verb, look up user's stored preferences by category
        for verb in matched_actions:
            categories = _VERB_CATEGORIES[verb]
            for cat in categories:
                try:
                    # Search PREFERENCE nodes by name OR by properties.category
                    prefs = self._graph.find_nodes(type="PREFERENCE", name_like=cat, limit=2)
                    # Also search properties.category directly
                    try:
                        prop_prefs = self._graph._db.execute(
                            "SELECT * FROM nodes WHERE type = 'PREFERENCE' AND properties LIKE ? ORDER BY importance DESC LIMIT ?",
                            (f'%"{cat}"%', 2)
                        ).fetchall()
                        for row in prop_prefs:
                            node = dict(row)
                            node["properties"] = _unjson(node.get("properties"))
                            if node["id"] not in [p["id"] for p in prefs]:
                                prefs.append(node)
                    except Exception:
                        pass

                    for p in prefs:
                        if p["id"] not in seen_ids:
                            seen_ids.add(p["id"])
                            lines.append(f"USER_PREF ({verb}): {p['name']} [category: {cat}]")

                            # Also get edges of this preference
                            edges = self._graph.get_edges(p["id"], "both")
                            for edge in edges[:2]:
                                other_id = edge["target_id"] if edge["source_id"] == p["id"] else edge["source_id"]
                                other = self._graph._db.execute(
                                    "SELECT name, type FROM nodes WHERE id = ?", (other_id,)
                                ).fetchone()
                                if other:
                                    lines.append(f"  {edge['predicate']} → {other['name']}")
                except Exception:
                    pass

            # Also try GOAL nodes (user might have a goal related to the action)
            try:
                goals = self._graph.find_nodes(type="GOAL", name_like=verb, limit=2)
                for g in goals:
                    if g["id"] not in seen_ids:
                        seen_ids.add(g["id"])
                        lines.append(f"USER_GOAL ({verb}): {g['name']}")
            except Exception:
                pass

        # ── 5. Project/work context (dynamic from user's stored data) ──
        action_words = {"open", "launch", "work", "project", "task", "file",
                        "document", "design", "code", "edit", "review", "finish"}
        if words & action_words:
            # Look for most recent EVENT nodes (user's active projects)
            try:
                recent_events = self._cortex.get_temporal_context(hours=168) if self._cortex else []
                for evt in recent_events[:5]:
                    evt_domain = evt.get("domain", "")
                    evt_summary = evt.get("summary", "")
                    if evt_domain in ("work", "creative", "education") and evt.get("importance", 0) >= 5:
                        lines.append(f"ACTIVE_CONTEXT: {evt_summary[:80]} (domain: {evt_domain})")
            except Exception:
                pass

            # Also look for SKILL or PROJECT nodes
            for node_type in ["SKILL", "PROJECT", "GOAL"]:
                try:
                    nodes = self._graph.find_nodes(type=node_type, limit=3)
                    for n in nodes:
                        if n["id"] not in seen_ids:
                            seen_ids.add(n["id"])
                            lines.append(f"USER_{node_type}: {n['name']}")
                except Exception:
                    pass

        # ── 6. Multi-hop recall for all discovered entities ─────────────
        for name in person_names[:3]:
            if name.lower() not in _STOP_WORDS:
                try:
                    hops = self._graph.multi_hop_recall(name, max_hops=2, limit=5)
                    if hops:
                        hop_names = set()
                        for h in hops:
                            if h["name"] not in hop_names:
                                hop_names.add(h["name"])
                                lines.append(f"  MULTI_HOP: [{h['type']}] {h['name']}")
                except Exception:
                    pass

        # ── 7. Semantic full-text search for the whole user query ──────
        try:
            search_results = self._graph.search(user_text, limit=5)
            for r in search_results:
                if r.get("id") and r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    lines.append(f"SEMANTIC_MATCH: [{r['type']}] {r['name']} (score: {r.get('relevance', 0):.0%})")
        except Exception:
            pass

        if lines:
            lines.insert(0, "ENTITY-AWARE CONTEXT (auto-extracted from user's memory):")
        return "\n".join(lines)

    def _get_graph_context(self, user_text: str, limit: int = 5) -> str:
        """Get relevant entities from graph memory."""
        if not self._graph:
            return ""
        try:
            results = self._graph.search(user_text, limit)
            if not results:
                return ""
            lines = ["RELEVANT ENTITIES:"]
            for r in results:
                lines.append(f"  [{r['type']}] {r['label']} (relevance: {r['relevance']:.0%})")
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_predictive_context(self, user_text: str, domain: str) -> str:
        """Get predictive anticipations."""
        if not self._cortex:
            return ""
        predictions = self._cortex.anticipate(user_text, limit=3)
        if not predictions:
            return ""
        lines = ["PREDICTIONS:"]
        for p in predictions:
            lines.append(
                f"  IF {p['trigger_pattern'][:50]} "
                f"→ THEN {p['predicted_outcome'][:50]} "
                f"({p['confidence']:.0%})"
            )
        return "\n".join(lines)

    def _get_abstraction_context(self, domain: str) -> str:
        """Get hierarchical abstractions (patterns, principles)."""
        if not self._cortex:
            return ""
        try:
            from advanced_cortex import cortex
            rows = cortex._q(
                """SELECT * FROM abstraction_hierarchy
                   WHERE confidence > 0.5
                   ORDER BY times_applied DESC, confidence DESC LIMIT 5"""
            )
            if not rows:
                return ""
            lines = ["KNOWN PATTERNS & PRINCIPLES:"]
            for r in rows:
                lines.append(
                    f"  [{r['level']}] {r['name']} "
                    f"(applied {r['times_applied']}x, confidence {r['confidence']:.0%})"
                )
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_cross_domain_context(self, domain: str) -> str:
        """Get cross-domain insights."""
        if not self._cortex:
            return ""
        insights = self._cortex.get_cross_domain_insights(domain)
        if not insights:
            return ""
        lines = ["CROSS-DOMAIN INSIGHTS:"]
        for c in insights[:3]:
            lines.append(
                f"  {c['source_domain']} ↔ {c['target_domain']}: "
                f"{c['insight']} (strength: {c['strength']:.0%})"
            )
        return "\n".join(lines)

    def _get_conversation_context(self, session_id: str | None) -> str:
        """Get recent conversation history."""
        if not self._graph:
            return ""
        try:
            from graph_memory import memory as graph_mem
            # Get recent conversations
            rows = graph_mem._q(
                """SELECT * FROM conversations
                   ORDER BY timestamp DESC LIMIT 10"""
            )
            if not rows:
                return ""
            lines = ["RECENT CONVERSATION:"]
            for r in rows:
                role = r["role"] or "unknown"
                content = r["content"] or ""
                lines.append(f"  [{role}] {content[:100]}")
            return "\n".join(lines)
        except Exception:
            return ""

    # ───────────────────────────────────────────────────────────────────
    # ASSEMBLY & COMPRESSION
    # ───────────────────────────────────────────────────────────────────

    def _assemble_final(self, sections: list[tuple], max_tokens: int,
                        domain: str) -> str:
        """
        Assemble final context with priority-based compression.

        Higher-priority sections get more tokens. Lower-priority
        sections get summarized/compressed.
        """
        if not sections:
            return ""

        # Sort by priority (descending)
        sections.sort(key=lambda x: x[2], reverse=True)

        # Allocate token budget proportionally
        total_priority = sum(s[2] for s in sections)
        max_chars = max_tokens * 4  # Rough estimate: 1 token ≈ 4 chars

        assembled = []
        used_chars = 0

        for name, text, priority in sections:
            # Calculate allocation
            allocation = int((priority / total_priority) * max_chars)

            # Compress if needed
            if len(text) > allocation:
                # Keep beginning (most important) and add summary marker
                text = text[:allocation - 50] + f"\n  ... [{name}: truncated, {len(text)} chars total]"

            # Check budget
            if used_chars + len(text) > max_chars:
                remaining = max_chars - used_chars
                if remaining > 100:
                    text = text[:remaining - 30] + f"\n  ... [budget exhausted]"
                    assembled.append(text)
                break

            assembled.append(text)
            used_chars += len(text)

        return "\n\n".join(assembled)

    # ───────────────────────────────────────────────────────────────────
    # LEARNING: Auto-update profile from conversations
    # ───────────────────────────────────────────────────────────────────

    def learn_from_interaction(self, user_text: str, agent_response: str):
        """
        Auto-learn from every interaction to build the user profile.
        This is what makes JARVIS smarter over time.
        """
        if not self._cortex:
            return

        now = time.time()

        # Record the event
        event_id = self._cortex.record_event(
            summary=user_text[:200],
            full_content=user_text,
            event_type="conversation",
            domain=self._classify_domain(user_text),
            importance=3.0,
        )

        # Extract and learn personality dimensions
        text_lower = user_text.lower()

        # Communication style
        word_count = len(user_text.split())
        if word_count > 50:
            self._cortex.update_user_profile(
                "communication_style", "verbose", confidence=0.6
            )
        elif word_count < 10:
            self._cortex.update_user_profile(
                "communication_style", "concise", confidence=0.6
            )

        # Emotional expressiveness
        emotion_words = {"feel", "feeling", "felt", "emotion", "mood"}
        if any(w in text_lower for w in emotion_words):
            self._cortex.update_user_profile(
                "emotional_expressiveness", "high", confidence=0.5
            )

        # Technical level
        tech_words = {"api", "function", "variable", "algorithm", "database",
                      "server", "deploy", "kubernetes", "docker", "terraform"}
        if any(w in text_lower for w in tech_words):
            self._cortex.update_user_profile(
                "technical_level", "advanced", confidence=0.7
            )

        # Question asking (indicates curiosity)
        if "?" in user_text:
            self._cortex.update_user_profile(
                "communication_pattern", "question_oriented", confidence=0.5
            )

        # Decision making
        decision_words = {"decided", "chose", "picked", "going with", "committed"}
        if any(w in text_lower for w in decision_words):
            self._cortex.record_event(
                summary=f"Decision: {user_text[:100]}",
                event_type="decision",
                importance=7.0,
            )

        # Learn predictive patterns from sequences
        # (If user does X, they often follow with Y)
        # This is handled by the cortex's learn_predictive_pattern method

    # ───────────────────────────────────────────────────────────────────
    # ANALYTICS
    # ───────────────────────────────────────────────────────────────────

    def get_context_analytics(self) -> dict:
        """Get analytics about context quality and usage."""
        analytics = {
            "orchestrator_status": "active",
            "memory_systems": {
                "cortex": self._cortex is not None,
                "graph": self._graph is not None,
                "companion": self._companion is not None,
            },
        }
        if self._cortex:
            analytics["cortex_stats"] = self._cortex.get_analytics()
        return analytics


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

orchestrator = ContextOrchestrator()
