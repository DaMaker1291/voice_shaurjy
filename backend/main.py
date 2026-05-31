"""FastAPI — document uploads, text chat, LiveKit tokens, system health."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import TextQuery, DocumentUpload, LicenseActivate, LiveKitTokenRequest, ReminderCreate, ReminderUpdate, TaskRespond
from document_processor import process_upload
from rag_engine import index_document, has_documents, count_chunks
from billing import get_tier, activate_license, is_premium
from ai_agent import generate_response, _load as _load_llm
from reminders import create_reminder, list_reminders, update_reminder, delete_reminder

load_dotenv()

app = FastAPI(title="Second Brain API", version="1.0.0")


@app.on_event("startup")
async def warmup():
    print("Pre-loading LLM (this may take ~30s on first run)...")
    import threading
    threading.Thread(target=_load_llm, daemon=True).start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    livekit_url = os.getenv("LIVEKIT_URL", "")
    return {
        "status": "ok",
        "assistant": "jason",
        "tier": get_tier(),
        "livekit": bool(livekit_url),
        "livekit_url": livekit_url,
        "models": {
            "llm": "Qwen2.5-0.5B-Instruct (float32)",
            "stt": "faster-whisper tiny.en",
            "tts": "Piper lessac-medium",
            "embed": "bge-small-en-v1.5",
        },
    }


@app.post("/api/text/chat")
async def text_chat(query: TextQuery):
    from reminders import create_reminder

    tier = get_tier() if not query.tier else query.tier
    result = generate_response(query.user_id, query.text, tier)

    # Auto-create reminder if detected
    reminder_data = result.get("reminder")
    if reminder_data:
        r = create_reminder(
            query.user_id,
            reminder_data["title"],
            reminder_data.get("description", ""),
            reminder_data.get("due_date", ""),
        )
        result["reminder"] = {"id": r["id"], "title": r["title"], "due_date": r["due_date"]}

    return result


@app.post("/api/task/respond")
async def task_respond(req: TaskRespond):
    from backend.orchestrator import continue_task

    result = continue_task(req.session_id, req.response)
    return result


@app.post("/api/documents/upload")
async def upload_document(doc: DocumentUpload):
    try:
        chunks = process_upload(doc.file_name, doc.file_type, doc.content_b64)
        index_document(doc.user_id, chunks)
        return {"status": "ok", "chunks": len(chunks)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/documents/has")
async def document_status(user_id: str):
    return {
        "has_documents": has_documents(user_id),
        "chunk_count": count_chunks(user_id),
    }


@app.post("/api/license/activate")
async def license_activate(req: LicenseActivate):
    result = activate_license(req.key)
    if result == "invalid":
        raise HTTPException(400, "Invalid license key")
    return {"tier": result}


@app.get("/api/license/status")
async def license_status():
    return {"tier": get_tier(), "is_premium": is_premium()}


# ── Reminders ─────────────────────────────────────────────────

@app.post("/api/reminders")
async def reminder_create(req: ReminderCreate):
    r = create_reminder(req.user_id, req.title, req.description, req.due_date)
    return {"reminder": r}


@app.get("/api/reminders")
async def reminder_list(user_id: str = "local"):
    return {"reminders": list_reminders(user_id)}


@app.patch("/api/reminders/{reminder_id}")
async def reminder_update(reminder_id: str, req: ReminderUpdate):
    r = update_reminder(reminder_id, req.model_dump(exclude_none=True))
    if not r:
        raise HTTPException(404, "Reminder not found")
    return {"reminder": r}


@app.delete("/api/reminders/{reminder_id}")
async def reminder_delete(reminder_id: str):
    if not delete_reminder(reminder_id):
        raise HTTPException(404, "Reminder not found")
    return {"status": "ok"}


# ── LiveKit token endpoint ────────────────────────────────────

@app.post("/api/livekit/token")
async def livekit_token(req: LiveKitTokenRequest):
    from livekit.api import AccessToken, VideoGrants

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise HTTPException(400, "LiveKit not configured on server")

    token = AccessToken(api_key, api_secret)
    token.identity = req.identity or "second-brain-user"
    token.add_grant(VideoGrants(room_join=True, room=req.room_name or "second-brain"))
    return {"token": token.jwt, "url": os.getenv("LIVEKIT_URL")}


# ── Text-to-Speech via edge-tts ───────────────────────────────

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    import edge_tts
    import tempfile
    from fastapi.responses import FileResponse

    communicate = edge_tts.Communicate(req.text, req.voice)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()

    await communicate.save(tmp_path)
    return FileResponse(tmp_path, media_type="audio/mpeg", headers={"Content-Disposition": "inline"})
