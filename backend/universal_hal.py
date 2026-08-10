"""
JARVIS Universal Hardware Abstraction Layer (HAL)
=================================================
Normalizes every device protocol into a single, clean JSON contract.
The AI models never see proprietary APIs — they see unified actions.

This is the core insight: instead of writing 100 drivers, we write
ONE abstraction layer that translates any device into:
  {
    "device_id": "vacuum_living_room_0x4F",
    "device_type": "ROBOTIC_CLEANER",
    "network_address": "<ip_or_mac>",
    "protocol": "LOCAL_TUYA_UDP",
    "state": { "power": "OFF", "battery": 92, "suction": "NORMAL" },
    "normalized_actions": {
      "TURN_ON": { "payload": "hex_0x01_start" },
      "SET_SPEED": { "payload": "hex_0x05_speed", "range": ["QUIET", "MAX"] }
    }
  }
"""

import json
import os
import time
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Callable
from collections import defaultdict


# ── Device Type Definitions ──────────────────────────────────

DEVICE_TYPES = {
    "LIGHT": {
        "label": "Light",
        "icon": "💡",
        "actions": {
            "TURN_ON": {"type": "boolean", "default": True},
            "TURN_OFF": {"type": "boolean", "default": False},
            "TOGGLE": {"type": "toggle"},
            "SET_BRIGHTNESS": {"type": "int", "min": 0, "max": 100, "unit": "%"},
            "SET_COLOR": {"type": "color"},
            "SET_COLOR_TEMP": {"type": "int", "min": 2700, "max": 6500, "unit": "K"},
        },
        "state_schema": {
            "power": {"type": "enum", "values": ["ON", "OFF"]},
            "brightness": {"type": "int", "min": 0, "max": 100},
            "color": {"type": "string"},
            "color_temp": {"type": "int"},
        },
    },
    "SWITCH": {
        "label": "Switch/Plug",
        "icon": "🔌",
        "actions": {
            "TURN_ON": {"type": "boolean", "default": True},
            "TURN_OFF": {"type": "boolean", "default": False},
            "TOGGLE": {"type": "toggle"},
            "GET_POWER": {"type": "read"},
        },
        "state_schema": {
            "power": {"type": "enum", "values": ["ON", "OFF"]},
            "watts": {"type": "float"},
        },
    },
    "THERMOSTAT": {
        "label": "Thermostat",
        "icon": "🌡",
        "actions": {
            "SET_TEMPERATURE": {"type": "float", "min": 10, "max": 40, "unit": "C"},
            "SET_MODE": {"type": "enum", "values": ["HEAT", "COOL", "AUTO", "OFF"]},
            "SET_FAN_MODE": {"type": "enum", "values": ["AUTO", "LOW", "MEDIUM", "HIGH"]},
        },
        "state_schema": {
            "current_temp": {"type": "float"},
            "target_temp": {"type": "float"},
            "mode": {"type": "enum", "values": ["HEAT", "COOL", "AUTO", "OFF"]},
            "humidity": {"type": "float"},
        },
    },
    "LOCK": {
        "label": "Smart Lock",
        "icon": "🔒",
        "actions": {
            "LOCK": {"type": "command"},
            "UNLOCK": {"type": "command", "requires_auth": True},
            "GET_STATUS": {"type": "read"},
        },
        "state_schema": {
            "lock_state": {"type": "enum", "values": ["LOCKED", "UNLOCKED", "JAMMED"]},
            "battery": {"type": "int"},
        },
    },
    "CAMERA": {
        "label": "Camera/Doorbell",
        "icon": "📷",
        "actions": {
            "GET_SNAPSHOT": {"type": "read"},
            "START_STREAM": {"type": "command"},
            "STOP_STREAM": {"type": "command"},
            "TWO_WAY_AUDIO": {"type": "command"},
        },
        "state_schema": {
            "recording": {"type": "boolean"},
            "motion_detected": {"type": "boolean"},
            "online": {"type": "boolean"},
        },
    },
    "VACUUM": {
        "label": "Robot Vacuum",
        "icon": "🤖",
        "actions": {
            "START_CLEANING": {"type": "command"},
            "STOP": {"type": "command"},
            "PAUSE": {"type": "command"},
            "DOCK": {"type": "command"},
            "FIND_ROBOT": {"type": "command"},
            "SET_SPEED": {"type": "enum", "values": ["QUIET", "NORMAL", "MAX", "TURBO"]},
        },
        "state_schema": {
            "power": {"type": "enum", "values": ["ON", "OFF", "CHARGING"]},
            "battery": {"type": "int", "min": 0, "max": 100},
            "cleaning_area": {"type": "float"},
            "suction_level": {"type": "enum"},
        },
    },
    "CLIMATE": {
        "label": "AC/Fan",
        "icon": "❄️",
        "actions": {
            "TURN_ON": {"type": "boolean", "default": True},
            "TURN_OFF": {"type": "boolean", "default": False},
            "SET_TEMPERATURE": {"type": "float", "min": 16, "max": 32, "unit": "C"},
            "SET_MODE": {"type": "enum", "values": ["COOL", "HEAT", "DRY", "FAN", "AUTO"]},
            "SET_FAN_SPEED": {"type": "enum", "values": ["LOW", "MEDIUM", "HIGH", "AUTO"]},
        },
        "state_schema": {
            "power": {"type": "enum", "values": ["ON", "OFF"]},
            "current_temp": {"type": "float"},
            "target_temp": {"type": "float"},
            "mode": {"type": "enum"},
        },
    },
    "MEDIA_PLAYER": {
        "label": "Media Player/Speaker",
        "icon": "📺",
        "actions": {
            "PLAY": {"type": "command"},
            "PAUSE": {"type": "command"},
            "NEXT": {"type": "command"},
            "PREVIOUS": {"type": "command"},
            "SET_VOLUME": {"type": "int", "min": 0, "max": 100},
            "MUTE": {"type": "command"},
            "UNMUTE": {"type": "command"},
        },
        "state_schema": {
            "playing": {"type": "boolean"},
            "volume": {"type": "int"},
            "muted": {"type": "boolean"},
            "current_track": {"type": "string"},
        },
    },
    "SENSOR": {
        "label": "Sensor",
        "icon": "📡",
        "actions": {
            "READ": {"type": "read"},
            "GET_BATTERY": {"type": "read"},
        },
        "state_schema": {
            "value": {"type": "float"},
            "unit": {"type": "string"},
            "battery": {"type": "int"},
        },
    },
    "HUB": {
        "label": "Hub/Bridge",
        "icon": "🏠",
        "actions": {
            "GET_STATUS": {"type": "read"},
            "GET_DEVICES": {"type": "read"},
        },
        "state_schema": {
            "online": {"type": "boolean"},
            "connected_devices": {"type": "int"},
        },
    },
    "COVER": {
        "label": "Cover/Blind",
        "icon": "🪟",
        "actions": {
            "OPEN": {"type": "command"},
            "CLOSE": {"type": "command"},
            "STOP": {"type": "command"},
            "SET_POSITION": {"type": "int", "min": 0, "max": 100, "unit": "%"},
        },
        "state_schema": {
            "position": {"type": "int", "min": 0, "max": 100},
            "state": {"type": "enum", "values": ["OPEN", "CLOSED", "OPENING", "CLOSING"]},
        },
    },
    "SCENE": {
        "label": "Scene Controller",
        "icon": "🎬",
        "actions": {
            "ACTIVATE": {"type": "command"},
            "DEACTIVATE": {"type": "command"},
        },
        "state_schema": {
            "active": {"type": "boolean"},
        },
    },
    "ROUTER": {
        "label": "Network Router",
        "icon": "🌐",
        "actions": {
            "REBOOT": {"type": "command", "requires_auth": True},
            "GET_STATUS": {"type": "read"},
            "BLOCK_DEVICE": {"type": "command", "requires_auth": True},
        },
        "state_schema": {
            "online": {"type": "boolean"},
            "connected_devices": {"type": "int"},
            "cpu_usage": {"type": "float"},
            "memory_usage": {"type": "float"},
        },
    },
}


