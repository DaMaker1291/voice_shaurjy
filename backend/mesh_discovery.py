"""
JARVIS Mesh Discovery — mDNS + Home Assistant + UPnP device discovery.
Auto-discovers local smart devices, cameras, lights, thermostats.
"""
import json
import time
import logging
import socket
import asyncio
from typing import Optional

logger = logging.getLogger("mesh")


class DeviceRegistry:
    """In-memory device registry backed by SQLite."""

    def __init__(self, db=None):
        self.db = db
        self._devices: dict[str, dict] = {}

    def add_device(self, device_id: str, name: str, dtype: str,
                   ip: str, port: int = 0, capabilities: list[str] = None):
        self._devices[device_id] = {
            "id": device_id, "name": name, "type": dtype,
            "ip": ip, "port": port,
            "capabilities": capabilities or [],
            "last_seen": time.time(),
        }
        if self.db:
            self.db.register_device(device_id, name, dtype, ip, port, capabilities)
        logger.info(f"Device discovered: {name} ({dtype}) at {ip}:{port}")

    def get_device(self, device_id: str) -> Optional[dict]:
        return self._devices.get(device_id)

    def get_all(self) -> list[dict]:
        return list(self._devices.values())

    def get_by_type(self, dtype: str) -> list[dict]:
        return [d for d in self._devices.values() if d["type"] == dtype]

    def remove_stale(self, max_age_s: float = 300):
        now = time.time()
        stale = [k for k, v in self._devices.items() if now - v["last_seen"] > max_age_s]
        for k in stale:
            del self._devices[k]


class MDNSDiscovery:
    """Discover devices via mDNS/ZeroConf."""

    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
        self._browser = None

    def start(self):
        try:
            from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange
            self._zeroconf = Zeroconf()

            def on_change(zeroconf, service_type, name, state_change):
                if state_change == ServiceStateChange.Added:
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else "unknown"
                        caps = [f"{k}={v}" for k, v in (info.properties or {}).items()]
                        self.registry.add_device(
                            name, info.name, service_type, ip, info.port, caps
                        )

            self._browser = ServiceBrowser(self._zeroconf, "_http._tcp.local.", on_change)
            self._browser2 = ServiceBrowser(self._zeroconf, "_googlecast._tcp.local.", on_change)
            logger.info("mDNS discovery started")
        except ImportError:
            logger.warning("zeroconf not installed — mDNS discovery disabled")
        except Exception as e:
            logger.warning(f"mDNS failed: {e}")

    def stop(self):
        if hasattr(self, "_zeroconf"):
            self._zeroconf.close()


class HomeAssistantBridge:
    """Connect to a local Home Assistant instance via WebSocket."""

    def __init__(self, registry: DeviceRegistry, url: str = "ws://localhost:8123/api/websocket",
                 token: str = None):
        self.registry = registry
        self.url = url
        self.token = token
        self._ws = None

    async def connect(self):
        if not self.token:
            logger.info("Home Assistant: no token configured — skipping")
            return
        try:
            import websockets
            self._ws = await websockets.connect(self.url)
            # Authenticate
            auth = await self._ws.recv()
            await self._ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            result = json.loads(await self._ws.recv())
            if result.get("type") == "auth_ok":
                logger.info("Home Assistant connected")
                await self._sync_entities()
            else:
                logger.warning(f"HA auth failed: {result}")
        except Exception as e:
            logger.warning(f"Home Assistant connection failed: {e}")

    async def _sync_entities(self):
        """Fetch all entities from Home Assistant."""
        await self._ws.send(json.dumps({"id": 1, "type": "get_states"}))
        result = json.loads(await self._ws.recv())
        for entity in result.get("result", []):
            eid = entity["entity_id"]
            state = entity.get("state", "")
            attrs = entity.get("attributes", {})
            friendly_name = attrs.get("friendly_name", eid)
            domain = eid.split(".")[0]
            caps = [f"state={state}"]
            if "brightness" in attrs:
                caps.append(f"brightness={attrs['brightness']}")
            if "temperature" in attrs:
                caps.append(f"temperature={attrs['temperature']}")
            self.registry.add_device(eid, friendly_name, f"ha_{domain}",
                                     "homeassistant", 8123, caps)

    async def call_service(self, domain: str, service: str, entity_id: str, data: dict = None):
        """Call a Home Assistant service."""
        if not self._ws:
            return {"success": False, "error": "Not connected"}
        msg = {
            "id": int(time.time()),
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": data or {"entity_id": entity_id},
        }
        await self._ws.send(json.dumps(msg))
        result = json.loads(await self._ws.recv())
        return {"success": True, "result": result}

    async def turn_on(self, entity_id: str, **kwargs):
        return await self.call_service("light", "turn_on", entity_id, kwargs)

    async def turn_off(self, entity_id: str):
        return await self.call_service("light", "turn_off", entity_id)

    async def set_temperature(self, entity_id: str, temp: float):
        return await self.call_service("climate", "set_temperature", entity_id, {"temperature": temp})


class UPnPDiscovery:
    """Discover UPnP/SSDP devices on the local network."""

    def __init__(self, registry: DeviceRegistry):
        self.registry = registry

    def scan(self):
        try:
            import socket
            msg = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: 239.255.255.250:1900\r\n"
                "MAN: \"ssdp:discover\"\r\n"
                "MX: 3\r\n"
                "ST: ssdp:all\r\n"
                "\r\n"
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(4)
            sock.sendto(msg.encode(), ("239.255.255.250", 1900))
            devices = []
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode(errors="ignore")
                    headers = {}
                    for line in response.split("\r\n"):
                        if ":" in line:
                            k, v = line.split(":", 1)
                            headers[k.strip().upper()] = v.strip()
                    usn = headers.get("USN", "unknown")
                    server = headers.get("SERVER", "unknown")
                    if usn not in [d["id"] for d in devices]:
                        devices.append({
                            "id": usn, "name": server, "type": "upnp",
                            "ip": addr[0], "port": addr[1],
                        })
                except socket.timeout:
                    break
            sock.close()
            for d in devices:
                self.registry.add_device(d["id"], d["name"], d["type"],
                                         d["ip"], d["port"])
            return devices
        except Exception as e:
            logger.warning(f"UPnP scan failed: {e}")
            return []


class MeshController:
    """Main mesh controller — orchestrates all discovery methods."""

    def __init__(self, db=None):
        self.registry = DeviceRegistry(db)
        self.mdns = MDNSDiscovery(self.registry)
        self.ha = HomeAssistantBridge(self.registry)
        self.upnp = UPnPDiscovery(self.registry)

    async def start(self):
        self.mdns.start()
        self.upnp.scan()
        await self.ha.connect()
        logger.info(f"Mesh: {len(self.registry.get_all())} devices discovered")

    def get_devices(self) -> list[dict]:
        return self.registry.get_all()

    async def control(self, device_id: str, action: str, **kwargs):
        device = self.registry.get_device(device_id)
        if not device:
            return {"success": False, "error": f"Device not found: {device_id}"}
        if device["type"].startswith("ha_"):
            domain = device["type"].replace("ha_", "")
            return await self.ha.call_service(domain, action, device_id, kwargs)
        return {"success": False, "error": f"Cannot control {device['type']} devices yet"}
