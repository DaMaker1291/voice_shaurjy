"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import AgentNodeMap from "@/components/flightdeck/AgentNodeMap";
import CommandOmniBox from "@/components/flightdeck/CommandOmniBox";
import SystemTelemetry from "@/components/flightdeck/SystemTelemetry";
import InterceptModal from "@/components/flightdeck/InterceptModal";
import DiagnosticsGrid from "@/components/flightdeck/DiagnosticsGrid";

interface ChatMessage {
  role: "user" | "jarvis";
  content: string;
  ts: number;
  agent?: string;
  mode?: string;
  confidence?: number;
}

interface ActivityLog {
  ts: number;
  msg: string;
  agent?: string;
  type: string;
}

interface TelemetryLog {
  ts: number;
  level: "info" | "warn" | "error" | "success" | "vault";
  source: string;
  msg: string;
}

interface InterceptRequest {
  isOpen: boolean;
  actionType: string;
  targetIdentifier: string;
  scriptBody?: string;
  riskLevel: "low" | "medium" | "high" | "critical";
}

const BASE_URL = "https://dgfhgjhj-jarvis-ai-brain.hf.space";

export default function CockpitPage() {
  // State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activityLog, setActivityLog] = useState<ActivityLog[]>([]);
  const [telemetryLogs, setTelemetryLogs] = useState<TelemetryLog[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeAgent, setActiveAgent] = useState<string | undefined>();
  const [routingConfidence, setRoutingConfidence] = useState(0);
  const [latencyMs, setLatencyMs] = useState(0);
  const [systemStats, setSystemStats] = useState<any>(null);
  const [platformData, setPlatformData] = useState<any>(null);
  const [contextNodes, setContextNodes] = useState<{ label: string; type: string; confidence: number }[]>([]);
  const [intercept, setIntercept] = useState<InterceptRequest>({
    isOpen: false,
    actionType: "",
    targetIdentifier: "",
    riskLevel: "medium",
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Fetch platform stats
  const fetchPlatformStats = useCallback(async () => {
    try {
      const [lat, vault, heal, gram, cortex] = await Promise.allSettled([
        fetch(`${BASE_URL}/api/platform/latency`).then((r) => r.json()),
        fetch(`${BASE_URL}/api/platform/vault`).then((r) => r.json()),
        fetch(`${BASE_URL}/api/platform/healing`).then((r) => r.json()),
        fetch(`${BASE_URL}/api/platform/grammars`).then((r) => r.json()),
        fetch(`${BASE_URL}/api/cortex/analytics`).then((r) => r.json()),
      ]);

      const latData = lat.status === "fulfilled" ? lat.value : null;
      const vaultData = vault.status === "fulfilled" ? vault.value : null;
      const healData = heal.status === "fulfilled" ? heal.value : null;
      const gramData = gram.status === "fulfilled" ? gram.value : null;
      const cortexData = cortex.status === "fulfilled" ? cortex.value : null;

      setPlatformData({
        latency: latData,
        vault: vaultData,
        healing: healData,
        grammars: gramData,
        cortex: cortexData,
      });

      if (latData?.supervisor) {
        setLatencyMs(latData.supervisor.current || 0);
      }
    } catch {}
  }, []);

  // Fetch system stats
  const fetchSystemStats = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/system/stats`);
      if (res.ok) {
        setSystemStats(await res.json());
      }
    } catch {}
  }, []);

  // Initial data load
  useEffect(() => {
    fetchPlatformStats();
    fetchSystemStats();
    const platformInterval = setInterval(fetchPlatformStats, 5000);
    const systemInterval = setInterval(fetchSystemStats, 8000);
    return () => {
      clearInterval(platformInterval);
      clearInterval(systemInterval);
    };
  }, [fetchPlatformStats, fetchSystemStats]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  // Handle send
  const handleSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        role: "user",
        content: text,
        ts: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsProcessing(true);

      // Add activity log
      setActivityLog((prev) => [
        ...prev,
        { ts: Date.now(), msg: `User input received: "${text.slice(0, 50)}"`, type: "info" },
      ]);

      // Add telemetry log
      setTelemetryLogs((prev) => [
        ...prev,
        { ts: Date.now(), level: "info", source: "INGEST", msg: `Processing: "${text.slice(0, 60)}"` },
      ]);

      try {
        // Step 1: Route through supervisor
        setActiveAgent(undefined);
        setActivityLog((prev) => [
          ...prev,
          { ts: Date.now(), msg: "Supervisor routing...", agent: "SUPERVISOR", type: "routing" },
        ]);

        const startMs = performance.now();
        const res = await fetch(`${BASE_URL}/api/router/dispatch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, user_id: "local" }),
        });
        const elapsed = performance.now() - startMs;
        setLatencyMs(Math.round(elapsed));

        if (!res.ok) throw new Error(`Router error: ${res.status}`);
        const data = await res.json();

        // Step 2: Identify active agent
        const agent =
          data.target_agent ||
          data.agent ||
          data.routing_packet?.target_agent ||
          "OS_AGENT";
        setActiveAgent(agent);
        setRoutingConfidence(data.routing_confidence || data.confidence || 0.85);

        setActivityLog((prev) => [
          ...prev,
          { ts: Date.now(), msg: `Routed to ${agent} (confidence: ${((data.routing_confidence || 0.85) * 100).toFixed(0)}%)`, agent, type: "routing" },
        ]);

        setTelemetryLogs((prev) => [
          ...prev,
          { ts: Date.now(), level: "success", source: "ROUTER", msg: `Dispatched to ${agent} in ${elapsed.toFixed(0)}ms` },
        ]);

        // Step 3: Extract response
        let reply = "";
        if (data.reply) reply = data.reply;
        else if (data.system_state_update?.active_application) reply = `Executed: ${data.system_state_update.active_application}`;
        else if (data.web_action_payload) reply = `Web action: ${data.web_action_payload.workflow_type}`;
        else if (data.mode) reply = `[${data.mode}] ${data.reply || "Processed"}`;
        else reply = JSON.stringify(data).slice(0, 300);

        const jarvisMsg: ChatMessage = {
          role: "jarvis",
          content: reply,
          ts: Date.now(),
          agent,
          mode: data.mode,
          confidence: data.routing_confidence,
        };
        setMessages((prev) => [...prev, jarvisMsg]);

        // Step 4: Extract context nodes
        const nodes: { label: string; type: string; confidence: number }[] = [];
        if (data.entities_involved) {
          data.entities_involved.forEach((e: any) => {
            nodes.push({ label: e.name || e, type: e.type || "ENTITY", confidence: e.confidence || 0.8 });
          });
        }
        if (data.memory_stored) {
          nodes.push({ label: "Memory Stored", type: "EVENT", confidence: 1.0 });
        }
        setContextNodes(nodes);

        // Step 5: Check for security intercept
        if (data.system_state_update?.execution_status === "CRITICAL_ERROR") {
          setIntercept({
            isOpen: true,
            actionType: data.os_action_payload?.action_type || "UNKNOWN",
            targetIdentifier: data.os_action_payload?.target_identifier || "UNKNOWN",
            scriptBody: data.os_action_payload?.payload_data?.script_body,
            riskLevel: "high",
          });
        }

        // Step 6: Audit log
        setTelemetryLogs((prev) => [
          ...prev,
          {
            ts: Date.now(),
            level: "vault",
            source: "VAULT",
            msg: `Action verified — ${agent} — ${data.execution_status || "OK"}`,
          },
        ]);

        setActivityLog((prev) => [
          ...prev,
          { ts: Date.now(), msg: `Execution complete: ${reply.slice(0, 60)}...`, agent, type: "success" },
        ]);
      } catch (err: any) {
        setMessages((prev) => [
          ...prev,
          { role: "jarvis", content: `Error: ${err.message}`, ts: Date.now() },
        ]);
        setTelemetryLogs((prev) => [
          ...prev,
          { ts: Date.now(), level: "error", source: "ERROR", msg: err.message.slice(0, 100) },
        ]);
      } finally {
        setIsProcessing(false);
        setTimeout(() => setActiveAgent(undefined), 3000);
      }
    },
    []
  );

  // Handle intercept
  const handleInterceptApprove = useCallback(() => {
    setIntercept((prev) => ({ ...prev, isOpen: false }));
    setTelemetryLogs((prev) => [
      ...prev,
      { ts: Date.now(), level: "success", source: "INTERCEPT", msg: "Action approved by user" },
    ]);
  }, []);

  const handleInterceptDeny = useCallback(() => {
    setIntercept((prev) => ({ ...prev, isOpen: false }));
    setTelemetryLogs((prev) => [
      ...prev,
      { ts: Date.now(), level: "warn", source: "INTERCEPT", msg: "Action denied — operation cancelled" },
    ]);
  }, []);

  // Platform data extraction
  const sup = platformData?.latency?.supervisor || {};
  const healingRate =
    platformData?.healing?.total_attempts > 0
      ? platformData.healing.successful_heals / platformData.healing.total_attempts
      : 0;

  return (
    <div className="h-screen flex flex-col bg-zinc-950 text-zinc-200 overflow-hidden">
      {/* Top bar */}
      <header className="h-10 border-b border-white/[0.06] bg-zinc-950/90 backdrop-blur-sm flex items-center px-4 shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            <span className="text-xs font-semibold text-zinc-100 tracking-tight">JARVIS</span>
            <span className="text-[9px] font-mono text-zinc-600">FLIGHT DECK</span>
          </div>
        </div>

        <div className="flex-1" />

        {/* Top-right status indicators */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${isProcessing ? "bg-violet-400 animate-pulse" : "bg-emerald-400"}`} />
            <span className="text-[9px] font-mono text-zinc-500">
              {isProcessing ? "EXECUTING" : "READY"}
            </span>
          </div>
          <div className="text-[9px] font-mono text-zinc-600">
            {latencyMs > 0 && `${latencyMs}ms`}
          </div>
          <div className="text-[9px] font-mono text-zinc-600">
            {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </div>
        </div>
      </header>

      {/* Main content: 3-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT PANEL: Agent Network ── */}
        <div className="w-72 border-r border-white/[0.06] bg-zinc-950/50 flex flex-col shrink-0">
          <AgentNodeMap
            activeAgent={activeAgent}
            routingConfidence={routingConfidence}
            activityLog={activityLog}
          />
        </div>

        {/* ── CENTER PANEL: Chat + Command ── */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages area */}
          <div ref={chatContainerRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                  </svg>
                </div>
                <h2 className="text-lg font-light text-zinc-300 mb-1">JARVIS Flight Deck</h2>
                <p className="text-xs text-zinc-600 max-w-sm">
                  Sovereign Cognitive Operating System — type a command to begin
                </p>
                <div className="flex gap-2 mt-4">
                  {["Open my project", "Ping Sarah", "What's my schedule?", "Show system health"].map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSend(q)}
                      className="px-3 py-1.5 rounded-lg text-[10px] font-mono text-zinc-500 bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700 hover:text-zinc-300 transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[70%] rounded-xl px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-violet-500/10 border border-violet-500/20"
                      : "bg-zinc-900/50 border border-zinc-800/50"
                  }`}
                >
                  {msg.role === "jarvis" && msg.agent && (
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{
                          backgroundColor:
                            msg.agent === "OS_AGENT"
                              ? "#34d399"
                              : msg.agent === "HAL_AGENT"
                              ? "#22d3ee"
                              : msg.agent === "WEB_AGENT"
                              ? "#fbbf24"
                              : "#f472b6",
                        }}
                      />
                      <span className="text-[9px] font-mono text-zinc-500">
                        {msg.agent.replace("_AGENT", "")}
                        {msg.mode && ` · ${msg.mode}`}
                      </span>
                      {msg.confidence && (
                        <span className="text-[8px] font-mono text-zinc-600 ml-auto">
                          {(msg.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  )}
                  <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
                    {msg.content}
                  </p>
                  <div className="text-[8px] font-mono text-zinc-700 mt-1.5">
                    {new Date(msg.ts).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Command Omni-Box */}
          <div className="px-6 pb-4 pt-2 border-t border-white/[0.04]">
            <CommandOmniBox
              onSend={handleSend}
              isProcessing={isProcessing}
              latencyMs={latencyMs}
              activeAgent={activeAgent}
              contextNodes={contextNodes}
            />
          </div>
        </div>

        {/* ── RIGHT PANEL: Telemetry + Diagnostics ── */}
        <div className="w-80 border-l border-white/[0.06] bg-zinc-950/50 flex flex-col shrink-0 overflow-y-auto">
          <SystemTelemetry
            systemStats={systemStats}
            vaultMethod={platformData?.vault?.method}
            sandboxState="SECURE_ISOLATED"
            healingRate={healingRate}
            grammarCount={platformData?.grammars?.count}
            logs={telemetryLogs}
          />

          <div className="border-t border-white/[0.06] px-3 py-3">
            <DiagnosticsGrid
              p95Latency={sup.p95 || 0}
              p50Latency={sup.p50 || 0}
              currentLatency={latencyMs}
              slaViolations={platformData?.latency?.sla_violations || 0}
              selfHealingRate={healingRate}
              totalHeals={platformData?.healing?.total_attempts || 0}
              successfulHeals={platformData?.healing?.successful_heals || 0}
              sandboxMethod={platformData?.vault?.method || "process"}
              grammarCount={platformData?.grammars?.count || 6}
              entityCount={platformData?.cortex?.entities || 0}
              eventCount={platformData?.cortex?.events || 0}
              activeAgents={activeAgent ? 1 : 0}
            />
          </div>
        </div>
      </div>

      {/* Bottom Layer: Intercept Modal */}
      <InterceptModal
        isOpen={intercept.isOpen}
        actionType={intercept.actionType}
        targetIdentifier={intercept.targetIdentifier}
        scriptBody={intercept.scriptBody}
        riskLevel={intercept.riskLevel}
        onApprove={handleInterceptApprove}
        onDeny={handleInterceptDeny}
      />
    </div>
  );
}
