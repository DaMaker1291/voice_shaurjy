"""JARVIS — The System Engine.

Hugging Face Space: Autonomous ecosystem orchestrator with voice-first AI,
system control, smart home, and web automation.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import TextQuery, DocumentUpload, LicenseActivate, LiveKitTokenRequest, ReminderCreate, ReminderUpdate, TaskRespond
from document_processor import process_upload
from rag_engine import index_document, has_documents, count_chunks
from billing import get_tier, activate_license, is_premium
from ai_agent import generate_response

load_dotenv()

app = FastAPI(title="JARVIS — The System Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return RedirectResponse(url="/voice_shaurjy/")

@app.get("/relay_agent")
@app.get("/relay")
async def relay_download():
    fp = os.path.join(os.path.dirname(__file__), "..", "standalone_relay.py")
    if os.path.isfile(fp):
        from fastapi.responses import FileResponse
        return FileResponse(fp, media_type="text/plain", filename="relay.py")
    # fallback to old location
    fp2 = os.path.join(os.path.dirname(__file__), "..", "relay_agent.py")
    if os.path.isfile(fp2):
        from fastapi.responses import FileResponse
        return FileResponse(fp2, media_type="text/plain", filename="relay_agent.py")
    return {"error": "Relay agent not found"}

@app.get("/health")
async def health():
    livekit_url = os.getenv("LIVEKIT_URL", "")
    return {
        "status": "ok",
        "assistant": "jarvis",
        "tier": get_tier(),
        "livekit": bool(livekit_url),
        "livekit_url": livekit_url,
        "models": {
            "llm": "Groq Llama3-70B (cloud, instant)",
            "stt": "Web Speech API",
            "tts": "edge-tts AriaNeural",
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
    # Handle launch preference questions (app vs browser)
    if req.session_id.startswith("launch_"):
        from actions import cloud_safe_execute, relay_action, _ACTION_LABELS
        from entity_engine import get_entity
        action_name = req.session_id[7:]  # remove "launch_" prefix
        ans = req.response.strip().lower()
        if ans in ("app", "native", "desktop", "native app", "in the app", "in app"):
            entity = get_entity(req.user_id or "local")
            entity.memory.add_preference(f"launch_{action_name}", "app")
            # App requires relay — force relay check (bypass cloud-safe)
            result = relay_action(action_name, req.response, user_id=req.user_id or "local")
            if "__NEEDS_RELAY__" in result:
                return {"type": "ask", "question": "Relay agent is offline. Start J.A.R.V.I.S. Relay on your desktop:\n  curl -O https://dgfhgjhj-jarvis-ai-brain.hf.space/relay\n  python3 relay --user yourname\nRun that on your machine, then ask me again.", "session_id": req.session_id}
            if result.startswith("__RELAY__:"):
                parts = result.split(":", 2)
                relay_id = parts[1] if len(parts) > 1 else ""
                return {"type": "complete", "text": f"Saved! I'll use the app for that next time. Queued on your computer...", "async": True, "relay_id": relay_id}
            return {"type": "complete", "text": f"Saved! I'll use the app for that next time.\n{result}\n\n(If it didn't open, the relay agent may need to be started on your machine.)"}
        else:
            # Browser — save preference and return a link the user can open
            entity = get_entity(req.user_id or "local")
            entity.memory.add_preference(f"launch_{action_name}", "browser")
            BROWSER_URLS = {
                "spotify": "https://open.spotify.com",
                "whatsapp_open": "https://web.whatsapp.com",
                "web_app_open": "https://",
                "teams_open": "https://teams.microsoft.com",
            }
            url = BROWSER_URLS.get(action_name, "")
            if url:
                return {"type": "complete", "text": f"Opening {action_name} in your browser...", "link": url}
            # Fallback: try server-side execution
            result = cloud_safe_execute(action_name, req.response, user_id=req.user_id or "local")
            return {"type": "complete", "text": f"Opening in your browser...\n{result}"}

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
    from reminders import list_reminders
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
    token.identity = req.identity or "jarvis-user"
    token.add_grant(VideoGrants(room_join=True, room=req.room_name or "jarvis"))
    return {"token": token.jwt, "url": os.getenv("LIVEKIT_URL")}


# ── Text-to-Speech via edge-tts (streaming) ───────────────────

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-GB-RyanNeural"

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    from fastapi.responses import StreamingResponse, Response
    import io, asyncio, re

    text = req.text
    voice = req.voice or "en-GB-RyanNeural"

    # Strip emoji and special chars that cause TTS issues
    text_clean = re.sub(r'[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF\uFE00-\uFE0F]', '', text)
    text_clean = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text_clean)
    text_clean = re.sub(r'[-_#>`|]', ' ', text_clean)
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()

    if not text_clean:
        text_clean = "Done."

    # Try edge_tts with plain text (avoid SSML — causes XML tag reading on some voices)
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text_clean, voice)

        async def stream():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(stream(), media_type="audio/mpeg")
    except Exception:
        pass

    # Fallback: browser speech synthesis (handled client-side)
    return Response(content="TTS unavailable on server", status_code=503, media_type="text/plain")


# ── Device scanner ───────────────────────────────────────────

@app.post("/api/device/scan")
async def device_scan(user_id: str = "local"):
    if os.name != "nt":
        # On cloud — queue a relay scan for the local agent to pick up
        from relay import queue_action
        queue_action("device_scan", "", user_id)
        return {"status": "queued", "message": "Scan queued on your Windows PC via relay agent"}
    # Running locally — scan directly
    from device_scanner import scan_device
    data = scan_device(user_id, force=True)
    try:
        from user_profile import load_profile, save_profile, merge_device_data
        p = load_profile(user_id)
        merge_device_data(p, data)
        save_profile(user_id, p)
    except:
        pass
    return {"status": "ok", "scan_time": data.get("scan_time", "")}


# ── User profile ─────────────────────────────────────────────

@app.get("/api/profile")
async def get_profile(user_id: str = "local"):
    from user_profile import load_profile, generate_summary

    profile = load_profile(user_id)
    summary = generate_summary(user_id)
    return {"profile": profile, "summary": summary}


@app.delete("/api/profile")
async def reset_profile(user_id: str = "local"):
    from user_profile import save_profile, _default_profile

    save_profile(user_id, _default_profile())
    return {"status": "ok"}


# ── Autonomous task execution with SSE streaming ─────────────

from fastapi.responses import StreamingResponse
import json

from pydantic import BaseModel


class StrategyRequest(BaseModel):
    user_input: str
    user_id: str = "local"


class WorkflowAdvanceRequest(BaseModel):
    execution_id: str
    user_input: str = None
    user_id: str = "local"


# ── Entity Engine Endpoints ────────────────────────────────────────

@app.post("/api/entity/process")
async def entity_process(req: StrategyRequest):
    from entity_engine import get_entity
    entity = get_entity(req.user_id)
    result = entity.process(req.user_input)
    return result


@app.get("/api/entity/state")
async def entity_state(user_id: str = "local"):
    from entity_engine import get_entity
    entity = get_entity(user_id)
    return entity.get_state()


@app.get("/api/entity/goals")
async def entity_goals(user_id: str = "local"):
    from entity_engine import get_entity
    entity = get_entity(user_id)
    return {"goals": entity.memory.get_active_goals()}


@app.post("/api/entity/goals")
async def entity_add_goal(goal: str, priority: int = 5, user_id: str = "local"):
    from entity_engine import get_entity
    entity = get_entity(user_id)
    entity.memory.add_goal(goal, priority)
    return {"status": "ok", "goal": goal}


@app.post("/api/entity/goals/complete")
async def entity_complete_goal(goal: str, user_id: str = "local"):
    from entity_engine import get_entity
    entity = get_entity(user_id)
    entity.memory.complete_goal(goal)
    return {"status": "ok", "goal": goal}


@app.post("/api/entity/strategies")
async def generate_strategies_endpoint(req: StrategyRequest):
    from entity_engine import generate_strategies
    from entity_engine import get_entity
    entity = get_entity(req.user_id)
    strategies = generate_strategies(req.user_input, {
        "memory_summary": entity.memory.get_summary(),
        "active_goals": entity.memory.get_active_goals(),
    })
    return strategies


@app.get("/api/entity/memory")
async def entity_memory(user_id: str = "local"):
    from entity_engine import get_entity
    entity = get_entity(user_id)
    return {"memory_summary": entity.memory.get_summary()}


# ── Workflow Engine Endpoints ──────────────────────────────────────

@app.post("/api/workflow/start")
async def start_workflow(task: str, user_id: str = "local"):
    from workflow_engine import get_engine
    from entity_engine import get_entity
    entity = get_entity(user_id)
    engine = get_engine()
    execution = engine.create_workflow(task, {
        "active_goals": entity.memory.get_active_goals(),
        "memory_summary": entity.memory.get_summary(),
        "query": task,
        "user_id": user_id,
    })
    result = engine.advance(execution.execution_id, action_executor=_exec_action)
    return {
        "execution_id": execution.execution_id,
        "workflow": execution.workflow.to_dict(),
        "result": result,
    }


@app.post("/api/workflow/advance")
async def advance_workflow(req: WorkflowAdvanceRequest):
    from workflow_engine import get_engine
    engine = get_engine()
    result = engine.advance(req.execution_id, req.user_input, action_executor=_exec_action)
    return result


@app.get("/api/workflow/status")
async def workflow_status(execution_id: str):
    from workflow_engine import get_engine
    engine = get_engine()
    execution = engine.get_execution(execution_id)
    if not execution:
        return {"error": "Execution not found"}
    return execution.to_dict()


@app.get("/api/workflow/list")
async def list_executions():
    from workflow_engine import get_engine
    engine = get_engine()
    return {"executions": engine.list_executions()}


@app.post("/api/task/execute")
async def execute_task_stream(task: str, user_id: str = "local"):
    async def event_stream():
        from task_agent import execute_task as run_task
        for event in run_task(task):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _exec_action(action: str, params: str = "") -> str:
    try:
        from actions import execute_action, detect_action
        detected = detect_action(action) or action
        return execute_action(detected, params)
    except Exception as e:
        return f"Error: {e}"


@app.get("/api/task/scenes")
async def list_scenes():
    return {
        "scenes": [
            {"id": "travel", "name": "Travel / Globe", "description": "Rotating globe with flight paths, destination markers, and animated routes"},
            {"id": "document", "name": "Document", "description": "Simulated Word document with typing animation, formatting, and source citations"},
            {"id": "network", "name": "Network", "description": "Network topology graph with devices, connections, and data flow"},
            {"id": "system", "name": "System", "description": "System control viz with terminal, progress bars, and settings panels"},
            {"id": "research", "name": "Research", "description": "Knowledge graph with sources, connections, and insights"},
            {"id": "media", "name": "Media", "description": "Media player / playlist visualization"},
            {"id": "file", "name": "Files", "description": "File system tree with operations animation"},
        ]
    }


# ═══════════════════════════════════════════════════════════════════
# NEW: SYSTEM CONTROL API — structured JSON for rich frontend UIs
# ═══════════════════════════════════════════════════════════════════

class ActionRequest(BaseModel):
    action_id: str
    params: str = ""
    user_id: str = "local"

@ app.get("/api/system/stats")
async def system_stats():
    """Live CPU, RAM, battery, disk, network stats as structured JSON."""
    import psutil, time
    from datetime import datetime
    cpu_pct = psutil.cpu_percent(interval=0.3)
    cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)
    mem = psutil.virtual_memory()
    bat = psutil.sensors_battery()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    boot_ts = psutil.boot_time()
    uptime_h = round((time.time() - boot_ts) / 3600, 1)
    return {
        "cpu": {"percent": cpu_pct, "cores": cpu_per_core, "count": len(cpu_per_core)},
        "memory": {"percent": mem.percent, "used_gb": round(mem.used / 1e9, 1), "total_gb": round(mem.total / 1e9, 1), "free_gb": round(mem.available / 1e9, 1)},
        "battery": {"percent": bat.percent if bat else None, "charging": bat.power_plugged if bat else None, "present": bat is not None},
        "disk": {"percent": disk.percent, "free_gb": round(disk.free / 1e9, 1), "total_gb": round(disk.total / 1e9, 1), "used_gb": round(disk.used / 1e9, 1)},
        "network": {"bytes_sent_mb": round(net.bytes_sent / 1e6, 1), "bytes_recv_mb": round(net.bytes_recv / 1e6, 1)},
        "uptime_h": uptime_h, "boot_time": datetime.fromtimestamp(boot_ts).isoformat(),
    }


@ app.get("/api/system/processes")
async def system_processes(top: int = 15):
    """Top processes by CPU usage."""
    import psutil
    procs = []
    for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]), key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:top]:
        try:
            mi = p.info["memory_info"]
            mem_mb = round(mi.rss / 1e6, 1) if mi else 0
            procs.append({"pid": p.info["pid"], "name": p.info["name"], "cpu": p.info["cpu_percent"] or 0, "mem": round(p.info["memory_percent"] or 0, 1), "mem_mb": mem_mb})
        except: pass
    return {"processes": procs}


@ app.get("/api/system/info")
async def system_info_json():
    """OS, hardware, user info as JSON."""
    from actions import execute_action
    os_line = execute_action("os_info", "")
    cpu_line = execute_action("cpu_usage", "")
    mem_line = execute_action("memory_usage", "")
    return {"os": os_line, "cpu": cpu_line, "memory": mem_line}


@ app.get("/api/clipboard")
async def clipboard_get():
    """Get clipboard content."""
    from actions import execute_action
    text = execute_action("clipboard_show", "")
    return {"text": text.replace("Clipboard: ", "")}


@ app.post("/api/clipboard")
async def clipboard_set(text: str):
    """Set clipboard content."""
    from actions import execute_action
    result = execute_action("clipboard_copy", text)
    return {"status": result}


@ app.get("/api/media/nowplaying")
async def media_nowplaying():
    """Get current media info (uses PS to query)."""
    try:
        from ps_executor import ps as _ps
        info = _ps('''
            $s=New-Object -ComObject "WScript.Shell";
            $s.SendKeys("{MEDIA_INFO}");
            Start-Sleep -Milliseconds 200;
            $t=$s.AppActivate("");  # dummy - media info unreliable via PS
            "Media query sent"
        ''')
        return {"status": "ok", "text": info}
    except: return {"status": "no_media", "text": "No media detected"}


@ app.post("/api/notify")
async def send_notification(title: str = "JARVIS", message: str = ""):
    """Send Windows toast notification."""
    from actions import execute_action
    result = execute_action("send_notification", f"send notification {message}")
    return {"status": result}


@ app.get("/api/actions")
async def list_all_actions():
    """List all available action executors."""
    from actions import get_all_actions
    return {"actions": get_all_actions(), "count": len(get_all_actions())}


@ app.post("/api/actions/run")
async def run_action(req: ActionRequest):
    """Execute any action by ID with optional params."""
    from actions import execute_action, detect_action
    try:
        aid = detect_action(req.action_id) or req.action_id
        text = req.params or req.action_id
        result = execute_action(aid, text)
        return {"status": "ok", "action_id": aid, "result": result}
    except Exception as e:
        return {"status": "error", "action_id": req.action_id, "error": str(e)}


@ app.get("/api/actions/search")
async def action_search(q: str = ""):
    """Search available actions by keyword."""
    from actions import get_all_actions, detect_action
    all_actions = get_all_actions()
    if not q: return {"actions": all_actions, "count": len(all_actions)}
    ql = q.lower()
    matched = {k: v for k, v in all_actions.items() if ql in k or ql in v.get("label", "").lower() or ql in v.get("tip", "").lower()}
    return {"actions": matched, "count": len(matched)}


@ app.post("/api/screenshot")
async def take_screenshot():
    """Take screenshot and return as base64."""
    import base64, os, time
    path = os.path.expanduser("~/Desktop/_jarvis_screenshot.png")
    from actions import execute_action
    result = execute_action("screenshot", "")
    if not os.path.exists(path):
        return {"status": "error", "text": "Screenshot failed"}
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    os.unlink(path)
    return {"status": "ok", "image": b64, "text": result}


@ app.post("/api/system/volume")
async def set_volume(level: int = -1, action: str = ""):
    """Set/get volume. level 0-100, or action: up/down/mute."""
    from actions import execute_action
    if level >= 0:
        result = execute_action("vol_set", str(level))
    elif action == "up":
        result = execute_action("vol_up", "")
    elif action == "down":
        result = execute_action("vol_down", "")
    elif action == "mute":
        result = execute_action("vol_mute", "")
    else:
        result = execute_action("vol_level", "")
    return {"status": "ok", "result": result}


@ app.get("/api/web/search")
async def web_search(q: str = ""):
    """Search the web via DuckDuckGo and return structured results."""
    if not q:
        return {"results": []}
    try:
        import urllib.request, urllib.parse, json
        url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(q)}"
        # Alternative: use a free API
        try:
            req = urllib.request.Request(f"https://api.duckduckgo.com/?q={urllib.parse.quote(q)}&format=json&pretty=1", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                results = []
                if data.get("AbstractText"):
                    results.append({"title": data.get("Heading", q), "snippet": data.get("AbstractText"), "url": data.get("AbstractURL", "")})
                for topic in data.get("RelatedTopics", [])[:8]:
                    if "Text" in topic:
                        results.append({"title": topic.get("Text", "").split(" - ")[0], "snippet": topic.get("Text", ""), "url": topic.get("FirstURL", "")})
                    elif "Topics" in topic:
                        for st in topic["Topics"][:3]:
                            results.append({"title": st.get("Text", "").split(" - ")[0], "snippet": st.get("Text", ""), "url": st.get("FirstURL", "")})
                return {"query": q, "results": results[:10]}
        except:
            pass
        # Fallback: scrape Google
        req = urllib.request.Request(f"https://www.google.com/search?q={urllib.parse.quote(q)}&num=10", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            results = []
            import re
            for m in re.finditer(r'<a[^>]*href="/url\?q=([^"&]+)[^"]*"[^>]*>(.*?)</a>', html)[:10]:
                url = urllib.parse.unquote(m.group(1))
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if title and not url.startswith("http"):
                    continue
                results.append({"title": title[:100], "url": url, "snippet": ""})
            return {"query": q, "results": results[:8]}
    except Exception as e:
        return {"query": q, "results": [], "error": str(e)}


@ app.get("/api/web/weather")
async def web_weather(city: str = ""):
    """Get weather via wttr.in."""
    try:
        import urllib.request, json
        loc = city or "London"
        req = urllib.request.Request(f"https://wttr.in/{urllib.parse.quote(loc)}?format=j1", headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            cc = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]
            return {
                "location": f"{area.get('areaName', [{}])[0].get('value', loc)}, {area.get('country', [{}])[0].get('value', '')}",
                "temp_c": cc.get("temp_C", "?"),
                "temp_f": cc.get("temp_F", "?"),
                "condition": cc.get("weatherDesc", [{}])[0].get("value", "Unknown"),
                "humidity": cc.get("humidity", "?"),
                "wind_kph": cc.get("windspeedKmph", "?"),
                "wind_dir": cc.get("winddir16Point", "?"),
                "feels_like": cc.get("FeelsLikeC", "?"),
                "uv": cc.get("uvIndex", "?"),
                "visibility": cc.get("visibility", "?"),
            }
    except Exception as e:
        return {"error": str(e)}


@ app.post("/api/system/brightness")
async def set_brightness(level: int = -1, action: str = ""):
    """Set/get brightness. level 0-100, or action: up/down."""
    from actions import execute_action
    if level >= 0:
        result = execute_action("brightness_set", str(level))
    elif action == "up":
        result = execute_action("brightness_up", "")
    elif action == "down":
        result = execute_action("brightness_down", "")
    else:
        result = execute_action("display_info", "")
    return {"status": "ok", "result": result}


@app.post("/api/computer/run")
async def computer_run(query: TextQuery):
    """Run a computer-use task (AI sees screen and controls mouse/keyboard)."""
    from screen_agent import start_task_bg, get_task_status
    task_id = start_task_bg(query.text)
    return {"status": "started", "task_id": task_id, "description": query.text}


@app.get("/api/computer/status")
async def computer_status(task_id: str = ""):
    """Get status of a computer-use task."""
    from screen_agent import get_task_status
    return get_task_status(task_id)


@app.post("/api/computer/stop")
async def computer_stop():
    """Stop the current computer-use task (flag-based, thread safe)."""
    from screen_agent import _current_task, _task_lock
    with _task_lock:
        if _current_task:
            _current_task["status"] = "stopped"
            return {"status": "stopped", "task_id": _current_task["id"]}
    return {"status": "no_task"}


# ── Relay bridge (cloud ↔ local Windows agent) ─────────────────

from pydantic import BaseModel


class RelayResult(BaseModel):
    relay_id: str
    result: str
    success: bool = True


@app.post("/api/relay/action")
async def relay_action(req: ActionRequest):
    """Queue a Windows action for the local relay agent to execute."""
    from relay import queue_action
    relay_id = queue_action(req.action_id, req.params, user_id=req.user_id or "local")
    return {"status": "queued", "relay_id": relay_id, "action": req.action_id}


@app.get("/api/relay/pending")
async def relay_pending(user_id: str = "local"):
    """Polled by local agent — returns pending actions for that user (claims atomically)."""
    from relay import claim_next
    actions = []
    while True:
        a = claim_next(user_id=user_id)
        if a is None:
            break
        actions.append(a)
    return {"actions": actions}


@app.post("/api/relay/result")
async def relay_result(req: RelayResult):
    """Local agent posts execution results here."""
    from relay import submit_result
    submit_result(req.relay_id, req.result, req.success)
    return {"status": "ok"}


@app.get("/api/relay/result")
async def relay_get_result(relay_id: str):
    """Frontend or entity polls for result."""
    from relay import get_result
    return get_result(relay_id)


@app.post("/api/relay/execute")
async def relay_execute(req: ActionRequest):
    """Queue AND wait for result (max 30s polling). Used by entity engine."""
    from relay import queue_action, get_result
    import time as _time
    relay_id = queue_action(req.action_id, req.params)
    deadline = _time.time() + 30
    while _time.time() < deadline:
        _time.sleep(0.5)
        res = get_result(relay_id)
        if res["status"] in ("done", "failed", "timeout"):
            return res
    return {"status": "timeout", "result": "Relay agent did not respond within 30s", "relay_id": relay_id}


# ── Agent command dispatch (relay agents poll this) ─────────────

@app.get("/api/agent/pending")
async def agent_pending(target: str = "", user_id: str = "local"):
    """Legacy endpoint — relay agents poll this. Maps to relay system."""
    from relay import claim_next
    actions = []
    while True:
        a = claim_next(user_id=user_id)
        if a is None:
            break
        actions.append(a)
    return {"actions": actions}

@app.post("/api/agent/command")
async def agent_command(data: dict):
    """Dispatch a command to all relay agents for this user."""
    from relay import queue_action
    action = data.get("command", data.get("action", ""))
    params = data.get("params", data.get("text", ""))
    user_id = data.get("user_id", "local")
    target = data.get("target", "all")
    if action:
        relay_id = queue_action(action, params, user_id=user_id)
        return {"status": "queued", "relay_id": relay_id, "action": action, "target": target}
    return {"status": "no_action"}


@app.get("/api/jarvis/command")
async def jarvis_command_get(user_id: str = "local"):
    """Get pending commands for jarvis relay."""
    return await agent_pending(user_id=user_id)

@app.post("/api/jarvis/command")
async def jarvis_command_post(data: dict):
    """Post a command for jarvis relay."""
    return await agent_command(data)


# ── Relay device registration ───────────────────────────────────

_relay_devices: dict[str, dict] = {}


# ── Smart Home API ──────────────────────────────────────────────

@app.get("/api/smarthome/devices")
async def smarthome_devices():
    from smart_home_manager import get_all_devices
    return {"devices": [d.to_dict() for d in get_all_devices()]}

@app.get("/api/smarthome/dashboard")
async def smarthome_dashboard():
    from smart_home_manager import get_dashboard
    return get_dashboard()

@app.post("/api/smarthome/discover")
async def smarthome_discover():
    from smart_home_manager import run_discovery
    devices = run_discovery()
    return {"devices": devices, "count": len(devices)}

@app.get("/api/smarthome/discover")
async def smarthome_discover_get():
    from smart_home_manager import run_discovery
    devices = run_discovery()
    return {"devices": devices, "count": len(devices)}

@app.post("/api/smarthome/control")
async def smarthome_control(data: dict):
    from smart_home_manager import control_device, control_by_ip
    device_id = data.get("device_id", "")
    ip = data.get("ip", "")
    action = data.get("action", "on")
    params = data.get("params", "")
    if device_id:
        result = control_device(device_id, action, params)
    elif ip:
        result = control_by_ip(ip, action, params)
    else:
        return {"error": "Provide device_id or ip"}
    return {"result": result}

@app.get("/api/smarthome/scenes")
async def smarthome_scenes():
    from smart_home_manager import get_scenes
    return {"scenes": get_scenes()}

@app.post("/api/smarthome/scenes/activate")
async def smarthome_scene_activate(data: dict):
    from smart_home_manager import activate_scene
    name = data.get("name", "")
    result = activate_scene(name)
    return {"result": result}

@app.post("/api/smarthome/scenes/create")
async def smarthome_scene_create(data: dict):
    from smart_home_manager import create_scene
    name = data.get("name", "")
    devices = data.get("devices", [])
    scene = create_scene(name, devices)
    return {"scene": scene}

@app.post("/api/smarthome/device/rename")
async def smarthome_device_rename(data: dict):
    from smart_home_manager import get_device, update_device
    device_id = data.get("device_id", "")
    new_name = data.get("name", "")
    room = data.get("room", "")
    dev = get_device(device_id)
    if not dev:
        return {"error": "Device not found"}
    if new_name:
        dev.name = new_name
    if room:
        dev.room = room
    update_device(dev)
    return {"device": dev.to_dict()}

@app.post("/api/smarthome/device/delete")
async def smarthome_device_delete(data: dict):
    from smart_home_manager import delete_device
    device_id = data.get("device_id", "")
    delete_device(device_id)
    return {"deleted": True}

@app.post("/api/relay/register")
async def relay_register(data: dict):
    """Called by relay agent on startup to register this device."""
    from relay import record_heartbeat
    from acc_manager import register_relay_device
    uid = data.get("user_id", "local")
    _relay_devices[uid] = {
        "hostname": data.get("hostname", "?"),
        "platform": data.get("platform", "?"),
        "info": data.get("info", {}),
        "last_seen": __import__("time").time(),
    }
    register_relay_device(uid, {"hostname": data.get("hostname", "?"), "platform": data.get("platform", "?"), "info": data.get("info", {})})
    record_heartbeat(uid)
    return {"status": "registered"}

@app.post("/api/relay/heartbeat")
async def relay_heartbeat(data: dict):
    """Called periodically by relay agent to signal it's alive."""
    from relay import record_heartbeat
    uid = data.get("user_id", "local")
    record_heartbeat(uid)
    return {"status": "ok"}

