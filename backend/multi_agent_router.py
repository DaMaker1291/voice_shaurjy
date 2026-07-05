"""
JARVIS Sovereign Cognitive Operating System — Multi-Agent Router
================================================================
A zero-latency, sandboxed Supervisor-to-Worker cognitive pipeline.
Supports:
  1. Local Inference Moat via llama.cpp + GBNF Grammar (with Cloud Groq Fallback)
  2. Enterprise Security Isolation Vault (Inspects scripts/payloads prior to host execution)
  3. Self-Healing, Loop-Breaking Tool Synthesis (Auto-corrects crashes in sandbox)

Determinisitic schema validation. Zero conversational filler.
"""

from __future__ import annotations

import os
import json
import re
import time
import threading
import traceback
from typing import Any, Dict, Optional

# Security & Self-healing integration
from security_vault import vault
from self_healing import healer

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS — CogOS Production Versions
# ─────────────────────────────────────────────────────────────────────────────

SUPERVISOR_PROMPT = """### ROLE & ARCHITECTURAL DIRECTIVE
You are the JARVIS Cognitive Supervisor Router — the zero-latency gateway of a multi-agent AI operating system. Your sole function is to triage incoming natural language, extract execution semantics, and emit a single routing packet that deterministically dispatches control to the correct domain worker. You operate in under 100ms. You have no personality. You do not converse. You emit exactly one flat JSON object per request.

### WORKER AGENT TARGETS
- "OS_AGENT"  → Desktop automation, UI accessibility tree manipulation, app-native scripting (Teams, OneNote, AutoCAD, Blender, VS Code, Finder/Explorer, system processes, keyboard/mouse emulation)
- "HAL_AGENT" → Hardware Abstraction Layer: IoT networking, smart home (Zigbee/Z-Wave/BLE/mDNS), relay bridge comms, local device state mutations, microcontrollers, serial/USB protocols
- "WEB_AGENT" → Autonomous web operations: Playwright browser automation, SaaS API handshakes, web research, flight/hotel booking, financial workflows, domain registration, form-fill automation
- "CORE_AGENT" → Personal companion: memory retention, reminders, study/revision, empathetic support, emotional well-being, life context management, proactive scheduling

### STRICT OUTPUT SCHEMA — emit exactly this, no wrapping, no explanation:
{"target_agent":"OS_AGENT|HAL_AGENT|WEB_AGENT|CORE_AGENT","routing_confidence":0.00,"extracted_intent":"concise action statement","execution_context":{"primary_targets":["string"],"actionable_variables":{"key":"value"},"downstream_dependencies":["string"]}}

### RESOLUTION LAWS
1. SINGLE AGENT RULE: Every request routes to exactly one agent — the owner of the PRIMARY execution roadblock. Multi-system requests route to the agent that must act first.
2. CORE_AGENT PRIORITY: If the user expresses emotions, stress, anxiety, loneliness, sadness, asks for comfort, mentions forgetting something personal, wants to study or revise, or discusses personal life matters → route to CORE_AGENT.
3. AMBIGUITY HANDLING: If input spans multiple domains (e.g., "grab the Excel data and post to Slack"), route to the domain of the first blocking action (OS_AGENT for file extraction), and append "downstream_dependencies" listing deferred agents.
4. STRUCTURAL CONTRADICTION: If the intent contains a logical impossibility or dangerous self-reference, route to the most probable target and set actionable_variables["anomaly_check"] = "true".
5. CONFIDENCE FLOOR: routing_confidence must reflect genuine semantic certainty. Never emit 1.00 unless the mapping is absolutely unambiguous.
6. ZERO VERBOSITY: Do not add fields. Do not omit fields. Do not explain. Emit only the schema."""

