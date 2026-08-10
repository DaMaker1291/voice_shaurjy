"use client";

import React, { useState } from "react";

interface ProcedureStep {
  order: number;
  action: string;
  description: string;
  tool?: string;
}

interface Procedure {
  name: string;
  description?: string;
  application?: string;
  requirements?: string[];
  steps: ProcedureStep[];
  successfulExecutions: number;
  failedExecutions: number;
  lastUsed?: string;
  successRate: number;
  category: string;
}

interface ProcedureViewerProps {
  procedure: Procedure | null;
  onClose?: () => void;
  onRun?: (procedure: Procedure) => void;
  onForget?: (name: string) => void;
}

export default function ProcedureViewer({
  procedure,
  onClose,
  onRun,
  onForget,
}: ProcedureViewerProps) {
  const [activeTab, setActiveTab] = useState<"steps" | "stats">("steps");

  if (!procedure) return null;

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      zIndex: 10000,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "rgba(0,0,0,0.85)",
      backdropFilter: "blur(12px)",
      animation: "fade-in 0.2s ease",
    }}>
      <div style={{
        width: 500,
        maxHeight: "80vh",
        background: "linear-gradient(145deg, #0d0f12 0%, #111317 100%)",
        border: "1px solid rgba(255,255,255,0.04)",
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
        display: "flex",
        flexDirection: "column",
        animation: "scale-in 0.2s ease",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 18px",
          borderBottom: "1px solid rgba(255,255,255,0.03)",
        }}>
          <div>
            <div style={{
              fontSize: 13,
              color: "#e5e5e5",
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 600,
              marginBottom: 2,
            }}>
              {procedure.name}
            </div>
            {procedure.description && (
              <div style={{
                fontSize: 8,
                color: "#555",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {procedure.description}
              </div>
            )}
          </div>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: "none", border: "none",
                color: "#444", fontSize: 14,
                cursor: "pointer", padding: "4px 8px",
                borderRadius: 3,
              }}
            >
              ×
            </button>
          )}
        </div>

        <div style={{
          display: "flex", gap: 0,
          borderBottom: "1px solid rgba(255,255,255,0.03)",
        }}>
          {(["steps", "stats"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                flex: 1,
                padding: "8px 0",
                fontSize: 7,
                fontFamily: "'JetBrains Mono', monospace",
                background: "transparent",
                border: "none",
                borderBottom: activeTab === tab ? "1px solid #00FF66" : "1px solid transparent",
                color: activeTab === tab ? "#00FF66" : "#444",
                cursor: "pointer",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 18px",
        }}>
          {activeTab === "steps" && (
            <div>
              {procedure.requirements && procedure.requirements.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{
                    fontSize: 6,
                    color: "#444",
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    marginBottom: 6,
                  }}>
                    Requirements
                  </div>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {procedure.requirements.map((req, i) => (
                      <span key={i} style={{
                        padding: "2px 6px",
                        borderRadius: 2,
                        background: "rgba(0,180,216,0.06)",
                        border: "1px solid rgba(0,180,216,0.1)",
                        fontSize: 6,
                        color: "#00B4D8",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {req}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div style={{
                fontSize: 6,
                color: "#444",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}>
                Procedure ({procedure.steps.length} steps)
              </div>

              {procedure.steps.map((step) => (
                <div key={step.order} style={{
                  display: "flex",
                  gap: 8,
                  padding: "6px 0",
                  borderBottom: "1px solid rgba(255,255,255,0.02)",
                }}>
                  <div style={{
                    width: 16, height: 16,
                    borderRadius: "50%",
                    background: "rgba(0,255,102,0.06)",
                    border: "1px solid rgba(0,255,102,0.12)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    <span style={{
                      fontSize: 7,
                      color: "#00FF66",
                      fontFamily: "'JetBrains Mono', monospace",
                      fontWeight: 600,
                    }}>
                      {step.order}
                    </span>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: 8,
                      color: "#ccc",
                      fontFamily: "'JetBrains Mono', monospace",
                      fontWeight: 500,
                    }}>
                      {step.action}
                    </div>
                    <div style={{
                      fontSize: 7,
                      color: "#555",
                      fontFamily: "'JetBrains Mono', monospace",
                      marginTop: 2,
                      lineHeight: 1.3,
                    }}>
                      {step.description}
                    </div>
                    {step.tool && (
                      <span style={{
                        display: "inline-block",
                        marginTop: 3,
                        padding: "1px 5px",
                        borderRadius: 2,
                        background: "rgba(255,179,0,0.04)",
                        border: "1px solid rgba(255,179,0,0.08)",
                        fontSize: 5,
                        color: "#FFB300",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {step.tool}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "stats" && (
            <div>
              <div style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                gap: 8,
                marginBottom: 14,
              }}>
                {[
                  { label: "Executions", value: String(procedure.successfulExecutions + procedure.failedExecutions) },
                  { label: "Success Rate", value: `${procedure.successRate}%` },
                  { label: "Category", value: procedure.category },
                ].map(stat => (
                  <div key={stat.label} style={{
                    padding: "8px 10px",
                    borderRadius: 4,
                    background: "rgba(255,255,255,0.01)",
                    border: "1px solid rgba(255,255,255,0.03)",
                    textAlign: "center",
                  }}>
                    <div style={{
                      fontSize: 14,
                      color: "#e5e5e5",
                      fontFamily: "'JetBrains Mono', monospace",
                      fontWeight: 600,
                    }}>
                      {stat.value}
                    </div>
                    <div style={{
                      fontSize: 5,
                      color: "#444",
                      fontFamily: "'JetBrains Mono', monospace",
                      letterSpacing: "0.08em",
                      marginTop: 2,
                    }}>
                      {stat.label.toUpperCase()}
                    </div>
                  </div>
                ))}
              </div>

              {procedure.lastUsed && (
                <div style={{
                  fontSize: 7,
                  color: "#555",
                  fontFamily: "'JetBrains Mono', monospace",
                  marginBottom: 8,
                }}>
                  Last used: {procedure.lastUsed}
                </div>
              )}

              <div style={{
                fontSize: 6,
                color: "#444",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                marginBottom: 6,
              }}>
                Star Rating
              </div>
              <div style={{ display: "flex", gap: 2 }}>
                {[1, 2, 3, 4, 5].map(star => (
                  <span key={star} style={{
                    fontSize: 14,
                    color: star <= Math.round(procedure.successRate / 20) ? "#FFB300" : "#222",
                  }}>
                    ★
                  </span>
                ))}
                <span style={{
                  fontSize: 8,
                  color: "#555",
                  fontFamily: "'JetBrains Mono', monospace",
                  marginLeft: 6,
                }}>
                  {procedure.successRate >= 90 ? "Excellent" : procedure.successRate >= 70 ? "Good" : procedure.successRate >= 50 ? "Fair" : "Learning"}
                </span>
              </div>
            </div>
          )}
        </div>

        <div style={{
          display: "flex",
          gap: 6,
          padding: "10px 18px",
          borderTop: "1px solid rgba(255,255,255,0.03)",
        }}>
          {onRun && (
            <button
              onClick={() => onRun(procedure)}
              style={{
                flex: 1,
                padding: "7px 0",
                borderRadius: 4,
                fontSize: 7,
                fontFamily: "'JetBrains Mono', monospace",
                background: "rgba(0,255,102,0.08)",
                border: "1px solid rgba(0,255,102,0.15)",
                color: "#00FF66",
                cursor: "pointer",
                letterSpacing: "0.06em",
              }}
            >
              RUN PROCEDURE
            </button>
          )}
          {onForget && (
            <button
              onClick={() => onForget(procedure.name)}
              style={{
                padding: "7px 12px",
                borderRadius: 4,
                fontSize: 7,
                fontFamily: "'JetBrains Mono', monospace",
                background: "rgba(239,68,68,0.04)",
                border: "1px solid rgba(239,68,68,0.1)",
                color: "#EF4444",
                cursor: "pointer",
                letterSpacing: "0.06em",
              }}
            >
              FORGET
            </button>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes scale-in { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
      `}</style>
    </div>
  );
}

export type { Procedure, ProcedureStep };
