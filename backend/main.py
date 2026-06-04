"""FastAPI — document uploads, text chat, LiveKit tokens, system health."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, WebSocket as _WS
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import TextQuery, DocumentUpload, LicenseActivate, LiveKitTokenRequest, ReminderCreate, ReminderUpdate, TaskRespond
from document_processor import process_upload
from rag_engine import index_document, has_documents, count_chunks
from billing import get_tier, activate_license, is_premium
from ai_agent import generate_response

load_dotenv()

app = FastAPI(title="Second Brain API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"app": "Second Brain API", "status": "running", "docs": "/docs", "health": "/health"}


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


# ── Text-to-Speech via edge-tts (streaming) ───────────────────

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-AriaNeural"

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    from fastapi.responses import StreamingResponse, Response
    import io, asyncio, re

    text = req.text
    voice = req.voice or "en-US-AriaNeural"

    # Build SSML with expressive style for more human-like speech
    cheer_words = ["great", "nice", "awesome", "love", "amazing", "cool", "yes"]
    sad_words = ["sorry", "sad", "unfortunate", "ugh", "oh no", "argh"]
    style = "cheerful" if any(w in text.lower() for w in cheer_words) else "empathetic" if any(w in text.lower() for w in sad_words) else "chat"

    text_escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
    ssml = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts"><voice name="{voice}"><mstts:express-as style="{style}" styledegree="1.5">{text_escaped}</mstts:express-as></voice></speak>'

    # Try edge_tts with SSML (expressive, much more human-like)
    try:
        import edge_tts
        communicate = edge_tts.Communicate(ssml, voice)

        async def stream():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(stream(), media_type="audio/mpeg")
    except Exception:
        pass

    # Fallback: plain text edge_tts
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)

        async def stream2():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(stream2(), media_type="audio/mpeg")
    except Exception:
        pass

    # Local fallback via pyttsx3
    try:
        import pyttsx3, tempfile, os
        engine = pyttsx3.init()
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 1.0)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            data = f.read()
        os.unlink(tmp_path)
        return Response(content=data, media_type="audio/wav")
    except Exception as e:
        return Response(content=f"TTS error: {e}".encode(), status_code=500, media_type="text/plain")


# ── Device scanner ───────────────────────────────────────────

@app.post("/api/device/scan")
async def device_scan(user_id: str = "local"):
    from device_scanner import scan_device

    data = scan_device(user_id, force=True)
    # Also update profile with fresh scan
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
async def send_notification(title: str = "Jason", message: str = ""):
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
    path = os.path.expanduser("~/Desktop/_jason_screenshot.png")
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
    relay_id = queue_action(req.action_id, req.params)
    return {"status": "queued", "relay_id": relay_id, "action": req.action_id}


@app.get("/api/relay/pending")
async def relay_pending():
    """Polled by local agent — returns list of pending actions (claims them atomically)."""
    from relay import claim_next_pending
    actions = []
    while True:
        a = claim_next_pending()
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


@app.websocket("/ws/relay")
async def ws_relay(ws: _WS):
    """WebSocket endpoint — relay agent connects here for real-time action push."""
    from relay import ws_relay_handler
    await ws_relay_handler(ws)


@app.exception_handler(404)
async def serve_frontend(req, exc):
    """Serve frontend static files for non-API routes."""
    path = req.url.path.lstrip("/") or "index.html"
    if not path.startswith("api/") and not path.startswith("ws/") and not path.startswith("docs") and not path.startswith("openapi"):
        _frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "out")
        fp = os.path.join(_frontend_dir, path)
        if not os.path.isfile(fp):
            fp = os.path.join(_frontend_dir, "index.html")
        if os.path.isfile(fp):
            from fastapi.responses import FileResponse
            return FileResponse(fp)
    raise exc
