"""JARVIS — The System Engine.

Hugging Face Space: Autonomous ecosystem orchestrator with voice-first AI,
system control, smart home, and web automation.
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from models import TextQuery, DocumentUpload, LicenseActivate, LiveKitTokenRequest, ReminderCreate, ReminderUpdate, TaskRespond
from pydantic import BaseModel
from typing import Optional, Dict, Any
from document_processor import process_upload
from rag_engine import index_document, has_documents, count_chunks
from billing import get_tier, activate_license, is_premium
from ai_agent import generate_response

import importlib as _importlib

def _lazy_import(module_name, attr_name):
    """Lazily import a module attribute, returning None on failure."""
    def getter():
        try:
            mod = _importlib.import_module(module_name)
            return getattr(mod, attr_name)()
        except Exception:
            return None
    return getter

get_learning_engine = _lazy_import("self_improvement", "get_learning_engine")
get_device_mesh = _lazy_import("device_mesh", "get_device_mesh")
get_autonomous_engine = _lazy_import("autonomous_engine", "get_autonomous_engine")
get_enterprise_engine = _lazy_import("enterprise", "get_enterprise_engine")
get_skill_marketplace = _lazy_import("skill_marketplace", "get_skill_marketplace")

from auth import authenticate, AuthContext, create_jwt_token
from rate_limiter import RateLimitMiddleware, get_rate_limiter
from error_handler import ErrorHandlerMiddleware

load_dotenv()

app = FastAPI(title="JARVIS — The System Engine", version="2.0.0")

# ── Security: Restricted CORS ──────────────────────────────────
ALLOWED_ORIGINS = os.getenv("JARVIS_ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
if not ALLOWED_ORIGINS:
    # Dev mode: allow all. Production: restrict to known origins.
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-User-ID"],
)

# ── Rate Limiting Middleware ────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── Error Handler Middleware ────────────────────────────────────
app.add_middleware(ErrorHandlerMiddleware)


@app.on_event("startup")
async def startup_event():
    """
    Real device discovery on startup.
    Scans the actual local network via ARP and registers real devices.
    Skipped on cloud (HF Space) — relay pushes devices instead.
    """
    try:
        import socket
        # Detect if running on cloud (HF Space) — skip network scan
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            # HF Space uses 10.x.x.x or 172.x.x.x subnets
            is_cloud = local_ip.startswith("10.") or local_ip.startswith("172.") or local_ip.startswith("169.")
        except Exception:
            is_cloud = True
            local_ip = "127.0.0.1"

        if is_cloud:
            print("[SOVEREIGN] Cloud environment detected — skipping local network scan (relay pushes devices)")
            return

        from device_manager import upsert_device, get_all_devices
        from network_scanner import start_scanner
        import subprocess, re

        # Start the network scanner daemon (only on real machines)
        start_scanner(scan_interval=30)

        # Only scan if database is empty
        existing = get_all_devices()
        if len(existing) > 0:
            print(f"[SOVEREIGN] Database has {len(existing)} devices, skipping scan")
            return

        print("[SOVEREIGN] Scanning real local network...")

        # Get local subnet
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            local_subnet = ".".join(local_ip.split(".")[:3])
        except Exception:
            local_ip = "127.0.0.1"
            local_subnet = "192.168.1"

        # Real ARP scan
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=15)
            arp_output = result.stdout
        except Exception:
            arp_output = ""

        registered = 0

        # Parse ARP and register real devices
        for line in arp_output.splitlines():
            mac_match = re.search(r'at\s+([0-9a-fA-F:]{17})', line)
            ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
            if not mac_match or not ip_match:
                continue

            ip = ip_match.group(1)
            mac = mac_match.group(1).upper()

            # Skip broadcasts, multicast, incomplete
            if "FF:FF:FF:FF:FF:FF" in mac or "1:0:5E" in mac or "(incomplete)" in line:
                continue

            hostname = line.split("(")[0].strip() if "(" in line else ""
            hostname = hostname.replace("?", "").strip()

            # Identify device type from hostname/MAC
            device_type = "UNKNOWN"
            protocol = "unknown"
            manufacturer = ""
            model = ""
            device_name = hostname or ip

            hl = hostname.lower()

            # Router/Gateway
            if "skysr213" in hl or ip.endswith(".1") and "router" in hl:
                device_type = "ROUTER"
                protocol = "http"
                manufacturer = "Sky"
                model = "SR213"
            # TP-Link Tapo Smart Plugs
            elif "tapo" in hl or "p100" in hl or "p110" in hl or "p125" in hl:
                device_type = "SWITCH"
                protocol = "tapo"
                manufacturer = "TP-Link"
                if "p110" in hl:
                    model = "Tapo P110"
                elif "p100" in hl:
                    model = "Tapo P100"
                elif "p125" in hl:
                    model = "Tapo P125"
                else:
                    model = "Tapo Smart Plug"
            # HP Printer
            elif "hp" in hl or "printer" in hl:
                device_type = "PRINTER"
                protocol = "ipp"
                manufacturer = "HP"
                model = "Printer"
            # Samsung phones
            elif "samsung" in hl or "galaxy" in hl or "note20" in hl or "s24" in hl or "gargi" in hl or "suprotim" in hl:
                device_type = "PHONE"
                protocol = "adb"
                manufacturer = "Samsung"
                if "note20" in hl:
                    model = "Galaxy Note20"
                elif "s24 ultra" in hl:
                    model = "Galaxy S24 Ultra"
                elif "s24" in hl:
                    model = "Galaxy S24"
            # Range extender
            elif "re200" in hl or "extender" in hl or "repeater" in hl:
                device_type = "ROUTER"
                protocol = "http"
                manufacturer = "TP-Link"
                model = "RE200"
            # iMac / Apple
            elif "imac" in hl or "macbook" in hl or "apple" in hl:
                device_type = "HUB"
                protocol = "ssh"
                manufacturer = "Apple"
                model = "iMac"
            # Generic laptop
            elif "laptop" in hl or "nbkw" in hl:
                device_type = "HUB"
                protocol = "ssh"
                manufacturer = "Unknown"
                model = "Laptop"
            # lwip devices (likely IoT)
            elif "lwip" in hl:
                device_type = "SENSOR"
                protocol = "mqtt"
                manufacturer = "Unknown"
                model = "IoT Device"

            if device_type == "UNKNOWN":
                continue  # Skip unidentifiable devices

            device_id = f"real_{ip.replace('.', '_')}"

            upsert_device({
                "id": device_id,
                "name": device_name,
                "device_type": device_type,
                "ip": ip,
                "mac": mac,
                "protocol": protocol,
                "manufacturer": manufacturer,
                "model": model,
                "room": "unknown",
                "state": {"power": "UNKNOWN"},
                "is_online": True,
            })
            registered += 1

        print(f"[SOVEREIGN] Registered {registered} real devices from local network")
        print(f"[SOVEREIGN] Local IP: {local_ip}, Subnet: {local_subnet}")

    except Exception as e:
        print(f"[SOVEREIGN] Startup scan failed: {e}")

    # ── Initialize MCP Client ────────────────────────────────────────
    try:
        from mcp_client import get_mcp_client
        from mcp_registry import get_registry
        from compliance_ledger import get_ledger

        registry = get_registry()
        client = get_mcp_client()
        ledger = get_ledger()
        client.set_ledger(ledger)

        # Load discovered server configs
        for name, cfg in registry.get_all().items():
            from mcp_client import MCPServerConfig, TransportType
            transport = TransportType(cfg.get("transport", "stdio"))
            client.register_server(MCPServerConfig(
                name=name,
                transport=transport,
                command=cfg.get("command"),
                args=cfg.get("args", []),
                env=cfg.get("env"),
                url=cfg.get("url"),
                description=cfg.get("description", ""),
                tags=cfg.get("tags", []),
            ))

        # Connect to all servers (best-effort, async)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                def _connect_mcp():
                    asyncio.run(client.connect_all())
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                pool.submit(_connect_mcp)
            else:
                loop.run_until_complete(client.connect_all())
        except Exception:
            import concurrent.futures
            def _connect_mcp():
                asyncio.run(client.connect_all())
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            pool.submit(_connect_mcp)

        status = client.get_status()
        print(f"[MCP] Initialized: {status['connected_servers']}/{status['total_servers']} servers, {status['total_tools']} tools")
    except ImportError:
        print("[MCP] mcp_client module not available — MCP routing disabled")
    except Exception as e:
        print(f"[MCP] Initialization failed: {e}")

    # ── Auto-deploy core agents ───────────────────────────────────────
    try:
        from agent_pool import get_pool, AgentType
        pool = get_pool()
        for agent_type in [AgentType.OS, AgentType.HAL, AgentType.WEB, AgentType.DEVICE, AgentType.MONITOR]:
            try:
                agent = pool.spawn(f"JARVIS {agent_type.value.upper()} Agent", agent_type)
                print(f"[AGENTS] Spawned {agent_type.value} agent: {agent.id}")
            except Exception as e:
                print(f"[AGENTS] Failed to spawn {agent_type.value}: {e}")
        print(f"[AGENTS] Core agents initialized: {len(pool.get_all())} active")
    except ImportError:
        print("[AGENTS] agent_pool module not available")
    except Exception as e:
        print(f"[AGENTS] Auto-deploy failed: {e}")


class RouterDispatchRequest(BaseModel):
    user_text: str
    user_id: str = "local"
    relay_context: Optional[Dict[str, Any]] = None


@app.post("/api/router/dispatch")
async def router_dispatch(req: RouterDispatchRequest, auth: AuthContext = Depends(authenticate)):
    """
    Multi-Agent Router Dispatch — JARVIS cognitive triage pipeline.
    Stage 1: Supervisor Router classifies intent (<100ms, 8B model).
    Stage 2: Domain worker (OS/HAL/WEB) generates typed execution payload (70B model).
    Returns full telemetry packet with routing metadata and latency breakdowns.
    """
    try:
        from multi_agent_router import route_and_execute
        result = route_and_execute(
            user_text=req.user_text,
            user_id=auth.user_id if auth.user_id != "local" else req.user_id,
            relay_context=req.relay_context or {},
        )
        result["auth"] = {"user_id": auth.user_id, "method": auth.auth_method}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

@app.get("/install")
@app.get("/install.ps1")
async def install_download():
    fp = os.path.join(os.path.dirname(__file__), "install.ps1")
    if os.path.isfile(fp):
        from fastapi.responses import FileResponse
        return FileResponse(fp, media_type="text/plain", filename="install.ps1")
    return {"error": "Installer not found"}

# ── MCP Endpoints ────────────────────────────────────────────────────────

@app.get("/api/mcp/status")
async def mcp_status():
    """Get status of all MCP server connections."""
    try:
        from mcp_client import get_mcp_client
        client = get_mcp_client()
        return client.get_status()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/mcp/tools")
async def mcp_tools():
    """List all discovered MCP tools."""
    try:
        from mcp_client import get_mcp_client
        from dataclasses import asdict
        client = get_mcp_client()
        tools = client.get_tools()
        return {"tools": [asdict(t) for t in tools], "count": len(tools)}
    except Exception as e:
        return {"error": str(e), "tools": []}

@app.post("/api/mcp/call")
async def mcp_call_tool(body: dict, request: None = None):
    """
    Secure MCP tool invocation with enterprise identity propagation
    and deterministic guardrail enforcement.
    
    Security pipeline:
    1. Extract enterprise identity (OAuth2/OIDC JWT or local fallback)
    2. Enforce scope-based access control
    3. Run deterministic guardrails (SQL injection, destructive ops, etc.)
    4. Down-scope token for target MCP server
    5. Execute tool with isolated identity context
    6. Log to hash-chained compliance ledger
    """
    tool_name = body.get("tool")
    arguments = body.get("arguments", {})
    if not tool_name:
        return {"error": "Missing 'tool' parameter"}

    try:
        from mcp_client import get_mcp_client
        from mcp_auth import (
            extract_identity_from_request,
            get_local_identity,
            launder_token_for_server,
        )
        from mcp_guardrails import screen_or_block, RiskLevel
        from compliance_ledger import get_ledger
        from dataclasses import asdict

        # ── Step 1: Extract Identity ─────────────────────────────────
        # In production, pass the real request object. For now, use local identity.
        # To enable enterprise SSO, set JARVIS_OIDC_ISSUER env var.
        try:
            if request is not None:
                identity = extract_identity_from_request(request)
            else:
                identity = get_local_identity()
        except Exception:
            identity = get_local_identity()

        # ── Step 2: Scope Check ──────────────────────────────────────
        is_write = body.get("is_write", False)
        if not identity.can_access_tool(tool_name, is_write):
            # Log the denied attempt
            ledger = get_ledger()
            await ledger.log_invocation(
                tool_name=tool_name,
                server_name="access_denied",
                arguments=arguments,
                result={"denied": True, "reason": "insufficient_scope"},
                duration_ms=0,
                is_error=True,
                identity_jwt_hash=identity.identity_hash,
                security_scope="access_denied",
            )
            return {
                "error": "Access denied: insufficient identity scopes",
                "required_scopes": ["db:read"] if not is_write else ["db:write"],
                "user_scopes": identity.scopes,
                "identity_hash": identity.identity_hash[:16] + "...",
            }

        # ── Step 3: Guardrail Screening ──────────────────────────────
        guardrail_result = screen_or_block(
            tool_name=tool_name,
            arguments=arguments,
            user_id=identity.user_id,
            is_write=is_write,
        )

        if not guardrail_result.allowed:
            # Log the blocked violation
            ledger = get_ledger()
            await ledger.log_invocation(
                tool_name=tool_name,
                server_name="guardrail_blocked",
                arguments=arguments,
                result={
                    "blocked": True,
                    "reason": guardrail_result.blocked_reason,
                    "violations": guardrail_result.violations,
                },
                duration_ms=0,
                is_error=True,
                identity_jwt_hash=identity.identity_hash,
                security_scope="guardrail_violation",
            )
            return {
                "error": guardrail_result.blocked_reason,
                "violations": guardrail_result.violations,
                "risk_level": guardrail_result.risk_level.value,
                "identity_hash": identity.identity_hash[:16] + "...",
                "logged_to_compliance_ledger": True,
            }

        # ── Step 4: Down-scope Token for Target Server ───────────────
        scoped_headers = launder_token_for_server(
            identity=identity,
            server_name=tool_name.split("__")[0] if "__" in tool_name else tool_name,
            tool_name=tool_name,
            is_write=is_write,
        )

        # Inject scoped identity into arguments (for downstream MCP servers)
        arguments["_identity"] = {
            "user_id": identity.user_id,
            "identity_hash": identity.identity_hash,
            "tenant_id": identity.tenant_id,
            "scopes": identity.scopes,
            "auth_method": identity.auth_method,
        }

        # ── Step 5: Execute Tool ─────────────────────────────────────
        client = get_mcp_client()
        result = await client.call_tool(tool_name, arguments)

        # ── Step 6: Compliance Ledger ────────────────────────────────
        # The mcp_client already logs to the ledger. Add identity context.
        ledger = get_ledger()
        await ledger.log_invocation(
            tool_name=tool_name,
            server_name=result.server_name or "unknown",
            arguments=arguments,
            result=asdict(result),
            duration_ms=result.duration_ms,
            is_error=result.is_error,
            identity_jwt_hash=identity.identity_hash,
            security_scope=f"{identity.user_id}:{identity.tenant_id}",
        )

        response = asdict(result)
        response["identity"] = {
            "user_id": identity.user_id,
            "identity_hash": identity.identity_hash[:16] + "...",
            "auth_method": identity.auth_method,
            "scopes_applied": scoped_headers.get("X-JARVIS-Effective-Scopes", ""),
        }
        response["guardrails"] = {
            "passed": True,
            "risk_level": guardrail_result.risk_level.value,
            "warnings": guardrail_result.warnings,
        }

        return response

    except ImportError as e:
        return {"error": f"Security module not available: {e}"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/mcp/guardrails")
async def mcp_guardrails_status():
    """Get guardrail engine status and statistics."""
    try:
        from mcp_guardrails import get_guardrail
        guardrail = get_guardrail()
        return guardrail.get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/mcp/registry")
async def mcp_registry():
    """List all discovered MCP server configurations."""
    try:
        from mcp_registry import get_registry
        registry = get_registry()
        return {"servers": registry.get_all(), "count": len(registry.get_all())}
    except Exception as e:
        return {"error": str(e), "servers": {}}

@app.get("/api/mcp/compliance")
async def mcp_compliance_report():
    """Generate a compliance report."""
    try:
        from compliance_ledger import get_ledger
        ledger = get_ledger()
        return {
            "stats": ledger.get_stats(),
            "report": ledger.generate_report(),
            "recent_records": ledger.get_records(limit=20),
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
@app.get("/api/health")
async def health():
    livekit_url = os.getenv("LIVEKIT_URL", "")
    try:
        from relay import is_relay_alive
        relay_alive = is_relay_alive()
    except Exception:
        relay_alive = False
    try:
        from device_manager import DeviceManager
        devices = DeviceManager().get_all_devices()
    except Exception:
        devices = []
    return {
        "status": "ok",
        "assistant": "jarvis",
        "tier": get_tier(),
        "livekit": bool(livekit_url),
        "livekit_url": livekit_url,
        "relay": relay_alive,
        "devices": len(devices),
        "models": {
            "llm": "Groq Llama3-70B (cloud, instant)",
            "stt": "Web Speech API",
            "tts": "kokoro-onnx (am_michael)",
        },
    }


# ── Auth Endpoints ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None

class TokenRefreshRequest(BaseModel):
    token: str

@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """Authenticate and receive a JWT token."""
    # Simple credential check via env vars
    expected_user = os.getenv("JARVIS_ADMIN_USER", "admin")
    expected_pass = os.getenv("JARVIS_ADMIN_PASS", "")

    if expected_pass and (req.username != expected_user or req.password != expected_pass):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt_token(
        user_id=req.username,
        scopes=["read", "write", "admin"],
        tenant_id="default",
    )
    return {"token": token, "user_id": req.username, "expires_in_hours": 72}


@app.post("/api/auth/refresh")
async def auth_refresh(req: TokenRefreshRequest):
    """Refresh an existing JWT token."""
    from auth import refresh_token
    new_token = refresh_token(req.token)
    return {"token": new_token}


@app.get("/api/auth/status")
async def auth_status(auth: AuthContext = Depends(authenticate)):
    """Get current authentication status."""
    return {
        "authenticated": auth.auth_method != "anonymous",
        "user_id": auth.user_id,
        "auth_method": auth.auth_method,
        "scopes": auth.scopes,
        "tenant_id": auth.tenant_id,
    }


@app.get("/api/rate-limit/stats")
async def rate_limit_stats():
    """Get rate limiter statistics."""
    return get_rate_limiter().get_stats()


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
                from config import get_config
                deploy_url = get_config().get_deployment_url()
                return {"type": "ask", "question": f"Relay agent is offline. Start J.A.R.V.I.S. Relay on your desktop:\n\n**Mac/Linux:**\n```bash\ncurl -sL '{deploy_url}/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user $USER\n```\n\n**Windows (PowerShell):**\n```powershell\npowershell -c \"curl.exe -sL '{deploy_url}/relay' -o $env:TEMP\\\\relay.py; python $env:TEMP\\\\relay.py --user $env:USERNAME\"\n```\n\nRun that on your machine, then ask me again.", "session_id": req.session_id}
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


# ── Text-to-Speech via Kokoro TTS (local, hyper-realistic) ──────────────

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str
    voice: str = "am_michael"

_kokoro_pipe = None
_kokoro_lock = asyncio.Lock()

async def _get_kokoro():
    global _kokoro_pipe
    if _kokoro_pipe is not None:
        return _kokoro_pipe
    async with _kokoro_lock:
        if _kokoro_pipe is not None:
            return _kokoro_pipe
        try:
            from kokoro_onnx import Kokoro
            _kokoro_pipe = Kokoro("kokoro-v0_19.onnx", "voices-v0_19.bin")
            return _kokoro_pipe
        except Exception:
            return None

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    from fastapi.responses import StreamingResponse, Response
    import io, re, wave, struct

    text = req.text
    voice = req.voice or "am_michael"

    # Strip emoji and markdown
    text_clean = re.sub(r'[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF\uFE00-\uFE0F]', '', text)
    text_clean = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text_clean)
    text_clean = re.sub(r'[-_#>`|]', ' ', text_clean)
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()

    if not text_clean:
        text_clean = "Done."

    # Try Kokoro TTS first
    kokoro = await _get_kokoro()
    if kokoro:
        try:
            import numpy as np
            audio, sample_rate = kokoro.create(text_clean, voice=voice, speed=1.0)
            # Convert float32 numpy array to WAV bytes
            audio_int16 = (audio * 32767).astype(np.int16)
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
            wav_bytes = wav_buf.getvalue()
            return Response(content=wav_bytes, media_type="audio/wav")
        except Exception:
            pass

    # Fallback: edge-tts
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text_clean, "en-GB-RyanNeural")

        async def stream():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(stream(), media_type="audio/mpeg")
    except Exception:
        pass

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
    history: list = []  # [{role: "user"|"assistant", content: "..."}]


class WorkflowAdvanceRequest(BaseModel):
    execution_id: str
    user_input: str = None
    user_id: str = "local"


# ── Context Relay Endpoints ───────────────────────────────────────

@app.get("/api/context/relay")
async def context_relay_status():
    from context_relay import get_context_relay
    relay = get_context_relay()
    return relay.get_state()


@app.get("/api/context/relay/full")
async def context_relay_full(user_id: str = "local"):
    from context_relay import get_context_relay
    relay = get_context_relay()
    return relay.get_full_context(user_id)


@app.get("/api/context/calendar")
async def context_calendar(lookahead_days: int = 2):
    from context_relay import get_context_relay
    relay = get_context_relay()
    return {"events": relay.ingest_calendar(lookahead_days)}


@app.get("/api/context/emails")
async def context_emails(limit: int = 10):
    from context_relay import get_context_relay
    relay = get_context_relay()
    return {"emails": relay.ingest_emails(limit)}


@app.get("/api/context/contacts")
async def context_contacts(limit: int = 20):
    from context_relay import get_context_relay
    relay = get_context_relay()
    return {"contacts": relay.ingest_contacts(limit)}


@app.post("/api/context/relay/inject")
async def context_relay_inject(data: dict):
    """Receive context pushed from relay agent on user's machine."""
    from context_relay import get_context_relay
    relay = get_context_relay()
    relay.inject_relay_context(data)
    return {"status": "ok"}


