"""
Intent Understander — LLM-powered natural language understanding.

Handles typos, casual speech, ambiguous requests, and multi-goal prompts.
Falls back gracefully when LLM is unavailable.
"""

import re
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-understander")


@dataclass
class ParsedIntent:
    """Structured representation of what the user wants."""
    raw_text: str
    goals: List[str] = field(default_factory=list)        # Clean goal strings
    actions: List[Dict] = field(default_factory=list)     # [{"action": ..., "params": {...}}]
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    entities: Dict[str, str] = field(default_factory=dict)  # App names, URLs, etc.
    is_multi_goal: bool = False
    parse_method: str = "llm"  # "llm", "regex", "fallback"


# ── Typo corrections for common terms ──────────────────────────────────────
_TYPO_MAP = {
    # Apps
    "chrme": "chrome", "chorme": "chrome", "chromme": "chrome",
    "powepoint": "powerpoint", "powerpint": "powerpoint", "ppoint": "powerpoint",
    "whatspp": "whatsapp", "whatsap": "whatsapp",
    "openode": "opencode", "opne": "open", "opnece": "opencode",
    # Actions
    "strem": "stream", "strema": "stream", "stram": "stream",
    "duplicte": "duplicate", "dupliate": "duplicate", "duplciate": "duplicate",
    "sreenshot": "screenshot", "screnshot": "screenshot", "screenhot": "screenshot",
    "trdae": "trade", "tradig": "trading", "tradding": "trading",
    "broswe": "browse", "broswe": "browse", "brower": "browse",
    "scrape": "scrape", "scrpae": "scrape",
    "craete": "create", "creeate": "create",
    "doenload": "download", "dwonload": "download",
    "uplaod": "upload", "uplod": "upload",
    # Common phrases
    "wht is": "what is", "wat is": "what is", "wut is": "what is",
    "hw do": "how do", "hou do": "how do",
    "cn you": "can you", "cna you": "can you",
    "pls": "please", "plz": "please",
    "idk": "I don't know",
    "rn": "right now",
    "tmrw": "tomorrow",
    "asap": "as soon as possible",
    # Desktop/browser
    "hiddden": "hidden", "hiden": "hidden", "hiddne": "hidden",
    "desktp": "desktop", "desktio": "desktop",
    "brwoser": "browser", "brower": "browser",
}


def _fix_typos(text: str) -> str:
    """Fix common typos and normalize text."""
    words = text.lower().split()
    fixed = []
    for w in words:
        # Direct lookup
        if w in _TYPO_MAP:
            fixed.append(_TYPO_MAP[w])
            continue
        # Partial match (prefix)
        matched = False
        for typo, correct in _TYPO_MAP.items():
            if len(w) >= 3 and (w.startswith(typo[:3]) or typo.startswith(w[:3])):
                fixed.append(correct)
                matched = True
                break
        if not matched:
            fixed.append(w)
    return " ".join(fixed)


def _extract_entities(text: str) -> Dict[str, str]:
    """Extract known entities (apps, URLs, etc.) from text."""
    entities = {}

    # App names
    app_patterns = [
        (r"\b(chrome|google\s*chrome)\b", "chrome"),
        (r"\b(whatsapp|whats\s*app)\b", "whatsapp"),
        (r"\b(powerpoint|ms\s*power|ppt)\b", "powerpoint"),
        (r"\b(opencode|open\s*code)\b", "opencode"),
        (r"\b(excel|spreadsheet|ms\s*excel)\b", "excel"),
        (r"\b(word|ms\s*word|document)\b", "word"),
        (r"\b(notepad|text\s*editor)\b", "notepad"),
        (r"\b(file\s*explorer|explorer)\b", "explorer"),
        (r"\b(spotify|music)\b", "spotify"),
        (r"\b(discord|dc)\b", "discord"),
        (r"\b(telegram|tg)\b", "telegram"),
    ]
    for pattern, name in app_patterns:
        if re.search(pattern, text, re.I):
            entities["app"] = name
            break

    # URLs
    url_match = re.search(r'https?://[^\s]+', text)
    if url_match:
        entities["url"] = url_match.group()

    # Domain-like patterns
    domain_match = re.search(r'\b(\w+\.\w{2,4})\b', text)
    if domain_match and "." in domain_match.group():
        entities["domain"] = domain_match.group()

    # Trading 212
    if re.search(r"trading\s*212|t212", text, re.I):
        entities["platform"] = "trading212"

    # Port numbers
    port_match = re.search(r"port\s*(\d{4,5})", text, re.I)
    if port_match:
        entities["port"] = port_match.group(1)

    # Time expressions
    time_match = re.search(r'\b(\d{1,2}:\d{2}\s*(?:am|pm)?)\b', text, re.I)
    if time_match:
        entities["time"] = time_match.group(1)

    return entities