@app.get("/api/relay/devices")
async def relay_devices(user_id: str = "local"):
    return {"devices": [_relay_devices.get(user_id, {})]}


# ── Autonomous Agent ────────────────────────────────────────────

@app.post("/api/agent/autonomous")
async def start_autonomous(data: dict):
    """Start a complex autonomous task. Returns session_id + plan."""
    from autonomous_agent import start_autonomous_task
    goal = data.get("goal", data.get("text", ""))
    user_id = data.get("user_id", "local")
    if not goal:
        return {"error": "No goal specified"}
    return start_autonomous_task(user_id, goal)

@app.get("/api/agent/autonomous/{session_id}")
async def get_autonomous_status(session_id: str):
    """Get status and results of an autonomous task."""
    from autonomous_agent import _ACTIVE_TASKS
    session = _ACTIVE_TASKS.get(session_id)
    if not session:
        return {"error": "Task not found"}
    return {
        "status": session["status"],
        "goal": session["goal"],
        "step_index": session["step_index"],
        "total_steps": len(session["plan"]),
        "current_step": session.get("current_step", ""),
        "results": session["results"],
        "last_result": session.get("last_result"),
    }

@app.post("/api/agent/autonomous/{session_id}/continue")
async def continue_autonomous(session_id: str, data: dict = {}):
    """Continue an autonomous task (advance to next step, optionally with user input)."""
    from autonomous_agent import continue_autonomous_task
    user_input = data.get("user_input", data.get("response", ""))
    return continue_autonomous_task(session_id, user_input or None)

