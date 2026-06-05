const { app, BrowserWindow, Tray, Menu, nativeImage, protocol, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');

let mainWindow = null;
let tray = null;
let pythonProcess = null;
let isQuitting = false;

const BACKEND_PORT = 8000;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;
const FRONTEND_DIR = path.join(__dirname, '..', 'frontend', 'out');

// ── Python Backend ──────────────────────────────────────────────

function findPython() {
  const candidates = [
    path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe'),
    path.join(process.resourcesPath, '..', '.venv', 'Scripts', 'python.exe'),
    'python',
    'python3',
  ];
  for (const c of candidates) {
    try { require('child_process').execSync(`"${c}" --version`, { stdio: 'ignore' }); return c; } catch {}
  }
  return 'python';
}

function startBackend() {
  const python = findPython();
  const args = ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)];

  pythonProcess = spawn(python, args, {
    cwd: path.join(__dirname, '..'),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONPATH: path.join(__dirname, '..') },
  });

  pythonProcess.stdout.on('data', (d) => process.stdout.write(`[Backend] ${d}`));
  pythonProcess.stderr.on('data', (d) => process.stderr.write(`[Backend] ${d}`));

  pythonProcess.on('exit', (code) => {
    if (!isQuitting) {
      console.log(`[Backend] exited (${code}), restarting in 2s...`);
      setTimeout(startBackend, 2000);
    }
  });
}

async function waitForPort(timeout = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      await new Promise((resolve, reject) => {
        const s = net.createConnection(BACKEND_PORT, '127.0.0.1', () => { s.end(); resolve(); });
        s.on('error', reject);
      });
      return true;
    } catch {
      await new Promise(r => setTimeout(r, 200));
    }
  }
  return false;
}

// ── Custom Protocol (serve frontend from disk) ─────────────────

function registerAppProtocol() {
  protocol.handle('app', (req) => {
    let url = req.url.replace('app://', '');
    if (url === '' || url.endsWith('/')) url += 'index.html';
    const filePath = path.join(FRONTEND_DIR, url);
    if (fs.existsSync(filePath)) {
      return net.fetch('file://' + filePath.replace(/\\/g, '/'));
    }
    // SPA fallback
    return net.fetch('file://' + path.join(FRONTEND_DIR, 'index.html').replace(/\\/g, '/'));
  });
}

// ── Loading Window ─────────────────────────────────────────────

function createLoadingWindow() {
  const win = new BrowserWindow({
    width: 500,
    height: 400,
    frame: false,
    transparent: true,
    resizable: false,
    show: false,
    backgroundColor: '#05081a',
  });

  const html = `<!DOCTYPE html>
<html><body style="margin:0;background:#05081a;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:system-ui,sans-serif;color:white">
<div style="font-size:48px;margin-bottom:16px">🧠</div>
<div style="font-size:22px;font-weight:600;margin-bottom:8px;color:#a855f7">Second Brain</div>
<div style="font-size:13px;color:#6b7280;margin-bottom:24px">Starting...</div>
<div style="width:200px;height:3px;background:#1f2937;border-radius:2px;overflow:hidden">
<div style="width:30%;height:100%;background:linear-gradient(90deg,#a855f7,#06b6d4);border-radius:2px;animation:pulse 1.2s ease-in-out infinite"></div>
</div>
<style>@keyframes pulse{0%{transform:translateX(-100%)}100%{transform:translateX(400%)}}</style>
</body></html>`;

  win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
  win.once('ready-to-show', () => win.show());
  return win;
}

// ── Main Window ────────────────────────────────────────────────

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: path.join(__dirname, 'icon.png'),
    title: 'Second Brain',
    backgroundColor: '#05081a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load frontend from disk via custom protocol
  mainWindow.loadURL('app://');

  mainWindow.once('ready-to-show', () => mainWindow.show());

  mainWindow.on('close', (e) => {
    if (!isQuitting) { e.preventDefault(); mainWindow.hide(); }
  });
}

// ── System Tray ────────────────────────────────────────────────

function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, 'icon.png')).resize({ width: 16, height: 16 });
  tray = new Tray(icon);
  tray.setToolTip('Second Brain');

  const menu = Menu.buildFromTemplate([
    { label: 'Open Second Brain', click: () => mainWindow ? mainWindow.show() : createMainWindow() },
    { type: 'separator' },
    {
      label: 'Auto-start with Windows', type: 'checkbox', checked: true,
      click: (m) => app.setLoginItemSettings({ openAtLogin: m.checked }),
    },
    { type: 'separator' },
    { label: 'Restart Backend', click: () => { if (pythonProcess) pythonProcess.kill(); } },
    { type: 'separator' },
    { label: 'Quit', click: () => { isQuitting = true; app.quit(); } },
  ]);

  tray.setContextMenu(menu);
  tray.on('double-click', () => mainWindow ? mainWindow.show() : createMainWindow());
}

// ── App Lifecycle ──────────────────────────────────────────────

app.whenReady().then(async () => {
  registerAppProtocol();
  createTray();

  const loadingWin = createLoadingWindow();

  startBackend();
  const ready = await waitForPort();

  if (loadingWin && !loadingWin.isDestroyed()) loadingWin.close();

  if (ready) {
    console.log('[App] Backend ready');
    createMainWindow();
  } else {
    dialog.showErrorBox(
      'Startup Error',
      'Could not connect to the Python backend. Make sure Python is installed with all dependencies in .venv/'
    );
    createMainWindow(); // show anyway, frontend will show connection error
  }
});

app.on('before-quit', () => { isQuitting = true; });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

app.on('will-quit', () => {
  if (pythonProcess) { pythonProcess.kill(); pythonProcess = null; }
  if (tray) { tray.destroy(); tray = null; }
});
