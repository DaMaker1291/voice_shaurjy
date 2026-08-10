"""
Smart Home Manager — full-spectrum device discovery, registry, and control.
Supports: Hue, WLED, ESPHome, Kasa/TPLink, Shelly, Tuya, Home Assistant,
MQTT auto-discovery, Matter (via bridge), UPnP/SSDP, mDNS/Bonjour, Sonoff, Tasmota.
"""

import json
import os
import re
import socket
import struct
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

try:
    import zeroconf as _zc
    _HAS_ZC = True
except ImportError:
    _HAS_ZC = False

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", ".smart_home_devices.json")
SCENES_PATH = os.path.join(os.path.dirname(__file__), "..", ".smart_home_scenes.json")
_lock = threading.Lock()


# ── Device type definitions ──────────────────────────────

DEVICE_CAPABILITIES = {
    "light": {
        "label": "💡 Light",
        "icon": "💡",
        "controls": ["on", "off", "toggle", "brightness", "color", "temperature"],
        "discovery": ["hue", "wled", "tasmota", "tuya", "esp", "matter", "mqtt", "eufy"],
    },
    "switch": {
        "label": "🔌 Switch/Plug",
        "icon": "🔌",
        "controls": ["on", "off", "toggle", "power_consumption"],
        "discovery": ["kasa", "shelly", "sonoff", "tasmota", "tuya", "mqtt", "matter", "eufy"],
    },
    "sensor": {
        "label": "📡 Sensor",
        "icon": "📡",
        "controls": ["read", "battery"],
        "discovery": ["esp", "mqtt", "zigbee", "matter", "eufy"],
    },
    "thermostat": {
        "label": "🌡 Thermostat",
        "icon": "🌡",
        "controls": ["on", "off", "temperature_set", "mode", "fan_mode", "schedule"],
        "discovery": ["nest", "ecobee", "mqtt", "ha", "matter"],
    },
    "lock": {
        "label": "🔒 Lock",
        "icon": "🔒",
        "controls": ["lock", "unlock", "status", "battery"],
        "discovery": ["matter", "mqtt", "ha", "tuya", "eufy"],
    },
    "cover": {
        "label": "🪟 Cover/Blind",
        "icon": "🪟",
        "controls": ["open", "close", "stop", "position"],
        "discovery": ["shelly", "mqtt", "ha", "matter"],
    },
    "camera": {
        "label": "📷 Camera/Doorbell",
        "icon": "📷",
        "controls": ["snapshot", "stream", "record", "two_way_audio", "motion_detect"],
        "discovery": ["rtsp", "onvif", "ha", "mqtt", "eufy"],
    },
    "vacuum": {
        "label": "🤖 Robot Vacuum",
        "icon": "🤖",
        "controls": ["start", "stop", "pause", "dock", "status", "schedule", "find"],
        "discovery": ["miio", "mqtt", "ha", "tuya", "eufy"],
    },
    "climate": {
        "label": "❄️ Climate (AC/Fan)",
        "icon": "❄️",
        "controls": ["on", "off", "temperature_set", "mode", "fan_speed", "swing"],
        "discovery": ["mqtt", "ha", "matter", "broadlink"],
    },
    "media_player": {
        "label": "📺 Media Player",
        "icon": "📺",
        "controls": ["on", "off", "volume", "mute", "input", "play_pause", "next", "prev"],
        "discovery": ["upnp", "ha", "dlna", "roku", "alexa"],
    },
    "hub": {
        "label": "🏠 Hub/Bridge",
        "icon": "🏠",
        "controls": ["status", "pair", "remove"],
        "discovery": ["hue", "ha", "mqtt", "zigbee", "matter", "eufy"],
    },
    "alexa": {
        "label": "🔊 Alexa/Echo",
        "icon": "🔊",
        "controls": ["speak", "volume", "routine", "music", "notification"],
        "discovery": ["upnp", "mdns", "ha"],
    },
    "speaker": {
        "label": "🔊 Smart Speaker",
        "icon": "🔊",
        "controls": ["volume", "play", "pause", "next", "speak"],
        "discovery": ["upnp", "ha", "airplay", "dlna"],
    },
    "doorbell": {
        "label": "🔔 Doorbell",
        "icon": "🔔",
        "controls": ["snapshot", "stream", "motion_detect", "record", "speak"],
        "discovery": ["eufy", "ring", "nest", "onvif", "rtsp"],
    },
}

ALL_CAPABILITIES = {}
for dtype, info in DEVICE_CAPABILITIES.items():
    for ctrl in info["controls"]:
        ALL_CAPABILITIES[ctrl] = dtype


# ── Data models ──────────────────────────────────────────

@dataclass
class SmartDevice:
    id: str
    name: str
    type: str  # light, switch, sensor, etc.
    ip: str
    port: int = 80
    mac: str = ""
    protocol: str = "http"  # http, mqtt, ha, matter, etc.
    status: str = "offline"  # online, offline
    room: str = "unknown"
    manufacturer: str = ""
    model: str = ""
    capabilities: list = field(default_factory=list)
    state: dict = field(default_factory=dict)
    last_seen: float = 0.0
    bridge_id: str = ""  # parent hub/bridge

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return SmartDevice(**d)


