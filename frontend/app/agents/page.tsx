"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";

const API = "";

interface Task {
  task_id: string;
  intent: string;
  status: string;
  current_step: number;
  total_steps: number;
  steps: any[];
  log: string[];
}

export default function AgentsPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [intent, setIntent] = useState("");
  const [starting, setStarting] = useState(false);
  const [headlessRunning, setHeadlessRunning] = useState(false);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/autonomous/tasks`);
      const data = await res.json();
      setTasks(data.tasks || []);
    } catch {}
    try {
      const res = await fetch(`${API}/api/headless/status`);
      const data = await res.json();
      setHeadlessRunning(data.running);
    } catch {}
  }, []);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);
  useEffect(() => {
    const i = setInterval(fetchTasks, 2000);
    return () => clearInterval(i);
  }, [fetchTasks]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [tasks]);

  const handleStart = async () => {
    if (!intent.trim()) return;
    setStarting(true);
    try {
      const res = await fetch(`${API}/api/autonomous/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent: intent.trim(), user_id: "local" }),
      });
      const data = await res.json();
      setSelectedTask(data.task_id);
      setIntent("");
    } catch {}
    setStarting(false);
  };

  const handleStop = async (taskId: string) => {
    await fetch(`${API}/api/autonomous/tasks/stop/${taskId}`, { method: "POST" });
  };

  const activeTasks = tasks.filter(t => t.status === "running");
  const completedTasks = tasks.filter(t => t.status !== "running");

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--void)", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        @keyframes pulse-glow { 0%,100% { box-shadow: 0 0 4px rgba(0,255,102,0.2); } 50% { box-shadow: 0 0 12px rgba(0,255,102,0.4); } }
        .animate-fade { animation: fade-in 0.25s cubic-bezier(0.16,1,0.3,1) both; }
        .pulse-active { animation: pulse-glow 2s ease-in-out infinite; }
      `}</style>

      {/* Header */}
      <header style={{ height: 32, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/" style={{ fontSize: 10, color: "var(--text-muted)", textDecoration: "none" }}>← BACK</Link>
          <div style={{ width: 1, height: 14, background: "var(--border)" }} />
          <span style={{ fontSize: 10, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600 }}>AUTONOMOUS AGENTS</span>
          <span style={{ fontSize: 9, color: activeTasks.length > 0 ? "var(--neon-green)" : "var(--text-muted)" }}>
            {activeTasks.length} active
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 9, color: headlessRunning ? "var(--neon-green)" : "var(--text-muted)" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: headlessRunning ? "var(--neon-green)" : "var(--crimson)" }} />
            HEADLESS {headlessRunning ? "ONLINE" : "OFFLINE"}
          </div>
        </div>
      </header>

      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>

          {/* Task Input */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: 16, marginBottom: 16 }}>
            <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>NEW AUTONOMOUS TASK</div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 8 }}>
              Describe what you want done. The agent will plan steps and execute them automatically until complete.
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={intent}
                onChange={e => setIntent(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleStart()}
                placeholder="e.g. Check my email for flights and check me in..."
                style={{ flex: 1, padding: "8px 12px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-raised)", color: "var(--text-primary)", fontSize: 11, outline: "none", fontFamily: "var(--font-mono)" }}
              />
              <button
                onClick={handleStart}
                disabled={starting || !intent.trim()}
                style={{ padding: "8px 18px", borderRadius: 4, fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--neon-green)", color: "#000", border: "none", opacity: starting || !intent.trim() ? 0.4 : 1, letterSpacing: "0.05em" }}
              >
                {starting ? "SPAWNING..." : "SPAWN AGENT"}
              </button>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              {[
                "Check email for flights",
                "Check in for my flight",
                "Do I have passport photos?",
                "Go to Gmail",
                "Open YouTube",
                "Research flight deals",
              ].map(suggestion => (
                <button
                  key={suggestion}
                  onClick={() => setIntent(suggestion)}
                  style={{ padding: "3px 8px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--surface-raised)", color: "var(--text-muted)", border: "1px solid var(--border)" }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>

          {/* Active Tasks */}
          {activeTasks.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>ACTIVE TASKS</div>
              {activeTasks.map(task => (
                <div
                  key={task.task_id}
                  className="animate-fade pulse-active"
                  onClick={() => setSelectedTask(selectedTask === task.task_id ? null : task.task_id)}
                  style={{ background: "var(--surface)", border: "1px solid rgba(0,255,102,0.2)", borderRadius: 6, padding: 12, marginBottom: 8, cursor: "pointer" }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-primary)" }}>{task.intent}</div>
                      <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
                        Step {task.current_step + 1}/{task.total_steps || "?"} • Task ID: {task.task_id}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 60, height: 4, borderRadius: 2, background: "var(--surface-raised)", overflow: "hidden" }}>
                        <div style={{ height: "100%", background: "var(--neon-green)", borderRadius: 2, width: `${task.total_steps ? ((task.current_step + 1) / task.total_steps * 100) : 0}%`, transition: "width 0.3s" }} />
                      </div>
                      <button
                        onClick={e => { e.stopPropagation(); handleStop(task.task_id); }}
                        style={{ padding: "3px 8px", borderRadius: 3, fontSize: 9, cursor: "pointer", background: "var(--crimson-dim)", color: "var(--crimson)", border: "1px solid rgba(255,51,51,0.2)", fontFamily: "var(--font-mono)" }}
                      >
                        STOP
                      </button>
                    </div>
                  </div>

                  {/* Live Log */}
                  {selectedTask === task.task_id && (
                    <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.08em" }}>EXECUTION LOG</div>
                      <div style={{ maxHeight: 200, overflow: "auto", background: "var(--void)", borderRadius: 4, padding: 8, fontSize: 9, color: "var(--text-secondary)" }}>
                        {(task.log || []).map((line: string, i: number) => (
                          <div key={i} style={{ marginBottom: 2, opacity: line.includes("→") ? 1 : 0.7 }}>{line}</div>
                        ))}
                        <div ref={logEndRef} />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Completed Tasks */}
          {completedTasks.length > 0 && (
            <div>
              <div style={{ fontSize: 9, color: "var(--steel)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 8 }}>COMPLETED</div>
              {completedTasks.map(task => (
                <div
                  key={task.task_id}
                  className="animate-fade"
                  onClick={() => setSelectedTask(selectedTask === task.task_id ? null : task.task_id)}
                  style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: 12, marginBottom: 6, cursor: "pointer", opacity: 0.7 }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{task.intent}</div>
                      <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
                        {task.status === "completed" ? "✓ Complete" : task.status === "stopped" ? "■ Stopped" : "✗ Failed"} • {task.total_steps} steps
                      </div>
                    </div>
                  </div>
                  {selectedTask === task.task_id && task.log && (
                    <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
                      <div style={{ maxHeight: 200, overflow: "auto", background: "var(--void)", borderRadius: 4, padding: 8, fontSize: 9, color: "var(--text-secondary)" }}>
                        {task.log.map((line: string, i: number) => (
                          <div key={i} style={{ marginBottom: 2 }}>{line}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {tasks.length === 0 && (
            <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--text-muted)", fontSize: 11 }}>
              <div style={{ fontSize: 24, marginBottom: 12 }}>🤖</div>
              <div>No autonomous tasks running.</div>
              <div style={{ fontSize: 9, marginTop: 6, opacity: 0.5 }}>Describe a task above and the agent will plan and execute it automatically.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
