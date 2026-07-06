#!/usr/bin/env python3
"""
Alexa WiFi Controller for JARVIS
Discovers and controls Amazon Echo devices on the local network.
Uses UPnP/SSDP discovery + local HTTP API control.
"""
import subprocess
import json
import socket
import time
import re
import os
import http.client
import ssl
import urllib.parse
from typing import Dict, List, Optional, Any

class AlexaController:
    """Control Amazon Echo devices on local WiFi network."""

    def __init__(self):
        self.devices = {}
        self._discovered = False

    def discover_devices(self) -> List[Dict]:
        """Discover Echo devices via UPnP/SSDP and network scan."""
        devices = []

        # Method 1: UPnP/SSDP multicast discovery
        try:
            ssdp_devices = self._ssdp_discover()
            devices.extend(ssdp_devices)
        except Exception:
            pass

        # Method 2: Network scan for Amazon devices
        try:
            amazon_devices = self._scan_amazon_devices()
            for d in amazon_devices:
                if not any(existing.get("ip") == d.get("ip") for existing in devices):
                    devices.append(d)
        except Exception:
            pass

        # Method 3: ARP table scan
        try:
            arp_devices = self._arp_scan_amazon()
            for d in arp_devices:
                if not any(existing.get("ip") == d.get("ip") for existing in devices):
                    devices.append(d)
        except Exception:
            pass

        self.devices = {d["ip"]: d for d in devices}
        self._discovered = True
        return devices

    def _ssdp_discover(self) -> List[Dict]:
        """Discover devices via UPnP SSDP multicast."""
        devices = []
        SSDP_ADDR = "239.255.255.250"
        SSDP_PORT = 1900
        SSDP_MX = 3
        SSDP_ST = "urn:schemas-upnp-org:device:Basic:1"

        msg = (
            f"M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
            f"MAN: \"ssdp:discover\"\r\n"
            f"MX: {SSDP_MX}\r\n"
            f"ST: {SSDP_ST}\r\n"
            f"\r\n"
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        sock.settimeout(4)

        try:
            sock.sendto(msg.encode(), (SSDP_ADDR, SSDP_PORT))
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode("utf-8", errors="ignore")
                    if "amazon" in response.lower() or "echo" in response.lower() or "alexa" in response.lower():
                        ip = addr[0]
                        name = self._extract_device_name(response)
                        devices.append({
                            "ip": ip,
                            "name": name or f"Echo ({ip})",
                            "type": "ALEXA",
                            "protocol": "upnp",
                            "model": self._extract_model(response),
                        })
                except socket.timeout:
                    break
        finally:
            sock.close()

        return devices

    def _scan_amazon_devices(self) -> List[Dict]:
        """Scan local network for Amazon devices by MAC OUI."""
        devices = []
        try:
            # Get local IP to determine subnet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            subnet = ".".join(local_ip.split(".")[:3])
            # Amazon MAC OUI prefixes
            amazon_ouis = ["f0:27:2d", "f0:f0:a4", "44:35:83", "ac:63:be", "84:d6:db",
                          "fc:65:de", "a0:02:dc", "3c:aa:8f", "74:c2:46", "e8:48:b8",
                          "0c:47:3d", "88:71:b1", "d8:72:5a", "e4:7a:2c", "fc:15:b4"]

            # ARP scan
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split("\n"):
                for oui in amazon_ouis:
                    if oui.lower() in line.lower():
                        ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                        if ip_match:
                            ip = ip_match.group(1)
                            devices.append({
                                "ip": ip,
                                "name": f"Echo ({ip})",
                                "type": "ALEXA",
                                "protocol": "arp",
                                "mac": line.split()[3] if len(line.split()) > 3 else "",
                            })
                        break
        except Exception:
            pass
        return devices

    def _arp_scan_amazon(self) -> List[Dict]:
        """Parse ARP table for Amazon devices."""
        devices = []
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split("\n"):
                if any(c in line.lower() for c in ["amazon", "echo", "alexa"]):
                    ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                    if ip_match:
                        devices.append({
                            "ip": ip_match.group(1),
                            "name": f"Echo ({ip_match.group(1)})",
                            "type": "ALEXA",
                            "protocol": "arp",
                        })
        except Exception:
            pass
        return devices

    def _extract_device_name(self, ssdp_response: str) -> str:
        """Extract device name from SSDP response."""
        for line in ssdp_response.split("\r\n"):
            if "server:" in line.lower():
                return line.split(":", 1)[1].strip()
            if "friendlyname" in line.lower():
                return line.split(":", 1)[1].strip()
        return ""

    def _extract_model(self, ssdp_response: str) -> str:
        """Extract device model from SSDP response."""
        for line in ssdp_response.split("\r\n"):
            if "modelname" in line.lower():
                return line.split(":", 1)[1].strip()
            if "model" in line.lower():
                return line.split(":", 1)[1].strip()
        return "Echo"

    def control_device(self, ip: str, command: str, **kwargs) -> Dict[str, Any]:
        """Send a command to an Echo device."""
        command = command.lower().strip()

        # Volume control
        if command.startswith("volume"):
            return self._set_volume(ip, kwargs.get("level", 50))

        # Playback control
        if command in ("play", "pause", "stop", "next", "previous", "prev"):
            return self._playback_control(ip, command)

        # TTS (text to speak)
        if command in ("speak", "say", "tts", "announce"):
            return self._tts(ip, kwargs.get("text", ""))

        # Routine trigger
        if command == "routine":
            return self._trigger_routine(ip, kwargs.get("name", ""))

        # Do Not Disturb
        if command in ("dnd on", "dnd off", "do not disturb on", "do not disturb off"):
            state = "on" if "on" in command else "off"
            return self._set_dnd(ip, state)

        # Timer
        if command == "timer":
            return self._set_timer(ip, kwargs.get("duration", "5 minutes"), kwargs.get("label", ""))

        # Reminder
        if command == "reminder":
            return self._set_reminder(ip, kwargs.get("time", ""), kwargs.get("text", ""))

        # Smart home control (through Alexa)
        if command in ("turn on", "turn off", "toggle"):
            return self._smart_home_control(ip, kwargs.get("device_name", ""), command)

        return {"success": False, "error": f"Unknown command: {command}"}

    def _set_volume(self, ip: str, level: int) -> Dict:
        """Set Echo volume (0-100)."""
        level = max(0, min(100, level))
        # Map 0-100 to Alexa's internal scale (0-40 typically)
        alexa_level = int(level * 40 / 100)
        result = self._send_api_command(ip, f"volume/{alexa_level}")
        return {"success": result is not None, "action": "volume", "level": level, "ip": ip}

    def _playback_control(self, ip: str, command: str) -> Dict:
        """Control playback (play/pause/stop/next/prev)."""
        cmd_map = {
            "play": "play",
            "pause": "pause",
            "stop": "pause",
            "next": "next",
            "previous": "previous",
            "prev": "previous",
        }
        alexa_cmd = cmd_map.get(command, command)
        result = self._send_api_command(ip, f"player/{alexa_cmd}")
        return {"success": result is not None, "action": command, "ip": ip}

    def _tts(self, ip: str, text: str) -> Dict:
        """Make Echo speak text (TTS)."""
        if not text:
            return {"success": False, "error": "No text provided"}
        result = self._send_api_command(ip, f"speak/{urllib.parse.quote(text)}")
        return {"success": result is not None, "action": "speak", "text": text[:50], "ip": ip}

    def _trigger_routine(self, ip: str, routine_name: str) -> Dict:
        """Trigger an Alexa routine by name."""
        result = self._send_api_command(ip, f"routine/{urllib.parse.quote(routine_name)}")
        return {"success": result is not None, "action": "routine", "name": routine_name, "ip": ip}

    def _set_dnd(self, ip: str, state: str) -> Dict:
        """Set Do Not Disturb on/off."""
        result = self._send_api_command(ip, f"dnd/{state}")
        return {"success": result is not None, "action": "dnd", "state": state, "ip": ip}

    def _set_timer(self, ip: str, duration: str, label: str) -> Dict:
        """Set a timer on Echo."""
        result = self._send_api_command(ip, f"timer/{urllib.parse.quote(duration)}/{urllib.parse.quote(label)}")
        return {"success": result is not None, "action": "timer", "duration": duration, "ip": ip}

    def _set_reminder(self, ip: str, reminder_time: str, text: str) -> Dict:
        """Set a reminder on Echo."""
        result = self._send_api_command(ip, f"reminder/{urllib.parse.quote(reminder_time)}/{urllib.parse.quote(text)}")
        return {"success": result is not None, "action": "reminder", "ip": ip}

    def _smart_home_control(self, ip: str, device_name: str, action: str) -> Dict:
        """Control smart home devices through Alexa."""
        result = self._send_api_command(ip, f"smarthome/{action}/{urllib.parse.quote(device_name)}")
        return {"success": result is not None, "action": action, "device": device_name, "ip": ip}

    def _send_api_command(self, ip: str, command: str) -> Optional[str]:
        """Send HTTP command to Echo device's local API."""
        # Echo devices expose a local API on port 443 (HTTPS)
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            conn = http.client.HTTPSConnection(ip, 443, timeout=5, context=context)
            # Try the local control API endpoints
            endpoints = [
                f"/api/{command}",
                f"/{command}",
                f"/v2/{command}",
            ]

            for endpoint in endpoints:
                try:
                    conn.request("GET", endpoint)
                    response = conn.getresponse()
                    if response.status in (200, 201, 202):
                        return response.read().decode()
                except Exception:
                    continue

            # Try POST with JSON body
            for endpoint in endpoints:
                try:
                    body = json.dumps({"command": command})
                    conn.request("POST", endpoint, body=body, headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    if response.status in (200, 201, 202):
                        return response.read().decode()
                except Exception:
                    continue

            conn.close()
        except Exception:
            pass

        # Fallback: use curl
        try:
            result = subprocess.run(
                ["curl", "-s", "-k", "-m", "5",
                 f"https://{ip}/api/{command}",
                 "-H", "Content-Type: application/json"],
                capture_output=True, text=True, timeout=8
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            pass

        return None

    def get_all_devices(self) -> List[Dict]:
        """Get all discovered Alexa devices."""
        if not self._discovered:
            self.discover_devices()
        return list(self.devices.values())

    def get_device_status(self, ip: str) -> Dict:
        """Get status of an Alexa device."""
        result = self._send_api_command(ip, "status")
        if result:
            try:
                return json.loads(result)
            except:
                return {"status": "online", "raw": result}
        return {"status": "unknown", "ip": ip}


# ── Singleton ────────────────────────────────────────────────────────
_alexa = None

def get_alexa_controller():
    global _alexa
    if _alexa is None:
        _alexa = AlexaController()
    return _alexa


# ── CLI Interface ────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    controller = get_alexa_controller()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  alexa_controller.py discover          - Find Echo devices")
        print("  alexa_controller.py control <ip> <cmd> - Control a device")
        print("  alexa_controller.py speak <ip> <text>  - Make Echo speak")
        print("  alexa_controller.py volume <ip> <0-100> - Set volume")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "discover":
        devices = controller.discover_devices()
        print(json.dumps(devices, indent=2))

    elif cmd == "control" and len(sys.argv) >= 4:
        ip = sys.argv[2]
        action = sys.argv[3]
        text = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
        result = controller.control_device(ip, action, text=text)
        print(json.dumps(result, indent=2))

    elif cmd == "speak" and len(sys.argv) >= 4:
        ip = sys.argv[2]
        text = " ".join(sys.argv[3:])
        result = controller.control_device(ip, "speak", text=text)
        print(json.dumps(result, indent=2))

    elif cmd == "volume" and len(sys.argv) >= 4:
        ip = sys.argv[2]
        level = int(sys.argv[3])
        result = controller.control_device(ip, "volume", level=level)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