# ── LLM parse prompt ────────────────────────────────────────────────────────
_PARSE_PROMPT = """You are JARVIS intent parser. Parse the user's message into structured goals.

Handle: typos, casual speech, slang, abbreviations, multi-goal requests.

USER MESSAGE: {text}

{context}

Respond with ONLY valid JSON:
{{
  "goals": ["goal 1", "goal 2"],
  "actions": [{{"action": "action_name", "params": {{}}}}],
  "needs_clarification": false,
  "clarification_question": "",
  "confidence": 0.9,
  "entities": {{"app": "chrome", "url": "https://..."}}
}}

RULES:
- If the request is clear, set needs_clarification=false
- If ambiguous (which app? which file? what time?), set needs_clarification=true and ask ONE clear question
- If typos exist, fix them in the goals
- If multiple goals, list them in order
- confidence: 0.0-1.0 based on how well you understood
- Available actions: open_app, browse, web_search, close_app, screenshot, type_text,
  click_text, scroll, key_press, clipboard_copy, clipboard_paste, file_create,
  file_read, web_scrape, web_extract, web_duplicate_session, web_stream_desktop,
  web_capture_screen, web_stop_stream, cpu_info, memory_info, kill_process,
  system_lock, system_shutdown, volume_up, volume_down, volume_set, mute,
  send_whatsapp, email_send, notification, launch_desktop_app,
  research_prices, compare_prices, plan_travel, research_topic,
  create_presentation, create_document, create_spreadsheet,
  orchestrate, chain, task_status, task_cancel,
  add_knowledge, search_knowledge, get_knowledge_graph,
  render_canvas, render_dashboard, render_osint_dashboard,
  git_status, git_diff, git_commit, git_push, git_pull, git_clone,
  add_entity, add_relationship,
  trade_start_session, trade_read_portfolio, trade_analyze,
  trade_generate_orders, trade_render_dashboard"""


def parse_with_llm(text: str, context: str = "") -> Optional[ParsedIntent]:
    """Use LLM to parse intent from text (handles typos, casual language)."""
    try:
        from groq_agent import call
        prompt = _PARSE_PROMPT.format(text=text, context=context)
        response = call(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
        )
        if not response:
            return None

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None

        data = json.loads(json_match.group())

        return ParsedIntent(
            raw_text=text,
            goals=data.get("goals", [text]),
            actions=data.get("actions", []),
            confidence=min(max(data.get("confidence", 0.5), 0.0), 1.0),
            needs_clarification=data.get("needs_clarification", False),
            clarification_question=data.get("clarification_question", ""),
            entities=data.get("entities", {}),
            is_multi_goal=len(data.get("goals", [])) > 1,
            parse_method="llm",
        )

    except json.JSONDecodeError:
        log.debug("LLM returned invalid JSON")
        return None
    except Exception as e:
        log.debug(f"LLM parse failed: {e}")
        return None