# ── Multi-Agent Strategy Endpoint ────────────────────────────────────

@app.post("/api/router/strategy")
async def router_strategy(req: StrategyRequest):
    """Strategy generation endpoint (entity-based, uses StrategyRequest model)."""
    from multi_agent_router import route_and_execute
    result = route_and_execute(req.user_input, user_id=req.user_id)
    return result


# ── Proactive Engine Endpoints ─────────────────────────────────────

@app.get("/api/proactive/status")
async def proactive_status():
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    return engine.get_status()


@app.get("/api/proactive/messages")
async def proactive_messages():
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    msgs = engine.get_pending_messages()
    return {"messages": msgs}


@app.post("/api/proactive/reminder")
async def proactive_reminder(data: dict):
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    title = data.get("title", "")
    when = data.get("when", "")
    engine.add_reminder(title, when)
    return {"status": "ok"}


@app.post("/api/proactive/monitor")
async def proactive_monitor(data: dict):
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    monitor_type = data.get("type", "")
    engine.add_monitor(monitor_type, data)
    return {"status": "ok"}


# ── System Task Agent Endpoints ────────────────────────────────────

@app.post("/api/system/execute")
async def system_execute(data: dict):
    from system_task_agent import quick_action
    action = data.get("action", "")
    params = data.get("params", {})
    if isinstance(params, str):
        params = {"text": params}
    result = quick_action(action, params)
    return {"result": result}


@app.get("/api/system/task/status")
async def system_task_status():
    from system_task_agent import get_system_agent
    agent = get_system_agent()
    return agent.get_status()


