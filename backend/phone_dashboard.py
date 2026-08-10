"""
JARVIS Phone Dashboard — Quick control for Galaxy S23.
Run this and open http://localhost:8888

Usage:
  python phone_dashboard.py                # Start dashboard
  python phone_dashboard.py --ip 192.168.8.186  # Custom phone IP
"""
import os
import sys
import json
import time
import subprocess
import argparse
import logging
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from http.server import HTTPServer
from urllib.parse import urlparse, parse_qs

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


logging.basicConfig(level=logging.INFO, format="[DASHBOARD] %(message)s")
logger = logging.getLogger("dashboard")

ADB_PATH = r"C:\platform-tools\adb.exe"
PHONE_IP = "192.168.8.186"
PHONE_PORT = 33857
DASHBOARD_HTML = Path(__file__).parent / "phone_dashboard.html"


def run_adb(*args, timeout=15) -> str:
    """Run ADB command and return output."""
    cmd = [ADB_PATH] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def adb_shell(command: str) -> str:
    """Run shell command on phone."""
    return run_adb("-s", f"{PHONE_IP}:{PHONE_PORT}", "shell", command)


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the phone dashboard."""

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "/index.html":
                self._serve_html()
            elif path == "/api/adb/info":
                self._get_info()
            elif path == "/api/adb/screenshot":
                self._screenshot()
            elif path.startswith("/api/adb/"):
                action = path.split("/")[-1]
                self._adb_action(action, parse_qs(parsed.query))
            else:
                self.send_error(404)
        except Exception as e:
            logger.error(f"GET error: {e}")
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            if path.startswith("/api/adb/"):
                action = path.split("/")[-1]
                self._adb_action(action, data)
            else:
                self.send_error(404)
        except Exception as e:
            logger.error(f"POST error: {e}")
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def _serve_html(self):
        if DASHBOARD_HTML.exists():
            html = DASHBOARD_HTML.read_text(encoding="utf-8")
        else:
            html = "<h1>Dashboard HTML not found</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _get_info(self):
        """Get phone information."""
        connected = False
        try:
            # Check connection
            devices = run_adb("devices")
            device_id = f"{PHONE_IP}:{PHONE_PORT}"
            connected = device_id in devices

            if not connected:
                # Try connecting
                run_adb("connect", f"{PHONE_IP}:{PHONE_PORT}")
                devices = run_adb("devices")
                connected = device_id in devices

            info = {"connected": connected, "ip": PHONE_IP}
            if connected:
                info["battery"] = _extract_battery()
                info["ssid"] = adb_shell("dumpsys wifi | grep 'SSID:' | head -1 | sed 's/.*SSID: \"//;s/\"//'")
                info["android_version"] = adb_shell("getprop ro.build.version.release")
                info["model"] = adb_shell("getprop ro.product.model")
                info["brand"] = adb_shell("getprop ro.product.brand")
            self._json_response(info)
        except Exception as e:
            self._json_response({"connected": False, "error": str(e)})

    def _screenshot(self):
        """Take screenshot and return as PNG."""
        try:
            remote = "/sdcard/jarvis_screen.png"
            local = os.path.join(os.environ.get("TEMP", "."), "jarvis_screen.png")
            adb_shell(f"screencap -p {remote}")
            time.sleep(0.5)
            run_adb("-s", f"{PHONE_IP}:{PHONE_PORT}", "pull", remote, local)
            adb_shell(f"rm {remote}")

            if os.path.exists(local):
                with open(local, "rb") as f:
                    data = f.read()
                os.unlink(local)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(500, "Screenshot failed: file not found")
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            self.send_error(500, f"Screenshot error: {e}")

    def _adb_action(self, action: str, params: dict):
        """Execute ADB action."""
        actions = {
            "power_off": lambda: adb_shell("reboot -p") or "Powering off...",
            "reboot": lambda: adb_shell("reboot") or "Rebooting...",
            "lock": lambda: adb_shell("input keyevent 26") or "Locked",
            "unlock": lambda: (adb_shell("input keyevent 26"), time.sleep(0.5), adb_shell("input swipe 500 1500 500 500 300")) or "Unlocked",
            "screen_on": lambda: adb_shell("input keyevent 224") or "Screen on",
            "screen_off": lambda: adb_shell("input keyevent 223") or "Screen off",
            "home": lambda: adb_shell("input keyevent 3") or "Home",
            "back": lambda: adb_shell("input keyevent 4") or "Back",
            "recent": lambda: adb_shell("input keyevent 187") or "Recent",
            "enter": lambda: adb_shell("input keyevent 66") or "Enter",
            "vol_up": lambda: adb_shell("input keyevent 24") or "Volume up",
            "vol_down": lambda: adb_shell("input keyevent 25") or "Volume down",
            "vibrate": lambda: adb_shell("input vibration 500") or "Vibrating...",
            "wifi_on": lambda: adb_shell("svc wifi enable") or "WiFi on",
            "wifi_off": lambda: adb_shell("svc wifi disable") or "WiFi off",
            "airplane_on": lambda: (adb_shell("settings put global airplane_mode_on 1"), adb_shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true")) or "Airplane on",
            "airplane_off": lambda: (adb_shell("settings put global airplane_mode_on 0"), adb_shell("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false")) or "Airplane off",
            "data_on": lambda: adb_shell("svc data enable") or "Data on",
            "data_off": lambda: adb_shell("svc data disable") or "Data off",
            "brightness": lambda: adb_shell(f"settings put system screen_brightness {params.get('level', ['128'])[0]}") or "Brightness set",
            "volume": lambda: adb_shell(f"media volume --stream 3 --set {params.get('level', ['8'])[0]}") or "Volume set",
            "type": lambda: adb_shell(f"input text '{params.get('text', [''])[0]}'") or "Typed",
            "launch": lambda: adb_shell(f"monkey -p {params.get('package', ['com.android.settings'])[0]} -c android.intent.category.LAUNCHER 1") or "Launched",
        }

        if action in actions:
            try:
                result = actions[action]()
                self._json_response({"success": True, "message": str(result), "action": action})
            except Exception as e:
                self._json_response({"success": False, "error": str(e), "action": action})
        else:
            self._json_response({"success": False, "error": f"Unknown action: {action}"})

    def _json_response(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def _extract_battery() -> int:
    output = adb_shell("dumpsys battery | grep level")
    import re
    match = re.search(r"level:\s*(\d+)", output)
    return int(match.group(1)) if match else -1


def main():
    global PHONE_IP, PHONE_PORT
    parser = argparse.ArgumentParser(description="JARVIS Phone Dashboard")
    parser.add_argument("--ip", default=PHONE_IP, help="Phone IP address")
    parser.add_argument("--port", type=int, default=PHONE_PORT, help="ADB port")
    parser.add_argument("--server-port", type=int, default=8888, help="Dashboard server port")
    args = parser.parse_args()

    PHONE_IP = args.ip
    PHONE_PORT = args.port

    # Connect to phone
    logger.info(f"Connecting to phone at {PHONE_IP}:{PHONE_PORT}...")
    result = run_adb("connect", f"{PHONE_IP}:{PHONE_PORT}")
    logger.info(f"ADB: {result}")

    # Start server
    server = ThreadedHTTPServer(("0.0.0.0", args.server_port), DashboardHandler)
    logger.info(f"Dashboard running at http://localhost:{args.server_port}")
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