# ── Protocol Translators ────────────────────────────────────
# Each translator converts a device's native protocol into
# the universal JSON contract.


class ProtocolTranslator:
    """Base class for protocol translators."""

    def normalize_state(self, raw_state: dict, device_type: str) -> dict:
        """Convert raw device state to normalized state."""
        return raw_state

    def translate_action(self, action: str, params: dict, raw_device: dict) -> dict:
        """Translate a universal action into a protocol-specific command."""
        return {"action": action, "params": params, "raw": raw_device}


class TuyaTranslator(ProtocolTranslator):
    """Translate Tuya protocol devices."""

    TUYA_TYPE_MAP = {
        "light": "LIGHT",
        "switch": "SWITCH",
        "cover": "COVER",
        "sensor": "SENSOR",
        "thermostat": "THERMOSTAT",
        "vacuum": "VACUUM",
    }

    def normalize_state(self, raw_state: dict, device_type: str) -> dict:
        state = {}
        # Tuya uses DPS (data point service) format
        for key, value in raw_state.items():
            if key.startswith("1") and isinstance(value, bool):
                state["power"] = "ON" if value else "OFF"
            elif key.startswith("2") and isinstance(value, int):
                state["brightness"] = value
            elif key.startswith("3") and isinstance(value, str):
                state["color"] = value
        return state

    def translate_action(self, action: str, params: dict, raw_device: dict) -> dict:
        # Build Tuya-specific command payload
        dps = {}
        if action == "TURN_ON":
            dps["1"] = True
        elif action == "TURN_OFF":
            dps["1"] = False
        elif action == "SET_BRIGHTNESS":
            dps["2"] = params.get("brightness", 50)
        elif action == "SET_COLOR":
            dps["3"] = params.get("color", "ffffff")

        return {
            "protocol": "tuya",
            "command": "set",
            "dps": dps,
            "dev_id": raw_device.get("tuya_id", ""),
        }


