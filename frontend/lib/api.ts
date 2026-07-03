function getBaseURL(): string {
  if (typeof window === "undefined") return "http://localhost:8000";
  const custom = localStorage.getItem("backend_url");
  if (custom) return custom;
  if ((window as any).electronAPI?.backendURL) return (window as any).electronAPI.backendURL;
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  }
  return "https://dgfhgjhj-jarvis-ai-brain.hf.space";
}

export const BASE = getBaseURL();

export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function textChat(text: string, userId = "local", tier = "free") {
  const res = await fetch(`${BASE}/api/text/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, user_id: userId, tier }),
  });
  if (!res.ok) throw new Error("text chat failed");
  return res.json();
}

export async function getLiveKitToken(identity = "second-brain-user", roomName = "second-brain") {
  const res = await fetch(`${BASE}/api/livekit/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identity, room_name: roomName }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function uploadDocument(
  fileName: string,
  fileType: string,
  contentB64: string,
  userId = "local"
) {
  const res = await fetch(`${BASE}/api/documents/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, file_name: fileName, file_type: fileType, content_b64: contentB64 }),
  });
  return res.json();
}

export async function getDocuments(userId = "local") {
  const res = await fetch(`${BASE}/api/documents/has?user_id=${userId}`);
  return res.json();
}

export async function createReminder(title: string, description = "", dueDate = "", userId = "local") {
  const res = await fetch(`${BASE}/api/reminders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, title, description, due_date: dueDate }),
  });
  return res.json();
}

export async function listReminders(userId = "local") {
  const res = await fetch(`${BASE}/api/reminders?user_id=${userId}`);
  return res.json();
}

export async function updateReminder(id: string, updates: Record<string, unknown>) {
  const res = await fetch(`${BASE}/api/reminders/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function deleteReminder(id: string) {
  const res = await fetch(`${BASE}/api/reminders/${id}`, { method: "DELETE" });
  return res.json();
}

// ── Entity API ────────────────────────────────────────────────────

export async function entityProcess(text: string, userId = "local") {
  const res = await fetch(`${BASE}/api/entity/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_input: text, user_id: userId }),
  });
  return res.json();
}

export async function getEntityState(userId = "local") {
  const res = await fetch(`${BASE}/api/entity/state?user_id=${userId}`);
  return res.json();
}

export async function getEntityGoals(userId = "local") {
  const res = await fetch(`${BASE}/api/entity/goals?user_id=${userId}`);
  return res.json();
}

export async function generateStrategies(text: string, userId = "local") {
  const res = await fetch(`${BASE}/api/entity/strategies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_input: text, user_id: userId }),
  });
  return res.json();
}

// ── Workflow API ──────────────────────────────────────────────────

export async function startWorkflow(task: string, userId = "local") {
  const res = await fetch(`${BASE}/api/workflow/start?task=${encodeURIComponent(task)}&user_id=${userId}`, { method: "POST" });
  return res.json();
}

export async function advanceWorkflow(executionId: string, userInput = "") {
  const res = await fetch(`${BASE}/api/workflow/advance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ execution_id: executionId, user_input: userInput }),
  });
  return res.json();
}

export async function getWorkflowStatus(executionId: string) {
  const res = await fetch(`${BASE}/api/workflow/status?execution_id=${executionId}`);
  return res.json();
}

// ── System API ────────────────────────────────────────────────────

export async function getSystemStats() {
  const res = await fetch(`${BASE}/api/system/stats`);
  return res.json();
}

export async function getSystemProcesses(top = 15) {
  const res = await fetch(`${BASE}/api/system/processes?top=${top}`);
  return res.json();
}

export async function getSystemInfo() {
  const res = await fetch(`${BASE}/api/system/info`);
  return res.json();
}

export async function getClipboard() {
  const res = await fetch(`${BASE}/api/clipboard`);
  return res.json();
}

export async function setClipboard(text: string) {
  const res = await fetch(`${BASE}/api/clipboard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return res.json();
}

export async function getMediaNowPlaying() {
  const res = await fetch(`${BASE}/api/media/nowplaying`);
  return res.json();
}

export async function sendNotification(message: string, title = "JARVIS") {
  const res = await fetch(`${BASE}/api/notify?title=${encodeURIComponent(title)}&message=${encodeURIComponent(message)}`, { method: "POST" });
  return res.json();
}

export async function listActions() {
  const res = await fetch(`${BASE}/api/actions`);
  return res.json();
}

export async function runAction(actionId: string, params = "") {
  const res = await fetch(`${BASE}/api/actions/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_id: actionId, params }),
  });
  return res.json();
}