@app.post("/api/agent/autonomous/{session_id}/cancel")
async def cancel_autonomous(session_id: str):
    """Cancel an autonomous task."""
    from autonomous_agent import _ACTIVE_TASKS
    if session_id in _ACTIVE_TASKS:
        _ACTIVE_TASKS[session_id]["status"] = "cancelled"
        return {"status": "cancelled"}
    return {"error": "Task not found"}

# ── SSE streaming executor ────────────────────────────────────

@app.post("/api/task/stream")
async def stream_task_execution(data: dict):
    """SSE stream: execute a multi-step task with real-time progress."""
    from autonomous_agent import start_autonomous_task, continue_autonomous_task, _ACTIVE_TASKS
    from fastapi.responses import StreamingResponse
    import asyncio

    goal = data.get("goal", data.get("text", ""))
    user_id = data.get("user_id", "local")
    if not goal:
        return {"error": "No goal"}

    result = start_autonomous_task(user_id, goal)
    if "error" in result:
        return result
    session_id = result["session_id"]

    async def event_stream():
        session = _ACTIVE_TASKS.get(session_id)
        if not session:
            yield f"data: {json.dumps({'type':'error','text':'Session not found'})}\n\n"
            return

        yield f"data: {json.dumps({'type':'plan','steps':result['steps'],'total':len(result['steps'])})}\n\n"

        while session["status"] == "running":
            try:
                step_result = continue_autonomous_task(session_id)
                if step_result.get("type") == "ask":
                    yield f"data: {json.dumps({'type':'ask','question':step_result['question'],'session_id':session_id})}\n\n"
                    return
                yield f"data: {json.dumps({'type':'progress','step':session['step_index'],'total':len(session['plan']),'current':session.get('current_step',''),'last_result':session.get('last_result')})}\n\n"
                if session["step_index"] >= len(session["plan"]):
                    break
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','text':str(e)})}\n\n"
                break

        final = _ACTIVE_TASKS.get(session_id, {})
        yield f"data: {json.dumps({'type':'complete','results':final.get('results',[]),'summary':final.get('results',[])})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Entity / Agent thoughts ─────────────────────────────────────