class MQTTTranslator(ProtocolTranslator):
    """Translate MQTT protocol devices."""

    def normalize_state(self, raw_state: dict, device_type: str) -> dict:
        state = {}
        for key, value in raw_state.items():
            state[key] = value
        return state

    def translate_action(self, action: str, params: dict, raw_device: dict) -> dict:
        topic = raw_device.get("mqtt_topic", "")
        payload = json.dumps({"action": action.lower(), **params})
        return {
            "protocol": "mqtt",
            "topic": f"{topic}/set",
            "payload": payload,
            "qos": 1,
        }


class HomeAssistantTranslator(ProtocolTranslator):
    """Translate Home Assistant devices."""

    def normalize_state(self, raw_state: dict, device_type: str) -> dict:
        state = {}
        ha_state = raw_state.get("state", "")
        attrs = raw_state.get("attributes", {})

        state["power"] = "ON" if ha_state == "on" else "OFF"
        if "brightness" in attrs:
            state["brightness"] = int(attrs["brightness"] / 255 * 100)
        if "current_temperature" in attrs:
            state["current_temp"] = attrs["current_temperature"]
        if "temperature" in attrs:
            state["target_temp"] = attrs["temperature"]

        return state

    def translate_action(self, action: str, params: dict, raw_device: dict) -> dict:
        entity_id = raw_device.get("ha_entity_id", "")
        service = action.lower()
        return {
            "protocol": "home_assistant",
            "entity_id": entity_id,
            "service": service,
            "service_data": params,
        }


class UPnPTranslator(ProtocolTranslator):
    """Translate UPnP/DLNA media devices."""

    def normalize_state(self, raw_state: dict, device_type: str) -> dict:
        return {
            "playing": raw_state.get("transport_state") == "PLAYING",
            "volume": raw_state.get("volume", 0),
            "muted": raw_state.get("mute") == "1",
            "current_track": raw_state.get("title", ""),
        }

    def translate_action(self, action: str, params: dict, raw_device: dict) -> dict:
        ip = raw_device.get("ip", "")
        port = raw_device.get("port", 80)
        return {
            "protocol": "upnp",
            "url": f"http://{ip}:{port}/upnp/control/AVTransport",
            "action": action,
            "params": params,
        }


class MiioTranslator(ProtocolTranslator):
    """Translate Xiaomi/Miio protocol (robot vacuums, sensors)."""

    MIIO_COMMANDS = {
        "START_CLEANING": "s_start",
        "STOP": "s_stop",
        "PAUSE": "s_pause",
        "DOCK": "s_charge",
        "FIND_ROBOT": "find_me",
        "GET_STATUS": "get_status",
    }

    def normalize_state(self, raw_state: dict, device_type: str) -> dict:
        return {
            "battery": raw_state.get("battery", 0),
            "power": "ON" if raw_state.get("state") == "cleaning" else "OFF",
            "suction_level": raw_state.get("fan_speed", "normal"),
            "cleaning_area": raw_state.get("area", 0),
        }

    def translate_action(self, action: str, params: dict, raw_device: dict) -> dict:
        return {
            "protocol": "miio",
            "command": self.MIIO_COMMANDS.get(action, action),
            "params": params,
            "ip": raw_device.get("ip", ""),
            "token": raw_device.get("miio_token", ""),
        }


# ── Universal HAL ────────────────────────────────────────────


