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
  { id: "custom", label: "CUSTOM", icon: "⚙️", desc: "Custom task agent", color: "#71717a" },
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

const statusColor = (s: string) => {
  switch (s) {
    case "running": return "#22c55e";
    case "idle": return "#a78bfa";
    case "completed": return "#06b6d4";
    case "failed": case "error": return "#ef4444";
    case "cancelled": return "#52525b";
    case "paused": return "#eab308";
    default: return "#52525b";
  }
};

const agentTypeMeta = (t: string) => AGENT_TYPES.find(a => a.id === t) || AGENT_TYPES[6];

const formatTime = (ts: number) => {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const formatDuration = (ms: number | null) => {
  if (!ms) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

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
  const [modelLoading, setModelLoading] = useState(false);
  const [modelMsg, setModelMsg] = useState("");

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/agents`);
      const data = await res.json();
      setAgents(data.agents || []);
      setStats(data.stats || null);
    } catch {}
  }, []);

  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/agents/pool/events?limit=30`);
      const data = await res.json();
      setEvents(data.events || []);
    } catch {}
  }, []);

  const fetchLocalModel = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/local-model/info`);
      const data = await res.json();
      setLocalModel(data);
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

  const handleLoadModel = async () => {
    setModelLoading(true);
    setModelMsg("Loading model...");
    try {
      const res = await fetch(`${API}/api/local-model/load`, { method: "POST" });
      const data = await res.json();
      setModelMsg(data.loaded ? "Model loaded!" : "Failed to load model");
      fetchLocalModel();
    } catch (e: any) {
      setModelMsg(`Error: ${e.message}`);
    }
    setTimeout(() => setModelMsg(""), 3000);
    setModelLoading(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)", color: "var(--text-primary)", fontFamily: "var(--font-inter), system-ui, sans-serif" }}>
      <style jsx global>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .agent-card { animation: fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) both; }
        .agent-card:nth-child(1) { animation-delay: 0ms; }
        .agent-card:nth-child(2) { animation-delay: 40ms; }
        .agent-card:nth-child(3) { animation-delay: 80ms; }
        .agent-card:nth-child(4) { animation-delay: 120ms; }
        .agent-card:nth-child(5) { animation-delay: 160ms; }
        .glow-ring { box-shadow: 0 0 0 1px rgba(139,92,246,0.15), 0 0 20px -5px rgba(139,92,246,0.1); }
        .card-hover { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
        .card-hover:hover { border-color: rgba(139,92,246,0.2); background: rgba(139,92,246,0.03); }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.2); border-radius: 2px; }
      `}</style>

      {/* Header */}
      <header style={{ position: "sticky", top: 0, zIndex: 100, borderBottom: "1px solid var(--border-subtle)", background: "rgba(9,9,11,0.85)", backdropFilter: "blur(20px) saturate(180%)" }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <Link href="/" style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 32, height: 32, borderRadius: 8, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)", textDecoration: "none", transition: "all 0.15s", fontSize: 14 }}>
              ←
            </Link>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: stats && stats.running > 0 ? "var(--success)" : "var(--text-muted)", boxShadow: stats && stats.running > 0 ? "0 0 12px rgba(34,197,94,0.4)" : "none", transition: "all 0.3s" }} />
              <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>Agent Pool</span>
            </div>
            {stats && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: 4 }}>
                <span style={{ fontSize: 11, color: "var(--text-muted)", padding: "3px 8px", borderRadius: 6, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)" }}>
                  {stats.running}<span style={{ color: "var(--text-tertiary)" }}>/{stats.max_concurrent}</span> slots
                </span>
                {stats.active_tasks > 0 && (
                  <span style={{ fontSize: 11, color: "var(--accent)", padding: "3px 8px", borderRadius: 6, background: "var(--accent-dim)" }}>
                    {stats.active_tasks} task{stats.active_tasks !== 1 ? "s" : ""}
                  </span>
                )}
              </div>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button onClick={() => setAutoRefresh(!autoRefresh)} style={{ padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: autoRefresh ? "var(--success-dim)" : "var(--bg-secondary)", color: autoRefresh ? "var(--success)" : "var(--text-muted)", border: `1px solid ${autoRefresh ? "rgba(34,197,94,0.2)" : "var(--border-subtle)"}`, transition: "all 0.15s" }}>
              {autoRefresh ? "● Live" : "○ Paused"}
            </button>
            <Link href="/sovereign" style={{ padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, color: "var(--text-muted)", textDecoration: "none", border: "1px solid var(--border-subtle)", background: "var(--bg-secondary)", transition: "all 0.15s" }}>
              Network →
            </Link>
          </div>
        </div>
      </header>

      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* ─── Left Column ─── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Edge Architecture Card */}
          <div className="card-hover" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: 20, animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) both" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em" }}>Edge Architecture</span>
                <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: localModel?.is_loaded ? "var(--success-dim)" : "var(--bg-tertiary)", color: localModel?.is_loaded ? "var(--success)" : "var(--text-muted)", fontWeight: 500 }}>
                  {localModel?.is_loaded ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
              {!localModel?.is_loaded && (
                <button onClick={handleLoadModel} disabled={modelLoading} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--accent-dim)", color: "var(--accent)", border: "1px solid rgba(139,92,246,0.2)", opacity: modelLoading ? 0.5 : 1, transition: "all 0.15s" }}>
                  {modelLoading ? "Loading..." : "Load Model"}
                </button>
              )}
            </div>

            {localModel?.stats && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                <div style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Model</div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: localModel.is_loaded ? "var(--text-primary)" : "var(--text-muted)" }}>
                    {localModel.stats.model_name ? localModel.stats.model_name.split("-").slice(0, 3).join(" ") : "none"}
                  </div>
                </div>
                <div style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>RAM</div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)" }}>{localModel.stats.hardware?.ram_total_human || "—"}</div>
                </div>
                <div style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Inferences</div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)" }}>{localModel.stats.total_inferences}</div>
                </div>
              </div>
            )}
            {modelMsg && (
              <div style={{ marginTop: 10, padding: "8px 12px", borderRadius: 6, background: "var(--accent-dim)", border: "1px solid rgba(139,92,246,0.15)", fontSize: 11, color: "var(--accent)", fontWeight: 500 }}>
                {modelMsg}
              </div>
            )}
          </div>

          {/* Deploy Agent Card */}
          <div className="card-hover" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: 20, animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) 0.05s both" }}>
            <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 14 }}>Deploy Agent</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <input value={spawnName} onChange={e => setSpawnName(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSpawn()} placeholder="Agent name..." style={{ flex: 1, padding: "9px 14px", borderRadius: 8, border: "1px solid var(--border-default)", background: "var(--bg-tertiary)", color: "var(--text-primary)", fontSize: 13, outline: "none", transition: "border-color 0.15s" }} />
              <select value={spawnType} onChange={e => setSpawnType(e.target.value)} style={{ padding: "9px 12px", borderRadius: 8, border: "1px solid var(--border-default)", background: "var(--bg-tertiary)", color: "var(--text-primary)", fontSize: 12, outline: "none", cursor: "pointer" }}>
                {AGENT_TYPES.map(t => <option key={t.id} value={t.id}>{t.icon} {t.label}</option>)}
              </select>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
              {AGENT_TYPES.map(t => (
                <button key={t.id} onClick={() => { setSpawnType(t.id); setSpawnName(`JARVIS ${t.label}`); }} style={{ padding: "5px 10px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: spawnType === t.id ? `${t.color}12` : "var(--bg-tertiary)", color: spawnType === t.id ? t.color : "var(--text-muted)", border: `1px solid ${spawnType === t.id ? `${t.color}25` : "var(--border-subtle)"}`, transition: "all 0.15s" }}>
                  {t.icon} {t.label}
                </button>
              ))}
            </div>
            <button onClick={handleSpawn} disabled={spawning || !spawnName.trim()} style={{ width: "100%", padding: "10px 0", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", background: "var(--accent)", color: "#fff", border: "none", opacity: spawning || !spawnName.trim() ? 0.4 : 1, transition: "all 0.15s", letterSpacing: "-0.01em" }}>
              {spawning ? "Deploying..." : "Deploy Agent"}
            </button>
          </div>

          {/* Agent List Card */}
          <div className="card-hover" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: 20, animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em" }}>Agents</span>
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{agents.length}</span>
            </div>
            {agents.length === 0 && (
              <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: 12 }}>
                <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.3 }}>🤖</div>
                No agents deployed yet
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 400, overflowY: "auto" }}>
              {agents.map(agent => {
                const meta = agentTypeMeta(agent.agent_type);
                return (
                  <div key={agent.id} className="agent-card" onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)} style={{ padding: "12px 14px", borderRadius: 10, cursor: "pointer", background: selectedAgent === agent.id ? "rgba(139,92,246,0.06)" : "var(--bg-tertiary)", border: `1px solid ${selectedAgent === agent.id ? "rgba(139,92,246,0.2)" : "var(--border-subtle)"}`, transition: "all 0.15s" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 8, background: `${meta.color}10`, border: `1px solid ${meta.color}20`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>{meta.icon}</div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 500 }}>{agent.name}</div>
                          <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "monospace" }}>{agent.id.slice(0, 18)}…</div>
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {agent.status === "running" && <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", animation: "pulse 1.5s infinite" }} />}
                        <span style={{ fontSize: 10, fontWeight: 500, padding: "3px 8px", borderRadius: 5, background: `${statusColor(agent.status)}10`, color: statusColor(agent.status), textTransform: "uppercase", letterSpacing: "0.03em" }}>{agent.status}</span>
                      </div>
                    </div>
                    {selectedAgent === agent.id && (
                      <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border-subtle)" }}>
                        <div style={{ display: "flex", gap: 10, marginBottom: 10, fontSize: 11, color: "var(--text-muted)" }}>
                          <span>Tasks: <span style={{ color: "var(--text-secondary)" }}>{agent.total_tasks}</span></span>
                          <span>Errors: <span style={{ color: agent.error_count > 0 ? "var(--error)" : "var(--text-secondary)" }}>{agent.error_count}</span></span>
                          <span>Active: <span style={{ color: agent.current_task ? "var(--success)" : "var(--text-secondary)" }}>{agent.current_task ? "yes" : "no"}</span></span>
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                          {agent.status === "running" && <button onClick={e => { e.stopPropagation(); handlePause(agent.id); }} style={{ padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--warning-dim)", color: "var(--warning)", border: "1px solid rgba(234,179,8,0.2)" }}>Pause</button>}
                          {agent.status === "paused" && <button onClick={e => { e.stopPropagation(); handleResume(agent.id); }} style={{ padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--success-dim)", color: "var(--success)", border: "1px solid rgba(34,197,94,0.2)" }}>Resume</button>}
                          <button onClick={e => { e.stopPropagation(); handleKill(agent.id); }} style={{ padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--error-dim)", color: "var(--error)", border: "1px solid rgba(239,68,68,0.2)" }}>Kill</button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Task Submit */}
          {selectedAgent && (
            <div className="card-hover glow-ring" style={{ background: "var(--bg-secondary)", border: "1px solid rgba(139,92,246,0.2)", borderRadius: 12, padding: 20, animation: "fade-up 0.25s cubic-bezier(0.16, 1, 0.3, 1) both" }}>
              <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 10 }}>
                Task → <span style={{ color: "var(--accent)" }}>{agents.find(a => a.id === selectedAgent)?.name}</span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <input value={taskCommand} onChange={e => setTaskCommand(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSubmitTask()} placeholder="Enter command..." style={{ flex: 1, padding: "9px 14px", borderRadius: 8, border: "1px solid var(--border-default)", background: "var(--bg-tertiary)", color: "var(--text-primary)", fontSize: 13, outline: "none" }} />
                <button onClick={handleSubmitTask} disabled={submitting || !taskCommand.trim()} style={{ padding: "9px 20px", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer", background: "var(--accent)", color: "#fff", border: "none", opacity: submitting || !taskCommand.trim() ? 0.4 : 1, transition: "all 0.15s" }}>
                  {submitting ? "..." : "Run"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ─── Right Column ─── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Cognitive Router */}
          <div className="card-hover" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: 20, animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) 0.05s both" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em" }}>Cognitive Router</span>
              <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "var(--accent-dim)", color: "var(--accent)", fontWeight: 500 }}>SUPERVISOR</span>
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 14 }}>Triage intent → route to OS / HAL / WEB / CORE agent</div>
            <div style={{ display: "flex", gap: 8 }}>
              <input value={dispatchText} onChange={e => setDispatchText(e.target.value)} onKeyDown={e => e.key === "Enter" && handleDispatch()} placeholder="Describe a task..." style={{ flex: 1, padding: "9px 14px", borderRadius: 8, border: "1px solid var(--border-default)", background: "var(--bg-tertiary)", color: "var(--text-primary)", fontSize: 13, outline: "none" }} />
              <button onClick={handleDispatch} disabled={dispatching || !dispatchText.trim()} style={{ padding: "9px 20px", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer", background: "var(--success)", color: "#fff", border: "none", opacity: dispatching || !dispatchText.trim() ? 0.4 : 1, transition: "all 0.15s" }}>
                {dispatching ? "Routing..." : "Dispatch"}
              </button>
            </div>
            {dispatchResult && (
              <div style={{ marginTop: 14, padding: 14, borderRadius: 10, background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)", animation: "fade-up 0.2s ease both" }}>
                {dispatchResult.error ? (
                  <div style={{ color: "var(--error)", fontSize: 12 }}>Error: {dispatchResult.error}</div>
                ) : (
                  <>
                    <div style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 5, background: "var(--accent-dim)", color: "var(--accent)", fontWeight: 500 }}>{dispatchResult.target_agent}</span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{Math.round((dispatchResult.routing?.routing_confidence || 0) * 100)}% confidence</span>
                      <span style={{ fontSize: 11, color: dispatchResult.security_status === "PASSED" ? "var(--success)" : "var(--error)" }}>{dispatchResult.security_status}</span>
                      {dispatchResult.latency_ms?.total && <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{Math.round(dispatchResult.latency_ms.total)}ms</span>}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.6, fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                      {dispatchResult.routing?.extracted_intent || JSON.stringify(dispatchResult.routing, null, 2)}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Task History */}
          {selectedAgent && (
            <div className="card-hover" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: 20, animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both" }}>
              <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 14 }}>Task History</div>
              {agentTasks.length === 0 && (
                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: 12 }}>No tasks yet</div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 300, overflowY: "auto" }}>
                {agentTasks.map(task => (
                  <div key={task.id} style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: "var(--text-secondary)", fontFamily: "monospace" }}>{task.command.slice(0, 50)}{task.command.length > 50 ? "…" : ""}</span>
                      <span style={{ fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4, background: `${statusColor(task.status)}10`, color: statusColor(task.status), textTransform: "uppercase" }}>{task.status}</span>
                    </div>
                    <div style={{ display: "flex", gap: 10, fontSize: 10, color: "var(--text-muted)" }}>
                      <span>{formatDuration(task.latency_ms)}</span>
                      <span>{formatTime(task.started_at || 0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Event Log */}
          <div className="card-hover" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: 20, animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) 0.15s both" }}>
            <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 14 }}>Event Log</div>
            <div style={{ maxHeight: 220, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
              {events.length === 0 && (
                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: 12 }}>No events</div>
              )}
              {events.map((ev, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 10px", borderRadius: 6, fontSize: 11, background: "var(--bg-tertiary)" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: ev.type.includes("spawn") ? "var(--success)" : ev.type.includes("kill") || ev.type.includes("fail") ? "var(--error)" : ev.type.includes("complete") ? "var(--info)" : "var(--text-muted)", flexShrink: 0 }} />
                  <span style={{ color: "var(--text-secondary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ev.type}{ev.name ? ` — ${ev.name}` : ""}</span>
                  {ev.duration_ms && <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>{formatDuration(ev.duration_ms)}</span>}
                  <span style={{ color: "var(--text-muted)", flexShrink: 0, fontFamily: "monospace", fontSize: 10 }}>{formatTime(ev.time)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
