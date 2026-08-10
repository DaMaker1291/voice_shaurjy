"use client";

import React, { useRef, useEffect, useState } from "react";
import { BASE } from "@/lib/api";

interface Props {
  workspaceId?: string;
  isRunning?: boolean;
  currentAction?: string;
  missionId?: string;
}

interface GraphNode {
  id: string;
  action: string;
  description: string;
  status: string;
  result: any;
  verification: any;
  retries: number;
  started_at: number;
  completed_at: number;
}

interface AgentTeam {
  id: string;
  role: string;
  objective: string;
  status: string;
  tools: string[];
}

interface MissionData {
  id: string;
  objective: string;
  status: string;
  progress: number;
  current_action: string;
  nodes: Record<string, GraphNode>;
  agent_team: AgentTeam[];
  error: string;
}

export default function LiveWorkspace({ workspaceId, isRunning, currentAction, missionId }: Props) {
  const [mission, setMission] = useState<MissionData | null>(null);
  const [logs, setLogs] = useState<{ time: number; text: string; type: string }[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const prevStatuses = useRef<Record<string, string>>({});

  useEffect(() => {
    if (!missionId || !isRunning) return;
    let active = true;

    const poll = async () => {
      try {
        const res = await fetch(`${BASE}/api/workspace/mission/status?mission_id=${encodeURIComponent(missionId)}`);
        const data = await res.json();
        if (!active || !data.mission) return;

        const m: MissionData = data.mission;
        setMission(m);

        // Generate log entries for status changes
        const newLogs: typeof logs = [];
        if (m.agent_team) {
          m.agent_team.forEach((a) => {
            const prev = prevStatuses.current[a.id];
            if (prev !== a.status) {
              const text = a.status === "running" ? `► ${a.role} started` :
                a.status === "completed" ? `✓ ${a.role} finished` :
                  a.status === "failed" ? `✗ ${a.role} failed` :
                    `${a.role}: ${a.status}`;
              newLogs.push({ time: Date.now(), text, type: a.status });
            }
            prevStatuses.current[a.id] = a.status;
          });
        }
        if (m.nodes) {
          Object.values(m.nodes).forEach((n) => {
            const prev = prevStatuses.current[n.id];
            if (prev !== n.status) {
              const text = n.status === "running" ? `► ${n.description.slice(0, 50)}` :
                n.status === "completed" ? `✓ ${n.description.slice(0, 50)}` :
                  n.status === "failed" ? `✗ ${n.description.slice(0, 50)}` :
                    `${n.description.slice(0, 40)}: ${n.status}`;
              newLogs.push({ time: Date.now(), text, type: n.status });
            }
            prevStatuses.current[n.id] = n.status;
          });
        }
        if (newLogs.length > 0) {
          setLogs((prev) => [...prev.slice(-300), ...newLogs]);
        }
      } catch { /* ok */ }
    };

    poll();
    const interval = setInterval(poll, 1500);
    return () => { active = false; clearInterval(interval); };
  }, [missionId, isRunning]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const statusColor = (s: string) =>
    s === "completed" ? "#00FF66" :
    s === "running" ? "#FFB300" :
    s === "failed" ? "#EF4444" :
    s === "ready" ? "#0096FF" :
    "#555";

  if (!isRunning) {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#030305", gap: 16, padding: 24 }}>
        <div style={{ width: 48, height: 48, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 20, opacity: 0.3 }}>◉</span>
        </div>
        <div style={{ fontSize: 11, color: "#333", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.1em" }}>WORKSPACE OFFLINE</div>
        <div style={{ fontSize: 10, color: "#444", textAlign: "center", maxWidth: 280, lineHeight: 1.6 }}>Enter a mission to provision a workspace and deploy agents.</div>
      </div>
    );
  }

  const nodes = mission ? Object.values(mission.nodes || {}) : [];
  const completedNodes = nodes.filter((n) => n.status === "completed").length;
  const totalNodes = nodes.length;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#030305", minWidth: 0, minHeight: 0 }}>
      {/* Status bar */}
      <div style={{ height: 28, background: "#08090c", borderBottom: "1px solid rgba(255,255,255,0.04)", display: "flex", alignItems: "center", padding: "0 10px", gap: 12, flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 6px rgba(0,255,102,0.4)", display: "inline-block", animation: "jv-pulse 1.5s infinite" }} />
          <span style={{ fontSize: 9, color: "#00FF66", fontFamily: "'JetBrains Mono', monospace" }}>LIVE</span>
        </div>
        {workspaceId && <span style={{ fontSize: 8, color: "#444", fontFamily: "'JetBrains Mono', monospace" }}>ws://{workspaceId}</span>}
        <div style={{ flex: 1 }} />
        {totalNodes > 0 && (
          <span style={{ fontSize: 8, color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>
            {completedNodes}/{totalNodes} nodes
          </span>
        )}
        {mission?.agent_team && (
          <span style={{ fontSize: 8, color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>
            {mission.agent_team.length} agents
          </span>
        )}
      </div>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Main content area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          {/* Mission Graph Visualization */}
          {mission?.agent_team && mission.agent_team.length > 0 && (
            <div style={{ borderBottom: "1px solid rgba(255,255,255,0.04)", padding: "8px 10px", background: "rgba(0,0,0,0.2)" }}>
              <div style={{ fontSize: 8, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em", marginBottom: 6 }}>AGENT TEAM</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {mission.agent_team.map((a) => (
                  <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 3, background: `${statusColor(a.status)}11`, border: `1px solid ${statusColor(a.status)}33` }}>
                    <span style={{ width: 5, height: 5, borderRadius: "50%", background: statusColor(a.status), display: "inline-block" }} />
                    <span style={{ fontSize: 8, color: statusColor(a.status), fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                      {a.role}
                    </span>
                    {a.status === "running" && (
                      <span style={{ fontSize: 7, color: "#777", fontFamily: "'JetBrains Mono', monospace" }}>working...</span>
                    )}
                    {a.status === "completed" && (
                      <span style={{ fontSize: 7, color: "#00FF66", fontFamily: "'JetBrains Mono', monospace" }}>✓</span>
                    )}
                    {a.status === "failed" && (
                      <span style={{ fontSize: 7, color: "#EF4444", fontFamily: "'JetBrains Mono', monospace" }}>✗</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Log stream */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ height: 22, display: "flex", alignItems: "center", padding: "0 10px", borderBottom: "1px solid rgba(255,255,255,0.03)", background: "rgba(255,255,255,0.01)", flexShrink: 0 }}>
              <span style={{ fontSize: 8, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>MISSION LOG</span>
            </div>
            <div ref={logRef} style={{ flex: 1, overflow: "auto", padding: "6px 10px", display: "flex", flexDirection: "column", gap: 1 }}>
              {logs.length === 0 && (
                <div style={{ fontSize: 10, color: "#333", fontFamily: "'JetBrains Mono', monospace" }}>Waiting for agent activity...</div>
              )}
              {logs.map((log, i) => (
                <div key={i} style={{ fontSize: 10, lineHeight: 1.5, fontFamily: "'JetBrains Mono', monospace", display: "flex", gap: 6 }}>
                  <span style={{ color: "#333", flexShrink: 0 }}>
                    {new Date(log.time).toLocaleTimeString("en", { hour12: false })}
                  </span>
                  <span style={{ color: log.type === "completed" ? "#00FF66" : log.type === "failed" ? "#EF4444" : log.type === "running" ? "#FFB300" : "#777" }}>
                    {log.text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel — Graph Nodes */}
        {nodes.length > 0 && (
          <div style={{ width: 220, display: "flex", flexDirection: "column", flexShrink: 0, borderLeft: "1px solid rgba(255,255,255,0.04)" }}>
            <div style={{ height: 22, display: "flex", alignItems: "center", padding: "0 10px", borderBottom: "1px solid rgba(255,255,255,0.03)", background: "rgba(255,255,255,0.01)", flexShrink: 0 }}>
              <span style={{ fontSize: 8, color: "#555", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.08em" }}>GRAPH</span>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "6px 8px" }}>
              {nodes.map((n) => (
                <div key={n.id} style={{ padding: "5px 6px", marginBottom: 4, borderRadius: 3, background: "rgba(255,255,255,0.01)", borderLeft: `2px solid ${statusColor(n.status)}` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}>
                    <span style={{ width: 4, height: 4, borderRadius: "50%", background: statusColor(n.status), flexShrink: 0 }} />
                    <span style={{ fontSize: 9, color: statusColor(n.status), fontFamily: "'JetBrains Mono', monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {n.description.slice(0, 28)}
                    </span>
                  </div>
                  {n.verification && !n.verification.success && (
                    <div style={{ fontSize: 7, color: "#EF4444", fontFamily: "'JetBrains Mono', monospace", paddingLeft: 8 }}>
                      ↳ {n.verification.diagnosis.slice(0, 35)}
                    </div>
                  )}
                  {n.retries > 0 && (
                    <div style={{ fontSize: 7, color: "#FFB300", fontFamily: "'JetBrains Mono', monospace", paddingLeft: 8 }}>
                      retry #{n.retries}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Current action footer */}
      {(currentAction || mission?.current_action) && (
        <div style={{ height: 24, background: "#08090c", borderTop: "1px solid rgba(0,255,102,0.08)", display: "flex", alignItems: "center", padding: "0 10px", gap: 6, flexShrink: 0 }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#FFB300", animation: "jv-pulse 1s infinite", display: "inline-block" }} />
          <span style={{ fontSize: 9, color: "#FFB300", fontFamily: "'JetBrains Mono', monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {mission?.current_action || currentAction}
          </span>
        </div>
      )}

      <style>{`@keyframes jv-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.4;transform:scale(0.7)} }`}</style>
    </div>
  );
}
