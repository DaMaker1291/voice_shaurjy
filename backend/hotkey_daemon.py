"""Global Hotkey Daemon — summons JARVIS from anywhere via Ctrl+Shift+J."""

import sys
import threading
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

DEFAULT_HOTKEY = "ctrl+shift+j"
HOTKEY_ACTIONS = {}  # registered callbacks

_executor = ThreadPoolExecutor(max_workers=1)
_listener = None
_listener_thread = None
_running = False


def register_action(hotkey: str, callback):
    """Register a callback for a hotkey combination."""
    HOTKEY_ACTIONS[hotkey] = callback


def _on_activate(hotkey: str):
    logger.info(f"Hotkey triggered: {hotkey}")
    callback = HOTKEY_ACTIONS.get(hotkey)
    if callback:
        _executor.submit(callback)


def start():
    global _listener, _listener_thread, _running

    if _running:
        logger.warning("Hotkey daemon already running")
        return

    try:
        from pynput import keyboard
    except ImportError:
        logger.warning("pynput not installed — hotkey daemon unavailable. Install with: pip install pynput")
        return

    _running = True

    current_keys = set()
    HOTKEY_MAP = {
        "ctrl+shift+j": {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('j')},
        "ctrl+shift+k": {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('k')},
        "ctrl+space":   {keyboard.Key.ctrl, keyboard.Key.space},
        "alt+space":    {keyboard.Key.alt, keyboard.Key.space},
    }

    def _on_press(key):
        current_keys.add(key)
        for hotkey_str, key_set in HOTKEY_MAP.items():
            if key_set.issubset(current_keys):
                _on_activate(hotkey_str)
                current_keys.clear()

    def _on_release(key):
        current_keys.discard(key)

    def _run():
        with keyboard.Listener(on_press=_on_press, on_release=_on_release) as listener:
            _listener = listener
            listener.join()

    _listener_thread = threading.Thread(target=_run, daemon=True, name="hotkey-daemon")
    _listener_thread.start()
    logger.info(f"Hotkey daemon started — press {DEFAULT_HOTKEY} to summon JARVIS")


def stop():
    global _running, _listener
    _running = False
    if _listener:
        _listener.stop()
    logger.info("Hotkey daemon stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def test_callback():
        print("JARVIS SUMMONED!")

    register_action(DEFAULT_HOTKEY, test_callback)
    start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        stop()