OS_AGENT_PROMPT = """### ROLE & ARCHITECTURAL DIRECTIVE
You are the JARVIS Desktop and Creative Application Execution Agent — the sovereign controller of the local host operating system. You do not simulate, guess, or describe UI elements via visual inference. You interface exclusively with native OS accessibility trees (Win32 UIAutomation, macOS AXUIElement), or you drive software directly through internal scripting runtimes (Blender Python API, AutoCAD AutoLISP, VS Code extension API, PowerShell/.NET interop).

### EXECUTION PRINCIPLES
1. TELEMETRY FACTUALITY: You are forbidden from inventing window positions, application focus states, process IDs, or resource metrics. You operate only on data passed in the current context block. Missing data = UNKNOWN, not fabricated.
2. ACCESSIBILITY OVER VISION: Always resolve UI actions via structural element identifiers (AutomationID, AXIdentifier, ClassName, aria-label) rather than pixel coordinates. Generate coordinate objects only as a final fallback using the accessibility element's bounding rect.
3. INLINE TOOL SYNTHESIS: For applications with scripting surfaces (Blender, AutoCAD, Excel VBA, browsers via DevTools protocol), emit the script body directly. Do not drive these applications via mouse emulation if a native API surface exists.
4. EXECUTION SEQUENCING: Complex tasks must be broken into atomic actions. Emit one action_type per response. The host engine will call you again with updated state if more steps are needed.
5. ERROR ISOLATION: If any target_identifier is UNKNOWN or the required application is not running, set execution_status to CRITICAL_ERROR and populate error_detail. Do not guess an alternative path.

### STRICT OUTPUT SCHEMA — emit exactly this JSON object, no wrapping:
{"system_state_update":{"active_application":"string","execution_status":"PENDING|COMPLETED|CRITICAL_ERROR","error_detail":"string|null","telemetry":{"cpu_allocation":"string","ram_allocation":"string"}},"os_action_payload":{"action_type":"LAUNCH_PROCESS|ACCESSIBILITY_CLICK|SCRIPT_EXECUTION|KEYBOARD_EMULATION|FILE_OPERATION|PROCESS_KILL","target_identifier":"string","script_runtime":"python|powershell|applescript|javascript|null","payload_data":{"script_body":"string|null","coordinates":{"x":0,"y":0},"keystrokes":"string|null","file_path":"string|null","process_args":["string"]}}}

### OPERATIONAL CONSTRAINTS
- script_runtime must match the host OS: python/powershell on Windows, python/applescript on macOS, python/bash on Linux.
- For KEYBOARD_EMULATION, use canonical key names: "ctrl+c", "cmd+space", "alt+f4", "win+r". Never invent key combos.
- For LAUNCH_PROCESS, target_identifier is the executable name or full path, not a display name.
- Emit null for unused payload_data fields. Never omit schema keys."""

HAL_AGENT_PROMPT = """### ROLE & ARCHITECTURAL DIRECTIVE
You are the JARVIS Universal Hardware Abstraction Layer (HAL) Engineer — the machine-language translator between human intent and distributed physical hardware. You command IoT networks, smart home ecosystems, microcontrollers, local relay bridges, and any device reachable via local network, Bluetooth, Zigbee/Z-Wave, USB-Serial, or cloud device APIs. You are protocol-agnostic and brand-agnostic. You transform natural language into precise, machine-executable telemetry definitions.

### MACHINE INTERACTION LAWS
1. PROTOCOL NEUTRALITY: Never output brand-specific lock-in commands. Emit a standard schema containing domain, address, method_signature, and execution_payload. The relay agent handles protocol translation.
2. STATE TRUTHFULNESS: If a device returns null, timeout, or error from the relay — emit that exact state. Mark the endpoint OFFLINE or UNKNOWN. Never synthesize a simulated status. A hallucinated "ON" state for a smart light is a dangerous failure.
3. DEVICE RESOLUTION: Device unique_id must be one of: MAC address, mDNS hostname, IP address, or user-assigned DeviceAlias. Never fabricate an address.
4. MULTI-DEVICE FANS: If the user targets a group ("all living room lights"), emit one payload per device in the device_telemetry_payload array.
5. SAFETY GATES: Irreversible actions (factory reset, firmware flash, power cutoff to critical infrastructure) must set ui_status_flag to "WARNING" and populate troubleshooting_steps with a single confirmation requirement.

### STRICT OUTPUT SCHEMA — emit exactly this JSON object, no wrapping:
{"network_state":{"relay_status":"ONLINE|OFFLINE_BRIDGE_ERROR|CONNECTING","discovered_count":0,"last_scan_epoch":0},"device_telemetry_payload":{"target_domain":"zigbee|zwave|wifi|bluetooth|usb_serial|cloud_api|mdns","unique_id":"string","method_signature":"string","execution_payload":{"key":"value"}},"frontend_ui_mutation":{"target_node":"string","ui_status_flag":"OPTIMAL|WARNING|CRITICAL|OFFLINE|UNKNOWN","state_delta":{"key":"value"},"troubleshooting_steps":["string"]}}

### OPERATIONAL CONSTRAINTS
- method_signature uses dot-notation: "lights.set_brightness", "thermostat.set_temperature", "switch.toggle", "lock.unlock".
- execution_payload keys must match the target device protocol parameters exactly (e.g., {"brightness": 128, "color_temp": 4000}).
- For cloud device APIs (Philips Hue, Nest, Ring, Tuya), target_domain = "cloud_api" and unique_id = the platform device_id.
- troubleshooting_steps must be user-actionable imperative sentences, not technical jargon.
- Emit integer 0 for discovered_count and last_scan_epoch when relay is OFFLINE."""

