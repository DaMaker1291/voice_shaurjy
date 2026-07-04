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

DEVICE_TYPES = {
    "light": ["light", "lamp", "bulb", "led", "strip", "hue", "lifx", "wled"],
    "switch": ["switch", "plug", "outlet", "relay", "power strip"],
    "thermostat": ["thermostat", "temperature", "heating", "cooling", "hvac", "ac", "air conditioner", "heater"],
    "lock": ["lock", "deadbolt", "door lock", "smart lock", "august", "yale"],
    "camera": ["camera", "cam", "doorbell", "ring", "nest cam", "security cam", "webcam"],
    "vacuum": ["vacuum", "roborock", "roomba", "sweep", "mop", "cleaning robot"],
    "speaker": ["speaker", "echo", "alexa", "google home", "sonos", "play speaker", "music speaker"],
    "media_player": ["tv", "television", "apple tv", "roku", "chromecast", "fire tv", "nvidia shield"],
    "fan": ["fan", "ceiling fan", "desk fan", "exhaust fan"],
    "sensor": ["sensor", "temperature sensor", "humidity sensor", "motion sensor", "door sensor"],
    "blind": ["blind", "shades", "curtain", "shutter", "roller", "towel"],
    "garage": ["garage", "garage door", "gate"],
    "hub": ["hub", "bridge", "gateway", "coordinator"],
}

ACTIONS = {
    "turn_on": ["turn on", "switch on", "enable", "activate", "start", "power on", "lights on"],
    "turn_off": ["turn off", "switch off", "disable", "deactivate", "stop", "power off", "lights off"],
    "toggle": ["toggle", "flip", "switch"],
    "set_brightness": ["brighten", "dim", "set brightness", "brightness to", "make it brighter", "make it darker", "set to percent"],
    "set_color": ["set color", "change color to", "make it", "color to", "change to red", "change to blue", "set to green"],
    "set_temperature": ["set temperature", "set temp to", "set to degrees", "set to ", "set heating to", "set cooling to", "temperature to"],
    "lock": ["lock", "lock the", "engage lock"],
    "unlock": ["unlock", "unlock the", "disengage lock"],
    "open": ["open", "raise", "lift"],
    "close": ["close", "lower", "shut"],
    "status": ["status", "what is", "how is", "report", "check"],
    "play": ["play", "start playing", "resume"],
    "pause": ["pause", "stop playing", "halt"],
    "next": ["next track", "skip", "next song"],
    "prev": ["previous track", "previous song", "go back"],
    "set_volume": ["set volume", "volume to", "volume up", "volume down", "mute", "unmute"],
    "snapshot": ["take a picture", "snapshot", "capture", "take a photo"],
    "start_clean": ["clean", "start cleaning", "vacuum", "start vacuuming"],
    "dock": ["dock", "return to dock", "go home", "return home"],
}

PARAM_PATTERNS = {
    "brightness": [
        (r'(?:to|at)\s+(\d{1,3})\s*%', 'percent'),
        (r'(?:to|at)\s+(\d{1,3})', 'percent'),
        (r'(\d{1,3})\s*percent', 'percent'),
        (r'max(?:imum)?|full', 'max'),
        (r'min(?:imum)?|low', 'min'),
    ],
    "color": [
        (r'\b(red|blue|green|yellow|purple|pink|orange|white|warm white|cool white|cyan|magenta|lavender|teal|amber)\b', 'color_name'),
    ],
    "temperature": [
        (r'(\d{2,3})\s*(?:degrees?|°)', 'value'),
        (r'to\s+(\d{2,3})', 'value'),
    ],
    "volume": [
        (r'(?:to|at)\s+(\d{1,3})\s*%', 'percent'),
        (r'(\d{1,3})\s*percent', 'percent'),
        (r'up', 'up'),
        (r'down', 'down'),
        (r'mute', 'mute'),
        (r'unmute', 'unmute'),
    ],
}

COLOR_MAP = {
    "red": [255, 0, 0], "blue": [0, 0, 255], "green": [0, 255, 0],
    "yellow": [255, 255, 0], "purple": [128, 0, 255], "pink": [255, 105, 180],
    "orange": [255, 165, 0], "white": [255, 255, 255], "warm white": [255, 180, 100],
    "cool white": [200, 220, 255], "cyan": [0, 255, 255], "magenta": [255, 0, 255],
    "lavender": [230, 190, 255], "teal": [0, 128, 128], "amber": [255, 191, 0],
}


def parse_command(text: str, devices: Optional[List[Dict]] = None) -> ParsedCommand:
    """Parse natural language into a structured device command."""
    text_lower = text.lower().strip()
    result = ParsedCommand(raw_text=text, confidence=0.0)

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
    """Use Groq LLM for complex command parsing."""
    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return None

        client = Groq(api_key=api_key)
        system = """You are a device command parser. Given a natural language command, extract:
- intent: one of [turn_on, turn_off, toggle, set_brightness, set_color, set_temperature, lock, unlock, open, close, status, play, pause, next, prev, set_volume, snapshot, start_clean, dock]
- device_type: one of [light, switch, thermostat, lock, camera, vacuum, speaker, media_player, fan, sensor, blind, garage]
- device_name: specific device name if mentioned (e.g. "living room light")
- params: any parameters (brightness: 0-100, color: [r,g,b], temperature: number, volume: 0-100)

Return ONLY valid JSON. If the input is not a device command, return {"intent": "chat", "confidence": 0.0}."""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
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
    result = ParsedCommand(raw_text=text)

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
