"use client";

import React, { useState } from "react";

interface MissionRecord {
  id: string;
  objective: string;
  status: "completed" | "failed" | "paused" | "stopped";
  startedAt: string;
  completedAt?: string;
  actions: number;
  recoveries: number;
  errors: number;
  artifacts?: { name: string; type: string; size?: string }[];
  steps?: { label: string; status: string }[];
}

interface MissionHistoryProps {
  missions?: MissionRecord[];
  onSelectMission?: (mission: MissionRecord) => void;
  onResumeMission?: (mission: MissionRecord) => void;
}

export default function MissionHistory({
  missions = [],
  onSelectMission,
  onResumeMission,
}: MissionHistoryProps) {
  const [expandedMission, setExpandedMission] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "completed" | "failed" | "paused">("all");

  const filteredMissions = missions.filter(m => {
    if (filter === "all") return true;
    return m.status === filter;
  });

  const groupedByDate = filteredMissions.reduce((groups, mission) => {
    const date = new Date(mission.startedAt).toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    if (!groups[date]) groups[date] = [];
    groups[date].push(mission);
    return groups;
  }, {} as Record<string, MissionRecord[]>);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed": return "#00FF66";
      case "failed": return "#EF4444";
      case "paused": return "#FFB300";
      case "stopped": return "#666";
      default: return "#444";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed": return "✓";
      case "failed": return "✗";
      case "paused": return "Ⅱ";
      case "stopped": return "■";
      default: return "○";
    }
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 14px",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
      }}>
        <div style={{
          fontSize: 8,
          color: "#555",
          fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
        }}>
          Mission History
        </div>
        <div style={{ display: "flex", gap: 3 }}>
          {(["all", "completed", "failed", "paused"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: "2px 6px",
                borderRadius: 2,
                fontSize: 5,
                fontFamily: "'JetBrains Mono', monospace",
                background: filter === f ? "rgba(0,255,102,0.06)" : "transparent",
                border: `1px solid ${filter === f ? "rgba(0,255,102,0.12)" : "rgba(255,255,255,0.03)"}`,
                color: filter === f ? "#00FF66" : "#444",
                cursor: "pointer",
                letterSpacing: "0.06em",
                textTransform: "capitalize",
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
        {Object.keys(groupedByDate).length === 0 && (
          <div style={{
            padding: "24px 14px",
            textAlign: "center",
            fontSize: 8,
            color: "#333",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            No missions yet.
            <br />
            <span style={{ fontSize: 6, color: "#222" }}>
              Start your first mission above.
            </span>
          </div>
        )}

        {Object.entries(groupedByDate).map(([date, dateMissions]) => (
          <div key={date}>
            <div style={{
              fontSize: 6,
              color: "#333",
              letterSpacing: "0.1em",
              padding: "6px 14px 4px",
              textTransform: "uppercase",
            }}>
              {date}
            </div>
            {dateMissions.map(mission => (
              <div key={mission.id}>
                <div
                  onClick={() => {
                    setExpandedMission(expandedMission === mission.id ? null : mission.id);
                    onSelectMission?.(mission);
                  }}
                  style={{
                    padding: "6px 14px",
                    cursor: "pointer",
                    transition: "background 0.15s",
                    background: expandedMission === mission.id ? "rgba(255,255,255,0.02)" : "transparent",
                  }}
                >
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}>
                    <span style={{
                      fontSize: 8,
                      color: getStatusColor(mission.status),
                      width: 12,
                      textAlign: "center",
                      flexShrink: 0,
                    }}>
                      {getStatusIcon(mission.status)}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 8,
                        color: "#999",
                        fontFamily: "'JetBrains Mono', monospace",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}>
                        {mission.objective}
                      </div>
                    </div>
                    <div style={{
                      display: "flex",
                      gap: 6,
                      flexShrink: 0,
                    }}>
                      <span style={{
                        fontSize: 5,
                        color: "#444",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {mission.actions}A
                      </span>
                      {mission.recoveries > 0 && (
                        <span style={{
                          fontSize: 5,
                          color: "#FFB300",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {mission.recoveries}R
                        </span>
                      )}
                      {mission.errors > 0 && (
                        <span style={{
                          fontSize: 5,
                          color: "#EF4444",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {mission.errors}E
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {expandedMission === mission.id && (
                  <div style={{
                    padding: "4px 14px 8px 34px",
                    borderBottom: "1px solid rgba(255,255,255,0.02)",
                  }}>
                    {mission.steps && mission.steps.length > 0 && (
                      <div style={{ marginBottom: 6 }}>
                        {mission.steps.slice(0, 6).map((step, i) => (
                          <div key={i} style={{
                            fontSize: 6,
                            color: step.status === "done" ? "#444" : step.status === "active" ? "#FFB300" : "#333",
                            fontFamily: "'JetBrains Mono', monospace",
                            padding: "1px 0",
                          }}>
                            {step.status === "done" ? "✓" : step.status === "active" ? "●" : "○"} {step.label}
                          </div>
                        ))}
                        {mission.steps.length > 6 && (
                          <div style={{
                            fontSize: 5,
                            color: "#333",
                            fontFamily: "'JetBrains Mono', monospace",
                            marginTop: 2,
                          }}>
                            +{mission.steps.length - 6} more steps
                          </div>
                        )}
                      </div>
                    )}

                    {mission.artifacts && mission.artifacts.length > 0 && (
                      <div style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 3,
                        marginBottom: 6,
                      }}>
                        {mission.artifacts.slice(0, 4).map((a, i) => (
                          <span key={i} style={{
                            padding: "1px 5px",
                            borderRadius: 2,
                            background: "rgba(255,255,255,0.02)",
                            border: "1px solid rgba(255,255,255,0.03)",
                            fontSize: 5,
                            color: "#555",
                            fontFamily: "'JetBrains Mono', monospace",
                          }}>
                            {a.type === "folder" ? "📁" : a.type === "image" ? "🎨" : a.type === "spreadsheet" ? "📊" : "📄"} {a.name}
                          </span>
                        ))}
                      </div>
                    )}

                    <div style={{ display: "flex", gap: 4 }}>
                      {onResumeMission && mission.status === "paused" && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onResumeMission(mission); }}
                          style={{
                            padding: "3px 8px", borderRadius: 2, fontSize: 5,
                            background: "rgba(0,255,102,0.06)",
                            border: "1px solid rgba(0,255,102,0.1)",
                            color: "#00FF66", cursor: "pointer",
                            fontFamily: "'JetBrains Mono', monospace",
                          }}
                        >
                          RESUME
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export type { MissionRecord };
