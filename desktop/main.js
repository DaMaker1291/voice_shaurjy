/**
 * JARVIS — Ambient Operating Layer
 * Electron Main Process
 *
 * Transforms the desktop into an ambient AI ecosystem:
 *  - Global hotkey overlay (Ctrl+Shift+J)
 *  - System tray with full control
 *  - Backend lifecycle management
 *  - Auto-launch & power monitoring
 */

const {
  app, BrowserWindow, Tray, Menu, nativeImage,
  nativeTheme, clipboard, shell, dialog, Notification,
  ipcMain, globalShortcut, powerMonitor, screen,
} = require("electron");
const path = require("path");
const { spawn, exec } = require("child_process");
const fs = require("fs");
const os = require("os");

// ── Config ──────────────────────────────────────────────────────────────
const isDev = process.env.NODE_ENV === "development";
const JARVIS_DIR = path.join(app.getPath("home"), ".jarvis");
const BACKEND_PORT = parseInt(process.env.JARVIS_BACKEND_PORT || "8000", 10);
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const LOCAL_FRONTEND = `file://${path.join(__dirname, "renderer", "dashboard.html")}`;
const HF_URL = process.env.HF_API_URL || process.env.JARVIS_DEPLOYMENT_URL || "";

// ── State ───────────────────────────────────────────────────────────────
let mainWindow = null;
let overlayWindow = null;
let pipWindow = null;
let tray = null;
let backendProcess = null;
let relayProcess = null;
let backendReady = false;
let isQuitting = false;

// ── Backend Management ──────────────────────────────────────────────────
function findPython() {
  const candidates = os.platform() === "win32"
    ? ["python", "python3", "py"]
    : ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const { execSync } = require("child_process");
      const ver = execSync(`${cmd} --version`, { encoding: "utf8", timeout: 5000, stdio: ["pipe", "pipe", "pipe"] });
      if (ver.includes("Python 3")) return cmd;
    } catch {}
  }
  return null;
}

function killPort(port) {
  try {
    const { execSync } = require("child_process");
    const out = execSync(`netstat -ano | findstr :${port}`, { encoding: "utf8", timeout: 3000, stdio: ["pipe", "pipe", "pipe"] });
    const pids = new Set();
    for (const line of out.split("\n")) {
      const m = line.trim().match(/\s+(\d+)\s*$/);
      if (m) pids.add(m[1]);
    }
    for (const pid of pids) {
      try { process.kill(Number(pid), "SIGTERM"); } catch {}
    }
  } catch {}
}

function startBackend() {
  if (backendProcess) return;
  const py = findPython();
  if (!py) {
    log("Python 3 not found — backend will not start");
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadURL(`data:text/html,${encodeURIComponent(createErrorHTML("Python 3 not found", "Install Python 3 from python.org and restart JARVIS."))}`);
    }
    return;
  }

  const backendMain = path.join(
    app.isPackaged
      ? path.join(process.resourcesPath, "backend")
      : path.join(__dirname, "..", "backend"),
    "main.py"
  );
  if (!fs.existsSync(backendMain)) { log("Backend main.py not found — cloud mode"); return; }

  log(`Starting backend: ${backendMain}`);
  const env = { ...process.env, PYTHONUNBUFFERED: "1", JARVIS_PORT: String(BACKEND_PORT) };
  const frontendDir = app.isPackaged
    ? path.join(process.resourcesPath, "frontend")
    : path.join(__dirname, "..", "frontend", "out");
  if (fs.existsSync(frontendDir)) env.JARVIS_FRONTEND_DIR = frontendDir;

  // Install deps if needed
  const reqFile = path.join(path.dirname(backendMain), "requirements-render.txt");
  const markerFile = path.join(JARVIS_DIR, ".deps_installed");
  if (fs.existsSync(reqFile) && !fs.existsSync(markerFile)) {
    log("Installing Python dependencies...");
    try {
      const { execSync } = require("child_process");
      execSync(`${py} -m pip install -r "${reqFile}" --quiet`, { timeout: 120000, stdio: "pipe" });
      if (!fs.existsSync(JARVIS_DIR)) fs.mkdirSync(JARVIS_DIR, { recursive: true });
      fs.writeFileSync(markerFile, new Date().toISOString());
      log("Dependencies installed");
    } catch (e) { log(`Dependency install warning: ${e.message?.slice(0, 100)}`); }
  }

  backendProcess = spawn(py, [backendMain], { cwd: path.dirname(backendMain), stdio: ["pipe", "pipe", "pipe"], env });
  backendProcess.stdout.on("data", (d) => { const m = d.toString().trim(); if (m) log(`[Backend] ${m}`); });
  backendProcess.stderr.on("data", (d) => { const m = d.toString().trim(); if (m) log(`[Backend] ${m}`); });
  backendProcess.on("exit", (code) => {
    log(`Backend exited with code ${code}`);
    backendProcess = null;
    backendReady = false;
    updateTrayMenu();
    if (!isQuitting) setTimeout(startBackend, 3000);
  });
  setTimeout(() => {
    backendReady = true;
    updateTrayMenu();
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send("backend-status", { ready: true });
  }, 2000);
}

