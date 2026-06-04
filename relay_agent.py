"""
Relay agent — runs on your Windows PC.
Connects to the cloud backend via WebSocket for real-time action push.
Auto-reconnects on disconnect.
"""

import json
import os
import socket
import sys
import time
import threading

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


def run():
    """Main WebSocket loop — connects, listens for actions, executes, responds."""
    import websocket

    def on_message(ws, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if data.get("type") == "ping":
            ws.send('{"type":"pong"}')
            return
        if data.get("type") != "action":
            return
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

    def on_error(ws, err):
        print(f"[Relay Agent] WebSocket error: {err}")

    def on_close(ws, close_status, close_msg):
        print(f"[Relay Agent] Disconnected. Reconnecting in 3s...")
        time.sleep(3)

    def on_open(ws):
        print(f"[Relay Agent] Connected via WebSocket to {WS_URL}")

    while True:
        try:
            ws = websocket.WebSocketApp(
                WS_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever(reconnect=3)
        except Exception as e:
            print(f"[Relay Agent] Connection failed: {e}")
            time.sleep(3)


def main():
    print("\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557")
    print("\u2551    Second Brain \u2014 Windows Relay Agent (WebSocket)     \u2551")
    print("\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d")
    if not _check_connectivity():
        return
    t = threading.Thread(target=run, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Relay Agent] Shutting down...")


if __name__ == "__main__":
    main()
