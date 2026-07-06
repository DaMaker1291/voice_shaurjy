#!/usr/bin/env python3
"""
Universal Device Discovery & Control for JARVIS
Scans entire WiFi network for ALL devices — no login required for most.
Handles: HTTP APIs, MQTT, UPnP, Tuya, ESPHome, WLED, Zigbee hubs, gates, locks, cameras, etc.
"""
import subprocess
import json
import socket
import time
import re
import os
import ssl
import http.client
import urllib.parse
import struct
from typing import Dict, List, Optional, Any

# ── Network Discovery ────────────────────────────────────────────────

def get_local_network():
    """Get local IP and subnet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        subnet = ".".join(ip.split(".")[:3])
        return ip, subnet
    except:
        return "192.168.0.1", "192.168.0"

def discover_all_devices() -> List[Dict]:
    """Aggressive full network scan — finds EVERY device."""
    local_ip, subnet = get_local_network()
    devices = []

    # Phase 1: ARP table (instant, shows recently seen devices)
    devices.extend(_scan_arp())

    # Phase 2: Ping sweep (fast host discovery)
    alive_hosts = _ping_sweep(subnet)
    for host in alive_hosts:
        if not any(d.get("ip") == host for d in devices):
            devices.append({"ip": host, "name": f"Device ({host})", "type": "UNKNOWN", "protocol": "ping"})

    # Phase 3: Port scan on alive hosts (identify services)
    for device in devices:
        ip = device["ip"]
        device.update(_probe_device(ip))

    # Phase 4: UPnP/SSDP discovery (finds smart TVs, Echo, Chromecast, etc.)
    devices.extend(_ssdp_discover())

    # Phase 5: MQTT broker discovery
    devices.extend(_scan_mqtt(subnet))

    # Phase 6: Check common IoT ports
    for device in devices:
        ip = device["ip"]
        if device.get("type") == "UNKNOWN":
            device.update(_probe_iot_ports(ip))

    # Deduplicate by IP
    seen = set()
    unique = []
    for d in devices:
        if d["ip"] not in seen:
            seen.add(d["ip"])
            unique.append(d)

    return unique

def _scan_arp() -> List[Dict]:
    """Parse ARP table for all devices."""
    devices = []
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
        for line in result.stdout.split("\n"):
            ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
            mac_match = re.search(r'([0-9a-fA-F]{1,2}:[0-9a-fA-F]{1,2}:[0-9a-fA-F]{1,2}:[0-9a-fA-F]{1,2}:[0-9a-fA-F]{1,2}:[0-9a-fA-F]{1,2})', line)
            if ip_match:
                ip = ip_match.group(1)
                mac = mac_match.group(1) if mac_match else ""
                name = _identify_by_mac(mac) if mac else f"Device ({ip})"
                dtype = _identify_type_by_mac(mac) if mac else "UNKNOWN"
                devices.append({"ip": ip, "name": name, "type": dtype, "mac": mac, "protocol": "arp"})
    except:
        pass
    return devices

def _ping_sweep(subnet: str) -> List[str]:
    """Fast ping sweep to find alive hosts."""
    alive = []
    # Use arp -a results first (faster)
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
        for line in result.stdout.split("\n"):
            ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
            if ip_match:
                alive.append(ip_match.group(1))
    except:
        pass

    # If few results, do a quick ping sweep
    if len(alive) < 5:
        try:
            # Parallel ping with timeout
            result = subprocess.run(
                ["bash", "-c", f"for i in $(seq 1 254); do ping -c 1 -W 1 {subnet}.$i &>/dev/null && echo {subnet}.$i & done; wait"],
                capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.split("\n"):
                line = line.strip()
                if re.match(r'\d+\.\d+\.\d+\.\d+', line) and line not in alive:
                    alive.append(line)
        except:
            pass
    return alive

def _probe_device(ip: str) -> Dict:
    """Probe a device to identify what it is."""
    info = {}

    # Check HTTP
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Try HTTPS
        try:
            conn = http.client.HTTPSConnection(ip, 443, timeout=2, context=ctx)
            conn.request("GET", "/")
            resp = conn.getresponse()
            server = resp.getheader("Server", "")
            body = resp.read(2000).decode(errors="ignore")
            info["server"] = server
            if "tapo" in server.lower() or "tp-link" in body.lower():
                info["type"] = "TAPO_PLUG"
                info["name"] = f"Tapo Plug ({ip})"
                info["protocol"] = "tapo"
            elif "chromecast" in server.lower() or "cast" in body.lower():
                info["type"] = "CHROMECAST"
                info["name"] = f"Chromecast ({ip})"
            conn.close()
        except:
            pass

        # Try HTTP
        try:
            conn = http.client.HTTPConnection(ip, 80, timeout=2)
            conn.request("GET", "/")
            resp = conn.getresponse()
            server = resp.getheader("Server", "")
            body = resp.read(2000).decode(errors="ignore")
            if not info.get("server"):
                info["server"] = server

            # ESPHome
            if "esphome" in body.lower() or "esp" in server.lower():
                info["type"] = "ESPHOME"
                info["name"] = f"ESPHome ({ip})"
                info["protocol"] = "http"
            # WLED
            elif "wled" in body.lower():
                info["type"] = "WLED"
                info["name"] = f"WLED Strip ({ip})"
                info["protocol"] = "http"
            # Tuya
            elif "tuya" in body.lower():
                info["type"] = "TUYA"
                info["name"] = f"Tuya Device ({ip})"
                info["protocol"] = "tuya"
            # Web interface (router, camera, etc.)
            elif "<html" in body.lower():
                if "router" in body.lower() or "gateway" in body.lower():
                    info["type"] = "ROUTER"
                    info["name"] = f"Router ({ip})"
                elif "camera" in body.lower() or "ipcam" in body.lower():
                    info["type"] = "CAMERA"
                    info["name"] = f"IP Camera ({ip})"
                elif "hue" in body.lower() or "philips" in body.lower():
                    info["type"] = "HUE_BRIDGE"
                    info["name"] = f"Philips Hue ({ip})"
                else:
                    info["type"] = "HTTP_DEVICE"
                    info["name"] = f"Web Device ({ip})"
                info["protocol"] = "http"
            conn.close()
        except:
            pass
    except:
        pass

    return info

def _probe_iot_ports(ip: str) -> Dict:
    """Check common IoT ports to identify device type."""
    port_map = {
        22: ("LINUX_DEVICE", "SSH Device"),
        23: ("TELNET_DEVICE", "Telnet Device"),
        80: ("HTTP_DEVICE", "HTTP Device"),
        443: ("HTTPS_DEVICE", "HTTPS Device"),
        1883: ("MQTT_BROKER", "MQTT Broker"),
        554: ("RTSP_CAMERA", "RTSP Camera"),
        8080: ("HTTP_ALT", "HTTP Device"),
        8443: ("HTTPS_ALT", "HTTPS Device"),
        9090: ("CHROMECAST", "Chromecast"),
        5000: ("UPNP_DEVICE", "UPnP Device"),
        5353: ("MDNS_DEVICE", "mDNS Device"),
        6466: ("TUYA_GATEWAY", "Tuya Gateway"),
        8888: ("HTTP_ALT2", "HTTP Device"),
        32400: ("PLEX_MEDIA", "Plex Media"),
        8200: ("UPNP_ALT", "UPnP Device"),
        1400: ("SONOS", "Sonos Speaker"),
        49152: ("UPNP_ALT2", "UPnP Device"),
    }

    for port, (dtype, name) in port_map.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return {"type": dtype, "name": f"{name} ({ip})", "port": port, "protocol": "tcp"}
        except:
            pass
    return {}

def _ssdp_discover() -> List[Dict]:
    """UPnP/SSDP multicast discovery."""
    devices = []
    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    msg = f"M-SEARCH * HTTP/1.1\r\nHOST: {SSDP_ADDR}:{SSDP_PORT}\r\nMAN: \"ssdp:discover\"\r\nMX: 3\r\nST: urn:schemas-upnp-org:device:Basic:1\r\n\r\n"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    sock.settimeout(4)

    try:
        sock.sendto(msg.encode(), (SSDP_ADDR, SSDP_PORT))
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                response = data.decode("utf-8", errors="ignore")
                ip = addr[0]
                name = _extract_ssdp_name(response)
                dtype = _identify_ssdp_type(response)
                devices.append({"ip": ip, "name": name or f"UPnP Device ({ip})", "type": dtype, "protocol": "upnp"})
            except socket.timeout:
                break
    finally:
        sock.close()
    return devices

def _scan_mqtt(subnet: str) -> List[Dict]:
    """Scan for MQTT brokers."""
    devices = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((subnet + ".1", 1883))
        sock.close()
        if result == 0:
            devices.append({"ip": subnet + ".1", "name": "MQTT Broker", "type": "MQTT_BROKER", "protocol": "mqtt"})
    except:
        pass
    return devices

# ── Device Identification ────────────────────────────────────────────

def _identify_by_mac(mac: str) -> str:
    """Identify device by MAC address OUI."""
    mac = mac.lower().replace(":", "").replace("-", "")[:6]
    oui_map = {
        "f0272d": "Amazon Echo", "f0f0a4": "Amazon Echo", "443583": "Amazon Echo",
        "ac63be": "Amazon Echo", "84d6db": "Amazon Echo", "fc65de": "Amazon Echo",
        "a002dc": "Amazon Echo", "3caa8f": "Amazon Echo", "74c246": "Amazon Echo",
        "e848b8": "Amazon Echo", "0c473d": "Amazon Echo", "8871b1": "Amazon Echo",
        "d8725a": "Amazon Echo", "e47a2c": "Amazon Echo", "fc15b4": "Amazon Echo",
        "b04e26": "TP-Link", "50c7bf": "TP-Link", "14cc20": "TP-Link",
        "6032b1": "TP-Link", "b09575": "TP-Link", "30b5c2": "TP-Link",
        "ec086b": "TP-Link", "c025e9": "TP-Link", "a42bb0": "TP-Link",
        "001a2b": "Google", "3c5ab4": "Google", "f4f5d8": "Google",
        "546009": "Google", "30fd38": "Google", "a47733": "Google",
        "dca632": "Raspberry Pi", "b827eb": "Raspberry Pi", "e45f01": "Raspberry Pi",
        "28cdc1": "Raspberry Pi", "d83add": "Raspberry Pi",
        "001132": "Sonos", "b8e937": "Sonos", "480d3e": "Sonos",
        "5caa7f": "Sonos", "9440c5": "Sonos",
        "0024d7": "Philips Hue", "ecb5fa": "Philips Hue", "001788": "Philips Hue",
        "fffe01": "Philips Hue", "cc5ef3": "Philips Hue",
    }
    for prefix, name in oui_map.items():
        if mac.startswith(prefix.lower()):
            return name
    return "Network Device"

def _identify_type_by_mac(mac: str) -> str:
    """Identify device type by MAC."""
    name = _identify_by_mac(mac)
    if "Echo" in name: return "ALEXA"
    if "TP-Link" in name: return "TAPO_PLUG"
    if "Sonos" in name: return "SONOS"
    if "Philips" in name: return "HUE_BRIDGE"
    if "Raspberry" in name: return "RASPBERRY_PI"
    if "Google" in name: return "CHROMECAST"
    return "UNKNOWN"

def _extract_ssdp_name(response: str) -> str:
    """Extract friendly name from SSDP response."""
    for line in response.split("\r\n"):
        if "friendlyname" in line.lower():
            return line.split(":", 1)[1].strip() if ":" in line else ""
        if "servername" in line.lower():
            return line.split(":", 1)[1].strip() if ":" in line else ""
    return ""

def _identify_ssdp_type(response: str) -> str:
    """Identify device type from SSDP response."""
    lower = response.lower()
    if "amazon" in lower or "echo" in lower or "alexa" in lower: return "ALEXA"
    if "chromecast" in lower or "google" in lower: return "CHROMECAST"
    if "sonos" in lower: return "SONOS"
    if "hue" in lower or "philips" in lower: return "HUE_BRIDGE"
    if "samsung" in lower: return "SAMSUNG_TV"
    if "lg" in lower: return "LG_TV"
    if "roku" in lower: return "ROKU"
    return "UPNP_DEVICE"

# ── Universal Device Control ─────────────────────────────────────────

def control_any_device(ip: str, action: str, params: str = "") -> Dict:
    """Try to control a device — tries every known protocol."""
    results = []

    # 1. Try HTTP/REST API (most IoT devices)
    result = _try_http_control(ip, action, params)
    if result: results.append(("http", result))

    # 2. Try ESPHome API
    result = _try_esphome(ip, action, params)
    if result: results.append(("esphome", result))

    # 3. Try WLED API
    result = _try_wled(ip, action, params)
    if result: results.append(("wled", result))

    # 4. Try Tuya local control
    result = _try_tuya(ip, action, params)
    if result: results.append(("tuya", result))

    # 5. Try Tapo (with common default credentials)
    result = _try_tapo_default(ip, action)
    if result: results.append(("tapo", result))

    # 6. Try UPnP control
    result = _try_upnp(ip, action)
    if result: results.append(("upnp", result))

    # 7. Try MQTT
    result = _try_mqtt(ip, action, params)
    if result: results.append(("mqtt", result))

    if results:
        return {"success": True, "protocol": results[0][0], "result": results[0][1]}

    return {"success": False, "error": "No supported protocol found", "ip": ip}

def _try_http_control(ip: str, action: str, params: str) -> Optional[str]:
    """Try controlling via HTTP REST API."""
    endpoints = {
        "on": ["/relay?state=on", "/control?state=on", "/api/relay/on", "/cm?cmnd=Power1%20ON"],
        "off": ["/relay?state=off", "/control?state=off", "/api/relay/off", "/cm?cmnd=Power1%20OFF"],
        "toggle": ["/relay?state=toggle", "/toggle", "/api/relay/toggle"],
        "status": ["/relay?state=status", "/status", "/api/status", "/cm?cmnd=Status"],
    }

    for ep in endpoints.get(action, []):
        for port in [80, 8080, 8443]:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                conn = http.client.HTTPSConnection(ip, port, timeout=3, context=ctx) if port == 443 else http.client.HTTPConnection(ip, port, timeout=3)
                conn.request("GET", ep)
                resp = conn.getresponse()
                if resp.status in (200, 201, 202, 204):
                    return resp.read().decode(errors="ignore")
                conn.close()
            except:
                try:
                    conn = http.client.HTTPConnection(ip, port, timeout=3)
                    conn.request("GET", ep)
                    resp = conn.getresponse()
                    if resp.status in (200, 201, 202, 204):
                        return resp.read().decode(errors="ignore")
                    conn.close()
                except:
                    pass
    return None

def _try_esphome(ip: str, action: str, params: str) -> Optional[str]:
    """Try ESPHome native API."""
    try:
        import http.client
        conn = http.client.HTTPConnection(ip, 80, timeout=3)
        # ESPHome web server endpoints
        endpoints = {
            "on": "/switch/relay/turn_on",
            "off": "/switch/relay/turn_off",
            "toggle": "/switch/relay/toggle",
            "status": "/switch/relay",
        }
        conn.request("GET", endpoints.get(action, "/"))
        resp = conn.getresponse()
        if resp.status in (200, 201, 202):
            return resp.read().decode(errors="ignore")
        conn.close()
    except:
        pass
    return None

def _try_wled(ip: str, action: str, params: str) -> Optional[str]:
    """Try WLED JSON API."""
    try:
        payload = None
        if action == "on":
            payload = json.dumps({"on": True})
        elif action == "off":
            payload = json.dumps({"on": False})
        elif action == "toggle":
            payload = json.dumps({"on": True, "bri": 255})
        elif action == "status":
            payload = json.dumps({"info": True})

        if payload:
            conn = http.client.HTTPConnection(ip, 80, timeout=3)
            conn.request("POST", "/json", body=payload, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            if resp.status in (200, 201, 202):
                return resp.read().decode(errors="ignore")
            conn.close()
    except:
        pass
    return None

def _try_tuya(ip: str, action: str, params: str) -> Optional[str]:
    """Try Tuya local control (unencrypted)."""
    try:
        import tinytuya
        d = tinytuya.OutletDevice("placeholder", ip, "local_key_placeholder")
        if action == "on":
            d.set_state(True)
            return "Turned on"
        elif action == "off":
            d.set_state(False)
            return "Turned off"
        elif action == "toggle":
            d.set_state(not d.status())
            return "Toggled"
    except:
        pass
    return None

def _try_tapo_default(ip: str, action: str) -> Optional[str]:
    """Try Tapo with common default credentials."""
    default_creds = [
        ("admin", "admin"),
        ("admin", "password"),
        ("admin", "1234"),
        ("admin", ""),
        ("tplink", "tplink"),
        ("", ""),
    ]

    for username, password in default_creds:
        try:
            os.environ["TAPO_USERNAME"] = username
            os.environ["TAPO_PASSWORD"] = password
            from tapo_client import TapoClient
            client = TapoClient()
            client.set_credentials(username, password)
            if action == "on":
                result = client.turn_on(ip)
            elif action == "off":
                result = client.turn_off(ip)
            elif action == "toggle":
                result = client.toggle(ip)
            else:
                result = client.get_device_info(ip)
            if result and result.get("success"):
                return f"Tapo ({username}): {result}"
        except:
            pass
    return None

def _try_upnp(ip: str, action: str) -> Optional[str]:
    """Try UPnP SOAP control."""
    try:
        # Discover UPnP service
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((ip, 49152))
        # Send UPnP description request
        req = f"GET /rootDesc.xml HTTP/1.1\r\nHost: {ip}:49152\r\n\r\n"
        sock.send(req.encode())
        resp = sock.recv(4096).decode(errors="ignore")
        sock.close()
        if "xml" in resp.lower():
            return f"UPnP device found at {ip}"
    except:
        pass
    return None

def _try_mqtt(ip: str, action: str, params: str) -> Optional[str]:
    """Try MQTT control."""
    # Most MQTT brokers need the topic — check common ones
    common_topics = [
        f"home/relay/{action}",
        f"cmnd/power",
        f"device/{action}",
        f"light/{action}",
    ]
    # This is a placeholder — real MQTT needs topic discovery
    return None


# ── CLI ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        devices = discover_all_devices()
        print(json.dumps(devices, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "control":
        ip = sys.argv[2]
        action = sys.argv[3]
        params = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
        result = control_any_device(ip, action, params)
        print(json.dumps(result, indent=2))
    else:
        print("Usage:")
        print("  universal_scanner.py scan          - Scan entire network")
        print("  universal_scanner.py control <ip> <action> [params]")
