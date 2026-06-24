"""
Relay agent — runs on any Windows PC, polls HF Space for that user's actions.

USAGE:
  python relay_agent.py --user <user_id>

ONE-CLICK INSTALL ON NEW DEVICE (run in PowerShell):
   powershell -c "& { curl.exe -sL 'https://dgfhgjhj-my-actual-brain.hf.space/relay_agent' -o \"$env:TEMP\\relay_agent.py\"; python \"$env:TEMP\\relay_agent.py\" --user $env:USERNAME }"
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import ssl

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl._create_unverified_context()

def _urlopen(req_or_url, **kwargs):
    kwargs.setdefault("context", _SSL_CTX)
    kwargs.setdefault("timeout", 20)
    return urllib.request.urlopen(req_or_url, **kwargs)

HF_API = os.environ.get("HF_API_URL", "https://dgfhgjhj-my-actual-brain.hf.space").rstrip("/")


def ensure_deps():
    req_file = os.path.join(os.path.dirname(__file__), "backend", "requirements-render.txt")
    if os.path.isfile(req_file):
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", req_file], shell=True)


def ensure_backend():
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    if os.path.isdir(backend_dir) and os.path.isfile(os.path.join(backend_dir, "actions.py")):
        sys.path.insert(0, backend_dir)


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
    parser.add_argument("--install", action="store_true", help="Install dependencies and exit")
    args = parser.parse_args()
    user_id = args.user

    if args.install:
        ensure_deps()
        print("[Relay] Dependencies installed. Run: python relay_agent.py --user <user_id>")
        return

    from urllib.parse import urlparse
    hostname = urlparse(HF_API).hostname
    try:
        socket.gethostbyname(hostname)
        print(f"[Relay] Connected to {HF_API} as user '{user_id}'")
    except socket.gaierror:
        print(f"[Relay] DNS failed for {hostname}")
        print(f"[Relay] Check that the URL is correct: {HF_API}")
        return

    ensure_backend()
    ensure_deps()

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
        except urllib.error.HTTPError as e:
            print(f"[Relay] Backend returned {e.code}: {e.reason}")
            print(f"[Relay] Will retry...")
        except Exception:
            pass
        time.sleep(0.5)


if __name__ == "__main__":
    main()