@app.get("/api/jarvis/thoughts")
async def jarvis_thoughts(user_id: str = "local", limit: int = 10):
    """Return the entity's current thought + recent thought history."""
    from entity_engine import get_entity
    entity = get_entity(user_id)
    return {
        "current_thought": entity._current_thought,
        "mood": entity.mood,
        "thought_history": entity._thought_history[-limit:],
    }

@app.get("/api/jarvis/status")
async def jarvis_status(user_id: str = "local"):
    """Return full agent status summary."""
    return await jarvis_thoughts(user_id)


# ── ACC (Agent Command Center) ────────────────────────────────────

class ACCCommandRequest(BaseModel):
    device_id: str = ""
    device_type: str = ""
    device_name: str = ""
    device_protocol: str = ""
    command: str = ""
    capabilities: list = []

class ACCDeviceActionRequest(BaseModel):
    device_id: str = ""
    device_ip: str = ""
    device_type: str = ""
    action: str = ""
    params: str = ""

@app.get("/api/acc/devices")
async def acc_devices():
    """Return all devices across all sources (smart home, system, relay)."""
    from acc_manager import get_all_acc_devices
    devices = get_all_acc_devices()
    total = len(devices)
    online = sum(1 for d in devices if d.get("status") == "online")
    by_type = {}
    for d in devices:
        t = d.get("type", "unknown")
        by_type.setdefault(t, {"total": 0, "online": 0})
        by_type[t]["total"] += 1
        if d.get("status") == "online":
            by_type[t]["online"] += 1
    return {"devices": devices, "total": total, "online": online, "offline": total - online, "by_type": by_type}


