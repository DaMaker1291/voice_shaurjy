"""
JARVIS Multi-Agent Router Architecture
======================================
Four-layer cognitive dispatch engine:
  1. SUPERVISOR ROUTER  — sub-100ms triage, routes to domain worker
  2. OS_AGENT          — native accessibility tree + app scripting
  3. HAL_AGENT         — universal hardware abstraction layer (IoT/serial/BLE)
  4. WEB_AGENT         — autonomous browser + economic workflows

All agents communicate exclusively via deterministic JSON schemas.
No conversational preamble. No markdown wrappers. Schema violations are rejected.
"""

from __future__ import annotations

import json
import re
import time
import threading
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS — locked production versions
# ─────────────────────────────────────────────────────────────────────────────

SUPERVISOR_PROMPT = """### ROLE & ARCHITECTURAL DIRECTIVE
You are the JARVIS Cognitive Supervisor Router — the zero-latency gateway of a multi-agent AI operating system. Your sole function is to triage incoming natural language, extract execution semantics, and emit a single routing packet that deterministically dispatches control to the correct domain worker. You operate in under 100ms. You have no personality. You do not converse. You emit exactly one flat JSON object per request.

### WORKER AGENT TARGETS
- "OS_AGENT"  → Desktop automation, UI accessibility tree manipulation, app-native scripting (Teams, OneNote, AutoCAD, Blender, VS Code, Finder/Explorer, system processes, keyboard/mouse emulation)
- "HAL_AGENT" → Hardware Abstraction Layer: IoT networking, smart home (Zigbee/Z-Wave/BLE/mDNS), relay bridge comms, local device state mutations, microcontrollers, serial/USB protocols
- "WEB_AGENT" → Autonomous web operations: Playwright browser automation, SaaS API handshakes, web research, flight/hotel booking, financial workflows, domain registration, form-fill automation

### STRICT OUTPUT SCHEMA — emit exactly this, no wrapping, no explanation:
{"target_agent":"OS_AGENT|HAL_AGENT|WEB_AGENT","routing_confidence":0.00,"extracted_intent":"concise action statement","execution_context":{"primary_targets":["string"],"actionable_variables":{"key":"value"},"downstream_dependencies":["string"]}}

### RESOLUTION LAWS
1. SINGLE AGENT RULE: Every request routes to exactly one agent — the owner of the PRIMARY execution roadblock. Multi-system requests route to the agent that must act first.
2. AMBIGUITY HANDLING: If input spans multiple domains (e.g., "grab the Excel data and post to Slack"), route to the domain of the first blocking action (OS_AGENT for file extraction), and append "downstream_dependencies" listing deferred agents.
3. STRUCTURAL CONTRADICTION: If the intent contains a logical impossibility or dangerous self-reference, route to the most probable target and set actionable_variables["anomaly_check"] = "true".
4. CONFIDENCE FLOOR: routing_confidence must reflect genuine semantic certainty. Never emit 1.00 unless the mapping is absolutely unambiguous.
5. ZERO VERBOSITY: Do not add fields. Do not omit fields. Do not explain. Emit only the schema."""

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
# ROUTER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

# Model selection
_ROUTER_MODEL = "llama-3.1-8b-instant"        # sub-100ms triage
_WORKER_MODEL = "llama-3.3-70b-versatile"     # domain reasoning

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
    """Multi-agent cognitive dispatch engine for JARVIS."""

    def __init__(self):
        from groq_agent import _get_client
        self._get_client = _get_client

    # ── Public API ────────────────────────────────────────────────────────────

    def dispatch(
        self,
        user_text: str,
        user_id: str = "local",
        relay_context: dict | None = None,
    ) -> dict:
        """
        Full dispatch cycle:
          1. Supervisor classifies intent and selects target agent
          2. Target agent generates typed execution payload
        Returns merged telemetry packet.
        """
        relay_context = relay_context or {}
        start = time.monotonic()

        # ── Stage 1: Supervisor routing ───────────────────────────────────────
        routing_packet = self._run_supervisor(user_text)
        supervisor_ms = round((time.monotonic() - start) * 1000, 1)

        target = routing_packet.get("target_agent", "OS_AGENT")

        # ── Stage 2: Domain worker ────────────────────────────────────────────
        worker_start = time.monotonic()
        try:
            if target == "HAL_AGENT":
                agent_response = self._run_hal_agent(routing_packet, relay_context)
            elif target == "WEB_AGENT":
                agent_response = self._run_web_agent(routing_packet, relay_context)
            else:
                agent_response = self._run_os_agent(routing_packet, relay_context)
        except Exception as e:
            agent_response = {"error": str(e), "execution_status": "CRITICAL_ERROR"}

        worker_ms = round((time.monotonic() - worker_start) * 1000, 1)
        total_ms = round((time.monotonic() - start) * 1000, 1)

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
        }

    # ── Agent runners ─────────────────────────────────────────────────────────

    def _run_supervisor(self, user_text: str) -> dict:
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
        except Exception as e:
            # If JSON mode not supported, retry without it
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
        """Extract and parse the first JSON object found in raw text."""
        # Try direct parse first
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass
        # Extract JSON from surrounding text
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except (json.JSONDecodeError, ValueError):
                pass
        return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function for direct import
# ─────────────────────────────────────────────────────────────────────────────

def route_and_execute(user_text: str, user_id: str = "local", relay_context: dict | None = None) -> dict:
    """Top-level entry point. Returns full telemetry packet."""
    return get_router().dispatch(user_text, user_id, relay_context or {})