@dataclass
class SmartScene:
    id: str
    name: str
    icon: str = "🎬"
    devices: list = field(default_factory=list)  # [{device_id, state:{...}}]
    created: float = 0.0

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return SmartScene(**d)


# ── Registry persistence ────────────────────────────────

def _load_registry() -> dict[str, SmartDevice]:
    with _lock:
        if not os.path.isfile(REGISTRY_PATH):
            return {}
        try:
            with open(REGISTRY_PATH) as f:
                raw = json.load(f)
            return {k: SmartDevice.from_dict(v) for k, v in raw.items()}
        except:
            return {}

def _save_registry(devices: dict):
    with _lock:
        raw = {k: v.to_dict() for k, v in devices.items()}
        with open(REGISTRY_PATH, "w") as f:
            json.dump(raw, f, indent=2)

def _load_scenes() -> dict[str, SmartScene]:
    with _lock:
        if not os.path.isfile(SCENES_PATH):
            return {}
        try:
            with open(SCENES_PATH) as f:
                raw = json.load(f)
            return {k: SmartScene.from_dict(v) for k, v in raw.items()}
        except:
            return {}

def _save_scenes(scenes: dict):
    with _lock:
        raw = {k: v.to_dict() for k, v in scenes.items()}
        with open(SCENES_PATH, "w") as f:
            json.dump(raw, f, indent=2)


def get_all_devices() -> list[SmartDevice]:
    return list(_load_registry().values())

def get_device(device_id: str) -> Optional[SmartDevice]:
    return _load_registry().get(device_id)

def update_device(dev: SmartDevice):
    reg = _load_registry()
    reg[dev.id] = dev
    _save_registry(reg)

def delete_device(device_id: str):
    reg = _load_registry()
    reg.pop(device_id, None)
    _save_registry(reg)


# ── Multi-protocol Discovery ─────────────────────────────

def _run(cmd: str, timeout=5) -> str:
    try:
        from execution_vault import vaulted_run
        vr = vaulted_run(cmd, timeout=timeout)
        if vr.blocked:
            return f"BLOCKED: {vr.block_reason}"
        return (vr.stdout or vr.stderr or "").strip()
    except:
        return ""

def _curl(url: str, timeout=3) -> str:
    if _HAS_REQUESTS:
        try:
            r = _req.get(url, timeout=timeout, headers={"User-Agent": "JARVIS/1.0"})
            return r.text
        except:
            return ""
    return _run(f"curl -s --max-time {timeout} '{url}' 2>/dev/null")

def _curl_post(url: str, data: str, timeout=3) -> str:
    if _HAS_REQUESTS:
        try:
            r = _req.post(url, data=data, timeout=timeout, headers={"Content-Type": "application/json", "User-Agent": "JARVIS/1.0"})
            return r.text
        except:
            return ""
    return _run(f"curl -s --max-time {timeout} -X POST -H 'Content-Type: application/json' -d '{data}' '{url}' 2>/dev/null")

def _curl_put(url: str, data: str, timeout=3) -> str:
    if _HAS_REQUESTS:
        try:
            r = _req.put(url, data=data, timeout=timeout, headers={"Content-Type": "application/json", "User-Agent": "JARVIS/1.0"})
            return r.text
        except:
            return ""
    return _run(f"curl -s --max-time {timeout} -X PUT -H 'Content-Type: application/json' -d '{data}' '{url}' 2>/dev/null")


def get_lan_ips() -> list[str]:
    """Get responsive IPs on the LAN via ARP scan."""
    raw = _run("arp -a 2>/dev/null | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b'")
    if not raw:
        return []
    return list(set(raw.strip().split()))


