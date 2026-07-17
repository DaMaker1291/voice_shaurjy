"use client";

import { useEffect, useState } from "react";

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

interface Task {
  task_id: string;
  intent: string;
  status: string;
  current_step: number;
  total_steps: number;
  log: string[];
  steps: { action: string; description: string; status: string; result?: string }[];
  started_at?: number;
}

export default function AgentWorksheet({ task, onClose }: { task: Task; onClose: () => void }) {
  const [liveLog, setLiveLog] = useState<string[]>(task.log || []);
  const [activeStep, setActiveStep] = useState(task.current_step);

  // Poll for updates
  useEffect(() => {
    if (task.status !== "running") return;
    const i = setInterval(async () => {
      try {
        const res = await fetch(`/api/autonomous/tasks/${task.task_id}`);
        const data = await safeJson(res);
        setLiveLog(data.log || []);
        setActiveStep(data.current_step || 0);
      } catch {}
    }, 2000);
    return () => clearInterval(i);
  }, [task.task_id, task.status]);

  const progress = task.total_steps ? ((activeStep + 1) / task.total_steps * 100) : 0;
  const elapsed = task.started_at ? Math.floor((Date.now() / 1000) - task.started_at) : 0;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999,
      background: "rgba(3,3,3,0.88)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <style jsx>{`
        @keyframes ws-in { from { opacity:0; transform:translateY(12px) scale(0.97); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes step-pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
        .ws { animation: ws-in 0.3s cubic-bezier(0.16,1,0.3,1) both; }
        .sp { animation: step-pulse 1.5s ease-in-out infinite; }
      `}</style>

      <div className="ws" onClick={e => e.stopPropagation()} style={{
        width: 640, maxHeight: "85vh", overflow: "hidden",
        background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 12,
        display: "flex", flexDirection: "column",
        boxShadow: "0 0 60px rgba(0,255,102,0.05), 0 20px 60px rgba(0,0,0,0.5)",
      }}>
        {/* Header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <div className={task.status === "running" ? "sp" : ""} style={{
                width: 8, height: 8, borderRadius: "50%",
                background: task.status === "running" ? "#00FF66" : task.status === "completed" ? "#00FF66" : task.status === "failed" ? "#FF3333" : "#FFB300",
                boxShadow: task.status === "running" ? "0 0 8px rgba(0,255,102,0.4)" : "none",
              }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: "#e5e5e5" }}>{task.intent}</span>
            </div>
            <div style={{ fontSize: 9, color: "#667085" }}>
              Task {task.task_id} · {task.status.toUpperCase()}
            </div>
          </div>
          <button onClick={onClose} style={{
            padding: "4px 10px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
            background: "#1a1d23", color: "#667085", border: "1px solid #252830", cursor: "pointer",
          }}>
            ESC
          </button>
        </div>

        {/* Progress */}
        <div style={{ padding: "12px 20px", borderBottom: "1px solid #1a1d23" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 9, color: "#667085" }}>STEP {activeStep + 1} / {task.total_steps || "?"}</span>
            <span style={{ fontSize: 9, color: "#667085" }}>{Math.round(progress)}%</span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: "#1a1d23", overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: 2, transition: "width 0.3s",
              background: task.status === "failed" ? "#FF3333" : "linear-gradient(90deg, #00FF66, #FFB300)",
              width: `${progress}%`,
            }} />
          </div>
        </div>

        {/* Steps */}
        <div style={{ flex: 1, overflow: "auto", padding: "12px 20px" }}>
          <div style={{ fontSize: 9, color: "#667085", letterSpacing: "0.1em", marginBottom: 8 }}>EXECUTION STEPS</div>
          {task.steps?.map((step, i) => (
            <div key={i} style={{
              display: "flex", gap: 10, padding: "8px 0",
              borderBottom: i < (task.steps?.length || 0) - 1 ? "1px solid #1a1d23" : "none",
              opacity: i <= activeStep ? 1 : 0.4,
            }}>
              <div style={{ width: 20, height: 20, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9,
                background: step.status === "done" ? "rgba(0,255,102,0.15)" : step.status === "running" ? "rgba(255,179,0,0.15)" : step.status === "failed" ? "rgba(255,51,51,0.15)" : "#1a1d23",
                color: step.status === "done" ? "#00FF66" : step.status === "running" ? "#FFB300" : step.status === "failed" ? "#FF3333" : "#667085",
                border: `1px solid ${step.status === "done" ? "rgba(0,255,102,0.3)" : step.status === "running" ? "rgba(255,179,0,0.3)" : "transparent"}`,
              }}>
                {step.status === "done" ? "✓" : step.status === "running" ? "●" : step.status === "failed" ? "✗" : i + 1}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: step.status === "running" ? "#FFB300" : "#e5e5e5", fontWeight: step.status === "running" ? 500 : 400 }}>
                  {step.description}
                </div>
                <div style={{ fontSize: 8, color: "#667085", marginTop: 2 }}>{step.action}</div>
                {step.result && (
                  <div style={{ fontSize: 9, color: "#9ca3af", marginTop: 4, padding: "6px 8px", background: "#030303", borderRadius: 4, border: "1px solid #1a1d23" }}>
                    {typeof step.result === "string" ? step.result.slice(0, 200) : JSON.stringify(step.result).slice(0, 200)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Live Log */}
        <div style={{ borderTop: "1px solid #1a1d23", maxHeight: 160, overflow: "auto", padding: "10px 20px", background: "#08090c" }}>
          <div style={{ fontSize: 9, color: "#667085", letterSpacing: "0.1em", marginBottom: 6 }}>LIVE LOG</div>
          {liveLog.slice(-20).map((line, i) => (
            <div key={i} style={{
              fontSize: 10, lineHeight: 1.5, fontFamily: "var(--font-mono)",
              color: line.includes("✓") ? "#00FF66" : line.includes("✗") ? "#FF3333" : line.includes("Step") ? "#FFB300" : "#9ca3af",
            }}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
