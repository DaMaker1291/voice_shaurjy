"""
JARVIS Tapo Protocol Client
=============================
Real TP-Link Tapo smart plug control over local WiFi.
Uses the official `tapo` library for P100/P110/P125 plugs.

This is NOT a simulation. Commands execute on real hardware.
"""

import os
import time
import threading
import json
import socket
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

try:
    from tapo import ApiClient
    from tapo.responses import DeviceInfoSmartPlug
    _HAS_TAPO = True
except ImportError:
    _HAS_TAPO = False


@dataclass
class TapoDevice:
    """A real TP-Link Tapo device on the local network."""
    ip: str
    name: str
    model: str = ""
    device_type: str = "SWITCH"
    username: str = ""
    password: str = ""
    is_online: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    last_controlled: float = 0.0
    energy_data: Dict[str, Any] = field(default_factory=dict)
    uptime: int = 0
    fw_version: str = ""
    signal_strength: int = 0

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "name": self.name,
            "model": self.model,
            "device_type": self.device_type,
            "is_online": self.is_online,
            "state": self.state,
            "last_controlled": self.last_controlled,
            "energy_data": self.energy_data,
            "uptime": self.uptime,
            "fw_version": self.fw_version,
            "signal_strength": self.signal_strength,
        }


class TapoClient:
    """
    Real TP-Link Tapo smart plug controller.
    Connects to devices over local WiFi and executes actual commands.
    """

    def __init__(self):
        self._devices: Dict[str, TapoDevice] = {}
        self._clients: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._credentials: Dict[str, str] = {}

    def set_credentials(self, username: str, password: str):
        """Set Tapo device credentials (same for all devices)."""
        self._credentials = {"username": username, "password": password}

    def add_device(self, ip: str, name: str = "", username: str = "", password: str = "") -> TapoDevice:
        """Register a Tapo device by IP."""
        with self._lock:
            device = TapoDevice(
                ip=ip,
                name=name or f"Tapo {ip}",
                username=username or self._credentials.get("username", ""),
                password=password or self._credentials.get("password", ""),
            )
            self._devices[ip] = device
            return device

    def _get_client(self, ip: str):
        """Get or create a Tapo API client for a device."""
        if ip in self._clients:
            return self._clients[ip]

        if not _HAS_TAPO:
            return None

        device = self._devices.get(ip)
        if not device:
            return None

        try:
            client = ApiClient(device.username, device.password)
            self._clients[ip] = client
            return client
        except Exception:
            return None

    def _get_tapo_client(self, ip: str):
        """Get the device-specific Tapo client."""
        if not _HAS_TAPO:
            return None

        device = self._devices.get(ip)
        if not device:
            return None

        try:
            client = self._get_client(ip)
            if client:
                return client.smart_plug(device.ip)
        except Exception:
            pass
        return None

    def get_device_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get real device info from a Tapo plug."""
        plug = self._get_tapo_client(ip)
        if not plug:
            return None

        try:
            info = plug.get_device_info()
            device = self._devices.get(ip)
            if device:
                device.is_online = True
                device.model = getattr(info, "model", "")
                device.fw_version = getattr(info, "firmware_version", "")
                device.uptime = getattr(info, "uptime", 0)
                device.signal_strength = getattr(info, "signal_level", 0)
                device.state = {
                    "power": "ON" if getattr(info, "device_on", False) else "OFF",
                    "brightness": getattr(info, "brightness", None),
                    "overheat": getattr(info, "overheat_status", "NORMAL"),
                }
            return device.to_dict() if device else None
        except Exception as e:
            if device:
                device.is_online = False
            return None

    def turn_on(self, ip: str) -> Dict[str, Any]:
        """Turn ON a real Tapo smart plug."""
        plug = self._get_tapo_client(ip)
        if not plug:
            return {"success": False, "error": "Client not available"}

        try:
            plug.on()
            device = self._devices.get(ip)
            if device:
                device.is_online = True
                device.state["power"] = "ON"
                device.last_controlled = time.time()
            return {"success": True, "action": "turn_on", "ip": ip}
        except Exception as e:
            return {"success": False, "error": str(e), "ip": ip}

    def turn_off(self, ip: str) -> Dict[str, Any]:
        """Turn OFF a real Tapo smart plug."""
        plug = self._get_tapo_client(ip)
        if not plug:
            return {"success": False, "error": "Client not available"}

        try:
            plug.off()
            device = self._devices.get(ip)
            if device:
                device.is_online = True
                device.state["power"] = "OFF"
                device.last_controlled = time.time()
            return {"success": True, "action": "turn_off", "ip": ip}
        except Exception as e:
            return {"success": False, "error": str(e), "ip": ip}

    def toggle(self, ip: str) -> Dict[str, Any]:
        """Toggle a Tapo smart plug."""
        device = self._devices.get(ip)
        if device and device.state.get("power") == "ON":
            return self.turn_off(ip)
        return self.turn_on(ip)

    def get_energy_usage(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get real-time energy usage from a Tapo P110."""
        plug = self._get_tapo_client(ip)
        if not plug:
            return None

        try:
            energy = plug.get_realtime_energy()
            device = self._devices.get(ip)
            if device:
                device.energy_data = {
                    "current_ma": getattr(energy, "current_ma", 0),
                    "voltage_mv": getattr(energy, "voltage_mv", 0),
                    "power_mw": getattr(energy, "power_mw", 0),
                    "total_wh": getattr(energy, "total_wh", 0),
                }
            return device.energy_data if device else None
        except Exception:
            return None

    def set_brightness(self, ip: str, brightness: int) -> Dict[str, Any]:
        """Set brightness on a Tapo dimmable plug (P125)."""
        plug = self._get_tapo_client(ip)
        if not plug:
            return {"success": False, "error": "Client not available"}

        try:
            plug.set_brightness(brightness)
            device = self._devices.get(ip)
            if device:
                device.state["brightness"] = brightness
                device.last_controlled = time.time()
            return {"success": True, "action": "set_brightness", "brightness": brightness, "ip": ip}
        except Exception as e:
            return {"success": False, "error": str(e), "ip": ip}

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get status of all registered Tapo devices."""
        devices = []
        with self._lock:
            for ip, device in self._devices.items():
                # Try to get fresh info
                try:
                    self.get_device_info(ip)
                except Exception:
                    pass
                devices.append(device.to_dict())
        return devices

    def discover_on_network(self, ip_range: str = "") -> List[Dict[str, Any]]:
        """
        Discover Tapo devices on the local network.
        Tries common Tapo IPs and checks for responses.
        """
        if not ip_range:
            # Detect local subnet
            ip_range = _detect_subnet()

        discovered = []

        # Check known Tapo IPs from ARP scan using device_patterns.json keywords
        tapo_keywords = _load_tapo_keywords()
        try:
            import subprocess
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=15)
            for line in result.stdout.splitlines():
                for keyword in tapo_keywords:
                    if keyword in line.lower():
                        import re
                        match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                        if match:
                            ip = match.group(1)
                            discovered.append({
                                "ip": ip,
                                "name": line.split("(")[0].strip() if "(" in line else f"Tapo {ip}",
                                "protocol": "tapo",
                                "manufacturer": "TP-Link",
                                "device_type": "SWITCH",
                            })
                        break
        except Exception:
            pass

        return discovered


# ── Global singleton ───────────────────────────────────────

_tapo: Optional[TapoClient] = None
_tapo_lock = threading.Lock()


def _detect_subnet() -> str:
    """Detect the local subnet prefix dynamically, with env override."""
    env_subnet = os.environ.get("JARVIS_LOCAL_SUBNET", "").strip()
    if env_subnet:
        return env_subnet
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return ".".join(local_ip.split(".")[:3])
    except Exception:
        return ""


def _load_tapo_keywords() -> List[str]:
    """Load Tapo discovery keywords from device_patterns.json (fallback: generic set)."""
    default_keywords = ["tapo", "kasa", "tp-link", "smart plug"]
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_patterns.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        keywords = []
        for pattern in data.get("patterns", []):
            if pattern.get("protocol") == "tapo":
                keywords.extend(pattern.get("match_hostname_contains", []))
        return list(dict.fromkeys(keywords)) or default_keywords
    except (FileNotFoundError, json.JSONDecodeError):
        return default_keywords


def get_tapo_client() -> TapoClient:
    """Get or create the global TapoClient instance."""
    global _tapo
    with _tapo_lock:
        if _tapo is None:
            _tapo = TapoClient()
            # Set credentials from environment
            username = os.environ.get("TAPO_USERNAME", "")
            password = os.environ.get("TAPO_PASSWORD", "")
            if username and password:
                _tapo.set_credentials(username, password)
        return _tapo