export async function takeScreenshot() {
  const res = await fetch(`${BASE}/api/screenshot`, { method: "POST" });
  return res.json();
}

export async function setVolume(level?: number, action?: string) {
  const body: Record<string, unknown> = {};
  if (level !== undefined) body.level = level;
  if (action) body.action = action;
  const res = await fetch(`${BASE}/api/system/volume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ── Computer Agent API ─────────────────────────────────────────

export async function computerRunTask(description: string) {
  const res = await fetch(`${BASE}/api/computer/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: description }),
  });
  return res.json();
}

export async function computerTaskStatus(taskId = "") {
  const res = await fetch(`${BASE}/api/computer/status?task_id=${encodeURIComponent(taskId)}`);
  return res.json();
}

export async function computerStopTask() {
  const res = await fetch(`${BASE}/api/computer/stop`, { method: "POST" });
  return res.json();
}

export async function webSearch(q: string) {
  const res = await fetch(`${BASE}/api/web/search?q=${encodeURIComponent(q)}`);
  return res.json();
}

export async function getWeather(city = "") {
  const res = await fetch(`${BASE}/api/web/weather?city=${encodeURIComponent(city)}`);
  return res.json();
}

export async function setBrightness(level?: number, action?: string) {
  const body: Record<string, unknown> = {};
  if (level !== undefined) body.level = level;
  if (action) body.action = action;
  const res = await fetch(`${BASE}/api/system/brightness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export function setBackendUrl(url: string) {
  localStorage.setItem("backend_url", url);
  window.location.reload();
}

export function getBackendUrl(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("backend_url") || "";
}

export async function relayStatus(relayId: string) {
  const res = await fetch(`${BASE}/api/relay/result?relay_id=${relayId}`);
  return res.json();
}

// ── Agent Command API ──────────────────────────────────────────

export async function issueCommand(command: string, target = "all", params: Record<string, unknown> = {}) {
  const res = await fetch(`${BASE}/api/agent/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, target, params }),
  });
  return res.json();
}

export async function getAgentCommands() {
  const res = await fetch(`${BASE}/api/agent/commands`);
  return res.json();
}

export async function getAgentStatus() {
  const res = await fetch(`${BASE}/api/agent/status`);
  return res.json();
}

// ── Scanner API ────────────────────────────────────────────────

export async function scanQuick() {
  const res = await fetch(`${BASE}/api/scan/quick`);
  return res.json();
}

export async function scanFull() {
  const res = await fetch(`${BASE}/api/scan/full`);
  return res.json();
}

export async function scanWifi() {
  const res = await fetch(`${BASE}/api/scan/wifi`);
  return res.json();
}

export async function scanLan() {
  const res = await fetch(`${BASE}/api/scan/lan`);
  return res.json();
}

export async function scanProcesses() {
  const res = await fetch(`${BASE}/api/scan/processes`);
  return res.json();
}

export async function scanInfo() {
  const res = await fetch(`${BASE}/api/scan/info`);
  return res.json();
}

// ── Propagation API ────────────────────────────────────────────

export async function getPropagationStatus() {
  const res = await fetch(`${BASE}/api/propagation/status`);
  return res.json();
}

export async function getPropagationLogs() {
  const res = await fetch(`${BASE}/api/propagation/logs`);
  return res.json();
}

// ── Smart Home API ──────────────────────────────────────────────

export async function discoverSmartHome() {
  const res = await fetch(`${BASE}/api/smarthome/discover`);
  return res.json();
}

export async function smartHomeControl(ip: string, action: string) {
  const res = await fetch(`${BASE}/api/smarthome/control?ip=${encodeURIComponent(ip)}&action=${encodeURIComponent(action)}`);
  return res.json();
}

export async function controlSmartHomeDevice(ip: string, action: string) {
  const res = await fetch(`${BASE}/api/smarthome/control?ip=${encodeURIComponent(ip)}&action=${encodeURIComponent(action)}`);
  return res.json();
}

export async function getSmartHomeDevices() {
  const res = await fetch(`${BASE}/api/smarthome/devices`);
  return res.json();
}

export async function getSmartHomeScenes() {
  const res = await fetch(`${BASE}/api/smarthome/scenes`);
  return res.json();
}

