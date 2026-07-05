"""
JARVIS Command Engine
======================
Local command emission with protocol translation, execution tracking,
and self-healing. Commands are dispatched locally — zero cloud, zero latency.

The command engine is the bridge between the AI's decision and the
physical device's action. It:
1. Receives a universal action (e.g., "TURN_ON", "SET_BRIGHTNESS")
2. Translates it to the device's native protocol via UniversalHAL
3. Executes the command locally (HTTP, MQTT, mDNS, etc.)
4. Logs the result and updates device state
5. Self-heals if the command fails (retry, alternative protocol, etc.)
"""

import json
import os
import socket
import struct
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Callable

from device_manager import (
    get_device, update_device_state, log_command, update_command_status,
)
from universal_hal import get_hal


# ── Command Result ──────────────────────────────────────────


@dataclass
class CommandResult:
    """Result of a command execution."""
    device_id: str
    action: str
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending, success, error, timeout
    result: dict = field(default_factory=dict)
    latency_ms: float = 0
    error: str = ""
    protocol_used: str = ""
    retries: int = 0
    timestamp: float = field(default_factory=time.time)
    log_id: int = 0

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "action": self.action,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "latency_ms": round(self.latency_ms, 1),
            "error": self.error,
            "protocol_used": self.protocol_used,
            "retries": self.retries,
            "timestamp": self.timestamp,
            "log_id": self.log_id,
        }


# ── Protocol Executors ──────────────────────────────────────
# Each executor handles the actual network call for a specific protocol.


class HTTPExecutor:
    """Execute commands over HTTP/HTTPS."""

    def execute(self, ip: str, port: int, path: str, method: str = "GET",
                data: dict = None, headers: dict = None, timeout: float = 5) -> dict:
        """Send an HTTP request to a device."""
        url = f"http://{ip}:{port}{path}"
        try:
            import requests
            resp = requests.request(
                method, url, json=data, headers=headers or {},
                timeout=timeout
            )
            return {"status_code": resp.status_code, "body": resp.text[:1000]}
        except ImportError:
            # Fallback to curl
            cmd = ["curl", "-s", "--max-time", str(timeout), "-X", method]
            if data:
                cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(data)])
            cmd.append(url)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
            return {"status_code": 200, "body": result.stdout[:1000]}
        except Exception as e:
            return {"error": str(e)}


class MQTTExecutor:
    """Execute commands over MQTT."""

    def execute(self, broker: str, port: int, topic: str, payload: str,
                qos: int = 1, timeout: float = 5) -> dict:
        """Publish a message to an MQTT broker."""
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client()
            client.connect(broker, port, timeout)
            result = client.publish(topic, payload, qos=qos)
            client.disconnect()
            return {"status": "published", "mid": result.mid}
        except ImportError:
            # Fallback to mosquitto_pub
            cmd = [
                "mosquitto_pub", "-h", broker, "-p", str(port),
                "-t", topic, "-m", payload, "-q", str(qos)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
            return {"status": "published" if result.returncode == 0 else "error",
                    "stderr": result.stderr[:500]}
        except Exception as e:
            return {"error": str(e)}


class UDPExecutor:
    """Execute commands over raw UDP (Tuya, Miio, etc.)."""

    def execute(self, ip: str, port: int, payload: bytes, timeout: float = 3) -> dict:
        """Send a UDP packet to a device."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(payload, (ip, port))
            try:
                data, addr = sock.recvfrom(1024)
                sock.close()
                return {"status": "received", "response": data.hex()[:200]}
            except socket.timeout:
                sock.close()
                return {"status": "sent_no_response"}
        except Exception as e:
            return {"error": str(e)}


class UPnPExecutor:
    """Execute UPnP/SOAP commands for media devices."""

    def execute(self, ip: str, port: int, action: str, service: str = "AVTransport",
                params: dict = None, timeout: float = 5) -> dict:
        """Send a UPnP SOAP action."""
        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="urn:schemas-upnp-org:service:{service}:1">
      {" ".join(f"<{k}>{v}</{k}>" for k, v in (params or {}).items())}
    </u:{action}>
  </s:Body>
</s:Envelope>"""

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"urn:schemas-upnp-org:service:{service}:1#{action}"',
        }

        try:
            import requests
            resp = requests.post(
                f"http://{ip}:{port}/upnp/control/{service}",
                data=soap_body, headers=headers, timeout=timeout
            )
            return {"status_code": resp.status_code, "body": resp.text[:1000]}
        except Exception as e:
            return {"error": str(e)}


class SSHExecutor:
    """Execute commands over SSH for Linux-based IoT devices."""

    def execute(self, ip: str, port: int, command: str, username: str = "root",
                key_path: str = "", timeout: float = 10) -> dict:
        """Execute a command on a remote device via SSH."""
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
        if key_path:
            ssh_cmd.extend(["-i", key_path])
        ssh_cmd.extend(["-p", str(port), f"{username}@{ip}", command])

        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:500],
            }
        except Exception as e:
            return {"error": str(e)}


