"use client";

import React from "react";

interface CompletionScreenProps {
  mission?: string;
  actions?: number;
  recoveries?: number;
  errors?: number;
  duration?: string;
  artifacts?: { name: string; type: string; size?: string }[];
  onOpenResult?: () => void;
  onViewWork?: () => void;
  onDismiss?: () => void;
}

export default function CompletionScreen({
  mission = "",
  actions = 0,
  recoveries = 0,
  errors = 0,
  duration = "",
  artifacts = [],
  onOpenResult,
  onViewWork,
  onDismiss,
}: CompletionScreenProps) {
  return (
    <div style={{
      position: "fixed",
      inset: 0,
      zIndex: 9999,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "rgba(0,0,0,0.9)",
      backdropFilter: "blur(16px)",
      animation: "fade-in 0.5s ease",
    }}>
      <div style={{
        width: 480,
        textAlign: "center",
        animation: "rise-in 0.6s ease",
      }}>
        <div style={{
          fontSize: 48,
          marginBottom: 16,
          animation: "checkmark-bounce 0.8s ease",
        }}>
          ✓
        </div>

        <div style={{
          fontSize: 10,
          color: "#00FF66",
          fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: "0.15em",
          marginBottom: 8,
        }}>
          ✓ COMPLETE
        </div>

        <div style={{
          fontSize: 18,
          color: "#e5e5e5",
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 600,
          marginBottom: 24,
          lineHeight: 1.3,
        }}>
          {mission || "Mission completed"}
        </div>

        <div style={{
          display: "flex",
          justifyContent: "center",
          gap: 24,
          marginBottom: 24,
          padding: "16px 0",
          borderTop: "1px solid rgba(255,255,255,0.06)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}>
          <div>
            <div style={{ fontSize: 20, color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
              {actions}
            </div>
            <div style={{ fontSize: 7, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>
              ACTIONS
            </div>
          </div>
          <div>
            <div style={{ fontSize: 20, color: recoveries > 0 ? "#FFB300" : "#00FF66", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
              {recoveries}
            </div>
            <div style={{ fontSize: 7, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>
              RECOVERIES
            </div>
          </div>
          <div>
            <div style={{ fontSize: 20, color: errors > 0 ? "#EF4444" : "#00FF66", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
              {errors}
            </div>
            <div style={{ fontSize: 7, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>
              ERRORS
            </div>
          </div>
          <div>
            <div style={{ fontSize: 20, color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
              {duration || "—"}
            </div>
            <div style={{ fontSize: 7, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>
              DURATION
            </div>
          </div>
        </div>

        {artifacts.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <div style={{
              fontSize: 8,
              color: "#444",
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: "0.1em",
              marginBottom: 8,
            }}>
              CREATED
            </div>
            <div style={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "center",
              gap: 6,
            }}>
              {artifacts.map((a, i) => (
                <div key={i} style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "4px 10px",
                  borderRadius: 4,
                  background: "rgba(0,255,102,0.04)",
                  border: "1px solid rgba(0,255,102,0.1)",
                  fontSize: 8,
                  color: "#00FF66",
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  <span>{a.type === "folder" ? "📁" : a.type === "image" ? "🎨" : a.type === "spreadsheet" ? "📊" : a.type === "presentation" ? "📑" : "📄"}</span>
                  {a.name}
                  {a.size && <span style={{ color: "#555", fontSize: 7 }}>{a.size}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
          {onOpenResult && (
            <button
              onClick={onOpenResult}
              style={{
                padding: "10px 24px",
                borderRadius: 6,
                fontSize: 9,
                fontFamily: "'JetBrains Mono', monospace",
                background: "linear-gradient(135deg, rgba(0,255,102,0.15), rgba(0,180,216,0.1))",
                border: "1px solid rgba(0,255,102,0.25)",
                color: "#00FF66",
                cursor: "pointer",
                letterSpacing: "0.05em",
              }}
            >
              OPEN RESULT
            </button>
          )}
          {onViewWork && (
            <button
              onClick={onViewWork}
              style={{
                padding: "10px 24px",
                borderRadius: 6,
                fontSize: 9,
                fontFamily: "'JetBrains Mono', monospace",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "#888",
                cursor: "pointer",
                letterSpacing: "0.05em",
              }}
            >
              VIEW WORK
            </button>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              style={{
                padding: "10px 16px",
                borderRadius: 6,
                fontSize: 9,
                fontFamily: "'JetBrains Mono', monospace",
                background: "none",
                border: "1px solid rgba(255,255,255,0.06)",
                color: "#555",
                cursor: "pointer",
                letterSpacing: "0.05em",
              }}
            >
              DISMISS
            </button>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes rise-in { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes checkmark-bounce {
          0% { transform: scale(0); opacity: 0; }
          50% { transform: scale(1.2); }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
