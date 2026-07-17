"use client";

import { useEffect, useState, useRef } from "react";

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

interface Agent {
  task_id: string;
  intent: string;
  status: "running" | "completed" | "failed" | "stopped";
  current_step: number;
  total_steps: number;
  steps: { action: string; description: string; status: string; result?: string }[];
  log: string[];
  screenshot?: string;
  started_at?: number;
  url?: string;
}

interface Props {
  agents: Agent[];
  activeAgent: string | null;
  onSelectAgent: (id: string) => void;
  onStopAgent: (id: string) => void;
}

export default function LiveAgentPanel({ agents, activeAgent, onSelectAgent, onStopAgent }: Props) {
  const [liveSteps, setLiveSteps] = useState<Record<string, { description: string; status: string }>>({});
  const [screenshots, setScreenshots] = useState<Record<string, string>>({});
  const [currentUrls, setCurrentUrls] = useState<Record<string, string>>({});
  const logRef = useRef<HTMLDivElement>(null);
  const active = agents.find(a => a.task_id === activeAgent);

  // Poll live data for active agents
  useEffect(() => {
    const running = agents.filter(a => a.status === "running");
    if (running.length === 0) return;

    const i = setInterval(async () => {
      for (const agent of running) {
        try {
          const res = await fetch(`/api/autonomous/tasks/${agent.task_id}`);
          const data = await safeJson(res);
          if (data.steps?.length > 0) {
            const currentStep = data.steps[data.current_step || 0];
            if (currentStep) {
              setLiveSteps(prev => ({
                ...prev,
                [agent.task_id]: { description: currentStep.description, status: currentStep.status }
              }));
            }
          }
          if (data.url) setCurrentUrls(prev => ({ ...prev, [agent.task_id]: data.url }));
          // Get latest screenshot
          if (data.screenshots?.length > 0) {
            setScreenshots(prev => ({ ...prev, [agent.task_id]: data.screenshots[data.screenshots.length - 1] }));
          }
        } catch {}
      }
    }, 1500);

    return () => clearInterval(i);
  }, [agents]);

  // Auto-scroll log
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [active?.log]);

  const running = agents.filter(a => a.status === "running");
  const completed = agents.filter(a => a.status === "completed");
  const failed = agents.filter(a => a.status === "failed");

  return (
    <div style={{ display: "flex", height: "100%", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx>{`
        @keyframes agent-pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
        @keyframes step-slide { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:translateX(0); } }
        @keyframes typing-dots { 0%,100% { opacity:0.3; } 50% { opacity:1; } }
        .ap { animation: agent-pulse 1.5s ease-in-out infinite; }
        .ss { animation: step-slide 0.3s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Sidebar: Agent List */}
      <div style={{
        width: 240, borderRight: "1px solid #1a1d23", display: "flex", flexDirection: "column",
        background: "#08090c", flexShrink: 0,
      }}>
        <div style={{
          padding: "10px 12px", borderBottom: "1px solid #1a1d23",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ fontSize: 9, color: "#667085", letterSpacing: "0.1em", fontWeight: 600 }}>
            AGENTS ({agents.length})
          </div>
          {running.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div className="ap" style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66" }} />
              <span style={{ fontSize: 8, color: "#00FF66" }}>{running.length} ACTIVE</span>
            </div>
          )}
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: 6 }}>
          {/* Running */}
          {running.map(agent => (
            <div
              key={agent.task_id}
              onClick={() => onSelectAgent(agent.task_id)}
              style={{
                padding: "8px 10px", borderRadius: 6, marginBottom: 4, cursor: "pointer",
                background: activeAgent === agent.task_id ? "rgba(0,255,102,0.1)" : "transparent",
                border: `1px solid ${activeAgent === agent.task_id ? "rgba(0,255,102,0.2)" : "transparent"}`,
                transition: "all 0.1s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <div className="ap" style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66" }} />
                <span style={{ fontSize: 10, color: "#e5e5e5", fontWeight: 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {agent.intent}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ flex: 1, height: 2, borderRadius: 1, background: "#1a1d23", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", background: "#00FF66", borderRadius: 1,
                    width: `${agent.total_steps ? ((agent.current_step + 1) / agent.total_steps * 100) : 0}%`,
                    transition: "width 0.3s",
                  }} />
                </div>
                <span style={{ fontSize: 7, color: "#667085" }}>{agent.current_step + 1}/{agent.total_steps || "?"}</span>
              </div>
              {liveSteps[agent.task_id] && (
                <div className="ss" style={{ fontSize: 8, color: "#FFB300", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  → {liveSteps[agent.task_id].description}
                </div>
              )}
              <button
                onClick={e => { e.stopPropagation(); onStopAgent(agent.task_id); }}
                style={{
                  marginTop: 4, padding: "2px 6px", borderRadius: 3, fontSize: 7,
                  fontFamily: "inherit", cursor: "pointer",
                  background: "rgba(255,51,51,0.1)", color: "#FF3333", border: "1px solid rgba(255,51,51,0.2)",
                }}
              >
                STOP
              </button>
            </div>
          ))}

          {/* Completed */}
          {completed.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 8, color: "#667085", letterSpacing: "0.08em", padding: "4px 6px", marginBottom: 4 }}>
                COMPLETED ({completed.length})
              </div>
              {completed.map(agent => (
                <div
                  key={agent.task_id}
                  onClick={() => onSelectAgent(agent.task_id)}
                  style={{
                    padding: "6px 10px", borderRadius: 4, marginBottom: 2, cursor: "pointer",
                    background: activeAgent === agent.task_id ? "rgba(0,255,102,0.08)" : "transparent",
                    opacity: 0.7,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 8, color: "#00FF66" }}>✓</span>
                    <span style={{ fontSize: 9, color: "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {agent.intent}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Failed */}
          {failed.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 8, color: "#667085", letterSpacing: "0.08em", padding: "4px 6px", marginBottom: 4 }}>
                FAILED ({failed.length})
              </div>
              {failed.map(agent => (
                <div
                  key={agent.task_id}
                  onClick={() => onSelectAgent(agent.task_id)}
                  style={{ padding: "6px 10px", borderRadius: 4, marginBottom: 2, cursor: "pointer", opacity: 0.5 }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 8, color: "#FF3333" }}>✗</span>
                    <span style={{ fontSize: 9, color: "#9ca3af" }}>{agent.intent}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main: Live View */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {active ? (
          <>
            {/* Agent Header */}
            <div style={{
              padding: "12px 16px", borderBottom: "1px solid #1a1d23",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className={active.status === "running" ? "ap" : ""} style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: active.status === "running" ? "#00FF66" : active.status === "completed" ? "#00FF66" : active.status === "failed" ? "#FF3333" : "#FFB300",
                  }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#e5e5e5" }}>{active.intent}</span>
                </div>
                <div style={{ fontSize: 9, color: "#667085", marginTop: 2 }}>
                  Step {active.current_step + 1} of {active.total_steps || "?"} · {active.task_id}
                </div>
              </div>
              {currentUrls[active.task_id] && (
                <div style={{
                  padding: "4px 8px", borderRadius: 4, fontSize: 9, fontFamily: "inherit",
                  background: "#0d0f12", border: "1px solid #1a1d23",
                  color: "#9ca3af", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  🔗 {currentUrls[active.task_id]}
                </div>
              )}
            </div>

            {/* Live Screen View */}
            <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
              {/* Screen Panel */}
              <div style={{ flex: 1, padding: 16, display: "flex", flexDirection: "column" }}>
                <div style={{
                  flex: 1, borderRadius: 8, overflow: "hidden",
                  border: "1px solid #1a1d23", background: "#08090c",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  position: "relative",
                }}>
                  {screenshots[active.task_id] ? (
                    <img
                      src={`data:image/png;base64,${screenshots[active.task_id]}`}
                      alt="Live screen"
                      style={{ width: "100%", height: "100%", objectFit: "contain" }}
                    />
                  ) : (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.2 }}>🖥️</div>
                      <div style={{ fontSize: 11, color: "#667085" }}>Live screen will appear here</div>
                      <div style={{ fontSize: 9, color: "#667085", marginTop: 4, opacity: 0.5 }}>
                        Agent captures screenshots during execution
                      </div>
                    </div>
                  )}

                  {/* Overlay: Current Action */}
                  {active.status === "running" && liveSteps[active.task_id] && (
                    <div style={{
                      position: "absolute", bottom: 12, left: 12, right: 12,
                      padding: "8px 12px", borderRadius: 6,
                      background: "rgba(0,0,0,0.85)", backdropFilter: "blur(8px)",
                      border: "1px solid rgba(255,179,0,0.2)",
                      display: "flex", alignItems: "center", gap: 8,
                    }}>
                      <div style={{ display: "flex", gap: 3 }}>
                        {[0, 0.2, 0.4].map((d, i) => (
                          <div key={i} style={{ width: 4, height: 4, borderRadius: "50%", background: "#FFB300", animation: `typing-dots 1.2s infinite ${d}s` }} />
                        ))}
                      </div>
                      <span style={{ fontSize: 10, color: "#FFB300" }}>
                        {liveSteps[active.task_id].description}
                      </span>
                    </div>
                  )}
                </div>

                {/* Steps Timeline */}
                <div style={{ marginTop: 12, display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {active.steps?.map((step, i) => (
                    <div key={i} style={{
                      padding: "3px 8px", borderRadius: 3, fontSize: 8,
                      background: step.status === "done" ? "rgba(0,255,102,0.1)" :
                                  step.status === "running" ? "rgba(255,179,0,0.1)" :
                                  step.status === "retrying" ? "rgba(255,179,0,0.15)" :
                                  step.status === "recovering" ? "rgba(0,180,216,0.1)" :
                                  step.status === "failed" ? "rgba(255,51,51,0.1)" : "#1a1d23",
                      color: step.status === "done" ? "#00FF66" :
                             step.status === "running" ? "#FFB300" :
                             step.status === "retrying" ? "#FFB300" :
                             step.status === "recovering" ? "#00B4D8" :
                             step.status === "failed" ? "#FF3333" : "#667085",
                      border: `1px solid ${step.status === "running" ? "rgba(255,179,0,0.2)" :
                                           step.status === "retrying" ? "rgba(255,179,0,0.3)" :
                                           step.status === "recovering" ? "rgba(0,180,216,0.3)" : "transparent"}`,
                    }}>
                      {step.status === "done" ? "✓" :
                       step.status === "running" ? "●" :
                       step.status === "retrying" ? "↻" :
                       step.status === "recovering" ? "⟳" :
                       step.status === "failed" ? "✗" : i + 1}
                    </div>
                  ))}
                </div>
              </div>

              {/* Log Panel */}
              <div style={{ width: 300, borderLeft: "1px solid #1a1d23", display: "flex", flexDirection: "column" }}>
                <div style={{ padding: "8px 12px", borderBottom: "1px solid #1a1d23", fontSize: 8, color: "#667085", letterSpacing: "0.08em" }}>
                  EXECUTION LOG
                </div>
                <div ref={logRef} style={{ flex: 1, overflow: "auto", padding: 10 }}>
                  {active.log?.map((line, i) => (
                    <div key={i} style={{
                      fontSize: 9, lineHeight: 1.5, marginBottom: 2, fontFamily: "var(--font-mono)",
                      color: line.includes("✓") ? "#00FF66" :
                             line.includes("✗") ? "#FF3333" :
                             line.includes("Step") ? "#FFB300" :
                             line.includes("Recovery") || line.includes("recovery") ? "#00B4D8" :
                             line.includes("Retrying") || line.includes("retrying") ? "#FFB300" :
                             line.includes("Skipping") ? "#A855F7" :
                             line.includes("error") || line.includes("Error") ? "#FF3333" :
                             line.includes("failed") ? "#FF3333" :
                             line.includes("recovered") || line.includes("Recovered") ? "#00FF66" :
                             "#9ca3af",
                    }}>
                      {line}
                    </div>
                  ))}
                  {active.status === "running" && (
                    <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>
                      <div style={{ display: "flex", gap: 2 }}>
                        {[0, 0.15, 0.3].map((d, i) => (
                          <div key={i} style={{ width: 3, height: 3, borderRadius: "50%", background: "#00FF66", animation: `typing-dots 1s infinite ${d}s` }} />
                        ))}
                      </div>
                      <span style={{ fontSize: 8, color: "#667085" }}>executing...</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          /* No agent selected */
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.2 }}>🤖</div>
              <div style={{ fontSize: 13, color: "#667085" }}>Select an agent to view live activity</div>
              <div style={{ fontSize: 9, color: "#667085", marginTop: 4, opacity: 0.5 }}>
                Agents show their screen and actions in real-time
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
