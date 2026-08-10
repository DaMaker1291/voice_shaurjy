// JARVIS Browser Bridge — Background Service Worker
// Connects to Python backend via Chrome Native Messaging
// Controls the user's REAL browser tabs without opening new profiles

let nativePort = null;
let connected = false;

// ── Native Messaging Connection ──────────────────────────────────
function connectNative() {
  try {
    nativePort = chrome.runtime.connectNative("com.jarvis.browser_bridge");
    connected = true;

    nativePort.onMessage.addListener((msg) => {
      handleCommand(msg);
    });

    nativePort.onDisconnect.addListener(() => {
      connected = false;
      console.log("[JARVIS] Native port disconnected, reconnecting...");
      setTimeout(connectNative, 3000);
    });

    // Announce connection
    nativePort.postMessage({ type: "connected", browser: "chrome" });
  } catch (e) {
    console.log("[JARVIS] Native connect failed:", e.message);
    connected = false;
    setTimeout(connectNative, 5000);
  }
}

// ── Command Handler ──────────────────────────────────────────────
async function handleCommand(cmd) {
  const { action, id, params } = cmd;
  let result = {};

  try {
    switch (action) {
      case "list_tabs":
        result = await listTabs();
        break;
      case "get_tab":
        result = await getTab(params.tabId);
        break;
      case "switch_tab":
        result = await switchTab(params.tabId);
        break;
      case "close_tab":
        result = await closeTab(params.tabId);
        break;
      case "open_url":
        result = await openUrl(params.url);
        break;
      case "execute_js":
        result = await executeJS(params.tabId, params.code);
        break;
      case "get_page_content":
        result = await getPageContent(params.tabId);
        break;
      case "search_tabs":
        result = await searchTabs(params.query);
        break;
      case "click_element":
        result = await clickElement(params.tabId, params.selector);
        break;
      case "type_in_tab":
        result = await typeInTab(params.tabId, params.text, params.selector);
        break;
      case "get_all_urls":
        result = await getAllUrls();
        break;
      case "screenshot_tab":
        result = await screenshotTab(params.tabId);
        break;
      default:
        result = { error: `Unknown action: ${action}` };
    }
  } catch (e) {
    result = { error: e.message };
  }

  // Send result back to Python
  if (nativePort && connected) {
    nativePort.postMessage({ type: "result", id: id, data: result });
  }
}

// ── Tab Operations ───────────────────────────────────────────────
async function listTabs() {
  const tabs = await chrome.tabs.query({});
  return {
    tabs: tabs.map((t) => ({
      id: t.id,
      title: t.title,
      url: t.url,
      active: t.active,
      windowId: t.windowId,
      favIconUrl: t.favIconUrl,
      status: t.status,
    })),
    count: tabs.length,
  };
}

async function getTab(tabId) {
  const tab = await chrome.tabs.get(tabId);
  return {
    id: tab.id,
    title: tab.title,
    url: tab.url,
    active: tab.active,
    windowId: tab.windowId,
    status: tab.status,
  };
}

async function switchTab(tabId) {
  const tab = await chrome.tabs.update(tabId, { active: true });
  await chrome.windows.update(tab.windowId, { focused: true });
  return { success: true, tabId: tab.id, title: tab.title };
}

async function closeTab(tabId) {
  await chrome.tabs.remove(tabId);
  return { success: true };
}

async function openUrl(url) {
  const tab = await chrome.tabs.create({ url: url, active: false });
  return { success: true, tabId: tab.id, url: url };
}

async function executeJS(tabId, code) {
  const results = await chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: (codeStr) => {
      try {
        return { result: eval(codeStr), error: null };
      } catch (e) {
        return { result: null, error: e.message };
      }
    },
    args: [code],
  });
  return results[0]?.result || { result: null, error: "No result" };
}

async function getPageContent(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: () => {
      return {
        title: document.title,
        url: window.location.href,
        text: document.body?.innerText?.substring(0, 50000) || "",
        html: document.body?.innerHTML?.substring(0, 50000) || "",
        forms: Array.from(document.forms).map((f) => ({
          action: f.action,
          method: f.method,
          fields: Array.from(f.elements).map((e) => ({
            name: e.name,
            type: e.type,
            value: e.value,
          })),
        })),
        links: Array.from(document.querySelectorAll("a[href]"))
          .slice(0, 200)
          .map((a) => ({
            text: a.innerText.trim().substring(0, 100),
            href: a.href,
          })),
      };
    },
  });
  return results[0]?.result || { error: "Could not get content" };
}

async function searchTabs(query) {
  const tabs = await chrome.tabs.query({});
  const q = query.toLowerCase();
  return {
    tabs: tabs
      .filter(
        (t) =>
          (t.title && t.title.toLowerCase().includes(q)) ||
          (t.url && t.url.toLowerCase().includes(q))
      )
      .map((t) => ({
        id: t.id,
        title: t.title,
        url: t.url,
        active: t.active,
      })),
  };
}

async function clickElement(tabId, selector) {
  const results = await chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: (sel) => {
      const el = document.querySelector(sel);
      if (!el) return { error: `Element not found: ${sel}` };
      el.click();
      return { success: true, tag: el.tagName, text: el.innerText?.substring(0, 100) };
    },
    args: [selector],
  });
  return results[0]?.result || { error: "No result" };
}

async function typeInTab(tabId, text, selector) {
  const results = await chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: (sel, txt) => {
      const el = sel ? document.querySelector(sel) : document.activeElement;
      if (!el) return { error: `Element not found: ${sel || "active"}` };
      el.focus();
      el.value = txt;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return { success: true };
    },
    args: [selector, text],
  });
  return results[0]?.result || { error: "No result" };
}

async function getAllUrls() {
  const tabs = await chrome.tabs.query({});
  return {
    urls: tabs.map((t) => t.url).filter((u) => u && !u.startsWith("chrome://")),
    count: tabs.length,
  };
}

async function screenshotTab(tabId) {
  // Use chrome.debugger to capture screenshot
  return { error: "Screenshot requires debugger attachment" };
}

// ── Initialize ───────────────────────────────────────────────────
connectNative();
