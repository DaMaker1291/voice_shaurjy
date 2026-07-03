"use client";

import { useEffect, useRef, useState } from "react";

interface RoutingPacket {
  target_agent: "OS_AGENT" | "HAL_AGENT" | "WEB_AGENT";
  routing_confidence: number;
  extracted_intent: string;
  execution_context: {
    primary_targets: string[];
    actionable_variables: Record<string, string>;
    downstream_dependencies: string[];
  };
}

interface AgentRouterProps {
  routingData?: {
    routing?: any;
    agent_response?: Record<string, unknown>;
    latency_ms?: { supervisor?: number; worker?: number; total?: number };
    target_agent?: string;
    model_source?: string;
    security_status?: string;
  } | null;
  isDispatching?: boolean;
  userText?: string;
}

const AGENT_META = {
  OS_AGENT: { label: "OS Agent", color: "#f59e0b", bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.3)", icon: "💻", desc: "Desktop & App Automation" },
  HAL_AGENT: { label: "HAL Agent", color: "#22d3ee", bg: "rgba(34,211,238,0.08)", border: "rgba(34,211,238,0.3)", icon: "🔌", desc: "Hardware Abstraction Layer" },
  WEB_AGENT: { label: "Web Agent", color: "#a78bfa", bg: "rgba(167,139,250,0.08)", border: "rgba(167,139,250,0.3)", icon: "🌐", desc: "Autonomous Web Operations" },
};

function JsonToken({ value }: { value: unknown }): JSX.Element {
  if (value === null) return <span style={{ color: "#94a3b8" }}>null</span>;
  if (typeof value === "boolean") return <span style={{ color: "#f59e0b" }}>{String(value)}</span>;
  if (typeof value === "number") return <span style={{ color: "#34d399" }}>{value}</span>;
  if (typeof value === "string") return <span style={{ color: "#86efac" }}>"{value}"</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span style={{ color: "#94a3b8" }}>[]</span>;
    return (
      <span>
        {"["}
        {value.map((v, i) => (
          <span key={i}>
            <JsonToken value={v} />
            {i < value.length - 1 && <span style={{ color: "#94a3b8" }}>, </span>}
          </span>
        ))}
        {"]"}
      </span>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span style={{ color: "#94a3b8" }}>{"{}"}</span>;
    return (
      <span>
        {"{"}
        {entries.map(([k, v], i) => (
          <span key={k}>
            <span style={{ color: "#93c5fd" }}>"{k}"</span>
            <span style={{ color: "#94a3b8" }}>: </span>
            <JsonToken value={v} />
            {i < entries.length - 1 && <span style={{ color: "#94a3b8" }}>, </span>}
          </span>
        ))}
        {"}"}
      </span>
    );
  }
  return <span style={{ color: "#94a3b8" }}>{String(value)}</span>;
}

