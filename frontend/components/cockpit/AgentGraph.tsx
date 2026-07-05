"use client";

import { useEffect, useState, useCallback } from "react";

interface AgentNode {
  id: string;
  label: string;
  x: number;
  y: number;
  status: "idle" | "active" | "error";
  type: "supervisor" | "worker";
}

const NODES: AgentNode[] = [
  { id: "supervisor", label: "SUPERVISOR", x: 200, y: 60, status: "idle", type: "supervisor" },
  { id: "os", label: "OS", x: 80, y: 160, status: "idle", type: "worker" },
  { id: "hal", label: "HAL", x: 160, y: 180, status: "idle", type: "worker" },
  { id: "web", label: "WEB", x: 240, y: 180, status: "idle", type: "worker" },
  { id: "core", label: "CORE", x: 320, y: 160, status: "idle", type: "worker" },
];

const EDGES = [
  { from: "supervisor", to: "os" },
  { from: "supervisor", to: "hal" },
  { from: "supervisor", to: "web" },
  { from: "supervisor", to: "core" },
];

interface LogEntry {
  time: string;
  agent: string;
  msg: string;
  type: "info" | "action" | "error" | "success";
}

export default function AgentGraph() {
  const [nodes, setNodes] = useState(NODES);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeEdge, setActiveEdge] = useState<string | null>(null);

  const addLog = useCallback((agent: string, msg: string, type: LogEntry["type"] = "info") => {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}.${String(now.getMilliseconds()).padStart(3, "0")}`;
    setLogs(prev => [...prev.slice(-20), { time, agent, msg, type }]);
  }, []);

  const activateNode = useCallback((nodeId: string, duration = 2000) => {
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, status: "active" } : n));
    const edge = EDGES.find(e => e.to === nodeId);
    if (edge) setActiveEdge(`${edge.from}-${edge.to}`);
    setTimeout(() => {
      setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, status: "idle" } : n));
      setActiveEdge(null);
    }, duration);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      const agents = ["os", "hal", "web", "core"];
      const msgs = [
        "Reading accessibility tree...",
        "Emitting hex payload 0x0A...",
        "Navigating to target URL...",
        "Querying local graph...",
        "Processing user intent...",
        "Scanning subnet nodes...",
        "Updating memory weights...",
        "Dispatching to worker...",
      ];
      const agent = agents[Math.floor(Math.random() * agents.length)];
      const msg = msgs[Math.floor(Math.random() * msgs.length)];
      activateNode(agent, 1500);
      addLog(agent.toUpperCase(), msg, "action");
    }, 4000);
    return () => clearInterval(interval);
  }, [activateNode, addLog]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--void)" }}>
      {/* Header */}
      <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "var(--neon-green)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", fontWeight: 600 }}>AGENT NETWORK</span>
        <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{nodes.filter(n => n.status === "active").length}/5 active</span>
      </div>

      {/* SVG Graph */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 16, minHeight: 240 }}>
        <svg width="400" height="240" viewBox="0 0 400 240">
          {/* Edges */}
          {EDGES.map(edge => {
            const from = nodes.find(n => n.id === edge.from)!;
            const to = nodes.find(n => n.id === edge.to)!;
            const isActive = activeEdge === `${edge.from}-${edge.to}`;
            return (
              <line
                key={`${edge.from}-${edge.to}`}
                x1={from.x} y1={from.y}
                x2={to.x} y2={to.y}
                className={isActive ? "edge-active" : "edge-idle"}
                style={{ transition: "all 0.3s" }}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map(node => {
            const isActive = node.status === "active";
            const isSupervisor = node.type === "supervisor";
            const r = isSupervisor ? 28 : 22;
            return (
              <g key={node.id} className={isActive ? "animate-node" : ""}>
                {/* Glow ring for active nodes */}
                {isActive && (
                  <circle cx={node.x} cy={node.y} r={r + 8} fill="none" stroke="var(--neon-green)" strokeWidth="1" opacity="0.3">
                    <animate attributeName="r" from={r + 4} to={r + 16} dur="1s" repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.4" to="0" dur="1s" repeatCount="indefinite" />
                  </circle>
                )}
                {/* Node circle */}
                <circle
                  cx={node.x} cy={node.y} r={r}
                  className={isActive ? "node-active" : "node-idle"}
                  style={{ transition: "all 0.3s" }}
                />
                {/* Node label */}
                <text
                  x={node.x} y={node.y + 1}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{
                    fontSize: isSupervisor ? 8 : 7,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    fill: isActive ? "var(--neon-green)" : "var(--text-muted)",
                    letterSpacing: "0.08em",
                    transition: "fill 0.3s",
                  }}
                >
                  {node.label}
                </text>
                {/* Status dot */}
                <circle
                  cx={node.x + r - 4} cy={node.y - r + 4}
                  r={3}
                  fill={isActive ? "var(--neon-green)" : "#333"}
                  style={{ transition: "fill 0.3s" }}
                />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Action Stream */}
      <div style={{ borderTop: "1px solid var(--border)", padding: "8px 12px", maxHeight: 160, overflowY: "auto" }}>
        <div style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em", marginBottom: 6, textTransform: "uppercase" }}>Action Stream</div>
        {logs.length === 0 && (
          <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", opacity: 0.4, textAlign: "center", padding: "12px 0" }}>Awaiting dispatch...</div>
        )}
        {logs.map((log, i) => (
          <div key={i} className="animate-fade" style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 3, display: "flex", gap: 6, lineHeight: 1.5 }}>
            <span style={{ color: "var(--steel)", flexShrink: 0 }}>{log.time}</span>
            <span style={{ color: log.type === "error" ? "var(--crimson)" : log.type === "success" ? "var(--neon-green)" : "var(--amber)", flexShrink: 0 }}>[{log.agent}]</span>
            <span style={{ color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{log.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
