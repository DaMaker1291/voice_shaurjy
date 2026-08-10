"""IoT Protocol Abstraction Layer for Zigbee, Z-Wave, and BLE devices."""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — libraries are only imported when a protocol is first used.
# ---------------------------------------------------------------------------

available_protocols: dict[str, bool] = {
    "ble": False,
    "zigbee": False,
    "zwave": False,
}

_bleak: Any = None
_zigpy: Any = None
_openzwave: Any = None


def _import_bleak() -> Any:
    global _bleak
    if _bleak is None:
        try:
            import bleak  # type: ignore[import-untyped]

            _bleak = bleak
            available_protocols["ble"] = True
            logger.info("bleak library loaded — BLE protocol available")
        except ImportError:
            available_protocols["ble"] = False
            logger.debug("bleak not installed — BLE protocol unavailable")
    return _bleak


def _import_zigpy() -> Any:
    global _zigpy
    if _zigpy is None:
        try:
            import zigpy.application  # type: ignore[import-untyped]

            _zigpy = zigpy
            available_protocols["zigbee"] = True
            logger.info("zigpy library loaded — Zigbee protocol available")
        except ImportError:
            available_protocols["zigbee"] = False
            logger.debug("zigpy not installed — Zigbee protocol unavailable")
    return _zigpy


def _import_openzwave() -> Any:
    global _openzwave
    if _openzwave is None:
        try:
            import libopenzwave  # type: ignore[import-untyped]

            _openzwave = libopenzwave
            available_protocols["zwave"] = True
            logger.info("libopenzwave loaded — Z-Wave protocol available")
        except ImportError:
            try:
                import openzwave  # type: ignore[import-untyped]

                _openzwave = openzwave
                available_protocols["zwave"] = True
                logger.info("openzwave loaded — Z-Wave protocol available")
            except ImportError:
                available_protocols["zwave"] = False
                logger.debug("openzwave not installed — Z-Wave protocol unavailable")
    return _openzwave


# ---------------------------------------------------------------------------
# Base protocol interface
# ---------------------------------------------------------------------------