@app.post("/api/acc/parse")
async def acc_parse(req: ACCCommandRequest):
    """Parse a natural language command for a specific device."""
    from acc_manager import parse_command_for_device
    device = {
        "id": req.device_id,
        "name": req.device_name,
        "type": req.device_type,
        "protocol": req.device_protocol,
        "capabilities": req.capabilities,
    }
    result = parse_command_for_device(device, req.command)
    return result


@app.post("/api/acc/execute")
async def acc_execute(req: ACCDeviceActionRequest):
    """Execute a parsed action on a device."""
    from acc_manager import execute_acc_command, get_all_acc_devices
    devices = get_all_acc_devices()
    device = None
    for d in devices:
        if d.get("id") == req.device_id or d.get("ip") == req.device_ip:
            device = d
            break
    if not device:
        device = {"id": req.device_id, "type": req.device_type, "ip": req.device_ip}
    result = execute_acc_command(device, req.action, req.params)
    return result


# ── Missing routes: Scan, Agent, Devices, Life, Trading, Business, Marketplace, Propagation ──

@app.get("/api/scan/quick")
async def scan_quick():
    return {"status": "idle", "devices": [], "timestamp": __import__("time").time()}

@app.get("/api/scan/full")
async def scan_full():
    return {"status": "idle", "devices": [], "timestamp": __import__("time").time()}

