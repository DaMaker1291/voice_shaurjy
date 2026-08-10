"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";

const AgentWorksheet = dynamic(() => import("@/components/AgentWorksheet"), { ssr: false });

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

const API = "";

interface Task {
  task_id: string;
  intent: string;
  status: string;
  current_step: number;
  total_steps: number;
  steps: any[];
  log: string[];
  started_at?: number;
}

interface Device {
  ip: string;
  name: string;
  type: string;
  protocol: string;
  mac?: string;
  is_online?: boolean;
}

export default function AgentsPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [intent, setIntent] = useState("");
  const [starting, setStarting] = useState(false);
  const [headlessRunning, setHeadlessRunning] = useState(false);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [worksheetTask, setWorksheetTask] = useState<Task | null>(null);
  const [activeTab, setActiveTab] = useState<"tasks" | "devices" | "logs">("tasks");
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [tRes, dRes, hRes] = await Promise.all([
        fetch(`${API}/api/autonomous/tasks`),
        fetch(`${API}/api/relay/devices?user_id=local`),
        fetch(`${API}/api/headless/status`),
      ]);
      const tData = await safeJson(tRes);
      const dData = await safeJson(dRes);
      const hData = await safeJson(hRes);
      setTasks(tData.tasks || []);
      setDevices(dData.devices || []);
      setHeadlessRunning(hData.running);
    } catch {}
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    const i = setInterval(fetchAll, 2000);
    return () => clearInterval(i);
  }, [fetchAll]);
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [tasks]);

  const handleStart = async () => {
    if (!intent.trim()) return;
    setStarting(true);
    try {
      // Check if multi-line (parallel)
      const lines = intent.split("\n").map(l => l.trim()).filter(l => l.length > 0);
      if (lines.length > 1) {
        // Parallel execution
        const res = await fetch(`${API}/api/autonomous/start_parallel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ intents: lines, user_id: "local" }),
        });
        const data = await safeJson(res);
        if (data.tasks?.length > 0) setSelectedTask(data.tasks[0].task_id);
      } else {
        // Single execution
        const res = await fetch(`${API}/api/autonomous/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ intent: intent.trim(), user_id: "local" }),
        });
        const data = await safeJson(res);
        setSelectedTask(data.task_id);
      }
      setIntent("");
    } catch {}
    setStarting(false);
  };

  const handleParallel = async (intents: string[]) => {
    setStarting(true);
    try {
      const res = await fetch(`${API}/api/autonomous/start_parallel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intents, user_id: "local" }),
      });
      const data = await safeJson(res);
      if (data.tasks?.length > 0) setSelectedTask(data.tasks[0].task_id);
    } catch {}
    setStarting(false);
  };

  const handleStop = async (taskId: string) => {
    await fetch(`${API}/api/autonomous/tasks/stop/${taskId}`, { method: "POST" });
  };

  const handleDeviceControl = async (ip: string, action: string) => {
    try {
      await fetch(`${API}/api/real/tapo/turn_${action}?ip=${ip}`, { method: "POST" });
      fetchAll();
    } catch {}
  };

  const activeTasks = tasks.filter(t => t.status === "running");
  const completedTasks = tasks.filter(t => t.status !== "running");

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        @keyframes pulse-glow { 0%,100% { box-shadow: 0 0 4px rgba(0,255,102,0.15); } 50% { box-shadow: 0 0 16px rgba(0,255,102,0.3); } }
        .af { animation: fade-in 0.25s cubic-bezier(0.16,1,0.3,1) both; }
        .pg { animation: pulse-glow 2s ease-in-out infinite; }
      `}</style>

      {/* Header */}
      <header style={{ height: 40, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
          <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
          <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>AGENT COMMAND CENTER</span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 9, color: headlessRunning ? "#00FF66" : "#667085" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: headlessRunning ? "#00FF66" : "#FF3333" }} />
            HEADLESS
          </div>
          <div style={{ fontSize: 9, color: "#667085" }}>{activeTasks.length} active</div>
        </div>
      </header>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #1a1d23", background: "#0d0f12" }}>
        {(["tasks", "devices", "logs"] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 16px", fontSize: 10, fontFamily: "inherit", cursor: "pointer",
              background: "none", border: "none", borderBottom: activeTab === tab ? "2px solid #00FF66" : "2px solid transparent",
              color: activeTab === tab ? "#00FF66" : "#667085", letterSpacing: "0.08em", fontWeight: 600,
            }}
          >
            {tab === "tasks" ? "AUTONOMOUS TASKS" : tab === "devices" ? "DEVICES" : "EXECUTION LOG"}
            {tab === "tasks" && activeTasks.length > 0 && (
              <span style={{ marginLeft: 6, padding: "1px 5px", borderRadius: 8, background: "rgba(0,255,102,0.15)", fontSize: 9 }}>
                {activeTasks.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {activeTab === "tasks" && (
          <div style={{ maxWidth: 900, margin: "0 auto" }}>
            {/* Task Input */}
            <div style={{ background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div style={{ fontSize: 9, color: "#00FF66", letterSpacing: "0.1em", fontWeight: 600 }}>NEW AUTONOMOUS TASK</div>
                <div style={{ fontSize: 8, color: "#667085" }}>Multi-line = parallel execution</div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <textarea
                  value={intent}
                  onChange={e => setIntent(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleStart(); } }}
                  placeholder={"Describe what you want done...\n\nOne task per line for parallel execution:\nCheck email for flights\nScan network devices\nAlexa say hello"}
                  rows={3}
                  style={{
                    flex: 1, padding: "10px 14px", borderRadius: 6, border: "1px solid #1a1d23",
                    background: "#030303", color: "#e5e5e5", fontSize: 12, outline: "none",
                    fontFamily: "inherit", resize: "none", lineHeight: 1.5,
                  }}
                />
                <button
                  onClick={handleStart}
                  disabled={starting || !intent.trim()}
                  style={{
                    padding: "10px 20px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                    fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
                    border: "none", opacity: starting || !intent.trim() ? 0.4 : 1,
                    letterSpacing: "0.05em",
                  }}
                >
                  {starting ? "SPAWNING..." : "SPAWN"}
                </button>
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                {["Check email for flights", "Check in for my flight", "Find passport photos", "Go to Gmail", "Scan all devices", "Alexa say hello"].map(s => (
                  <button key={s} onClick={() => setIntent(s)} style={{
                    padding: "4px 10px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                    cursor: "pointer", background: "#1a1d23", color: "#667085", border: "1px solid #252830",
                  }}>
                    {s}
                  </button>
                ))}
                <button onClick={() => handleParallel(["Check email for flights", "Scan all network devices", "Check system health"])} style={{
                  padding: "4px 10px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                  cursor: "pointer", background: "rgba(0,255,102,0.1)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)",
                  fontWeight: 600,
                }}>
                  ⚡ Run All (3 parallel)
                </button>
              </div>
            </div>

            {/* Active Tasks */}
            {activeTasks.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 9, color: "#00FF66", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>RUNNING</div>
                {activeTasks.map(task => (
                  <div
                    key={task.task_id}
                    className="af pg"
                    onClick={() => { setWorksheetTask(task); setSelectedTask(task.task_id); }}
                    style={{
                      background: "#0d0f12", border: "1px solid rgba(0,255,102,0.15)",
                      borderRadius: 8, padding: 14, marginBottom: 8, cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{task.intent}</div>
                        <div style={{ fontSize: 10, color: "#667085" }}>
                          Step {task.current_step + 1}/{task.total_steps || "?"} • {task.task_id}
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <div style={{ width: 80, height: 4, borderRadius: 2, background: "#1a1d23", overflow: "hidden" }}>
                          <div style={{
                            height: "100%", background: "linear-gradient(90deg, #00FF66, #FFB300)", borderRadius: 2,
                            width: `${task.total_steps ? ((task.current_step + 1) / task.total_steps * 100) : 0}%`,
                            transition: "width 0.3s",
                          }} />
                        </div>
                        <button
                          onClick={e => { e.stopPropagation(); handleStop(task.task_id); }}
                          style={{
                            padding: "4px 10px", borderRadius: 4, fontSize: 9, cursor: "pointer",
                            background: "rgba(255,51,51,0.1)", color: "#FF3333", border: "1px solid rgba(255,51,51,0.2)",
                            fontFamily: "inherit",
                          }}
                        >
                          STOP
                        </button>
                      </div>
                    </div>

                    {selectedTask === task.task_id && task.log && (
                      <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #1a1d23" }}>
                        <div style={{ fontSize: 9, color: "#667085", letterSpacing: "0.08em", marginBottom: 6 }}>LIVE LOG</div>
                        <div style={{
                          maxHeight: 200, overflow: "auto", background: "#030303", borderRadius: 6,
                          padding: 10, fontSize: 10, color: "#9ca3af",
                        }}>
                          {task.log.map((line: string, i: number) => (
                            <div key={i} style={{ marginBottom: 2, color: line.includes("✓") ? "#00FF66" : line.includes("✗") ? "#FF3333" : "#9ca3af" }}>
                              {line}
                            </div>
                          ))}
                          <div ref={logEndRef} />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Completed */}
            {completedTasks.length > 0 && (
              <div>
                <div style={{ fontSize: 9, color: "#667085", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>COMPLETED</div>
                {completedTasks.map(task => (
                  <div
                    key={task.task_id}
                    className="af"
                    onClick={() => setSelectedTask(selectedTask === task.task_id ? null : task.task_id)}
                    style={{
                      background: "#0d0f12", border: "1px solid #1a1d23",
                      borderRadius: 8, padding: 12, marginBottom: 6, cursor: "pointer", opacity: 0.7,
                    }}
                  >
                    <div style={{ fontSize: 12, color: "#9ca3af" }}>{task.intent}</div>
                    <div style={{ fontSize: 10, color: "#667085", marginTop: 2 }}>
                      {task.status === "completed" ? "✓ Complete" : task.status === "stopped" ? "■ Stopped" : "✗ Failed"} • {task.total_steps} steps
                    </div>
                  </div>
                ))}
              </div>
            )}

            {tasks.length === 0 && (
              <div style={{ textAlign: "center", padding: "80px 20px" }}>
                <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>🤖</div>
                <div style={{ fontSize: 12, color: "#667085" }}>No tasks running. Type a command above to spawn an agent.</div>
              </div>
            )}
          </div>
        )}

        {activeTab === "devices" && (
          <div style={{ maxWidth: 900, margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 9, color: "#00FF66", letterSpacing: "0.1em", fontWeight: 600 }}>
                DISCOVERED DEVICES ({devices.length})
              </div>
              <button
                onClick={() => fetch(`${API}/api/relay/action`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }) }).then(fetchAll)}
                style={{
                  padding: "6px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                  cursor: "pointer", background: "#1a1d23", color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)",
                }}
              >
                SCAN NETWORK
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 8 }}>
              {devices.map((d, i) => (
                <div
                  key={i}
                  className="af"
                  style={{
                    background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
                    padding: 14, transition: "all 0.15s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#00FF66" }} />
                    <span style={{ fontSize: 12, fontWeight: 500 }}>{d.name}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "#667085", marginBottom: 2 }}>{d.ip}</div>
                  <div style={{ fontSize: 9, color: "#667085", marginBottom: 8 }}>{d.type} • {d.protocol}</div>
                  {d.type === "TAPO_PLUG" && (
                    <div style={{ display: "flex", gap: 4 }}>
                      <button onClick={() => handleDeviceControl(d.ip, "on")} style={{ flex: 1, padding: "4px 0", borderRadius: 3, fontSize: 9, fontFamily: "inherit", cursor: "pointer", background: "rgba(0,255,102,0.1)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)" }}>ON</button>
                      <button onClick={() => handleDeviceControl(d.ip, "off")} style={{ flex: 1, padding: "4px 0", borderRadius: 3, fontSize: 9, fontFamily: "inherit", cursor: "pointer", background: "rgba(255,51,51,0.1)", color: "#FF3333", border: "1px solid rgba(255,51,51,0.2)" }}>OFF</button>
                    </div>
                  )}
                </div>
              ))}
              {devices.length === 0 && (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: "60px 0", color: "#667085", fontSize: 12 }}>
                  Click "Scan Network" to discover devices
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "logs" && (
          <div style={{ maxWidth: 900, margin: "0 auto" }}>
            <div style={{ fontSize: 9, color: "#00FF66", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>GLOBAL EXECUTION LOG</div>
            <div style={{
              background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
              padding: 16, fontFamily: "monospace", fontSize: 11, color: "#9ca3af",
              maxHeight: "calc(100vh - 200px)", overflow: "auto",
            }}>
              {tasks.flatMap(t => (t.log || []).map(l => ({ task: t.intent, line: l }))).map((entry, i) => (
                <div key={i} style={{ marginBottom: 2 }}>
                  <span style={{ color: "#667085" }}>[{entry.task}]</span> {entry.line}
                </div>
              ))}
              {tasks.length === 0 && (
                <div style={{ color: "#667085" }}>No logs yet. Start a task to see execution output.</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Agent Worksheet Modal */}
      {worksheetTask && (
        <AgentWorksheet task={worksheetTask} onClose={() => { setWorksheetTask(null); setSelectedTask(null); }} />
      )}
    </div>
  );
}
