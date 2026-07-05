"""
JARVIS Phone Client
====================
Real smartphone control over WiFi via ADB (Android Debug Bridge)
and mDNS service discovery.

Supports:
- Samsung Galaxy devices (Note20, S24, S24 Ultra)
- Any Android device with ADB over WiFi enabled
- mDNS/Bonjour device discovery
- Screen lock/unlock, app launch, volume, brightness, notification
"""

import os
import time
import threading
import subprocess
import re
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class PhoneDevice:
    """A real smartphone on the local network."""
    ip: str
    name: str
    device_type: str = "PHONE"
    manufacturer: str = ""
    model: str = ""
    os: str = "Android"
    protocol: str = "adb"
    is_online: bool = False
    adb_port: int = 5555
    state: Dict[str, Any] = field(default_factory=dict)
    last_action: float = 0.0
    adb_key: str = ""

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "name": self.name,
            "device_type": self.device_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "os": self.os,
            "protocol": self.protocol,
            "is_online": self.is_online,
            "state": self.state,
            "last_action": self.last_action,
        }


class PhoneClient:
    """
    Real smartphone controller over WiFi.
    Uses ADB (Android Debug Bridge) for command execution.
    """

    def __init__(self):
        self._phones: Dict[str, PhoneDevice] = {}
        self._adb_connected: Dict[str, bool] = {}
        self._lock = threading.Lock()

    def add_phone(self, ip: str, name: str = "", model: str = "",
                  manufacturer: str = "", adb_port: int = 5555) -> PhoneDevice:
        """Register a phone by IP."""
        with self._lock:
            phone = PhoneDevice(
                ip=ip,
                name=name or f"Phone {ip}",
                model=model,
                manufacturer=manufacturer,
                adb_port=adb_port,
            )
            self._phones[ip] = phone
            return phone

    def _run_adb(self, ip: str, command: str, timeout: int = 10) -> Dict[str, Any]:
        """Execute an ADB command on a phone."""
        try:
            target = f"{ip}:{self._phones.get(ip, PhoneDevice(ip=ip)).adb_port}"
            cmd = ["adb", "-s", target] + command.split()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except FileNotFoundError:
            return {"success": False, "error": "ADB not installed. Install with: brew install android-platform-tools"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "ADB command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def connect_adb(self, ip: str, port: int = 5555) -> Dict[str, Any]:
        """Connect to a phone via ADB over WiFi."""
        try:
            # First try to connect
            result = subprocess.run(
                ["adb", "connect", f"{ip}:{port}"],
                capture_output=True, text=True, timeout=10
            )

            if "connected" in result.stdout.lower():
                self._adb_connected[ip] = True
                phone = self._phones.get(ip)
                if phone:
                    phone.is_online = True
                    phone.adb_port = port
                    phone.last_action = time.time()
                return {"success": True, "action": "connect", "ip": ip, "port": port}
            else:
                return {"success": False, "error": result.stdout.strip() or result.stderr.strip()}

        except FileNotFoundError:
            return {"success": False, "error": "ADB not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disconnect_adb(self, ip: str) -> Dict[str, Any]:
        """Disconnect from a phone."""
        try:
            result = subprocess.run(
                ["adb", "disconnect", f"{ip}"],
                capture_output=True, text=True, timeout=5
            )
            self._adb_connected[ip] = False
            phone = self._phones.get(ip)
            if phone:
                phone.is_online = False
            return {"success": True, "action": "disconnect"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_device_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get real device info from a phone."""
        if not self._adb_connected.get(ip):
            self.connect_adb(ip)

        result = self._run_adb(ip, "shell getprop")
        if result["success"]:
            props = {}
            for line in result["stdout"].splitlines():
                if "[" in line and "]" in line:
                    match = re.match(r'\[(.+?)\]:\s*\[(.+?)\]', line)
                    if match:
                        props[match.group(1)] = match.group(2)

            phone = self._phones.get(ip)
            if phone:
                phone.is_online = True
                phone.model = props.get("ro.product.model", phone.model)
                phone.manufacturer = props.get("ro.product.manufacturer", phone.manufacturer)
                phone.os_version = props.get("ro.build.version.release", "")
                phone.state = {
                    "model": phone.model,
                    "manufacturer": phone.manufacturer,
                    "android_version": props.get("ro.build.version.release", ""),
                    "sdk_version": props.get("ro.build.version.sdk", ""),
                    "device_name": props.get("ro.product.name", ""),
                }
                phone.last_action = time.time()
                return phone.to_dict()
        return None

    def get_screen_state(self, ip: str) -> Dict[str, Any]:
        """Get real screen state (on/off, locked/unlocked)."""
        result = self._run_adb(ip, "shell dumpsys power")
        if result["success"]:
            screen_on = "Display Power: state=ON" in result["stdout"]
            return {"screen_on": screen_on}
        return {"screen_on": None}

    def get_battery_state(self, ip: str) -> Dict[str, Any]:
        """Get real battery level and charging state."""
        result = self._run_adb(ip, "shell dumpsys battery")
        if result["success"]:
            level_match = re.search(r"level:\s*(\d+)", result["stdout"])
            status_match = re.search(r"status:\s*(\d+)", result["stdout"])
            temp_match = re.search(r"temperature:\s*(\d+)", result["stdout"])

            status_map = {1: "unknown", 2: "charging", 3: "discharging",
                         4: "not_charging", 5: "full"}

            return {
                "level": int(level_match.group(1)) if level_match else None,
                "status": status_map.get(int(status_match.group(1)), "unknown") if status_match else "unknown",
                "temperature_c": int(temp_match.group(1)) / 10 if temp_match else None,
            }
        return {}

    def get_volume(self, ip: str) -> Dict[str, Any]:
        """Get current volume levels."""
        result = self._run_adb(ip, "shell dumpsys audio")
        if result["success"]:
            volumes = {}
            for line in result["stdout"].splitlines():
                if "STREAM_MUSIC" in line or "STREAM_RING" in line:
                    match = re.search(r"index:\s*(\d+)", line)
                    if match:
                        stream = "music" if "MUSIC" in line else "ring"
                        volumes[stream] = int(match.group(1))
            return volumes
        return {}

    def set_volume(self, ip: str, stream: str, level: int) -> Dict[str, Any]:
        """Set volume level (0-15)."""
        result = self._run_adb(ip, f"shell media volume --stream {stream} --set {level}")
        return {"success": result["success"], "action": "set_volume", "stream": stream, "level": level}

    def set_brightness(self, ip: str, level: int) -> Dict[str, Any]:
        """Set screen brightness (0-255)."""
        # First enable manual brightness
        self._run_adb(ip, "shell settings put system screen_brightness_mode 0")
        result = self._run_adb(ip, f"shell settings put system screen_brightness {level}")
        return {"success": result["success"], "action": "set_brightness", "level": level}

    def lock_screen(self, ip: str) -> Dict[str, Any]:
        """Lock the phone screen."""
        result = self._run_adb(ip, "shell input keyevent 26")
        return {"success": result["success"], "action": "lock_screen"}

    def unlock_screen(self, ip: str) -> Dict[str, Any]:
        """Unlock the phone screen (wakes up)."""
        # Wake up
        self._run_adb(ip, "shell input keyevent 26")
        time.sleep(0.5)
        # Swipe up to unlock
        result = self._run_adb(ip, "shell input swipe 540 1800 540 800 300")
        return {"success": result["success"], "action": "unlock_screen"}

    def launch_app(self, ip: str, package: str) -> Dict[str, Any]:
        """Launch an app by package name."""
        result = self._run_adb(ip, f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1")
        return {"success": result["success"], "action": "launch_app", "package": package}

    def take_screenshot(self, ip: str, save_path: str = "/tmp/screenshot.png") -> Dict[str, Any]:
        """Take a real screenshot from the phone."""
        remote_path = "/sdcard/screenshot.png"
        self._run_adb(ip, f"shell screencap -p {remote_path}")
        result = self._run_adb(ip, f"pull {remote_path} {save_path}")
        return {"success": result["success"], "action": "screenshot", "path": save_path}

    def get_running_apps(self, ip: str) -> List[str]:
        """Get list of running apps."""
        result = self._run_adb(ip, "shell ps -A")
        if result["success"]:
            apps = []
            for line in result["stdout"].splitlines()[1:]:
                parts = line.split()
                if len(parts) > 8:
                    apps.append(parts[-1])
            return list(set(apps))
        return []

    def send_notification(self, ip: str, title: str, message: str) -> Dict[str, Any]:
        """Send a notification to the phone via ADB."""
        # Use broadcast to send a notification
        cmd = f"shell am broadcast -a android.intent.action.SEND -e title '{title}' -e message '{message}'"
        result = self._run_adb(ip, cmd)
        return {"success": result["success"], "action": "notification", "title": title}

    def get_wifi_info(self, ip: str) -> Dict[str, Any]:
        """Get WiFi connection info."""
        result = self._run_adb(ip, "shell dumpsys wifi")
        if result["success"]:
            info = {}
            for line in result["stdout"].splitlines():
                if "mWifiInfo" in line or "SSID:" in line:
                    ssid_match = re.search(r'SSID:\s*"?([^",]+)"?', line)
                    if ssid_match:
                        info["ssid"] = ssid_match.group(1)
                    rssi_match = re.search(r'RSSI:\s*(-?\d+)', line)
                    if rssi_match:
                        info["rssi"] = int(rssi_match.group(1))
                    speed_match = re.search(r'Link speed:\s*(\d+)', line)
                    if speed_match:
                        info["link_speed"] = int(speed_match.group(1))
            return info
        return {}

    def get_location(self, ip: str) -> Dict[str, Any]:
        """Get last known location (if location services enabled)."""
        result = self._run_adb(ip, "shell dumpsys location")
        if result["success"]:
            info = {}
            lat_match = re.search(r'lat[itude]*[=:]\s*(-?\d+\.?\d*)', result["stdout"], re.IGNORECASE)
            lon_match = re.search(r'lon[gitude]*[=:]\s*(-?\d+\.?\d*)', result["stdout"], re.IGNORECASE)
            if lat_match:
                info["latitude"] = float(lat_match.group(1))
            if lon_match:
                info["longitude"] = float(lon_match.group(1))
            return info
        return {}

    def discover_phones(self) -> List[Dict[str, Any]]:
        """Discover phones on the local network via ARP."""
        discovered = []
        try:
            import subprocess
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=15)

            phone_keywords = ["samsung", "galaxy", "note20", "s24", "pixel", "oneplus",
                             "android", "gargi", "suprotim"]
            for line in result.stdout.splitlines():
                line_lower = line.lower()
                for keyword in phone_keywords:
                    if keyword in line_lower:
                        match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                        mac_match = re.search(r'at\s+([0-9a-fA-F:]+)', line)
                        if match:
                            ip = match.group(1)
                            hostname = line.split("(")[0].strip() if "(" in line else ""
                            # Determine manufacturer from hostname
                            manufacturer = "Samsung" if "samsung" in hostname.lower() or "gargi" in hostname.lower() or "note20" in hostname.lower() or "s24" in hostname.lower() else "Unknown"
                            model = ""
                            if "note20" in hostname.lower():
                                model = "Galaxy Note20"
                            elif "s24 ultra" in hostname.lower():
                                model = "Galaxy S24 Ultra"
                            elif "s24" in hostname.lower():
                                model = "Galaxy S24"

                            discovered.append({
                                "ip": ip,
                                "name": hostname,
                                "manufacturer": manufacturer,
                                "model": model,
                                "device_type": "PHONE",
                                "protocol": "adb",
                            })
                        break
        except Exception:
            pass

        return discovered

    def get_all_phones(self) -> List[Dict[str, Any]]:
        """Get status of all registered phones."""
        phones = []
        with self._lock:
            for ip, phone in self._phones.items():
                try:
                    self.get_device_info(ip)
                except Exception:
                    pass
                phones.append(phone.to_dict())
        return phones


# ── Global singleton ───────────────────────────────────────

_phone: Optional[PhoneClient] = None
_phone_lock = threading.Lock()


def get_phone_client() -> PhoneClient:
    """Get or create the global PhoneClient instance."""
    global _phone
    with _phone_lock:
        if _phone is None:
            _phone = PhoneClient()
        return _phone
