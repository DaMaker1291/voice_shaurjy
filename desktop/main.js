/**
 * JARVIS — Sovereign Network Orchestrator
 * Electron Main Process
 *
 * Manages the native window, system tray, backend lifecycle,
 * auto-launch, native notifications, and desktop automation.
 */

const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  nativeTheme,
  clipboard,
  shell,
  dialog,
  Notification,
  ipcMain,
  globalShortcut,
  powerMonitor,
  screen,
} = require("electron");
const path = require("path");
const { spawn, exec } = require("child_process");
const fs = require("fs");
const os = require("os");

// ── Config ──────────────────────────────────────────────────────────────
const isDev = process.env.NODE_ENV === "development";
const JARVIS_DIR = path.join(app.getPath("home"), ".jarvis");
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const LOCAL_FRONTEND = `${BACKEND_URL}/voice_shaurjy/`;
const HF_URL = "https://dgfhgjhj-jarvis-ai-brain.hf.space";

// ── State ───────────────────────────────────────────────────────────────
let mainWindow = null;
let tray = null;
let backendProcess = null;
let backendReady = false;
let isQuitting = false;

// ── Backend Management ──────────────────────────────────────────────────
function findPython() {
  const candidates =
    os.platform() === "win32"
      ? ["python", "python3", "py"]
      : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const { execSync } = require("child_process");
      const ver = execSync(`${cmd} --version`, {
        encoding: "utf8",
        timeout: 5000,
        stdio: ["pipe", "pipe", "pipe"],
      });
      if (ver.includes("Python 3")) return cmd;
    } catch {}
  }
  return null;
}

function startBackend() {
  if (backendProcess) return;

  const py = findPython();
  if (!py) {
    log("Python not found — backend will not start");
    return;
  }

  const backendMain = path.join(
    app.isPackaged
      ? path.join(process.resourcesPath, "backend")
      : path.join(__dirname, "..", "backend"),
    "main.py"
  );

  if (!fs.existsSync(backendMain)) {
    log("Backend main.py not found — running in cloud mode");
    return;
  }

  // Always start the full backend (serves API + frontend)
  const scriptPath = backendMain;
  const args = [];
  log(`Starting backend: ${scriptPath}`);

  // Set port via env
  const env = { ...process.env, PYTHONUNBUFFERED: "1", JARVIS_PORT: String(BACKEND_PORT) };

  // Pass frontend dir so main.py can find it
  const frontendDir = app.isPackaged
    ? path.join(process.resourcesPath, "frontend")
    : path.join(__dirname, "..", "frontend", "out");
  if (fs.existsSync(frontendDir)) {
    env.JARVIS_FRONTEND_DIR = frontendDir;
    log(`Frontend dir: ${frontendDir}`);
  }

  // Install Python dependencies if needed
  const reqFile = path.join(path.dirname(backendMain), "requirements-render.txt");
  const markerFile = path.join(JARVIS_DIR, ".deps_installed");
  if (fs.existsSync(reqFile) && !fs.existsSync(markerFile)) {
    log("Installing Python dependencies...");
    try {
      const { execSync } = require("child_process");
      execSync(`${py} -m pip install -r "${reqFile}" --quiet`, {
        timeout: 120000,
        stdio: "pipe",
      });
      if (!fs.existsSync(JARVIS_DIR)) fs.mkdirSync(JARVIS_DIR, { recursive: true });
      fs.writeFileSync(markerFile, new Date().toISOString());
      log("Dependencies installed");
    } catch (e) {
      log(`Dependency install warning: ${e.message?.slice(0, 100)}`);
    }
  }

  // Copy relay.py to ~/.jarvis if it exists
  const relaySrc = path.join(path.dirname(backendMain), "relay.py");
  const relayDst = path.join(JARVIS_DIR, "relay.py");
  if (fs.existsSync(relaySrc) && !fs.existsSync(relayDst)) {
    try {
      if (!fs.existsSync(JARVIS_DIR)) fs.mkdirSync(JARVIS_DIR, { recursive: true });
      fs.copyFileSync(relaySrc, relayDst);
      log(`Copied relay.py to ${JARVIS_DIR}`);
    } catch {}
  }

  backendProcess = spawn(py, [scriptPath, ...args], {
    cwd: path.dirname(scriptPath),
    stdio: ["pipe", "pipe", "pipe"],
    env,
  });

  backendProcess.stdout.on("data", (data) => {
    const msg = data.toString().trim();
    if (msg) log(`[Backend] ${msg}`);
  });

  backendProcess.stderr.on("data", (data) => {
    const msg = data.toString().trim();
    if (msg) log(`[Backend] ${msg}`);
  });

  backendProcess.on("exit", (code) => {
    log(`Backend exited with code ${code}`);
    backendProcess = null;
    backendReady = false;

    // Auto-restart if not quitting
    if (!isQuitting) {
      setTimeout(startBackend, 3000);
    }
  });

  // Mark as ready after a short delay
  setTimeout(() => {
    backendReady = true;
    if (mainWindow) {
      mainWindow.webContents.send("backend-status", { ready: true });
    }
  }, 2000);
}

