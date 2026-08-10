"""
JARVIS Network Controller — Universal phone/device control via router.
Works with Home Assistant, TP-Link, ASUS, Netgear, and generic UPnP routers.

Usage:
  from phone_controller import PhoneController
  pc = PhoneController(router_type="homeassistant", ...)
  pc.pause("iPhone")           # Block internet for a device
  pc.resume("iPhone")          # Restore internet
  pc.kick("iPhone")            # Force disconnect
  pc.block("iPhone")           # Permanent block
  pc.scan()                    # List all devices on network
  pc.get_device_info("iPhone") # Get device details
"""
import os
import re
import json
import time
import logging
import subprocess
import hashlib
from typing import Optional
from pathlib import Path

logger = logging.getLogger("phone_ctrl")

try:
    import requests
except ImportError:
    requests = None

CONFIG_DIR = Path(os.environ.get("JARVIS_CONFIG_DIR",
                   Path(__file__).parent / "data" / "phone_controller"))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# ── Router Base Classes ──

class RouterBase:
    """Base class for router integrations."""

    def __init__(self, host: str, username: str = "admin", password: str = ""):
        self.host = host
        self.username = username
        self.password = password
        self._authenticated = False
        self._session = None

    def connect(self) -> bool:
        raise NotImplementedError

    def get_connected_devices(self) -> list[dict]:
        """Return list of connected devices. Each dict has: name, ip, mac, type."""
        raise NotImplementedError

    def pause_device(self, mac: str) -> bool:
        """Temporarily block device internet access."""
        raise NotImplementedError

    def resume_device(self, mac: str) -> bool:
        """Restore device internet access."""
        raise NotImplementedError

    def block_device(self, mac: str) -> bool:
        """Permanently block device."""
        raise NotImplementedError

    def unblock_device(self, mac: str) -> bool:
        """Remove permanent block."""
        raise NotImplementedError

    def kick_device(self, mac: str) -> bool:
        """Force disconnect device (deauth)."""
        raise NotImplementedError

    def throttle_device(self, mac: str, up_kbps: int = 100, down_kbps: int = 100) -> bool:
        """Limit device bandwidth."""
        raise NotImplementedError

    def get_bandwidth_usage(self, mac: str) -> dict:
        """Get device bandwidth usage."""
        raise NotImplementedError


# ── Home Assistant Integration ──

