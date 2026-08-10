"""ACC (Agent Command Center) — unified device aggregation + natural language command parsing."""

import json, os, re, time, threading
from typing import Optional

try:
    from smart_home_manager import get_all_devices as get_sh_devices
    _HAS_SH = True
except:
    _HAS_SH = False

try:
    from actions import get_all_actions, execute_action, detect_action, _ACTION_LABELS, _ACTION_TIPS
    _HAS_ACTIONS = True
except:
    _HAS_ACTIONS = False

try:
    from hyperlocal_ai import get_hyperlocal
    _HAS_HL = True
except:
    _HAS_HL = False

_RELAY_DEVICES: dict[str, dict] = {}
_RELAY_LOCK = threading.Lock()


def register_relay_device(user_id: str, info: dict):
    with _RELAY_LOCK:
        _RELAY_DEVICES[user_id] = {
            "hostname": info.get("hostname", "unknown"),
            "platform": info.get("platform", "unknown"),
            "info": info.get("info", {}),
            "last_seen": time.time(),
        }


def get_relay_devices() -> list[dict]:
    with _RELAY_LOCK:
        return [
            {
                "id": f"relay_{uid}",
                "name": f"Relay: {dev.get('hostname', 'unknown')}",
                "type": "computer",
                "protocol": dev.get("platform", "unknown"),
                "status": "online" if (time.time() - dev.get("last_seen", 0)) < 120 else "offline",
                "room": "remote",
                "manufacturer": dev.get("info", {}).get("manufacturer", ""),
                "model": dev.get("info", {}).get("model", ""),
                "capabilities": ["scan", "execute", "propagate", "lock", "sleep", "restart",
                                 "volume", "brightness", "app_launch", "file_access", "screenshot",
                                 "clipboard", "process", "wifi", "bluetooth", "notification"],
                "state": {"hostname": dev.get("hostname"), "platform": dev.get("platform")},
                "ip": "",
                "port": 0,
            }
            for uid, dev in _RELAY_DEVICES.items()
        ]


def get_system_devices() -> list[dict]:
    if not _HAS_ACTIONS:
        return []
    actions = get_all_actions()
    categories = {
        "system": {"name": "System Control", "icon": "🖥", "actions": ["lock", "sleep", "restart", "shutdown", "logoff", "hibernate"]},
        "volume": {"name": "Audio", "icon": "🔊", "actions": ["vol_up", "vol_down", "vol_mute", "vol_set", "mic_toggle"]},
        "display": {"name": "Display", "icon": "🖥", "actions": ["brightness_up", "brightness_down", "brightness_set", "night_light", "toggle_theme"]},
        "network": {"name": "Network", "icon": "📶", "actions": ["wifi_list", "wifi_on", "wifi_off", "scan_network", "ping"]},
        "media": {"name": "Media", "icon": "🎵", "actions": ["media_play", "media_pause", "media_next", "media_prev", "spotify"]},
        "power": {"name": "Power", "icon": "🔋", "actions": ["battery_status", "uptime", "power_plan"]},
        "apps": {"name": "Applications", "icon": "📱", "actions": ["open_app", "app_list", "app_quit", "process_list", "process_kill"]},
        "clipboard": {"name": "Clipboard", "icon": "📋", "actions": ["clipboard_show", "clipboard_copy", "clipboard_paste"]},
        "files": {"name": "Files", "icon": "📁", "actions": ["search_files", "open_downloads", "open_documents", "drive_usage"]},
        "camera": {"name": "Camera", "icon": "📷", "actions": ["screenshot", "camera_snap"]},
        "browser": {"name": "Browser", "icon": "🌐", "actions": ["search", "open_url", "web_navigate"]},
        "bluetooth": {"name": "Bluetooth", "icon": "📡", "actions": ["bt_on", "bt_off", "bt_devices"]},
    }

    devices = []
    for cat_key, cat_info in categories.items():
        available = [a for a in cat_info["actions"] if a in actions]
        if not available:
            continue
        devices.append({
            "id": f"sys_{cat_key}",
            "name": cat_info["name"],
            "type": "system",
            "protocol": "native",
            "status": "online",
            "room": "local",
            "manufacturer": "",
            "model": "",
            "capabilities": available,
            "state": {},
            "ip": "127.0.0.1",
            "port": 0,
            "icon": cat_info["icon"],
        })
    return devices


