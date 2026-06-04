"""
Relay agent — runs on your Windows PC.
Connects via WebSocket for real-time action push, falls back to HTTP polling.
"""

import json
import os
import socket
import sys
import threading
import time
import urllib.request
import urllib.error

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-second-brain-api.hf.space").rstrip("/")
WS_URL = HF_API.replace("https://", "wss://").replace("http://", "ws://") + "/ws/relay"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def _check_connectivity():
    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        ip = socket.gethostbyname(hostname)
        print(f"[Relay Agent] DNS OK: {hostname} \u2192 {ip}")
        return True
    except socket.gaierror:
        print(f"[Relay Agent] \u26a0 DNS failed for {hostname}")
        return False


def _json_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _json_get(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def ws_loop():
    import websocket

    def on_message(ws, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if data.get("type") == "ping":
            try:
                ws.send('{"type":"pong"}')
            except:
                pass
            return
        if data.get("type") != "action":
            return
        _execute_and_respond(ws, data)

    def on_error(ws, err):
        pass

    def on_close(ws, close_status, close_msg):
        time.sleep(3)

    def on_open(ws):
        print(f"[Relay Agent] WebSocket connected")

    while True:
        try:
            ws = websocket.WebSocketApp(
                WS_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever(reconnect=3, ping_interval=20, ping_timeout=10)
        except Exception as e:
            print(f"[Relay Agent] WebSocket error: {e}")
            time.sleep(3)


def http_poll_loop():
    while True:
        try:
            resp = _json_get(f"{HF_API}/api/relay/pending")
            for a in resp.get("actions", []):
                rid, act, params = a["relay_id"], a["action"], a.get("params", "")
                print(f"[Relay Agent] (HTTP) Executing: {act}")
                try:
                    from actions import execute_action
                    result = execute_action(act, params)
                    _json_post(f"{HF_API}/api/relay/result", {"relay_id": rid, "result": result, "success": True})
                    print(f"[Relay Agent] (HTTP) Done: {act}")
                except Exception as e:
                    _json_post(f"{HF_API}/api/relay/result", {"relay_id": rid, "result": f"Error: {e}", "success": False})
                    print(f"[Relay Agent] (HTTP) Failed: {act} \u2192 {e}")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[Relay Agent] (HTTP) {e.code}")
        except urllib.error.URLError as e:
            pass
        except Exception as e:
            print(f"[Relay Agent] (HTTP) Error: {e}")
        time.sleep(2)


def _execute_and_respond(ws, data):
    rid = data.get("relay_id", "")
    act = data.get("action", "")
    params = data.get("params", "")
    print(f"[Relay Agent] Executing: {act}")
    try:
        from actions import execute_action
        result = execute_action(act, params)
        ws.send(json.dumps({"type": "result", "relay_id": rid, "result": result, "success": True}))
        print(f"[Relay Agent] Done: {act} \u2192 {result[:80]}")
    except Exception as e:
        ws.send(json.dumps({"type": "result", "relay_id": rid, "result": f"Error: {e}", "success": False}))
        print(f"[Relay Agent] Failed: {act} \u2192 {e}")


def main():
    print("\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557")
    print("\u2551    Second Brain \u2014 Windows Relay Agent (WebSocket + HTTP) \u2551")
    print("\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d")
    if not _check_connectivity():
        return
    threading.Thread(target=ws_loop, daemon=True).start()
    threading.Thread(target=http_poll_loop, daemon=True).start()
    print(f"[Relay Agent] Connected to {HF_API}")
    print(f"[Relay Agent] WebSocket: {WS_URL}")
    print(f"[Relay Agent] HTTP polling active as fallback")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Relay Agent] Shutting down...")


if __name__ == "__main__":
    main()