class BaseProtocol(ABC):
    """Abstract base class for all IoT protocol implementations."""

    name: str = "base"

    @abstractmethod
    def scan(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Discover devices on this protocol's transport."""
        ...


# ---------------------------------------------------------------------------
# BLE Protocol
# ---------------------------------------------------------------------------


class BLEProtocol(BaseProtocol):
    """Bluetooth Low Energy protocol using *bleak*.

    Provides scanning, connection management, and GATT characteristic
    read/write operations for BLE peripherals.

    Raises
    ------
    RuntimeError
        If the ``bleak`` library is not installed.
    """

    name = "ble"

    def __init__(self) -> None:
        self._bleak = _import_bleak()
        if self._bleak is None:
            raise RuntimeError(
                "bleak is not installed. Install it with: pip install bleak"
            )

    # -- scanning -----------------------------------------------------------

    def scan(self, duration: float = 5) -> list[dict[str, Any]]:
        """Discover nearby BLE devices.

        Parameters
        ----------
        duration:
            How long to scan, in seconds (default ``5``).

        Returns
        -------
        list[dict]
            A list of dicts, each containing at least ``address`` and
            ``name`` keys.
        """
        from bleak import BleakScanner  # type: ignore[import-not-found]

        async def _scan() -> list[dict[str, Any]]:
            devices = await BleakScanner.discover(timeout=duration)
            return [
                {
                    "address": d.address,
                    "name": d.name,
                    "rssi": d.rssi,
                    "metadata": dict(d.metadata) if d.metadata else {},
                }
                for d in devices
            ]

        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _scan())
                return future.result()
        return asyncio.run(_scan())

    # -- connection ---------------------------------------------------------

    def connect(self, address: str) -> bool:
        """Connect to a BLE device by its MAC/UUID address.

        Returns ``True`` on success, ``False`` otherwise.
        """
        from bleak import BleakClient  # type: ignore[import-not-found]

        async def _connect() -> bool:
            async with BleakClient(address) as client:
                return client.is_connected

        import asyncio

        try:
            return asyncio.run(_connect())
        except Exception as exc:
            logger.error("BLE connect failed for %s: %s", address, exc)
            return False

    def disconnect(self, address: str) -> bool:
        """Disconnect from a BLE device.

        Returns ``True`` on success, ``False`` otherwise.
        """
        from bleak import BleakClient  # type: ignore[import-not-found]

        async def _disconnect() -> bool:
            async with BleakClient(address) as client:
                await client.disconnect()
                return not client.is_connected

        import asyncio

        try:
            return asyncio.run(_disconnect())
        except Exception as exc:
            logger.error("BLE disconnect failed for %s: %s", address, exc)
            return False

    # -- GATT operations ----------------------------------------------------

    def read_characteristic(self, address: str, char_uuid: str) -> bytes:
        """Read a GATT characteristic from a connected BLE device.

        Parameters
        ----------
        address:
            MAC or UUID address of the peripheral.
        char_uuid:
            UUID string of the characteristic to read.

        Returns
        -------
        bytes
            The raw value of the characteristic.

        Raises
        ------
        RuntimeError
            If the read operation fails.
        """
        from bleak import BleakClient  # type: ignore[import-not-found]

        async def _read() -> bytes:
            async with BleakClient(address) as client:
                data = await client.read_gatt_char(char_uuid)
                return bytes(data)

        import asyncio

        try:
            return asyncio.run(_read())
        except Exception as exc:
            raise RuntimeError(
                f"Failed to read characteristic {char_uuid} from {address}: {exc}"
            ) from exc

    def write_characteristic(
        self, address: str, char_uuid: str, data: bytes
    ) -> bool:
        """Write data to a GATT characteristic.

        Parameters
        ----------
        address:
            MAC or UUID address of the peripheral.
        char_uuid:
            UUID string of the characteristic to write.
        data:
            Raw bytes to write.

        Returns
        -------
        bool
            ``True`` on success, ``False`` otherwise.
        """
        from bleak import BleakClient  # type: ignore[import-not-found]

        async def _write() -> bool:
            async with BleakClient(address) as client:
                await client.write_gatt_char(char_uuid, data)
                return True

        import asyncio

        try:
            return asyncio.run(_write())
        except Exception as exc:
            logger.error(
                "BLE write failed for %s char %s: %s", address, char_uuid, exc
            )
            return False

    def list_services(self, address: str) -> list[dict[str, Any]]:
        """List all GATT services and characteristics on a device.

        Parameters
        ----------
        address:
            MAC or UUID address of the peripheral.

        Returns
        -------
        list[dict]
            Each dict represents a service with ``uuid``, ``description``,
            and a ``characteristics`` list.
        """
        from bleak import BleakClient  # type: ignore[import-not-found]

        async def _list() -> list[dict[str, Any]]:
            async with BleakClient(address) as client:
                services: list[dict[str, Any]] = []
                for service in client.services:
                    chars = [
                        {
                            "uuid": char.uuid,
                            "description": char.description,
                            "properties": list(char.properties),
                        }
                        for char in service.characteristics
                    ]
                    services.append(
                        {
                            "uuid": service.uuid,
                            "description": service.description,
                            "characteristics": chars,
                        }
                    )
                return services

        import asyncio

        try:
            return asyncio.run(_list())
        except Exception as exc:
            raise RuntimeError(
                f"Failed to list services for {address}: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Zigbee Protocol
# ---------------------------------------------------------------------------


class ZigbeeProtocol(BaseProtocol):
    """Zigbee protocol using *zigpy*.

    Communicates with Zigbee devices via a coordinator (e.g. ConBee, CC2531,
    EFR32).  Requires a running Zigbee coordinator adapter.

    Raises
    ------
    RuntimeError
        If the ``zigpy`` library is not installed.
    """

    name = "zigbee"

    def __init__(self, coordinator_type: str = "znp", serial_port: str | None = None) -> None:
        self._zigpy = _import_zigpy()
        if self._zigpy is None:
            raise RuntimeError(
                "zigpy is not installed. Install it with: pip install zigpy"
            )
        self._coordinator_type = coordinator_type
        self._serial_port = serial_port
        self._app: Any = None
        self._devices: dict[str, dict[str, Any]] = {}

    # -- coordinator lifecycle ----------------------------------------------

    async def _start_coordinator(self) -> Any:
        """Initialise and start the Zigbee coordinator application."""
        if self._app is not None:
            return self._app

        import zigpy.config  # type: ignore[import-not-found]

        config = zigpy.config.ZigpyConfig()
        if self._serial_port:
            config.device.path = self._serial_port  # type: ignore[union-attr]

        if self._coordinator_type == "znp":
            from zigpy.znp import ZNP  # type: ignore[import-not-found]

            self._app = await ZNP(config).start()
        elif self._coordinator_type == "deconz":
            from zigpy.deconz import DeconzNetworkSettings  # type: ignore[import-not-found]

            self._app = await DeconzNetworkSettings(config).start()
        else:
            from zigpy.application import ControllerApplication  # type: ignore[import-not-found]

            self._app = await ControllerApplication(config).start()

        return self._app

    # -- scanning -----------------------------------------------------------

    def scan(self) -> list[dict[str, Any]]:
        """Discover Zigbee devices via the coordinator.

        Returns all devices that have been paired with the coordinator.

        Returns
        -------
        list[dict]
            Each dict contains ``ieee``, ``nwk``, ``name``, and ``endpoints``.
        """
        import asyncio

        async def _scan() -> list[dict[str, Any]]:
            app = await self._start_coordinator()
            devices: list[dict[str, Any]] = []
            for ieee, device in app.devices.items():
                info = {
                    "ieee": str(ieee),
                    "nwk": device.nwk if hasattr(device, "nwk") else None,
                    "name": device.name if hasattr(device, "name") else str(ieee),
                    "endpoints": list(device.endpoints.keys())
                    if hasattr(device, "endpoints")
                    else [],
                }
                self._devices[str(ieee)] = info
                devices.append(info)
            return devices

        try:
            return asyncio.run(_scan())
        except Exception as exc:
            logger.error("Zigbee scan failed: %s", exc)
            return []

    # -- pairing ------------------------------------------------------------

    def pair(self, device_ieee: str) -> bool:
        """Permit a device to join the network (pairing window).

        Parameters
        ----------
        device_ieee:
            IEEE address of the device (as a string).

        Returns
        -------
        bool
            ``True`` if pairing was initiated successfully.
        """
        import asyncio

        async def _pair() -> bool:
            app = await self._start_coordinator()
            await app.permit(duration_s=120)
            return True

        try:
            return asyncio.run(_pair())
        except Exception as exc:
            logger.error("Zigbee pair failed for %s: %s", device_ieee, exc)
            return False

    # -- commands -----------------------------------------------------------

    def send_command(
        self,
        device_ieee: str,
        cluster: int,
        command: int,
        args: list | None = None,
    ) -> dict[str, Any]:
        """Send a raw ZCL command to a device.

        Parameters
        ----------
        device_ieee:
            IEEE address of the target device.
        cluster:
            ZCL cluster ID.
        command:
            ZCL command ID within the cluster.
        args:
            Optional list of command arguments.

        Returns
        -------
        dict
            ``{"success": True/True, "response": ...}`` or
            ``{"success": False, "error": "..."}``.
        """
        import asyncio

        async def _send() -> dict[str, Any]:
            app = await self._start_coordinator()
            device = app.get_device(self._zigpy.types.EUI64.convert(device_ieee))
            result = await device.zcl_request(
                cluster=cluster,
                command=command,
                args=args or [],
            )
            return {"success": True, "response": result}

        try:
            return asyncio.run(_send())
        except Exception as exc:
            logger.error(
                "Zigbee command failed for %s (cluster=%d, cmd=%d): %s",
                device_ieee,
                cluster,
                command,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # -- state management ---------------------------------------------------

    def get_device_state(self, device_ieee: str) -> dict[str, Any]:
        """Retrieve the current state of a Zigbee device.

        Queries common clusters (OnOff, Level, Color) when available.

        Returns
        -------
        dict
            Key/value pairs representing device attributes.
        """
        import asyncio

        async def _get() -> dict[str, Any]:
            app = await self._start_coordinator()
            device = app.get_device(self._zigpy.types.EUI64.convert(device_ieee))
            state: dict[str, Any] = {"ieee": device_ieee}

            for endpoint_id, endpoint in device.endpoints.items():
                if endpoint_id == 0:
                    continue
                for cluster_id, cluster in endpoint.in_clusters.items():
                    try:
                        attrs = await cluster.read_attributes(
                            list(cluster.attributes.keys())
                        )
                        for attr_id, value in attrs.items():
                            attr_name = cluster.attributes.get(attr_id, str(attr_id))
                            state[f"ep{endpoint_id}_c{cluster_id}_{attr_name}"] = value
                    except Exception:
                        pass
            return state

        try:
            return asyncio.run(_get())
        except Exception as exc:
            logger.error("Zigbee get_state failed for %s: %s", device_ieee, exc)
            return {"error": str(exc)}

    def set_device_state(self, device_ieee: str, state: dict[str, Any]) -> bool:
        """Apply a state dict to a Zigbee device.

        The ``state`` dict should contain keys like ``on_off`` (bool),
        ``brightness`` (int 0-255), etc.  Unsupported keys are ignored.

        Returns
        -------
        bool
            ``True`` if all supported commands succeeded.
        """
        import asyncio

        async def _set() -> bool:
            app = await self._start_coordinator()
            device = app.get_device(self._zigpy.types.EUI64.convert(device_ieee))
            success = True

            on_off = state.get("on_off")
            if on_off is not None:
                try:
                    from zigpy.zcl.clusters.general import OnOff  # type: ignore[import-not-found]

                    cluster = device.endpoints[1].clusters[OnOff.cluster_id]
                    if on_off:
                        await cluster.command(OnOff.command_id["on"])
                    else:
                        await cluster.command(OnOff.command_id["off"])
                except Exception as exc:
                    logger.warning("OnOff command failed: %s", exc)
                    success = False

            brightness = state.get("brightness")
            if brightness is not None:
                try:
                    from zigpy.zcl.clusters.general import LevelControl  # type: ignore[import-not-found]

                    cluster = device.endpoints[1].clusters[LevelControl.cluster_id]
                    await cluster.command(
                        LevelControl.command_id["move_to_level_with_on_off"],
                        brightness,
                        0,
                    )
                except Exception as exc:
                    logger.warning("LevelControl command failed: %s", exc)
                    success = False

            return success

        try:
            return asyncio.run(_set())
        except Exception as exc:
            logger.error("Zigbee set_state failed for %s: %s", device_ieee, exc)
            return False


# ---------------------------------------------------------------------------
# Z-Wave Protocol
# ---------------------------------------------------------------------------


class ZWaveProtocol(BaseProtocol):
    """Z-Wave protocol using *python-openzwave* / *libopenzwave*.

    Provides network scanning, node management, and value read/write
    operations for Z-Wave networks.

    Raises
    ------
    RuntimeError
        If no compatible Z-Wave library is installed.
    """

    name = "zwave"

    def __init__(self, config_path: str | None = None) -> None:
        self._ozw = _import_openzwave()
        if self._ozw is None:
            raise RuntimeError(
                "openzwave/libopenzwave is not installed. "
                "Install with: pip install python-openzwave"
            )
        self._config_path = config_path
        self._manager: Any = None

    def _get_manager(self) -> Any:
        """Return (or create) the Z-Wave manager instance."""
        if self._manager is not None:
            return self._manager

        try:
            from openzwave.option import ZWaveOption  # type: ignore[import-not-found]

            options = ZWaveOption(
                self._config_path or "",
                "",
                "",
            )
            options.lock()
            from openzwave.network import ZWaveNetwork  # type: ignore[import-not-found]

            self._manager = ZWaveNetwork
            return self._manager
        except Exception as exc:
            raise RuntimeError(f"Failed to initialise Z-Wave manager: {exc}") from exc

    # -- scanning -----------------------------------------------------------

    def scan(self) -> list[dict[str, Any]]:
        """Discover all nodes on the Z-Wave network.

        Returns
        -------
        list[dict]
            Each dict contains ``node_id``, ``name``, ``product_name``,
            ``manufacturer``, and ``is_alive``.
        """
        try:
            network = self._get_manager()
            nodes: list[dict[str, Any]] = []
            for node_id in network.nodes:
                node = network.nodes[node_id]
                nodes.append(
                    {
                        "node_id": node_id,
                        "name": getattr(node, "name", f"Node {node_id}"),
                        "product_name": getattr(node, "product_name", None),
                        "manufacturer": getattr(node, "manufacturer", None),
                        "is_alive": getattr(node, "is_alive", True),
                    }
                )
            return nodes
        except Exception as exc:
            logger.error("Z-Wave scan failed: %s", exc)
            return []

    # -- node management ----------------------------------------------------

    def add_node(self) -> bool:
        """Enter inclusion mode to add a new Z-Wave node.

        Returns ``True`` if inclusion mode was entered successfully.
        """
        try:
            network = self._get_manager()
            network.begin_adding()
            return True
        except Exception as exc:
            logger.error("Z-Wave add_node failed: %s", exc)
            return False

    def remove_node(self, node_id: int) -> bool:
        """Remove (exclude) a node from the Z-Wave network.

        Parameters
        ----------
        node_id:
            The numeric ID of the node to remove.

        Returns
        -------
        bool
            ``True`` if exclusion mode was entered successfully.
        """
        try:
            network = self._get_manager()
            if node_id in network.nodes:
                network.begin_excluding()
                return True
            logger.warning("Z-Wave node %d not found in network", node_id)
            return False
        except Exception as exc:
            logger.error("Z-Wave remove_node %d failed: %s", node_id, exc)
            return False

    # -- value operations ---------------------------------------------------

    def set_value(self, node_id: int, value_id: int, value: Any) -> bool:
        """Write a value to a Z-Wave node.

        Parameters
        ----------
        node_id:
            Numeric ID of the target node.
        value_id:
            The value ID within the node.
        value:
            The value to set (type depends on the Z-Wave value type).

        Returns
        -------
        bool
            ``True`` on success.
        """
        try:
            network = self._get_manager()
            node = network.nodes[node_id]
            zwave_value = node.values[value_id]
            zwave_value.data = value
            return True
        except KeyError:
            logger.error(
                "Z-Wave set_value failed: node %d or value %d not found",
                node_id,
                value_id,
            )
            return False
        except Exception as exc:
            logger.error(
                "Z-Wave set_value failed (node=%d, value=%d): %s",
                node_id,
                value_id,
                exc,
            )
            return False

    def get_value(self, node_id: int, value_id: int) -> Any:
        """Read a value from a Z-Wave node.

        Parameters
        ----------
        node_id:
            Numeric ID of the target node.
        value_id:
            The value ID within the node.

        Returns
        -------
        Any
            The current value, or ``None`` if the read fails.
        """
        try:
            network = self._get_manager()
            node = network.nodes[node_id]
            zwave_value = node.values[value_id]
            return zwave_value.data
        except KeyError:
            logger.error(
                "Z-Wave get_value failed: node %d or value %d not found",
                node_id,
                value_id,
            )
            return None
        except Exception as exc:
            logger.error(
                "Z-Wave get_value failed (node=%d, value=%d): %s",
                node_id,
                value_id,
                exc,
            )
            return None


# ---------------------------------------------------------------------------
# Unified Protocol Manager
# ---------------------------------------------------------------------------


class ProtocolManager:
    """Unified manager that abstracts over all available IoT protocols.

    Features
    --------
    * Auto-detects which protocol libraries are installed.
    * Provides a single ``discover()`` call that scans across all protocols.
    * Provides a single ``control()`` call to send commands to any device.
    * Caches discovered devices for 30 seconds to avoid repeated scans.
    * Falls back gracefully when a library is unavailable.
    """

    CACHE_TTL: float = 30.0  # seconds

    def __init__(self) -> None:
        self._protocols: dict[str, BaseProtocol] = {}
        self._device_cache: dict[str, dict[str, Any]] = {}
        self._cache_ts: float = 0.0
        self._init_protocols()

    # -- internal helpers ---------------------------------------------------

    def _init_protocols(self) -> None:
        """Attempt to instantiate each protocol; skip on failure."""
        for name, cls in [
            ("ble", BLEProtocol),
            ("zigbee", ZigbeeProtocol),
            ("zwave", ZWaveProtocol),
        ]:
            try:
                self._protocols[name] = cls()
                logger.info("Protocol '%s' initialised", name)
            except RuntimeError as exc:
                logger.debug("Skipping protocol '%s': %s", name, exc)
            except Exception as exc:
                logger.warning("Unexpected error loading protocol '%s': %s", name, exc)

    def _is_cache_valid(self) -> bool:
        return (time.monotonic() - self._cache_ts) < self.CACHE_TTL

    # -- public API ---------------------------------------------------------

    @property
    def available(self) -> dict[str, bool]:
        """Return a snapshot of which protocols are currently usable."""
        return {name: name in self._protocols for name in available_protocols}

    def discover(self, force: bool = False) -> list[dict[str, Any]]:
        """Discover devices across **all** available protocols.

        Parameters
        ----------
        force:
            If ``True``, bypass the cache and perform a fresh scan.

        Returns
        -------
        list[dict]
            Combined device list from every active protocol.  Each entry
            includes a ``protocol`` key identifying its source.
        """
        if not force and self._is_cache_valid():
            return list(self._device_cache.values())

        devices: dict[str, dict[str, Any]] = {}

        for proto_name, protocol in self._protocols.items():
            try:
                discovered = protocol.scan()
                for dev in discovered:
                    dev_id = self._make_device_id(proto_name, dev)
                    dev["protocol"] = proto_name
                    dev["id"] = dev_id
                    devices[dev_id] = dev
            except Exception as exc:
                logger.error("Discover on '%s' failed: %s", proto_name, exc)

        self._device_cache = devices
        self._cache_ts = time.monotonic()
        return list(devices.values())

    def control(
        self,
        protocol: str,
        device_id: str,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a command to a device on a specific protocol.

        Parameters
        ----------
        protocol:
            Protocol name — ``"ble"``, ``"zigbee"``, or ``"zwave"``.
        device_id:
            Protocol-specific device identifier (address, IEEE, node ID…).
        command:
            Command name to execute (e.g. ``"connect"``, ``"read"``,
            ``"send_command"``).
        params:
            Optional keyword arguments forwarded to the command method.

        Returns
        -------
        dict
            ``{"success": True, "result": ...}`` or
            ``{"success": False, "error": "..."}``.
        """
        params = params or {}

        if protocol not in self._protocols:
            return {
                "success": False,
                "error": f"Protocol '{protocol}' is not available",
            }

        proto = self._protocols[protocol]

        method = getattr(proto, command, None)
        if method is None or command.startswith("_"):
            return {
                "success": False,
                "error": f"Command '{command}' not found on protocol '{protocol}'",
            }

        try:
            result = method(device_id, **params) if params else method(device_id)
            return {"success": True, "result": result}
        except TypeError as exc:
            return {"success": False, "error": f"Invalid arguments: {exc}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_protocol(self, name: str) -> BaseProtocol | None:
        """Return a specific protocol instance by name, or ``None``."""
        return self._protocols.get(name)

    def invalidate_cache(self) -> None:
        """Force the next ``discover()`` call to perform a fresh scan."""
        self._cache_ts = 0.0
        self._device_cache.clear()

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _make_device_id(protocol: str, device: dict[str, Any]) -> str:
        """Derive a unique device identifier across protocols."""
        if "address" in device:
            return f"{protocol}:{device['address']}"
        if "ieee" in device:
            return f"{protocol}:{device['ieee']}"
        if "node_id" in device:
            return f"{protocol}:{device['node_id']}"
        return f"{protocol}:{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

manager = ProtocolManager()
