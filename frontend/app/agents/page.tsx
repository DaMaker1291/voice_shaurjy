"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";

const API = "";

const AGENT_TYPES = [
  { id: "os", label: "OS", icon: "💻", desc: "Desktop automation, apps, files", color: "#6366f1" },
  { id: "hal", label: "HAL", icon: "🔌", desc: "IoT, smart home, devices", color: "#22c55e" },
  { id: "web", label: "WEB", icon: "🌐", desc: "Browser automation, APIs", color: "#f59e0b" },
  { id: "chat", label: "CHAT", icon: "💬", desc: "Conversation, memory", color: "#ec4899" },
  { id: "device", label: "DEVICE", icon: "📡", desc: "Network device control", color: "#06b6d4" },
  { id: "monitor", label: "MONITOR", icon: "👁", desc: "System monitoring", color: "#a78bfa" },
  { id: "custom", label: "CUSTOM", icon: "⚙️", desc: "Custom task agent", color: "#52525b" },
];

interface Agent {
  id: string;
  name: string;
  agent_type: string;
  status: string;
  created_at: number;
  last_active: number;
  current_task: string | null;
  total_tasks: number;
  error_count: number;
  capabilities: string[];
  tags: string[];
  memory: Record<string, any>;
}

interface Task {
  id: string;
  command: string;
  status: string;
  result: any;
  started_at: number | null;
  completed_at: number | null;
  latency_ms: number | null;
}

interface PoolStats {
  total_agents: number;
  running: number;
  idle: number;
  failed: number;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  active_tasks: number;
  max_concurrent: number;
  utilization: string;
}

interface LocalModel {
  is_loaded: boolean;
  model_info: { name: string; path: string; n_ctx: number; n_threads: number; quantization: string; size_human: string } | null;
  stats: {
    model_loaded: boolean;
    model_name: string;
    total_inferences: number;
    avg_tokens_per_second: number;
    hardware: { ram_total_mb: number; ram_total_human: string };
    model_tier: { tier: number; description: string; ram_required_mb?: number };
  };
}

