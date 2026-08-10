"use client";

import { useEffect, useState, useCallback } from "react";

interface AgentNode {
  id: string;
  label: string;
  x: number;
  y: number;
  status: "idle" | "active" | "error" | "queued";
  type: "supervisor" | "worker" | "specialist";
  task?: string;
  progress?: number;
}

interface Edge {
  from: string;
  to: string;
}

const INITIAL_NODES: AgentNode[] = [
  { id: "supervisor", label: "SUPERVISOR", x: 200, y: 40, status: "idle", type: "supervisor" },
  { id: "os", label: "OS", x: 60, y: 120, status: "idle", type: "worker" },
  { id: "hal", label: "HAL", x: 140, y: 140, status: "idle", type: "worker" },
  { id: "web", label: "WEB", x: 260, y: 140, status: "idle", type: "worker" },
  { id: "core", label: "CORE", x: 340, y: 120, status: "idle", type: "worker" },
  { id: "memory", label: "MEM", x: 100, y: 210, status: "idle", type: "specialist" },
  { id: "security", label: "SEC", x: 200, y: 230, status: "idle", type: "specialist" },
  { id: "router", label: "RTR", x: 300, y: 210, status: "idle", type: "specialist" },
  { id: "device", label: "DEV", x: 150, y: 280, status: "idle", type: "specialist" },
  { id: "voice", label: "VOC", x: 250, y: 280, status: "idle", type: "specialist" },
];

const INITIAL_EDGES: Edge[] = [
  { from: "supervisor", to: "os" },
  { from: "supervisor", to: "hal" },
  { from: "supervisor", to: "web" },
  { from: "supervisor", to: "core" },
  { from: "os", to: "memory" },
  { from: "hal", to: "device" },
  { from: "web", to: "router" },
  { from: "core", to: "security" },
  { from: "security", to: "voice" },
  { from: "memory", to: "device" },
];

interface LogEntry {
  time: string;
  agent: string;
  msg: string;
  type: "info" | "action" | "error" | "success";
}

const AGENT_MSGS: Record<string, string[]> = {
  os: ["Reading accessibility tree...", "Updating memory weights...", "Scanning process list...", "Capturing screenshot...", "Managing window focus..."],
  hal: ["Emitting hex payload 0x0A...", "Polling GPIO pins...", "Syncing device state...", "Sending Wake-on-LAN...", "Querying sensor data..."],
  web: ["Navigating to target URL...", "Fetching API response...", "Scraping DOM elements...", "Dispatching to worker...", "Resolving DNS..."],
  core: ["Processing user intent...", "Querying local graph...", "Generating response...", "Updating knowledge base...", "Running inference..."],
  memory: ["Loading vector embeddings...", "Indexing new memories...", "Pruning stale entries...", "Computing similarity...", "Consolidating context..."],
  security: ["Validating HMAC signature...", "Checking subnet pinning...", "Auditing command log...", "Rotating API keys...", "Scanning threat intel..."],
  router: ["Classifying intent...", "Evaluating confidence...", "Dispatching to worker...", "Balancing load...", "Updating route table..."],
  device: ["Scanning ARP table...", "Probing TCP ports...", "Syncing device registry...", "Executing device command...", "Updating device state..."],
  voice: ["Processing audio stream...", "Running STT inference...", "Generating speech...", "Playing audio buffer...", "Calibrating microphone..."],
};