@app.post("/api/system/task/stop")
async def system_task_stop():
    from system_task_agent import get_system_agent
    agent = get_system_agent()
    agent.stop()
    return {"status": "stopped"}


# ── Entity Engine Endpoints ────────────────────────────────────────

@app.post("/api/entity/process")
async def entity_process(req: StrategyRequest):
    from entity_engine import get_entity
    entity = get_entity(req.user_id)
    result = entity.process(req.user_input, history=req.history)
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
# Device data is now stored in relay.py to avoid circular imports

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
    from relay import record_heartbeat, update_relay_device
    from acc_manager import register_relay_device
    uid = data.get("user_id", "local")
    update_relay_device(uid, {
        "hostname": data.get("hostname", "?"),
        "platform": data.get("platform", "?"),
        "info": data.get("info", {}),
        "last_seen": __import__("time").time(),
    })
    register_relay_device(uid, {"hostname": data.get("hostname", "?"), "platform": data.get("platform", "?"), "info": data.get("info", {})})
    record_heartbeat(uid)
    return {"status": "registered"}

@app.post("/api/relay/heartbeat")
async def relay_heartbeat(data: dict):
    """Called periodically by relay agent to signal it's alive."""
    from relay import record_heartbeat, update_relay_device
    uid = data.get("user_id", "local")
    record_heartbeat(uid)
    update_relay_device(uid, {"last_seen": __import__("time").time()})
    return {"status": "ok"}

@app.get("/api/relay/devices")
async def relay_devices(user_id: str = "local"):
    from relay import get_relay_device
    return {"devices": [get_relay_device(user_id)]}

@app.get("/api/device/current")
async def current_device(user_id: str = "local"):
    """Return the current device the user is connected from — with full platform info."""
    from relay import get_relay_device
    relay_info = get_relay_device(user_id)
    platform_str = relay_info.get("platform", "")
    hostname = relay_info.get("hostname", "?")
    info = relay_info.get("info", {})

    # Determine OS from platform string
    plat_lower = platform_str.lower()
    if "darwin" in plat_lower or "macos" in plat_lower:
        os_name = "macOS"
        os_icon = "🍎"
    elif "windows" in plat_lower:
        os_name = "Windows"
        os_icon = "🪟"
    elif "linux" in plat_lower:
        os_name = "Linux"
        os_icon = "🐧"
    else:
        os_name = "Unknown"
        os_icon = "💻"

    # Extract version from platform string
    import re as _re
    version = ""
    v_match = _re.search(r'(\d+\.\d+(?:\.\d+)?)', platform_str)
    if v_match:
        version = v_match.group(1)

    # Get device profile if available
    profile = _device_profiles.get(user_id, {})
    hw = profile.get("hardware", {})
    apps = profile.get("apps", [])

    return {
        "hostname": hostname,
        "platform": platform_str,
        "os": os_name,
        "os_icon": os_icon,
        "version": version,
        "username": info.get("whoami", ""),
        "ram_gb": hw.get("ram_gb"),
        "cpu_cores": hw.get("cpu_cores"),
        "app_count": len(apps),
        "last_seen": relay_info.get("last_seen", 0),
    }


# ── Device Profile ────────────────────────────────────────────
_device_profiles: dict = {}

@app.get("/api/device/profile")
async def get_device_profile(user_id: str = "local"):
    """Get the device profile for a user (set by relay on registration)."""
    return {"profile": _device_profiles.get(user_id, {})}

@app.post("/api/device/profile")
async def set_device_profile(data: dict):
    """Relay sends device profile after running system_explore."""
    uid = data.get("user_id", "local")
    profile = data.get("profile", {})
    _device_profiles[uid] = profile
    return {"status": "ok", "apps": len(profile.get("apps", []))}

@app.post("/api/device/explore")
async def device_explore(user_id: str = "local"):
    """Trigger a full device exploration via relay."""
    try:
        from relay import is_relay_alive, queue_action
        if not is_relay_alive(user_id):
            return {"status": "offline", "error": "Relay not connected"}
        rid = queue_action("system_explore", "", user_id=user_id)
        return {"status": "queued", "relay_id": rid}
    except Exception as e:
        return {"status": "error", "error": str(e)}

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


# ── Core Engine API (SQLite Graph Memory + Compliance Ledger) ───────────

class CoreDispatchRequest(BaseModel):
    intent: str
    agent_domain: str = "CORE_AGENT"

@app.get("/api/core/status")
async def core_status():
    try:
        from core_engine import get_core_engine
        engine = get_core_engine()
        return engine.get_system_status()
    except Exception as e:
        return {"error": str(e), "memory_nodes": 0, "audit_blocks": 0, "chain_valid": True, "active_processes": 0, "security_intercepts": 0}

@app.post("/api/core/dispatch")
async def core_dispatch(req: CoreDispatchRequest):
    try:
        from core_engine import get_core_engine
        engine = get_core_engine()
        result = engine.process_intent(req.intent)
        status = engine.get_system_status()
        result["audit_blocks"] = status["audit_blocks"]
        return result
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

@app.get("/api/core/graph")
async def core_graph(node_type: str = None, limit: int = 50):
    try:
        from core_engine import get_core_engine
        engine = get_core_engine()
        return {"nodes": engine.memory.query_nodes(node_type, limit)}
    except Exception as e:
        return {"nodes": [], "error": str(e)}

@app.get("/api/core/graph/recall")
async def core_recall(entity: str, hops: int = 2):
    try:
        from core_engine import get_core_engine
        engine = get_core_engine()
        return {"entity": entity, "connections": engine.memory.multi_hop_recall(entity, hops)}
    except Exception as e:
        return {"connections": [], "error": str(e)}

@app.get("/api/core/audit")
async def core_audit(limit: int = 50):
    try:
        from core_engine import get_core_engine
        engine = get_core_engine()
        return {"trail": engine.memory.get_audit_trail(limit)}
    except Exception as e:
        return {"trail": [], "error": str(e)}

@app.get("/api/core/audit/verify")
async def core_audit_verify():
    try:
        from core_engine import get_core_engine
        engine = get_core_engine()
        return engine.memory.verify_chain_integrity()
    except Exception as e:
        return {"valid": False, "error": str(e)}


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


# ═══════════════════════════════════════════════════════════════════
# JARVIS PLATFORM — Multi-Agent Pool, NL Parsing, Device Control
# ═══════════════════════════════════════════════════════════════════

from agent_pool import get_pool, AgentType
from nl_command_parser import parse_command, build_device_command
from device_bridge import get_bridge


class AgentSpawnRequest(BaseModel):
    name: str
    agent_type: str = "chat"
    config: Optional[Dict[str, Any]] = None
    capabilities: Optional[list] = None
    tags: Optional[list] = None


class AgentTaskRequest(BaseModel):
    command: str
    metadata: Optional[Dict[str, Any]] = None


class NLCommandRequest(BaseModel):
    text: str


class DeviceControlRequest(BaseModel):
    device_id: Optional[str] = None
    device_ip: Optional[str] = None
    command: Dict[str, Any]


# ── Agent Pool Routes ───────────────────────────────────────────

@app.get("/api/agents")
async def list_agents(status: Optional[str] = None, agent_type: Optional[str] = None):
    pool = get_pool()
    agents = pool.list_agents(status=status, agent_type=agent_type)
    return {"agents": [a.to_dict() for a in agents], "stats": pool.get_pool_stats()}


@app.post("/api/agents/spawn")
async def spawn_agent(req: AgentSpawnRequest):
    pool = get_pool()
    agent = pool.spawn(
        name=req.name,
        agent_type=req.agent_type,
        config=req.config,
        capabilities=req.capabilities,
        tags=req.tags,
    )
    return agent.to_dict()


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    pool = get_pool()
    agent = pool.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    tasks = pool.get_agent_tasks(agent_id)
    return {**agent.to_dict(), "tasks": [{"id": t.id, "command": t.command, "status": t.status, "result": t.result, "latency_ms": t.latency_ms} for t in tasks]}


@app.delete("/api/agents/{agent_id}")
async def kill_agent(agent_id: str):
    pool = get_pool()
    ok = pool.kill(agent_id)
    if not ok:
        raise HTTPException(404, "Agent not found")
    return {"status": "killed", "agent_id": agent_id}


@app.post("/api/agents/{agent_id}/pause")
async def pause_agent(agent_id: str):
    pool = get_pool()
    ok = pool.pause(agent_id)
    return {"status": "paused" if ok else "not_running"}


@app.post("/api/agents/{agent_id}/resume")
async def resume_agent(agent_id: str):
    pool = get_pool()
    ok = pool.resume(agent_id)
    return {"status": "resumed" if ok else "not_paused"}


@app.post("/api/agents/{agent_id}/task")
async def submit_agent_task(agent_id: str, req: AgentTaskRequest):
    pool = get_pool()
    task = pool.submit_task(agent_id, req.command, metadata=req.metadata)
    if not task:
        raise HTTPException(404, "Agent not found")
    return {"task_id": task.id, "status": task.status, "command": task.command}


@app.get("/api/agents/{agent_id}/tasks")
async def get_agent_tasks(agent_id: str):
    pool = get_pool()
    tasks = pool.get_agent_tasks(agent_id)
    return {"tasks": [{"id": t.id, "command": t.command, "status": t.status, "result": t.result, "started_at": t.started_at, "completed_at": t.completed_at, "latency_ms": t.latency_ms} for t in tasks]}


@app.get("/api/agents/pool/stats")
async def pool_stats():
    pool = get_pool()
    return pool.get_pool_stats()


@app.get("/api/agents/pool/events")
async def pool_events(limit: int = 50):
    pool = get_pool()
    return {"events": pool.get_event_log(limit)}


# ── NL Command Parser Routes ────────────────────────────────────

@app.post("/api/nl/parse")
async def parse_nl_command(req: NLCommandRequest):
    try:
        from smart_home_manager import get_all_devices
        devices = [{"id": d.id, "name": d.name, "type": d.type, "ip": d.ip, "protocol": d.protocol} for d in get_all_devices()]
    except Exception:
        devices = []

    parsed = parse_command(req.text, devices)
    device_cmd = build_device_command(parsed) if parsed.intent != "chat" else None

    return {
        "parsed": {
            "intent": parsed.intent,
            "device_type": parsed.device_type,
            "device_name": parsed.device_name,
            "device_ip": parsed.device_ip,
            "action": parsed.action,
            "params": parsed.params,
            "confidence": parsed.confidence,
            "method": parsed.method,
        },
        "command": device_cmd,
    }


@app.post("/api/nl/execute")
async def execute_nl_command(req: NLCommandRequest):
    try:
        from smart_home_manager import get_all_devices
        devices = [{"id": d.id, "name": d.name, "type": d.type, "ip": d.ip, "protocol": d.protocol} for d in get_all_devices()]
    except Exception:
        devices = []

    parsed = parse_command(req.text, devices)

    if parsed.intent == "chat":
        return {"status": "chat", "message": "This is a conversational message, not a device command."}

    device_cmd = build_device_command(parsed)

    # Find matching device
    matched_device = None
    for d in devices:
        if parsed.device_ip and d.get("ip") == parsed.device_ip:
            matched_device = d
            break
        if parsed.device_name and parsed.device_name.lower() in d.get("name", "").lower():
            matched_device = d
            break
        if parsed.device_type and d.get("type") == parsed.device_type:
            matched_device = d
            break

    if not matched_device:
        return {"status": "no_device", "parsed": device_cmd, "message": f"No device found matching '{parsed.device_name or parsed.device_type}'"}

    bridge = get_bridge()
    result = bridge.execute(matched_device, device_cmd.get("command", {}))

    return {
        "status": result.status,
        "device": {"name": matched_device.get("name"), "ip": matched_device.get("ip"), "type": matched_device.get("type")},
        "command": device_cmd,
        "result": result.result,
        "latency_ms": result.latency_ms,
    }


# ── Device Bridge Routes ────────────────────────────────────────

@app.get("/api/devices/command-log")
async def device_command_log(limit: int = 50):
    bridge = get_bridge()
    return {"commands": bridge.get_command_log(limit)}