@app.get("/api/scan/wifi")
async def scan_wifi():
    return {"status": "idle", "networks": [], "timestamp": __import__("time").time()}

@app.get("/api/scan/lan")
async def scan_lan():
    return {"status": "idle", "devices": [], "timestamp": __import__("time").time()}

@app.get("/api/scan/processes")
async def scan_processes():
    return {"status": "idle", "processes": [], "timestamp": __import__("time").time()}

@app.get("/api/scan/info")
async def scan_info():
    return {"hostname": os.uname().nodename, "platform": __import__("platform").system(), "timestamp": __import__("time").time()}

@app.get("/api/agent/status")
async def agent_status():
    return {"status": "idle", "commands_pending": 0, "timestamp": __import__("time").time()}

@app.get("/api/agent/commands")
async def agent_commands():
    return {"commands": [], "count": 0}

@app.post("/api/devices/discover")
async def devices_discover():
    return {"devices": [], "count": 0}

@app.get("/api/devices/stats")
async def devices_stats():
    return {"total": 0, "online": 0, "offline": 0, "by_type": {}}

@app.get("/api/money/balance")
async def money_balance():
    return {"balance": 0.0, "currency": "USD", "transactions": []}

@app.get("/api/money/history")
async def money_history(limit: int = 20):
    return {"transactions": [], "count": 0}

