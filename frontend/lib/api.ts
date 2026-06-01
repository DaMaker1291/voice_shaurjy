const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export async function getWorkflowTemplates() {
  const res = await fetch(`${BASE}/api/workflow/templates`);
  return res.json();
}

export async function startWorkflow(templateId: string, task = "", userId = "local") {
  const res = await fetch(`${BASE}/api/workflow/start?template_id=${templateId}&task=${encodeURIComponent(task)}&user_id=${userId}`, { method: "POST" });
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
