"""
JARVIS Device Bridge — Connects NL Parser → Smart Home Manager
==============================================================
Bridges parsed natural language commands to actual device control.
Supports MQTT, HTTP, and local protocol execution.
"""

import os
import json
import time
import socket
import struct
import threading
import traceback
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class DeviceCommand:
    device_id: str
    device_ip: str
    protocol: str
    command: Dict[str, Any]
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    latency_ms: int = 0


class DeviceBridge:
    """Bridges parsed commands to actual device control across protocols."""

    def __init__(self):
        self._command_log: List[DeviceCommand] = []
        self._mqtt_client = None
        self._http_pool = None
        self._lock = threading.Lock()

    def execute(
        self,
        device: Dict[str, Any],
        command: Dict[str, Any],
    ) -> DeviceCommand:
        """Execute a command on a device using the appropriate protocol."""
        proto = device.get("protocol", "http").lower()
        ip = device.get("ip", "")
        device_id = device.get("id", device.get("mac", ip))

        cmd = DeviceCommand(
            device_id=device_id,
            device_ip=ip,
            protocol=proto,
            command=command,
        )

        start = time.time()
        try:
            if proto in ("hue", "philips-hue"):
                result = self._execute_hue(device, command)
            elif proto in ("wled",):
                result = self._execute_wled(device, command)
            elif proto in ("shelly",):
                result = self._execute_shelly(device, command)
            elif proto in ("tasmota",):
                result = self._execute_tasmota(device, command)
            elif proto in ("esphome",):
                result = self._execute_esphome(device, command)
            elif proto in ("kasa", "tp-link"):
                result = self._execute_kasa(device, command)
            elif proto in ("mqtt",):
                result = self._execute_mqtt(device, command)
            elif proto in ("home-assistant", "ha"):
                result = self._execute_home_assistant(device, command)
            elif proto in ("upnp", "ssdp"):
                result = self._execute_upnp(device, command)
            elif proto in ("eufy",):
                result = self._execute_eufy(device, command)
            elif proto in ("tuya",):
                result = self._execute_tuya(device, command)
            elif proto in ("http", "rest", "api"):
                result = self._execute_http(device, command)
            else:
                result = {"status": "unsupported_protocol", "protocol": proto}

            cmd.status = "success"
            cmd.result = result
        except Exception as e:
            cmd.status = "failed"
            cmd.error = str(e)
            cmd.result = {"error": str(e)}

        cmd.latency_ms = int((time.time() - start) * 1000)

        with self._lock:
            self._command_log.append(cmd)
            if len(self._command_log) > 500:
                self._command_log = self._command_log[-500:]

        return cmd

    # ── Protocol Executors ──────────────────────────────────────

    def _execute_hue(self, device: Dict, command: Dict) -> Dict:
        """Philips Hue bridge control via REST API."""
        bridge_ip = device.get("bridge_ip", device.get("ip"))
        api_key = device.get("api_key", "newdeveloper")
        light_id = device.get("light_id", device.get("id", "1"))
        url = f"http://{bridge_ip}/api/{api_key}/lights/{light_id}/state"

        state = {}
        if "state" in command:
            state["on"] = command["state"] == "on"
        if "brightness" in command:
            state["bri"] = int(command["brightness"] * 254 / 100)
        if "color" in command:
            c = command["color"]
            if isinstance(c, list) and len(c) >= 3:
                state["rgb"] = c
        if "transition" in command:
            state["transitiontime"] = command["transition"]

        return self._http_put(url, state)

    def _execute_wled(self, device: Dict, command: Dict) -> Dict:
        """WLED LED controller control."""
        ip = device.get("ip")
        url = f"http://{ip}/json"

        state = {}
        if "state" in command:
            state["on"] = command["state"] == "on"
        if "brightness" in command:
            state["bri"] = int(command["brightness"] * 255 / 100)
        if "color" in command:
            c = command["color"]
            if isinstance(c, list) and len(c) >= 3:
                state["seg"] = [{"col": [[c[0], c[1], c[2]]]}]

        payload = {"state": state}
        return self._http_post(url, payload)

    def _execute_shelly(self, device: Dict, command: Dict) -> Dict:
        """Shelly relay control."""
        ip = device.get("ip")
        relay = device.get("relay_id", 0)
        state = command.get("state", "on")
        url = f"http://{ip}/relay/{relay}?turn={state}"
        return self._http_get(url)

    def _execute_tasmota(self, device: Dict, command: Dict) -> Dict:
        """Tasmota device control via MQTT/console."""
        ip = device.get("ip")
        state = command.get("state", "on")
        cmd = f"Power1 {state.upper()}"
        url = f"http://{ip}/cm?cmnd={cmd}"
        return self._http_get(url)

    def _execute_esphome(self, device: Dict, command: Dict) -> Dict:
        """ESPHome device control via HTTP API."""
        ip = device.get("ip")
        state = command.get("state", "on")

        if device.get("type") == "light":
            url = f"http://{ip}/switch/relay1/turn_{'on' if state == 'on' else 'off'}"
        else:
            url = f"http://{ip}/switch/relay1/turn_{'on' if state == 'on' else 'off'}"

        return self._http_get(url)

    def _execute_kasa(self, device: Dict, command: Dict) -> Dict:
        """TP-Link Kasa control (HTTP fallback for newer models)."""
        ip = device.get("ip")
        state = command.get("state", "on")

        try:
            import tplink_smartplug
            plug = tplink_smartplug.TPPlugSmartPlug(ip)
            if state == "on":
                plug.turn_on()
            elif state == "off":
                plug.turn_off()
            elif state == "toggle":
                plug.toggle()
            elif "brightness" in command:
                plug.set_brightness(int(command["brightness"] * 100 / 100))
            return {"status": "ok", "state": state}
        except ImportError:
            # Fallback to HTTP for newer Kasa devices
            url = f"http://{ip}/relay?state={'on' if state == 'on' else 'off'}"
            return self._http_get(url)

    def _execute_mqtt(self, device: Dict, command: Dict) -> Dict:
        """MQTT publish for IoT devices."""
        topic = device.get("topic", device.get("mqtt_topic", ""))
        if not topic:
            return {"error": "No MQTT topic configured"}

        try:
            import paho.mqtt.client as mqtt
            broker = device.get("mqtt_broker", "localhost")
            port = int(device.get("mqtt_port", 1883))

            client = mqtt.Client()
            client.connect(broker, port, 5)
            payload = json.dumps(command)
            client.publish(topic, payload)
            client.disconnect()
            return {"status": "published", "topic": topic, "payload": command}
        except ImportError:
            return {"error": "MQTT client not installed", "topic": topic, "payload": command}
        except Exception as e:
            return {"error": str(e), "topic": topic}

    def _execute_home_assistant(self, device: Dict, command: Dict) -> Dict:
        """Home Assistant REST API control."""
        ha_url = device.get("ha_url", os.getenv("HOME_ASSISTANT_URL", ""))
        ha_token = device.get("ha_token", os.getenv("HOME_ASSISTANT_TOKEN", ""))
        entity_id = device.get("entity_id", "")

        if not ha_url or not ha_token:
            return {"error": "Home Assistant not configured"}

        url = f"{ha_url}/api/services"
        headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }

        state = command.get("state", "on")
        if state in ("on", "off"):
            domain = entity_id.split(".")[0] if entity_id else "light"
            service = "turn_on" if state == "on" else "turn_off"
            payload = {"entity_id": entity_id}
            if "brightness" in command:
                payload["brightness"] = int(command["brightness"] * 255 / 100)
            if "color" in command:
                payload["rgb_color"] = command["color"]
            return self._http_post(url, payload, headers)

        return {"status": "no_action"}

    def _execute_upnp(self, device: Dict, command: Dict) -> Dict:
        """UPnP/AVTransport media control."""
        ip = device.get("ip")
        port = device.get("port", 1400)
        control_url = device.get("control_url", "/AVTransport/control")

        action_map = {
            "play": "Play",
            "pause": "Pause",
            "stop": "Stop",
            "next": "Next",
            "prev": "Previous",
        }
        action = action_map.get(command.get("state", "play"), "Play")

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:{action}>
  </s:Body>
