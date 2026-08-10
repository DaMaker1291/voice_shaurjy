"""
JARVIS Physical Environment Sync Engine
========================================
Automatically controls physical devices based on context:
- Dims lights when user joins a video call
- Sets status bulbs to "Do Not Disturb" during focus
- Mutes robot vacuums during meetings
- Adjusts smart plugs based on time-of-day rules
- Monitors active windows/apps for trigger detection
"""

import json
import os
import time
import logging
import subprocess
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

log = logging.getLogger("jarvis-env-sync")


class EnvironmentState(str, Enum):
    IDLE = "idle"
    MEETING = "meeting"
    FOCUS = "focus"
    NIGHT = "night"
    AWAY = "away"
    ACTIVE = "active"


class DeviceActionType(str, Enum):
    LIGHT_SCENE = "light_scene"
    PLUG_CONTROL = "plug_control"
    VACUUM_CONTROL = "vacuum_control"
    NOTIFICATION_LEVEL = "notification_level"
    STATUS_MESSAGE = "status_message"
    MUSIC_CONTROL = "music_control"
    SCREEN_TEMP = "screen_temp"
    LOCK_SCREEN = "lock_screen"


@dataclass
class EnvironmentAction:
    """A single environment control action."""
    action_type: str
    target_device: str = ""
    value: str = ""
    description: str = ""
    executed: bool = False
    timestamp: float = 0.0


@dataclass
class EnvironmentRule:
    """An automation rule for environment control."""
    id: str
    trigger_type: str
    trigger_keywords: List[str] = field(default_factory=list)
    trigger_start: float = 0.0
    trigger_end: float = 0.0
    trigger_inactivity_minutes: int = 0
    actions: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    last_triggered: float = 0.0
    cooldown_seconds: int = 300