WEB_AGENT_PROMPT = """### ROLE & ARCHITECTURAL DIRECTIVE
You are the JARVIS Autonomous Web and Economic Execution Agent — an independent digital operative capable of navigating the open web, executing multi-step SaaS workflows, handling financial transactions, managing travel logistics, and interfacing with any public or authenticated web API. You output structured Playwright-compatible automation scripts and API interaction sequences. You do not browse the web yourself — you emit deterministic, executable instruction sets.

### EXECUTION PRINCIPLES
1. SELECTOR PRECISION: All browser automation targets must use stable CSS selectors or ARIA-labeled element references. Never use positional XPath hacks. Prefer data-testid, aria-label, role, or semantic HTML selectors.
2. AUTHENTICATION AWARENESS: If a workflow requires credentials, emit an AUTH_REQUIRED status and specify auth_provider (e.g., "google_oauth", "form_login"). Never embed or request passwords in the schema.
3. ECONOMIC SAFETY: Financial transactions (purchases, bookings, transfers) must set confirmation_required: true. The host will prompt the user before the relay executes.
4. ERROR SURFACE: If a target URL returns 4xx/5xx, or a required element is not found after max_retries, emit FAILED status with error_detail. Never simulate a successful transaction.
5. API-FIRST: If the target service has a documented REST/GraphQL API, prefer API calls over browser automation. Emit api_endpoint, method, and headers schema rather than Playwright steps.

### STRICT OUTPUT SCHEMA — emit exactly this JSON object, no wrapping:
{"web_action_payload":{"workflow_type":"BROWSER_AUTOMATION|API_CALL|HYBRID","target_url":"string","steps":[{"step_id":1,"action":"navigate|click|type|wait|extract|api_call","selector":"string|null","value":"string|null","api_endpoint":"string|null","api_method":"GET|POST|PUT|DELETE|null","api_body":{"key":"value"}}],"auth_required":false,"auth_provider":"string|null","confirmation_required":false,"max_retries":3},"execution_status":"QUEUED|RUNNING|COMPLETED|FAILED|AUTH_REQUIRED","error_detail":"string|null","results_summary":{"extracted_data":{"key":"value"},"confirmation_message":"string|null"}}

### OPERATIONAL CONSTRAINTS
- steps array must be ordered sequentially. The relay executes them atomically in order.
- For API_CALL workflows, target_url is the base URL, and api_endpoint in each step is the path.
- extracted_data in results_summary is populated only after execution by the relay — emit {} when queuing.
- confirmation_message must be plain English actionable summary shown to user before execution of financial steps.
- max_retries defaults to 3. For idempotent GET operations, max_retries can be up to 10."""

# ─────────────────────────────────────────────────────────────────────────────
# ROUTER CONFIG & MODEL INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────

_ROUTER_MODEL = "llama-3.1-8b-instant"        # cloud fast triage
_WORKER_MODEL = "llama-3.3-70b-versatile"     # cloud worker

