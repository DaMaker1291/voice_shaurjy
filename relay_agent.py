"""
Relay agent — runs on your Windows PC, polls HF Space every 0.5s for actions.
Dead simple, no WebSocket, no complexity.
"""

import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-second-brain-api.hf.space").rstrip("/")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def main():
    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
        print(f"[Relay] Connected to {HF_API}")
    except socket.gaierror:
        print(f"[Relay] DNS failed for {hostname}"); return

    print("[Relay] Polling every 0.5s...")
    while True:
        try:
            resp = get(f"{HF_API}/api/relay/pending")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                print(f"[Relay] Executing: {act}")
                try:
                    from actions import execute_action
                    result = execute_action(act, params)
                    post(f"{HF_API}/api/relay/result",
                         {"relay_id": rid, "result": result, "success": True})
                    print(f"[Relay] Done: {act}")
                except Exception as e:
                    post(f"{HF_API}/api/relay/result",
                         {"relay_id": rid, "result": f"Error: {e}", "success": False})
                    print(f"[Relay] Failed: {act}")
        except Exception:
            pass
        time.sleep(0.5)


if __name__ == "__main__":
    main()
