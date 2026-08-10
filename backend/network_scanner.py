"""
JARVIS Sovereign Network Scanner
=================================
Background daemon that sniffs mDNS, UPnP/SSDP, and ARP traffic
to auto-discover every device on the local network. Zero-config,
zero-cloud. The Wi-Fi router becomes a unified hardware bus.

Architecture:
  Raw Wi-Fi / Zigbee Subnet Traffic
         │
         ▼
  JARVIS LOCAL RELAY DAEMON (mDNS / Broadcast Sniffer)
         │
         ▼
  UNIVERSAL HARDWARE ABSTRACTION LAYER (HAL)
  - Normalizes proprietary states into unified JSON
         │
         ▼
  LOCAL MODEL EXECUTION (Sub-50ms Packet Emission)
"""

import json
import os
import socket
import struct
import subprocess
import threading
import time
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict

# ── OUI Database for Device Fingerprinting ──────────────────
# Maps MAC address prefixes to device manufacturers.
# This is how we fingerprint a Eufy vacuum by its Tuya chip handshake,
# or an Echo speaker by its Amazon web request.

OUI_DB: Dict[str, str] = {
    "00:1A:2B": "Texas Instruments",
    "00:1B:2F": "Samsung",
    "00:1E:58": "D-Link",
    "00:24:01": "D-Link",
    "00:26:5D": "Netatmo",
    "00:27:22": "LIFX",
    "04:A1:51": "Netatmo",
    "08:3A:F2": "Espressif",
    "0C:80:63": "TP-Link",
    "18:B4:30": "Nest Labs",
    "20:DF:B9": "Google",
    "28:6C:07": "iRobot",
    "30:B5:C2": "TP-Link",
    "34:CE:00": "Philips Hue",
    "40:F4:EC": "Nintendo",
    "44:65:0D": "Amazon",
    "48:D7:05": "Tuya",
    "50:C7:BF": "Tuya",
    "54:60:09": "Google",
    "54:9F:13": "Amazon",
    "5C:CF:7F": "Espressif",
    "60:01:94": "LIFX",
    "60:38:E0": "Belkin",
    "60:A4:4C": "ASUS",
    "64:33:B5": "LIFX",
    "64:66:B3": "Sonos",
    "68:C9:0B": "Tuya",
    "70:4D:7B": "ASUS",
    "74:C2:46": "Amazon",
    "78:11:DC": "Tuya",
    "7C:49:EB": "Raspberry Pi",
    "80:CE:62": "Hewlett-Packard",
    "84:D6:D0": "Amazon",
    "88:2F:B4": "Xiaomi",
    "8C:3B:AD": "Netgear",
    "90:9C:4A": "Apple",
    "94:35:0A": "Samsung",
    "94:B9:7F": "Tuya",
    "98:76:B6": "Tuya",
    "9C:32:CE": "Tuya",
    "A0:20:A6": "Amazon",
    "A4:CF:12": "Espressif",
    "A8:15:5D": "Netatmo",
    "AC:63:BE": "Amazon",
    "B0:4E:26": "TP-Link",
    "B0:BE:76": "Tuya",
    "B4:E6:2D": "Amazon",
    "B8:27:EB": "Raspberry Pi",
    "BC:FF:7D": "Amazon",
    "C0:25:E9": "TP-Link",
    "C4:3A:28": "Tuya",
    "C8:2B:96": "Tuya",
    "CC:50:E3": "Amazon",
    "CC:9E:A2": "Amazon",
    "D0:27:17": "Amazon",
    "D4:3A:2E": "Google",
    "D8:0F:99": "Sonos",
    "DC:4F:22": "Amazon",
    "E0:52:42": "Tuya",
    "E4:5F:01": "Google",
    "E8:48:B8": "Amazon",
    "EC:FA:BC": "Tuya",
    "F0:27:2D": "Amazon",
    "F0:29:29": "Tuya",
    "F4:F5:D8": "Google",
    "F8:1A:67": "Tuya",
    "FC:67:1F": "Tuya",
}