function JsonTree({ data, depth = 0 }: { data: Record<string, unknown>; depth?: number }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const indent = depth * 16;

  return (
    <div style={{ fontFamily: "monospace", fontSize: "11px", lineHeight: "1.8" }}>
      {Object.entries(data).map(([key, value]) => {
        const isObj = value !== null && typeof value === "object" && !Array.isArray(value);
        const isCollapsed = collapsed.has(key);

        return (
          <div key={key} style={{ marginLeft: `${indent}px` }}>
            <span
              style={{
                color: "#93c5fd",
                cursor: isObj ? "pointer" : "default",
                userSelect: "none",
              }}
              onClick={() => {
                if (!isObj) return;
                setCollapsed((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                });
              }}
            >
              {isObj && (
                <span style={{ color: "#4b5563", marginRight: "4px", fontSize: "9px" }}>
                  {isCollapsed ? "▶" : "▼"}
                </span>
              )}
              <span style={{ color: "#60a5fa" }}>"{key}"</span>
            </span>
            <span style={{ color: "#4b5563" }}>: </span>
            {isObj && !isCollapsed ? (
              <JsonTree data={value as Record<string, unknown>} depth={depth + 1} />
            ) : (
              <JsonToken value={isObj && isCollapsed ? "{...}" : value} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function AgentRouter({ routingData, isDispatching, userText }: AgentRouterProps) {
  const [displayedJson, setDisplayedJson] = useState<Record<string, unknown> | null>(null);
  const [activeTab, setActiveTab] = useState<"routing" | "response">("routing");
  const [animPhase, setAnimPhase] = useState<"idle" | "routing" | "executing" | "done">("idle");
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isDispatching) {
      setAnimPhase("routing");
      setDisplayedJson(null);
    } else if (routingData) {
      setAnimPhase("executing");
      setTimeout(() => {
        setAnimPhase("done");
        setDisplayedJson(
          activeTab === "routing"
            ? (routingData.routing as any ?? null)
            : (routingData.agent_response as any ?? null)
        );
      }, 400);
    } else {
      setAnimPhase("idle");
    }

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isDispatching, routingData, activeTab]);

  useEffect(() => {
    if (!routingData) return;
    setDisplayedJson(
      activeTab === "routing"
        ? (routingData.routing as any ?? null)
        : (routingData.agent_response as any ?? null)
    );
  }, [activeTab, routingData]);


  const targetAgent = routingData?.target_agent as keyof typeof AGENT_META | undefined;
  const meta = targetAgent ? AGENT_META[targetAgent] : null;
  const confidence = routingData?.routing?.routing_confidence ?? 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "rgba(3,5,18,0.7)",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: "12px",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <div
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: animPhase === "done" ? "#34d399" : animPhase === "idle" ? "#374151" : "#f59e0b",
              boxShadow: animPhase !== "idle" ? `0 0 8px ${animPhase === "done" ? "#34d399" : "#f59e0b"}` : "none",
              transition: "all 0.3s",
            }}
          />
          <span style={{ fontSize: "11px", fontFamily: "monospace", color: "rgba(255,255,255,0.6)", letterSpacing: "0.08em" }}>
            COGNITIVE ROUTER
          </span>

          {routingData?.model_source && (
            <span
              style={{
                fontSize: "8px",
                fontFamily: "monospace",
                color: routingData.model_source === "LOCAL_LLAMA" ? "#34d399" : "#a78bfa",
                background: routingData.model_source === "LOCAL_LLAMA" ? "rgba(52,211,153,0.1)" : "rgba(167,139,250,0.1)",
                border: `1px solid ${routingData.model_source === "LOCAL_LLAMA" ? "rgba(52,211,153,0.2)" : "rgba(167,139,250,0.2)"}`,
                padding: "1px 5px",
                borderRadius: "3px",
                letterSpacing: "0.05em",
              }}
            >
              {routingData.model_source}
            </span>
          )}

          {routingData?.security_status && (
            <span
              style={{
                fontSize: "8px",
                fontFamily: "monospace",
                color: routingData.security_status === "PASSED" ? "#34d399" : "#ef4444",
                background: routingData.security_status === "PASSED" ? "rgba(52,211,153,0.1)" : "rgba(239,68,68,0.15)",
                border: `1px solid ${routingData.security_status === "PASSED" ? "rgba(52,211,153,0.2)" : "rgba(239,68,68,0.25)"}`,
                padding: "1px 5px",
                borderRadius: "3px",
                letterSpacing: "0.05em",
              }}
            >
              SEC: {routingData.security_status}
            </span>
          )}
        </div>


        {/* Tab switcher */}
        <div style={{ display: "flex", gap: "4px" }}>
          {(["routing", "response"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: "2px 8px",
                fontSize: "9px",
                fontFamily: "monospace",
                borderRadius: "4px",
                border: "1px solid",
                borderColor: activeTab === tab ? "rgba(255,255,255,0.2)" : "transparent",
                background: activeTab === tab ? "rgba(255,255,255,0.06)" : "transparent",
                color: activeTab === tab ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.3)",
                cursor: "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Routing flow diagram */}
      <div
        style={{
          padding: "12px 14px",
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          flexShrink: 0,
        }}
      >
        <RoutingFlowDiagram
          animPhase={animPhase}
          targetAgent={targetAgent}
          confidence={confidence}
          userText={userText}
          meta={meta}
        />
      </div>

      {/* JSON telemetry stream */}
      <div style={{ flex: 1, overflow: "auto", padding: "10px 14px" }}>
        {animPhase === "routing" && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 0" }}>
            <SkeletonLoader />
          </div>
        )}

        {animPhase === "idle" && !displayedJson && (
          <div
            style={{
              height: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              opacity: 0.3,
            }}
          >
            <span style={{ fontSize: "24px" }}>⚡</span>
            <span style={{ fontSize: "10px", fontFamily: "monospace", color: "rgba(255,255,255,0.5)" }}>
              Awaiting intent...
            </span>
          </div>
        )}

        {displayedJson && animPhase === "done" && (
          <div
            style={{
              animation: "fadeInUp 0.3s ease",
              background: "rgba(0,0,0,0.3)",
              borderRadius: "6px",
              padding: "10px",
            }}
          >
            <JsonTree data={displayedJson} />
          </div>
        )}
      </div>
    </div>
  );
}

function RoutingFlowDiagram({
  animPhase,
  targetAgent,
  confidence,
  userText,
  meta,
}: {
  animPhase: string;
  targetAgent?: string;
  confidence: number;
  userText?: string;
  meta: (typeof AGENT_META)[keyof typeof AGENT_META] | null;
}) {
  const nodes = [
    { id: "input", label: "USER INPUT", color: "#94a3b8", glow: "rgba(148,163,184,0.3)" },
    { id: "supervisor", label: "SUPERVISOR", color: "#34d399", glow: "rgba(52,211,153,0.3)" },
    { id: "worker", label: targetAgent ? (meta?.label ?? targetAgent).toUpperCase() : "WORKER", color: meta?.color ?? "#6b7280", glow: meta ? meta.bg : "rgba(107,114,128,0.3)" },
  ];

  const isActive = animPhase === "routing" || animPhase === "executing";
  const isDone = animPhase === "done";

  return (
    <div style={{ position: "relative" }}>
      {/* Intent text */}
      {userText && (
        <div
          style={{
            fontSize: "10px",
            fontFamily: "monospace",
            color: "rgba(255,255,255,0.4)",
            marginBottom: "10px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          <span style={{ color: "rgba(255,255,255,0.2)" }}>› </span>
          {userText.slice(0, 80)}
        </div>
      )}

      {/* Node flow */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {nodes.map((node, i) => (
          <div key={node.id} style={{ display: "flex", alignItems: "center", gap: "6px", flex: 1 }}>
            <div
              style={{
                flex: 1,
                padding: "6px 8px",
                borderRadius: "6px",
                border: `1px solid ${isDone || (isActive && i <= 1) ? node.color : "rgba(255,255,255,0.08)"}`,
                background: isDone || (isActive && i <= 1) ? `${node.glow}` : "rgba(0,0,0,0.2)",
                boxShadow: isDone && i === 2 && meta ? `0 0 12px ${meta.color}55` : "none",
                transition: "all 0.4s ease",
                textAlign: "center",
              }}
            >
              <div
                style={{
                  fontSize: "9px",
                  fontFamily: "monospace",
                  color: isDone || (isActive && i <= 1) ? node.color : "rgba(255,255,255,0.2)",
                  letterSpacing: "0.06em",
                  transition: "color 0.4s",
                }}
              >
                {i === 2 && meta ? meta.icon + " " : ""}{node.label}
              </div>
            </div>

            {i < nodes.length - 1 && (
              <div style={{ position: "relative", width: "20px", flexShrink: 0 }}>
                <svg width="20" height="12" viewBox="0 0 20 12">
                  <line
                    x1="0" y1="6" x2="20" y2="6"
                    stroke={isDone || (isActive && i === 0) ? "#34d399" : "rgba(255,255,255,0.1)"}
                    strokeWidth="1"
                    strokeDasharray={isActive && i === 0 ? "3 2" : "none"}
                    style={{ transition: "stroke 0.4s" }}
                  />
                  <polygon points="14,3 20,6 14,9" fill={isDone || (isActive && i === 0) ? "#34d399" : "rgba(255,255,255,0.1)"} style={{ transition: "fill 0.4s" }} />
                </svg>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Confidence arc */}
      {isDone && confidence > 0 && (
        <div style={{ marginTop: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
            CONFIDENCE
          </span>
          <div
            style={{
              flex: 1,
              height: "3px",
              background: "rgba(255,255,255,0.06)",
              borderRadius: "2px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${confidence * 100}%`,
                background: confidence > 0.8 ? "#34d399" : confidence > 0.5 ? "#f59e0b" : "#ef4444",
                borderRadius: "2px",
                transition: "width 0.6s ease",
              }}
            />
          </div>
          <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>
            {Math.round(confidence * 100)}%
          </span>
        </div>
      )}
    </div>
  );
}

function SkeletonLoader() {
  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "6px" }}>
      {[100, 75, 90, 60].map((w, i) => (
        <div
          key={i}
          style={{
            height: "10px",
            width: `${w}%`,
            background: "rgba(255,255,255,0.04)",
            borderRadius: "4px",
            animation: "skeleton-pulse 1.4s ease-in-out infinite",
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
    </div>
  );
}