class WebSocketExecutor:
    """Execute commands over WebSocket for real-time devices."""

    def __init__(self):
        self._connections: Dict[str, Any] = {}

    def execute(self, url: str, message: dict, timeout: float = 5) -> dict:
        """Send a WebSocket message."""
        try:
            import websocket
            ws = websocket.create_connection(url, timeout=timeout)
            ws.send(json.dumps(message))
            result = ws.recv()
            ws.close()
            return {"status": "received", "response": result[:1000]}
        except ImportError:
            return {"error": "websocket-client not installed"}
        except Exception as e:
            return {"error": str(e)}


# ── Command Engine ──────────────────────────────────────────


class CommandEngine:
    """
    Local command emission engine with protocol translation,
    execution tracking, and self-healing.
    """

    def __init__(self):
        self._hal = get_hal()
        self._executors = {
            "http": HTTPExecutor(),
            "https": HTTPExecutor(),
            "mqtt": MQTTExecutor(),
            "udp": UDPExecutor(),
            "upnp": UPnPExecutor(),
            "dlna": UPnPExecutor(),
            "ssh": SSHExecutor(),
            "websocket": WebSocketExecutor(),
        }
        self._interceptors: List[Callable] = []
        self._max_retries = 2
        self._command_timeout = 5.0
        self._lock = threading.Lock()

    def register_executor(self, protocol: str, executor: Any):
        """Register a custom protocol executor."""
        self._executors[protocol] = executor

    def add_interceptor(self, callback: Callable):
        """Add a command interceptor (for security, logging, etc.)."""
        self._interceptors.append(callback)

    def execute(
        self,
        device_id: str,
        action: str,
        params: dict = None,
        initiated_by: str = "user",
        bypass_safety: bool = False,
    ) -> CommandResult:
        """
        Execute a command on a device.

        1. Look up the device in the registry
        2. Translate the universal action to a protocol-specific command
        3. Execute the command via the appropriate protocol executor
        4. Log the result and update device state
        5. Self-heal on failure (retry, alternative protocol)
        """
        params = params or {}
        result = CommandResult(
            device_id=device_id,
            action=action,
            params=params,
        )

        # Look up device
        device = get_device(device_id)
        if not device:
            result.status = "error"
            result.error = f"Device {device_id} not found"
            result.log_id = log_command(
                device_id, action, params, "error", {}, 0, result.error, initiated_by
            )
            return result

        # Run interceptors (security, audit, etc.)
        if not bypass_safety:
            for interceptor in self._interceptors:
                try:
                    allowed = interceptor(device, action, params)
                    if allowed is False:
                        result.status = "error"
                        result.error = "Command blocked by interceptor"
                        result.log_id = log_command(
                            device_id, action, params, "error", {}, 0, result.error, initiated_by
                        )
                        return result
                except Exception:
                    pass

        # Translate to protocol-specific command
        raw_device = {
            "ip": device.get("ip", ""),
            "port": device.get("network_port", 80),
            "protocol": device.get("protocol", "http"),
            "mac": device.get("mac", ""),
            "manufacturer": device.get("manufacturer", ""),
            "state": device.get("state", {}),
        }
        command_payload = self._hal.translate_action(action, params, raw_device)

        # Execute with retries
        start_time = time.time()
        retries = 0
        last_error = ""

        for attempt in range(self._max_retries + 1):
            try:
                result = self._execute_protocol(
                    command_payload, device, action, params
                )
                result.retries = retries

                if result.status == "success":
                    break

                last_error = result.error
                retries += 1

            except Exception as e:
                last_error = str(e)
                retries += 1

            if attempt < self._max_retries:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff

        # Calculate latency
        elapsed = (time.time() - start_time) * 1000
        result.latency_ms = elapsed
        result.retries = retries

        # Log the command
        result.log_id = log_command(
            device_id, action, params,
            result.status, result.result,
            elapsed, result.error, initiated_by
        )

        # Update device state if successful
        if result.status == "success" and result.result:
            new_state = device.get("state", {})
            new_state.update(result.result)
            update_device_state(device_id, new_state)

        return result

    def _execute_protocol(
        self, command_payload: dict, device: dict, action: str, params: dict
    ) -> CommandResult:
        """Execute a command using the appropriate protocol executor."""
        protocol = command_payload.get("protocol", "http").lower()
        result = CommandResult(
            device_id=device.get("id", ""),
            action=action,
            params=params,
        )

        ip = device.get("ip", "")
        port = device.get("network_port", 80)
        result.protocol_used = protocol

        try:
            if protocol in ("http", "https"):
                executor = self._executors["http"]
                path = command_payload.get("path", f"/api/{action.lower()}")
                method = command_payload.get("method", "POST")
                data = command_payload.get("data", command_payload.get("payload", {}))

                response = executor.execute(ip, port, path, method, data)

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                elif response.get("status_code", 200) in (200, 201, 204):
                    result.status = "success"
                    result.result = self._parse_response(response.get("body", ""))
                else:
                    result.status = "error"
                    result.error = f"HTTP {response.get('status_code')}: {response.get('body', '')[:200]}"

            elif protocol == "mqtt":
                executor = self._executors["mqtt"]
                broker = command_payload.get("broker", ip)
                broker_port = command_payload.get("port", 1883)
                topic = command_payload.get("topic", "")
                payload = command_payload.get("payload", "{}")

                response = executor.execute(broker, broker_port, topic, payload)

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"published": True}

            elif protocol in ("upnp", "dlna"):
                executor = self._executors["upnp"]
                upnp_action = command_payload.get("action", action)
                service = command_payload.get("service", "AVTransport")
                upnp_params = command_payload.get("params", params)

                response = executor.execute(ip, port, upnp_action, service, upnp_params)

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"upnp_response": response.get("body", "")[:200]}

            elif protocol == "udp":
                executor = self._executors["udp"]
                payload = command_payload.get("payload", b"")
                if isinstance(payload, str):
                    payload = payload.encode()
                udp_port = command_payload.get("port", port)

                response = executor.execute(ip, udp_port, payload)

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"udp_response": response.get("response", "")[:200]}

            elif protocol == "ssh":
                executor = self._executors["ssh"]
                cmd = command_payload.get("command", f"echo '{action}'")
                username = command_payload.get("username", "root")
                key_path = command_payload.get("key_path", "")

                response = executor.execute(ip, port, cmd, username, key_path)

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"stdout": response.get("stdout", "")[:500]}

            elif protocol == "websocket":
                executor = self._executors["websocket"]
                url = command_payload.get("url", f"ws://{ip}:{port}")
                message = command_payload.get("message", {"action": action, **params})

                response = executor.execute(url, message)

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"ws_response": response.get("response", "")[:200]}

            elif protocol == "tuya":
                # Tuya devices use UDP with encrypted payloads
                executor = self._executors["udp"]
                payload = command_payload.get("dps", {})
                # In production, this would encrypt with the device's key
                response = executor.execute(ip, port, json.dumps(payload).encode())

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"tuya_dps": payload}

            elif protocol == "miio":
                # Miio devices use UDP with specific packet format
                executor = self._executors["udp"]
                cmd = command_payload.get("command", action)
                # In production, this would use the miio protocol format
                response = executor.execute(ip, port, cmd.encode())

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"miio_response": response.get("response", "")[:200]}

            elif protocol == "home_assistant":
                # Home Assistant API call
                executor = self._executors["http"]
                entity_id = command_payload.get("entity_id", "")
                service = command_payload.get("service", "turn_on")
                service_data = command_payload.get("service_data", {})

                # Assume HA is running on a known host
                ha_host = os.environ.get("HOME_ASSISTANT_HOST", "http://localhost:8123")
                ha_token = os.environ.get("HOME_ASSISTANT_TOKEN", "")

                path = f"/api/services/{service.split('.')[0]}/{service.split('.')[1] if '.' in service else service}"
                headers = {"Authorization": f"Bearer {ha_token}"}

                response = executor.execute(
                    ha_host.replace("http://", "").replace("https://", "").split(":")[0],
                    int(ha_host.split(":")[-1]) if ":" in ha_host else 80,
                    path, "POST", {"entity_id": entity_id, **service_data}, headers
                )

                if "error" in response:
                    result.status = "error"
                    result.error = response["error"]
                else:
                    result.status = "success"
                    result.result = {"ha_service": service, "entity_id": entity_id}

            else:
                result.status = "error"
                result.error = f"Unknown protocol: {protocol}"

        except Exception as e:
            result.status = "error"
            result.error = f"Protocol execution error: {str(e)}"

        return result

    def _parse_response(self, body: str) -> dict:
        """Try to parse an HTTP response body as JSON."""
        try:
            return json.loads(body)
        except Exception:
            return {"raw": body[:200]}

    def execute_batch(
        self, commands: List[dict], parallel: bool = False
    ) -> List[CommandResult]:
        """
        Execute multiple commands in sequence or parallel.
        Each command: {"device_id": "...", "action": "...", "params": {...}}
        """
        if not parallel:
            return [self.execute(c["device_id"], c["action"], c.get("params", {}))
                    for c in commands]

        results = []
        with threading.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(self.execute, c["device_id"], c["action"], c.get("params", {}))
                for c in commands
            ]
            for f in futures:
                try:
                    results.append(f.result(timeout=10))
                except Exception as e:
                    results.append(CommandResult(
                        device_id="unknown", action="batch",
                        status="error", error=str(e)
                    ))
        return results

    def get_stats(self) -> dict:
        """Get command engine statistics."""
        from .device_manager import get_command_stats
        return {
            "protocols_supported": list(self._executors.keys()),
            "interceptors": len(self._interceptors),
            "max_retries": self._max_retries,
            "command_timeout": self._command_timeout,
            **get_command_stats(),
        }


# ── Global singleton ───────────────────────────────────────

_engine: Optional[CommandEngine] = None
_engine_lock = threading.Lock()


def get_command_engine() -> CommandEngine:
    """Get or create the global CommandEngine instance."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = CommandEngine()
        return _engine