class HomeAssistantRouter(RouterBase):
    """
    Control devices via Home Assistant REST API.
    Works with any router that has HA integration (TP-Link, ASUS, etc.)
    """

    def __init__(self, host: str, token: str, port: int = 8123):
        super().__init__(host, password=token)
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def connect(self) -> bool:
        """Test connection to Home Assistant."""
        if not requests:
            logger.error("pip install requests")
            return False
        try:
            r = requests.get(f"{self.base_url}/api/", headers=self.headers, timeout=5)
            self._authenticated = r.status_code == 200
            if self._authenticated:
                logger.info("Connected to Home Assistant")
            return self._authenticated
        except Exception as e:
            logger.error(f"HA connection failed: {e}")
            return False

    def _call_service(self, domain: str, service: str, entity_id: str, data: dict = None) -> bool:
        """Call a Home Assistant service."""
        url = f"{self.base_url}/api/services/{domain}/{service}"
        payload = {"entity_id": entity_id}
        if data:
            payload.update(data)
        try:
            r = requests.post(url, headers=self.headers, json=payload, timeout=10)
            return r.status_code in (200, 201)
        except Exception as e:
            logger.error(f"HA service call failed: {e}")
            return False

    def get_connected_devices(self) -> list[dict]:
        """Get all devices from HA."""
        try:
            r = requests.get(f"{self.base_url}/api/states", headers=self.headers, timeout=10)
            states = r.json()
            devices = []
            for state in states:
                eid = state.get("entity_id", "")
                # Look for device tracker, sensor, or switch entities
                if any(x in eid for x in ["device_tracker.", "sensor.", "switch."]):
                    attrs = state.get("attributes", {})
                    if "mac" in attrs or "ip" in attrs or "host_name" in attrs:
                        devices.append({
                            "name": attrs.get("host_name", attrs.get("friendly_name", eid)),
                            "ip": attrs.get("ip", attrs.get("ip_address", "")),
                            "mac": attrs.get("mac", attrs.get("mac_address", "")),
                            "entity_id": eid,
                            "type": "phone" if "phone" in str(attrs).lower() else "device",
                            "state": state.get("state", "unknown"),
                            "is_home": attrs.get("is_home", state.get("state") == "home"),
                        })
            return devices
        except Exception as e:
            logger.error(f"Get devices failed: {e}")
            return []

    def _find_switch_entity(self, mac: str) -> Optional[str]:
        """Find the switch entity for a device MAC."""
        devices = self.get_connected_devices()
        for d in devices:
            if d.get("mac", "").upper() == mac.upper():
                eid = d.get("entity_id", "")
                # Convert device_tracker to switch
                if eid.startswith("device_tracker."):
                    return eid.replace("device_tracker.", "switch.router_") + "_internet"
                if eid.startswith("switch."):
                    return eid
        return None

    def pause_device(self, mac: str) -> bool:
        entity = self._find_switch_entity(mac)
        if entity:
            return self._call_service("switch", "turn_off", entity)
        logger.warning(f"No switch entity found for MAC {mac}")
        return False

    def resume_device(self, mac: str) -> bool:
        entity = self._find_switch_entity(mac)
        if entity:
            return self._call_service("switch", "turn_on", entity)
        return False

    def block_device(self, mac: str) -> bool:
        return self.pause_device(mac)

    def unblock_device(self, mac: str) -> bool:
        return self.resume_device(mac)

    def kick_device(self, mac: str) -> bool:
        """Kick device via HA (if router supports it)."""
        devices = self.get_connected_devices()
        for d in devices:
            if d.get("mac", "").upper() == mac.upper():
                eid = d.get("entity_id", "")
                return self._call_service("device_tracker", "disconnect", eid)
        return False

    def throttle_device(self, mac: str, up_kbps: int = 100, down_kbps: int = 100) -> bool:
        """Throttle via HA (requires router support)."""
        entity = self._find_switch_entity(mac)
        if entity:
            return self._call_service("switch", "turn_on", entity,
                                      {"bandwidth_up": up_kbps, "bandwidth_down": down_kbps})
        return False

    def get_bandwidth_usage(self, mac: str) -> dict:
        try:
            r = requests.get(f"{self.base_url}/api/states", headers=self.headers, timeout=10)
            for state in r.json():
                attrs = state.get("attributes", {})
                if attrs.get("mac", "").upper() == mac.upper():
                    return {
                        "rx_bytes": attrs.get("rx_bytes", 0),
                        "tx_bytes": attrs.get("tx_bytes", 0),
                        "rx_speed": attrs.get("rx_speed", 0),
                        "tx_speed": attrs.get("tx_speed", 0),
                    }
        except Exception:
            pass
        return {}


# ── TP-Link Router ──

class TPLinkRouter(RouterBase):
    """
    TP-Link Archer router integration via web scraping.
    Works with most TP-Link home routers.
    """

    def __init__(self, host: str = "192.168.0.1", username: str = "admin", password: str = "admin"):
        super().__init__(host, username, password)
        self.base_url = f"http://{host}"

    def connect(self) -> bool:
        if not requests:
            return False
        try:
            self._session = requests.Session()
            # TP-Link login
            r = self._session.post(f"{self.base_url}/", data={
                "username": self.username,
                "password": self.password,
            }, timeout=10)
            self._authenticated = "success" in r.text.lower() or r.status_code == 200
            return self._authenticated
        except Exception as e:
            logger.error(f"TP-Link connection failed: {e}")
            return False

    def get_connected_devices(self) -> list[dict]:
        if not self._authenticated:
            self.connect()
        try:
            # TP-Link client list API
            r = self._session.get(f"{self.base_url}/cgi?8", timeout=10)
            devices = []
            # Parse TP-Link response
            lines = r.text.split("\n")
            for i, line in enumerate(lines):
                if "hostName" in line:
                    name = line.split("=")[-1].strip('" ')
                    ip = lines[i+1].split("=")[-1].strip('" ') if i+1 < len(lines) else ""
                    mac = lines[i+2].split("=")[-1].strip('" ') if i+2 < len(lines) else ""
                    devices.append({"name": name, "ip": ip, "mac": mac, "type": "device"})
            return devices
        except Exception as e:
            logger.error(f"TP-Link device list failed: {e}")
            return []

    def pause_device(self, mac: str) -> bool:
        """Block device via TP-Link parental controls."""
        if not self._authenticated:
            self.connect()
        try:
            # Block via TP-Link access control
            r = self._session.post(f"{self.base_url}/cgi?8", data={
                "operation": "add",
                "mac": mac,
                "type": "block",
            }, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"TP-Link block failed: {e}")
            return False

    def resume_device(self, mac: str) -> bool:
        if not self._authenticated:
            self.connect()
        try:
            r = self._session.post(f"{self.base_url}/cgi?8", data={
                "operation": "delete",
                "mac": mac,
            }, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"TP-Link unblock failed: {e}")
            return False

    def kick_device(self, mac: str) -> bool:
        return self.pause_device(mac)