class UniversalHAL:
    """
    Universal Hardware Abstraction Layer.

    Normalizes every device into the unified JSON contract.
    Zero hardcoding — protocols are registered dynamically.
    """

    def __init__(self):
        self._translators: Dict[str, ProtocolTranslator] = {
            "tuya": TuyaTranslator(),
            "mqtt": MQTTTranslator(),
            "home_assistant": HomeAssistantTranslator(),
            "ha": HomeAssistantTranslator(),
            "upnp": UPnPTranslator(),
            "dlna": UPnPTranslator(),
            "miio": MiioTranslator(),
            "xiaomi": MiioTranslator(),
        }
        self._device_types = DEVICE_TYPES

    def register_translator(self, protocol: str, translator: ProtocolTranslator):
        """Register a new protocol translator."""
        self._translators[protocol.lower()] = translator

    def normalize_device(self, raw_device: dict) -> dict:
        """
        Convert a raw device into the universal JSON contract.

        Input: raw device data from any protocol (Tuya, MQTT, HA, etc.)
        Output: normalized JSON device contract
        """
        protocol = raw_device.get("protocol", "unknown").lower()
        device_type = raw_device.get("device_type", "unknown").upper()

        # Get the type definition
        type_def = self._device_types.get(device_type, {})

        # Get the translator for this protocol
        translator = self._translators.get(protocol, ProtocolTranslator())

        # Normalize the state
        raw_state = raw_device.get("state", {})
        normalized_state = translator.normalize_state(raw_state, device_type)

        # Build normalized actions from type definition
        normalized_actions = {}
        for action_name, action_def in type_def.get("actions", {}).items():
            normalized_actions[action_name] = {
                "type": action_def.get("type", "command"),
            }
            if "min" in action_def:
                normalized_actions[action_name]["min"] = action_def["min"]
            if "max" in action_def:
                normalized_actions[action_name]["max"] = action_def["max"]
            if "unit" in action_def:
                normalized_actions[action_name]["unit"] = action_def["unit"]
            if "values" in action_def:
                normalized_actions[action_name]["values"] = action_def["values"]
            if "requires_auth" in action_def:
                normalized_actions[action_name]["requires_auth"] = action_def["requires_auth"]

        # Build the universal contract
        contract = {
            "device_id": raw_device.get("id", raw_device.get("mac", "")),
            "device_type": device_type,
            "type_label": type_def.get("label", device_type),
            "type_icon": type_def.get("icon", "❓"),
            "network_address": raw_device.get("ip", ""),
            "network_port": raw_device.get("port", 80),
            "mac_address": raw_device.get("mac", ""),
            "protocol": protocol,
            "protocol_raw": raw_device,
            "manufacturer": raw_device.get("manufacturer", ""),
            "model": raw_device.get("model", ""),
            "firmware_version": raw_device.get("firmware", ""),
            "name": raw_device.get("name", raw_device.get("hostname", "")),
            "room": raw_device.get("room", "unknown"),
            "state": normalized_state,
            "normalized_actions": normalized_actions,
            "state_schema": type_def.get("state_schema", {}),
            "last_seen": raw_device.get("last_seen", time.time()),
            "is_online": raw_device.get("status") == "online",
            "signal_strength": raw_device.get("signal_strength"),
            "fingerprint": self._fingerprint(raw_device),
        }

        return contract

    def translate_action(self, action: str, params: dict, device: dict) -> dict:
        """
        Translate a universal action into a protocol-specific command.
        Returns the command payload for the device bridge to execute.
        """
        protocol = device.get("protocol", "unknown").lower()
        translator = self._translators.get(protocol, ProtocolTranslator())
        return translator.translate_action(action, params, device)

    def get_type_definition(self, device_type: str) -> Optional[dict]:
        """Get the type definition for a device type."""
        return self._device_types.get(device_type.upper())

    def get_all_types(self) -> dict:
        """Get all supported device type definitions."""
        return self._device_types

    def _fingerprint(self, device: dict) -> str:
        """Generate a unique fingerprint for a device."""
        key = f"{device.get('ip', '')}:{device.get('mac', '')}:{device.get('protocol', '')}"
        return hashlib.md5(key.encode()).hexdigest()[:12]


# ── Global singleton ───────────────────────────────────────

_hal: Optional[UniversalHAL] = None


def get_hal() -> UniversalHAL:
    """Get or create the global UniversalHAL instance."""
    global _hal
    if _hal is None:
        _hal = UniversalHAL()
    return _hal
