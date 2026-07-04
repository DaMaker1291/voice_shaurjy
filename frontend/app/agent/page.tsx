"use client";

import { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/Navbar";
import { BASE } from "@/lib/api";

interface Agent {
  id: string;
  name: string;
  type: string;
  status: string;
  task_count: number;
  created_at: number;
  tags: string[];
}

interface AgentTask {
  id: string;
  command: string;
  status: string;
  result: any;
  started_at?: number;
  completed_at?: number;
  latency_ms?: number;
}

interface PoolStats {
  total_agents: number;
  running: number;
  paused: number;
  idle: number;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
}

interface PoolEvent {
  timestamp: number;
  type: string;
  agent_id: string;
  agent_name: string;
  detail: string;
}

const AGENT_TYPES = [
  { value: "chat", label: "Chat", desc: "General conversation and Q&A" },
  { value: "coding", label: "Coding", desc: "Code generation and debugging" },
  { value: "research", label: "Research", desc: "Web search and analysis" },
  { value: "automation", label: "Automation", desc: "Task automation and scripting" },
  { value: "monitoring", label: "Monitoring", desc: "System and service monitoring" },
  { value: "analysis", label: "Analysis", desc: "Data analysis and insights" },
];

const STATUS_COLORS: Record<string, string> = {
  running: "bg-emerald-400",
  paused: "bg-amber-400",
  idle: "bg-zinc-500",
  completed: "bg-emerald-400",
  failed: "bg-red-400",
  pending: "bg-violet-400",
};

export default function AgentDashboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [stats, setStats] = useState<PoolStats | null>(null);
  const [events, setEvents] = useState<PoolEvent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [agentTasks, setAgentTasks] = useState<AgentTask[]>([]);
  const [spawnType, setSpawnType] = useState("chat");
  const [spawnName, setSpawnName] = useState("");
  const [spawning, setSpawning] = useState(false);
  const [taskCommand, setTaskCommand] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [nlInput, setNlInput] = useState("");
  const [nlResult, setNlResult] = useState<any>(null);
  const [parsing, setParsing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/api/agents`);
      const data = await r.json();
      setAgents(data.agents || []);
      setStats(data.stats || null);
    } catch {}
    try {
      const r = await fetch(`${BASE}/api/agents/pool/events?limit=30`);
      const data = await r.json();
      setEvents(data.events || []);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const i = setInterval(refresh, 5000);
    return () => clearInterval(i);
  }, [refresh]);

  const refreshAgentTasks = useCallback(async (agentId: string) => {
    try {
      const r = await fetch(`${BASE}/api/agents/${agentId}/tasks`);
      const data = await r.json();
      setAgentTasks(data.tasks || []);
    } catch {}
  }, []);

  useEffect(() => {
    if (selectedAgent) {
      refreshAgentTasks(selectedAgent.id);
      const i = setInterval(() => refreshAgentTasks(selectedAgent.id), 3000);
      return () => clearInterval(i);
    }
  }, [selectedAgent, refreshAgentTasks]);

  const spawnAgent = async () => {
    if (!spawnName.trim()) return;
    setSpawning(true);
    try {
      await fetch(`${BASE}/api/agents/spawn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: spawnName, agent_type: spawnType }),
      });
      setSpawnName("");
      refresh();
    } catch {}
    setSpawning(false);
  };

  const killAgent = async (id: string) => {
    await fetch(`${BASE}/api/agents/${id}`, { method: "DELETE" });
    if (selectedAgent?.id === id) setSelectedAgent(null);
    refresh();
  };

  const pauseAgent = async (id: string) => {
    await fetch(`${BASE}/api/agents/${id}/pause`, { method: "POST" });
    refresh();
  };

  const resumeAgent = async (id: string) => {
    await fetch(`${BASE}/api/agents/${id}/resume`, { method: "POST" });
    refresh();
  };

  const submitTask = async () => {
    if (!selectedAgent || !taskCommand.trim()) return;
    setSubmitting(true);
    try {
      await fetch(`${BASE}/api/agents/${selectedAgent.id}/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: taskCommand }),
      });
      setTaskCommand("");
      refreshAgentTasks(selectedAgent.id);
    } catch {}
    setSubmitting(false);
  };

  const parseNL = async () => {
    if (!nlInput.trim()) return;
    setParsing(true);
    try {
      const r = await fetch(`${BASE}/api/nl/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: nlInput }),
      });
      const data = await r.json();
      setNlResult(data);
    } catch {}
    setParsing(false);
  };

  const executeNL = async () => {
    if (!nlInput.trim()) return;
    setParsing(true);
    try {
      const r = await fetch(`${BASE}/api/nl/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: nlInput }),
      });
      const data = await r.json();
      setNlResult(data);
    } catch {}
    setParsing(false);
  };

  const timeAgo = (ts: number) => {
    if (!ts) return "";
    const diff = (Date.now() / 1000) - ts;
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-4 md:p-6 max-w-7xl mx-auto w-full">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Agent Pool</h1>
            <p className="text-xs text-zinc-500 font-mono mt-0.5">
              {stats ? `${stats.running} running — ${stats.total_agents} total — ${stats.completed_tasks} tasks` : "Loading..."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-white/[0.04] border border-white/[0.06] rounded-lg overflow-hidden">
              <input
                type="text"
                placeholder="Agent name"
                value={spawnName}
                onChange={(e) => setSpawnName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && spawnAgent()}
                className="bg-transparent text-xs font-mono text-zinc-300 px-3 py-2 w-36 outline-none placeholder:text-zinc-600"
              />
              <select
                value={spawnType}
                onChange={(e) => setSpawnType(e.target.value)}
                className="bg-transparent text-xs font-mono text-zinc-400 border-l border-white/[0.06] px-2 py-2 outline-none"
              >
                {AGENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value} className="bg-[#111113]">
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={spawnAgent}
              disabled={spawning || !spawnName.trim()}
              className="text-xs font-mono uppercase px-3 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors disabled:opacity-40"
            >
              {spawning ? "..." : "Spawn"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Agent Grid */}
          <div className="lg:col-span-1 space-y-3">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-xs font-mono text-zinc-500 uppercase tracking-wider">Agents</h2>
              <span className="text-[10px] font-mono text-zinc-600">{agents.length}</span>
            </div>
            {agents.length === 0 ? (
              <div className="text-center py-12 text-zinc-600 border border-dashed border-white/[0.06] rounded-xl">
                <p className="text-xs">No agents running</p>
                <p className="text-[10px] text-zinc-600 mt-1">Spawn one above</p>
              </div>
            ) : (
              <div className="space-y-2">
                {agents.map((agent) => (
                  <div
                    key={agent.id}
                    onClick={() => setSelectedAgent(agent)}
                    className={`bg-[#111113] border rounded-xl p-3 cursor-pointer transition-all duration-150 ${
                      selectedAgent?.id === agent.id
                        ? "border-violet-500/30 bg-violet-500/[0.04]"
                        : "border-white/[0.06] hover:border-white/[0.12]"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[agent.status] || "bg-zinc-600"}`} />
                        <span className="text-sm font-medium text-zinc-200 truncate">{agent.name}</span>
                      </div>
                      <span className="text-[10px] font-mono text-zinc-600 uppercase">{agent.type}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-zinc-500">{agent.task_count} tasks — {timeAgo(agent.created_at)}</span>
                      <div className="flex items-center gap-1">
                        {agent.status === "running" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); pauseAgent(agent.id); }}
                            className="text-[10px] font-mono text-amber-400/60 hover:text-amber-400 px-1"
                          >
                            pause
                          </button>
                        )}
                        {agent.status === "paused" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); resumeAgent(agent.id); }}
                            className="text-[10px] font-mono text-emerald-400/60 hover:text-emerald-400 px-1"
                          >
                            resume
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); killAgent(agent.id); }}
                          className="text-[10px] font-mono text-red-400/60 hover:text-red-400 px-1"
                        >
                          kill
                        </button>
                      </div>
                    </div>
                    {agent.tags && agent.tags.length > 0 && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {agent.tags.map((tag, i) => (
                          <span key={i} className="text-[9px] font-mono text-zinc-500 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Agent Detail + Tasks */}
          <div className="lg:col-span-2 space-y-4">
            {selectedAgent ? (
              <>
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <span className={`w-2.5 h-2.5 rounded-full ${STATUS_COLORS[selectedAgent.status] || "bg-zinc-600"}`} />
                      <h2 className="text-sm font-semibold text-zinc-200">{selectedAgent.name}</h2>
                      <span className="text-[10px] font-mono text-zinc-500 bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.06]">
                        {selectedAgent.type}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-zinc-600">{selectedAgent.id.slice(0, 8)}</span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500">
                    <span>Status: <span className="text-zinc-300">{selectedAgent.status}</span></span>
                    <span>Tasks: <span className="text-zinc-300">{selectedAgent.task_count}</span></span>
                    <span>Created: <span className="text-zinc-300">{timeAgo(selectedAgent.created_at)}</span></span>
                  </div>
                </div>

                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Submit Task</h3>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Enter command..."
                      value={taskCommand}
                      onChange={(e) => setTaskCommand(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && submitTask()}
                      className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs font-mono text-zinc-300 outline-none focus:border-violet-500/30 placeholder:text-zinc-600 transition-colors"
                    />
                    <button
                      onClick={submitTask}
                      disabled={submitting || !taskCommand.trim()}
                      className="text-xs font-mono uppercase px-4 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors disabled:opacity-40"
                    >
                      {submitting ? "..." : "Run"}
                    </button>
                  </div>
                </div>

                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">
                    Task History
                    <span className="text-zinc-600 ml-2">({agentTasks.length})</span>
                  </h3>
                  {agentTasks.length === 0 ? (
                    <p className="text-xs text-zinc-600 text-center py-8">No tasks yet</p>
                  ) : (
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {agentTasks.slice().reverse().map((task) => (
                        <div key={task.id} className="border-t border-white/[0.04] pt-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono text-zinc-300">{task.command}</span>
                            <div className="flex items-center gap-2">
                              {task.latency_ms && (
                                <span className="text-[10px] font-mono text-zinc-600">{task.latency_ms}ms</span>
                              )}
                              <span className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[task.status] || "bg-zinc-600"}`} />
                            </div>
                          </div>
                          {task.result && (
                            <pre className="text-[10px] font-mono text-zinc-500 mt-1 whitespace-pre-wrap max-h-20 overflow-y-auto">
                              {typeof task.result === "string" ? task.result : JSON.stringify(task.result, null, 2)}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-20 text-zinc-600 border border-dashed border-white/[0.06] rounded-xl">
                <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <p className="text-sm">Select an agent to view details</p>
              </div>
            )}
          </div>
        </div>

        {/* NL Command Section */}
        <div className="mt-6 bg-[#111113] border border-white/[0.06] rounded-xl p-4">
          <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Natural Language Command</h3>
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              placeholder='e.g. "turn on the living room lights" or "check the temperature"'
              value={nlInput}
              onChange={(e) => setNlInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && parseNL()}
              className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs font-mono text-zinc-300 outline-none focus:border-violet-500/30 placeholder:text-zinc-600 transition-colors"
            />
            <button
              onClick={parseNL}
              disabled={parsing || !nlInput.trim()}
              className="text-xs font-mono uppercase px-4 py-2 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors disabled:opacity-40"
            >
              {parsing ? "..." : "Parse"}
            </button>
            <button
              onClick={executeNL}
              disabled={parsing || !nlInput.trim()}
              className="text-xs font-mono uppercase px-4 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors disabled:opacity-40"
            >
              {parsing ? "..." : "Execute"}
            </button>
          </div>
          {nlResult && (
            <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
              {nlResult.parsed && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                  <div>
                    <span className="text-[10px] font-mono text-zinc-500 uppercase">Intent</span>
                    <p className="text-xs font-mono text-zinc-300 mt-0.5">{nlResult.parsed.intent}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-mono text-zinc-500 uppercase">Device</span>
                    <p className="text-xs font-mono text-zinc-300 mt-0.5">{nlResult.parsed.device_type || nlResult.parsed.device_name || "—"}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-mono text-zinc-500 uppercase">Action</span>
                    <p className="text-xs font-mono text-zinc-300 mt-0.5">{nlResult.parsed.action || "—"}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-mono text-zinc-500 uppercase">Confidence</span>
                    <p className="text-xs font-mono text-zinc-300 mt-0.5">{(nlResult.parsed.confidence * 100).toFixed(0)}%</p>
                  </div>
                </div>
              )}
              <pre className="text-[10px] font-mono text-zinc-500 whitespace-pre-wrap max-h-40 overflow-y-auto">
                {JSON.stringify(nlResult, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Events */}
        {events.length > 0 && (
          <div className="mt-6 bg-[#111113] border border-white/[0.06] rounded-xl p-4">
            <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">
              Recent Events
              <span className="text-zinc-600 ml-2">({events.length})</span>
            </h3>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {events.slice().reverse().map((ev, i) => (
                <div key={i} className="flex items-start gap-2 text-[10px] font-mono">
                  <span className="text-zinc-600 shrink-0">{timeAgo(ev.timestamp)}</span>
                  <span className={`shrink-0 px-1 rounded ${
                    ev.type === "spawned" ? "text-emerald-400/60 bg-emerald-400/5" :
                    ev.type === "killed" ? "text-red-400/60 bg-red-400/5" :
                    ev.type === "error" ? "text-red-400/60 bg-red-400/5" :
                    "text-zinc-500 bg-white/[0.04]"
                  }`}>
                    {ev.type}
                  </span>
                  <span className="text-zinc-500">{ev.agent_name}</span>
                  <span className="text-zinc-600 truncate">{ev.detail}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