# ── ASUS Router ──

class ASUSRouter(RouterBase):
    """
    ASUS router integration via ASUSWRT API.
    Works with RT-AC68U, RT-AX88U, GT-AX11000, etc.
    """

    def __init__(self, host: str = "192.168.1.1", username: str = "admin", password: str = "admin"):
        super().__init__(host, username, password)
        self.base_url = f"http://{host}"

    def connect(self) -> bool:
        if not requests:
            return False
        try:
            self._session = requests.Session()
            # ASUS login
            r = self._session.post(f"{self.base_url}/login.cgi", data={
                "login_authorization": self._encode_auth(),
            }, timeout=10)
            if "sid" in r.text:
                self._sid = r.text.split("sid=")[1].split('"')[0]
                self._authenticated = True
                return True
            return False
        except Exception as e:
            logger.error(f"ASUS connection failed: {e}")
            return False

    def _encode_auth(self) -> str:
        import base64
        cred = f"{self.username}:{self.password}"
        return base64.b64encode(cred.encode()).decode()

    def get_connected_devices(self) -> list[dict]:
        if not self._authenticated:
            self.connect()
        try:
            r = self._session.get(
                f"{self.base_url}/appGet.cgi?hook=devicelist",
                params={"sid": self._sid},
                timeout=10
            )
            data = r.json()
            devices = []
            for client in data.get("devicelist", {}).get("client_list", []):
                devices.append({
                    "name": client.get("name", "Unknown"),
                    "ip": client.get("ip", ""),
                    "mac": client.get("mac", ""),
                    "type": "phone" if client.get("vendor", "").lower() in ["apple", "samsung", "google", "oneplus", "xiaomi"] else "device",
                    "is_wired": client.get("is_wired", False),
                })
            return devices
        except Exception as e:
            logger.error(f"ASUS device list failed: {e}")
            return []

    def pause_device(self, mac: str) -> bool:
        if not self._authenticated:
            self.connect()
        try:
            # ASUS access restriction
            r = self._session.post(f"{self.base_url}/applydb.cgi",
                params={"sid": self._sid, "action_mode": "apply"},
                data={"wl_macaddr_x": mac, "macleard": "1"},
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"ASUS block failed: {e}")
            return False

    def resume_device(self, mac: str) -> bool:
        return self.pause_device(mac)

    def kick_device(self, mac: str) -> bool:
        return self.pause_device(mac)


# ── Netgear Router ──