@app.post("/api/devices/control")
async def control_device_direct(req: DeviceControlRequest):
    try:
        from smart_home_manager import get_all_devices
        all_devices = get_all_devices()
    except Exception:
        raise HTTPException(500, "Smart home manager not available")

    device = None
    if req.device_id:
        for d in all_devices:
            if d.id == req.device_id:
                device = {"id": d.id, "name": d.name, "type": d.type, "ip": d.ip, "protocol": d.protocol}
                break
    if not device and req.device_ip:
        for d in all_devices:
            if d.ip == req.device_ip:
                device = {"id": d.id, "name": d.name, "type": d.type, "ip": d.ip, "protocol": d.protocol}
                break

    if not device:
        raise HTTPException(404, "Device not found")

    bridge = get_bridge()
    result = bridge.execute(device, req.command)
    return {"status": result.status, "result": result.result, "latency_ms": result.latency_ms}


# ── Platform Pillar Routes ──────────────────────────────────────

@app.get("/api/platform/latency")
async def get_latency_stats():
    try:
        from multi_agent_router import get_router
        return get_router().get_latency_stats()
    except Exception:
        return {"error": "Router not available"}


@app.get("/api/platform/vault")
async def get_vault_stats():
    try:
        from execution_vault import get_vault
        vault = get_vault()
        return {
            "method": vault._method,
            "violations": vault.get_violations(10),
            "recent_executions": vault.get_execution_log(10),
            "tools_count": len(vault.list_tools()),
        }
    except Exception:
        return {"error": "Vault not available"}


@app.get("/api/platform/healing")
async def get_healing_stats():
    try:
        from self_healing import healer
        return {
            **healer.get_stats(),
            "recent_log": healer.get_healing_log(10),
            "tools": healer.list_tools()[:20],
        }
    except Exception:
        return {"error": "Self-healing engine not available"}


@app.get("/api/platform/grammars")
async def get_grammar_info():
    grammar_dir = os.path.join(os.path.dirname(__file__), "grammars")
    if not os.path.isdir(grammar_dir):
        grammar_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "grammars")
    grammars = []
    if os.path.isdir(grammar_dir):
        for f in os.listdir(grammar_dir):
            if f.endswith(".gbnf"):
                fpath = os.path.join(grammar_dir, f)
                with open(fpath) as fh:
                    content = fh.read()
                grammars.append({
                    "name": f.replace(".gbnf", ""),
                    "file": f,
                    "lines": len(content.split("\n")),
                    "bytes": len(content),
                })
    return {"grammars": grammars, "count": len(grammars)}


# ── Local Model Routes ──────────────────────────────────────────