// ═══════════════════════════════════════════════════════
//  BUSINESS SECRETARY API
// ═══════════════════════════════════════════════════════
export async function configureEmail(smtpServer: string, smtpPort: number, imapServer: string, email: string, password: string) {
  const res = await fetch(`${BASE}/api/business/email/configure`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ smtp_server: smtpServer, smtp_port: smtpPort, imap_server: imapServer, email, password }) }); return res.json();
}
export async function getEmailConfig() { const res = await fetch(`${BASE}/api/business/email/config`); return res.json(); }
export async function getCalendar(day = "") { const res = await fetch(`${BASE}/api/business/calendar?day=${encodeURIComponent(day)}`); return res.json(); }
export async function addCalendarEvent(title: string, date: string, time = "", durationMin = 60, description = "") {
  const res = await fetch(`${BASE}/api/business/calendar/add`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, date, time, duration_min: durationMin, description }) }); return res.json();
}
export async function getCalendarSummary(days = 7) { const res = await fetch(`${BASE}/api/business/calendar/summary?days=${days}`); return res.json(); }
export async function getContacts() { const res = await fetch(`${BASE}/api/business/contacts`); return res.json(); }
export async function addContact(name: string, email: string, phone = "", company = "", notes = "") {
  const res = await fetch(`${BASE}/api/business/contacts/add`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, email, phone, company, notes }) }); return res.json();
}
export async function searchContacts(query: string) { const res = await fetch(`${BASE}/api/business/contacts/search?q=${encodeURIComponent(query)}`); return res.json(); }
export async function webResearch(topic: string, depth = "basic") { const res = await fetch(`${BASE}/api/business/research?topic=${encodeURIComponent(topic)}&depth=${depth}`); return res.json(); }
export async function getBusinessActivity() { const res = await fetch(`${BASE}/api/business/activity`); return res.json(); }
export async function getBusinessSummary() { const res = await fetch(`${BASE}/api/business/summary`); return res.json(); }

// ═══════════════════════════════════════════════════════
//  LIFE OS API
// ═══════════════════════════════════════════════════════
export async function getLifeDashboard() { const res = await fetch(`${BASE}/api/life/dashboard`); return res.json(); }
export async function getLifeMorningBriefing() { const res = await fetch(`${BASE}/api/life/briefing`); return res.json(); }
export async function getLifeFinance() { const res = await fetch(`${BASE}/api/life/finance/balance`); return res.json(); }
export async function addLifeTransaction(amount: number, category: string, description: string, type = "expense") {
  const res = await fetch(`${BASE}/api/life/finance/transaction`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ amount, category, description, type }) }); return res.json();
}
export async function getLifeBudgets() { const res = await fetch(`${BASE}/api/life/finance/budgets`); return res.json(); }
export async function setLifeBudget(category: string, limit: number) {
  const res = await fetch(`${BASE}/api/life/finance/budget`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category, limit }) }); return res.json();
}
export async function getLifeSubscriptions() { const res = await fetch(`${BASE}/api/life/finance/subscriptions`); return res.json(); }
export async function getLifeHealthSummary() { const res = await fetch(`${BASE}/api/life/health/summary`); return res.json(); }
export async function logLifeWorkout(exercise: string, durationMin: number, calories = 0) {
  const res = await fetch(`${BASE}/api/life/health/workout`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ exercise, duration_min: durationMin, calories }) }); return res.json();
}
export async function logLifeMeal(mealType: string, description: string, calories = 0) {
  const res = await fetch(`${BASE}/api/life/health/meal`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ meal_type: mealType, description, calories }) }); return res.json();
}
export async function logLifeSleep(hours: number, quality = 3) {
  const res = await fetch(`${BASE}/api/life/health/sleep`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ hours, quality }) }); return res.json();
}
export async function logLifeWater(ml: number) {
  const res = await fetch(`${BASE}/api/life/health/water`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ml }) }); return res.json();
}
export async function getLifePlanner(date = "") { const res = await fetch(`${BASE}/api/life/planner/tasks?date=${encodeURIComponent(date)}`); return res.json(); }
export async function addLifeTask(title: string, priority = 3, dueDate = "", estimatedMin = 30) {
  const res = await fetch(`${BASE}/api/life/planner/task`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, priority, due_date: dueDate, estimated_min: estimatedMin }) }); return res.json();
}
export async function completeLifeTask(taskId: string) {
  const res = await fetch(`${BASE}/api/life/planner/complete/${taskId}`, { method: "POST" }); return res.json();
}
export async function getLifeHabits() { const res = await fetch(`${BASE}/api/life/habits`); return res.json(); }
export async function logLifeHabit(habitId: string, value = 1) {
  const res = await fetch(`${BASE}/api/life/habits/log`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ habit_id: habitId, value }) }); return res.json();
}
export async function getLifeGoals() { const res = await fetch(`${BASE}/api/life/goals`); return res.json(); }
export async function getLifeJournal(limit = 10) { const res = await fetch(`${BASE}/api/life/journal/recent?limit=${limit}`); return res.json(); }
export async function writeLifeJournal(content: string, tags: string[] = []) {
  const res = await fetch(`${BASE}/api/life/journal`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content, tags }) }); return res.json();
}
export async function getLifeMoodTrend(days = 30) { const res = await fetch(`${BASE}/api/life/mood/trend?days=${days}`); return res.json(); }