def get_all_acc_devices() -> list[dict]:
    devices = []

    if _HAS_SH:
        for d in get_sh_devices():
            devices.append(d.to_dict())

    devices.extend(get_system_devices())
    devices.extend(get_relay_devices())

    return devices


_DEVICE_CAPABILITY_MAP = {
    "on": ["on", "power_on", "enable", "start", "turn_on", "switch_on"],
    "off": ["off", "power_off", "disable", "stop", "turn_off", "switch_off"],
    "toggle": ["toggle", "switch"],
    "brightness": ["brightness", "dim", "dimmer", "brighter", "brightness_set", "brightness_up", "brightness_down",
                   "set brightness", "change brightness", "brightness level", "brightness percentage"],
    "color": ["color", "colour", "set color", "change color", "hue"],
    "temperature": ["temperature", "temp", "color_temp", "warm", "cool", "kelvin"],
    "lock": ["lock", "secure"],
    "unlock": ["unlock", "open_lock"],
    "open": ["open", "raise", "up"],
    "close": ["close", "lower", "down"],
    "stop": ["stop", "halt", "pause"],
    "volume": ["volume", "vol", "sound", "loud", "quiet", "vol_up", "vol_down", "vol_set"],
    "mute": ["mute", "silence", "quiet"],
    "snapshot": ["snapshot", "photo", "picture", "capture", "photo_snap", "camera_snap"],
    "speak": ["speak", "say", "announce", "tell", "tts"],
    "start": ["start", "begin", "run", "launch", "activate"],
    "dock": ["dock", "return", "charge", "home", "go_home"],
    "read": ["read", "status", "get", "check", "what is", "report", "show", "display"],
    "temperature_set": ["set temperature", "set temp", "change temp", "temperature to", "temp to"],
    "mode": ["mode", "heat", "cool", "auto", "fan", "dry", "eco"],
    "scan": ["scan", "discover", "find devices", "list devices", "network scan"],
    "screenshot": ["screenshot", "capture screen", "screen capture"],
    "search": ["search", "find", "look up", "google", "web search"],
    "media_play": ["play", "resume", "start music", "start media"],
    "media_pause": ["pause", "stop music", "stop media"],
    "media_next": ["next", "skip", "next track", "next song"],
    "media_prev": ["previous", "prev", "previous track"],
    "process_list": ["processes", "running", "list processes", "task manager"],
    "process_kill": ["kill", "end task", "stop process"],
    "wifi_list": ["wifi", "wi-fi", "networks", "list wifi", "show wifi"],
    "app_launch": ["open app", "launch", "start app", "run app"],
    "clipboard_show": ["clipboard", "clipboard content", "what's copied"],
    "clipboard_copy": ["copy", "copy to clipboard"],
    "battery_status": ["battery", "power", "battery level", "charge"],
    "uptime": ["uptime", "how long", "last boot"],
    "notification": ["notify", "notification", "alert", "send notification"],
}


