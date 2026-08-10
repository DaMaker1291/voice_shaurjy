"use client";

import React from "react";

interface ExecutionPanelProps {
  currentAction?: string;
  reason?: string;
  application?: string;
  tool?: string;
  recentActivity?: { time: string; label: string; status: "done" | "active" | "error" }[];
  artifacts?: { name: string; type: string; size?: string }[];
}

export default function ExecutionPanel({
  currentAction = "",
  reason = "",
  application = "",
  tool = "",
  recentActivity = [],
  artifacts = [],
}: ExecutionPanelProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "done": return "#00FF66";
      case "active": return "#FFB300";
      case "error": return "#EF4444";
      default: return "#444";
    }
  };

  return (
    <div style={{
      width: 260,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      position: "relative",
    }}>
      <div style={{
        padding: "10px 12px",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
      }}>
        <div style={{
          fontSize: 6, color: "#444", letterSpacing: "0.12em",
          marginBottom: 5, textTransform: "uppercase",
        }}>
          Current Action
        </div>
        {currentAction && (
          <div style={{
            fontSize: 10, color: "#00FF66", fontWeight: 500,
            display: "flex", alignItems: "center", gap: 5, marginBottom: 6,
          }}>
            <span style={{
              width: 4, height: 4, borderRadius: "50%", background: "#00FF66",
              flexShrink: 0, display: "inline-block",
              animation: "pulse-dot 1.5s ease-in-out infinite",
            }} />
            {currentAction}
          </div>
        )}
        {reason && (
          <div style={{ marginBottom: 6 }}>
            <div style={{
              fontSize: 6, color: "#333", letterSpacing: "0.1em",
              marginBottom: 2, textTransform: "uppercase",
            }}>
              Why
            </div>
            <div style={{ fontSize: 7, color: "#666", lineHeight: 1.3 }}>{reason}</div>
          </div>
        )}
        {(application || tool) && (
          <div style={{ display: "flex", gap: 4 }}>
            {application && (
              <div style={{
                padding: "2px 6px", borderRadius: 2,
                background: "rgba(0,180,216,0.06)",
                border: "1px solid rgba(0,180,216,0.1)",
                fontSize: 6, color: "#00B4D8", letterSpacing: "0.04em",
              }}>
                {application}
              </div>
            )}
            {tool && (
              <div style={{
                padding: "2px 6px", borderRadius: 2,
                background: "rgba(255,179,0,0.04)",
                border: "1px solid rgba(255,179,0,0.08)",
                fontSize: 6, color: "#FFB300", letterSpacing: "0.04em",
              }}>
                {tool}
              </div>
            )}
          </div>
        )}
      </div>

      {recentActivity.length > 0 && (
        <div style={{ flex: 1, overflowY: "auto" }}>
          <div style={{
            fontSize: 6, color: "#333", letterSpacing: "0.1em",
            padding: "6px 12px 3px", textTransform: "uppercase",
          }}>
            Recent
          </div>
          <div style={{ padding: "0 8px 6px" }}>
            {recentActivity.map((item, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 5, padding: "2px 4px",
              }}>
                <span style={{ fontSize: 6, color: "#333", minWidth: 24, flexShrink: 0 }}>{item.time}</span>
                <span style={{
                  fontSize: 7, width: 8, textAlign: "center",
                  color: getStatusColor(item.status),
                }}>
                  {item.status === "done" ? "✓" : item.status === "active" ? "●" : "!"}
                </span>
                <span style={{
                  fontSize: 7,
                  color: item.status === "active" ? "#ccc" : item.status === "error" ? "#EF4444" : "#444",
                }}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {artifacts.length > 0 && (
        <div style={{
          borderTop: "1px solid rgba(255,255,255,0.03)", padding: "8px 12px",
        }}>
          <div style={{
            fontSize: 6, color: "#333", letterSpacing: "0.1em",
            marginBottom: 5, textTransform: "uppercase",
          }}>
            Artifacts
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {artifacts.map((a, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 3,
                padding: "2px 6px", borderRadius: 2,
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.03)",
                fontSize: 6, color: "#666", cursor: "pointer",
              }}>
                <span>{a.type === "folder" ? "📁" : a.type === "image" ? "🎨" : a.type === "spreadsheet" ? "📊" : a.type === "presentation" ? "📑" : "📄"}</span>
                {a.name}
                {a.size && <span style={{ color: "#333", fontSize: 5 }}>{a.size}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.7); }
        }
      `}</style>
    </div>
  );
}
