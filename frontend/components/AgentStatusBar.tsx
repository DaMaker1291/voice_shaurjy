"use client";

import { useEffect, useRef, useState } from "react";

type AgentId = "SUPERVISOR" | "OS_AGENT" | "HAL_AGENT" | "WEB_AGENT";

interface AgentStatus {
  id: AgentId;
  label: string;
  color: string;
  glowColor: string;
  icon: string;
  state: "IDLE" | "ROUTING" | "EXECUTING" | "COMPLETED" | "ERROR";
  lastIntent?: string;
  latencyMs?: number;
  confidence?: number;
}

interface AgentStatusBarProps {
  routingData?: {
    target_agent?: string;
    routing?: {
      routing_confidence?: number;
      extracted_intent?: string;
    };
    latency_ms?: {
      supervisor?: number;
      worker?: number;
      total?: number;
    };
  } | null;
  isDispatching?: boolean;
}

const AGENT_CONFIG: Omit<AgentStatus, "state" | "lastIntent" | "latencyMs" | "confidence">[] = [
  { id: "SUPERVISOR", label: "Router", color: "#34d399", glowColor: "rgba(52,211,153,0.4)", icon: "⚡" },
  { id: "OS_AGENT", label: "OS Agent", color: "#f59e0b", glowColor: "rgba(245,158,11,0.4)", icon: "💻" },
  { id: "HAL_AGENT", label: "HAL Agent", color: "#22d3ee", glowColor: "rgba(34,211,238,0.4)", icon: "🔌" },
  { id: "WEB_AGENT", label: "Web Agent", color: "#a78bfa", glowColor: "rgba(167,139,250,0.4)", icon: "🌐" },
];

export default function AgentStatusBar({ routingData, isDispatching }: AgentStatusBarProps) {
  const [agents, setAgents] = useState<AgentStatus[]>(
    AGENT_CONFIG.map((a) => ({ ...a, state: "IDLE" }))
  );
  const prevDispatch = useRef(false);

  useEffect(() => {
    if (isDispatching && !prevDispatch.current) {
      // Supervisor fires immediately
      setAgents((prev) =>
        prev.map((a) =>
          a.id === "SUPERVISOR" ? { ...a, state: "ROUTING" } : { ...a, state: "IDLE" }
        )
      );
    }
    if (!isDispatching && prevDispatch.current && routingData) {
      const target = routingData.target_agent as AgentId | undefined;
      const confidence = routingData.routing?.routing_confidence;
      const intent = routingData.routing?.extracted_intent;
      const latencyMs = routingData.latency_ms;

      setAgents((prev) =>
        prev.map((a) => {
          if (a.id === "SUPERVISOR")
            return { ...a, state: "COMPLETED", latencyMs: latencyMs?.supervisor, confidence };
          if (a.id === target)
            return { ...a, state: "COMPLETED", lastIntent: intent, latencyMs: latencyMs?.worker };
          return { ...a, state: "IDLE" };
        })
      );

      // Reset to IDLE after 4 seconds
      const t = setTimeout(() => {
        setAgents((prev) => prev.map((a) => ({ ...a, state: "IDLE" })));
      }, 4000);
      return () => clearTimeout(t);
    }
    prevDispatch.current = !!isDispatching;
  }, [isDispatching, routingData]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "6px 12px",
        background: "rgba(3,5,18,0.85)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        backdropFilter: "blur(12px)",
        overflowX: "auto",
        flexShrink: 0,
      }}
    >
      {/* JARVIS label */}
      <span
        style={{
          fontSize: "10px",
          fontFamily: "monospace",
          color: "rgba(255,255,255,0.25)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          marginRight: "4px",
          whiteSpace: "nowrap",
        }}
      >
        COGNITIVE PIPELINE
      </span>

      <div style={{ width: "1px", height: "20px", background: "rgba(255,255,255,0.08)" }} />

      {agents.map((agent, i) => (
        <AgentPill key={agent.id} agent={agent} showArrow={i < agents.length - 1} />
      ))}

      {/* Total latency */}
      {routingData?.latency_ms?.total && (
        <span
          style={{
            marginLeft: "auto",
            fontSize: "9px",
            fontFamily: "monospace",
            color: "rgba(255,255,255,0.3)",
            whiteSpace: "nowrap",
          }}
        >
          {routingData.latency_ms.total}ms total
        </span>
      )}
    </div>
  );
}

function AgentPill({ agent, showArrow }: { agent: AgentStatus; showArrow: boolean }) {
  const isActive = agent.state === "ROUTING" || agent.state === "EXECUTING";
  const isCompleted = agent.state === "COMPLETED";
  const isError = agent.state === "ERROR";

  const stateColor = isError
    ? "#ef4444"
    : isCompleted
    ? agent.color
    : isActive
    ? agent.color
    : "rgba(255,255,255,0.2)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "5px",
          padding: "3px 8px",
          borderRadius: "20px",
          border: `1px solid ${stateColor}`,
          background: isActive || isCompleted
            ? `${agent.glowColor.replace("0.4", "0.12")}`
            : "transparent",
          boxShadow: isActive ? `0 0 10px ${agent.glowColor}` : "none",
          transition: "all 0.3s ease",
          position: "relative",
          overflow: "hidden",
          whiteSpace: "nowrap",
        }}
      >
        {/* Animated scan line for active state */}
        {isActive && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(90deg, transparent, ${agent.glowColor.replace("0.4", "0.3")}, transparent)`,
              animation: "scan-sweep 1.2s ease-in-out infinite",
              pointerEvents: "none",
            }}
          />
        )}

        <span style={{ fontSize: "10px" }}>{agent.icon}</span>
        <span
          style={{
            fontSize: "9px",
            fontFamily: "monospace",
            color: stateColor,
            letterSpacing: "0.05em",
          }}
        >
          {agent.label}
        </span>

        {/* State badge */}
        <span
          style={{
            fontSize: "7px",
            fontFamily: "monospace",
            color: stateColor,
            opacity: 0.8,
            letterSpacing: "0.05em",
          }}
        >
          [{isActive ? (agent.id === "SUPERVISOR" ? "ROUTING" : "EXEC") : isCompleted ? "DONE" : isError ? "ERR" : "IDLE"}]
        </span>

        {/* Confidence mini bar for supervisor */}
        {isCompleted && agent.id === "SUPERVISOR" && agent.confidence !== undefined && (
          <div
            style={{
              width: "24px",
              height: "3px",
              background: "rgba(255,255,255,0.1)",
              borderRadius: "2px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${agent.confidence * 100}%`,
                background: agent.color,
                borderRadius: "2px",
              }}
            />
          </div>
        )}

        {agent.latencyMs !== undefined && (
          <span style={{ fontSize: "7px", color: "rgba(255,255,255,0.3)", fontFamily: "monospace" }}>
            {agent.latencyMs}ms
          </span>
        )}
      </div>

      {showArrow && (
        <span style={{ fontSize: "8px", color: "rgba(255,255,255,0.15)" }}>→</span>
      )}
    </div>
  );
}