interface Event {
  type: string;
  time: number;
  agent_id?: string;
  task_id?: string;
  status?: string;
  duration_ms?: number;
  command?: string;
  name?: string;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [stats, setStats] = useState<PoolStats | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [agentTasks, setAgentTasks] = useState<Task[]>([]);
  const [spawnName, setSpawnName] = useState("");
  const [spawnType, setSpawnType] = useState("chat");
  const [taskCommand, setTaskCommand] = useState("");
  const [dispatchText, setDispatchText] = useState("");
  const [dispatchResult, setDispatchResult] = useState<any>(null);
  const [dispatching, setDispatching] = useState(false);
  const [spawning, setSpawning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [localModel, setLocalModel] = useState<LocalModel | null>(null);
  const eventsRef = useRef<HTMLDivElement>(null);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/agents`);
      const data = await res.json();
      setAgents(data.agents || []);
      setStats(data.stats || null);
    } catch {}
  }, []);

  const fetchLocalModel = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/local-model/info`);
      const data = await res.json();
      setLocalModel(data);
    } catch {}
  }, []);

  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/agents/pool/events?limit=30`);
      const data = await res.json();
      setEvents(data.events || []);
    } catch {}
  }, []);

  const fetchAgentTasks = useCallback(async (agentId: string) => {
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/tasks`);
      const data = await res.json();
      setAgentTasks(data.tasks || []);
    } catch {}
  }, []);

  useEffect(() => {
    fetchAgents();
    fetchEvents();
    fetchLocalModel();
  }, [fetchAgents, fetchEvents, fetchLocalModel]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchAgents();
      fetchEvents();
      fetchLocalModel();
      if (selectedAgent) fetchAgentTasks(selectedAgent);
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchAgents, fetchEvents, fetchLocalModel, selectedAgent, fetchAgentTasks]);

  useEffect(() => {
    if (selectedAgent) fetchAgentTasks(selectedAgent);
  }, [selectedAgent, fetchAgentTasks]);

  const handleSpawn = async () => {
    if (!spawnName.trim()) return;
    setSpawning(true);
    try {
      const res = await fetch(`${API}/api/agents/spawn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: spawnName.trim(), agent_type: spawnType }),
      });
      if (res.ok) {
        setSpawnName("");
        fetchAgents();
      }
    } catch {}
    setSpawning(false);
  };

  const handleSubmitTask = async () => {
    if (!selectedAgent || !taskCommand.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/agents/${selectedAgent}/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: taskCommand.trim() }),
      });
      if (res.ok) {
        setTaskCommand("");
        fetchAgentTasks(selectedAgent);
        fetchAgents();
      }
    } catch {}
    setSubmitting(false);
  };

  const handleDispatch = async () => {
    if (!dispatchText.trim()) return;
    setDispatching(true);
    setDispatchResult(null);
    try {
      const res = await fetch(`${API}/api/router/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_text: dispatchText.trim(), user_id: "local" }),
      });
      const data = await res.json();
      setDispatchResult(data);
    } catch (e: any) {
      setDispatchResult({ error: e.message });
    }
    setDispatching(false);
  };

  const handleKill = async (agentId: string) => {
    await fetch(`${API}/api/agents/${agentId}`, { method: "DELETE" });
    if (selectedAgent === agentId) setSelectedAgent(null);
    fetchAgents();
  };

  const handlePause = async (agentId: string) => {
    await fetch(`${API}/api/agents/${agentId}/pause`, { method: "POST" });
    fetchAgents();
  };

  const handleResume = async (agentId: string) => {
    await fetch(`${API}/api/agents/${agentId}/resume`, { method: "POST" });
    fetchAgents();
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "running": return "#22c55e";
      case "idle": return "#a78bfa";
      case "completed": return "#06b6d4";
      case "failed": case "error": return "#ef4444";
      case "cancelled": return "#52525b";
      case "paused": return "#f59e0b";
      default: return "#52525b";
    }
  };

  const agentTypeIcon = (t: string) => AGENT_TYPES.find(a => a.id === t)?.icon || "⚙️";
  const agentTypeColor = (t: string) => AGENT_TYPES.find(a => a.id === t)?.color || "#52525b";

  const formatTime = (ts: number) => {
    if (!ts) return "—";
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return "—";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0a0a0f", color: "#fafafa", fontFamily: "'Inter', -apple-system, sans-serif" }}>
      {/* Header */}
      <div style={{ position: "sticky", top: 0, zIndex: 100, borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(10,10,15,0.95)", backdropFilter: "blur(20px)" }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "0 20px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Link href="/" style={{ color: "#52525b", textDecoration: "none", fontSize: 18 }}>←</Link>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
            </svg>
            <span style={{ fontSize: 16, fontWeight: 600 }}>Agent Pool</span>
            {stats && (
              <span style={{ fontSize: 11, color: "#52525b", background: "rgba(255,255,255,0.04)", padding: "2px 8px", borderRadius: 4 }}>
                {stats.running} running / {stats.utilization} slots
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              style={{
                padding: "4px 10px", borderRadius: 4, fontSize: 11, fontWeight: 500, cursor: "pointer",
                background: autoRefresh ? "rgba(34,197,94,0.1)" : "rgba(255,255,255,0.04)",
                color: autoRefresh ? "#22c55e" : "#52525b",
                border: `1px solid ${autoRefresh ? "rgba(34,197,94,0.2)" : "rgba(255,255,255,0.06)"}`,
              }}
            >
              {autoRefresh ? "● LIVE" : "○ PAUSED"}
            </button>
            <Link href="/sovereign" style={{ padding: "4px 10px", borderRadius: 4, fontSize: 11, fontWeight: 500, color: "#52525b", textDecoration: "none", border: "1px solid rgba(255,255,255,0.06)" }}>
              Network
            </Link>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Left Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Local Model Status */}
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Edge Architecture
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: localModel?.is_loaded ? "#22c55e" : "#52525b" }} />
              <span style={{ fontSize: 12, color: localModel?.is_loaded ? "#22c55e" : "#52525b" }}>
                {localModel?.is_loaded ? "LOCAL ROUTING ACTIVE" : "CLOUD ROUTING (no local model)"}
              </span>
            </div>
            {localModel?.stats && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 11 }}>
                <div style={{ padding: "6px 8px", borderRadius: 4, background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ color: "#52525b", marginBottom: 2 }}>Model</div>
                  <div style={{ color: "#a1a1aa" }}>{localModel.stats.model_name || "none"}</div>
                </div>
                <div style={{ padding: "6px 8px", borderRadius: 4, background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ color: "#52525b", marginBottom: 2 }}>Tier</div>
                  <div style={{ color: "#a1a1aa" }}>{localModel.stats.model_tier?.description || "—"}</div>
                </div>
                <div style={{ padding: "6px 8px", borderRadius: 4, background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ color: "#52525b", marginBottom: 2 }}>RAM</div>
                  <div style={{ color: "#a1a1aa" }}>{localModel.stats.hardware?.ram_total_human || "—"}</div>
                </div>
                <div style={{ padding: "6px 8px", borderRadius: 4, background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ color: "#52525b", marginBottom: 2 }}>Inferences</div>
                  <div style={{ color: "#a1a1aa" }}>{localModel.stats.total_inferences}</div>
                </div>
              </div>
            )}
            {localModel?.model_info && (
              <div style={{ marginTop: 8, padding: "6px 8px", borderRadius: 4, background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.1)", fontSize: 10, color: "#22c55e" }}>
                {localModel.model_info.size_human} · {localModel.model_info.quantization} · {localModel.model_info.n_ctx} ctx · {localModel.model_info.n_threads} threads
              </div>
            )}
          </div>

          {/* Spawn Panel */}
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Deploy Agent</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
              <input
                value={spawnName}
                onChange={e => setSpawnName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSpawn()}
                placeholder="Agent name..."
                style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fafafa", fontSize: 13, outline: "none" }}
              />
              <select
                value={spawnType}
                onChange={e => setSpawnType(e.target.value)}
                style={{ padding: "8px 10px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fafafa", fontSize: 12, outline: "none", cursor: "pointer" }}
              >
                {AGENT_TYPES.map(t => (
                  <option key={t.id} value={t.id}>{t.icon} {t.label}</option>
                ))}
              </select>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {AGENT_TYPES.map(t => (
                <button
                  key={t.id}
                  onClick={() => { setSpawnType(t.id); setSpawnName(`JARVIS ${t.label}`); }}
                  style={{
                    padding: "4px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer",
                    background: spawnType === t.id ? `${t.color}15` : "rgba(255,255,255,0.02)",
                    color: spawnType === t.id ? t.color : "#52525b",
                    border: `1px solid ${spawnType === t.id ? `${t.color}30` : "rgba(255,255,255,0.04)"}`,
                  }}
                >
                  {t.icon} {t.label}
                </button>
              ))}
            </div>
            <button
              onClick={handleSpawn}
              disabled={spawning || !spawnName.trim()}
              style={{
                width: "100%", marginTop: 10, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
                background: "rgba(139,92,246,0.1)", color: "#a78bfa", border: "1px solid rgba(139,92,246,0.2)",
                opacity: spawning || !spawnName.trim() ? 0.5 : 1,
              }}
            >
              {spawning ? "Deploying..." : "Deploy Agent"}
            </button>
          </div>

          {/* Agent List */}
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Agents ({agents.length})
            </div>
            {agents.length === 0 && (
              <div style={{ textAlign: "center", padding: "30px 0", color: "#52525b", fontSize: 12 }}>No agents deployed yet</div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 400, overflowY: "auto" }}>
              {agents.map(agent => (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)}
                  style={{
                    padding: "10px 12px", borderRadius: 8, cursor: "pointer",
                    background: selectedAgent === agent.id ? "rgba(139,92,246,0.08)" : "rgba(255,255,255,0.02)",
                    border: `1px solid ${selectedAgent === agent.id ? "rgba(139,92,246,0.2)" : "rgba(255,255,255,0.04)"}`,
                    transition: "all 0.15s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 16 }}>{agentTypeIcon(agent.agent_type)}</span>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{agent.name}</div>
                        <div style={{ fontSize: 10, color: "#52525b" }}>{agent.id.slice(0, 16)}...</div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 3, background: `${statusColor(agent.status)}15`, color: statusColor(agent.status) }}>
                        {agent.status.toUpperCase()}
                      </span>
                      {agent.status === "running" && (
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", animation: "pulse 1.5s infinite" }} />
                      )}
                    </div>
                  </div>
                  {selectedAgent === agent.id && (
                    <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                      <div style={{ display: "flex", gap: 6, marginBottom: 8, fontSize: 10, color: "#52525b" }}>
                        <span>Tasks: {agent.total_tasks}</span>
                        <span>·</span>
                        <span>Errors: {agent.error_count}</span>
                        <span>·</span>
                        <span>Active: {agent.current_task ? "yes" : "no"}</span>
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        {agent.status === "running" && (
                          <button onClick={(e) => { e.stopPropagation(); handlePause(agent.id); }} style={{ padding: "3px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer", background: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.2)" }}>Pause</button>
                        )}
                        {agent.status === "paused" && (
                          <button onClick={(e) => { e.stopPropagation(); handleResume(agent.id); }} style={{ padding: "3px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer", background: "rgba(34,197,94,0.1)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.2)" }}>Resume</button>
                        )}
                        <button onClick={(e) => { e.stopPropagation(); handleKill(agent.id); }} style={{ padding: "3px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer", background: "rgba(239,68,68,0.1)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.2)" }}>Kill</button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Task Submit */}
          {selectedAgent && (
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Submit Task → {agents.find(a => a.id === selectedAgent)?.name}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  value={taskCommand}
                  onChange={e => setTaskCommand(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSubmitTask()}
                  placeholder="Enter command..."
                  style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fafafa", fontSize: 13, outline: "none" }}
                />
                <button
                  onClick={handleSubmitTask}
                  disabled={submitting || !taskCommand.trim()}
                  style={{
                    padding: "8px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
                    background: "rgba(139,92,246,0.1)", color: "#a78bfa", border: "1px solid rgba(139,92,246,0.2)",
                    opacity: submitting || !taskCommand.trim() ? 0.5 : 1,
                  }}
                >
                  {submitting ? "..." : "Run"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Cognitive Router Dispatch */}
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Cognitive Router
            </div>
            <div style={{ fontSize: 11, color: "#52525b", marginBottom: 10 }}>
              Supervisor triages intent → routes to OS / HAL / WEB / CORE agent
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={dispatchText}
                onChange={e => setDispatchText(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleDispatch()}
                placeholder="Describe a task..."
                style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fafafa", fontSize: 13, outline: "none" }}
              />
              <button
                onClick={handleDispatch}
                disabled={dispatching || !dispatchText.trim()}
                style={{
                  padding: "8px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
                  background: "rgba(34,197,94,0.1)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.2)",
                  opacity: dispatching || !dispatchText.trim() ? 0.5 : 1,
                }}
              >
                {dispatching ? "Routing..." : "Dispatch"}
              </button>
            </div>
            {dispatchResult && (
              <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)", fontSize: 11 }}>
                {dispatchResult.error ? (
                  <span style={{ color: "#ef4444" }}>Error: {dispatchResult.error}</span>
                ) : (
                  <>
                    <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                      <span style={{ color: "#a78bfa" }}>Target: {dispatchResult.target_agent}</span>
                      <span style={{ color: "#52525b" }}>·</span>
                      <span style={{ color: "#52525b" }}>Confidence: {((dispatchResult.routing?.routing_confidence || 0) * 100).toFixed(0)}%</span>
                      <span style={{ color: "#52525b" }}>·</span>
                      <span style={{ color: dispatchResult.security_status === "PASSED" ? "#22c55e" : "#ef4444" }}>{dispatchResult.security_status}</span>
                    </div>
                    <div style={{ color: "#a1a1aa", lineHeight: 1.5 }}>
                      {JSON.stringify(dispatchResult.routing?.extracted_intent || dispatchResult.routing, null, 2)}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Agent Tasks */}
          {selectedAgent && (
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Task History
              </div>
              {agentTasks.length === 0 && (
                <div style={{ textAlign: "center", padding: "20px 0", color: "#52525b", fontSize: 11 }}>No tasks yet</div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 300, overflowY: "auto" }}>
                {agentTasks.map(task => (
                  <div key={task.id} style={{ padding: "8px 10px", borderRadius: 6, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 11, color: "#a1a1aa" }}>{task.command.slice(0, 60)}{task.command.length > 60 ? "..." : ""}</span>
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, background: `${statusColor(task.status)}15`, color: statusColor(task.status) }}>
                        {task.status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 9, color: "#52525b" }}>
                      <span>{formatDuration(task.latency_ms)}</span>
                      <span>{formatTime(task.started_at || 0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Event Log */}
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Event Log
            </div>
            <div ref={eventsRef} style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: 3 }}>
              {events.length === 0 && (
                <div style={{ textAlign: "center", padding: "20px 0", color: "#52525b", fontSize: 11 }}>No events</div>
              )}
              {events.map((ev, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 8px", borderRadius: 4, fontSize: 10, background: "rgba(255,255,255,0.01)" }}>
                  <span style={{ color: ev.type.includes("spawn") ? "#22c55e" : ev.type.includes("kill") || ev.type.includes("fail") ? "#ef4444" : ev.type.includes("complete") ? "#06b6d4" : "#52525b" }}>
                    {ev.type}
                  </span>
                  {ev.name && <span style={{ color: "#a1a1aa" }}>{ev.name}</span>}
                  {ev.duration_ms && <span style={{ color: "#52525b" }}>{formatDuration(ev.duration_ms)}</span>}
                  <span style={{ color: "#3f3f46", marginLeft: "auto" }}>{formatTime(ev.time)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <style jsx global>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.2); border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,0.3); }
      `}</style>
    </div>
  );
}
