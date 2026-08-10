"""Electron Desktop Shell — native desktop wrapper with global shortcuts."""

import os
import sys
import json
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_shell_process: Optional[subprocess.Popen] = None


def _get_electron_path() -> Optional[Path]:
    """Find bundled Electron or system electron."""
    # Check for locally installed electron
    local_electron = Path(__file__).parent.parent / "node_modules" / ".bin" / "electron"
    if sys.platform == "win32":
        local_electron = local_electron.with_suffix(".cmd")
    if local_electron.exists():
        return local_electron

    # Check npm global
    try:
        result = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=5)
        global_node_modules = Path(result.stdout.strip())
        electron_path = global_node_modules / "electron" / "cli.js"
        if electron_path.exists():
            return electron_path
    except Exception:
        pass

    return None


def _get_main_js_path() -> Path:
    return Path(__file__).parent / "shell" / "main.js"


def _ensure_shell_files():
    """Create Electron shell files if they don't exist."""
    shell_dir = Path(__file__).parent / "shell"
    shell_dir.mkdir(exist_ok=True)

    # package.json for electron app
    pkg_path = shell_dir / "package.json"
    if not pkg_path.exists():
        pkg_path.write_text(json.dumps({
            "name": "jarvis-desktop",
            "version": "1.0.0",
            "main": "main.js",
            "private": True
        }, indent=2))

    # main.js — Electron main process
    main_js = shell_dir / "main.js"
    if not main_js.exists():
        main_js.write_text(r"""const { app, BrowserWindow, globalShortcut, Tray, Menu, nativeImage, clipboard, ipcMain } = require('electron');
const path = require('path');

let mainWindow = null;
let tray = null;
let overlayWindow = null;

const JARVIS_URL = process.env.JARVIS_URL || 'http://127.0.0.1:7890';

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: true,
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'icon.png'),
  });
  mainWindow.loadURL(JARVIS_URL);
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createOverlayWindow() {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.isVisible() ? overlayWindow.hide() : overlayWindow.show();
    if (overlayWindow.isVisible()) overlayWindow.focus();
    return;
  }

  overlayWindow = new BrowserWindow({
    width: 700,
    height: 520,
    frame: false,
    transparent: true,
    resizable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  overlayWindow.loadURL(JARVIS_URL + '/ambient/overlay');
  overlayWindow.setVisibleOnAllWorkspaces(true);
  overlayWindow.center();

  overlayWindow.on('blur', () => {
    overlayWindow.hide();
  });
}

function toggleOverlay() {
  if (overlayWindow && overlayWindow.isVisible()) {
    overlayWindow.hide();
  } else {
    createOverlayWindow();
  }
}

function createTray() {
  const icon = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAAXNSR0IArs4c6QAAAMlJREFUeJzt2rENwjAQBdD/FYyAWIAJYAQKOkZgBEZgBNoR2IAOIsoViS2f7fN96ZMrO5+yLQAAAAAAAAAA/IqvVSUiqlpb7k5E5t6qdiIif29uEZHfN3c+AQAAAAAAAAAAAAAAFCIidxG5zzi/XkTkPiO/3/4KAAAAAAAAAAAAAAAo5Nq9/VTtIiL363v3iMjPmwMAAAAAAAAAAAAAABSiu5+q3UXkMfv+exYRub05AAAAAAAAAAAAAABAEaq99+7j3Ps/AX1Gjud8BgAAAAAAAAAAAAAAUKPWGgAAAAAAAAAAAAAAAAAAAAB4kxfHAhFGRVsASAAAAABJRU5ErkJggg==');
  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open JARVIS', click: () => { if (mainWindow) mainWindow.show(); } },
    { label: 'Toggle Overlay', click: toggleOverlay },
    { type: 'separator' },
    { label: 'Quit', click: () => { app.isQuitting = true; app.quit(); } },
  ]);
  tray.setToolTip('JARVIS — The System Engine');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => { if (mainWindow) mainWindow.show(); });
}

app.whenReady().then(() => {
  createMainWindow();
  createTray();

  globalShortcut.register('CommandOrControl+Shift+J', toggleOverlay);
  globalShortcut.register('CommandOrControl+Shift+K', () => {
    if (mainWindow) mainWindow.show();
  });

  app.on('activate', () => {
    if (mainWindow) mainWindow.show();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

ipcMain.on('toggle-overlay', toggleOverlay);
""");

    # Create a simple icon placeholder
    icon_path = shell_dir / "icon.png"
    if not icon_path.exists():
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([16, 16, 112, 112], fill=(68, 136, 255, 220))
            draw.polygon([(48, 40), (88, 64), (48, 88)], fill=(255, 255, 255, 230))
            img.save(str(icon_path))
        except Exception:
            pass


def start():
    global _shell_process

    if _shell_process is not None:
        logger.warning("Electron shell already running")
        return

    electron_path = _get_electron_path()
    if not electron_path:
        logger.info("Electron not found — install with: npm install -g electron")
        return

    _ensure_shell_files()
    main_js = str(_get_main_js_path())

    try:
        _shell_process = subprocess.Popen(
            [str(electron_path), main_js],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "JARVIS_URL": "http://127.0.0.1:7890"},
        )
        logger.info(f"Electron shell started (PID {_shell_process.pid})")
    except Exception as e:
        logger.error(f"Failed to start Electron shell: {e}")
        _shell_process = None


def stop():
    global _shell_process
    if _shell_process:
        _shell_process.terminate()
        _shell_process = None
        logger.info("Electron shell stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting JARVIS Electron desktop shell...")
    start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
