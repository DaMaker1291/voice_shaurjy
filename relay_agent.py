"""Relay agent — runs on your Windows PC, bridges cloud backend to local actions."""

import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import threading

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-second-brain-api.hf.space").rstrip("/")
POLL_INTERVAL = 2.0

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def _check_connectivity():
    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        ip = socket.gethostbyname(hostname)
        print(f"[Relay Agent] DNS OK: {hostname} → {ip}")
        return True
    except socket.gaierror:
        print(f"[Relay Agent] ⚠ DNS failed for {hostname}")
        print(f"[Relay Agent] To fix, run PowerShell AS ADMINISTRATOR and paste:")
        print(f'  Add-Content "$env:SystemRoot\\System32\\drivers\\etc\\hosts" "`n99.80.141.75 {hostname}"')
        print(f"[Relay Agent] Then restart this agent.")
        return False


def _req(url: str, data: dict = None) -> dict:
    kwargs = {"url": url, "headers": {"Content-Type": "application/json"}, "timeout": 15}
    if data:
        kwargs["data"] = json.dumps(data).encode()
        req = urllib.request.Request(**kwargs, method="POST")
    else:
        req = urllib.request.Request(url, method="GET")
        if data:
            req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _json_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _json_get(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def poll_loop():
    print(f"[Relay Agent] Connected to {HF_API}")
    print(f"[Relay Agent] Polling every {POLL_INTERVAL}s...")
    while True:
        try:
            resp = _json_get(f"{HF_API}/api/relay/pending")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                print(f"[Relay Agent] Executing: {act}")
                try:
                    from actions import execute_action
                    result = execute_action(act, params)
                    _json_post(f"{HF_API}/api/relay/result", {"relay_id": rid, "result": result, "success": True})
                    print(f"[Relay Agent] Done: {act} → {result[:80]}")
                except Exception as e:
                    _json_post(f"{HF_API}/api/relay/result", {"relay_id": rid, "result": f"Error: {e}", "success": False})
                    print(f"[Relay Agent] Failed: {act} → {e}")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[Relay Agent] HTTP {e.code}")
        except urllib.error.URLError as e:
            print(f"[Relay Agent] Connection issue: {e.reason}")
        except Exception as e:
            print(f"[Relay Agent] Error: {e}")
        time.sleep(POLL_INTERVAL)


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║    Second Brain — Windows Relay Agent       ║")
    print("╚══════════════════════════════════════════════╝")
    if not _check_connectivity():
        return
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Relay Agent] Shutting down...")


if __name__ == "__main__":
    main()
