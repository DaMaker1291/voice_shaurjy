"use client";

import React from "react";

interface MissionPanelProps {
  mission?: string;
  objective?: string;
  steps?: {
    label: string;
    description?: string;
    status: "done" | "active" | "pending" | "error";
    actions?: { label: string; status: string }[];
  }[];
  onStepClick?: (index: number) => void;
}

export default function MissionPanel({
  mission = "",
  objective = "",
  steps = [],
}: MissionPanelProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "done": return "✓";
      case "active": return "●";
      case "error": return "✗";
      default: return "○";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "done": return "#00FF66";
      case "active": return "#FFB300";
      case "error": return "#EF4444";
      default: return "#222";
    }
  };

  return (
    <div style={{
      width: 220,
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
          marginBottom: 4, textTransform: "uppercase",
        }}>
          Mission
        </div>
        <div style={{
          fontSize: 10, color: "#ccc", fontWeight: 500, lineHeight: 1.4,
        }}>
          {mission || "No active mission"}
        </div>
        {objective && mission && (
          <div style={{
            fontSize: 7, color: "#555", marginTop: 4, lineHeight: 1.3,
          }}>
            {objective}
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
        <div style={{
          fontSize: 6, color: "#333", letterSpacing: "0.1em",
          padding: "4px 12px", textTransform: "uppercase",
        }}>
          Progress
        </div>
        {steps.length === 0 && (
          <div style={{
            padding: "8px 12px",
            fontSize: 7, color: "#333", lineHeight: 1.4,
          }}>
            Define a mission to see steps here.
          </div>
        )}
        {steps.map((step, i) => (
          <div key={i}>
            <div style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 6,
              padding: "5px 12px",
              background: step.status === "active" ? "rgba(255,179,0,0.02)" : "transparent",
              transition: "background 0.15s",
            }}>
              <span style={{
                fontSize: 8, color: getStatusColor(step.status),
                width: 10, textAlign: "center", marginTop: 1, flexShrink: 0,
              }}>
                {getStatusIcon(step.status)}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 8,
                  color: step.status === "active" ? "#ccc" : step.status === "done" ? "#444" : "#333",
                  fontWeight: step.status === "active" ? 500 : 400,
                  lineHeight: 1.3,
                }}>
                  {step.label}
                </div>
                {step.actions && step.status === "active" && (
                  <div style={{ marginTop: 3, paddingLeft: 3, borderLeft: "1px solid rgba(255,179,0,0.1)" }}>
                    {step.actions.map((action, j) => (
                      <div key={j} style={{
                        fontSize: 6,
                        color: action.status === "done" ? "#444" : "#FFB300",
                        padding: "1px 0",
                      }}>
                        {action.status === "done" ? "✓" : "○"} {action.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
