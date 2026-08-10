/**
 * JARVIS — Electron Preload Script
 * Exposes safe IPC bridges to the renderer process.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jarvis", {
  // ── Window Controls ──
  window: {
    minimize: () => ipcRenderer.send("window-minimize"),
    maximize: () => ipcRenderer.send("window-maximize"),
    close: () => ipcRenderer.send("window-close"),
    isMaximized: () => ipcRenderer.invoke("window-is-maximized"),
  },

  // ── Overlay ──
  hideOverlay: () => ipcRenderer.send("overlay-hide"),
  executeOverlay: (command) => ipcRenderer.send("overlay-execute", command),
  onOverlayFocus: (cb) => ipcRenderer.on("overlay-focus", () => cb()),

  // ── Backend ──
  backend: {
    status: () => ipcRenderer.invoke("backend-status"),
    restart: () => ipcRenderer.invoke("backend-restart"),
    onStatus: (cb) => ipcRenderer.on("backend-status", (_, data) => cb(data)),
  },

  // ── Deployment URL (from env) ──
  deploymentUrl: () => ipcRenderer.invoke("get-deployment-url"),

  // ── System Info ──
  system: {
    info: () => ipcRenderer.invoke("get-system-info"),
  },

  // ── Clipboard ──
  clipboard: {
    read: () => ipcRenderer.invoke("clipboard-read"),
    write: (text) => ipcRenderer.invoke("clipboard-write", text),
  },

  // ── Notifications ──
  notify: (title, body, options = {}) => {
    ipcRenderer.send("notify", { title, body, ...options });
  },

  // ── Shell ──
  shell: {
    openExternal: (url) => ipcRenderer.invoke("open-external", url),
    openPath: (p) => ipcRenderer.invoke("open-path", p),
  },

  // ── File Dialogs ──
  dialog: {
    open: (options) => ipcRenderer.invoke("dialog-open", options),
    save: (options) => ipcRenderer.invoke("dialog-save", options),
  },

  // ── Auto Launch ──
  autoLaunch: {
    get: () => ipcRenderer.invoke("auto-launch-get"),
    set: (enabled) => ipcRenderer.invoke("auto-launch-set", enabled),
  },

  // ── PiP Window ──
  pip: {
    toggle: () => ipcRenderer.send("pip-show"),
    show: () => ipcRenderer.send("pip-show"),
    onFrameRaw: (cb) => ipcRenderer.on("pip-frame-raw", (_, data) => cb(data)),
    onFrame: (cb) => ipcRenderer.on("pip-frame", (_, data) => cb(data)),
  },

  // ── App Control ──
  quit: () => ipcRenderer.send("app-quit"),
});