function stopBackend() {
  if (backendProcess) { try { backendProcess.kill("SIGTERM"); } catch {} backendProcess = null; backendReady = false; }
  if (relayProcess) { try { relayProcess.kill("SIGTERM"); } catch {} relayProcess = null; }
  updateTrayMenu();
}

// ── Relay Management ────────────────────────────────────────────────────
function startRelay() {
  if (relayProcess) return;
  const py = findPython();
  if (!py) return;
  const backendDir = app.isPackaged ? path.join(process.resourcesPath, "backend") : path.join(__dirname, "..", "backend");
  let relayScript = path.join(backendDir, "relay.py");
  if (!fs.existsSync(relayScript)) relayScript = path.join(JARVIS_DIR, "relay.py");
  if (!fs.existsSync(relayScript)) return;
  relayProcess = spawn(py, [relayScript, "--user", "local"], { cwd: path.dirname(relayScript), stdio: ["pipe", "pipe", "pipe"], env: { ...process.env, PYTHONUNBUFFERED: "1" } });
  relayProcess.stdout.on("data", (d) => { const m = d.toString().trim(); if (m) log(`[Relay] ${m}`); });
  relayProcess.stderr.on("data", (d) => { const m = d.toString().trim(); if (m) log(`[Relay] ${m}`); });
  relayProcess.on("exit", (code) => { log(`Relay exited with code ${code}`); relayProcess = null; if (!isQuitting && code !== 0) setTimeout(startRelay, 5000); });
}

// ── Logging ─────────────────────────────────────────────────────────────
function log(msg) {
  const ts = new Date().toISOString().slice(11, 19);
  const line = `[JARVIS ${ts}] ${msg}`;
  console.log(line);
  try {
    const home = require("os").homedir();
    const logPath = path.join(home, ".jarvis", "electron.log");
    fs.appendFileSync(logPath, line + "\n");
  } catch {}
}

let _logFileInit = false;
function initLogFile() {
  if (_logFileInit) return;
  _logFileInit = true;
  try {
    const home = require("os").homedir();
    const logDir = path.join(home, ".jarvis");
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    fs.writeFileSync(path.join(logDir, "electron.log"), `[JARVIS] Restarted ${new Date().toISOString()}\n`);
  } catch {}
}

// ── Ambient Overlay Window (Spotlight-style) ────────────────────────────
function createOrToggleOverlay() {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    if (overlayWindow.isVisible()) {
      overlayWindow.hide();
      return;
    }
    overlayWindow.show();
    overlayWindow.focus();
    overlayWindow.webContents.send("overlay-focus");
    return;
  }

  const display = screen.getPrimaryDisplay();
  const { width: screenWidth } = display.workAreaSize;
  const overlayWidth = 680;
  const overlayHeight = 500;
  const x = Math.round((screenWidth - overlayWidth) / 2);
  const y = Math.round(screen.height * 0.12);

  overlayWindow = new BrowserWindow({
    width: overlayWidth,
    height: overlayHeight,
    x, y,
    frame: false,
    transparent: true,
    resizable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    show: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
  });

  overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  overlayWindow.setIgnoreMouseEvents(false);

  // Load the overlay HTML
  overlayWindow.loadFile(path.join(__dirname, "renderer", "overlay.html"));

  overlayWindow.once("ready-to-show", () => {
    overlayWindow.show();
    overlayWindow.focus();
    overlayWindow.webContents.send("overlay-focus");
  });

  // Hide on blur (click outside)
  overlayWindow.on("blur", () => {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
      overlayWindow.hide();
    }
  });

  overlayWindow.on("closed", () => { overlayWindow = null; });
}

