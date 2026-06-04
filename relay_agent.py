"""Relay agent — runs on your Windows PC, bridges cloud backend to local actions."""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import threading

# ── Config ─────────────────────────────────────────────────────
HF_API = "https://dgfhgjhj-second-brain-api.hf.space"
POLL_INTERVAL = 2.0  # seconds
# ────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

_agent_id = os.environ.get("COMPUTERNAME", "windows-pc")
_running = True


def _json_post(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _json_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def poll_loop():
    global _running
    print(f"[Relay Agent] Connected to {HF_API}")
    print(f"[Relay Agent] Polling every {POLL_INTERVAL}s...")
    while _running:
        try:
            resp = _json_get(f"{HF_API}/api/relay/pending")
            actions = resp.get("actions", [])
            for action in actions:
                relay_id = action["relay_id"]
                act = action["action"]
                params = action.get("params", "")
                print(f"[Relay Agent] Executing: {act} (relay_id={relay_id})")
                try:
                    from actions import execute_action
                    result = execute_action(act, params)
                    _json_post(f"{HF_API}/api/relay/result", {
                        "relay_id": relay_id,
                        "result": result,
                        "success": True,
                    })
                    print(f"[Relay Agent] Done: {act} → {result[:80]}")
                except Exception as e:
                    _json_post(f"{HF_API}/api/relay/result", {
                        "relay_id": relay_id,
                        "result": f"Error: {e}",
                        "success": False,
                    })
                    print(f"[Relay Agent] Failed: {act} → {e}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pass
            else:
                print(f"[Relay Agent] HTTP error: {e.code}")
        except Exception as e:
            print(f"[Relay Agent] Poll error: {e}")
        time.sleep(POLL_INTERVAL)


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║    Second Brain — Windows Relay Agent       ║")
    print("╚══════════════════════════════════════════════╝")
    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Relay Agent] Shutting down...")
        global _running
        _running = False


if __name__ == "__main__":
    main()