class NetgearRouter(RouterBase):
    """
    Netgear router integration.
    Works with Nighthawk, Orbi, etc.
    """

    def __init__(self, host: str = "192.168.1.1", username: str = "admin", password: str = "password"):
        super().__init__(host, username, password)

    def connect(self) -> bool:
        if not requests:
            return False
        try:
            self._session = requests.Session()
            r = self._session.post(f"http://{self.host}/login.cgi", data={
                "username": self.username,
                "password": self.password,
            }, timeout=10)
            self._authenticated = r.status_code == 200
            return self._authenticated
        except Exception as e:
            logger.error(f"Netgear connection failed: {e}")
            return False

    def get_connected_devices(self) -> list[dict]:
        if not self._authenticated:
            self.connect()
        try:
            r = self._session.get(f"http://{self.host}/DEV_device_to_macBinding.htm", timeout=10)
            devices = []
            for match in re.finditer(r'"([^"]+)".*?"([0-9A-Fa-f:]+)"', r.text):
                devices.append({"name": match.group(1), "mac": match.group(2), "type": "device"})
            return devices
        except Exception:
            return []

    def pause_device(self, mac: str) -> bool:
        if not self._authenticated:
            self.connect()
        try:
            r = self._session.post(f"http://{self.host}/accessControl.htm", data={
                "action": "block",
                "mac": mac,
            }, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def resume_device(self, mac: str) -> bool:
        if not self._authenticated:
            self.connect()
        try:
            r = self._session.post(f"http://{self.host}/accessControl.htm", data={
                "action": "unblock",
                "mac": mac,
            }, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def kick_device(self, mac: str) -> bool:
        return self.pause_device(mac)


# ── Generic UPnP/SNMP Router ──

class GenericRouter(RouterBase):
    """
    Generic router using UPnP/SNMP for basic control.
    Works with most routers but with limited features.
    """

    def __init__(self, host: str, username: str = "admin", password: str = ""):
        super().__init__(host, username, password)

    def connect(self) -> bool:
        try:
            # Try UPnP discovery
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect((self.host, 80))
            s.close()
            self._authenticated = True
            return True
        except Exception:
            return False

    def get_connected_devices(self) -> list[dict]:
        """Get devices via ARP table."""
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
            devices = []
            for line in result.stdout.splitlines():
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})", line)
                if match:
                    devices.append({
                        "ip": match.group(1),
                        "mac": match.group(2),
                        "type": "device",
                        "name": "Unknown",
                    })
            return devices
        except Exception:
            return []

    def pause_device(self, mac: str) -> bool:
        """Pause via ARP spoofing (requires admin/root)."""
        logger.warning("Generic router: pause requires manual router admin")
        return False

    def resume_device(self, mac: str) -> bool:
        return True

    def kick_device(self, mac: str) -> bool:
        return self.pause_device(mac)


# ── ADB (Android Debug Bridge) Controller ──────────────────────────────