def parse_with_regex(text: str) -> ParsedIntent:
    """Fast regex-based parse (no LLM, handles known patterns only)."""
    fixed = _fix_typos(text)
    entities = _extract_entities(fixed)

    # Detect multi-goal
    parts = re.split(r'\s+(?:and|then|also|plus|,)\s+', fixed, flags=re.I)
    is_multi = len(parts) > 1

    # Basic confidence from pattern matching
    confidence = 0.6 if entities else 0.4

    # Detect if clarification needed
    needs_clarification = False
    question = ""

    # Vague requests
    vague_patterns = [
        (r"^(do\s+something|help|idk|surprise\s+me|you\s+decide)", "What would you like me to do? I can open apps, search the web, automate tasks, and more."),
        (r"^(open|launch|start)$", "What would you like me to open? An app, a website, or a file?"),
        (r"^(search|find|look)$", "What should I search for?"),
        (r"^(close|quit|kill)$", "What should I close? An app, a tab, or a window?"),
        (r"^(run|execute)$", "What should I run? A script, an app, or a command?"),
    ]
    for pattern, question_text in vague_patterns:
        if re.search(pattern, fixed, re.I):
            needs_clarification = True
            question = question_text
            break

    return ParsedIntent(
        raw_text=text,
        goals=[fixed],
        actions=[],
        confidence=confidence,
        needs_clarification=needs_clarification,
        clarification_question=question,
        entities=entities,
        is_multi_goal=is_multi,
        parse_method="regex",
    )


def understand(text: str, context: str = "", force_clarification: bool = False) -> ParsedIntent:
    """Main entry point: understand user intent from natural language.
    
    Handles typos, casual speech, ambiguous requests, and multi-goal prompts.
    Returns structured ParsedIntent with goals, actions, and clarification if needed.
    
    Uses the grouped clarification engine for complex requests that need
    multiple parameters (e.g. travel, research, software).
    """
    if not text or not text.strip():
        return ParsedIntent(
            raw_text=text,
            needs_clarification=True,
            clarification_question="I didn't catch that. What would you like me to do?",
            parse_method="fallback",
        )

    text = text.strip()

    # Step 1: Fix typos and extract entities
    fixed = _fix_typos(text)
    entities = _extract_entities(fixed)

    # Step 2: Try grouped clarification engine first (for complex requests)
    try:
        from clarification_engine import needs_clarification_grouped
        needs_it, grouped_question, plan = needs_clarification_grouped(fixed)
        if needs_it and grouped_question:
            return ParsedIntent(
                raw_text=text,
                goals=[fixed],
                confidence=0.5,
                needs_clarification=True,
                clarification_question=grouped_question,
                entities=entities,
                parse_method="grouped_clarification",
            )
    except ImportError:
        pass

    # Step 3: Try regex first (fast, <1ms)
    result = parse_with_regex(fixed)

    # Step 4: If regex confidence is low or request is complex, use LLM
    if result.confidence < 0.7 or result.is_multi_goal or result.needs_clarification:
        llm_result = parse_with_llm(fixed, context)
        if llm_result and llm_result.confidence >= result.confidence:
            # Merge entities
            llm_result.entities = {**entities, **llm_result.entities}
            if not llm_result.raw_text:
                llm_result.raw_text = text
            return llm_result

    # Merge entities into regex result
    result.entities = {**entities, **result.entities}
    result.raw_text = text
    return result


def needs_clarification(text: str) -> Tuple[bool, str]:
    """Quick check: does this request need clarification? Returns (needs_it, question)."""
    result = understand(text)
    return result.needs_clarification, result.clarification_question


def get_quota_status() -> Dict:
    """Get current LLM provider quota status."""
    try:
        from groq_agent import _providers, _ROTATION_LOCK
        with _ROTATION_LOCK:
            status = {}
            for p in _providers:
                is_rate_limited = p["cooldown_until"] > time.time()
                cooldown_remaining = max(0, p["cooldown_until"] - time.time())
                status[p["name"]] = {
                    "enabled": p["enabled"],
                    "rate_limited": is_rate_limited,
                    "cooldown_remaining": round(cooldown_remaining, 1),
                    "failures": p["failures"],
                }
            return status
    except Exception:
        return {"error": "Could not check provider status"}
