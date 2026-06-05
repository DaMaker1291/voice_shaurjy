const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let tray = null;
let pythonProcess = null;
let isQuitting = false;

const BACKEND_PORT = 8000;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

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
  const backendDir = path.join(__dirname, '..', 'backend');
  const args = ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)];

  pythonProcess = spawn(python, args, {
    cwd: path.join(__dirname, '..'),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONPATH: path.join(__dirname, '..') },
  });

  pythonProcess.stdout.on('data', (d) => {
    const text = d.toString();
    process.stdout.write(`[Backend] ${text}`);
  });

  pythonProcess.stderr.on('data', (d) => {
    const text = d.toString();
    process.stderr.write(`[Backend] ${text}`);
  });

  pythonProcess.on('exit', (code) => {
    console.log(`[Backend] exited with code ${code}`);
    if (!isQuitting) {
      console.log('[Backend] Restarting in 2s...');
      setTimeout(startBackend, 2000);
    }
  });
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = (n) => {
      http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else if (n > 0) setTimeout(() => check(n - 1), 500);
        else reject(new Error('Backend did not start'));
      }).on('error', () => {
        if (n > 0) setTimeout(() => check(n - 1), 500);
        else reject(new Error('Backend did not start'));
      });
    };
    check(retries);
  });
}

// ── App Window ─────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: path.join(__dirname, 'icon.png'),
    title: 'Second Brain',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    backgroundColor: '#05081a',
    show: false,
  });

  mainWindow.loadURL(BACKEND_URL);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

// ── System Tray ────────────────────────────────────────────────

function createTray() {
  const iconPath = path.join(__dirname, 'icon.png');
  const icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  tray = new Tray(icon);
  tray.setToolTip('Second Brain');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open Second Brain', click: () => { if (mainWindow) mainWindow.show(); else createWindow(); } },
    { type: 'separator' },
    { label: 'Auto-start with Windows', type: 'checkbox', checked: true, click: (m) => { app.setLoginItemSettings({ openAtLogin: m.checked }); } },
    { type: 'separator' },
    { label: 'Restart Backend', click: () => { if (pythonProcess) { pythonProcess.kill(); } } },
    { type: 'separator' },
    { label: 'Quit', click: () => { isQuitting = true; app.quit(); } },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => { if (mainWindow) mainWindow.show(); else createWindow(); });
}

// ── App Lifecycle ──────────────────────────────────────────────

app.whenReady().then(async () => {
  startBackend();
  createTray();

  try {
    await waitForBackend();
    console.log('[App] Backend ready');
    createWindow();
  } catch (e) {
    console.error('[App] Backend failed to start:', e.message);
    dialog.showErrorBox('Backend Error', 'Failed to start the Python backend. Make sure Python is installed with all dependencies.');
  }

  app.on('activate', () => { if (mainWindow) mainWindow.show(); else createWindow(); });
});

app.on('before-quit', () => { isQuitting = true; });

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
  if (tray) { tray.destroy(); tray = null; }
});
