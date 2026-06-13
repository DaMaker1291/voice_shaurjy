function getBaseURL(): string {
  if (typeof window === "undefined") return "http://localhost:8000";
  const custom = localStorage.getItem("backend_url");
  if (custom) return custom;
  if ((window as any).electronAPI?.backendURL) return (window as any).electronAPI.backendURL;
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  }
  return "https://dgfhgjhj-my-actual-brain.hf.space";
}

const BASE = getBaseURL();

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

export async function sendNotification(message: string, title = "Jason") {
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
