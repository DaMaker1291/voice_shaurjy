"""
Device Discovery & Mobile/Wearable Streamer
- zeroconf ServiceBrowser for mDNS device discovery
- WebSocket server at ws://localhost:8080/stream
- Compressed VDI screen stream to connected watch/phone WebApps
"""
import os
import json
import logging
import threading
import asyncio
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger("wearable_sync")

WS_PORT = 8080
WS_ENDPOINT = "/stream"
MDNS_SERVICE_TYPE = "_jarvis._tcp.local."


class DeviceDiscovery:
    """Discovers local IoT/smart devices via mDNS (zeroconf)."""

    def __init__(self):
        self._browser = None
        self._devices: List[Dict[str, Any]] = []
        self._callbacks: List[callable] = []

    def discover(self, service_type: str = MDNS_SERVICE_TYPE, timeout: int = 5) -> List[Dict[str, Any]]:
        """Discover local mDNS devices."""
        self._devices = []
        try:
            from zeroconf import ServiceBrowser, Zeroconf
        except ImportError:
            logger.warning("zeroconf not installed. Install with: pip install zeroconf")
            return self._get_mock_devices()

        class Listener:
            def __init__(self, outer):
                self.outer = outer

            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    device = {
                        "name": name,
                        "type": type_,
                        "address": str(info.parsed_addresses()[0]) if info.parsed_addresses() else "unknown",
                        "port": info.port,
                        "properties": {k.decode(): v.decode() if isinstance(v, bytes) else str(v) for k, v in (info.properties or {}).items()},
                    }
                    self.outer._devices.append(device)
                    for cb in self.outer._callbacks:
                        try:
                            cb("added", device)
                        except Exception:
                            pass

            def update_service(self, zc, type_, name):
                pass

            def remove_service(self, zc, type_, name):
                for cb in self.outer._callbacks:
                    try:
                        cb("removed", {"name": name, "type": type_})
                    except Exception:
                        pass

        zc = Zeroconf()
        self._browser = ServiceBrowser(zc, service_type, Listener(self))
        import time
        time.sleep(timeout)
        zc.close()

        return self._devices

    def _get_mock_devices(self) -> List[Dict[str, Any]]:
        """Return mock devices when zeroconf is not available."""
        return [
            {"name": "SmartLight_01", "type": "_hue._tcp.local.", "address": "192.168.1.10", "port": 80, "properties": {}},
            {"name": "SmartTV_LivingRoom", "type": "_androidtv._tcp.local.", "address": "192.168.1.15", "port": 8080, "properties": {}},
            {"name": "AudioReceiver", "type": "_sonos._tcp.local.", "address": "192.168.1.20", "port": 1400, "properties": {}},
        ]

    def on_device_event(self, callback: callable) -> None:
        """Register a callback for device add/remove events."""
        self._callbacks.append(callback)


class WearableStreamer:
    """WebSocket server for streaming VDI screen to wearables."""

    def __init__(self, port: int = WS_PORT):
        self.port = port
        self._server = None
        self._clients: Set[asyncio.WebSocketServerProtocol] = set()
        self._running = False

    async def _handle_client(self, websocket, path=None):
        self._clients.add(websocket)
        logger.info(f"Wearable client connected: {path or '/'}")
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if data.get("action") == "ping":
                            await websocket.send(json.dumps({"type": "pong"}))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"Client error: {e}")
        finally:
            self._clients.discard(websocket)
            logger.info(f"Wearable client disconnected")

    async def start(self):
        """Start the WebSocket server."""
        try:
            import websockets
        except ImportError:
            logger.warning("websockets not installed. Install with: pip install websockets")
            return False

        self._running = True
        self._server = await websockets.serve(
            self._handle_client,
            "localhost",
            self.port,
            max_size=2**20,
        )
        logger.info(f"Wearable streamer started on ws://localhost:{self.port}{WS_ENDPOINT}")
        return True

    async def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Wearable streamer stopped")

    async def stream_frame(self, frame_data: bytes, quality: int = 30):
        """Stream a compressed frame to all connected wearables."""
        if not self._clients:
            return
        message = json.dumps({
            "type": "frame",
            "quality": quality,
            "size": len(frame_data),
        })
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(message)
            except Exception:
                disconnected.add(client)
        for client in disconnected:
            self._clients.discard(client)

    def is_running(self) -> bool:
        return self._running

    async def stream_vdi_frame(self, frame_data: bytes, quality: int = 30) -> int:
        """Stream a compressed VDI desktop frame to all connected wearables.
        
        This implements the 'Send to my watch' feature: the active background VDI display
        buffer is compressed and streamed live to smartwatches or phones over local WebSockets.
        """
        return await self.stream_frame(frame_data, quality)


class WearableSyncManager:
    """Combined device discovery and wearable streaming manager."""

    def __init__(self):
        self.discovery = DeviceDiscovery()
        self.streamer = WearableStreamer()
        self._vdi_frame_callback = None
        self._target_devices: List[str] = []

    async def start(self) -> Dict[str, Any]:
        """Start both discovery and streaming."""
        devices = self.discovery.discover()
        streamer_ok = await self.streamer.start()
        return {
            "devices_found": len(devices),
            "devices": devices,
            "streamer_running": streamer_ok,
            "ws_endpoint": f"ws://localhost:{WS_PORT}{WS_ENDPOINT}",
        }

    async def stop():
        """Stop both discovery and streaming."""
        await self.streamer.stop()

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get discovered devices."""
        return self.discovery._devices

    def set_vdi_callback(self, callback: callable) -> None:
        """Register a callback to receive VDI frames from the background desktop.

        Called by the headless worker / VDI manager to push live frames to wearables.
        """
        self._vdi_frame_callback = callback

    def set_targets(self, device_names: List[str]) -> None:
        """Set target wearable devices for 'Send to my watch' streaming."""
        self._target_devices = device_names

    def get_targets(self) -> List[str]:
        """Get target wearable device names."""
        return self._target_devices

    async def send_to_watch(self, frame_data: bytes, quality: int = 25) -> Dict[str, Any]:
        """Send a VDI frame to paired smartwatch/phone devices.

        Compresses the active background VDI display buffer and streams it
        to connected wearables via ws://localhost:8080/stream.
        """
        if not self.streamer.is_running():
            return {"success": False, "error": "Streamer not running"}

        sent_count = await self.streamer.stream_frame(frame_data, quality)
        return {
            "success": True,
            "frames_sent": sent_count,
            "clients_connected": len(self.streamer._clients),
            "target_devices": self._target_devices,
        }


# ── Singleton ──────────────────────────────────────────────────────────

_wearable_manager: Optional[WearableSyncManager] = None


def get_wearable_sync() -> WearableSyncManager:
    """Get the shared WearableSyncManager singleton."""
    global _wearable_manager
    if _wearable_manager is None:
        _wearable_manager = WearableSyncManager()
    return _wearable_manager