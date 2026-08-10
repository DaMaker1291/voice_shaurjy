"""Edge Intent Router — fast regex + LLM fallback for typos and casual speech."""

import re
import time
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)

# ── Intent taxonomy ──────────────────────────────────────────────────────────
INTENTS = {
    "chat":           "General conversation",
    "system":         "OS/Desktop control",
    "device":         "Smart home / IoT control",
    "search":         "Web search / information retrieval",
    "code":           "Code generation / programming",
    "file":           "File system operations",
    "voice":          "Voice/audio commands",
    "automation":     "Workflow/task automation",
    "memory":         "Memory / knowledge graph recall",
    "agent":          "Autonomous agent spawn",
    "schedule":       "Calendar / reminders / scheduling",
    "email":          "Email / messaging",
    "economic":       "Economic / travel / booking",
    "learning":       "Learning / self-improvement",
    "skill":          "Skill marketplace",
    "enterprise":     "Enterprise / organization",
    "help":           "Help / about JARVIS",
    "trading":        "Trading / finance / portfolio",
    "browser":        "Browser automation / web scraping",
    "unknown":        "Unclassified",
}

# ── Pattern-based classifiers (sub-100µs) ──────────────────────────────────
_PATTERNS = [
    # Trading / Finance
    (r"\b(trad(e|ing)|portfolio|stock|buy|sell|position|pnl|profit|loss)\b", "trading", "trading_action"),
    (r"\b(trading\s*212|t212|broker)\b", "trading", "broker_specific"),
    (r"\b(dividend|yield|sector|allocation|rebalance)\b", "trading", "portfolio_mgmt"),
    (r"\b(rsi|sma|ema|bollinger|momentum|backtest|sharpe)\b", "trading", "quant_analysis"),

    # Browser / Web
    (r"\b(browse|broswe|brower|open\s*(tab|url|website|page))\b", "browser", "browse"),
    (r"\b(scrape|scrpae|extract|crawl)\s*(data|info|content|table|price)?", "browser", "scrape"),
    (r"\b(duplicat|clone|copy)\s*(session|chrome|tab|browser)", "browser", "duplicate"),
    (r"\b(stream|strema|screencast|mirror)\s*(screen|desktop|tab)", "browser", "stream"),
    (r"\b(screenshot|screnshot|screen\s*shot|capture)\b", "browser", "screenshot"),
    (r"\b(automate|auto|bot)\s*(browser|web|chrome|tab)", "browser", "automate"),

    # System / Desktop
    (r"\b(open|launch|start|run|quit|close|kill)\s+\w+", "system", "app_control"),
    (r"\b(click|type|press|scroll|mouse|keyboard)\b", "system", "input_simulation"),
    (r"\b(cpu|memory|disk|task\s*manager|process)\b", "system", "system_monitor"),
    (r"\b(wifi|network|ip\s*address|connect|disconnect)\b", "system", "network"),
    (r"\b(volume|brightness|mute|airdrop|bluetooth)\b", "system", "hardware_control"),
    (r"\b(shutdown|restart|sleep|lock|log\s*out)\b", "system", "power_management"),

    # Phone / Device Control
    (r"\b(pause|block|kick|throttle|unblock)\s+\w+", "system", "phone_control"),
    (r"\b(phone|device)\s+(wifi|internet|network)\b", "system", "phone_control"),
    (r"\b(who|what)\s*(?:'s|is)\s+on\s+(?:my\s+)?(?:wifi|network)\b", "system", "phone_control"),

    # Smart Home / IoT
    (r"\b(turn\s*(on|off)|dim|brighten|set\s*temperature)\b", "device", "light_control"),
    (r"\b(thermostat|plug|switch|sensor|tapo|alexa|google\s*home)\b", "device", "device_specific"),

    # Web Search
    (r"\b(search|google|find|look\s*up|research|investigate)\b", "search", "web_search"),
    (r"\b(who|what|where|when|why|how)\s+(is|are|was|were|does|do)\b", "search", "question_answering"),
    (r"\b(news|weather|stock|price|latest)\b", "search", "live_data"),

    # Code
    (r"\b(code|program|script|function|class|implement|debug|refactor)\b", "code", "code_gen"),
    (r"\b(python|javascript|typescript|rust|go|react|api|endpoint)\b", "code", "language_specific"),
    (r"\b(compile|build|deploy|test|lint|format)\b", "code", "dev_ops"),
    (r"\b(git\s*(status|diff|commit|push|pull|clone|log|branch))\b", "code", "git_ops"),

    # File
    (r"\b(create|delete|rename|move|copy|find|search)\s+(file|folder|directory)\b", "file", "file_ops"),
    (r"\b(read|write|edit|save|open)\s+(file|document)\b", "file", "file_edit"),

    # Voice
    (r"\b(speak|say|read\s*(aloud|out)|narrate|announce)\b", "voice", "tts"),

    # Automation / Workflow
    (r"\b(automate|workflow|routine|macro|batch|sequence)\b", "automation", "workflow_create"),
    (r"\b(schedule|every\s+\w+|daily|weekly|hourly)\b", "automation", "scheduled_task"),

    # Memory
    (r"\b(remember|recall|forget|store|save)\s+(that|this|about)\b", "memory", "memory_store"),
    (r"\b(what\s+did\s+(I|we)|tell\s+me\s+about)\b", "memory", "memory_recall"),

    # Schedule / Calendar
    (r"\b(remind|reminder|alert|notify|todo|task)\b", "schedule", "reminder"),
    (r"\b(calendar|meeting|appointment|event|schedule)\b", "schedule", "calendar"),

    # Email / Messaging
    (r"\b(email|mail|inbox|send\s*(message|email)|compose)\b", "email", "email_ops"),
    (r"\b(text|message|sms|whatsapp|telegram|discord)\b", "email", "messaging"),

    # Economic / Travel
    (r"\b(flight|hotel|book|reservation|travel|trip)\b", "economic", "travel"),
    (r"\b(price|cost|buy|purchase|order|shop)\b", "economic", "commerce"),

    # Presentations / Documents
    (r"\b(presentation|powerpoint|ppt|slides|deck)\b", "system", "presentation"),
    (r"\b(document|report|memo|summary)\b", "system", "document"),

    # Chat (fallback)
    (r"\b(hello|hi|hey|thanks|thank\s*you|good)\b", "chat", "greeting"),
    (r"\b(who\s*are\s*you|what\s*are\s*you)\b", "help", "identity"),
]


