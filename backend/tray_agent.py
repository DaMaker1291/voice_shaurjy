"""System Tray Agent — persistent system tray icon for JARVIS."""

import os
import sys
import json
import threading
import logging
import webbrowser
from typing import Optional

logger = logging.getLogger(__name__)

_tray_thread: Optional[threading.Thread] = None
_running = False


def _create_tray_icon():
    """Create system tray icon using pystray."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("pystray/Pillow not installed. Install with: pip install pystray Pillow")
        return

    def _create_image():
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(68, 136, 255, 220))
        draw.polygon([(24, 20), (44, 32), (24, 44)], fill=(255, 255, 255, 230))
        return img

    def _on_open(icon, item):
        webbrowser.open("http://127.0.0.1:7890/ambient/overlay")

    def _on_toggle_overlay(icon, item):
        try:
            import requests
            requests.post("http://127.0.0.1:7890/api/ambient/toggle", timeout=2)
        except Exception:
            webbrowser.open("http://127.0.0.1:7890/ambient/overlay")

    def _on_open_dashboard(icon, item):
        webbrowser.open("http://127.0.0.1:7890/")

    def _on_open_settings(icon, item):
        webbrowser.open("http://127.0.0.1:7890/settings")

    def _on_quit(icon, item):
        icon.stop()
        _stop_server()

    def _stop_server():
        try:
            import requests
            requests.post("http://127.0.0.1:7890/api/shutdown", timeout=2)
        except Exception:
            pass
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open JARVIS", _on_open, default=True),
        pystray.MenuItem("Toggle Overlay", _on_toggle_overlay),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Dashboard", _on_open_dashboard),
        pystray.MenuItem("Settings", _on_open_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _on_quit),
    )

    icon = pystray.Icon("jarvis", _create_image(), "JARVIS — The System Engine", menu)
    icon.run()


def start():
    global _tray_thread, _running

    if _running:
        return

    _running = True
    _tray_thread = threading.Thread(target=_create_tray_icon, daemon=True, name="tray-agent")
    _tray_thread.start()
    logger.info("System tray agent started")


def stop():
    global _running
    _running = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting JARVIS tray agent...")
    start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        stop()