// ── VDI Screenshot Poller (main process → PiP via IPC) ───────────────────
let vdiPollTimer = null;

function startVdiStreamProxy() {
  // PiP connects directly to ws://127.0.0.1:8766/ws — no proxy needed
  // This is just a no-op placeholder
  log("PiP should connect directly to VDI WebSocket");
}

function stopVdiStreamProxy() {
  if (vdiPollTimer) { clearTimeout(vdiPollTimer); vdiPollTimer = null; }
}

// ── PiP Window (movable/resizable live VDI view) ─────────────────────────
function createOrTogglePiP() {
  if (pipWindow && !pipWindow.isDestroyed()) {
    if (pipWindow.isVisible()) {
      pipWindow.hide();
      stopVdiStreamProxy();
      return;
    }
    pipWindow.show();
    pipWindow.focus();
    startVdiStreamProxy();
    return;
  }

  try {
    const display = screen.getPrimaryDisplay();
    const { workArea } = display;
    const pipWidth = 480;
    const pipHeight = 270;

    const x = workArea.x + workArea.width - pipWidth - 20;
    const y = workArea.y + workArea.height - pipHeight - 60;

    pipWindow = new BrowserWindow({
      width: pipWidth,
      height: pipHeight,
      minWidth: 200,
      minHeight: 120,
      x, y,
      frame: false,
      transparent: false,
      resizable: true,
      movable: true,
      skipTaskbar: false,
      alwaysOnTop: true,
      show: true,
      hasShadow: true,
      title: "JARVIS PiP",
      backgroundColor: "#030712",
      webPreferences: {
        preload: path.join(__dirname, "preload.js"),
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: false,
        webSecurity: false,
      },
    });

    pipWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

    pipWindow.loadFile(path.join(__dirname, "renderer", "pip_overlay.html"));

    pipWindow.webContents.on("did-finish-load", () => {
      log("PiP did-finish-load, starting stream in 500ms");
      setTimeout(() => startVdiStreamProxy(), 500);
    });

    pipWindow.on("closed", () => { pipWindow = null; stopVdiStreamProxy(); });
    log("PiP window created");
  } catch (e) {
    log(`PiP creation error: ${e.message}`);
  }
}

// ── Main Window ─────────────────────────────────────────────────────────
function createMainWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const isMac = os.platform() === "darwin";
  const winOpts = {
    width: Math.min(1400, width - 100),
    height: Math.min(900, height - 100),
    minWidth: 800, minHeight: 600,
    title: "JARVIS",
    icon: path.join(__dirname, "assets", "icon.png"),
    backgroundColor: "#030303",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false, contextIsolation: true, sandbox: false, webSecurity: false,
    },
  };
  // macOS gets hidden title bar with traffic lights; Windows gets standard frame
  if (isMac) {
    winOpts.titleBarStyle = "hidden";
    winOpts.titleBarOverlay = { color: "#0a0c10", symbolColor: "#667085", height: 36 };
  }
  mainWindow = new BrowserWindow(winOpts);

  const loadFrontend = async () => {
    mainWindow.loadURL(`data:text/html,${encodeURIComponent(createLoadingHTML())}`);
    const http = require("http");
    let attempts = 0;
    while (attempts < 30) {
      try {
        await new Promise((resolve, reject) => {
          const req = http.get(`${BACKEND_URL}/api/health`, { timeout: 2000 }, (res) => res.statusCode === 200 ? resolve() : reject());
          req.on("error", reject); req.on("timeout", () => { req.destroy(); reject(); });
        });
        log(`Backend ready after ${attempts} attempts`);
        mainWindow.loadURL(LOCAL_FRONTEND);
        return;
      } catch { attempts++; await new Promise(r => setTimeout(r, 1000)); }
    }
    log("Backend failed — falling back to HF Space");
    mainWindow.loadURL(HF_URL);
  };
  loadFrontend();

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools({ mode: "detach" });
    // Auto-open PiP window after main window loads (with error handling)
    setTimeout(() => {
      try { createOrTogglePiP(); } catch(e) { log(`PiP auto-open error: ${e.message}`); }
    }, 3000);
  });
  mainWindow.on("close", (e) => {
    if (!isQuitting) { e.preventDefault(); mainWindow.hide(); showTrayNotification(); }
  });
  mainWindow.on("closed", () => { mainWindow = null; });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
}