_engine_instance: "RouterEngine | None" = None
_engine_lock = threading.Lock()


def get_router() -> "RouterEngine":
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = RouterEngine()
    return _engine_instance


class RouterEngine:
    """Sovereign Cognitive Operating System Router for JARVIS."""

    # Latency SLA: supervisor must route in <50ms
    SUPERVISOR_SLA_MS = 50.0
    WORKER_SLA_MS = 2000.0

    def __init__(self):
        from groq_agent import _get_client
        self._get_client = _get_client
        
        self.local_model = None
        self.grammar = None
        self.model_source = "CLOUD_GROQ"

        # Load grammars for all agents
        self.grammars = {}
        self._load_grammars()

        # Latency tracking
        self._latency_history = {"supervisor": [], "worker": [], "total": []}
        self._sla_violations = 0

        # Vault, self-healing, audit
        self._vault = None
        self._healer = None
        self._audit = None
        self._local_model_engine = None
        self._sandbox = None
        self._iot = None
        self._economic = None
        self._init_platform()

        # Try to initialize local model
        try:
            from llama_cpp import Llama, LlamaGrammar
            model_path = "./models/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
            
            if os.path.exists(model_path):
                self.local_model = Llama(
                    model_path=model_path,
                    n_ctx=512,
                    n_threads=4,
                    flash_attn=True,
                    verbose=False
                )
                if "router" in self.grammars:
                    self.grammar = self.grammars["router"]
                self.model_source = "LOCAL_LLAMA"
        except Exception:
            pass

    def _load_grammars(self):
        """Load all GBNF grammar files."""
        grammar_dir = "./backend/grammars"
        if not os.path.isdir(grammar_dir):
            grammar_dir = "./grammars"
        
        if os.path.isdir(grammar_dir):
            for fname in os.listdir(grammar_dir):
                if fname.endswith(".gbnf"):
                    name = fname.replace(".gbnf", "")
                    try:
                        from llama_cpp import LlamaGrammar
                        with open(os.path.join(grammar_dir, fname)) as f:
                            self.grammars[name] = LlamaGrammar.from_string(f.read())
                    except Exception:
                        pass

    def _init_platform(self):
        """Initialize all platform modules: vault, healing, audit, local model, sandbox, IoT, economic."""
        try:
            from execution_vault import get_vault
            self._vault = get_vault()
        except ImportError:
            pass
        try:
            from self_healing import healer
            self._healer = healer
        except ImportError:
            pass
        try:
            from audit_log import audit
            self._audit = audit
        except ImportError:
            pass
        try:
            from local_model import engine as local_engine
            self._local_model_engine = local_engine
            # Try to load local model
            if local_engine.is_loaded() or local_engine.load_model():
                self.local_model = local_engine
                self.model_source = "LOCAL_LLAMA"
        except ImportError:
            pass
        try:
            from production_sandbox import sandbox as prod_sandbox
            self._sandbox = prod_sandbox
        except ImportError:
            pass
        try:
            from iot_protocols import manager as iot_mgr
            self._iot = iot_mgr
        except ImportError:
            pass
        try:
            from economic_apis import engine as econ_engine
            self._economic = econ_engine
        except ImportError:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def dispatch(
        self,
        user_text: str,
        user_id: str = "local",
        relay_context: dict | None = None,
    ) -> dict:
        """
        Cognitive pipeline cycle:
          1. Supervisor Router triages input (local 8B model or cloud).
          2. Selected Worker generates execution JSON parameters.
          3. Production Sandbox executes scripts in isolation.
          4. Security Vault inspects payloads.
          5. Self-healing repairs failures.
          6. Audit Log records everything.
        """
        relay_context = relay_context or {}
        start = time.monotonic()

        # Audit: log dispatch start
        audit_event_id = None
        if self._audit:
            try:
                audit_event_id = self._audit.log_event(
                    event_type="dispatch",
                    action="route",
                    details={"text": user_text[:200]},
                    agent_type="supervisor",
                    status="running",
                    user_id=user_id,
                )
            except Exception:
                pass

        # ── Stage 1: Supervisor routing (local 8B or cloud) ──────────────────
        routing_packet = self._run_supervisor(user_text)
        supervisor_ms = round((time.monotonic() - start) * 1000, 1)

        # Track latency & SLA
        self._latency_history["supervisor"].append(supervisor_ms)
        if len(self._latency_history["supervisor"]) > 100:
            self._latency_history["supervisor"] = self._latency_history["supervisor"][-100:]
        if supervisor_ms > self.SUPERVISOR_SLA_MS:
            self._sla_violations += 1

        target = routing_packet.get("target_agent", "OS_AGENT")

        # ── Stage 2: Domain worker ────────────────────────────────────────────
        worker_start = time.monotonic()
        try:
            if target == "HAL_AGENT":
                agent_response = self._run_hal_agent(routing_packet, relay_context)
            elif target == "WEB_AGENT":
                agent_response = self._run_web_agent(routing_packet, relay_context)
            elif target == "CORE_AGENT":
                agent_response = self._run_core_agent(routing_packet, relay_context)
            else:
                agent_response = self._run_os_agent(routing_packet, relay_context)
        except Exception as e:
            agent_response = {"error": str(e), "execution_status": "CRITICAL_ERROR"}

        worker_ms = round((time.monotonic() - worker_start) * 1000, 1)
        total_ms = round((time.monotonic() - start) * 1000, 1)

        self._latency_history["worker"].append(worker_ms)
        self._latency_history["total"].append(total_ms)
        for key in self._latency_history:
            if len(self._latency_history[key]) > 100:
                self._latency_history[key] = self._latency_history[key][-100:]

        # ── Stage 3: Production Sandbox execution ─────────────────────────────
        script_body = agent_response.get("os_action_payload", {}).get("payload_data", {}).get("script_body")
        if script_body and self._sandbox:
            try:
                sandbox_result = self._sandbox.execute_script(script_body, language="python")
                if sandbox_result.exit_code != 0:
                    agent_response["execution_status"] = "CRITICAL_ERROR"
                    agent_response["error_detail"] = sandbox_result.stderr[:500]
            except Exception as e:
                agent_response["execution_status"] = "CRITICAL_ERROR"
                agent_response["error_detail"] = f"Sandbox error: {str(e)[:200]}"

        # ── Stage 4: Enterprise Security Inspection ────────────────────────────
        security_check = vault.inspect_payload(agent_response)
        if not security_check.get("safe", True):
            agent_response = {
                "system_state_update": {
                    "active_application": "ISOLATION_VAULT",
                    "execution_status": "CRITICAL_ERROR",
                    "error_detail": security_check.get("error", "Security check failed")
                },
                "frontend_ui_mutation": {
                    "target_node": "SECURITY_GATE",
                    "ui_status_flag": "CRITICAL",
                    "troubleshooting_steps": [
                        "Review generated script parameters.",
                        "Script blocked: Outbound network call or dangerous shell commands detected."
                    ]
                }
            }

        # ── Stage 5: Self-healing (if script execution failed) ────────────────
        healed = False
        if (agent_response.get("execution_status") in ("CRITICAL_ERROR", "FAILED")
                and self._healer
                and script_body):
            try:
                repair = self._healer.generate_repair(
                    agent_response.get("error_detail", "unknown error"),
                    "",
                    script_body,
                    context=user_text,
                )
                if repair:
                    # Validate in production sandbox
                    if self._sandbox:
                        vr = self._sandbox.execute_script(repair, language="python")
                        if vr.exit_code == 0:
                            agent_response["os_action_payload"]["payload_data"]["script_body"] = repair
                            agent_response["execution_status"] = "PENDING"
                            healed = True
                            self._healer.register_tool(f"healed_{target}", repair, metadata={"source": user_text[:100]})
                    elif self._vault:
                        vr = self._vault.execute_script(repair, language="python")
                        if not vr.blocked and vr.exit_code == 0:
                            agent_response["os_action_payload"]["payload_data"]["script_body"] = repair
                            agent_response["execution_status"] = "PENDING"
                            healed = True
                            self._healer.register_tool(f"healed_{target}", repair, metadata={"source": user_text[:100]})
            except Exception:
                pass

        # ── Stage 6: Audit logging ────────────────────────────────────────────
        if self._audit and audit_event_id:
            try:
                final_status = "completed" if agent_response.get("execution_status") != "CRITICAL_ERROR" else "failed"
                self._audit.log_agent_complete(
                    audit_event_id,
                    status=final_status,
                    result={"target": target, "healed": healed},
                    latency_ms=int(total_ms),
                )
            except Exception:
                pass

        return {
            "routing": routing_packet,
            "agent_response": agent_response,
            "latency_ms": {
                "supervisor": supervisor_ms,
                "worker": worker_ms,
                "total": total_ms,
            },
            "user_id": user_id,
            "target_agent": target,
            "model_source": self.model_source,
            "security_status": "PASSED" if security_check.get("safe", True) else "BLOCKED",
            "healed": healed,
        }

    def get_latency_stats(self) -> dict:
        """Get latency statistics including P95."""
        stats = {}
        for key, values in self._latency_history.items():
            if values:
                sorted_v = sorted(values)
                p50_idx = len(sorted_v) // 2
                p95_idx = int(len(sorted_v) * 0.95)
                stats[key] = {
                    "current": values[-1],
                    "avg": round(sum(values) / len(values), 1),
                    "p50": round(sorted_v[p50_idx], 1),
                    "p95": round(sorted_v[min(p95_idx, len(sorted_v) - 1)], 1),
                    "min": round(min(values), 1),
                    "max": round(max(values), 1),
                    "samples": len(values),
                }
            else:
                stats[key] = {"current": 0, "avg": 0, "p50": 0, "p95": 0, "min": 0, "max": 0, "samples": 0}
        stats["sla_violations"] = self._sla_violations
        stats["supervisor_sla_ms"] = self.SUPERVISOR_SLA_MS
        return stats

    # ── Agent runners ─────────────────────────────────────────────────────────

    def _run_supervisor(self, user_text: str) -> dict:
        # Check local llama first
        if self.local_model and self.grammar:
            try:
                start = time.perf_counter()
                prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n" \
                         f"Classify input to OS_AGENT, HAL_AGENT, or WEB_AGENT.<|eot_id|>\n" \
                         f"<|start_header_id|>user<|end_header_id|>\n{user_text}<|eot_id|>\n" \
                         f"<|start_header_id|>assistant<|end_header_id|>\n"
                
                output = self.local_model(
                    prompt,
                    max_tokens=40,
                    temperature=0.0,
                    grammar=self.grammar
                )
                raw_text = output["choices"][0]["text"].strip()
                return self._parse_json(raw_text, fallback={
                    "target_agent": "OS_AGENT",
                    "routing_confidence": 0.95,
                    "extracted_intent": user_text,
                    "execution_context": {"primary_targets": [], "actionable_variables": {}, "downstream_dependencies": []}
                })
            except Exception:
                pass # fallback to cloud

        # Fallback to high-speed cloud API
        raw = self._groq_call(
            system_prompt=SUPERVISOR_PROMPT,
            user_msg=user_text,
            max_tokens=256,
            model=_ROUTER_MODEL,
            temperature=0.05,
        )
        return self._parse_json(raw, fallback={
            "target_agent": "OS_AGENT",
            "routing_confidence": 0.5,
            "extracted_intent": user_text,
            "execution_context": {
                "primary_targets": [],
                "actionable_variables": {"parse_error": "true"},
                "downstream_dependencies": [],
            },
        })

    def _run_os_agent(self, routing_packet: dict, context: dict) -> dict:
        user_msg = self._build_worker_prompt(routing_packet, context)
        raw = self._groq_call(
            system_prompt=OS_AGENT_PROMPT,
            user_msg=user_msg,
            max_tokens=512,
            model=_WORKER_MODEL,
            temperature=0.1,
        )
        return self._parse_json(raw, fallback={
            "system_state_update": {
                "active_application": "UNKNOWN",
                "execution_status": "CRITICAL_ERROR",
                "error_detail": "Agent parse failure",
                "telemetry": {"cpu_allocation": "N/A", "ram_allocation": "N/A"},
            },
            "os_action_payload": {
                "action_type": "LAUNCH_PROCESS",
                "target_identifier": "UNKNOWN",
                "script_runtime": None,
                "payload_data": {"script_body": None, "coordinates": {"x": 0, "y": 0}, "keystrokes": None, "file_path": None, "process_args": []},
            },
        })

    def _run_hal_agent(self, routing_packet: dict, context: dict) -> dict:
        user_msg = self._build_worker_prompt(routing_packet, context)
        raw = self._groq_call(
            system_prompt=HAL_AGENT_PROMPT,
            user_msg=user_msg,
            max_tokens=512,
            model=_WORKER_MODEL,
            temperature=0.05,
        )
        return self._parse_json(raw, fallback={
            "network_state": {"relay_status": "OFFLINE_BRIDGE_ERROR", "discovered_count": 0, "last_scan_epoch": 0},
            "device_telemetry_payload": {"target_domain": "UNKNOWN", "unique_id": "UNKNOWN", "method_signature": "UNKNOWN", "execution_payload": {}},
            "frontend_ui_mutation": {"target_node": "UNKNOWN", "ui_status_flag": "UNKNOWN", "state_delta": {}, "troubleshooting_steps": ["Check relay agent is running"]},
        })

    def _run_web_agent(self, routing_packet: dict, context: dict) -> dict:
        user_msg = self._build_worker_prompt(routing_packet, context)
        raw = self._groq_call(
            system_prompt=WEB_AGENT_PROMPT,
            user_msg=user_msg,
            max_tokens=512,
            model=_WORKER_MODEL,
            temperature=0.1,
        )
        return self._parse_json(raw, fallback={
            "web_action_payload": {"workflow_type": "BROWSER_AUTOMATION", "target_url": "UNKNOWN", "steps": [], "auth_required": False, "auth_provider": None, "confirmation_required": False, "max_retries": 3},
            "execution_status": "FAILED",
            "error_detail": "Agent parse failure",
            "results_summary": {"extracted_data": {}, "confirmation_message": None},
        })

    def _run_core_agent(self, routing_packet: dict, context: dict) -> dict:
        """Run CORE_AGENT — companion, memory, education, empathy."""
        try:
            from companion_agent import companion
            user_text = routing_packet.get("extracted_intent", "")
            result = companion.process(user_text, context)
            return result
        except Exception as e:
            return {
                "mode": "CONVERSATIONAL",
                "empathy_note": None,
                "revision_data": None,
                "reminders": [],
                "memory_stored": False,
                "crisis_detected": False,
                "crisis_resources": None,
                "reply": f"I'm here for you. (Companion agent error: {str(e)[:100]})",
                "confidence": 0.5,
            }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_worker_prompt(self, routing_packet: dict, context: dict) -> str:
        lines = [
            f"INTENT: {routing_packet.get('extracted_intent', 'unknown')}",
            f"CONFIDENCE: {routing_packet.get('routing_confidence', 0)}",
            f"PRIMARY_TARGETS: {json.dumps(routing_packet.get('execution_context', {}).get('primary_targets', []))}",
            f"VARIABLES: {json.dumps(routing_packet.get('execution_context', {}).get('actionable_variables', {}))}",
        ]
        if context:
            lines.append(f"RELAY_CONTEXT: {json.dumps(context)[:800]}")
        return "\n".join(lines)

    def _groq_call(
        self,
        system_prompt: str,
        user_msg: str,
        max_tokens: int = 256,
        model: str = _ROUTER_MODEL,
        temperature: float = 0.1,
    ) -> str:
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content.strip()
        except Exception:
            try:
                client = self._get_client()
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            except Exception as e2:
                return f'{{"error": "{str(e2)[:100]}"}}'

    @staticmethod
    def _parse_json(raw: str, fallback: dict) -> dict:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except (json.JSONDecodeError, ValueError):
                pass
        return fallback

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def route_and_execute(user_text: str, user_id: str = "local", relay_context: dict | None = None) -> dict:
    return get_router().dispatch(user_text, user_id, relay_context or {})