class EdgeRouter:
    """Intent classifier: fast regex + LLM fallback for typos/casual speech.
    
    Flow:
    1. Fix typos (sub-ms)
    2. Regex match (sub-ms)
    3. If low confidence → LLM parse (100-500ms)
    4. If still unclear → ask clarifying question
    """

    def __init__(self):
        self._compiled = [(re.compile(p, re.IGNORECASE | re.DOTALL), intent, sub) for p, intent, sub in _PATTERNS]
        self._stats = {"classified": 0, "avg_time_ms": 0.0, "llm_fallback": 0, "clarifications": 0}

    def classify(self, text: str) -> Tuple[str, float, str]:
        """Classify intent. Returns (intent_name, confidence, sub_type)."""
        start = time.perf_counter()
        text = text.strip()

        if not text:
            self._update_stats(start)
            return ("unknown", 0.0, "empty_query")

        # Phase 1: Fix typos
        from intent_understander import _fix_typos, _extract_entities
        fixed = _fix_typos(text)
        entities = _extract_entities(fixed)

        # Phase 2: Pattern match on fixed text
        for pattern, intent, sub_type in self._compiled:
            if pattern.search(fixed) or pattern.search(text):
                confidence = self._compute_confidence(pattern, fixed)
                # Boost confidence if entities were extracted
                if entities:
                    confidence = min(confidence + 0.1, 0.95)
                self._update_stats(start)
                return (intent, confidence, sub_type)

        # Phase 3: LLM fallback for typos and casual language
        try:
            from intent_understander import understand
            result = understand(text)
            if result.confidence > 0.5:
                # Map ParsedIntent to (intent, confidence, sub_type)
                intent = self._map_goals_to_intent(result.goals)
                self._stats["llm_fallback"] += 1
                self._update_stats(start)
                return (intent, result.confidence, "llm_parsed")
        except Exception as e:
            logger.debug(f"LLM fallback failed: {e}")

        # Phase 4: Unknown
        self._update_stats(start)
        return ("unknown", 0.3, "unclassified")

    def classify_multi(self, text: str) -> List[Tuple[str, float, str]]:
        """Detect multiple intents in a compound prompt."""
        parts = re.split(r'\s+(?:and|then|next|after\s+that|also|plus)\s+|[,;]\s*', text, flags=re.I)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) <= 1:
            return [self.classify(text)]

        results = []
        seen_intents = set()
        for part in parts:
            intent, conf, sub = self.classify(part)
            key = (intent, sub)
            if key not in seen_intents:
                results.append((intent, conf, sub))
                seen_intents.add(key)

        return results if results else [self.classify(text)]

    def is_complex(self, text: str) -> bool:
        """Check if a prompt requires multi-step orchestration."""
        multi = self.classify_multi(text)
        if len(multi) > 1:
            return True
        complex_markers = [
            r'\band\b.*\bthen\b', r'\bthen\b.*\band\b',
            r'\bstep\s*\d', r'\bfirst\b.*\bthen\b.*\bfinally\b',
            r'\bresearch\b.*\bthen\b.*\b(create|build|generate)\b',
        ]
        for marker in complex_markers:
            if re.search(marker, text, re.I):
                return True
        return False

    def needs_clarification(self, text: str) -> Tuple[bool, str]:
        """Check if request is too vague and needs clarification."""
        from intent_understander import needs_clarification as _check
        return _check(text)

    def _map_goals_to_intent(self, goals: List[str]) -> str:
        """Map parsed goals back to an intent name."""
        combined = " ".join(goals).lower()
        if any(w in combined for w in ["trade", "portfolio", "stock", "buy", "sell", "broker"]):
            return "trading"
        if any(w in combined for w in ["browse", "scrape", "extract", "browser", "tab"]):
            return "browser"
        if any(w in combined for w in ["open", "launch", "close", "app"]):
            return "system"
        if any(w in combined for w in ["search", "find", "look up"]):
            return "search"
        if any(w in combined for w in ["file", "folder", "create", "read"]):
            return "file"
        if any(w in combined for w in ["email", "message", "send"]):
            return "email"
        if any(w in combined for w in ["git", "commit", "push"]):
            return "code"
        if any(w in combined for w in ["presentation", "ppt", "slides"]):
            return "system"
        return "automation"

    def _compute_confidence(self, pattern: re.Pattern, text: str) -> float:
        match = pattern.search(text)
        if not match:
            return 0.5
        matched_len = len(match.group())
        text_len = len(text)
        base = min(0.5 + (matched_len / max(text_len, 1)) * 0.5, 0.95)
        return round(base, 2)

    def _update_stats(self, start: float):
        elapsed = (time.perf_counter() - start) * 1000
        self._stats["classified"] += 1
        n = self._stats["classified"]
        self._stats["avg_time_ms"] = round(
            (self._stats["avg_time_ms"] * (n - 1) + elapsed) / n, 3
        )

    @property
    def stats(self) -> dict:
        return {**self._stats}


_router = None

def get_router() -> EdgeRouter:
    global _router
    if _router is None:
        _router = EdgeRouter()
    return _router

def classify_intent(text: str) -> Tuple[str, float, str]:
    return get_router().classify(text)