function stopBackend() {
  if (backendProcess) {
    try {
      backendProcess.kill("SIGTERM");
    } catch {}
    backendProcess = null;
    backendReady = false;
  }
}

// ── Logging ─────────────────────────────────────────────────────────────
function log(msg) {
  const ts = new Date().toISOString().slice(11, 19);
  console.log(`[JARVIS ${ts}] ${msg}`);
}

// ── Window ──────────────────────────────────────────────────────────────
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: Math.min(1400, width - 100),
    height: Math.min(900, height - 100),
    minWidth: 800,
    minHeight: 600,
    title: "JARVIS",
    icon: path.join(__dirname, "assets", "icon.png"),
    backgroundColor: "#030303",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      webSecurity: false,
    },
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#0a0c10",
      symbolColor: "#667085",
      height: 36,
    },
    frame: true,
    transparent: false,
  });

  // Load the frontend — local backend serves it, fallback to HF Space
  const loadFrontend = async () => {
    // Show loading screen immediately
    mainWindow.loadURL(`data:text/html,${encodeURIComponent(`
      <!DOCTYPE html>
      <html><head><style>
        body{margin:0;background:#030303;color:#a1a1aa;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px}
        .spinner{width:40px;height:40px;border:3px solid #1a1a2e;border-top-color:#00ff66;border-radius:50%;animation:spin 1s linear infinite}
        @keyframes spin{to{transform:rotate(360deg)}}
        h2{color:#e4e4e7;font-size:18px;margin:0}p{font-size:13px;margin:0}
      </style></head><body>
        <div class="spinner"></div>
        <h2>JARVIS</h2>
        <p>Starting local backend...</p>
      </body></html>
    `)}`);

    // Poll until backend is ready
    const http = require("http");
    let attempts = 0;
    const maxAttempts = 30;
    const tryConnect = () => new Promise((resolve, reject) => {
      const req = http.get(`${BACKEND_URL}/api/health`, { timeout: 2000 }, (res) => {
        if (res.statusCode === 200) resolve(true);
        else reject(new Error("not ok"));
      });
      req.on("error", reject);
      req.on("timeout", () => { req.destroy(); reject(new Error("timeout")); });
    });

    while (attempts < maxAttempts) {
      try {
        await tryConnect();
        log(`Backend ready after ${attempts} attempts`);
        mainWindow.loadURL(LOCAL_FRONTEND);
        return;
      } catch {
        attempts++;
        await new Promise(r => setTimeout(r, 1000));
      }
    }
    log("Backend failed to start — falling back to HF Space");
    mainWindow.loadURL(HF_URL);
  };
  loadFrontend();

  // Show when ready
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools({ mode: "detach" });
  });

  // Minimize to tray instead of closing
  mainWindow.on("close", (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
      if (os.platform() === "win32") {
        tray?.displayBalloon({
          title: "JARVIS",
          content: "Running in background. Click tray icon to reopen.",
          iconType: "info",
        });
      }
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── System Tray ─────────────────────────────────────────────────────────
function createTray() {
  // Create tray icon
  const iconPath = path.join(__dirname, "assets", "tray-icon.png");
  let trayIcon;

  if (fs.existsSync(iconPath)) {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } else {
    // Create a simple green dot icon
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip("JARVIS — Sovereign Network Orchestrator");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Open JARVIS",
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      },
    },
    { type: "separator" },
    {
      label: "Backend Status",
      enabled: false,
      toolTip: backendReady ? "Online" : "Offline",
    },
    {
      label: backendReady ? "● Online" : "○ Offline",
      enabled: false,
    },
    { type: "separator" },
    {
      label: "Restart Backend",
      click: () => {
        stopBackend();
        setTimeout(startBackend, 1000);
      },
    },
    {
      label: "Open JARVIS Folder",
      click: () => shell.openPath(JARVIS_DIR),
    },
    { type: "separator" },
    {
      label: "Quit JARVIS",
      click: () => {
        isQuitting = true;
        stopBackend();
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  tray.on("click", () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow?.show();
      mainWindow?.focus();
    }
  });

  // Update tray every 10 seconds
  setInterval(() => {
    if (tray && !tray.isDestroyed()) {
      tray.setToolTip(
        `JARVIS — ${backendReady ? "Online" : "Offline"}`
      );
    }
  }, 10000);
}

// ── Auto Launch ─────────────────────────────────────────────────────────
function setupAutoLaunch() {
  const autoLaunch = require("electron").app.getLoginItemSettings();
  if (!autoLaunch.openAtLogin) {
    // Don't force it — let user enable from settings
  }
}

function setAutoLaunch(enabled) {
  app.setLoginItemSettings({
    openAtLogin: enabled,
    openAsHidden: true,
    path: app.getPath("exe"),
  });
}

// ── IPC Handlers ────────────────────────────────────────────────────────
function setupIPC() {
  // Window controls
  ipcMain.on("window-minimize", () => mainWindow?.minimize());
  ipcMain.on("window-maximize", () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });
  ipcMain.on("window-close", () => mainWindow?.close());
  ipcMain.handle("window-is-maximized", () => mainWindow?.isMaximized() ?? false);

  // Backend
  ipcMain.handle("backend-status", () => ({ ready: backendReady }));
  ipcMain.handle("backend-restart", () => {
    stopBackend();
    setTimeout(startBackend, 1000);
    return { ok: true };
  });

  // System
  ipcMain.handle("get-system-info", () => ({
    platform: os.platform(),
    release: os.release(),
    version: os.version(),
    arch: os.arch(),
    hostname: os.hostname(),
    user: os.userInfo().username,
    homedir: os.homedir(),
    cpus: os.cpus().length,
    totalmem: os.totalmem(),
    freemem: os.freemem(),
  }));

  // Clipboard
  ipcMain.handle("clipboard-read", () => clipboard.readText());
  ipcMain.handle("clipboard-write", (_, text) => {
    clipboard.writeText(text);
    return { ok: true };
  });

  // Notifications
  ipcMain.on("notify", (_, { title, body, icon }) => {
    if (Notification.isSupported()) {
      const notification = new Notification({ title, body, icon });
      notification.show();
    }
  });

  // Shell
  ipcMain.handle("open-external", (_, url) => shell.openExternal(url));
  ipcMain.handle("open-path", (_, p) => shell.openPath(p));

  // Dialog
  ipcMain.handle("dialog-open", async (_, options) => {
    const result = await dialog.showOpenDialog(mainWindow, options);
    return result;
  });
  ipcMain.handle("dialog-save", async (_, options) => {
    const result = await dialog.showSaveDialog(mainWindow, options);
    return result;
  });

  // Auto-launch
  ipcMain.handle("auto-launch-get", () => app.getLoginItemSettings().openAtLogin);
  ipcMain.handle("auto-launch-set", (_, enabled) => {
    setAutoLaunch(enabled);
    return { ok: true };
  });

  // Quit
  ipcMain.on("app-quit", () => {
    isQuitting = true;
    stopBackend();
    app.quit();
  });
}

// ── Single Instance Lock ────────────────────────────────────────────────
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  // ── App Lifecycle ─────────────────────────────────────────────────────
  app.whenReady().then(() => {
    setupIPC();
    createWindow();
    createTray();
    setupAutoLaunch();
    startBackend();

    // Register global shortcut
    globalShortcut.register("CommandOrControl+Shift+J", () => {
      if (mainWindow?.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow?.show();
        mainWindow?.focus();
      }
    });

    // Power monitor — pause backend on sleep
    powerMonitor.on("suspend", () => {
      log("System suspending — pausing backend");
      stopBackend();
    });

    powerMonitor.on("resume", () => {
      log("System resuming — restarting backend");
      setTimeout(startBackend, 2000);
    });

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on("will-quit", () => {
    globalShortcut.unregisterAll();
    stopBackend();
  });
}