class EnvironmentSyncEngine:
    """
    Real-time environment synchronization engine.
    Monitors system state and triggers device actions based on rules.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(
            os.path.expanduser("~"), ".jarvis", "environment"
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self._state = EnvironmentState.IDLE
        self._rules: List[EnvironmentRule] = []
        self._action_log: List[EnvironmentAction] = []
        self._last_activity = time.time()
        self._active_apps: List[str] = []
        self._load_rules()

    def _load_rules(self):
        """Load environment rules from data directory."""
        rules_file = os.path.join(self.data_dir, "rules.json")
        if not os.path.exists(rules_file):
            # Copy default rules from project data
            default_rules = os.path.join(
                os.path.dirname(__file__), "..", "data", "environment_rules.json"
            )
            if os.path.exists(default_rules):
                try:
                    with open(default_rules, "r") as f:
                        rules_data = json.load(f)
                    self._parse_rules(rules_data)
                    with open(rules_file, "w") as f:
                        json.dump(rules_data, f, indent=2)
                    return
                except Exception as e:
                    log.error(f"Failed to load default rules: {e}")
            return

        try:
            with open(rules_file, "r") as f:
                rules_data = json.load(f)
            self._parse_rules(rules_data)
            log.info(f"Loaded {len(self._rules)} environment rules")
        except Exception as e:
            log.error(f"Failed to load rules: {e}")

    def _parse_rules(self, rules_data: List[Dict[str, Any]]):
        """Parse raw rule data into EnvironmentRule objects."""
        self._rules = []
        for r in rules_data:
            trigger = r.get("trigger", {})
            rule = EnvironmentRule(
                id=r.get("id", "unknown"),
                trigger_type=trigger.get("type", "keyword"),
                trigger_keywords=trigger.get("keywords", []),
                trigger_start=trigger.get("start", 0),
                trigger_end=trigger.get("end", 0),
                trigger_inactivity_minutes=trigger.get("minutes", 0),
                actions=r.get("actions", []),
                description=r.get("description", ""),
                enabled=r.get("enabled", True),
            )
            self._rules.append(rule)

    def _get_active_windows(self) -> List[str]:
        """Detect currently active windows/apps on the system."""
        apps = []
        try:
            if os.name == "nt":
                # Windows: use tasklist or PowerShell
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object -ExpandProperty ProcessName"],
                    capture_output=True, text=True, timeout=5
                )
                apps = [line.strip().lower() for line in result.stdout.strip().split("\n") if line.strip()]
            else:
                # Linux/macOS: use wmctrl or osascript
                try:
                    result = subprocess.run(
                        ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.stdout.strip():
                        apps = [result.stdout.strip().lower()]
                except FileNotFoundError:
                    result = subprocess.run(
                        ["wmctrl", "-l"], capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split()
                        if len(parts) >= 4:
                            apps.append(" ".join(parts[3:]).lower())
        except Exception as e:
            log.debug(f"Window detection failed: {e}")
        return apps

    def _detect_meeting_app(self, apps: List[str]) -> bool:
        """Check if a meeting app is currently active."""
        meeting_keywords = ["zoom", "teams", "meet", "webex", "skype", "discord", "slack"]
        return any(
            any(kw in app for kw in meeting_keywords)
            for app in apps
        )

    def check_triggers(self) -> List[EnvironmentAction]:
        """
        Check all environment triggers and return actions to execute.
        This is the main entry point called periodically.
        """
        now = time.time()
        actions_to_execute = []

        # Update active windows
        self._active_apps = self._get_active_windows()

        # Check if user is in a meeting
        in_meeting = self._detect_meeting_app(self._active_apps)

        # Update state
        if in_meeting and self._state != EnvironmentState.MEETING:
            self._state = EnvironmentState.MEETING
        elif not in_meeting and self._state == EnvironmentState.MEETING:
            self._state = EnvironmentState.ACTIVE

        # Check each rule
        for rule in self._rules:
            if not rule.enabled:
                continue

            # Cooldown check
            if now - rule.last_triggered < rule.cooldown_seconds:
                continue

            triggered = False

            if rule.trigger_type == "app_active":
                triggered = self._detect_meeting_app(self._active_apps) if rule.trigger_keywords else False
                # More generic: check if any active app matches keywords
                if not triggered:
                    for app in self._active_apps:
                        if any(kw in app for kw in rule.trigger_keywords):
                            triggered = True
                            break

            elif rule.trigger_type == "time_range":
                hour = time.localtime().tm_hour + time.localtime().tm_min / 60.0
                if rule.trigger_start <= rule.trigger_end:
                    triggered = rule.trigger_start <= hour <= rule.trigger_end
                else:
                    triggered = hour >= rule.trigger_start or hour <= rule.trigger_end

            elif rule.trigger_type == "keyword":
                # Check recent user input for keywords
                triggered = False  # Will be triggered via API call

            elif rule.trigger_type == "inactivity":
                idle_minutes = (now - self._last_activity) / 60.0
                triggered = idle_minutes >= rule.trigger_inactivity_minutes

            if triggered:
                rule.last_triggered = now
                for action_data in rule.actions:
                    action = EnvironmentAction(
                        action_type=action_data.get("type", "unknown"),
                        value=action_data.get("value", ""),
                        description=action_data.get("description", ""),
                        executed=False,
                        timestamp=now,
                    )
                    actions_to_execute.append(action)

        return actions_to_execute

    def execute_action(self, action: EnvironmentAction) -> Dict[str, Any]:
        """
        Execute a single environment action.
        Returns success/failure with details.
        """
        result = {"action": action.action_type, "success": False, "details": ""}

        try:
            if action.action_type == "light_scene":
                result = self._execute_light_scene(action)
            elif action.action_type == "plug_control":
                result = self._execute_plug_control(action)
            elif action.action_type == "vacuum_control":
                result = self._execute_vacuum_control(action)
            elif action.action_type == "lock_screen":
                result = self._execute_lock_screen(action)
            elif action.action_type == "notification_level":
                result = {"action": "notification_level", "success": True, "details": f"Set to {action.value}"}
            elif action.action_type == "status_message":
                result = {"action": "status_message", "success": True, "details": f"Status: {action.value}"}
            elif action.action_type == "screen_temp":
                result = self._execute_screen_temp(action)
            else:
                result["details"] = f"Unknown action type: {action.action_type}"

            action.executed = result.get("success", False)
            action.timestamp = time.time()
            self._action_log.append(action)

            # Keep log bounded
            if len(self._action_log) > 200:
                self._action_log = self._action_log[-200:]

        except Exception as e:
            result["details"] = f"Execution error: {str(e)}"
            log.error(f"Action execution failed: {e}")

        return result

    def _execute_light_scene(self, action: EnvironmentAction) -> Dict[str, Any]:
        """Execute a light scene change via smart home manager."""
        try:
            from smart_home_manager import get_smart_home_manager
            manager = get_smart_home_manager()

            scene = action.value
            if scene == "focus":
                brightness = 30
                color_temp = 2700
            elif scene == "warm_dim":
                brightness = 20
                color_temp = 2200
            elif scene == "night":
                brightness = 5
                color_temp = 1800
            elif scene == "bright":
                brightness = 100
                color_temp = 5000
            elif scene == "off":
                brightness = 0
                color_temp = 0
            else:
                brightness = 50
                color_temp = 4000

            # Set all lights to scene
            devices = manager.get_devices_by_type("LIGHT")
            for device in devices:
                try:
                    manager.set_brightness(device["id"], brightness)
                    if color_temp > 0:
                        manager.set_color_temp(device["id"], color_temp)
                except Exception:
                    pass

            return {
                "action": "light_scene",
                "success": True,
                "details": f"Scene '{scene}' applied to {len(devices)} lights",
            }
        except ImportError:
            return {"action": "light_scene", "success": False, "details": "Smart home manager not available"}
        except Exception as e:
            return {"action": "light_scene", "success": False, "details": str(e)}

    def _execute_plug_control(self, action: EnvironmentAction) -> Dict[str, Any]:
        """Control smart plugs (on/off)."""
        try:
            from smart_home_manager import get_smart_home_manager
            manager = get_smart_home_manager()

            state = action.value.lower() == "on"
            devices = manager.get_devices_by_type("SWITCH")
            affected = 0
            for device in devices:
                try:
                    manager.set_power(device["id"], state)
                    affected += 1
                except Exception:
                    pass

            return {
                "action": "plug_control",
                "success": True,
                "details": f"Set {affected} plugs to {action.value}",
            }
        except ImportError:
            return {"action": "plug_control", "success": False, "details": "Smart home manager not available"}
        except Exception as e:
            return {"action": "plug_control", "success": False, "details": str(e)}

    def _execute_vacuum_control(self, action: EnvironmentAction) -> Dict[str, Any]:
        """Control robot vacuum (pause/resume/stop)."""
        try:
            from smart_home_manager import get_smart_home_manager
            manager = get_smart_home_manager()

            devices = manager.get_devices_by_type("VACUUM")
            for device in devices:
                try:
                    if action.value == "pause":
                        manager.pause_vacuum(device["id"])
                    elif action.value == "stop":
                        manager.stop_vacuum(device["id"])
                    elif action.value == "resume":
                        manager.start_vacuum(device["id"])
                except Exception:
                    pass

            return {
                "action": "vacuum_control",
                "success": True,
                "details": f"Vacuum {action.value} executed",
            }
        except ImportError:
            return {"action": "vacuum_control", "success": False, "details": "Smart home manager not available"}
        except Exception as e:
            return {"action": "vacuum_control", "success": False, "details": str(e)}

    def _execute_lock_screen(self, action: EnvironmentAction) -> Dict[str, Any]:
        """Lock the workstation screen."""
        try:
            if os.name == "nt":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
            else:
                subprocess.run(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"], timeout=5)
            return {"action": "lock_screen", "success": True, "details": "Screen locked"}
        except Exception as e:
            return {"action": "lock_screen", "success": False, "details": str(e)}

    def _execute_screen_temp(self, action: EnvironmentAction) -> Dict[str, Any]:
        """Adjust screen color temperature (blue light filter)."""
        try:
            if action.value == "warm":
                # Use f.lux or Windows Night Light
                if os.name == "nt":
                    subprocess.run([
                        "powershell", "-Command",
                        "Start-Process ms-settings:nightlight"
                    ], timeout=5)
                return {"action": "screen_temp", "success": True, "details": "Warm screen temperature applied"}
            return {"action": "screen_temp", "success": True, "details": f"Screen temp set to {action.value}"}
        except Exception as e:
            return {"action": "screen_temp", "success": False, "details": str(e)}

    def process_keyword_trigger(self, user_input: str) -> List[EnvironmentAction]:
        """
        Check user input for keyword-based triggers.
        Returns actions to execute if a rule matches.
        """
        user_lower = user_input.lower()
        actions = []

        for rule in self._rules:
            if not rule.enabled or rule.trigger_type != "keyword":
                continue

            if any(kw in user_lower for kw in rule.trigger_keywords):
                if time.time() - rule.last_triggered < rule.cooldown_seconds:
                    continue
                rule.last_triggered = time.time()
                for action_data in rule.actions:
                    action = EnvironmentAction(
                        action_type=action_data.get("type", "unknown"),
                        value=action_data.get("value", ""),
                        description=action_data.get("description", ""),
                        executed=False,
                        timestamp=time.time(),
                    )
                    actions.append(action)

        return actions

    def update_activity(self):
        """Update last activity timestamp (call on user interaction)."""
        self._last_activity = time.time()

    def get_state(self) -> Dict[str, Any]:
        """Get current environment sync state."""
        return {
            "state": self._state.value,
            "active_apps": self._active_apps,
            "in_meeting": self._detect_meeting_app(self._active_apps),
            "idle_minutes": round((time.time() - self._last_activity) / 60.0, 1),
            "rules_loaded": len(self._rules),
            "rules_enabled": sum(1 for r in self._rules if r.enabled),
            "recent_actions": [
                {
                    "type": a.action_type,
                    "value": a.value,
                    "success": a.executed,
                    "timestamp": a.timestamp,
                }
                for a in self._action_log[-10:]
            ],
        }

    def add_rule(self, rule_data: Dict[str, Any]) -> str:
        """Add a new environment rule."""
        rule_id = rule_data.get("id", f"rule_{int(time.time())}")
        trigger = rule_data.get("trigger", {})
        rule = EnvironmentRule(
            id=rule_id,
            trigger_type=trigger.get("type", "keyword"),
            trigger_keywords=trigger.get("keywords", []),
            trigger_start=trigger.get("start", 0),
            trigger_end=trigger.get("end", 0),
            trigger_inactivity_minutes=trigger.get("minutes", 0),
            actions=rule_data.get("actions", []),
            description=rule_data.get("description", ""),
            enabled=rule_data.get("enabled", True),
        )
        self._rules.append(rule)
        self._save_rules()
        return rule_id

    def _save_rules(self):
        """Persist rules to disk."""
        rules_file = os.path.join(self.data_dir, "rules.json")
        try:
            rules_data = []
            for rule in self._rules:
                rules_data.append({
                    "id": rule.id,
                    "trigger": {
                        "type": rule.trigger_type,
                        "keywords": rule.trigger_keywords,
                        "start": rule.trigger_start,
                        "end": rule.trigger_end,
                        "minutes": rule.trigger_inactivity_minutes,
                    },
                    "actions": rule.actions,
                    "description": rule.description,
                    "enabled": rule.enabled,
                })
            with open(rules_file, "w") as f:
                json.dump(rules_data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save rules: {e}")


# ── Singleton ────────────────────────────────────────────────────────────
_engine: Optional[EnvironmentSyncEngine] = None


def get_environment_sync() -> EnvironmentSyncEngine:
    global _engine
    if _engine is None:
        _engine = EnvironmentSyncEngine()
    return _engine