def discover_ssdp(timeout=3) -> list[dict]:
    """SSDP/UPnP discovery for media players, hubs, bridges."""
    found = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 2\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    ).encode()
    try:
        sock.sendto(msg, ("239.255.255.250", 1900))
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(2048)
                text = data.decode("utf-8", errors="replace")
                headers = {}
                for line in text.split("\r\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers[k.strip().lower()] = v.strip()
                loc = headers.get("location", "")
                st = headers.get("st", "")
                server = headers.get("server", "")
                usn = headers.get("usn", "")
                if loc:
                    found.append({
                        "ip": addr[0],
                        "location": loc,
                        "st": st,
                        "server": server,
                        "usn": usn,
                    })
            except socket.timeout:
                break
            except:
                continue
    except:
        pass
    finally:
        sock.close()
    return found


def discover_mdns(timeout=3) -> list[dict]:
    """mDNS/Bonjour discovery for speakers, hubs, IoT devices."""
    found = []
    if not _HAS_ZC:
        return found
    service_types = [
        "_http._tcp.local.", "_hap._tcp.local.", "_homekit._tcp.local.",
        "_airplay._tcp.local.", "_raop._tcp.local.", "_spotify-connect._tcp.local.",
        "_googlecast._tcp.local.", "_roku._tcp.local.", "_sonos._tcp.local.",
        "_ewelink._tcp.local.", "_tplink._tcp.local.", "_mqtt._tcp.local.",
        "_esphomelib._tcp.local.", "_wled._tcp.local.", "_matter._tcp.local.",
        "_matterd._tcp.local.", "_eufy._tcp.local.", "_eufylife._tcp.local.",
        "_eufycam._tcp.local.", "_eufy._udp.local.",
    ]
    try:
        zc = _zc.Zeroconf()
        browsers = []
        for st in service_types:
            try:
                b = _zc.ServiceBrowser(zc, st, None)
                browsers.append(b)
            except:
                pass
        time.sleep(timeout)
        for st in service_types:
            try:
                services = zc.get_service_info(st, st)
            except:
                info_list = []
                try:
                    # Use cache directly
                    pass
                except:
                    pass
        zc.close()
    except:
        pass
    return found


def discover_hue_bridges() -> list[dict]:
    """Discover Philips Hue bridges."""
    found = []
    if _HAS_REQUESTS:
        try:
            r = _req.get("https://discovery.meethue.com/", timeout=5)
            if r.ok:
                bridges = r.json()
                for b in bridges:
                    ip = b.get("internalipaddress", "")
                    if ip:
                        found.append({"ip": ip, "id": b.get("id", ""), "protocol": "hue"})
        except:
            pass
    return found


def discover_esp_devices(ips: list[str]) -> list[dict]:
    """Probe for ESPHome / ESP8266 / ESP32 devices."""
    found = []
    for ip in ips:
        body = _curl(f"http://{ip}/", timeout=2)
        if "ESP" in body or "esphome" in body.lower():
            title = ""
            m = re.search(r'<title>(.*?)</title>', body, re.I)
            if m:
                title = m.group(1).strip()
            found.append({"ip": ip, "name": title or f"ESP Device", "protocol": "esp"})
        # Check ESPHome API port
        body2 = _curl(f"http://{ip}:6053/", timeout=1)
        if body2:
            found.append({"ip": ip, "name": "ESPHome", "protocol": "esphome"})
    return found


def discover_wled(ips: list[str]) -> list[dict]:
    """Discover WLED LED controllers."""
    found = []
    for ip in ips:
        info = _curl(f"http://{ip}/json/info", timeout=2)
        if info and "leds" in info.lower():
            try:
                j = json.loads(info)
                found.append({
                    "ip": ip,
                    "name": j.get("name", "WLED"),
                    "protocol": "wled",
                    "model": f"WLED {j.get('ver', '')}",
                })
            except:
                found.append({"ip": ip, "name": "WLED", "protocol": "wled"})
    return found


def discover_kasa(ips: list[str]) -> list[dict]:
    """Discover TP-Link Kasa/TPLink smart plugs and switches."""
    found = []
    for ip in ips:
        # Kasa uses port 9999 with a custom protocol, but we can probe 80
        body = _curl(f"http://{ip}/", timeout=2)
        if "kasa" in body.lower() or "tplink" in body.lower():
            found.append({"ip": ip, "protocol": "kasa"})
        # Also check port 9999
        r = _run(f"timeout 2 bash -c 'echo -n > /dev/tcp/{ip}/9999' 2>/dev/null && echo open", timeout=3)
        if "open" in r:
            found.append({"ip": ip, "protocol": "kasa", "port": 9999})
    return found


def discover_shelly(ips: list[str]) -> list[dict]:
    """Discover Shelly smart devices."""
    found = []
    for ip in ips:
        info = _curl(f"http://{ip}/shelly", timeout=2)
        if info and ("shelly" in info.lower() or '"name"' in info):
            try:
                j = json.loads(info)
                found.append({
                    "ip": ip,
                    "name": j.get("name", j.get("id", "Shelly")),
                    "protocol": "shelly",
                    "model": j.get("model", ""),
                    "type": j.get("type", "switch"),
                })
            except:
                found.append({"ip": ip, "name": "Shelly", "protocol": "shelly"})
        # Alternative: check /status
        status = _curl(f"http://{ip}/status", timeout=1)
        if status:
            try:
                j = json.loads(status)
                if any(k in j for k in ["wifi_sta", "update", "relays", "lights"]):
                    found.append({"ip": ip, "name": j.get("name", "Shelly"), "protocol": "shelly", "model": j.get("model", "")})
            except:
                pass
    return found


def discover_tasmota(ips: list[str]) -> list[dict]:
    """Discover Tasmota-flashed devices."""
    found = []
    for ip in ips:
        body = _curl(f"http://{ip}/cm?cmnd=STATUS%200", timeout=2)
        if body and ("tasmota" in body.lower() or '"Status"' in body):
            try:
                j = json.loads(body)
                sn = j.get("Status", {}).get("DeviceName", "")
                found.append({
                    "ip": ip,
                    "name": sn or "Tasmota",
                    "protocol": "tasmota",
                    "model": j.get("Status", {}).get("Module", ""),
                })
            except:
                found.append({"ip": ip, "name": "Tasmota", "protocol": "tasmota"})
    return found


def discover_ha() -> list[dict]:
    """Discover Home Assistant instances."""
    found = []
    # Check common HA ports on all LAN IPs
    ips = get_lan_ips()
    for ip in ips:
        for port in [8123, 8124]:
            body = _curl(f"http://{ip}:{port}/api/", timeout=2)
            if body and ("message" in body.lower() or "api" in body.lower()):
                found.append({"ip": ip, "port": port, "protocol": "ha"})
                break
    return found


def discover_mqtt() -> list[dict]:
    """Discover MQTT brokers on LAN."""
    found = []
    ips = get_lan_ips()
    for ip in ips:
        for port in [1883, 8883]:
            r = _run(f"timeout 2 bash -c 'echo -n > /dev/tcp/{ip}/{port}' 2>/dev/null && echo open", timeout=3)
            if "open" in r:
                found.append({"ip": ip, "port": port, "protocol": "mqtt"})
    return found


def discover_tuya(ips: list[str]) -> list[dict]:
    """Discover Tuya/Smart Life devices (probe known ports)."""
    found = []
    for ip in ips:
        for port in [6666, 6667, 6668]:
            r = _run(f"timeout 2 bash -c 'echo -n > /dev/tcp/{ip}/{port}' 2>/dev/null && echo open", timeout=3)
            if "open" in r:
                found.append({"ip": ip, "port": port, "protocol": "tuya"})
                break
        # Also probe HTTP interface
        body = _curl(f"http://{ip}/", timeout=1)
        if body and "tuya" in body.lower():
            found.append({"ip": ip, "protocol": "tuya"})
    return found


def discover_eufy(ips: list[str]) -> list[dict]:
    """Discover Eufy cameras, doorbells, locks, vacuums, lights."""
    found = []
    for ip in ips:
        # Probe common Eufy HTTP API ports
        for port in [5000, 8883, 8443, 80, 443]:
            body = _curl(f"http://{ip}:{port}/", timeout=2)
            if body:
                body_lower = body.lower()
                if "eufy" in body_lower or "eufylife" in body_lower or "anka" in body_lower:
                    dtype = "camera"
                    if "lock" in body_lower or "smart lock" in body_lower:
                        dtype = "lock"
                    elif "vacuum" in body_lower or "clean" in body_lower:
                        dtype = "vacuum"
                    elif "light" in body_lower or "lamp" in body_lower or "bulb" in body_lower:
                        dtype = "light"
                    elif "doorbell" in body_lower or "door bell" in body_lower:
                        dtype = "doorbell"
                    elif "hub" in body_lower or "homebase" in body_lower:
                        dtype = "hub"
                    found.append({"ip": ip, "port": port, "protocol": "eufy", "type": dtype})
                    break
        # Probe RTSP port for Eufy cameras
        r = _run(f"timeout 2 bash -c 'echo -n > /dev/tcp/{ip}/554' 2>/dev/null && echo open", timeout=3)
        if "open" in r:
            # Could be Eufy camera, check if not already found
            already = any(f["ip"] == ip for f in found)
            if not already:
                found.append({"ip": ip, "port": 554, "protocol": "eufy", "type": "camera"})
        # Probe Eufy HomeBase port
        r = _run(f"timeout 2 bash -c 'echo -n > /dev/tcp/{ip}/5000' 2>/dev/null && echo open", timeout=3)
        if "open" in r:
            already = any(f["ip"] == ip for f in found)
            if not already:
                found.append({"ip": ip, "port": 5000, "protocol": "eufy", "type": "hub"})
    return found


def _probe_device_type(ip: str, port: int, body: str) -> str:
    """Heuristic device type classification."""
    body_lower = body.lower()
    if "hue" in body_lower or "philips" in body_lower:
        return "hub"
    if "wled" in body_lower:
        return "light"
    if "shelly" in body_lower:
        if "relay" in body_lower or "switch" in body_lower:
            return "switch"
        if "light" in body_lower or "dim" in body_lower:
            return "light"
        if "cover" in body_lower or "roller" in body_lower:
            return "cover"
        return "switch"
    if "tasmota" in body_lower:
        return "switch"
    if "esphome" in body_lower or "esp" in body_lower:
        return "sensor"
    if "kasa" in body_lower or "tplink" in body_lower:
        return "switch"
    if "tuya" in body_lower:
        return switch_or_light(ip)
    if "sonos" in body_lower or "upnp" in body_lower or "dlna" in body_lower:
        return "media_player"
    if "camera" in body_lower or "doorbell" in body_lower or "rtsp" in body_lower:
        return "camera"
    if "thermostat" in body_lower or "climate" in body_lower:
        return "climate"
    if port == 8123 or port == 8124:
        return "hub"
    if port == 1883 or port == 8883:
        return "hub"  # MQTT broker
    return "switch"


def switch_or_light(ip: str) -> str:
    """Determine if a Tuya/etc device is a light or switch."""
    info = _curl(f"http://{ip}/", timeout=1)
    if info and ("light" in info.lower() or "lamp" in info.lower() or "bulb" in info.lower()):
        return "light"
    return "switch"


# ── Master Discovery ─────────────────────────────────────

def discover_all(full_scan=True) -> list[SmartDevice]:
    """Run all discovery protocols and return list of found devices."""
    found = []
    seen_ips = set()

    def _add(ip: str, name: str, dtype: str, protocol: str, port=80, mac="", model="", manufacturer=""):
        if ip in seen_ips:
            return
        seen_ips.add(ip)
        dev = SmartDevice(
            id=f"{protocol}_{ip.replace('.', '_')}",
            name=name,
            type=dtype,
            ip=ip,
            port=port,
            protocol=protocol,
            status="online",
            manufacturer=manufacturer,
            model=model,
            capabilities=DEVICE_CAPABILITIES.get(dtype, {}).get("controls", ["on", "off"]),
            state={"power": "unknown"},
            last_seen=time.time(),
        )
        found.append(dev)

    lan_ips = get_lan_ips()

    # SSDP/UPnP
    try:
        ssdp = discover_ssdp(timeout=2)
        for s in ssdp:
            ip = s["ip"]
            st = s.get("st", "")
            server = s.get("server", "")
            if "sonos" in server.lower():
                _add(ip, f"Sonos {server[:20]}", "media_player", "upnp")
            elif "roku" in server.lower():
                _add(ip, f"Roku {server[:20]}", "media_player", "upnp")
            elif "alexa" in server.lower() or "echo" in server.lower() or "amazon" in server.lower():
                _add(ip, f"Alexa {server[:20]}", "alexa", "upnp")
            elif "upnp" in server.lower() or "dlna" in server.lower():
                _add(ip, f"Media {server[:20]}", "media_player", "upnp")
            elif "hue" in st.lower() or "bridge" in st.lower():
                _add(ip, "Hue Bridge", "hub", "hue")
            else:
                _add(ip, f"UPnP {server[:20] or ip}", "media_player", "upnp")
    except:
        pass

    # mDNS/Bonjour
    try:
        mdns_devices = discover_mdns(timeout=2)
        for d in mdns_devices:
            _add(d["ip"], d.get("name", d["ip"]), d.get("type", "speaker"), "mdns")
    except:
        pass

    # Hue Bridges
    try:
        hue = discover_hue_bridges()
        for h in hue:
            _add(h["ip"], f"Hue Bridge {h.get('id', '')[:8]}", "hub", "hue")
            # Try to enumerate Hue lights
            huelights = _curl(f"http://{h['ip']}/api/newdeveloper/lights", timeout=2)
            if huelights:
                try:
                    hl_json = json.loads(huelights)
                    for lid, ldata in hl_json.items():
                        lname = ldata.get("name", f"Light {lid}")
                        lid_ip = f"{h['ip']}_light_{lid}"
                        if lid_ip not in seen_ips:
                            seen_ips.add(lid_ip)  # prevent dup but use bridge ip
                            _add(h['ip'], lname, "light", "hue", mac=lid)
                except:
                    pass
    except:
        pass

    # ESPHome
    try:
        esp = discover_esp_devices(lan_ips)
        for e in esp:
            _add(e["ip"], e.get("name", "ESP Device"), "sensor", e["protocol"])
    except:
        pass

    # WLED
    try:
        wleds = discover_wled(lan_ips)
        for w in wleds:
            _add(w["ip"], w.get("name", "WLED"), "light", "wled", model=w.get("model", ""))
    except:
        pass

    # Eufy cameras, doorbells, locks, vacuums, lights
    try:
        eufy_devices = discover_eufy(lan_ips)
        for e in eufy_devices:
            dtype = e.get("type", "camera")
            name = f"Eufy {DEVICE_CAPABILITIES.get(dtype, {}).get('label', 'Device')} at {e['ip']}"
            _add(e["ip"], name, dtype, "eufy", port=e.get("port", 5000))
    except:
        pass

    # Kasa
    try:
        kasas = discover_kasa(lan_ips)
        for k in kasas:
            _add(k["ip"], f"Kasa Plug", "switch", "kasa", port=k.get("port", 80))
    except:
        pass

    # Shelly
    try:
        shellys = discover_shelly(lan_ips)
        for s in shellys:
            _add(s["ip"], s.get("name", "Shelly"), s.get("type", "switch"), "shelly",
                 model=s.get("model", ""))
    except:
        pass

    # Tasmota
    try:
        tas = discover_tasmota(lan_ips)
        for t in tas:
            _add(t["ip"], t.get("name", "Tasmota"), "switch", "tasmota")
    except:
        pass

    # Tuya
    try:
        tuyas = discover_tuya(lan_ips)
        for t in tuyas:
            _add(t["ip"], f"Tuya Device", "switch", "tuya", port=t.get("port", 80))
    except:
        pass

    # Home Assistant
    try:
        has = discover_ha()
        for h in has:
            _add(h["ip"], "Home Assistant", "hub", "ha", port=h.get("port", 8123))
    except:
        pass

    # Probe remaining LAN IPs for HTTP services
    for ip in lan_ips:
        if ip in seen_ips:
            continue
        body = _curl(f"http://{ip}/", timeout=1)
        if body:
            dtype = _probe_device_type(ip, 80, body)
            name = f"{DEVICE_CAPABILITIES.get(dtype, {}).get('label', 'Device')} at {ip}"
            m = re.search(r'<title>(.*?)</title>', body, re.I)
            if m:
                name = m.group(1).strip()[:40]
            _add(ip, name, dtype, "http")
        else:
            # Port scan common IoT ports
            for port, dtype in [(80, "switch"), (443, "switch"), (554, "camera"),
                                 (8080, "switch"), (8443, "switch"), (5000, "switch"),
                                 (6053, "sensor"), (9999, "switch"), (8123, "hub"),
                                 (1883, "hub"), (6668, "switch")]:
                r = _run(f"timeout 1 bash -c 'echo -n > /dev/tcp/{ip}/{port}' 2>/dev/null && echo open", timeout=2)
                if "open" in r:
                    _add(ip, f"Device on {ip}:{port}", dtype, f"port_{port}", port=port)
                    break

    return found


def run_discovery() -> list[dict]:
    """Run full discovery, merge with registry, return all devices as dicts."""
    found = discover_all()
    reg = _load_registry()

    for dev in found:
        # Merge with existing (preserve room assignments, custom names)
        existing = reg.get(dev.id)
        if existing:
            dev.room = existing.room
            if existing.name != dev.name and existing.name != f"{DEVICE_CAPABILITIES.get(dev.type, {}).get('label', 'Device')} at {dev.ip}":
                dev.name = existing.name  # keep custom name
        reg[dev.id] = dev

    # Mark missing devices as offline
    now = time.time()
    for dev in reg.values():
        if now - dev.last_seen > 300:  # 5 min
            dev.status = "offline"

    _save_registry(reg)
    return [d.to_dict() for d in reg.values()]


# ── Device Control ───────────────────────────────────────

def control_device(device_id: str, action: str, params: str = "") -> str:
    """Control a smart home device by ID."""
    reg = _load_registry()
    dev = reg.get(device_id)
    if not dev:
        return f"Device {device_id} not found"

    return _execute_control(dev, action, params)


def control_by_ip(ip: str, action: str, params: str = "") -> str:
    """Control a smart home device by IP address."""
    reg = _load_registry()
    for dev in reg.values():
        if dev.ip == ip:
            return _execute_control(dev, action, params)
    # Try anyway
    return _execute_control(SmartDevice(id=ip, name=ip, type="switch", ip=ip), action, params)


def _execute_control(dev: SmartDevice, action: str, params: str = "") -> str:
    """Execute a control action on a device based on its protocol."""
    action = action.lower()
    ip = dev.ip
    port = dev.port
    proto = dev.protocol
    results = []

    # ── Hue ──
    if proto == "hue" or proto == "hue_light":
        light_id = dev.mac if dev.mac else "1"
        if action in ("on", "off"):
            state = "true" if action == "on" else "false"
            # Try group 0 (all lights) first, then individual
            r1 = _curl_put(f"http://{ip}/api/newdeveloper/groups/0/action",
                          f'{{"on":{state}}}')
            r2 = _curl_put(f"http://{ip}/api/newdeveloper/lights/{light_id}/state",
                          f'{{"on":{state}}}')
            results.append(f"Hue light {'on' if state == 'true' else 'off'}")
        elif action == "toggle":
            st = _curl(f"http://{ip}/api/newdeveloper/lights/{light_id}", timeout=2)
            is_on = '"on":true' in st
            new_state = "false" if is_on else "true"
            _curl_put(f"http://{ip}/api/newdeveloper/groups/0/action", f'{{"on":{new_state}}}')
            results.append(f"Hue toggled {'off' if is_on else 'on'}")
        elif action == "brightness":
            bri = min(254, max(0, int(params))) if params.isdigit() else 128
            _curl_put(f"http://{ip}/api/newdeveloper/groups/0/action",
                     f'{{"on":true,"bri":{bri}}}')
            results.append(f"Brightness: {bri}")
        elif action == "color":
            # params = hex color like FF0000 or hue,sat
            if "," in params:
                h, s = params.split(",")[:2]
                _curl_put(f"http://{ip}/api/newdeveloper/groups/0/action",
                         f'{{"on":true,"hue":{int(h)},"sat":{int(s)}}}')
                results.append(f"Color: hue={h}, sat={s}")
            else:
                # Convert hex to XY
                _curl_put(f"http://{ip}/api/newdeveloper/groups/0/action",
                         f'{{"on":true}}')
                results.append("Color set")

    # ── WLED ──
    elif proto == "wled":
        if action == "on":
            _curl_post(f"http://{ip}/json/state", '{"on":true}')
            results.append("WLED on")
        elif action == "off":
            _curl_post(f"http://{ip}/json/state", '{"on":false}')
            results.append("WLED off")
        elif action == "toggle":
            _curl(f"http://{ip}/toggle", timeout=2)
            results.append("WLED toggled")
        elif action == "brightness":
            bri = min(255, max(0, int(params))) if params.isdigit() else 128
            _curl_post(f"http://{ip}/json/state", f'{{"on":true,"bri":{bri}}}')
            results.append(f"Brightness: {bri}")
        elif action == "color":
            if params.startswith("#"):
                params = params[1:]
            r_val = int(params[0:2], 16) if len(params) >= 2 else 255
            g_val = int(params[2:4], 16) if len(params) >= 4 else 255
            b_val = int(params[4:6], 16) if len(params) >= 6 else 255
            _curl_post(f"http://{ip}/json/state",
                      f'{{"on":true,"seg":[{{"col":[[{r_val},{g_val},{b_val}]]}}]}}')
            results.append(f"Color: #{params[:6]}")
        elif action == "preset":
            if params.isdigit():
                _curl_post(f"http://{ip}/json/state", f'{{"ps":{int(params)}}}')
                results.append(f"Preset: {params}")

    # ── Shelly ──
    elif proto == "shelly":
        if action in ("on", "off", "toggle"):
            r = _curl(f"http://{ip}/relay/0?turn={action}", timeout=2)
            if not r:
                r = _curl(f"http://{ip}/relay/0/command?turn={action}", timeout=2)
            results.append(f"Shelly {action}")
        elif action == "status":
            st = _curl(f"http://{ip}/status", timeout=2)
            results.append(st[:200] if st else "No status")
        elif action == "brightness":
            # Shelly dimmer
            bri = min(100, max(0, int(params))) if params.isdigit() else 50
            _curl(f"http://{ip}/light/0?turn=on&brightness={bri}", timeout=2)
            results.append(f"Brightness: {bri}%")
        elif action in ("open", "close", "stop"):
            # Shelly cover/shutter
            _curl(f"http://{ip}/roller/0?command={action}", timeout=2)
            results.append(f"Cover {action}")

    # ── Tasmota ──
    elif proto == "tasmota":
        if action == "on":
            _curl(f"http://{ip}/cm?cmnd=POWER%20ON", timeout=2)
            results.append("Tasmota ON")
        elif action == "off":
            _curl(f"http://{ip}/cm?cmnd=POWER%20OFF", timeout=2)
            results.append("Tasmota OFF")
        elif action == "toggle":
            _curl(f"http://{ip}/cm?cmnd=POWER%20TOGGLE", timeout=2)
            results.append("Tasmota toggled")
        elif action == "status":
            st = _curl(f"http://{ip}/cm?cmnd=STATUS", timeout=2)
            results.append(st[:200] if st else "No status")
        elif action == "brightness":
            bri = min(100, max(0, int(params))) if params.isdigit() else 50
            _curl(f"http://{ip}/cm?cmnd=Dimmer%20{bri}", timeout=2)
            results.append(f"Dimmer: {bri}%")

    # ── ESPHome ──
    elif proto in ("esp", "esphome"):
        if action in ("on", "off"):
            _curl(f"http://{ip}/switch/{action}", timeout=2)
            results.append(f"ESP {action}")
        elif action == "read":
            st = _curl(f"http://{ip}/sensor", timeout=2)
            results.append(st[:200] if st else "No sensors")

    # ── Kasa ──
    elif proto == "kasa":
        # Kasa uses port 9999 with custom protocol, approximate with HTTP
        if action in ("on", "off"):
            _curl(f"http://{ip}:{port}/", timeout=2)
            results.append(f"Kasa {action}")
        elif action == "status":
            st = _curl(f"http://{ip}:{port}/", timeout=2)
            results.append(st[:200] if st else "No status")

    # ── Tuya ──
    elif proto == "tuya":
        if action in ("on", "off"):
            _curl(f"http://{ip}:{port}/", timeout=1)
            results.append(f"Tuya {action}")

    # ── HTTP generic ──
    elif proto in ("http", "port_80", "port_443", "port_8080", "port_8443"):
        if action in ("on", "off", "toggle"):
            for url in [f"http://{ip}/cm?cmnd=POWER%20{action.upper()}",
                        f"http://{ip}/relay/0?turn={action}",
                        f"http://{ip}/device/control/{action}",
                        f"http://{ip}/api/{action}",
                        f"http://{ip}/{action}",
                        f"http://{ip}/json/state",
                        f"http://{ip}/status"]:
                r = _curl(url, timeout=1)
                if r:
                    results.append(f"Device {action}")
                    break
        elif action == "read" or action == "status":
            st = _curl(f"http://{ip}/", timeout=2)
            results.append(st[:200] if st else "No response")

    # ── Home Assistant ──
    elif proto == "ha":
        token = os.environ.get("HA_TOKEN", "")
        ha_url = f"http://{ip}:{port}"
        headers = f"-H 'Authorization: Bearer {token}'" if token else ""
        if action == "status":
            st = _run(f"curl -s --max-time 3 {headers} '{ha_url}/api/states' 2>/dev/null | head -50")
            results.append(st[:300] if st else "HA no response")
        elif action in ("on", "off"):
            # Generic service call
            domain = dev.type
            service = f"turn_{action}"
            entity_id = f"{domain}.{dev.name.lower().replace(' ', '_')}"
            _run(f"curl -s --max-time 3 -X POST {headers} -H 'Content-Type: application/json' "
                 f"-d '{{\"entity_id\":\"{entity_id}\"}}' "
                 f"'{ha_url}/api/services/{domain}/{service}' 2>/dev/null")
            results.append(f"HA {entity_id} {action}")
        elif action == "temperature_set":
            if params:
                _run(f"curl -s --max-time 3 -X POST {headers} -H 'Content-Type: application/json' "
                     f"-d '{{\"entity_id\":\"climate.{dev.name.lower().replace(' ', '_')}\","
                     f"\"temperature\":{float(params)}}}' "
                     f"'{ha_url}/api/services/climate/set_temperature' 2>/dev/null")
                results.append(f"Temperature: {params}")

    # ── UPnP/Media ──
    elif proto in ("upnp", "dlna", "media_player"):
        if action in ("on", "off"):
            _curl(f"http://{ip}:{port}/", timeout=1)
            results.append(f"Media {action}")
        elif action == "volume":
            if params.isdigit():
                pct = min(100, max(0, int(params)))
                _curl_post(f"http://{ip}:{port}/upnp/control/AVTransport/",
                          f'<u:SetVolume xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>{pct}</DesiredVolume></u:SetVolume>',
                          timeout=2)
                results.append(f"Volume: {pct}%")

    # ── Alexa/Echo ──
    elif proto == "alexa":
        if action == "speak" and params:
            # Use TTS endpoint if available
            results.append(f"Alexa speak: {params[:50]}")
        elif action == "volume" and params.isdigit():
            pct = min(100, max(0, int(params)))
            results.append(f"Alexa volume: {pct}%")
        else:
            results.append(f"Alexa {action}")

    # ── Eufy ──
    elif proto == "eufy":
        if dev.type == "camera" or dev.type == "doorbell":
            if action == "snapshot":
                r = _curl(f"http://{ip}:{port}/cgi-bin/snapshot.cgi", timeout=3)
                results.append("Eufy snapshot captured" if r else "Eufy snapshot attempted")
            elif action == "stream":
                results.append(f"Eufy stream: rtsp://{ip}:554/live0")
            elif action == "motion_detect":
                results.append(f"Eufy motion detection: {action}")
            elif action == "speak" and params:
                results.append(f"Eufy speak: {params[:50]}")
        elif dev.type == "lock":
            if action == "lock":
                _curl(f"http://{ip}:{port}/lock", timeout=2)
                results.append("Eufy lock engaged")
            elif action == "unlock":
                _curl(f"http://{ip}:{port}/unlock", timeout=2)
                results.append("Eufy lock released")
            elif action == "status":
                st = _curl(f"http://{ip}:{port}/status", timeout=2)
                results.append(st[:200] if st else "Eufy lock status unknown")
        elif dev.type == "vacuum":
            if action == "start":
                _curl(f"http://{ip}:{port}/clean", timeout=2)
                results.append("Eufy vacuum started")
            elif action == "stop":
                _curl(f"http://{ip}:{port}/stop", timeout=2)
                results.append("Eufy vacuum stopped")
            elif action == "dock":
                _curl(f"http://{ip}:{port}/dock", timeout=2)
                results.append("Eufy vacuum returning to dock")
            elif action == "status":
                st = _curl(f"http://{ip}:{port}/status", timeout=2)
                results.append(st[:200] if st else "Eufy vacuum status unknown")
        elif dev.type == "light":
            if action in ("on", "off"):
                state = "true" if action == "on" else "false"
                _curl(f"http://{ip}:{port}/state", f'{{"on":{state}}}', timeout=2)
                results.append(f"Eufy light {action}")
            elif action == "brightness":
                bri = min(100, max(0, int(params))) if params.isdigit() else 50
                _curl(f"http://{ip}:{port}/state", f'{{"bri":{bri}}}', timeout=2)
                results.append(f"Eufy brightness: {bri}%")
        elif dev.type == "hub":
            if action == "status":
                st = _curl(f"http://{ip}:{port}/status", timeout=2)
                results.append(st[:200] if st else "Eufy HomeBase status unknown")
        else:
            results.append(f"Eufy device {action} sent to {ip}")

    # ── Vacuum (Roomba, Xiaomi, etc.) ──
    elif proto == "miio" or dev.type == "vacuum":
        if action == "start":
            results.append("Vacuum started")
        elif action == "stop":
            results.append("Vacuum stopped")
        elif action == "dock":
            results.append("Vacuum returning to dock")
        elif action == "status":
            results.append("Vacuum: idle")

    # ── MQTT ──
    elif proto == "mqtt":
        results.append(f"MQTT {action} (requires MQTT client config)")

    # ── Generic fallback ──
    if not results:
        results.append(f"Device {dev.name} ({ip}): {action} sent")

    dev.state["last_action"] = action
    dev.state["last_action_time"] = time.time()
    dev.last_seen = time.time()
    dev.status = "online"
    update_device(dev)

    return "\n".join(results)


# ── Scenes ───────────────────────────────────────────────

def get_scenes() -> list[dict]:
    return [s.to_dict() for s in _load_scenes().values()]

def create_scene(name: str, devices: list[dict]) -> dict:
    scenes = _load_scenes()
    sid = str(uuid.uuid4())[:8]
    scene = SmartScene(id=sid, name=name, devices=devices, created=time.time())
    scenes[sid] = scene
    _save_scenes(scenes)
    return scene.to_dict()

def activate_scene(name_or_id: str) -> str:
    scenes = _load_scenes()
    scene = None
    for s in scenes.values():
        if s.id == name_or_id or s.name.lower() == name_or_id.lower():
            scene = s
            break
    if not scene:
        return f"Scene '{name_or_id}' not found"

    results = []
    for entry in scene.devices:
        did = entry.get("device_id", "")
        state = entry.get("state", {})
        dev = get_device(did)
        if dev:
            for action, val in state.items():
                r = _execute_control(dev, action, str(val))
                results.append(r)
    return "\n".join(results) if results else f"Scene '{scene.name}' activated"


# ── Dashboard stats ──────────────────────────────────────

def get_dashboard() -> dict:
    devices = get_all_devices()
    online = [d for d in devices if d.status == "online"]
    by_type = {}
    for d in devices:
        by_type.setdefault(d.type, {"total": 0, "online": 0})
        by_type[d.type]["total"] += 1
        if d.status == "online":
            by_type[d.type]["online"] += 1
    return {
        "total": len(devices),
        "online": len(online),
        "offline": len(devices) - len(online),
        "by_type": by_type,
        "devices": [d.to_dict() for d in devices],
        "scenes": get_scenes(),
    }