export default function AgentGraph() {
  const [nodes, setNodes] = useState(INITIAL_NODES);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeEdge, setActiveEdge] = useState<string | null>(null);
  const [particles, setParticles] = useState<{ id: number; fromX: number; fromY: number; toX: number; toY: number; color: string; start: number }[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const addLog = useCallback((agent: string, msg: string, type: LogEntry["type"] = "info") => {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}.${String(now.getMilliseconds()).padStart(3, "0")}`;
    setLogs(prev => [...prev.slice(-30), { time, agent, msg, type }]);
  }, []);

  const activateNode = useCallback((nodeId: string, duration = 2000) => {
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, status: "active" as const } : n));
    const edge = INITIAL_EDGES.find(e => e.to === nodeId);
    if (edge) {
      setActiveEdge(`${edge.from}-${edge.to}`);
      const fromNode = INITIAL_NODES.find(n => n.id === edge.from);
      const toNode = INITIAL_NODES.find(n => n.id === edge.to);
      if (fromNode && toNode) {
        const pid = Date.now();
        setParticles(prev => [...prev, {
          id: pid,
          fromX: fromNode.x, fromY: fromNode.y,
          toX: toNode.x, toY: toNode.y,
          color: "#00FF66",
          start: Date.now(),
        }]);
        setTimeout(() => setParticles(prev => prev.filter(p => p.id !== pid)), 1500);
      }
    }
    setTimeout(() => {
      setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, status: "idle" as const } : n));
      setActiveEdge(null);
    }, duration);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      const workerIds = ["os", "hal", "web", "core", "memory", "security", "router", "device", "voice"];
      const agent = workerIds[Math.floor(Math.random() * workerIds.length)];
      const msgs = AGENT_MSGS[agent] || ["Processing..."];
      const msg = msgs[Math.floor(Math.random() * msgs.length)];
      activateNode(agent, 1500);
      addLog(agent.toUpperCase(), msg, "action");
    }, 3000);
    return () => clearInterval(interval);
  }, [activateNode, addLog]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--void)" }}>
      {/* Header */}
      <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "var(--neon-green)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", fontWeight: 600 }}>AGENT NETWORK</span>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{nodes.filter(n => n.status === "active").length}/{nodes.length}</span>
          <div style={{ display: "flex", gap: 3 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 6px rgba(0,255,102,0.4)" }} />
          </div>
        </div>
      </div>

      {/* SVG Graph */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 8, minHeight: 200 }}>
        <svg width="400" height="320" viewBox="0 0 400 320">
          {/* Edges */}
          {INITIAL_EDGES.map(edge => {
            const from = nodes.find(n => n.id === edge.from)!;
            const to = nodes.find(n => n.id === edge.to)!;
            const isActive = activeEdge === `${edge.from}-${edge.to}`;
            return (
              <g key={`${edge.from}-${edge.to}`}>
                <line
                  x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                  className={isActive ? "edge-active" : "edge-idle"}
                  style={{ transition: "all 0.3s" }}
                />
                {isActive && (
                  <circle r="3" fill="var(--neon-green)" opacity="0.8">
                    <animateMotion dur="1s" repeatCount="1" path={`M${from.x},${from.y} L${to.x},${to.y}`} />
                  </circle>
                )}
              </g>
            );
          })}

          {/* Data flow particles */}
          {particles.map(p => {
            const elapsed = Date.now() - p.start;
            const t = Math.min(elapsed / 1500, 1);
            const x = p.fromX + (p.toX - p.fromX) * t;
            const y = p.fromY + (p.toY - p.fromY) * t;
            return (
              <circle key={p.id} cx={x} cy={y} r="2" fill={p.color} opacity={1 - t}>
                <animate attributeName="r" from="2" to="4" dur="0.3s" repeatCount="indefinite" />
              </circle>
            );
          })}

          {/* Nodes */}
          {nodes.map(node => {
            const isActive = node.status === "active";
            const isSupervisor = node.type === "supervisor";
            const isSpecialist = node.type === "specialist";
            const r = isSupervisor ? 24 : isSpecialist ? 16 : 18;
            const isSelected = selectedNode === node.id;
            return (
              <g key={node.id} onClick={() => setSelectedNode(isSelected ? null : node.id)} style={{ cursor: "pointer" }}>
                {/* Glow ring for active nodes */}
                {isActive && (
                  <circle cx={node.x} cy={node.y} r={r + 6} fill="none" stroke="var(--neon-green)" strokeWidth="1" opacity="0.3">
                    <animate attributeName="r" from={r + 2} to={r + 14} dur="1s" repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.4" to="0" dur="1s" repeatCount="indefinite" />
                  </circle>
                )}
                {/* Selection ring */}
                {isSelected && (
                  <circle cx={node.x} cy={node.y} r={r + 4} fill="none" stroke="var(--amber)" strokeWidth="1" strokeDasharray="4 2" opacity="0.5">
                    <animateTransform attributeName="transform" type="rotate" from={`0 ${node.x} ${node.y}`} to={`360 ${node.x} ${node.y}`} dur="4s" repeatCount="indefinite" />
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
                    fontSize: isSupervisor ? 7 : 6,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    fill: isActive ? "var(--neon-green)" : isSelected ? "var(--amber)" : "var(--text-muted)",
                    letterSpacing: "0.08em",
                    transition: "fill 0.3s",
                  }}
                >
                  {node.label}
                </text>
                {/* Status dot */}
                <circle
                  cx={node.x + r - 3} cy={node.y - r + 3}
                  r={2.5}
                  fill={isActive ? "var(--neon-green)" : node.status === "error" ? "var(--crimson)" : "#333"}
                  style={{ transition: "fill 0.3s" }}
                />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Selected node info */}
      {selectedNode && nodes.find(n => n.id === selectedNode) && (() => {
          const node = nodes.find(n => n.id === selectedNode)!;
          return (
            <div style={{ padding: "8px 14px", borderTop: "1px solid var(--border)", background: "var(--surface-raised)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 9, color: "var(--neon-green)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>{node.label}</span>
                <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{node.type}</span>
                <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: node.status === "active" ? "var(--neon-green-dim)" : "var(--surface)", color: node.status === "active" ? "var(--neon-green)" : "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{node.status}</span>
              </div>
              <div style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                Connections: {INITIAL_EDGES.filter(e => e.from === node.id || e.to === node.id).map(e => e.from === node.id ? e.to : e.from).join(", ")}
              </div>
            </div>
          );
      })()}
    </div>
  );
}
