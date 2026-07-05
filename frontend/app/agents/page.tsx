"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

const API = "";

const AGENT_TYPES = [
  { id: "os", label: "OS", icon: "💻", color: "#00FF66" },
  { id: "hal", label: "HAL", icon: "🔌", color: "#00FF66" },
  { id: "web", label: "WEB", icon: "🌐", color: "#00FF66" },
  { id: "chat", label: "CHAT", icon: "💬", color: "#00FF66" },
  { id: "device", label: "DEVICE", icon: "📡", color: "#00FF66" },
  { id: "monitor", label: "MONITOR", icon: "👁", color: "#00FF66" },
  { id: "custom", label: "CUSTOM", icon: "⚙️", color: "#667085" },
];

interface Agent { id: string; name: string; agent_type: string; status: string; total_tasks: number; error_count: number; current_task: string | null; }
interface PoolStats { total_agents: number; running: number; max_concurrent: number; active_tasks: number; }
interface LocalModel { is_loaded: boolean; model_info: any; stats: { model_name: string; total_inferences: number; hardware: { ram_total_human: string }; model_tier: { description: string }; }; }

const statusColor = (s: string) => {
  switch (s) {
    case "running": return "var(--neon-green)";
    case "idle": return "var(--steel)";
    case "paused": return "var(--amber)";
    case "failed": return "var(--crimson)";
    default: return "var(--text-muted)";
  }
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [stats, setStats] = useState<PoolStats | null>(null);
  const [localModel, setLocalModel] = useState<LocalModel | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [spawnName, setSpawnName] = useState("");
  const [spawnType, setSpawnType] = useState("chat");
  const [taskCommand, setTaskCommand] = useState("");
  const [dispatchText, setDispatchText] = useState("");
  const [dispatchResult, setDispatchResult] = useState<any>(null);
  const [spawning, setSpawning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [aRes, mRes] = await Promise.all([fetch(`${API}/api/agents`), fetch(`${API}/api/local-model/info`)]);
      const aData = await aRes.json();
      const mData = await mRes.json();
      setAgents(aData.agents || []);
      setStats(aData.stats || null);
      setLocalModel(mData);
    } catch {}
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    if (!autoRefresh) return;
    const i = setInterval(fetchAll, 3000);
    return () => clearInterval(i);
  }, [autoRefresh, fetchAll]);

  const handleSpawn = async () => {
    if (!spawnName.trim()) return;
    setSpawning(true);
    await fetch(`${API}/api/agents/spawn`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: spawnName.trim(), agent_type: spawnType }) });
    setSpawnName(""); fetchAll(); setSpawning(false);
  };

  const handleSubmitTask = async () => {
    if (!selectedAgent || !taskCommand.trim()) return;
    setSubmitting(true);
    await fetch(`${API}/api/agents/${selectedAgent}/task`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command: taskCommand.trim() }) });
    setTaskCommand(""); fetchAll(); setSubmitting(false);
  };

  const handleDispatch = async () => {
    if (!dispatchText.trim()) return;
    setDispatching(true); setDispatchResult(null);
    try {
      const res = await fetch(`${API}/api/router/dispatch`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_text: dispatchText.trim(), user_id: "local" }) });
      setDispatchResult(await res.json());
    } catch (e: any) { setDispatchResult({ error: e.message }); }
    setDispatching(false);
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--void)", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        .animate-fade { animation: fade-in 0.25s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Header */}
      <header style={{ height: 32, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/" style={{ fontSize: 10, color: "var(--text-muted)", textDecoration: "none" }}>← BACK</Link>
          <div style={{ width: 1, height: 14, background: "var(--border)" }} />
          <span style={{ fontSize: 10, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600 }}>AGENT POOL</span>
          {stats && <span style={{ fontSize: 9, color: "var(--text-muted)" }}>{stats.running}/{stats.max_concurrent}</span>}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button onClick={() => setAutoRefresh(!autoRefresh)} style={{ padding: "3px 8px", borderRadius: 3, fontSize: 9, cursor: "pointer", fontFamily: "var(--font-mono)", background: autoRefresh ? "var(--neon-green-dim)" : "var(--surface-raised)", color: autoRefresh ? "var(--neon-green)" : "var(--text-muted)", border: "1px solid var(--border)", letterSpacing: "0.05em" }}>
            {autoRefresh ? "● LIVE" : "○ OFF"}
          </button>
          <Link href="/sovereign" style={{ padding: "3px 8px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-muted)", textDecoration: "none", border: "1px solid var(--border)", background: "var(--surface-raised)" }}>NETWORK →</Link>
        </div>
      </header>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

          {/* Left: Deploy + Agents */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Deploy */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: 16 }}>
              <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 10 }}>DEPLOY AGENT</div>
              <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                <input value={spawnName} onChange={e => setSpawnName(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSpawn()} placeholder="name..." style={{ flex: 1, padding: "7px 10px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-primary)", fontSize: 11, outline: "none", fontFamily: "var(--font-mono)" }} />
                <select value={spawnType} onChange={e => setSpawnType(e.target.value)} style={{ padding: "7px 8px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-primary)", fontSize: 10, outline: "none", fontFamily: "var(--font-mono)" }}>
                  {AGENT_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
              </div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 8 }}>
                {AGENT_TYPES.map(t => (
                  <button key={t.id} onClick={() => { setSpawnType(t.id); setSpawnName(`JARVIS ${t.label}`); }} style={{ padding: "3px 7px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", cursor: "pointer", background: spawnType === t.id ? "var(--neon-green-dim)" : "var(--surface-raised)", color: spawnType === t.id ? "var(--neon-green)" : "var(--text-muted)", border: `1px solid ${spawnType === t.id ? "rgba(0,255,102,0.2)" : "var(--border)"}` }}>
                    {t.icon} {t.label}
                  </button>
                ))}
              </div>
              <button onClick={handleSpawn} disabled={spawning || !spawnName.trim()} style={{ width: "100%", padding: "7px 0", borderRadius: 4, fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--neon-green)", color: "#000", border: "none", opacity: spawning || !spawnName.trim() ? 0.4 : 1, letterSpacing: "0.05em" }}>
                {spawning ? "DEPLOYING..." : "DEPLOY"}
              </button>
            </div>

            {/* Agent List */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600 }}>AGENTS</span>
                <span style={{ fontSize: 9, color: "var(--text-muted)" }}>{agents.length}</span>
              </div>
              {agents.length === 0 && <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)", fontSize: 10, opacity: 0.4 }}>No agents deployed</div>}
              {agents.map(agent => (
                <div key={agent.id} className="animate-fade" onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)} style={{ padding: "8px 10px", borderRadius: 4, cursor: "pointer", background: selectedAgent === agent.id ? "var(--neon-green-dim)" : "var(--surface-raised)", border: `1px solid ${selectedAgent === agent.id ? "rgba(0,255,102,0.2)" : "var(--border)"}`, marginBottom: 4, transition: "all 0.15s" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 12 }}>{AGENT_TYPES.find(t => t.id === agent.agent_type)?.icon || "⚙️"}</span>
                      <span style={{ fontSize: 11, fontWeight: 500 }}>{agent.name}</span>
                    </div>
                    <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 3, background: `${statusColor(agent.status)}10`, color: statusColor(agent.status), fontWeight: 600 }}>{agent.status}</span>
                  </div>
                  {selectedAgent === agent.id && (
                    <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--border)", display: "flex", gap: 6, fontSize: 9, color: "var(--text-muted)" }}>
                      <span>Tasks: {agent.total_tasks}</span>
                      <span>Errors: {agent.error_count}</span>
                      <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
                        <button onClick={e => { e.stopPropagation(); fetch(`${API}/api/agents/${agent.id}`, { method: "DELETE" }).then(fetchAll); }} style={{ padding: "2px 6px", borderRadius: 3, fontSize: 9, cursor: "pointer", background: "var(--crimson-dim)", color: "var(--crimson)", border: "1px solid rgba(255,51,51,0.2)" }}>Kill</button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Task Submit */}
            {selectedAgent && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border-active)", borderRadius: 6, padding: 16 }}>
                <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>TASK → {agents.find(a => a.id === selectedAgent)?.name}</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <input value={taskCommand} onChange={e => setTaskCommand(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSubmitTask()} placeholder="command..." style={{ flex: 1, padding: "7px 10px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-primary)", fontSize: 11, outline: "none", fontFamily: "var(--font-mono)" }} />
                  <button onClick={handleSubmitTask} disabled={submitting || !taskCommand.trim()} style={{ padding: "7px 14px", borderRadius: 4, fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--neon-green)", color: "#000", border: "none", opacity: submitting || !taskCommand.trim() ? 0.4 : 1 }}>
                    {submitting ? "..." : "RUN"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right: Router + Local Model */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Cognitive Router */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                <span style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600 }}>COGNITIVE ROUTER</span>
                <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: "var(--neon-green-dim)", color: "var(--neon-green)" }}>SUPERVISOR</span>
              </div>
              <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                <input value={dispatchText} onChange={e => setDispatchText(e.target.value)} onKeyDown={e => e.key === "Enter" && handleDispatch()} placeholder="describe task..." style={{ flex: 1, padding: "7px 10px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-primary)", fontSize: 11, outline: "none", fontFamily: "var(--font-mono)" }} />
                <button onClick={handleDispatch} disabled={dispatching || !dispatchText.trim()} style={{ padding: "7px 14px", borderRadius: 4, fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--neon-green)", color: "#000", border: "none", opacity: dispatching || !dispatchText.trim() ? 0.4 : 1 }}>
                  {dispatching ? "..." : "DISPATCH"}
                </button>
              </div>
              {dispatchResult && (
                <div style={{ padding: 10, borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)", fontSize: 10, fontFamily: "var(--font-mono)" }}>
                  {dispatchResult.error ? (
                    <span style={{ color: "var(--crimson)" }}>Error: {dispatchResult.error}</span>
                  ) : (
                    <>
                      <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                        <span style={{ color: "var(--neon-green)" }}>{dispatchResult.target_agent}</span>
                        <span style={{ color: "var(--text-muted)" }}>{Math.round((dispatchResult.routing?.routing_confidence || 0) * 100)}%</span>
                        <span style={{ color: dispatchResult.security_status === "PASSED" ? "var(--neon-green)" : "var(--crimson)" }}>{dispatchResult.security_status}</span>
                      </div>
                      <div style={{ color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>{dispatchResult.routing?.extracted_intent || JSON.stringify(dispatchResult.routing, null, 2)}</div>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Edge Architecture */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: 16 }}>
              <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 10 }}>EDGE ARCHITECTURE</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
                {[
                  { label: "STATUS", value: localModel?.is_loaded ? "ACTIVE" : "INACTIVE", color: localModel?.is_loaded ? "var(--neon-green)" : "var(--text-muted)" },
                  { label: "MODEL", value: localModel?.stats?.model_name?.split("-").slice(0, 3).join(" ") || "none" },
                  { label: "RAM", value: localModel?.stats?.hardware?.ram_total_human || "—" },
                ].map(item => (
                  <div key={item.label} style={{ padding: "6px 8px", background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 4 }}>
                    <div style={{ fontSize: 7, color: "var(--text-muted)", letterSpacing: "0.08em", marginBottom: 3 }}>{item.label}</div>
                    <div style={{ fontSize: 10, color: item.color || "var(--text-secondary)", fontWeight: 500 }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