@app.get("/api/propagation/status")
async def propagation_status():
    return {"status": "idle", "active": False, "timestamp": __import__("time").time()}

@app.get("/api/propagation/logs")
async def propagation_logs():
    return {"logs": [], "count": 0}

@app.get("/api/jarvis/hud")
async def jarvis_hud(user_id: str = "local"):
    from entity_engine import get_entity
    entity = get_entity(user_id)
    return {
        "mood": entity.mood,
        "mood_emoji": entity._mood_emoji,
        "current_thought": entity._current_thought,
        "interaction_count": entity._interaction_count,
    }

@app.get("/api/life/dashboard")
async def life_dashboard():
    return {"habits": [], "tasks": [], "mood": "neutral", "finance": {"balance": 0}, "health": {"water_ml": 0, "sleep_hours": 0}}

@app.get("/api/life/briefing")
async def life_briefing():
    return {"greeting": "Good day!", "tasks": [], "habits": [], "mood": "neutral", "summary": "No data yet."}

@app.get("/api/life/finance/balance")
async def life_finance_balance():
    return {"balance": 0.0, "income": 0.0, "expenses": 0.0, "currency": "USD"}

@app.post("/api/life/finance/transaction")
async def life_finance_transaction(data: dict):
    return {"status": "ok", "transaction": {"id": "t1", "amount": data.get("amount", 0), "category": data.get("category", ""), "description": data.get("description", ""), "type": data.get("type", "expense")}}

@app.get("/api/life/finance/budgets")
async def life_finance_budgets():
    return {"budgets": []}

@app.post("/api/life/finance/budget")
async def life_finance_budget(data: dict):
    return {"status": "ok", "budget": {"category": data.get("category", ""), "limit": data.get("limit", 0)}}

@app.get("/api/life/finance/subscriptions")
async def life_finance_subscriptions():
    return {"subscriptions": []}

@app.get("/api/life/health/summary")
async def life_health_summary():
    return {"water_ml": 0, "sleep_hours": 0, "workouts": [], "meals": []}

@app.post("/api/life/health/workout")
async def life_health_workout(data: dict):
    return {"status": "ok", "workout": {"exercise": data.get("exercise", ""), "duration_min": data.get("duration_min", 0), "calories": data.get("calories", 0)}}

@app.post("/api/life/health/meal")
async def life_health_meal(data: dict):
    return {"status": "ok", "meal": {"type": data.get("meal_type", ""), "description": data.get("description", ""), "calories": data.get("calories", 0)}}

@app.post("/api/life/health/sleep")
async def life_health_sleep(data: dict):
    return {"status": "ok", "sleep": {"hours": data.get("hours", 0), "quality": data.get("quality", 3)}}

@app.post("/api/life/health/water")
async def life_health_water(data: dict):
    return {"status": "ok", "water_ml": data.get("ml", 0)}

@app.get("/api/life/planner/tasks")
async def life_planner_tasks(date: str = ""):
    return {"tasks": [], "count": 0}

@app.post("/api/life/planner/task")
async def life_planner_task(data: dict):
    return {"status": "ok", "task": {"id": "task1", "title": data.get("title", ""), "priority": data.get("priority", 3), "completed": False}}

@app.post("/api/life/planner/complete/{task_id}")
async def life_planner_complete(task_id: str):
    return {"status": "ok", "completed": True}

@app.get("/api/life/habits")
async def life_habits():
    return {"habits": []}

@app.post("/api/life/habits/log")
async def life_habits_log(data: dict):
    return {"status": "ok", "logged": True}

@app.get("/api/life/goals")
async def life_goals():
    return {"goals": []}

@app.get("/api/life/journal/recent")
async def life_journal_recent(limit: int = 10):
    return {"entries": [], "count": 0}

