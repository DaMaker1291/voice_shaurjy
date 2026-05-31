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
