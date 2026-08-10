"use client";

import React, { useState } from "react";

interface Evidence {
  check: string;
  passed: boolean;
  detail?: string;
  timestamp?: string;
}

interface EvidencePanelProps {
  title?: string;
  type?: "website" | "powerpoint" | "blender" | "file" | "general";
  evidence?: Evidence[];
  onViewFiles?: () => void;
  onViewTerminal?: () => void;
  onOpenUrl?: () => void;
}

export default function EvidencePanel({
  title = "Action Verified",
  type = "general",
  evidence = [],
  onViewFiles,
  onViewTerminal,
  onOpenUrl,
}: EvidencePanelProps) {
  const [expanded, setExpanded] = useState(true);

  const getTypeIcon = () => {
    switch (type) {
      case "website": return "🌐";
      case "powerpoint": return "📑";
      case "blender": return "🎨";
      case "file": return "📄";
      default: return "✓";
    }
  };

  const passedCount = evidence.filter(e => e.passed).length;
  const totalCount = evidence.length;
  const allPassed = passedCount === totalCount && totalCount > 0;

  return (
    <div style={{
      borderRadius: 6,
      background: allPassed ? "rgba(0,255,102,0.02)" : "rgba(255,179,0,0.02)",
      border: `1px solid ${allPassed ? "rgba(0,255,102,0.08)" : "rgba(255,179,0,0.08)"}`,
      overflow: "hidden",
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 10px",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}>
          <span style={{ fontSize: 10, color: allPassed ? "#00FF66" : "#FFB300" }}>
            {getTypeIcon()}
          </span>
          <span style={{
            fontSize: 8,
            color: "#ccc",
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 500,
          }}>
            {title}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            fontSize: 6,
            color: allPassed ? "#00FF66" : "#FFB300",
            fontFamily: "'JetBrains Mono', monospace",
            padding: "1px 5px",
            borderRadius: 2,
            background: allPassed ? "rgba(0,255,102,0.08)" : "rgba(255,179,0,0.08)",
          }}>
            {passedCount}/{totalCount}
          </span>
          <span style={{
            fontSize: 6,
            color: "#444",
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}>
            ▼
          </span>
        </div>
      </div>

      {expanded && evidence.length > 0 && (
        <div style={{
          padding: "0 10px 8px",
          borderTop: "1px solid rgba(255,255,255,0.02)",
        }}>
          {evidence.map((ev, i) => (
            <div key={i} style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 5,
              padding: "3px 0",
            }}>
              <span style={{
                fontSize: 7,
                color: ev.passed ? "#00FF66" : "#EF4444",
                width: 10,
                textAlign: "center",
                flexShrink: 0,
                marginTop: 1,
              }}>
                {ev.passed ? "✓" : "✗"}
              </span>
              <div style={{ flex: 1 }}>
                <span style={{
                  fontSize: 7,
                  color: ev.passed ? "#999" : "#EF4444",
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {ev.check}
                </span>
                {ev.detail && (
                  <span style={{
                    fontSize: 6,
                    color: "#444",
                    marginLeft: 4,
                  }}>
                    {ev.detail}
                  </span>
                )}
              </div>
              {ev.timestamp && (
                <span style={{
                  fontSize: 5,
                  color: "#333",
                  fontFamily: "'JetBrains Mono', monospace",
                  flexShrink: 0,
                }}>
                  {ev.timestamp}
                </span>
              )}
            </div>
          ))}

          {(onViewFiles || onViewTerminal || onOpenUrl) && (
            <div style={{
              display: "flex",
              gap: 4,
              marginTop: 6,
              paddingTop: 6,
              borderTop: "1px solid rgba(255,255,255,0.02)",
            }}>
              {onViewTerminal && (
                <button
                  onClick={onViewTerminal}
                  style={{
                    padding: "2px 8px", borderRadius: 2, fontSize: 6,
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.04)",
                    color: "#666", cursor: "pointer",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  VIEW TERMINAL
                </button>
              )}
              {onViewFiles && (
                <button
                  onClick={onViewFiles}
                  style={{
                    padding: "2px 8px", borderRadius: 2, fontSize: 6,
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.04)",
                    color: "#666", cursor: "pointer",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  VIEW FILES
                </button>
              )}
              {onOpenUrl && (
                <button
                  onClick={onOpenUrl}
                  style={{
                    padding: "2px 8px", borderRadius: 2, fontSize: 6,
                    background: "rgba(0,180,216,0.06)",
                    border: "1px solid rgba(0,180,216,0.1)",
                    color: "#00B4D8", cursor: "pointer",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  OPEN SITE
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export type { Evidence };
