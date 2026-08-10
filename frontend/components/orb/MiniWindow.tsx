"use client";

import React from "react";
import JARVISOrb from "./JARVISOrb";

interface MiniWindowProps {
  mission?: string;
  progress?: number;
  state?: "idle" | "listening" | "planning" | "working" | "waiting" | "needs_approval" | "error" | "recovering" | "complete";
  currentAction?: string;
  steps?: { label: string; status: "done" | "active" | "pending" }[];
  onOpen?: () => void;
  onPause?: () => void;
  onClose?: () => void;
}

export default function MiniWindow({
  mission = "",
  progress = 0,
  state = "idle",
  currentAction = "",
  steps = [],
  onOpen,
  onPause,
  onClose,
}: MiniWindowProps) {
  return (
    <div
      style={{
        width: 320,
        background: "linear-gradient(145deg, #0d0f12 0%, #111317 100%)",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: "0 20px 60px rgba(0,0,0,0.6), 0 0 40px rgba(0,255,102,0.03)",
        fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          borderBottom: "1px solid rgba(255,255,255,0.04)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <JARVISOrb state={state} size={28} progress={progress} interactive={false} />
          <span style={{ fontSize: 10, color: "#e5e5e5", fontWeight: 600, letterSpacing: "0.05em" }}>
            JARVIS
          </span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: "none", border: "none", color: "#666", cursor: "pointer",
                fontSize: 14, padding: "2px 6px", borderRadius: 3,
              }}
            >
              ×
            </button>
          )}
        </div>
      </div>

      <div style={{ padding: "14px 16px" }}>
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: "#e5e5e5", fontWeight: 500, marginBottom: 6 }}>
            {mission || "No active mission"}
          </div>
          {state === "working" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ flex: 1, height: 3, background: "#1a1a1a", borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  width: `${Math.round(progress)}%`,
                  height: "100%",
                  background: "linear-gradient(90deg, #00FF66, #00B4D8)",
                  borderRadius: 2,
                  transition: "width 0.4s ease",
                }} />
              </div>
              <span style={{ fontSize: 9, color: "#888", minWidth: 28, textAlign: "right" }}>
                {Math.round(progress)}%
              </span>
            </div>
          )}
        </div>

        {currentAction && state === "working" && (
          <div style={{ fontSize: 9, color: "#00FF66", marginBottom: 8, opacity: 0.8 }}>
            ● {currentAction}
          </div>
        )}

        {steps.length > 0 && (
          <div style={{ marginTop: 4 }}>
            {steps.map((step, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0" }}>
                <span style={{
                  fontSize: 8,
                  width: 12, textAlign: "center",
                  color: step.status === "done" ? "#00FF66" : step.status === "active" ? "#FFB300" : "#333",
                }}>
                  {step.status === "done" ? "✓" : step.status === "active" ? "●" : "○"}
                </span>
                <span style={{
                  fontSize: 8,
                  color: step.status === "done" ? "#555" : step.status === "active" ? "#e5e5e5" : "#444",
                }}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 4, padding: "8px 12px", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
        {onPause && (
          <button
            onClick={onPause}
            style={{
              flex: 1, padding: "6px 0", borderRadius: 4, fontSize: 8,
              background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)",
              color: "#888", cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.05em",
            }}
          >
            PAUSE
          </button>
        )}
        {onOpen && (
          <button
            onClick={onOpen}
            style={{
              flex: 1, padding: "6px 0", borderRadius: 4, fontSize: 8,
              background: "rgba(0,255,102,0.08)", border: "1px solid rgba(0,255,102,0.2)",
              color: "#00FF66", cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.05em",
            }}
          >
            OPEN
          </button>
        )}
      </div>
    </div>
  );
}
