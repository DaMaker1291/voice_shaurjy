"""Probe LG TV (192.168.8.140) for UPnP/SSDP + webOS control surface."""
import sys, os, socket, re, json, urllib.request, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TV = "192.168.8.140"

def ssdp_search():
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    ).encode()
    results = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.settimeout(3)
    s.sendto(msg, ("239.255.255.250", 1900))
    try:
        while True:
            data, addr = s.recvfrom(2048)
            if addr[0] == TV:
                results.append(data.decode(errors="ignore"))
    except socket.timeout:
        pass
    s.close()
    return results

print("=== SSDP responses from LG TV ===")
responses = ssdp_search()
for r in responses:
    for line in r.splitlines():
        if line.lower().startswith(("server:", "st:", "location:", "usn:")):
            print(f"  {line.strip()}")
if not responses:
    print("  (no SSDP response)")

print("\n=== webOS port 3000/3001 probe ===")
for port in (3000, 3001, 57621, 61999, 8123):
    try:
        c = socket.create_connection((TV, port), timeout=1)
        c.close()
        print(f"  port {port}: OPEN")
    except Exception:
        print(f"  port {port}: closed")

print("\n=== webOS JSON API (legacy port 3000) ===")
try:
    req = urllib.request.Request(f"http://{TV}:3000/", method="GET")
    with urllib.request.urlopen(req, timeout=3) as r:
        print("  status", r.status, "| body:", r.read(200).decode(errors="ignore")[:200])
except Exception as e:
    print("  ERR:", e)

print("\n=== ChromeCast/DIAL (port 8008) ===")
try:
    c = socket.create_connection((TV, 8008), timeout=1)
    c.close()
    print("  port 8008: OPEN -> DIAL/cast present")
    try:
        with urllib.request.urlopen(f"http://{TV}:8008/ssdp/device-desc.xml", timeout=3) as r:
            print("  ", r.read(400).decode(errors="ignore")[:400].replace("\n", " "))
    except Exception as e:
        print("  ERR:", e)
except Exception:
    print("  port 8008: closed")