</s:Envelope>"""

        return self._http_post(
            f"http://{ip}:{port}{control_url}",
            soap_body,
            headers={"Content-Type": 'text/xml; charset="utf-8"', "SOAPACTION": f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"'},
        )

    def _execute_eufy(self, device: Dict, command: Dict) -> Dict:
        """Eufy device control."""
        ip = device.get("ip")
        dev_type = device.get("type", "")

        if dev_type == "camera":
            if command.get("action") == "snapshot":
                return self._http_get(f"http://{ip}:5000/monitoring/snapshot")
            elif command.get("action") == "stream":
                rtsp_url = f"rtsp://{ip}:554/live0"
                return {"status": "stream_url", "url": rtsp_url}
        elif dev_type == "lock":
            state = command.get("state", "lock")
            return self._http_post(f"http://{ip}:80/api/lock", {"action": state})

        return {"status": "unsupported"}

    def _execute_tuya(self, device: Dict, command: Dict) -> Dict:
        """Tuya device control (local key based)."""
        ip = device.get("ip")
        local_key = device.get("local_key", "")
        dev_id = device.get("tuya_id", "")

        if not local_key:
            return {"error": "No Tuya local key configured"}

        try:
            import tinytuya
            d = tinytuya.OutletDevice(dev_id, ip, local_key)
            state = command.get("state", "on")
            if state in ("on", "off"):
                d.set_status(state == "on")
            elif "brightness" in command:
                d.set_brightness(int(command["brightness"]))
            return {"status": "ok"}
        except ImportError:
            return {"error": "tinytuya not installed"}
        except Exception as e:
            return {"error": str(e)}

    def _execute_http(self, device: Dict, command: Dict) -> Dict:
        """Generic HTTP/REST control."""
        ip = device.get("ip")
        port = device.get("port", 80)
        path = device.get("control_path", "/")
        method = device.get("control_method", "POST").upper()

        url = f"http://{ip}:{port}{path}"
        if method == "GET":
            return self._http_get(url)
        elif method == "POST":
            return self._http_post(url, command)
        elif method == "PUT":
            return self._http_put(url, command)
        return {"status": "unsupported_method"}

    # ── HTTP Utilities ──────────────────────────────────────────

    def _http_get(self, url: str, headers: Optional[Dict] = None, timeout: int = 5) -> Dict:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode()
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {"status": "ok", "raw": data[:500]}
        except Exception as e:
            return {"error": str(e)}

    def _http_post(self, url: str, payload: Any, headers: Optional[Dict] = None, timeout: int = 5) -> Dict:
        try:
            import urllib.request
            if isinstance(payload, dict):
                data = json.dumps(payload).encode()
                hdrs = {"Content-Type": "application/json"}
            else:
                data = str(payload).encode()
                hdrs = {}
            if headers:
                hdrs.update(headers)
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode()
                try:
                    return json.loads(resp_data)
                except json.JSONDecodeError:
                    return {"status": "ok", "raw": resp_data[:500]}
        except Exception as e:
            return {"error": str(e)}

    def _http_put(self, url: str, payload: Any, headers: Optional[Dict] = None, timeout: int = 5) -> Dict:
        try:
            import urllib.request
            data = json.dumps(payload).encode() if isinstance(payload, dict) else str(payload).encode()
            hdrs = {"Content-Type": "application/json"}
            if headers:
                hdrs.update(headers)
            req = urllib.request.Request(url, data=data, headers=hdrs, method="PUT")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode()
                try:
                    return json.loads(resp_data)
                except json.JSONDecodeError:
                    return {"status": "ok", "raw": resp_data[:500]}
        except Exception as e:
            return {"error": str(e)}

    def get_command_log(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return [
                {
                    "device_id": c.device_id,
                    "device_ip": c.device_ip,
                    "protocol": c.protocol,
                    "command": c.command,
                    "status": c.status,
                    "latency_ms": c.latency_ms,
                    "timestamp": c.timestamp,
                    "error": c.error,
                }
                for c in self._command_log[-limit:]
            ]


_bridge: Optional[DeviceBridge] = None
_bridge_lock = threading.Lock()


def get_bridge() -> DeviceBridge:
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                _bridge = DeviceBridge()
    return _bridge