def parse_command_for_device(device: dict, command_text: str) -> dict:
    """Parse a natural language command for a specific device.
    Returns: { ok: bool, parsed: str, action: str, params: str, explanation: str }
    """
    capabilities = device.get("capabilities", [])
    device_type = device.get("type", "unknown")
    device_name = device.get("name", "Unknown")
    lower_cmd = command_text.lower().strip()

    # First try direct capability matching via keywords
    matched_cap = None
    for cap in capabilities:
        keywords = _DEVICE_CAPABILITY_MAP.get(cap, [cap.lower()])
        for kw in keywords:
            if kw in lower_cmd:
                matched_cap = cap
                break
        if matched_cap:
            break

    if matched_cap:
        return {
            "ok": True,
            "parsed": f"{device_name} → {matched_cap}",
            "action": matched_cap,
            "params": command_text,
            "explanation": f"Mapped '{command_text}' to action '{matched_cap}' on {device_name}",
        }

    if _HAS_HL:
        caps_str = ", ".join(capabilities) if capabilities else "none"
        prompt = f"""You are a device command parser. Map the user's natural language request to a device action.

Device: {device_name}
Device type: {device_type}
Available capabilities: {caps_str}

User command: "{command_text}"

Respond with ONLY a JSON object:
- "ok": true if the command can be mapped to an available capability, false otherwise
- "action": the best matching capability name from the list (or empty string if not possible)
- "params": any parameters extracted (e.g. brightness value, temperature, text to speak, etc.)
- "explanation": brief 1-sentence explanation

Examples:
{{"ok": true, "action": "brightness", "params": "50", "explanation": "Set brightness to 50%"}}
{{"ok": false, "action": "", "params": "", "explanation": "This device does not support recording video"}}

JSON:"""
        try:
            raw = get_hyperlocal("acc_parser")._generator.generate(prompt, max_tokens=200)
            if raw:
                raw = raw.strip()
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    return {
                        "ok": parsed.get("ok", False),
                        "parsed": f"{device_name} → {parsed.get('action', '?')}",
                        "action": parsed.get("action", ""),
                        "params": parsed.get("params", ""),
                        "explanation": parsed.get("explanation", ""),
                    }
        except Exception:
            pass

    # Try system-level action detection as fallback
    if _HAS_ACTIONS:
        try:
            detected = detect_action(command_text)
            if detected:
                return {
                    "ok": True,
                    "parsed": f"System → {detected}",
                    "action": detected,
                    "params": command_text,
                    "explanation": f"'{command_text}' mapped to system action '{detected}'",
                }
        except Exception:
            pass

    return {
        "ok": False,
        "parsed": "",
        "action": "",
        "params": "",
        "explanation": f"Cannot execute '{command_text}' on {device_name}. Available: {', '.join(capabilities) if capabilities else 'no capabilities defined'}",
    }


def execute_acc_command(device: dict, action: str, params: str = "") -> dict:
    """Execute a parsed command on a device. Returns { ok: bool, result: str }."""
    device_type = device.get("type", "unknown")
    device_id = device.get("id", "")

    if device_type == "system":
        if _HAS_ACTIONS:
            try:
                result = execute_action(action, params or action)
                return {"ok": True, "result": result}
            except Exception as e:
                return {"ok": False, "result": f"Execution failed: {e}"}
        return {"ok": False, "result": "System actions not available"}

    if device_type in ("light", "switch", "sensor", "thermostat", "lock", "cover",
                       "camera", "vacuum", "climate", "media_player", "hub", "alexa",
                       "speaker", "doorbell"):
        if _HAS_SH:
            try:
                from smart_home_manager import control_device, control_by_ip
                if device_id:
                    r = control_device(device_id, action, params)
                else:
                    r = control_by_ip(device.get("ip", ""), action, params)
                return {"ok": True, "result": r}
            except Exception as e:
                return {"ok": False, "result": f"Smart home control failed: {e}"}
        return {"ok": False, "result": "Smart home module not available"}

    if device_type == "computer":
        if _HAS_ACTIONS:
            try:
                result = execute_action(action, params or action)
                return {"ok": True, "result": result}
            except Exception as e:
                return {"ok": False, "result": f"Relay execution failed: {e}"}
        return {"ok": False, "result": "Relay actions not available"}

    return {"ok": False, "result": f"Unknown device type: {device_type}"}