function createLoadingHTML() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:#030303;color:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:0;overflow:hidden;}
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes pulse{0%,100%{opacity:0.4}50%{opacity:1}}
  @keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
  @keyframes fillBar{0%{width:0%}100%{width:100%}}
  @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  .orb{width:52px;height:52px;border-radius:50%;background:conic-gradient(#00FF66,#0088ff,#00FF66,#0088ff);
    animation:spin 3s linear infinite;position:relative;margin-bottom:24px;}
  .orb::after{content:'';position:absolute;inset:3px;background:#030303;border-radius:50%;}
  .orb-core{position:absolute;inset:8px;border-radius:50%;background:#030303;z-index:1;}
  .orb-core-inner{width:16px;height:16px;border-radius:50%;background:#00FF66;position:absolute;top:50%;left:50%;
    transform:translate(-50%,-50%);box-shadow:0 0 20px rgba(0,255,102,0.3);animation:pulse 2s ease-in-out infinite;}
  h1{font-size:20px;font-weight:400;letter-spacing:0.05em;color:#e5e5e5;margin-bottom:4px;}
  .tagline{font-size:10px;color:#667085;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:28px;}
  .status-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;margin-bottom:24px;}
  .status-item{display:flex;align-items:center;gap:8px;font-size:11px;color:#3a3d43;animation:fadeUp 0.4s both;}
  .status-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0;}
  .status-dot.loading{background:#667085;animation:pulse 1.2s ease-in-out infinite;}
  .status-dot.done{background:#00FF66;box-shadow:0 0 6px rgba(0,255,102,0.3);}
  .status-dot.pending{background:#1a1d23;}
  .status-label{color:#667085;font-size:11px;}
  .bar-track{width:220px;height:2px;background:#1a1d23;border-radius:2px;overflow:hidden;}
  .bar-fill{height:100%;width:0%;background:linear-gradient(90deg,#00FF66,#0088ff);border-radius:2px;
    animation:fillBar 2.5s ease-in-out forwards;}
  .version{font-size:9px;color:#1a1d23;margin-top:24px;letter-spacing:0.05em;}
</style>
</head>
<body>
  <div class="orb"><div class="orb-core"><div class="orb-core-inner"></div></div></div>
  <h1>JARVIS</h1>
  <div class="tagline">Ambient Operating Layer</div>
  <div class="status-grid">
    <div class="status-item" style="animation-delay:0s"><span class="status-dot loading" id="s1"></span><span>Core Engine</span></div>
    <div class="status-item" style="animation-delay:0.1s"><span class="status-dot pending" id="s2"></span><span>Agent Network</span></div>
    <div class="status-item" style="animation-delay:0.2s"><span class="status-dot pending" id="s3"></span><span>Screen Vision</span></div>
    <div class="status-item" style="animation-delay:0.3s"><span class="status-dot pending" id="s4"></span><span>Voice Engine</span></div>
    <div class="status-item" style="animation-delay:0.4s"><span class="status-dot pending" id="s5"></span><span>Context Relay</span></div>
    <div class="status-item" style="animation-delay:0.5s"><span class="status-dot pending" id="s6"></span><span>Ambient Layer</span></div>
  </div>
  <div class="bar-track"><div class="bar-fill"></div></div>
  <div class="version">v3.0 · Windows</div>
  <script>
    const states = [document.getElementById('s1'),document.getElementById('s2'),document.getElementById('s3'),
      document.getElementById('s4'),document.getElementById('s5'),document.getElementById('s6')];
    let i = 0;
    const tick = () => {
      if (i < states.length) {
        states[i].className = 'status-dot done';
        if (i + 1 < states.length) states[i+1].className = 'status-dot loading';
        i++;
        setTimeout(tick, 350 + Math.random() * 300);
      }
    };
    setTimeout(tick, 400);
  </script>
</body></html>`;
}

// ── Error HTML (shown when Python or backend not found) ──────────────
function createErrorHTML(title, message) {
  return `<!DOCTYPE html>
<html lang="en">
<head><style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:#080A0E;color:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;padding:40px;text-align:center;}
  .icon{width:36px;height:36px;border-radius:50%;border:2px solid rgba(255,60,50,0.3);display:flex;align-items:center;justify-content:center;color:#FF3B30;font-size:18px;margin-bottom:4px;}
  h1{font-size:16px;font-weight:500;color:#e5e5e5;}
  p{font-size:12px;color:#667085;line-height:1.5;max-width:400px;}
  .btn{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);color:#e5e5e5;padding:8px 20px;border-radius:8px;cursor:pointer;font-size:12px;margin-top:8px;}
</style></head><body>
  <div class="icon">!</div>
  <h1>${escHtml(title)}</h1>
  <p>${escHtml(message)}</p>
  <button class="btn" onclick="require('electron').shell.openExternal('https://python.org/downloads')">Download Python</button>
</body></html>`;
}
function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── System Tray ─────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, "assets", "tray-icon.png");
  const trayIcon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : createTrayIconNative();
  tray = new Tray(trayIcon);
  tray.setToolTip("JARVIS — Ambient Operating Layer");
  updateTrayMenu();
  tray.on("click", () => { toggleMainWindow(); });
}

function createTrayIconNative() {
  const size = 16;
  const canvas = nativeImage.createFromBuffer(
    Buffer.from(createPNG(size), "base64"), { width: size, height: size }
  );
  return canvas;
}

function createPNG(size) {
  // Minimal inline PNG: green dot
  const w = size, h = size;
  const raw = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const cx = x - w/2, cy = y - h/2;
      const dist = Math.sqrt(cx*cx + cy*cy);
      if (dist < w/2 - 1) {
        raw[i] = 0; raw[i+1] = 255; raw[i+2] = 102; raw[i+3] = 220;
      } else {
        raw[i] = 0; raw[i+1] = 0; raw[i+2] = 0; raw[i+3] = 0;
      }
    }
  }
  // Return a data URL as base64
  return nativeImage.createFromBuffer(raw, { width: w, height: h }).toDataURL().split(",")[1];
}

function updateTrayMenu() {
  if (!tray || tray.isDestroyed()) return;
  const statusIcon = backendReady ? "●" : "○";
  const statusColor = backendReady ? "#00FF66" : "#FF3B30";
  const relayIcon = relayProcess ? "●" : "○";
  const relayColor = relayProcess ? "#00FF66" : "#667085";

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Open JARVIS",
      click: () => toggleMainWindow(),
    },
    {
      label: "Quick Command...   Ctrl+Shift+J",
      click: () => createOrToggleOverlay(),
    },
    {
      label: "PiP Overlay...      Ctrl+Shift+P",
      click: () => createOrTogglePiP(),
    },
    { type: "separator" },
    {
      label: `  ${statusIcon} Backend`,
      enabled: false,
      icon: null,
    },
    {
      label: `  ${relayIcon} Relay`,
      enabled: false,
    },
    { type: "separator" },
    {
      label: "Restart Backend",
      click: () => { stopBackend(); setTimeout(() => { startBackend(); setTimeout(startRelay, 3000); }, 1000); },
    },
    {
      label: "Open JARVIS Folder",
      click: () => shell.openPath(JARVIS_DIR),
    },
    {
      label: "Auto-Launch on Startup",
      type: "checkbox",
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked, openAsHidden: true }),
    },
    { type: "separator" },
    {
      label: "Quit JARVIS",
      click: () => { isQuitting = true; stopBackend(); app.quit(); },
    },
  ]);
  tray.setContextMenu(contextMenu);
}

function toggleMainWindow() {
  if (mainWindow?.isVisible()) { mainWindow.hide(); }
  else { mainWindow?.show(); mainWindow?.focus(); }
}

function showTrayNotification() {
  if (os.platform() === "win32") {
    tray?.displayBalloon({ title: "JARVIS", content: "Running in background. Ctrl+Shift+J to summon.", iconType: "info" });
  }
}

// ── IPC Handlers ────────────────────────────────────────────────────────
function setupIPC() {
  // Window controls
  ipcMain.on("window-minimize", () => mainWindow?.minimize());
  ipcMain.on("window-maximize", () => { mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize(); });
  ipcMain.on("window-close", () => mainWindow?.close());
  ipcMain.handle("window-is-maximized", () => mainWindow?.isMaximized() ?? false);

  // Overlay
  ipcMain.on("overlay-hide", () => { if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.hide(); });
  ipcMain.on("overlay-execute", (_, command) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("overlay-command", command);
    }
    if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.hide();
  });
  ipcMain.on("pip-show", () => createOrTogglePiP());

  // Backend
  ipcMain.handle("backend-status", () => ({ ready: backendReady }));
  ipcMain.handle("get-deployment-url", () => HF_URL || BACKEND_URL);
  ipcMain.handle("backend-restart", () => { stopBackend(); setTimeout(startBackend, 1000); return { ok: true }; });

  // System
  ipcMain.handle("get-system-info", () => ({
    platform: os.platform(), release: os.release(), version: os.version(),
    arch: os.arch(), hostname: os.hostname(), user: os.userInfo().username,
    homedir: os.homedir(), cpus: os.cpus().length,
    totalmem: os.totalmem(), freemem: os.freemem(),
  }));

  // Clipboard
  ipcMain.handle("clipboard-read", () => clipboard.readText());
  ipcMain.handle("clipboard-write", (_, text) => { clipboard.writeText(text); return { ok: true }; });

  // Notifications
  ipcMain.on("notify", (_, { title, body, icon }) => {
    if (Notification.isSupported()) new Notification({ title, body, icon }).show();
  });

  // Shell
  ipcMain.handle("open-external", (_, url) => shell.openExternal(url));
  ipcMain.handle("open-path", (_, p) => shell.openPath(p));

  // Dialogs
  ipcMain.handle("dialog-open", async (_, options) => await dialog.showOpenDialog(mainWindow, options));
  ipcMain.handle("dialog-save", async (_, options) => await dialog.showSaveDialog(mainWindow, options));

  // Auto-launch
  ipcMain.handle("auto-launch-get", () => app.getLoginItemSettings().openAtLogin);
  ipcMain.handle("auto-launch-set", (_, enabled) => { app.setLoginItemSettings({ openAtLogin: enabled, openAsHidden: true }); return { ok: true }; });

  // Quit
  ipcMain.on("app-quit", () => { isQuitting = true; stopBackend(); app.quit(); });
}

// ── Single Instance Lock ────────────────────────────────────────────────
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.show(); mainWindow.focus(); }
  });

  // ── App Lifecycle ─────────────────────────────────────────────────────
  app.whenReady().then(() => {
    initLogFile();
    log("App ready — starting...");
    try { setupIPC(); log("IPC setup done"); } catch(e) { log("IPC error: " + e.message); }
    try { createMainWindow(); log("Main window created"); } catch(e) { log("Main window error: " + e.message); }
    try { createTray(); log("Tray created"); } catch(e) { log("Tray error: " + e.message); }
    try { setTimeout(startBackend, 1000); log("Backend starting..."); } catch(e) { log("Backend error: " + e.message); }
    setTimeout(startRelay, 5000);

    // Global hotkeys
    globalShortcut.register("CommandOrControl+Shift+J", () => createOrToggleOverlay());
    globalShortcut.register("CommandOrControl+Shift+K", () => toggleMainWindow());
    globalShortcut.register("CommandOrControl+Shift+P", () => createOrTogglePiP());

    // HTTP listener for PiP auto-open from backend
    const http = require("http");
    const pipServer = http.createServer((req, res) => {
      if (req.method === "POST" && req.url === "/pip-show") {
        let body = "";
        req.on("data", (chunk) => { body += chunk; });
        req.on("end", () => {
          // Always respond immediately
          res.writeHead(200, { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" });
          res.end(JSON.stringify({ ok: true }));
          // Always create/show PiP on POST
          setImmediate(() => createOrTogglePiP());
        });
      } else if (req.method === "OPTIONS") {
        res.writeHead(200, { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST,OPTIONS", "Access-Control-Allow-Headers": "Content-Type" });
        res.end();
      } else {
        res.writeHead(404);
        res.end();
      }
    });
    pipServer.listen(18080, "127.0.0.1", () => {
      log("PiP HTTP listener on port 18080");
    });

    // Power monitoring
    powerMonitor.on("suspend", () => { log("System suspending — pausing backend"); stopBackend(); });
    powerMonitor.on("resume", () => { log("System resuming — restarting backend"); setTimeout(startBackend, 2000); });
    app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createMainWindow(); });
  });

  app.on("will-quit", () => { globalShortcut.unregisterAll(); stopBackend(); });
}