@app.get("/api/local-model/info")
async def local_model_info():
    try:
        from local_model import engine
        return {
            "is_loaded": engine.is_loaded(),
            "model_info": engine.get_model_info(),
            "available_models": engine.list_available_models(),
            "stats": engine.get_stats(),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/local-model/load")
async def local_model_load(model_name: str = None):
    try:
        from local_model import engine
        ok = engine.load_model(model_name)
        return {"loaded": ok, "model_info": engine.get_model_info()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/local-model/download")
async def local_model_download(repo_id: str, filename: str = None, quantization: str = "Q4_K_M"):
    try:
        from local_model import engine
        path = engine.download_model(repo_id, filename, quantization)
        return {"downloaded": True, "path": path}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/local-model/unload")
async def local_model_unload():
    try:
        from local_model import engine
        engine.unload_model()
        return {"unloaded": True}
    except Exception as e:
        return {"error": str(e)}


# ── Production Sandbox Routes ───────────────────────────────────

@app.get("/api/sandbox/info")
async def sandbox_info():
    try:
        from production_sandbox import sandbox
        return {
            "backend": sandbox.get_backend(),
            "stats": sandbox.get_stats(),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sandbox/execute")
async def sandbox_execute(command: str, language: str = "bash", timeout: int = 30, network: bool = False):
    try:
        from production_sandbox import sandbox
        result = sandbox.execute(command, language=language, timeout=timeout, network=network)
        return {
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
            "exit_code": result.exit_code,
            "execution_time_ms": result.execution_time_ms,
            "backend": result.backend_used,
        }
    except Exception as e:
        return {"error": str(e)}


# ── IoT Protocol Routes ─────────────────────────────────────────

@app.get("/api/iot/protocols")
async def iot_protocols():
    try:
        from iot_protocols import manager
        return {"available": manager.available}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/iot/discover")
async def iot_discover():
    try:
        from iot_protocols import manager
        devices = manager.discover()
        return {"devices": devices, "count": len(devices)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/iot/control")
async def iot_control(protocol: str, device_id: str, command: str, params: dict = None):
    try:
        from iot_protocols import manager
        result = manager.control(protocol, device_id, command, params or {})
        return result
    except Exception as e:
        return {"error": str(e)}


# ── Economic API Routes ─────────────────────────────────────────

@app.get("/api/economic/status")
async def economic_status():
    try:
        from economic_apis import engine
        return {
            "apis_available": {
                "amadeus": bool(os.getenv("AMADEUS_API_KEY")),
                "stripe": bool(os.getenv("STRIPE_SECRET_KEY")),
                "skyscanner": bool(os.getenv("SKYSCANNER_API_KEY")),
                "namecheap": bool(os.getenv("NAMECHEAP_API_USER")),
            }
        }
    except Exception as e:
        return {"error": str(e)}


class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    date: str
    return_date: Optional[str] = None
    passengers: int = 1


@app.post("/api/economic/flights/search")
async def search_flights(req: FlightSearchRequest):
    try:
        from economic_apis import engine
        results = engine.execute_transaction("flight_search", {
            "origin": req.origin,
            "destination": req.destination,
            "date": req.date,
            "return_date": req.return_date,
            "passengers": req.passengers,
        })
        return results
    except Exception as e:
        return {"error": str(e)}


class HotelSearchRequest(BaseModel):
    location: str
    checkin: str
    checkout: str
    guests: int = 1


@app.post("/api/economic/hotels/search")
async def search_hotels(req: HotelSearchRequest):
    try:
        from economic_apis import engine
        results = engine.execute_transaction("hotel_search", {
            "location": req.location,
            "checkin": req.checkin,
            "checkout": req.checkout,
            "guests": req.guests,
        })
        return results
    except Exception as e:
        return {"error": str(e)}


# ── Audit Log Routes ────────────────────────────────────────────

@app.get("/api/audit/events")
async def audit_events(limit: int = 100, event_type: str = None, status: str = None, since: float = None):
    try:
        from audit_log import audit
        events = audit.get_events(limit=limit, event_type=event_type, status=status, since=since)
        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/audit/stats")
async def audit_stats():
    try:
        from audit_log import audit
        return audit.get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/audit/timeline")
async def audit_timeline(hours: int = 24):
    try:
        from audit_log import audit
        return {"timeline": audit.get_timeline(hours)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/audit/errors")
async def audit_errors(limit: int = 20):
    try:
        from audit_log import audit
        return {"errors": audit.get_recent_errors(limit)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/audit/export")
async def audit_export(format: str = "json"):
    try:
        from audit_log import audit
        filepath = audit.export_events(format=format)
        return {"exported": True, "path": filepath, "format": format}
    except Exception as e:
        return {"error": str(e)}


# ── Companion Agent Routes ──────────────────────────────────────

class CompanionRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None


@app.post("/api/companion/process")
async def companion_process(req: CompanionRequest):
    try:
        from companion_agent import companion
        return companion.process(req.text, req.context)
    except Exception as e:
        return {"error": str(e), "mode": "CONVERSATIONAL", "reply": "I'm here for you."}


@app.get("/api/companion/memory")
async def companion_memory(limit: int = 20):
    try:
        from companion_agent import companion
        return {"memories": companion.memory.get_recent(limit), "stats": companion.memory.get_stats()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/companion/memory/store")
async def companion_memory_store(content: str, category: str = "fact", importance: int = 5):
    try:
        from companion_agent import companion
        entry_id = companion.memory.store(content, category, importance)
        return {"stored": True, "id": entry_id}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/companion/memory/recall")
async def companion_memory_recall(query: str, limit: int = 10):
    try:
        from companion_agent import companion
        return {"results": companion.memory.recall(query, limit)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/companion/reminders")
async def companion_reminders():
    try:
        from companion_agent import companion
        return {"reminders": companion.memory.get_active_reminders()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/companion/reminders/create")
async def companion_reminder_create(trigger_text: str, recurring: Optional[str] = None):
    try:
        from companion_agent import companion
        reminder_id = companion.memory.create_reminder(trigger_text, recurring)
        return {"created": True, "id": reminder_id}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/companion/education/stats")
async def companion_education_stats():
    try:
        from companion_agent import companion
        return companion.education.get_retention_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/companion/education/due")
async def companion_education_due(field: str = None, limit: int = 10):
    try:
        from companion_agent import companion
        return {"cards": companion.education.get_due_cards(field, limit)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/companion/education/add")
async def companion_education_add(concept: str, summary: str, quiz_question: str, answer: str, field: str = "general"):
    try:
        from companion_agent import companion
        card_id = companion.education.add_concept(concept, summary, quiz_question, answer, field)
        return {"created": True, "id": card_id}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/companion/education/review")
async def companion_education_review(card_id: int, quality: int):
    try:
        from companion_agent import companion
        result = companion.education.review_card(card_id, quality)
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/companion/crisis/resources")
async def companion_crisis_resources(country: str = "US"):
    try:
        from companion_agent import companion
        return companion.empathy.get_crisis_resources(country)
    except Exception as e:
        return {"error": str(e)}


# ── Hybrid Graph Memory Routes ──────────────────────────────────

@app.get("/api/graph/stats")
async def graph_stats():
    try:
        from graph_memory import memory
        return memory.get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/search")
async def graph_search(query: str, limit: int = 20):
    try:
        from graph_memory import memory
        return {"results": memory.search(query, limit)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/traverse")
async def graph_traverse(start: str, max_hops: int = 3, node_type: str = None):
    try:
        from graph_memory import memory
        return {"results": memory.multi_hop_recall(start, max_hops, node_type)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/context")
async def graph_context(agent_type: str, user_text: str):
    try:
        from graph_memory import memory
        return {"context": memory.inject_context(agent_type, user_text)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/profile")
async def graph_profile():
    try:
        from graph_memory import memory
        return memory.get_user_profile()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/worktree")
async def graph_worktree(root: str = None):
    try:
        from graph_memory import memory
        if root:
            return {"tree": memory.get_worktree(root)}
        return {"due": memory.get_due_reviews()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/graph/worktree/create")
async def graph_worktree_create(root_concept: str, branch_name: str, parent_id: str = None):
    try:
        from graph_memory import memory
        branch_id = memory.create_branch(root_concept, branch_name, parent_id)
        return {"created": True, "id": branch_id}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/graph/worktree/grow")
async def graph_worktree_grow(branch_id: str, child_concept: str):
    try:
        from graph_memory import memory
        child_id = memory.grow_branch(branch_id, child_concept)
        return {"grown": True, "child_id": child_id}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/graph/worktree/review")
async def graph_worktree_review(branch_id: str, quality: int):
    try:
        from graph_memory import memory
        memory.update_mastery(branch_id, quality)
        return {"reviewed": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/graph/extract")
async def graph_extract(text: str, role: str = "user"):
    try:
        from graph_memory import memory
        entities = memory.extract_and_store(text, role)
        return {"extracted": entities, "count": len(entities)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/nodes")
async def graph_nodes(type: str = None, limit: int = 50):
    try:
        from graph_memory import memory
        return {"nodes": memory.find_nodes(type=type, limit=limit)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/edges")
async def graph_edges(node_id: str, direction: str = "both"):
    try:
        from graph_memory import memory
        return {"edges": memory.get_edges(node_id, direction)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph/shortest-path")
async def graph_shortest_path(source: str, target: str):
    try:
        from graph_memory import memory
        return {"path": memory.shortest_path(source, target)}
    except Exception as e:
        return {"error": str(e)}


# ── Advanced Cortex Routes ──────────────────────────────────────

@app.get("/api/cortex/analytics")
async def cortex_analytics():
    try:
        from advanced_cortex import cortex
        return cortex.get_analytics()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/context")
async def cortex_context(user_text: str, agent_type: str = "CORE_AGENT",
                         max_tokens: int = 2000):
    try:
        from advanced_cortex import cortex
        return {"context": cortex.assemble_context(user_text, agent_type, max_tokens=max_tokens)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/emotional/arc")
async def cortex_emotional_arc(hours: float = 168, domain: str = None):
    try:
        from advanced_cortex import cortex
        return {"arc": cortex.get_emotional_arc(hours, domain)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/emotional/summary")
async def cortex_emotional_summary(hours: float = 168):
    try:
        from advanced_cortex import cortex
        return cortex.get_emotional_summary(hours)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/emotional/shifts")
async def cortex_emotional_shifts(threshold: float = 0.3):
    try:
        from advanced_cortex import cortex
        return {"shifts": cortex.detect_emotional_shifts(threshold)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/events/record")
async def cortex_record_event(summary: str, event_type: str = "observation",
                              cause_event_id: str = None, domain: str = None,
                              importance: float = 5.0):
    try:
        from advanced_cortex import cortex
        eid = cortex.record_event(summary, event_type=event_type,
                                  cause_event_id=cause_event_id,
                                  domain=domain, importance=importance)
        return {"event_id": eid, "recorded": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/events/chain")
async def cortex_causal_chain(event_id: str, max_depth: int = 10):
    try:
        from advanced_cortex import cortex
        return {"chain": cortex.get_causal_chain(event_id, max_depth)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/events/timeline")
async def cortex_timeline(domain: str = None, hours: float = 168):
    try:
        from advanced_cortex import cortex
        return {"events": cortex.get_temporal_context(hours=hours, domain=domain)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/predictions/learn")
async def cortex_learn_prediction(trigger: str, outcome: str,
                                  domain: str = "general", confidence: float = 0.5):
    try:
        from advanced_cortex import cortex
        pid = cortex.learn_predictive_pattern(trigger, outcome, domain, confidence)
        return {"pattern_id": pid, "learned": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/predictions/anticipate")
async def cortex_anticipate(context: str, limit: int = 5):
    try:
        from advanced_cortex import cortex
        return {"predictions": cortex.anticipate(context, limit)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/abstractions/create")
async def cortex_create_abstraction(level: str, name: str, description: str = "",
                                    parent_id: str = None):
    try:
        from advanced_cortex import cortex
        aid = cortex.create_abstraction(level, name, description, parent_id)
        return {"abstraction_id": aid, "created": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/abstractions/tree")
async def cortex_abstraction_tree():
    try:
        from advanced_cortex import cortex
        return {"tree": cortex.get_abstraction_tree()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/cross-domain/link")
async def cortex_cross_domain_link(source_domain: str, target_domain: str,
                                   insight: str):
    try:
        from advanced_cortex import cortex
        lid = cortex.create_cross_domain_link(source_domain, target_domain, insight)
        return {"link_id": lid, "created": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/cross-domain/insights")
async def cortex_cross_domain_insights(domain: str = None):
    try:
        from advanced_cortex import cortex
        return {"insights": cortex.get_cross_domain_insights(domain)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/cross-domain/synthesize")
async def cortex_synthesize_domains():
    try:
        from advanced_cortex import cortex
        return cortex.synthesize_domains()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/profile")
async def cortex_user_profile():
    try:
        from advanced_cortex import cortex
        return cortex.get_user_profile()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/profile/personality")
async def cortex_personality_summary():
    try:
        from advanced_cortex import cortex
        return {"personality": cortex.get_personality_summary()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/consolidate")
async def cortex_consolidate(force: bool = False):
    try:
        from advanced_cortex import cortex
        return cortex.consolidate_memories(force)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/drift")
async def cortex_concept_drift():
    try:
        from advanced_cortex import cortex
        return {"drifts": cortex.detect_concept_drift()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/privacy/set")
async def cortex_set_privacy(entity_id: str = None, domain: str = None,
                             rule_type: str = "allow", target: str = "all"):
    try:
        from advanced_cortex import cortex
        cortex.set_privacy(entity_id, domain, rule_type, target)
        return {"set": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/privacy/check")
async def cortex_check_privacy(entity_id: str = None, domain: str = None,
                               action: str = "read"):
    try:
        from advanced_cortex import cortex
        allowed = cortex.check_privacy(entity_id, domain, action)
        return {"allowed": allowed}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/privacy/shared-context")
async def cortex_shared_context(privacy_level: int = 1, domain: str = None):
    try:
        from advanced_cortex import cortex
        return cortex.get_shared_context(privacy_level, domain)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/domain/timeline")
async def cortex_domain_timeline(domain: str, limit: int = 100):
    try:
        from advanced_cortex import cortex
        return {"events": cortex.get_domain_timeline(domain, limit)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/cortex/entities/upsert")
async def cortex_upsert_entity(name: str, entity_type: str, description: str = "",
                               importance: float = 5.0, privacy: int = 1):
    try:
        from advanced_cortex import cortex
        eid = cortex.upsert_entity(name, entity_type, description,
                                   importance=importance, privacy=privacy)
        return {"entity_id": eid, "upserted": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/entities/search")
async def cortex_search_entities(query: str, limit: int = 20):
    try:
        from advanced_cortex import cortex
        return {"results": cortex.search_entities(query, limit)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/cortex/entities/{entity_id}/context")
async def cortex_entity_context(entity_id: str):
    try:
        from advanced_cortex import cortex
        return cortex.get_entity_context(entity_id)
    except Exception as e:
        return {"error": str(e)}


# ── Context Orchestrator Routes ──────────────────────────────────

@app.get("/api/orchestrator/context")
async def orchestrator_context(user_text: str, agent_type: str = "CORE_AGENT",
                                privacy_level: int = 1):
    try:
        from context_orchestrator import orchestrator
        return {"context": orchestrator.assemble_context(user_text, agent_type, privacy_level=privacy_level)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/orchestrator/analytics")
async def orchestrator_analytics():
    try:
        from context_orchestrator import orchestrator
        return orchestrator.get_context_analytics()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/orchestrator/learn")
async def orchestrator_learn(user_text: str, agent_response: str):
    try:
        from context_orchestrator import orchestrator
        orchestrator.learn_from_interaction(user_text, agent_response)
        return {"learned": True}
    except Exception as e:
        return {"error": str(e)}


# ── Sovereign Network Routes ────────────────────────────────────
# The $70B layer: Universal device discovery, control, and telemetry.
# Zero-cloud. The Wi-Fi router becomes a unified hardware bus.


@app.get("/api/sovereign/network/scan")
async def sovereign_network_scan():
    """Trigger a full network scan (mDNS, SSDP, ARP, TCP probe)."""
    try:
        from network_scanner import get_scanner
        scanner = get_scanner()
        devices = scanner.full_scan()
        return {
            "scanned": True,
            "devices_found": len(devices),
            "devices": [d.to_dict() for d in devices.values()],
            "stats": scanner.get_stats(),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/network/devices")
async def sovereign_network_devices(only_alive: bool = True):
    """Get all discovered network devices."""
    try:
        from network_scanner import get_scanner
        scanner = get_scanner()
        devices = scanner.get_alive() if only_alive else scanner.get_all()
        return {
            "count": len(devices),
            "devices": [d.to_dict() for d in devices],
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/network/topology")
async def sovereign_network_topology():
    """Get the full network topology map."""
    try:
        from network_scanner import get_scanner
        scanner = get_scanner()
        return scanner.get_network_topology()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/network/stats")
async def sovereign_network_stats():
    """Get network scanner statistics."""
    try:
        from network_scanner import get_scanner
        scanner = get_scanner()
        return scanner.get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/network/start")
async def sovereign_network_start(scan_interval: int = 30):
    """Start the background network scanning daemon."""
    try:
        from network_scanner import start_scanner
        scanner = start_scanner(scan_interval)
        return {"started": True, "scan_interval": scan_interval}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/devices")
async def sovereign_devices():
    """Get all registered devices from the device manager."""
    try:
        from device_manager import get_all_devices
        devices = get_all_devices()
        return {"count": len(devices), "devices": devices}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/devices/online")
async def sovereign_devices_online():
    """Get all online devices."""
    try:
        from device_manager import get_online_devices
        devices = get_online_devices()
        return {"count": len(devices), "devices": devices}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/devices/{device_id}")
async def sovereign_device_detail(device_id: str):
    """Get detailed info for a single device."""
    try:
        from device_manager import get_device
        device = get_device(device_id)
        if not device:
            return {"error": "Device not found"}
        return device
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/devices/type/{device_type}")
async def sovereign_devices_by_type(device_type: str):
    """Get all devices of a given type (LIGHT, SWITCH, VACUUM, etc.)."""
    try:
        from device_manager import get_devices_by_type
        devices = get_devices_by_type(device_type)
        return {"count": len(devices), "devices": devices}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/devices/room/{room}")
async def sovereign_devices_by_room(room: str):
    """Get all devices in a given room."""
    try:
        from device_manager import get_devices_by_room
        devices = get_devices_by_room(room)
        return {"count": len(devices), "devices": devices}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/devices")
async def sovereign_register_device(device: dict):
    """Register a new device in the sovereign registry."""
    try:
        from device_manager import upsert_device
        result = upsert_device(device)
        return {"registered": True, "device": result}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/sovereign/devices/{device_id}")
async def sovereign_delete_device(device_id: str):
    """Delete a device from the sovereign registry."""
    try:
        from device_manager import delete_device
        deleted = delete_device(device_id)
        return {"deleted": deleted}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/devices/{device_id}/state")
async def sovereign_update_state(device_id: str, state: dict):
    """Update a device's state."""
    try:
        from device_manager import update_device_state
        updated = update_device_state(device_id, state)
        return {"updated": updated}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/devices/{device_id}/history")
async def sovereign_device_history(device_id: str, hours: int = 24):
    """Get state change history for a device."""
    try:
        from device_manager import get_state_history
        history = get_state_history(device_id, hours)
        return {"count": len(history), "history": history}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/command")
async def sovereign_execute_command(
    device_id: str, action: str, params: dict = {},
    initiated_by: str = "user"
):
    """Execute a command on a device via the sovereign command engine."""
    try:
        from command_engine import get_command_engine
        engine = get_command_engine()
        result = engine.execute(device_id, action, params, initiated_by)
        return result.to_dict()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/command/batch")
async def sovereign_batch_commands(commands: list):
    """Execute multiple commands in parallel."""
    try:
        from command_engine import get_command_engine
        engine = get_command_engine()
        results = engine.execute_batch(commands, parallel=True)
        return {"count": len(results), "results": [r.to_dict() for r in results]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/command/history")
async def sovereign_command_history(device_id: str = None, limit: int = 50):
    """Get command execution history."""
    try:
        from device_manager import get_command_history
        history = get_command_history(device_id, limit)
        return {"count": len(history), "history": history}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/command/stats")
async def sovereign_command_stats():
    """Get command execution statistics."""
    try:
        from command_engine import get_command_engine
        return get_command_engine().get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/hal/types")
async def sovereign_hal_types():
    """Get all supported device type definitions."""
    try:
        from universal_hal import get_hal
        hal = get_hal()
        return hal.get_all_types()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/hal/normalize")
async def sovereign_hal_normalize(device: dict):
    """Normalize a raw device into the universal JSON contract."""
    try:
        from universal_hal import get_hal
        hal = get_hal()
        return hal.normalize_device(device)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/scenes")
async def sovereign_scenes():
    """Get all saved scenes."""
    try:
        from device_manager import get_all_scenes
        scenes = get_all_scenes()
        return {"count": len(scenes), "scenes": scenes}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/scenes")
async def sovereign_create_scene(name: str, icon: str = "🎬", device_states: list = []):
    """Create a new scene."""
    try:
        from device_manager import create_scene
        scene = create_scene(name, icon, device_states)
        return {"created": True, "scene": scene}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/scenes/{scene_id}/activate")
async def sovereign_activate_scene(scene_id: str):
    """Activate a scene and return commands to execute."""
    try:
        from device_manager import activate_scene
        result = activate_scene(scene_id)
        if not result:
            return {"error": "Scene not found"}
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/security/stats")
async def sovereign_security_stats():
    """Get sovereign security statistics."""
    try:
        from sovereign_security import get_security
        return get_security().get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/security/auth")
async def sovereign_authenticate(source_ip: str):
    """Authenticate a command source by network pinning."""
    try:
        from sovereign_security import get_security
        security = get_security()
        session = security.network_auth.authenticate_source(source_ip)
        return {
            "authenticated": session.authenticated,
            "session_id": session.session_id,
            "method": session.auth_method,
            "permissions": session.permissions,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/security/keys")
async def sovereign_keys():
    """List all security keys (without material)."""
    try:
        from sovereign_security import get_security
        security = get_security()
        return {"keys": security.key_manager.get_all_keys()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sovereign/security/keys/generate")
async def sovereign_generate_key(purpose: str = "signing", device_id: str = ""):
    """Generate a new security key."""
    try:
        from sovereign_security import get_security
        security = get_security()
        key = security.key_manager.generate_key(purpose, device_id)
        return {"key_id": key.key_id[:8] + "...", "purpose": purpose}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/dashboard")
async def sovereign_dashboard():
    """Get the full sovereign network dashboard."""
    try:
        from device_manager import get_dashboard
        from network_scanner import get_scanner
        from command_engine import get_command_engine
        from sovereign_security import get_security

        dashboard = get_dashboard()
        scanner = get_scanner()
        engine_stats = get_command_engine().get_stats()
        sec_stats = get_security().get_stats()

        return {
            "devices": dashboard["devices"],
            "by_type": dashboard["by_type"],
            "by_room": dashboard["by_room"],
            "by_protocol": dashboard["by_protocol"],
            "commands": dashboard["commands"],
            "recent_commands": dashboard["recent_commands"],
            "network": scanner.get_stats(),
            "security": sec_stats,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sovereign/stats")
async def sovereign_stats():
    """Get overall sovereign system statistics."""
    try:
        from device_manager import get_stats
        from network_scanner import get_scanner
        from command_engine import get_command_engine

        return {
            "registry": get_stats(),
            "network": get_scanner().get_stats(),
            "commands": get_command_engine().get_stats(),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Real Device Control Routes ──────────────────────────────────
# These routes control REAL hardware on the local network.
# No simulations. No placeholders. Real commands, real results.


@app.post("/api/real/tapo/turn_on")
async def real_tapo_turn_on(ip: str):
    """Turn ON a real TP-Link Tapo smart plug."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.add_device(ip)
        return client.turn_on(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/tapo/turn_off")
async def real_tapo_turn_off(ip: str):
    """Turn OFF a real TP-Link Tapo smart plug."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.add_device(ip)
        return client.turn_off(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/tapo/toggle")
async def real_tapo_toggle(ip: str):
    """Toggle a real TP-Link Tapo smart plug."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.add_device(ip)
        return client.toggle(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/real/tapo/info")
async def real_tapo_info(ip: str):
    """Get real device info from a Tapo plug."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.add_device(ip)
        info = client.get_device_info(ip)
        return info or {"error": "Could not reach device"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/real/tapo/energy")
async def real_tapo_energy(ip: str):
    """Get real energy usage from a Tapo P110."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.add_device(ip)
        energy = client.get_energy_usage(ip)
        return energy or {"error": "Could not read energy data"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/real/tapo/set_brightness")
async def real_tapo_brightness(ip: str, brightness: int):
    """Set brightness on a Tapo dimmable plug."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.add_device(ip)
        return client.set_brightness(ip, brightness)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/real/tapo/credentials")
async def real_tapo_set_credentials(username: str, password: str):
    """Set Tapo device credentials."""
    try:
        from tapo_client import get_tapo_client
        client = get_tapo_client()
        client.set_credentials(username, password)
        return {"success": True, "message": "Credentials set"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/real/printer/status")
async def real_printer_status(ip: str):
    """Get real printer status via IPP."""
    try:
        from printer_client import get_printer_client
        client = get_printer_client()
        client.add_printer(ip)
        return client.get_printer_status(ip) or {"error": "Printer not reachable"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/real/printer/ink")
async def real_printer_ink(ip: str):
    """Get real ink levels from an HP printer."""
    try:
        from printer_client import get_printer_client
        client = get_printer_client()
        client.add_printer(ip)
        return client.get_ink_levels(ip) or {"error": "Could not read ink levels"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/real/printer/print")
async def real_printer_print(ip: str, file_path: str, copies: int = 1):
    """Send a real print job to the printer."""
    try:
        from printer_client import get_printer_client
        client = get_printer_client()
        client.add_printer(ip)
        return client.print_file(ip, file_path, copies)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/real/printer/queue")
async def real_printer_queue(ip: str):
    """Get the current print queue."""
    try:
        from printer_client import get_printer_client
        client = get_printer_client()
        client.add_printer(ip)
        return {"jobs": client.get_queue(ip)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/real/printer/cancel")
async def real_printer_cancel(ip: str):
    """Cancel all pending print jobs."""
    try:
        from printer_client import get_printer_client
        client = get_printer_client()
        client.add_printer(ip)
        return client.cancel_jobs(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/phone/connect")
async def real_phone_connect(ip: str, port: int = 5555):
    """Connect to a phone via ADB over WiFi."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.connect_adb(ip, port)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/real/phone/info")
async def real_phone_info(ip: str):
    """Get real device info from a phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        info = client.get_device_info(ip)
        return info or {"error": "Could not reach phone"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/real/phone/battery")
async def real_phone_battery(ip: str):
    """Get real battery level from a phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.get_battery_state(ip)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/real/phone/screen")
async def real_phone_screen(ip: str):
    """Get real screen state from a phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.get_screen_state(ip)
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/real/phone/lock")
async def real_phone_lock(ip: str):
    """Lock a real phone screen."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.lock_screen(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/phone/unlock")
async def real_phone_unlock(ip: str):
    """Unlock a real phone screen."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.unlock_screen(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/phone/launch")
async def real_phone_launch(ip: str, package: str):
    """Launch an app on a real phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.launch_app(ip, package)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/phone/screenshot")
async def real_phone_screenshot(ip: str):
    """Take a real screenshot from a phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.take_screenshot(ip)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/phone/volume")
async def real_phone_volume(ip: str, level: int):
    """Set volume on a real phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.set_volume(ip, "music", level)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/phone/brightness")
async def real_phone_brightness(ip: str, level: int):
    """Set brightness on a real phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.set_brightness(ip, level)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/real/phone/wifi")
async def real_phone_wifi(ip: str):
    """Get WiFi info from a real phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.get_wifi_info(ip)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/real/phone/apps")
async def real_phone_apps(ip: str):
    """Get running apps on a real phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return {"apps": client.get_running_apps(ip)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/real/notify")
async def real_send_notification(ip: str, title: str, message: str):
    """Send a notification to a real phone."""
    try:
        from phone_client import get_phone_client
        client = get_phone_client()
        client.add_phone(ip)
        return client.send_notification(ip, title, message)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/sovereign/devices/sync")
async def sovereign_devices_sync(req: dict):
    """Sync real devices from the local relay agent."""
    try:
        from device_manager import upsert_device
        devices = req.get("devices", [])
        synced = 0
        for device in devices:
            if device.get("ip"):
                upsert_device(device)
                synced += 1
        return {"success": True, "synced": synced}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/real/scan")
async def real_network_scan():
    """Scan the real local network and register discovered devices."""
    try:
        from device_manager import upsert_device
        from network_scanner import get_scanner
        from tapo_client import get_tapo_client
        from printer_client import get_printer_client
        from phone_client import get_phone_client
        import subprocess, re, socket

        scanner = get_scanner()
        tapo = get_tapo_client()
        printer = get_printer_client()
        phone = get_phone_client()

        # Discover Tapo devices
        tapo_devices = tapo.discover_on_network()
        for d in tapo_devices:
            upsert_device({
                "id": f"real_{d['ip'].replace('.', '_')}",
                "name": d["name"],
                "device_type": d["device_type"],
                "ip": d["ip"],
                "protocol": d["protocol"],
                "manufacturer": d["manufacturer"],
                "room": "unknown",
                "state": {"power": "UNKNOWN"},
                "is_online": True,
            })

        # Discover printers
        printers = printer.discover_printers()
        for d in printers:
            if "ip" in d:
                upsert_device({
                    "id": f"real_{d['ip'].replace('.', '_')}",
                    "name": d["name"],
                    "device_type": "PRINTER",
                    "ip": d["ip"],
                    "protocol": "ipp",
                    "manufacturer": d.get("manufacturer", "HP"),
                    "room": "unknown",
                    "state": {"status": "discovered"},
                    "is_online": True,
                })

        # Discover phones
        phones = phone.discover_phones()
        for d in phones:
            upsert_device({
                "id": f"real_{d['ip'].replace('.', '_')}",
                "name": d["name"],
                "device_type": d["device_type"],
                "ip": d["ip"],
                "protocol": d["protocol"],
                "manufacturer": d.get("manufacturer", "Samsung"),
                "model": d.get("model", ""),
                "room": "unknown",
                "state": {"power": "UNKNOWN"},
                "is_online": True,
            })

        # Run network scanner
        net_devices = scanner.full_scan()

        return {
            "success": True,
            "tapo_found": len(tapo_devices),
            "printers_found": len(printers),
            "phones_found": len(phones),
            "network_devices": len(net_devices),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Autonomous Task Endpoints ────────────────────────────────────────

@app.get("/api/autonomous/tasks")
async def autonomous_tasks():
    """List all active autonomous tasks."""
    from autonomous_loop import get_task_loop
    loop = get_task_loop()
    return {"tasks": loop.list_tasks()}

@app.get("/api/autonomous/tasks/{task_id}")
async def autonomous_task_status(task_id: str):
    """Get status of a specific autonomous task."""
    from autonomous_loop import get_task_loop
    loop = get_task_loop()
    return loop.get_status(task_id)

@app.post("/api/autonomous/tasks/stop/{task_id}")
async def autonomous_task_stop(task_id: str):
    """Stop a running autonomous task."""
    from autonomous_loop import get_task_loop
    loop = get_task_loop()
    return loop.stop_task(task_id)

@app.post("/api/autonomous/start")
async def autonomous_start(req: dict):
    """Start an autonomous task."""
    from autonomous_loop import get_task_loop
    import uuid
    loop = get_task_loop()
    task_id = str(uuid.uuid4())[:8]
    intent = req.get("intent", "")
    user_id = req.get("user_id", "local")
    result = loop.start_task(task_id, intent, user_id)
    return result

@app.post("/api/autonomous/start_parallel")
async def autonomous_start_parallel(req: dict):
    """Start multiple autonomous tasks in parallel."""
    from autonomous_loop import get_task_loop
    loop = get_task_loop()
    intents = req.get("intents", [])
    user_id = req.get("user_id", "local")
    return loop.start_parallel(intents, user_id)

@app.get("/api/autonomous/stats")
async def autonomous_stats():
    """Get stats about all tasks."""
    from autonomous_loop import get_task_loop
    loop = get_task_loop()
    tasks = loop.active_tasks
    running = sum(1 for t in tasks.values() if t["status"] == "running")
    completed = sum(1 for t in tasks.values() if t["status"] == "completed")
    failed = sum(1 for t in tasks.values() if t["status"] == "failed")
    return {
        "total": len(tasks),
        "running": running,
        "completed": completed,
        "failed": failed,
        "max_parallel": loop._max_parallel,
    }

@app.get("/api/headless-browser/status")
async def headless_browser_status():
    """Check if headless browser is running."""
    try:
        from headless_browser import get_browser
        browser = get_browser()
        running = browser.chrome_proc is not None and browser.chrome_proc.poll() is None
        return {"running": running, "pid": browser.chrome_proc.pid if running else None}
    except Exception as e:
        return {"running": False, "error": str(e)}

# ── Proactive Engine ──────────────────────────────────────────────────
@app.get("/api/proactive/status")
async def proactive_status():
    """Get proactive engine status."""
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    return engine.get_status()

@app.get("/api/proactive/messages")
async def proactive_messages():
    """Get pending proactive messages."""
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    return {"messages": engine.get_pending_messages()}

@app.post("/api/proactive/reminder")
async def proactive_reminder(req: dict):
    """Schedule a reminder."""
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    message = req.get("message", "")
    delay = req.get("delay_seconds", 60)
    return engine.add_reminder(message, delay)

@app.post("/api/proactive/monitor")
async def proactive_monitor(req: dict):
    """Add a monitor."""
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    monitor_id = req.get("monitor_id", "custom")
    message = req.get("message", "Monitor triggered")
    # For custom monitors, we'd need a check function
    # For now, return status
    return {"status": "monitoring", "monitor_id": monitor_id}

@app.post("/api/proactive/queue")
async def proactive_queue(req: dict):
    """Queue a proactive message."""
    from proactive_engine import get_proactive_engine
    engine = get_proactive_engine()
    message = req.get("message", "")
    engine.queue_message(message)
    return {"status": "queued"}

# ── Universal Action Engine ───────────────────────────────────────────
@app.get("/api/unavailable/intents")
async def universal_intents():
    """Get all available action intents."""
    from universal_engine import get_engine
    engine = get_engine()
    return {"intents": engine.get_available_intents()}

@app.post("/api/universal/recognize")
async def universal_recognize(req: dict):
    """Recognize intent from text."""
    from universal_engine import get_engine
    engine = get_engine()
    text = req.get("text", "")
    return engine.recognize_intent(text)

@app.post("/api/universal/workflow")
async def universal_workflow(req: dict):
    """Get workflow for an intent."""
    from universal_engine import get_engine
    engine = get_engine()
    intent = req.get("intent", "")
    params = req.get("params", {})
    workflow = engine.create_workflow(intent, params)
    return {"workflow": workflow, "summary": engine.format_workflow_summary(workflow)}

# ── Resource Governor ─────────────────────────────────────────────────
@app.get("/api/system/assess")
async def system_assess():
    """Assess system capabilities and return tier + limits."""
    from resource_governor import get_governor
    governor = get_governor()
    return governor.assess()

@app.get("/api/system/status")
async def system_status():
    """Get current resource status and warnings."""
    from resource_governor import get_governor
    governor = get_governor()
    return governor.get_status()

@app.get("/api/system/can_start_agent")
async def system_can_start_agent():
    """Check if we can safely start a new agent."""
    from resource_governor import get_governor
    governor = get_governor()
    return governor.can_start_agent()

@app.get("/api/system/recommended")
async def system_recommended():
    """Get recommended settings for this system."""
    from resource_governor import get_governor
    governor = get_governor()
    return governor.get_recommended_settings()

# ── Smart Browser Manager ─────────────────────────────────────────────
@app.get("/api/system/browsers")
async def system_browsers():
    """Get browser manager status."""
    from browser_manager import get_browser_manager
    return get_browser_manager().get_status()

@app.get("/api/system/browsers/can_start")
async def system_browsers_can_start():
    """Check if we can start a new browser."""
    from browser_manager import get_browser_manager
    return get_browser_manager().can_start_browser()

@app.post("/api/system/browsers/kill_all")
async def system_browsers_kill_all():
    """Kill all browsers to free resources."""
    from browser_manager import get_browser_manager
    get_browser_manager().kill_all()
    return {"status": "all_killed"}

# ── System Controller (Keyboard/Mouse) ────────────────────────────────
@app.post("/api/system/type")
async def system_type(req: dict):
    """Type text on the system."""
    from system_controller import get_controller
    text = req.get("text", "")
    return get_controller().type_string(text)

@app.post("/api/system/key")
async def system_key(req: dict):
    """Press a key or hotkey."""
    from system_controller import get_controller
    keys = req.get("keys", [])
    if len(keys) == 1:
        return get_controller().press_key(keys[0])
    return get_controller().hotkey(*keys)

@app.post("/api/system/mouse/move")
async def system_mouse_move(req: dict):
    """Move mouse to position."""
    from system_controller import get_controller
    return get_controller().mouse_move(req.get("x", 0), req.get("y", 0))

@app.post("/api/system/mouse/click")
async def system_mouse_click(req: dict):
    """Click at position."""
    from system_controller import get_controller
    return get_controller().mouse_click(req.get("x", 0), req.get("y", 0), req.get("button", "left"))

@app.post("/api/system/mouse/scroll")
async def system_mouse_scroll(req: dict):
    """Scroll at position."""
    from system_controller import get_controller
    return get_controller().mouse_scroll(req.get("x", 0), req.get("y", 0), req.get("clicks", 3))

@app.post("/api/system/mouse/drag")
async def system_mouse_drag(req: dict):
    """Drag from (x1,y1) to (x2,y2)."""
    from system_controller import get_controller
    return get_controller().mouse_drag(req.get("x1", 0), req.get("y1", 0), req.get("x2", 0), req.get("y2", 0))

@app.post("/api/system/app/launch")
async def system_app_launch(req: dict):
    """Launch an app."""
    from system_controller import get_controller
    return get_controller().launch_app(req.get("app", ""))

@app.post("/api/system/app/quit")
async def system_app_quit(req: dict):
    """Quit an app."""
    from system_controller import get_controller
    return get_controller().quit_app(req.get("app", ""))

@app.get("/api/system/app/front")
async def system_app_front():
    """Get frontmost app."""
    from system_controller import get_controller
    return get_controller().get_frontmost_app()

@app.get("/api/system/app/running")
async def system_app_running():
    """Get running apps."""
    from system_controller import get_controller
    return get_controller().get_running_apps()

@app.get("/api/system/screen/size")
async def system_screen_size():
    """Get screen dimensions."""
    from system_controller import get_controller
    return get_controller().get_screen_size()

@app.get("/api/system/clipboard")
async def system_clipboard():
    """Get clipboard."""
    from system_controller import get_controller
    return get_controller().get_clipboard()

@app.post("/api/system/clipboard")
async def system_clipboard_set(req: dict):
    """Set clipboard."""
    from system_controller import get_controller
    return get_controller().set_clipboard(req.get("text", ""))

@app.post("/api/system/paste")
async def system_paste(req: dict):
    """Copy text to clipboard then paste it."""
    from system_controller import get_controller
    return get_controller().copy_paste(req.get("text", ""))

# ── Disk Cleaner ──────────────────────────────────────────────────────
@app.get("/api/disk/usage")
async def disk_usage():
    """Get disk usage info."""
    from disk_cleaner import get_cleaner
    return get_cleaner().get_disk_usage()

@app.get("/api/disk/scan")
async def disk_scan():
    """Full system scan for unnecessary files."""
    from disk_cleaner import get_cleaner
    return get_cleaner().scan_all()

@app.get("/api/disk/suggest")
async def disk_suggest():
    """Get cleaning suggestions."""
    from disk_cleaner import get_cleaner
    return {"suggestions": get_cleaner().suggest_cleaning()}

@app.post("/api/disk/clean")
async def disk_clean(req: dict):
    """Clean a category (requires confirm=true)."""
    from disk_cleaner import get_cleaner
    scan_id = req.get("scan_id", "")
    category = req.get("category", "")
    confirm = req.get("confirm", False)
    return get_cleaner().clean_category(scan_id, category, confirm)

@app.post("/api/disk/clean_cache")
async def disk_clean_cache(req: dict):
    """Clean a specific cache dir (requires confirm=true)."""
    from disk_cleaner import get_cleaner
    path = req.get("path", "")
    confirm = req.get("confirm", False)
    return get_cleaner().clean_cache(path, confirm)

# ── Screen Perception ─────────────────────────────────────────────────
@app.get("/api/screen/screenshot")
async def screen_screenshot():
    """Take a full screenshot."""
    from screen_perception import get_perception
    return get_perception().screenshot_full()

@app.post("/api/screen/screenshot_region")
async def screen_screenshot_region(req: dict):
    """Take a screenshot of a region."""
    from screen_perception import get_perception
    return get_perception().screenshot_region(req.get("x", 0), req.get("y", 0), req.get("w", 100), req.get("h", 100))

@app.get("/api/screen/ocr")
async def screen_ocr():
    """OCR the current screen to find all text elements."""
    from screen_perception import get_perception
    return get_perception().ocr_screen()

@app.get("/api/screen/understand")
async def screen_understand():
    """Understand what's on screen."""
    from screen_perception import get_perception
    return get_perception().understand_screen()

@app.get("/api/screen/describe")
async def screen_describe():
    """Describe screen in natural language."""
    from screen_perception import get_perception
    return {"description": get_perception().describe_screen()}

@app.post("/api/screen/find")
async def screen_find(req: dict):
    """Find a UI element by text."""
    from screen_perception import get_perception
    elem = get_perception().find_element(req.get("text", ""))
    if elem:
        return {"found": True, "element": elem}
    return {"found": False, "text": req.get("text", "")}

# ── System Task Agent ─────────────────────────────────────────────────
@app.post("/api/system/execute")
async def system_execute(req: dict):
    """Execute a high-level goal on the desktop."""
    from system_task_agent import get_system_agent
    goal = req.get("goal", "")
    max_steps = req.get("max_steps", 50)
    return get_system_agent().execute_goal(goal, max_steps)

@app.get("/api/system/agent/status")
async def system_agent_status():
    """Get system agent status."""
    from system_task_agent import get_system_agent
    return get_system_agent().get_status()

@app.post("/api/system/agent/stop")
async def system_agent_stop():
    """Stop current task."""
    from system_task_agent import get_system_agent
    get_system_agent().stop()
    return {"status": "stopped"}

@app.post("/api/system/quick")
async def system_quick(req: dict):
    """Execute a quick system action."""
    from system_task_agent import quick_action
    action = req.get("action", "")
    params = req.get("params", {})
    return quick_action(action, params)

# ── Headless Workstation Orchestrator ─────────────────────────────────────
from headless_api import router as headless_router
app.include_router(headless_router)

# ── Multi-Tenant Organization API ─────────────────────────────────────────
from org_api import router as org_router
app.include_router(org_router)

# ── Initialize Multi-Tenant Engine at Startup ──────────────────────────────
@app.on_event("startup")
async def init_multi_tenant():
    try:
        from org_manager import get_org_manager
        mgr = get_org_manager()
        print(f"[OrgManager] Initialized — {len(mgr._orgs)} organizations loaded")
    except Exception as e:
        print(f"[OrgManager] Init skipped: {e}")

# ── Initialize Context Relay & Proactive Engine at Startup ─────────────────
@app.on_event("startup")
async def init_context_relay():
    try:
        from context_relay import get_context_relay
        relay = get_context_relay()
        relay.start_background_sync(interval=300)
        print(f"[ContextRelay] Initialized — platform={relay._platform}, calendar={relay._calendar_source}, email={relay._email_source}")
    except Exception as e:
        print(f"[ContextRelay] Init skipped: {e}")
    try:
        from proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        engine.start()
        print(f"[ProactiveEngine] Initialized — monitoring active")
    except Exception as e:
        print(f"[ProactiveEngine] Init skipped: {e}")

# ── Serve Frontend Static Files (for Electron local mode) ──────────────────
from fastapi.responses import FileResponse, StreamingResponse

@app.get("/api/download/windows")
async def download_windows():
    """Redirect to Windows zip download hosted on HF Space."""
    from fastapi.responses import RedirectResponse
    url = "https://huggingface.co/spaces/dgfhgjhj/jarvis-ai-brain/resolve/main/downloads/JARVIS-Windows.zip"
    return RedirectResponse(url=url)

def _find_frontend_dir():
    """Find the frontend/out directory across dev, packaged, and env-based paths."""
    env_dir = os.environ.get("JARVIS_FRONTEND_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "frontend", "out"),        # dev: backend/ → frontend/out/
        os.path.join(here, "..", "frontend"),                # packaged: resources/frontend/ (extraResources to:"frontend")
        os.path.join(here, "..", "..", "frontend", "out"),   # nested dev
        os.path.join(here, "..", "..", "frontend"),          # nested packaged
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isfile(os.path.join(c, "index.html")):
            return os.path.abspath(c)
    return None

_frontend_out = _find_frontend_dir()

# ── Self-Improvement Engine ──────────────────────────────────────────────

@app.get("/api/learning/metrics/{agent_id}")
async def learning_metrics(agent_id: str):
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    return engine.get_agent_metrics(agent_id)

@app.get("/api/learning/curve/{agent_id}")
async def learning_curve(agent_id: str, days: int = 30):
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    return {"curve": engine.get_learning_curve(agent_id, days)}

@app.get("/api/learning/leaderboard")
async def learning_leaderboard():
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    return {"leaderboard": engine.get_leaderboard()}

@app.post("/api/learning/record")
async def learning_record(data: dict):
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    interaction_id = engine.record_interaction(
        agent_id=data.get("agent_id", "unknown"),
        task_type=data.get("task_type", "general"),
        input_text=data.get("input_text", ""),
        output_text=data.get("output_text", ""),
        strategy_id=data.get("strategy_id"),
        success=data.get("success", True),
        latency_ms=data.get("latency_ms", 0),
        user_feedback=data.get("user_feedback"),
        confidence=data.get("confidence", 0),
    )
    return {"id": interaction_id}

@app.get("/api/learning/strategies/{agent_id}")
async def learning_strategies(agent_id: str):
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    best = engine.get_best_strategy(agent_id)
    return {"best_strategy": best}

@app.post("/api/learning/evolve")
async def learning_evolve(data: dict):
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    new_id = engine.evolve_strategy(data["agent_id"], data["strategy_id"], data["new_parameters"])
    return {"new_strategy_id": new_id}

@app.get("/api/learning/timeline/{agent_id}")
async def learning_timeline(agent_id: str, limit: int = 50):
    engine = get_learning_engine()
    if not engine: return {"error": "engine_unavailable"}
    return {"timeline": engine.get_improvement_timeline(agent_id, limit)}

# ── Device Mesh Orchestration ─────────────────────────────────────────────

@app.get("/api/mesh/topology")
async def mesh_topology():
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable", "nodes": [], "edges": [], "zones": [], "stats": {}}
    return mesh.get_mesh_topology()

@app.get("/api/mesh/devices")
async def mesh_devices(status: str = None, zone: str = None, type: str = None):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable", "devices": []}
    return {"devices": mesh.get_all_devices(status=status, zone=zone, type=type)}

@app.post("/api/mesh/register")
async def mesh_register(data: dict):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable"}
    return mesh.register_device(
        name=data["name"], type=data["type"],
        platform=data.get("platform", "unknown"),
        ip_address=data.get("ip_address", ""),
        capabilities=data.get("capabilities", []),
        zone=data.get("zone", "default"),
        tags=data.get("tags", []),
        relay_id=data.get("relay_id"),
    )

@app.post("/api/mesh/command")
async def mesh_command(data: dict):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable"}
    return mesh.send_command(
        command=data["command"],
        target_device_id=data.get("target_device_id"),
        target_group_id=data.get("target_group_id"),
        retries=data.get("retries", 2),
    )

@app.post("/api/mesh/broadcast")
async def mesh_broadcast(data: dict):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable"}
    return mesh.broadcast_command(
        command=data["command"],
        zone=data.get("zone"),
        device_type=data.get("device_type"),
    )

@app.get("/api/mesh/stats")
async def mesh_stats():
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable"}
    return mesh.get_mesh_stats()

@app.post("/api/mesh/groups")
async def mesh_create_group(data: dict):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable"}
    return mesh.create_group(data["name"], data.get("description", ""), data.get("device_ids", []))

@app.get("/api/mesh/groups")
async def mesh_groups():
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable", "groups": []}
    return {"groups": mesh.get_all_groups()}

@app.post("/api/mesh/zones")
async def mesh_create_zone(data: dict):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable"}
    return mesh.create_zone(data["name"], data.get("description", ""), data.get("device_ids", []))

@app.get("/api/mesh/zones")
async def mesh_zones():
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable", "zones": []}
    return {"zones": mesh.get_all_zones()}

@app.get("/api/mesh/history")
async def mesh_history(limit: int = 50):
    mesh = get_device_mesh()
    if not mesh: return {"error": "engine_unavailable", "history": []}
    return {"history": mesh.get_command_history(limit)}

# ── Autonomous Workflow Engine ─────────────────────────────────────────────

@app.get("/api/workflows")
async def workflows(status: str = None):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable", "workflows": []}
    return {"workflows": engine.get_all_workflows(status)}

@app.post("/api/workflows")
async def create_workflow(data: dict):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable"}
    return engine.create_workflow(
        name=data["name"],
        description=data.get("description", ""),
        trigger_type=data.get("trigger_type", "manual"),
        trigger_config=data.get("trigger_config", {}),
        actions=data.get("actions", []),
        priority=data.get("priority", 5),
    )

@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    engine = get_autonomous_engine()
    if not engine: raise HTTPException(503, "Engine unavailable")
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf

@app.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, data: dict = None):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable"}
    return engine.run_workflow(workflow_id, data or {})

@app.get("/api/workflows/{workflow_id}/runs")
async def workflow_runs(workflow_id: str, limit: int = 20):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable", "runs": []}
    return {"runs": engine.get_workflow_runs(workflow_id, limit)}

@app.post("/api/workflows/events")
async def emit_event(data: dict):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable"}
    event_id = engine.emit_event(data["event_type"], data.get("source", "api"), data.get("payload", {}), data.get("severity", "info"))
    return {"event_id": event_id}

@app.get("/api/workflows/events")
async def get_events(event_type: str = None, limit: int = 100):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable", "events": []}
    return {"events": engine.get_events(event_type, limit)}

@app.post("/api/workflows/feedback")
async def workflow_feedback(data: dict):
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable"}
    engine.add_feedback(data["workflow_id"], data.get("run_id"), data["rating"], data.get("comment", ""))
    return {"status": "recorded"}

@app.get("/api/workflows/stats")
async def workflow_stats():
    engine = get_autonomous_engine()
    if not engine: return {"error": "engine_unavailable"}
    return engine.get_engine_stats()

# ── Enterprise Auth & Teams ──────────────────────────────────────────────

@app.post("/api/auth/register")
async def auth_register(data: dict):
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable"}
    return eng.create_user(data["username"], data["password"], data.get("email"), data.get("display_name"), data.get("role", "viewer"), data.get("team_id"))

@app.post("/api/auth/login")
async def auth_login(data: dict):
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable"}
    result = eng.authenticate(data["username"], data["password"])
    if not result:
        raise HTTPException(401, "Invalid credentials")
    return result

@app.get("/api/auth/me")
async def auth_me(token: str = ""):
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable"}
    user = eng.validate_token(token)
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user

@app.get("/api/enterprise/dashboard")
async def enterprise_dashboard():
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable"}
    return eng.get_compliance_dashboard()

@app.get("/api/enterprise/users")
async def enterprise_users():
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable", "users": []}
    return {"users": eng.get_all_users()}

@app.post("/api/enterprise/teams")
async def enterprise_create_team(data: dict):
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable"}
    return eng.create_team(data["name"], data["owner_id"], data.get("description", ""))

@app.get("/api/enterprise/audit")
async def enterprise_audit(limit: int = 100, user_id: str = None):
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable", "audit_log": []}
    return {"audit_log": eng.get_audit_log(limit, user_id)}

@app.post("/api/enterprise/role")
async def enterprise_role(data: dict):
    eng = get_enterprise_engine()
    if not eng: return {"error": "engine_unavailable"}
    success = eng.update_user_role(data["user_id"], data["new_role"], data["admin_id"])
    if not success:
        raise HTTPException(403, "Not authorized")
    return {"status": "updated"}

# ── Skill Marketplace ────────────────────────────────────────────────────

@app.get("/api/skills")
async def skills(category: str = None, search: str = None):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable", "skills": []}
    return {"skills": mp.get_all_skills(category=category, search=search)}

@app.get("/api/skills/installed")
async def skills_installed():
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable", "skills": []}
    return {"skills": mp.get_all_skills(installed_only=True)}

@app.get("/api/skills/{skill_id}")
async def skill_detail(skill_id: str):
    mp = get_skill_marketplace()
    if not mp: raise HTTPException(503, "Engine unavailable")
    skill = mp.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    reviews = mp.get_reviews(skill_id)
    config = mp.get_skill_config(skill_id)
    return {**skill, "reviews": reviews, "config": config}

@app.post("/api/skills/{skill_id}/install")
async def skill_install(skill_id: str):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable"}
    return mp.install_skill(skill_id)

@app.post("/api/skills/{skill_id}/uninstall")
async def skill_uninstall(skill_id: str):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable"}
    return mp.uninstall_skill(skill_id)

@app.post("/api/skills/{skill_id}/execute")
async def skill_execute(skill_id: str, data: dict = None):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable"}
    return mp.execute_skill(skill_id, data or {})

@app.post("/api/skills/{skill_id}/review")
async def skill_review(skill_id: str, data: dict):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable"}
    return mp.add_review(skill_id, data["rating"], data.get("comment", ""), data.get("user_id", "local"))

@app.get("/api/skills/categories")
async def skill_categories():
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable", "categories": []}
    return {"categories": mp.get_categories()}

@app.get("/api/skills/templates/list")
async def skill_templates(category: str = None):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable", "templates": []}
    return {"templates": mp.get_templates(category)}

@app.post("/api/skills/create")
async def skill_create(data: dict):
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable"}
    return mp.create_skill(data["name"], data["display_name"], data["description"], data["category"], data["entry_point"], data.get("version", "1.0.0"), data.get("author", "local"), data.get("icon", "🧩"))

@app.get("/api/skills/stats")
async def skill_stats():
    mp = get_skill_marketplace()
    if not mp: return {"error": "engine_unavailable"}
    return mp.get_marketplace_stats()


# ── Hardware Detection & AI Model Recommendation ───────────────────────

@app.get("/api/hardware/detect")
async def hardware_detect():
    """Detect user hardware and return full profile with AI model recommendations."""
    try:
        from hardware_detector import detect_hardware
        profile = detect_hardware()
        return profile.to_dict()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/hardware/refresh")
async def hardware_refresh():
    """Force re-detection of hardware (cached result is invalidated)."""
    try:
        from hardware_detector import refresh_hardware_profile
        profile = refresh_hardware_profile()
        return profile.to_dict()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/hardware/tier")
async def hardware_tier():
    """Get just the performance tier and top recommendation."""
    try:
        from hardware_detector import get_hardware_profile
        profile = get_hardware_profile()
        top_model = profile.recommended_models[0] if profile.recommended_models else None
        return {
            "tier": profile.performance_tier,
            "top_recommendation": top_model,
            "config": profile.recommended_config,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/hardware/models")
async def hardware_models():
    """Get all recommended AI models for this hardware."""
    try:
        from hardware_detector import get_hardware_profile
        profile = get_hardware_profile()
        return {
            "models": profile.recommended_models,
            "tier": profile.performance_tier,
            "hardware_summary": {
                "cpu": profile.cpu_brand,
                "ram_gb": profile.ram_total_gb,
                "gpu": f"{profile.gpu_name} ({profile.gpu_vram_gb}GB VRAM)" if profile.gpu_brand != "None" else "None",
            },
        }
    except Exception as e:
        return {"error": str(e)}


if _frontend_out:
    @app.get("/voice_shaurjy/download")
    async def serve_download():
        f = os.path.join(_frontend_out, "download.html")
        if os.path.isfile(f):
            return FileResponse(f, media_type="text/html")
        return {"error": "not found"}

    @app.get("/voice_shaurjy/install")
    async def serve_install():
        f = os.path.join(_frontend_out, "install.html")
        if os.path.isfile(f):
            return FileResponse(f, media_type="text/html")
        return {"error": "not found"}

    @app.get("/voice_shaurjy/welcome")
    async def serve_welcome():
        f = os.path.join(_frontend_out, "welcome.html")
        if os.path.isfile(f):
            return FileResponse(f, media_type="text/html")
        return {"error": "not found"}

    app.mount("/voice_shaurjy", StaticFiles(directory=_frontend_out, html=True), name="frontend")
    print(f"[Frontend] Serving static files from {_frontend_out}")
else:
    print("[Frontend] No frontend/out directory found — running in API-only mode")

# ── Local Run (Electron mode) ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("JARVIS_PORT", "8000"))
    print(f"[JARVIS] Starting on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