class ADBController:
    """
    Direct Android device control via ADB over WiFi.
    Requires: Wireless Debugging enabled on the Android device.
    
    Usage:
        adb = ADBController("192.168.8.186")
        adb.connect()
        adb.power_off()
        adb.lock_screen()
        adb.reboot()
    """

    ADB_PATHS = [
        "adb",
        r"C:\platform-tools\adb.exe",
        "/usr/bin/adb",
        "/usr/local/bin/adb",
    ]

    def __init__(self, phone_ip: str, port: int = 5555):
        self.phone_ip = phone_ip
        self.port = port
        self.device_address = f"{phone_ip}:{port}"
        self._connected = False
        self._adb_path = self._find_adb()

    def _find_adb(self) -> str:
        """Find ADB executable."""
        import shutil
        for path in self.ADB_PATHS:
            if os.path.exists(path):
                return path
            if shutil.which(path):
                return path
        return "adb"  # Fallback, will fail with clear error

    def _run_adb(self, *args) -> subprocess.CompletedProcess:
        """Run an ADB command."""
        cmd = [self._adb_path] + list(args)
        logger.info(f"ADB: {' '.join(cmd[:6])}...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 and result.stderr:
                logger.warning(f"ADB stderr: {result.stderr[:200]}")
            return result
        except FileNotFoundError:
            logger.error(f"ADB not found at {self._adb_path}. Install Android SDK Platform Tools.")
            return subprocess.CompletedProcess(cmd, 1, "", "adb not found")
        except subprocess.TimeoutExpired:
            logger.error("ADB command timed out")
            return subprocess.CompletedProcess(cmd, 1, "", "timeout")

    def connect(self) -> bool:
        """Connect to Android device via WiFi ADB."""
        result = self._run_adb("connect", self.device_address)
        output = result.stdout.lower()
        if "connected" in output:
            self._connected = True
            logger.info(f"Connected to {self.device_address}")
            return True
        logger.error(f"Failed to connect: {result.stdout}")
        return False

    def disconnect(self) -> bool:
        """Disconnect from the device."""
        result = self._run_adb("disconnect", self.device_address)
        self._connected = False
        return result.returncode == 0

    def is_connected(self) -> bool:
        """Check if device is connected."""
        result = self._run_adb("devices")
        return self.device_address in result.stdout

    def shell(self, command: str) -> str:
        """Execute a shell command on the device."""
        result = self._run_adb("-s", self.device_address, "shell", command)
        return result.stdout.strip()

    # ── Power Control ──

    def power_off(self) -> bool:
        """Power off the Android device."""
        self.shell("reboot -p")
        logger.info(f"Power off sent to {self.device_address}")
        return True

    def reboot(self) -> bool:
        """Reboot the device."""
        self.shell("reboot")
        logger.info(f"Reboot sent to {self.device_address}")
        return True

    def reboot_recovery(self) -> bool:
        """Reboot into recovery mode."""
        self.shell("reboot recovery")
        return True

    def reboot_bootloader(self) -> bool:
        """Reboot into bootloader/fastboot."""
        self.shell("reboot bootloader")
        return True

    # ── Screen Control ──

    def lock_screen(self) -> bool:
        """Lock the screen (simulates power button press)."""
        self.shell("input keyevent 26")
        logger.info(f"Screen locked on {self.device_address}")
        return True

    def unlock_screen(self) -> bool:
        """Wake up and swipe to unlock."""
        # Wake up
        self.shell("input keyevent 26")
        time.sleep(0.5)
        # Swipe up to unlock
        self.shell("input swipe 500 1500 500 500 300")
        return True

    def screen_on(self) -> bool:
        """Turn screen on without unlocking."""
        self.shell("input keyevent 224")  # KEYCODE_WAKEUP
        return True

    def screen_off(self) -> bool:
        """Turn screen off."""
        self.shell("input keyevent 223")  # KEYCODE_SLEEP
        return True

    # ── Input Control ──

    def tap(self, x: int, y: int) -> bool:
        """Tap at coordinates."""
        self.shell(f"input tap {x} {y}")
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        """Swipe from (x1,y1) to (x2,y2)."""
        self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        return True

    def type_text(self, text: str) -> bool:
        """Type text."""
        # Escape special characters
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("'", "\\'")
        self.shell(f"input text '{escaped}'")
        return True

    def press_key(self, keycode: str) -> bool:
        """Press a key by keycode name or number."""
        keymap = {
            "home": "3", "back": "4", "enter": "66", "delete": "67",
            "tab": "61", "space": "62", "menu": "82", "power": "26",
            "volume_up": "24", "volume_down": "25", "volume_mute": "164",
            "camera": "27", "play_pause": "85", "next": "87", "prev": "88",
            "search": "84", "settings": "176", "notification": "83",
        }
        code = keymap.get(keycode.lower(), keycode)
        self.shell(f"input keyevent {code}")
        return True

    # ── App Control ──

    def launch_app(self, package: str) -> bool:
        """Launch an app by package name."""
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
        return True

    def force_stop(self, package: str) -> bool:
        """Force stop an app."""
        self.shell(f"am force-stop {package}")
        return True

    def install_apk(self, apk_path: str) -> bool:
        """Install an APK file."""
        result = self._run_adb("-s", self.device_address, "install", "-r", apk_path)
        return "success" in result.stdout.lower()

    def uninstall_app(self, package: str) -> bool:
        """Uninstall an app."""
        result = self._run_adb("-s", self.device_address, "uninstall", package)
        return "success" in result.stdout.lower()

    # ── System Control ──

    def get_battery_level(self) -> int:
        """Get battery percentage."""
        output = self.shell("dumpsys battery | grep level")
        match = re.search(r"level:\s*(\d+)", output)
        return int(match.group(1)) if match else -1

    def get_wifi_info(self) -> dict:
        """Get WiFi connection info."""
        output = self.shell("dumpsys wifi | grep 'mWifiInfo'")
        return {"raw": output}

    def get_ip_address(self) -> str:
        """Get device IP address."""
        output = self.shell("ip route | grep 'src'")
        match = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", output)
        return match.group(1) if match else ""

    def get_ssid(self) -> str:
        """Get connected WiFi SSID."""
        output = self.shell("dumpsys wifi | grep 'SSID:'")
        match = re.search(r"SSID:\s*\"([^\"]+)\"", output)
        return match.group(1) if match else ""

    def airplane_mode_on(self) -> bool:
        """Enable airplane mode."""
        self.shell("settings put global airplane_mode_on 1")
        self.shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true")
        return True

    def airplane_mode_off(self) -> bool:
        """Disable airplane mode."""
        self.shell("settings put global airplane_mode_on 0")
        self.shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false")
        return True

    def disable_wifi(self) -> bool:
        """Turn off WiFi."""
        self.shell("svc wifi disable")
        return True

    def enable_wifi(self) -> bool:
        """Turn on WiFi."""
        self.shell("svc wifi enable")
        return True

    def disable_mobile_data(self) -> bool:
        """Turn off mobile data."""
        self.shell("svc data disable")
        return True

    def enable_mobile_data(self) -> bool:
        """Turn on mobile data."""
        self.shell("svc data enable")
        return True

    def set_brightness(self, level: int) -> bool:
        """Set screen brightness (0-255)."""
        self.shell(f"settings put system screen_brightness {max(0, min(255, level))}")
        return True

    def set_volume(self, stream: str, level: int) -> bool:
        """Set volume level (0-15)."""
        stream_map = {"ring": 2, "music": 3, "alarm": 4, "notification": 5}
        s = stream_map.get(stream.lower(), 3)
        self.shell(f"media volume --stream {s} --set {max(0, min(15, level))}")
        return True

    def vibrate(self, duration_ms: int = 500) -> bool:
        """Trigger vibration."""
        self.shell(f"input vibration {duration_ms}")
        return True

    def screenshot(self, local_path: str = "screenshot.png") -> bool:
        """Take a screenshot and save locally."""
        remote_path = "/sdcard/screenshot.png"
        self.shell(f"screencap -p {remote_path}")
        self._run_adb("-s", self.device_address, "pull", remote_path, local_path)
        self.shell(f"rm {remote_path}")
        return os.path.exists(local_path)

    def get_running_apps(self) -> list[str]:
        """Get list of running apps."""
        output = self.shell("ps -A | grep -v system")
        apps = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 9:
                apps.append(parts[-1])
        return apps

    def get_device_info(self) -> dict:
        """Get comprehensive device information."""
        return {
            "model": self.shell("getprop ro.product.model"),
            "brand": self.shell("getprop ro.product.brand"),
            "android_version": self.shell("getprop ro.build.version.release"),
            "ip": self.get_ip_address(),
            "ssid": self.get_ssid(),
            "battery": self.get_battery_level(),
            "connected": self.is_connected(),
        }


# ── Unified Controller ──

class PhoneController:
    """
    Unified phone/device controller.
    Auto-detects router or uses specified type.
    Supports: Home Assistant, TP-Link, ASUS, Netgear, Generic, ADB

    Usage:
        # Router control
        pc = PhoneController(router_type="homeassistant", host="192.168.1.100", token="...")
        pc.pause("iPhone")      # Block internet
        pc.resume("iPhone")     # Restore internet
        pc.kick("iPhone")       # Force disconnect

        # Direct ADB control
        pc = PhoneController(controller_type="adb", phone_ip="192.168.8.186")
        pc.adb.power_off()      # Turn off phone
        pc.adb.lock_screen()    # Lock screen
        pc.adb.reboot()         # Reboot device
    """

    ROUTER_TYPES = {
        "homeassistant": HomeAssistantRouter,
        "tplink": TPLinkRouter,
        "asus": ASUSRouter,
        "netgear": NetgearRouter,
        "generic": GenericRouter,
    }

    def __init__(self, router_type: str = "auto", controller_type: str = "router", **kwargs):
        self._config_file = CONFIG_DIR / "config.json"
        self._config = self._load_config()
        self.adb: Optional[ADBController] = None
        self.router = None

        # Override config with kwargs
        router_type = router_type or self._config.get("router_type", "generic")
        host = kwargs.get("host") or self._config.get("host", "192.168.1.1")
        username = kwargs.get("username") or self._config.get("username", "admin")
        password = kwargs.get("password") or self._config.get("password", "")
        token = kwargs.get("token") or self._config.get("token", "")
        phone_ip = kwargs.get("phone_ip") or self._config.get("phone_ip", "")
        adb_port = kwargs.get("adb_port") or self._config.get("adb_port", 5555)

        # Create ADB controller if specified
        if controller_type == "adb" or phone_ip:
            if phone_ip:
                self.adb = ADBController(phone_ip, adb_port)

        # Create router instance (if not ADB-only mode)
        if controller_type != "adb":
            router_cls = self.ROUTER_TYPES.get(router_type, GenericRouter)
            if router_type == "homeassistant":
                self.router = router_cls(host, token=token, port=kwargs.get("port", 8123))
            else:
                self.router = router_cls(host, username, password)

        self._device_cache: dict[str, dict] = {}
        self._device_names: dict[str, str] = {}  # MAC -> friendly name

    def _load_config(self) -> dict:
        if self._config_file.exists():
            with open(self._config_file) as f:
                return json.load(f)
        return {}

    def save_config(self, **kwargs):
        """Save router configuration."""
        self._config.update(kwargs)
        with open(self._config_file, "w") as f:
            json.dump(self._config, f, indent=2)

    def connect(self) -> bool:
        """Connect to router or ADB device."""
        if self.adb:
            return self.adb.connect()
        if self.router:
            return self.router.connect()
        return False

    def scan(self, force: bool = False) -> list[dict]:
        """Scan network for connected devices."""
        if not force and self._device_cache:
            return list(self._device_cache.values())

        devices = self.router.get_connected_devices()
        self._device_cache = {}
        for d in devices:
            mac = d.get("mac", "").upper()
            if mac:
                self._device_cache[mac] = d
        return devices

    def _find_device(self, identifier: str) -> Optional[dict]:
        """Find a device by name, IP, or MAC."""
        identifier_upper = identifier.upper()

        # Check cache first
        for mac, device in self._device_cache.items():
            if (identifier_upper in mac.upper() or
                identifier.lower() in device.get("name", "").lower() or
                identifier == device.get("ip", "")):
                return device

        # Scan if not found
        self.scan()
        for mac, device in self._device_cache.items():
            if (identifier_upper in mac.upper() or
                identifier.lower() in device.get("name", "").lower() or
                identifier == device.get("ip", "")):
                return device
        return None

    def _get_mac(self, identifier: str) -> Optional[str]:
        """Get MAC address from identifier."""
        device = self._find_device(identifier)
        if device:
            return device.get("mac", "")
        # If it looks like a MAC already
        if re.match(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", identifier):
            return identifier.upper()
        return None

    def pause(self, identifier: str) -> dict:
        """Pause device internet access."""
        mac = self._get_mac(identifier)
        if not mac:
            return {"success": False, "error": f"Device '{identifier}' not found"}
        success = self.router.pause_device(mac)
        return {
            "success": success,
            "action": "pause",
            "device": identifier,
            "mac": mac,
            "message": f"{'Paused' if success else 'Failed to pause'} {identifier}",
        }

    def resume(self, identifier: str) -> dict:
        """Resume device internet access."""
        mac = self._get_mac(identifier)
        if not mac:
            return {"success": False, "error": f"Device '{identifier}' not found"}
        success = self.router.resume_device(mac)
        return {
            "success": success,
            "action": "resume",
            "device": identifier,
            "mac": mac,
            "message": f"{'Resumed' if success else 'Failed to resume'} {identifier}",
        }

    def block(self, identifier: str) -> dict:
        """Permanently block device."""
        mac = self._get_mac(identifier)
        if not mac:
            return {"success": False, "error": f"Device '{identifier}' not found"}
        success = self.router.block_device(mac)
        # Save to blocked list
        if success:
            blocked = self._config.get("blocked_devices", [])
            if mac not in blocked:
                blocked.append(mac)
                self.save_config(blocked_devices=blocked)
        return {
            "success": success,
            "action": "block",
            "device": identifier,
            "mac": mac,
            "message": f"{'Blocked' if success else 'Failed to block'} {identifier}",
        }

    def unblock(self, identifier: str) -> dict:
        """Remove permanent block."""
        mac = self._get_mac(identifier)
        if not mac:
            return {"success": False, "error": f"Device '{identifier}' not found"}
        success = self.router.unblock_device(mac)
        # Remove from blocked list
        blocked = self._config.get("blocked_devices", [])
        if mac in blocked:
            blocked.remove(mac)
            self.save_config(blocked_devices=blocked)
        return {
            "success": success,
            "action": "unblock",
            "device": identifier,
            "mac": mac,
            "message": f"{'Unblocked' if success else 'Failed to unblock'} {identifier}",
        }

    def kick(self, identifier: str) -> dict:
        """Force disconnect device."""
        mac = self._get_mac(identifier)
        if not mac:
            return {"success": False, "error": f"Device '{identifier}' not found"}
        success = self.router.kick_device(mac)
        return {
            "success": success,
            "action": "kick",
            "device": identifier,
            "mac": mac,
            "message": f"{'Kicked' if success else 'Failed to kick'} {identifier}",
        }

    def throttle(self, identifier: str, up_kbps: int = 100, down_kbps: int = 100) -> dict:
        """Limit device bandwidth."""
        mac = self._get_mac(identifier)
        if not mac:
            return {"success": False, "error": f"Device '{identifier}' not found"}
        success = self.router.throttle_device(mac, up_kbps, down_kbps)
        return {
            "success": success,
            "action": "throttle",
            "device": identifier,
            "mac": mac,
            "up_kbps": up_kbps,
            "down_kbps": down_kbps,
            "message": f"{'Throttled' if success else 'Failed to throttle'} {identifier}",
        }

    def get_info(self, identifier: str) -> dict:
        """Get device information."""
        device = self._find_device(identifier)
        if not device:
            return {"error": f"Device '{identifier}' not found"}
        mac = device.get("mac", "")
        usage = self.router.get_bandwidth_usage(mac) if mac else {}
        return {
            "name": device.get("name", "Unknown"),
            "ip": device.get("ip", ""),
            "mac": mac,
            "type": device.get("type", "unknown"),
            "state": device.get("state", "unknown"),
            "is_home": device.get("is_home", None),
            "bandwidth": usage,
        }

    def get_status(self) -> dict:
        """Get controller status."""
        status = {
            "controller_type": "adb" if self.adb else "router",
            "devices_found": len(self._device_cache),
            "blocked": self._config.get("blocked_devices", []),
        }
        if self.adb:
            status["phone_ip"] = self.adb.phone_ip
            status["connected"] = self.adb.is_connected()
            status["device_info"] = self.adb.get_device_info()
        elif self.router:
            status["router_type"] = type(self.router).__name__
            status["connected"] = self.router._authenticated
        return status


# ── CLI ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Phone Controller")
    parser.add_argument("--type", default="generic",
                       choices=["homeassistant", "tplink", "asus", "netgear", "generic"],
                       help="Router type")
    parser.add_argument("--host", default="192.168.1.1", help="Router IP")
    parser.add_argument("--username", default="admin", help="Router username")
    parser.add_argument("--password", default="", help="Router password")
    parser.add_argument("--token", default="", help="Home Assistant token")
    parser.add_argument("--scan", action="store_true", help="Scan network")
    parser.add_argument("--pause", type=str, help="Pause device")
    parser.add_argument("--resume", type=str, help="Resume device")
    parser.add_argument("--block", type=str, help="Block device")
    parser.add_argument("--kick", type=str, help="Kick device")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[PHONE] %(message)s")

    pc = PhoneController(
        router_type=args.type,
        host=args.host,
        username=args.username,
        password=args.password,
        token=args.token,
    )

    if not pc.connect():
        print("Failed to connect to router")
        return

    if args.scan:
        devices = pc.scan()
        print(f"\nDevices on network ({len(devices)}):")
        for d in devices:
            print(f"  {d.get('name', 'Unknown'):20s} {d.get('ip', '?'):15s} {d.get('mac', '?'):17s}")

    if args.pause:
        result = pc.pause(args.pause)
        print(result["message"])

    if args.resume:
        result = pc.resume(args.resume)
        print(result["message"])

    if args.block:
        result = pc.block(args.block)
        print(result["message"])

    if args.kick:
        result = pc.kick(args.kick)
        print(result["message"])


if __name__ == "__main__":
    main()