@app.post("/api/life/journal")
async def life_journal(data: dict):
    return {"status": "ok", "entry": {"id": "j1", "content": data.get("content", ""), "tags": data.get("tags", [])}}

@app.get("/api/life/mood/trend")
async def life_mood_trend(days: int = 30):
    return {"trend": [], "average": "neutral"}

@app.get("/api/trading/portfolio")
async def trading_portfolio():
    return {"holdings": [], "total_value": 0.0, "profit_loss": 0.0}

@app.post("/api/trading/buy")
async def trading_buy(data: dict):
    return {"status": "ok", "trade": {"symbol": data.get("symbol", ""), "shares": data.get("shares", 0), "action": "buy"}}

@app.post("/api/trading/sell")
async def trading_sell(data: dict):
    return {"status": "ok", "trade": {"symbol": data.get("symbol", ""), "shares": data.get("shares", 0), "action": "sell"}}

@app.get("/api/trading/analyze")
async def trading_analyze(symbol: str = ""):
    return {"symbol": symbol, "analysis": "No data available.", "price": 0, "change": 0}

@app.get("/api/trading/search")
async def trading_search(q: str = ""):
    return {"results": [], "count": 0}

@app.get("/api/trading/history")
async def trading_history():
    return {"trades": [], "count": 0}

@app.get("/api/trading/strategies")
async def trading_strategies():
    return {"strategies": []}

@app.post("/api/trading/strategies/run")
async def trading_strategies_run(data: dict):
    return {"status": "ok", "strategy_id": data.get("strategy_id", "")}

@app.post("/api/trading/auto/start")
async def trading_auto_start(data: dict):
    return {"status": "ok", "interval_min": data.get("interval_min", 60)}

@app.post("/api/trading/auto/stop")
async def trading_auto_stop():
    return {"status": "ok", "stopped": True}

@app.get("/api/trading/market")
async def trading_market():
    return {"market": {}, "timestamp": __import__("time").time()}

@app.post("/api/business/email/configure")
async def business_email_configure(data: dict):
    return {"status": "ok", "configured": True}

@app.get("/api/business/email/config")
async def business_email_config():
    return {"configured": False, "email": ""}

@app.get("/api/business/calendar")
async def business_calendar(day: str = ""):
    return {"events": [], "count": 0}

@app.post("/api/business/calendar/add")
async def business_calendar_add(data: dict):
    return {"status": "ok", "event": {"id": "ev1", "title": data.get("title", ""), "date": data.get("date", "")}}

@app.get("/api/business/calendar/summary")
async def business_calendar_summary(days: int = 7):
    return {"events": [], "count": 0, "days": days}

@app.get("/api/business/contacts")
async def business_contacts():
    return {"contacts": [], "count": 0}

@app.post("/api/business/contacts/add")
async def business_contacts_add(data: dict):
    return {"status": "ok", "contact": {"id": "c1", "name": data.get("name", ""), "email": data.get("email", "")}}

@app.get("/api/business/contacts/search")
async def business_contacts_search(q: str = ""):
    return {"results": [], "count": 0}

@app.get("/api/business/research")
async def business_research(topic: str = "", depth: str = "basic"):
    return {"topic": topic, "results": [], "summary": "No research data available."}

@app.get("/api/business/activity")
async def business_activity():
    return {"activity": [], "count": 0}

@app.get("/api/business/summary")
async def business_summary():
    return {"summary": "No business data available.", "contacts": 0, "events": 0}

@app.get("/api/marketplace/plugins")
async def marketplace_plugins(category: str = ""):
    return {"plugins": [], "count": 0}

@app.post("/api/marketplace/install")
async def marketplace_install(data: dict):
    return {"status": "ok", "plugin_id": data.get("plugin_id", "")}

@app.get("/api/marketplace/installed")
async def marketplace_installed():
    return {"plugins": [], "count": 0}

@app.post("/api/marketplace/publish")
async def marketplace_publish(data: dict):
    return {"status": "ok", "plugin_id": "p1", "name": data.get("name", "")}

@app.get("/api/system/info")
async def system_info():
    import platform as _platform
    uname = os.uname()
    return {
        "os": f"{_platform.system()} {uname.release}",
        "cpu": f"{_platform.machine()} ({os.cpu_count() or '?'} cores)",
        "memory": f"{round(__import__('psutil').virtual_memory().total / 1e9, 1)}GB total",
        "hostname": uname.nodename,
        "python": _platform.python_version(),
    }


@app.exception_handler(404)
async def serve_frontend(req, exc):
    """Serve frontend static files for non-API routes."""
    path = req.url.path.lstrip("/") or "index.html"
    # Strip basePath prefix (used for GitHub Pages at /voice_shaurjy/)
    for prefix in ("voice_shaurjy/",):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    if not path.startswith("api/") and not path.startswith("ws/") and not path.startswith("docs") and not path.startswith("openapi"):
        _frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "out")
        # Next.js static export generates .html files (dashboard.html, settings.html, etc.)
        if "." not in path:
            fp_html = os.path.join(_frontend_dir, path + ".html")
            if os.path.isfile(fp_html):
                from fastapi.responses import FileResponse
                return FileResponse(fp_html)
            # Check for directory/index.html (Next.js static export pattern)
            fp_index = os.path.join(_frontend_dir, path, "index.html")
            if os.path.isfile(fp_index):
                from fastapi.responses import FileResponse
                return FileResponse(fp_index)
        fp = os.path.join(_frontend_dir, path)
        if not os.path.isfile(fp):
            fp = os.path.join(_frontend_dir, "index.html")
        if os.path.isfile(fp):
            from fastapi.responses import FileResponse
            return FileResponse(fp)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Not Found"}, status_code=404)
