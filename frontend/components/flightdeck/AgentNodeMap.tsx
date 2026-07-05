"use client";

import { useEffect, useState, useRef, useCallback } from "react";

interface AgentNode {
  id: string;
  label: string;
  status: "idle" | "active" | "processing" | "error" | "offline";
  type: "supervisor" | "worker" | "tool" | "memory";
  x: number;
  y: number;
  confidence?: number;
  lastAction?: string;
}

interface Edge {
  from: string;
  to: string;
  active: boolean;
  confidence: number;
}

interface AgentNodeMapProps {
  activeAgent?: string;
  routingConfidence?: number;
  activityLog?: { ts: number; msg: string; agent?: string; type: string }[];
}

const AGENT_COLORS: Record<string, string> = {
  supervisor: "#a78bfa",
  OS_AGENT: "#34d399",
  HAL_AGENT: "#22d3ee",
  WEB_AGENT: "#fbbf24",
  CORE_AGENT: "#f472b6",
  tool: "#6b7280",
  memory: "#c084fc",
};

const STATUS_GLOW: Record<string, string> = {
  idle: "rgba(107,114,128,0.3)",
  active: "rgba(52,211,153,0.6)",
  processing: "rgba(167,139,250,0.5)",
  error: "rgba(239,68,68,0.5)",
  offline: "rgba(55,65,81,0.3)",
};

