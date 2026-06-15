"""
Relay agent — runs on any Windows PC, polls HF Space for that user's actions.
Usage: relay_agent.py --user <user_id>

SETUP ON NEW DEVICE:
  1. git clone https://github.com/DaMaker1291/voice_shaurjy.git
  2. cd voice_shaurjy
  3. pip install -r backend/requirements-render.txt
  4. python relay_agent.py --user <your_user_id>
"""

import argparse
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-my-actual-brain.hf.space").rstrip("/")


def check_backend():
    """Verify backend/ directory exists and actions.py is importable."""
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    actions_path = os.path.join(backend_dir, "actions.py")
    if not os.path.isdir(backend_dir):
        print("")
        print("=" * 60)
        print("ERROR: 'backend/' directory not found!")
        print("=" * 60)
        print("")
        print("The relay agent needs the 'backend/' folder with action modules.")
        print("You likely downloaded relay_agent.py as a single file to %TEMP%.")
        print("")
        print("CORRECT SETUP:")
        print("  1. git clone https://github.com/DaMaker1291/voice_shaurjy.git")
        print("  2. cd voice_shaurjy")
        print("  3. pip install -r backend/requirements-render.txt")
        print("  4. python relay_agent.py --user <user_id>")
        print("")
        return False
    if not os.path.isfile(actions_path):
        print(f"WARNING: {actions_path} not found. Some actions may fail.")
    else:
        sys.path.insert(0, backend_dir)
        try:
            __import__("actions")
        except ImportError as e:
            print(f"WARNING: Could not import actions module: {e}")
    return True


def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def main():
    parser = argparse.ArgumentParser(description="Second Brain Relay Agent")
    parser.add_argument("--user", default="local", help="Your user ID")
    args = parser.parse_args()
    user_id = args.user

    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
        print(f"[Relay] Connected to {HF_API} as user '{user_id}'")
    except socket.gaierror:
        print(f"[Relay] DNS failed for {hostname}"); return

    if not check_backend():
        sys.exit(1)

    print(f"[Relay] Polling every 0.5s for user '{user_id}'...")
    while True:
        try:
            resp = get(f"{HF_API}/api/relay/pending?user_id={user_id}")
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