// ═══════════════════════════════════════════════════════
//  TRADING API
// ═══════════════════════════════════════════════════════
export async function getTradingPortfolio() { const res = await fetch(`${BASE}/api/trading/portfolio`); return res.json(); }
export async function tradingBuy(symbol: string, shares: number) {
  const res = await fetch(`${BASE}/api/trading/buy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol, shares }) }); return res.json();
}
export async function tradingSell(symbol: string, shares: number) {
  const res = await fetch(`${BASE}/api/trading/sell`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol, shares }) }); return res.json();
}
export async function tradingAnalyze(symbol: string) { const res = await fetch(`${BASE}/api/trading/analyze?symbol=${encodeURIComponent(symbol)}`); return res.json(); }
export async function searchStocks(query: string) { const res = await fetch(`${BASE}/api/trading/search?q=${encodeURIComponent(query)}`); return res.json(); }
export async function getTradingHistory() { const res = await fetch(`${BASE}/api/trading/history`); return res.json(); }
export async function getTradingStrategies() { const res = await fetch(`${BASE}/api/trading/strategies`); return res.json(); }
export async function runTradingStrategy(strategyId: string) {
  const res = await fetch(`${BASE}/api/trading/strategies/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strategy_id: strategyId }) }); return res.json();
}
export async function startAutoTrading(intervalMin = 60) {
  const res = await fetch(`${BASE}/api/trading/auto/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interval_min: intervalMin }) }); return res.json();
}
export async function stopAutoTrading() { const res = await fetch(`${BASE}/api/trading/auto/stop`, { method: "POST" }); return res.json(); }
export async function getTradingMarketData() { const res = await fetch(`${BASE}/api/trading/market`); return res.json(); }

// ═══════════════════════════════════════════════════════
//  PLUGIN MARKETPLACE API
// ═══════════════════════════════════════════════════════
export async function getMarketplacePlugins(category = "") { const res = await fetch(`${BASE}/api/marketplace/plugins?category=${encodeURIComponent(category)}`); return res.json(); }
export async function installPlugin(pluginId: string) {
  const res = await fetch(`${BASE}/api/marketplace/install`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plugin_id: pluginId }) }); return res.json();
}
export async function getInstalledPlugins() { const res = await fetch(`${BASE}/api/marketplace/installed`); return res.json(); }
export async function publishPlugin(name: string, description: string, version: string, price = 0) {
  const res = await fetch(`${BASE}/api/marketplace/publish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, description, version, price }) }); return res.json();
}

// ═══════════════════════════════════════════════════════
//  SMART HOME API (extended)
// ═══════════════════════════════════════════════════════
export async function activateSmartHomeScene(name: string) {
  const res = await fetch(`${BASE}/api/smarthome/scenes/activate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }); return res.json();
}

// ═══════════════════════════════════════════════════════
//  DEVICE HUB, MONEY ENGINE, JARVIS CORE, SCANNING
// ═══════════════════════════════════════════════════════
export async function deviceHubDiscover() { const res = await fetch(`${BASE}/api/devices/discover`, { method: "POST" }); return res.json(); }
export async function deviceHubStats() { const res = await fetch(`${BASE}/api/devices/stats`); return res.json(); }
export async function moneyBalance() { const res = await fetch(`${BASE}/api/money/balance`); return res.json(); }
export async function moneyHistory(limit = 20) { const res = await fetch(`${BASE}/api/money/history?limit=${limit}`); return res.json(); }
export async function getJarvisStatus() { const res = await fetch(`${BASE}/api/jarvis/status`); return res.json(); }
export async function getJarvisHUD() { const res = await fetch(`${BASE}/api/jarvis/hud`); return res.json(); }
export async function getJarvisThoughts() { const res = await fetch(`${BASE}/api/jarvis/thoughts`); return res.json(); }
export async function scanLAN() { const res = await fetch(`${BASE}/api/scan/lan`); return res.json(); }