export default function AgentNodeMap({
  activeAgent,
  routingConfidence = 0,
  activityLog = [],
}: AgentNodeMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [pulseTick, setPulseTick] = useState(0);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  useEffect(() => {
    const i = setInterval(() => setPulseTick((p) => p + 1), 1200);
    return () => clearInterval(i);
  }, []);

  const nodes: AgentNode[] = [
    { id: "supervisor", label: "SUPERVISOR", status: activeAgent ? "active" : "idle", type: "supervisor", x: 200, y: 140 },
    { id: "OS_AGENT", label: "OS", status: activeAgent === "OS_AGENT" ? "processing" : "idle", type: "worker", x: 80, y: 60 },
    { id: "HAL_AGENT", label: "HAL", status: activeAgent === "HAL_AGENT" ? "processing" : "idle", type: "worker", x: 80, y: 220 },
    { id: "WEB_AGENT", label: "WEB", status: activeAgent === "WEB_AGENT" ? "processing" : "idle", type: "worker", x: 320, y: 60 },
    { id: "CORE_AGENT", label: "CORE", status: activeAgent === "CORE_AGENT" ? "processing" : "idle", type: "worker", x: 320, y: 220 },
    { id: "memory", label: "MEM", status: "idle", type: "memory", x: 200, y: 280 },
    { id: "vault", label: "VAULT", status: "idle", type: "tool", x: 50, y: 140 },
    { id: "sandbox", label: "SANDBOX", status: "idle", type: "tool", x: 350, y: 140 },
  ];

  const getNodeById = useCallback((id: string) => nodes.find((n) => n.id === id), [nodes]);

  const edges: Edge[] = [
    { from: "supervisor", to: "OS_AGENT", active: activeAgent === "OS_AGENT", confidence: activeAgent === "OS_AGENT" ? routingConfidence : 0 },
    { from: "supervisor", to: "HAL_AGENT", active: activeAgent === "HAL_AGENT", confidence: activeAgent === "HAL_AGENT" ? routingConfidence : 0 },
    { from: "supervisor", to: "WEB_AGENT", active: activeAgent === "WEB_AGENT", confidence: activeAgent === "WEB_AGENT" ? routingConfidence : 0 },
    { from: "supervisor", to: "CORE_AGENT", active: activeAgent === "CORE_AGENT", confidence: activeAgent === "CORE_AGENT" ? routingConfidence : 0 },
    { from: "supervisor", to: "memory", active: false, confidence: 0 },
    { from: "supervisor", to: "vault", active: false, confidence: 0 },
    { from: "supervisor", to: "sandbox", active: false, confidence: 0 },
  ];

  const recentLogs = activityLog.slice(-5);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-3 py-2 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
          <span className="text-[10px] font-mono text-zinc-500 tracking-widest uppercase">
            Agent Network
          </span>
        </div>
      </div>

      {/* SVG Network */}
      <div className="flex-1 relative overflow-hidden">
        <svg
          ref={svgRef}
          viewBox="0 0 400 320"
          className="w-full h-full"
          style={{ filter: "drop-shadow(0 0 20px rgba(167,139,250,0.05))" }}
        >
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-strong">
              <feGaussianBlur stdDeviation="6" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <radialGradient id="nodeGrad" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(255,255,255,0.08)" />
              <stop offset="100%" stopColor="rgba(255,255,255,0)" />
            </radialGradient>
          </defs>

          {/* Grid lines */}
          {[0, 80, 160, 240, 320, 400].map((x) => (
            <line key={`gx${x}`} x1={x} y1={0} x2={x} y2={320} stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
          ))}
          {[0, 80, 160, 240, 320].map((y) => (
            <line key={`gy${y}`} x1={0} y1={y} x2={400} y2={y} stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
          ))}

          {/* Edges */}
          {edges.map((edge, i) => {
            const from = getNodeById(edge.from);
            const to = getNodeById(edge.to);
            if (!from || !to) return null;
            const isActive = edge.active;
            const opacity = isActive ? 0.8 : 0.15;
            const color = isActive ? AGENT_COLORS[edge.to] || "#a78bfa" : "rgba(255,255,255,0.1)";
            const strokeWidth = isActive ? 2 : 1;

            return (
              <g key={i}>
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={color}
                  strokeWidth={strokeWidth}
                  opacity={opacity}
                  filter={isActive ? "url(#glow)" : undefined}
                />
                {isActive && (
                  <circle r="3" fill={color} filter="url(#glow-strong)">
                    <animateMotion
                      dur="1.5s"
                      repeatCount="indefinite"
                      path={`M${from.x},${from.y} L${to.x},${to.y}`}
                    />
                  </circle>
                )}
                {isActive && edge.confidence > 0 && (
                  <text
                    x={(from.x + to.x) / 2}
                    y={(from.y + to.y) / 2 - 8}
                    textAnchor="middle"
                    fill={color}
                    fontSize="9"
                    fontFamily="monospace"
                    opacity="0.7"
                  >
                    {(edge.confidence * 100).toFixed(0)}%
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const color = AGENT_COLORS[node.id] || AGENT_COLORS[node.type] || "#6b7280";
            const isHovered = hoveredNode === node.id;
            const isActive = node.status === "processing" || node.status === "active";
            const r = node.type === "supervisor" ? 22 : node.type === "worker" ? 16 : 12;

            return (
              <g
                key={node.id}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Pulse ring for active nodes */}
                {isActive && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={r + 8}
                    fill="none"
                    stroke={color}
                    strokeWidth="1"
                    opacity={0.3 + (pulseTick % 2) * 0.2}
                    filter="url(#glow)"
                  />
                )}

                {/* Node background */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={r}
                  fill={STATUS_GLOW[node.status]}
                  stroke={color}
                  strokeWidth={isHovered ? 2 : 1}
                  filter={isActive ? "url(#glow)" : undefined}
                />

                {/* Node inner */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={r - 4}
                  fill="rgba(0,0,0,0.4)"
                  stroke={color}
                  strokeWidth="0.5"
                  opacity={isActive ? 1 : 0.5}
                />

                {/* Label */}
                <text
                  x={node.x}
                  y={node.y + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={isActive ? "#fff" : "rgba(255,255,255,0.5)"}
                  fontSize={node.type === "supervisor" ? "8" : "7"}
                  fontFamily="monospace"
                  fontWeight={isActive ? "bold" : "normal"}
                >
                  {node.label}
                </text>

                {/* Status dot */}
                <circle
                  cx={node.x + r - 2}
                  cy={node.y - r + 2}
                  r="3"
                  fill={
                    node.status === "processing"
                      ? "#34d399"
                      : node.status === "active"
                      ? "#fbbf24"
                      : node.status === "error"
                      ? "#ef4444"
                      : "#4b5563"
                  }
                  stroke="rgba(0,0,0,0.5)"
                  strokeWidth="1"
                />
              </g>
            );
          })}
        </svg>

        {/* Hover tooltip */}
        {hoveredNode && (() => {
          const node = getNodeById(hoveredNode);
          if (!node) return null;
          return (
            <div className="absolute bottom-2 left-2 right-2 bg-zinc-900/90 border border-zinc-700/50 rounded-lg px-3 py-2 backdrop-blur-sm">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: AGENT_COLORS[node.id] }} />
                <span className="text-[10px] font-mono text-zinc-300">{node.id}</span>
                <span className="text-[9px] font-mono text-zinc-500 ml-auto">{node.status}</span>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Activity Stream */}
      <div className="border-t border-white/[0.06] px-3 py-2 max-h-32 overflow-y-auto">
        <div className="text-[9px] font-mono text-zinc-600 mb-1 tracking-wider">STREAM</div>
        {recentLogs.length === 0 ? (
          <div className="text-[9px] font-mono text-zinc-700 italic">Awaiting input...</div>
        ) : (
          recentLogs.map((log, i) => (
            <div key={i} className="text-[9px] font-mono text-zinc-500 leading-relaxed truncate">
              <span className="text-zinc-600">
                {new Date(log.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              <span className="mx-1 text-zinc-700">|</span>
              {log.agent && (
                <span style={{ color: AGENT_COLORS[log.agent] || "#6b7280" }} className="mr-1">
                  [{log.agent.replace("_AGENT", "")}]
                </span>
              )}
              <span className="text-zinc-400">{log.msg.slice(0, 60)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
