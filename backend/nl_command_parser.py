"""
JARVIS NL Command Parser — ML Intent Extraction → Device Commands
=================================================================
Parses natural language into structured device commands using
LLM-based intent extraction with local regex fallback.
"""

import re
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ParsedCommand:
    intent: str
    device_type: Optional[str] = None
    device_name: Optional[str] = None
    device_ip: Optional[str] = None
    action: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""
    method: str = "regex"
    suggestions: List[str] = field(default_factory=list)


# ── Intent Patterns (ML-like regex with context awareness) ────
# All vocabulary loaded from nl_intents.json at runtime — no hardcoded values.

_INTENT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nl_intents.json")

def _load_intent_config() -> Dict[str, Any]:
    """Load NL intent vocabulary from the JSON config file."""
    try:
        with open(_INTENT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

_intent_cfg = _load_intent_config()

DEVICE_TYPES: Dict[str, List[str]] = _intent_cfg.get("device_types", {})
ACTIONS: Dict[str, List[str]] = _intent_cfg.get("actions", {})
PARAM_PATTERNS: Dict[str, List[Any]] = _intent_cfg.get("param_patterns", {})
COLOR_MAP: Dict[str, List[int]] = _intent_cfg.get("color_map", {})


def parse_command(text: str, devices: Optional[List[Dict]] = None) -> ParsedCommand:
    """Parse natural language into a structured device command."""
    text_lower = text.lower().strip()
    result = ParsedCommand(intent="unknown", raw_text=text, confidence=0.0)

    # Try LLM-based parsing first
    llm_result = _parse_with_llm(text)
    if llm_result and llm_result.confidence > 0.7:
        llm_result.method = "llm"
        return llm_result

    # Regex-based parsing fallback
    regex_result = _parse_with_regex(text_lower)
    if regex_result.confidence > result.confidence:
        result = regex_result

    # Device matching
    if devices and (result.device_type or result.device_name):
        matched = _match_device(result, devices)
        if matched:
            result.device_ip = matched.get("ip")
            result.device_name = matched.get("name", result.device_name)
            result.confidence = min(result.confidence + 0.1, 1.0)

    return result


def _parse_with_llm(text: str) -> Optional[ParsedCommand]:
    """Use local LLM for complex command parsing."""
    try:
        from groq_agent import call as llm_call
        system = """You are a device command parser. Given a natural language command, extract:
- intent: one of [turn_on, turn_off, toggle, set_brightness, set_color, set_temperature, lock, unlock, open, close, status, play, pause, next, prev, set_volume, snapshot, start_clean, dock]
- device_type: one of [light, switch, thermostat, lock, camera, vacuum, speaker, media_player, fan, sensor, blind, garage]
- device_name: specific device name if mentioned (e.g. "living room light")
- params: any parameters (brightness: 0-100, color: [r,g,b], temperature: number, volume: 0-100)

Return ONLY valid JSON. If the input is not a device command, return {"intent": "chat", "confidence": 0.0}."""

        content = llm_call(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            max_tokens=256,
            temperature=0.1,
        )
        if not content:
            return None
        data = json.loads(content)

        if data.get("intent") == "chat":
            return ParsedCommand(intent="chat", confidence=0.0)

        # Parse color params
        params = data.get("params", {})
        if "color_name" in params:
            color_name = params.pop("color_name").lower()
            if color_name in COLOR_MAP:
                params["color"] = COLOR_MAP[color_name]
            elif "color" not in params:
                params["color_name"] = color_name

        return ParsedCommand(
            intent=data.get("intent", "unknown"),
            device_type=data.get("device_type"),
            device_name=data.get("device_name"),
            action=data.get("intent"),
            params=params,
            confidence=data.get("confidence", 0.85),
            method="llm",
        )
    except Exception:
        return None


def _parse_with_regex(text: str) -> ParsedCommand:
    """Regex-based intent extraction (fast, no API call)."""
    result = ParsedCommand(intent="unknown", raw_text=text)

    # Detect device type
    for dtype, keywords in DEVICE_TYPES.items():
        for kw in keywords:
            if kw in text:
                result.device_type = dtype
                break
        if result.device_type:
            break

    # Detect action
    best_action = None
    best_score = 0
    for action, phrases in ACTIONS.items():
        for phrase in phrases:
            if phrase in text:
                score = len(phrase) / len(text)
                if score > best_score:
                    best_action = action
                    best_score = score
    if best_action:
        result.action = best_action
        result.intent = best_action
        result.confidence = 0.6 + (best_score * 0.2)

    # Extract device name (text between action phrase and end, or before "to" etc.)
    name_patterns = [
        r'(?:the|my)\s+([\w\s]+?)(?:\s+(?:to|at|in|on|for|\.|$))',
        r'(?:turn on|turn off|switch on|switch off|activate|deactivate)\s+(?:the\s+)?([\w\s]+?)(?:\s+(?:to|at|in|on|\.|$)|$)',
    ]
    for pat in name_patterns:
        m = re.search(pat, text)
        if m:
            name = m.group(1).strip()
            if len(name) > 2 and not any(kw in name for kw in ["the", "my", "all", "every"]):
                result.device_name = name
                break

    # Extract parameters
    for param_type, patterns in PARAM_PATTERNS.items():
        for pat, key in patterns:
            m = re.search(pat, text)
            if m:
                if key == 'percent':
                    result.params[param_type] = int(m.group(1))
                elif key == 'value':
                    result.params[param_type] = int(m.group(1))
                elif key == 'max':
                    result.params[param_type] = 100
                elif key == 'min':
                    result.params[param_type] = 1
                elif key == 'up':
                    result.params[f"{param_type}_direction"] = "up"
                elif key == 'down':
                    result.params[f"{param_type}_direction"] = "down"
                elif key == 'mute':
                    result.params["mute"] = True
                elif key == 'unmute':
                    result.params["mute"] = False
                elif key == 'color_name':
                    color = m.group(1).lower()
                    if color in COLOR_MAP:
                        result.params["color"] = COLOR_MAP[color]
                    else:
                        result.params["color_name"] = color
                break

    # Boost confidence if we found both device and action
    if result.device_type and result.action:
        result.confidence = max(result.confidence, 0.75)
    elif result.action:
        result.confidence = max(result.confidence, 0.5)

    return result


def _match_device(parsed: ParsedCommand, devices: List[Dict]) -> Optional[Dict]:
    """Match parsed command to a known device."""
    if not devices:
        return None

    best_match = None
    best_score = 0

    for device in devices:
        score = 0
        name = (device.get("name", "") + " " + device.get("type", "")).lower()
        dtype = device.get("type", "").lower()

        # Type match
        if parsed.device_type and dtype == parsed.device_type:
            score += 3
        elif parsed.device_type and parsed.device_type in name:
            score += 2

        # Name match
        if parsed.device_name:
            dev_name = device.get("name", "").lower()
            if parsed.device_name.lower() in dev_name or dev_name in parsed.device_name.lower():
                score += 5
            # Partial word match
            for word in parsed.device_name.lower().split():
                if word in dev_name and len(word) > 2:
                    score += 1

        # IP match
        if parsed.device_ip and device.get("ip") == parsed.device_ip:
            score += 10

        if score > best_score:
            best_score = score
            best_match = device

    return best_match if best_score > 0 else None


def build_device_command(parsed: ParsedCommand) -> Dict[str, Any]:
    """Convert parsed command to a device control payload."""
    payload = {
        "intent": parsed.intent,
        "device_type": parsed.device_type,
        "device_name": parsed.device_name,
        "device_ip": parsed.device_ip,
        "action": parsed.action,
        "params": parsed.params,
        "confidence": parsed.confidence,
    }

    # Build protocol-specific payload
    if parsed.action in ("turn_on", "turn_off", "toggle"):
        state = "on" if parsed.action == "turn_on" else ("off" if parsed.action == "turn_off" else "toggle")
        payload["command"] = {"state": state}

    elif parsed.action == "set_brightness":
        brightness = parsed.params.get("brightness", 50)
        payload["command"] = {"brightness": brightness, "state": "on"}

    elif parsed.action == "set_color":
        color = parsed.params.get("color", [255, 255, 255])
        payload["command"] = {"color": color, "state": "on"}

    elif parsed.action == "set_temperature":
        temp = parsed.params.get("temperature", 22)
        payload["command"] = {"temperature": temp}

    elif parsed.action in ("lock", "unlock"):
        payload["command"] = {"state": parsed.action}

    elif parsed.action in ("open", "close"):
        position = 100 if parsed.action == "open" else 0
        payload["command"] = {"position": position}

    elif parsed.action == "set_volume":
        if parsed.params.get("mute"):
            payload["command"] = {"mute": True}
        elif parsed.params.get("unmute"):
            payload["command"] = {"mute": False}
        elif "volume" in parsed.params:
            payload["command"] = {"volume": parsed.params["volume"]}
        elif parsed.params.get("volume_direction") == "up":
            payload["command"] = {"volume_step": 10}
        elif parsed.params.get("volume_direction") == "down":
            payload["command"] = {"volume_step": -10}

    elif parsed.action in ("play", "pause", "next", "prev"):
        payload["command"] = {"state": parsed.action}

    elif parsed.action == "start_clean":
        payload["command"] = {"action": "start"}

    elif parsed.action == "dock":
        payload["command"] = {"action": "return_to_base"}

    return payload
