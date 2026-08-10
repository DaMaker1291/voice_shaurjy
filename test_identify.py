"""Identify devices on the local network + check controllability."""
import sys, os, json, time, subprocess, socket, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from network_scanner import NetworkScanner, OUI_DB

def oui_lookup(mac):
    if not mac:
        return ""
    m = mac.upper().replace("-", ":").replace(".", ":")
    prefix = m[:8]
    for k, v in OUI_DB.items():
        if prefix.startswith(k):
            return v
    return "unknown-OUI"

ns = NetworkScanner(scan_interval=99999, db_path=os.path.join(os.environ.get("TEMP", "."), "jarvis_id.db"))
devs = ns.scan_arp()

local_ips = set()
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ips.add(s.getsockname()[0])
    s.close()
except: pass

def resolve(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""

def probe(ip):
    """Return dict of open ports + HTTP title if any."""
    info = {"ports": [], "title": "", "server": ""}
    ports = [(22,"ssh"),(80,"http"),(443,"https"),(445,"smb"),(554,"rtsp"),(1900,"upnp"),(8123,"ha"),(5000,"http"),(8080,"http"),(8443,"https"),(1883,"mqtt"),(5353,"mdns"),(9090,"?")]
    for port, _ in ports:
        try:
            c = socket.create_connection((ip, port), timeout=0.7)
            c.close()
            info["ports"].append(port)
        except Exception:
            pass
    if 80 in info["ports"]:
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://{ip}/", timeout=2) as r:
                body = r.read(4000).decode("utf-8", errors="ignore").lower()
                info["server"] = r.headers.get("Server", "")
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                if m: info["title"] = m.group(1).strip()[:60]
        except Exception: pass
    return info

print(f"{'IP':16} {'MAC':20} {'OUI/Mfg':22} {'hostname':30} {'ports':25} title")
for nd in sorted(devs, key=lambda d: d.ip):
    if nd.ip in local_ips:
        print(f"{nd.ip:16} {nd.mac or '-':20} {'LOCAL PC':22} {'':30} ''")
        continue
    mfg = oui_lookup(nd.mac)
    hn = resolve(nd.ip)
    p = probe(nd.ip)
    print(f"{nd.ip:16} {nd.mac or '-':20} {mfg:22} {hn or '?':30} {str(p['ports']):25} {p['title'] or p['server'] or ''}")

print("\nDone.")