@dataclass
class NetworkDevice:
    """A device discovered on the local network via any sniffing method."""
    id: str
    ip: str
    mac: str = ""
    hostname: str = ""
    manufacturer: str = ""
    device_type: str = "unknown"
    protocol: str = "unknown"
    ports: List[int] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    raw_ads: Dict[str, str] = field(default_factory=dict)
    discovery_method: str = ""  # mdns, ssdp, arp, arp_ping, tcp_probe
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    signal_strength: Optional[int] = None
    is_alive: bool = True
    fingerprint: str = ""
    network_latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "NetworkDevice":
        return NetworkDevice(**{k: v for k, v in d.items() if k in NetworkDevice.__dataclass_fields__})


class NetworkScanner:
    """
    Sovereign Network Scanner — background daemon that auto-discovers
    every device on the local network using multiple sniffing techniques:

    1. ARP table scanning — reads system ARP cache for all known neighbors
    2. UDP broadcast — sends packets to 255.255.255.255 to elicit responses
    3. TCP SYN probing — probes common smart device ports for responses
    4. mDNS probing — queries _ipp._tcp, _hap._tcp, etc. via DNS-SD
    5. SSDP discovery — sends M-SEARCH to 239.255.255.250:1900

    Zero-configuration. Zero-cloud. The Wi-Fi router is the bus.
    """

    def __init__(self, scan_interval: int = 30, db_path: str = ""):
        self.scan_interval = scan_interval
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", ".network_devices.db"
        )
        self._devices: Dict[str, NetworkDevice] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Any] = []
        self._stats = {
            "scans_completed": 0,
            "devices_found_total": 0,
            "last_scan_time": 0.0,
            "last_scan_duration_ms": 0.0,
            "methods_used": defaultdict(int),
        }

        # Ports to probe for smart device fingerprinting
        self.PROBE_PORTS = [80, 443, 554, 8080, 8443, 1883, 5683, 8883, 9100, 2000]

        # mDNS service types to probe
        self.MDNS_TYPES = [
            "_ipp._tcp.local.",
            "_hap._tcp.local.",
            "_http._tcp.local.",
            "_mqtt._tcp.local.",
            "_coap._tcp.local.",
            "_airplay._tcp.local.",
            "_raop._tcp.local.",
            "_sonos._tcp.local.",
            "_googlecast._tcp.local.",
        ]

        # Load existing devices from disk
        self._load()

    # ── Persistence ────────────────────────────────────────

    def _load(self):
        """Load previously discovered devices from disk."""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path) as f:
                    data = json.load(f)
                for d in data:
                    nd = NetworkDevice.from_dict(d)
                    self._devices[nd.id] = nd
        except Exception:
            pass

    def _save(self):
        """Persist discovered devices to disk."""
        try:
            with self._lock:
                data = [nd.to_dict() for nd in self._devices.values()]
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    # ── Discovery Methods ──────────────────────────────────

    def scan_arp(self) -> List[NetworkDevice]:
        """
        Read the system ARP table to find all known network neighbors.
        This is the fastest, most reliable first-pass discovery method.
        """
        devices = []
        output = ""
        try:
            # Try system ARP command with longer timeout
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout
        except Exception:
            try:
                result = subprocess.run(
                    ["ip", "neigh"],
                    capture_output=True, text=True, timeout=15
                )
                output = result.stdout
            except Exception:
                pass

        if not output:
            return devices

        for line in output.splitlines():
            # macOS ARP format: "hostname (ip) at mac on interface [type]"
            # Linux ARP format: "ip hwtype mac address mask interface"
            ip = ""
            mac = ""
            hostname = ""

            # Try macOS format first: hostname (ip) at mac
            import re
            macos_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]+)', line)
            if macos_match:
                ip = macos_match.group(1)
                mac = macos_match.group(2).upper()
                # Extract hostname (everything before the parenthesis)
                paren_pos = line.find("(")
                if paren_pos > 0:
                    hostname = line[:paren_pos].strip()
            else:
                # Try Linux format
                parts = line.split()
                if not parts:
                    continue
                for p in parts:
                    if self._is_ip(p):
                        ip = p
                    elif self._is_mac(p):
                        mac = p.upper()

            if not ip or ip in ("255.255.255.255", "0.0.0.0", "(incomplete)"):
                continue
            if self._is_multicast_or_broadcast(ip):
                continue

            device_id = self._make_id(ip, mac)
            manufacturer = self._lookup_oui(mac) if mac else ""

            nd = NetworkDevice(
                id=device_id,
                ip=ip,
                mac=mac,
                hostname=hostname,
                manufacturer=manufacturer,
                discovery_method="arp",
                last_seen=time.time(),
            )
            devices.append(nd)

        return devices

    def scan_udp_broadcast(self) -> List[NetworkDevice]:
        """
        Send a UDP broadcast to 255.255.255.255 and listen for responses.
        Many smart devices respond to broadcasts to announce themselves.
        """
        devices = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2.0)

            # Send a minimal broadcast probe
            probe = b"\x00" * 64
            sock.sendto(probe, ("255.255.255.255", 7))

            # Also try SSDP-style broadcast
            ssdp_msg = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: 239.255.255.250:1900\r\n"
                "MAN: \"ssdp:discover\"\r\n"
                "ST: ssdp:all\r\n"
                "MX: 2\r\n"
                "\r\n"
            )
            sock.sendto(ssdp_msg.encode(), ("239.255.255.250", 1900))

            responses = []
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    responses.append((addr[0], data))
                except socket.timeout:
                    break
            sock.close()

            for ip, data in responses:
                device_id = self._make_id(ip)
                nd = NetworkDevice(
                    id=device_id,
                    ip=ip,
                    discovery_method="udp_broadcast",
                    raw_ads={"broadcast_response": data[:200].decode("utf-8", errors="ignore")},
                    last_seen=time.time(),
                )
                devices.append(nd)

        except Exception:
            pass
        return devices

    def scan_tcp_probe(self, ip_range: str = "") -> List[NetworkDevice]:
        """
        Probe common smart device ports on all IPs in the local subnet.
        If a port responds, we fingerprint the device via banner grabbing.
        """
        devices = []
        try:
            # Detect local subnet
            if not ip_range:
                ip_range = self._get_local_subnet()
        except Exception:
            return devices

        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
                futures = {}
                for i in range(1, 255):
                    ip = f"{ip_range}.{i}"
                    for port in self.PROBE_PORTS:
                        futures[pool.submit(self._probe_port, ip, port)] = (ip, port)

                for future in concurrent.futures.as_completed(futures, timeout=10):
                    ip, port = futures[future]
                    try:
                        result = future.result()
                        if result:
                            device_id = self._make_id(ip)
                            with self._lock:
                                if device_id not in self._devices:
                                    nd = NetworkDevice(
                                        id=device_id,
                                        ip=ip,
                                        ports=[port],
                                        discovery_method="tcp_probe",
                                        last_seen=time.time(),
                                    )
                                    devices.append(nd)
                                else:
                                    if port not in self._devices[device_id].ports:
                                        self._devices[device_id].ports.append(port)
                    except Exception:
                        pass
        except Exception:
            pass

        return devices

    def _probe_port(self, ip: str, port: int) -> Optional[str]:
        """Try to connect to an IP:port and return the banner if found."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, port))
            if result == 0:
                banner = ""
                try:
                    sock.settimeout(0.5)
                    sock.send(b"\r\n")
                    banner = sock.recv(256).decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
                sock.close()
                return banner or "open"
        except Exception:
            pass
        return None

    def scan_mdns(self) -> List[NetworkDevice]:
        """
        Probe mDNS service types to discover devices via DNS-SD.
        Falls back to direct UDP multicast to 224.0.0.251:5353.
        """
        devices = []

        for svc_type in self.MDNS_TYPES:
            try:
                # Try dig first
                result = subprocess.run(
                    ["dig", "+short", "-t", "PTR", svc_type],
                    capture_output=True, text=True, timeout=3
                )
                for line in result.stdout.splitlines():
                    line = line.strip().rstrip(".")
                    if not line:
                        continue
                    # Extract hostname from PTR record
                    hostname = line.split(".")[0]
                    # Resolve the hostname to get IP
                    ip = self._resolve_mdns(hostname)
                    if ip:
                        device_id = self._make_id(ip)
                        nd = NetworkDevice(
                            id=device_id,
                            ip=ip,
                            hostname=hostname,
                            discovery_method="mdns",
                            services=[svc_type.rstrip(".local.")],
                            last_seen=time.time(),
                        )
                        devices.append(nd)
            except Exception:
                pass

        # Fallback: multicast probe to 224.0.0.251:5353
        try:
            devices.extend(self._mdns_multicast_probe())
        except Exception:
            pass

        return devices

    def _mdns_multicast_probe(self) -> List[NetworkDevice]:
        """Send a raw mDNS query to 224.0.0.251:5353."""
        devices = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception:
                    pass
            sock.settimeout(2.0)

            # Bind to multicast group
            mreq = struct.pack("4s4s", socket.inet_aton("224.0.0.251"),
                               socket.inet_aton("0.0.0.0"))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            # Build mDNS query packet (simplified)
            header = b"\x00\x00\x84\x00\x00\x01\x00\x00\x00\x00\x00\x00"
            question = b"\x09_services\x07_dns-sd\x04_udp\x05local\x00\x00\x0c\x00\x01"
            sock.sendto(header + question, ("224.0.0.251", 5353))

            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    ip = addr[0]
                    device_id = self._make_id(ip)
                    nd = NetworkDevice(
                        id=device_id,
                        ip=ip,
                        discovery_method="mdns_multicast",
                        raw_ads={"mdns_response": data[:200].hex()},
                        last_seen=time.time(),
                    )
                    devices.append(nd)
                except socket.timeout:
                    break
            sock.close()
        except Exception:
            pass
        return devices

    def _resolve_mdns(self, hostname: str) -> Optional[str]:
        """Resolve an mDNS hostname to an IP address."""
        try:
            result = subprocess.run(
                ["dig", "+short", hostname],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if self._is_ip(line):
                    return line
        except Exception:
            pass
        # Fallback: try gethostbyname
        try:
            return socket.gethostbyname(hostname)
        except Exception:
            return None

    def scan_ssdp(self) -> List[NetworkDevice]:
        """
        SSDP discovery — sends M-SEARCH to 239.255.255.250:1900
        and parses the responses for device info.
        """
        devices = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(3.0)

            ssdp_msg = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: 239.255.255.250:1900\r\n"
                "MAN: \"ssdp:discover\"\r\n"
                "ST: ssdp:all\r\n"
                "MX: 3\r\n"
                "\r\n"
            )
            sock.sendto(ssdp_msg.encode(), ("239.255.255.250", 1900))

            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    ip = addr[0]
                    text = data.decode("utf-8", errors="ignore")
                    server = ""
                    st = ""
                    location = ""
                    for line in text.splitlines():
                        if line.upper().startswith("SERVER:"):
                            server = line.split(":", 1)[1].strip()
                        elif line.upper().startswith("ST:"):
                            st = line.split(":", 1)[1].strip()
                        elif line.upper().startswith("LOCATION:"):
                            location = line.split(":", 1)[1].strip()

                    device_id = self._make_id(ip)
                    nd = NetworkDevice(
                        id=device_id,
                        ip=ip,
                        manufacturer=server,
                        discovery_method="ssdp",
                        services=[st] if st else [],
                        raw_ads={"location": location, "server": server},
                        last_seen=time.time(),
                    )
                    devices.append(nd)
                except socket.timeout:
                    break
            sock.close()
        except Exception:
            pass
        return devices

    # ── Utility Methods ────────────────────────────────────

    def _get_local_subnet(self) -> str:
        """Detect the local subnet prefix (e.g., '192.168.1')."""
        env_subnet = os.environ.get("JARVIS_LOCAL_SUBNET", "").strip()
        if env_subnet:
            return env_subnet
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            parts = local_ip.split(".")
            return ".".join(parts[:3])
        except Exception:
            return ""

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _is_ip(self, s: str) -> bool:
        """Check if a string is an IP address."""
        parts = s.split(".")
        return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

    def _is_multicast_or_broadcast(self, ip: str) -> bool:
        """Check if an IP is multicast (224/4), broadcast (x.x.x.255), or invalid (x.x.x.0)."""
        parts = ip.split(".")
        if len(parts) != 4:
            return True
        first = int(parts[0])
        last = int(parts[3])
        return first >= 224 or last in (0, 255)

    def _is_mac(self, s: str) -> bool:
        """Check if a string is a MAC address."""
        s = s.upper().replace("-", ":")
        parts = s.split(":")
        return len(parts) == 6 and all(len(p) == 2 and all(c in "0123456789ABCDEF" for c in p) for p in parts)

    def _make_id(self, ip: str, mac: str = "") -> str:
        """Generate a stable device ID from IP and MAC."""
        key = f"{ip}:{mac}".lower().replace(":", "")
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def _lookup_oui(self, mac: str) -> str:
        """Look up device manufacturer from MAC address OUI prefix."""
        if not mac:
            return ""
        prefix = mac[:8].upper()
        for oui_prefix, manufacturer in OUI_DB.items():
            if prefix.startswith(oui_prefix):
                return manufacturer
        return ""

    def _fingerprint_device(self, nd: NetworkDevice) -> str:
        """Generate a device fingerprint from available data."""
        parts = []
        if nd.manufacturer:
            parts.append(nd.manufacturer.lower())
        if nd.hostname:
            parts.append(nd.hostname.lower())
        if nd.services:
            parts.extend(s.lower() for s in nd.services)
        if nd.ports:
            parts.append(f"ports:{sorted(nd.ports)}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]

    # ── Full Scan ──────────────────────────────────────────

    def full_scan(self) -> Dict[str, NetworkDevice]:
        """
        Execute all discovery methods in parallel and merge results.
        Returns a dict of all discovered devices.
        """
        start = time.time()
        all_devices: Dict[str, NetworkDevice] = {}
        methods_used = defaultdict(int)

        # Run all scans in parallel
        scan_methods = [
            ("arp", self.scan_arp),
            ("ssdp", self.scan_ssdp),
            ("mdns", self.scan_mdns),
            ("tcp_probe", self.scan_tcp_probe),
            ("udp_broadcast", self.scan_udp_broadcast),
        ]

        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(fn): name for name, fn in scan_methods}
                for future in concurrent.futures.as_completed(futures, timeout=15):
                    name = futures[future]
                    try:
                        results = future.result()
                        methods_used[name] = len(results)
                        for nd in results:
                            if nd.ip == self._get_local_ip():
                                continue  # Skip self
                            if nd.id in all_devices:
                                existing = all_devices[nd.id]
                                existing.last_seen = time.time()
                                existing.is_alive = True
                                if nd.mac and not existing.mac:
                                    existing.mac = nd.mac
                                if nd.hostname and not existing.hostname:
                                    existing.hostname = nd.hostname
                                if nd.manufacturer and not existing.manufacturer:
                                    existing.manufacturer = nd.manufacturer
                                if nd.services:
                                    existing.services = list(set(existing.services + nd.services))
                                if nd.ports:
                                    existing.ports = list(set(existing.ports + nd.ports))
                            else:
                                nd.fingerprint = self._fingerprint_device(nd)
                                all_devices[nd.id] = nd
                    except Exception:
                        pass
        except Exception:
            pass

        # Merge with existing devices
        with self._lock:
            for nd in all_devices.values():
                if nd.id in self._devices:
                    existing = self._devices[nd.id]
                    existing.last_seen = time.time()
                    existing.is_alive = True
                    existing.network_latency_ms = nd.network_latency_ms
                    if nd.mac and not existing.mac:
                        existing.mac = nd.mac
                    if nd.hostname and not existing.hostname:
                        existing.hostname = nd.hostname
                    if nd.manufacturer and not existing.manufacturer:
                        existing.manufacturer = nd.manufacturer
                    if nd.services:
                        existing.services = list(set(existing.services + nd.services))
                    if nd.ports:
                        existing.ports = list(set(existing.ports + nd.ports))
                    if nd.raw_ads:
                        existing.raw_ads.update(nd.raw_ads)
                else:
                    self._devices[nd.id] = nd

            # Mark devices not seen in this scan as potentially offline
            now = time.time()
            for nd in self._devices.values():
                if nd.id not in all_devices and (now - nd.last_seen) > self.scan_interval * 3:
                    nd.is_alive = False

        elapsed_ms = (time.time() - start) * 1000

        # Update stats
        self._stats["scans_completed"] += 1
        self._stats["devices_found_total"] = len(self._devices)
        self._stats["last_scan_time"] = time.time()
        self._stats["last_scan_duration_ms"] = round(elapsed_ms, 1)
        self._stats["methods_used"] = dict(methods_used)

        # Persist
        self._save()

        # Fire callbacks
        for cb in self._callbacks:
            try:
                cb(self._devices)
            except Exception:
                pass

        return dict(self._devices)

    # ── Background Daemon ──────────────────────────────────

    def start(self):
        """Start the background scanning daemon."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background scanning daemon."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        """Background loop that scans periodically."""
        while self._running:
            try:
                self.full_scan()
            except Exception:
                pass
            time.sleep(self.scan_interval)

    def on_discovery(self, callback):
        """Register a callback that fires when new devices are discovered."""
        self._callbacks.append(callback)

    # ── Query Methods ──────────────────────────────────────

    def get_all(self) -> List[NetworkDevice]:
        """Get all known devices."""
        with self._lock:
            return list(self._devices.values())

    def get_alive(self) -> List[NetworkDevice]:
        """Get all currently alive devices."""
        with self._lock:
            return [nd for nd in self._devices.values() if nd.is_alive]

    def get_by_type(self, device_type: str) -> List[NetworkDevice]:
        """Get devices matching a given type."""
        with self._lock:
            return [nd for nd in self._devices.values() if nd.device_type == device_type]

    def get_by_manufacturer(self, manufacturer: str) -> List[NetworkDevice]:
        """Get devices from a given manufacturer."""
        with self._lock:
            return [nd for nd in self._devices.values()
                    if manufacturer.lower() in nd.manufacturer.lower()]

    def get_stats(self) -> dict:
        """Get scanner statistics."""
        with self._lock:
            alive = sum(1 for nd in self._devices.values() if nd.is_alive)
            return {
                **self._stats,
                "total_devices": len(self._devices),
                "alive_devices": alive,
                "offline_devices": len(self._devices) - alive,
                "subnet": self._get_local_subnet(),
                "local_ip": self._get_local_ip(),
                "scan_interval": self.scan_interval,
            }

    def get_network_topology(self) -> dict:
        """
        Build a network topology map showing:
        - All discovered devices
        - Their connections (IP-based grouping)
        - Protocol distribution
        - Manufacturer distribution
        """
        with self._lock:
            devices = list(self._devices.values())

        # Group by subnet
        subnets = defaultdict(list)
        for nd in devices:
            subnet = ".".join(nd.ip.split(".")[:3])
            subnets[subnet].append(nd.to_dict())

        # Manufacturer distribution
        manufacturers = defaultdict(int)
        for nd in devices:
            m = nd.manufacturer or "Unknown"
            manufacturers[m] += 1

        # Protocol distribution
        protocols = defaultdict(int)
        for nd in devices:
            protocols[nd.protocol] += 1

        # Service distribution
        services = defaultdict(int)
        for nd in devices:
            for svc in nd.services:
                services[svc] += 1

        return {
            "total_devices": len(devices),
            "alive_devices": sum(1 for nd in devices if nd.is_alive),
            "subnets": dict(subnets),
            "manufacturers": dict(manufacturers),
            "protocols": dict(protocols),
            "services": dict(services),
            "local_ip": self._get_local_ip(),
            "subnet": self._get_local_subnet(),
        }


# ── Global singleton ───────────────────────────────────────

_scanner: Optional[NetworkScanner] = None
_scanner_lock = threading.Lock()


def get_scanner(scan_interval: int = 30) -> NetworkScanner:
    """Get or create the global NetworkScanner instance."""
    global _scanner
    with _scanner_lock:
        if _scanner is None:
            _scanner = NetworkScanner(scan_interval=scan_interval)
        return _scanner


def start_scanner(scan_interval: int = 30) -> NetworkScanner:
    """Start the global network scanner daemon."""
    scanner = get_scanner(scan_interval)
    scanner.start()
    return scanner
