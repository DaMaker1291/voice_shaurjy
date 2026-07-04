"use client";

import { useEffect, useRef, useState } from "react";

interface DeviceNode {
  id: string;
  name: string;
  status: "ACTIVE" | "STANDBY" | "CHARGING" | "OFFLINE" | "UNKNOWN" | "OPTIMAL" | "WARNING" | "CRITICAL";
  domain?: string;
  metrics?: string;
  controls?: string[];
  lastUpdated?: number;
}

interface TelemetryPacket {
  network_state?: {
    relay_status?: string;
    discovered_count?: number;
    last_scan_epoch?: number;
  };
  device_telemetry_payload?: {
    unique_id?: string;
    target_domain?: string;
    method_signature?: string;
    execution_payload?: Record<string, unknown>;
  };
  frontend_ui_mutation?: {
    target_node?: string;
    ui_status_flag?: string;
    troubleshooting_steps?: string[];
  };
  system_state_update?: {
    active_application?: string;
    execution_status?: string;
    error_detail?: string;
    telemetry?: { cpu_allocation?: string; ram_allocation?: string };
  };
  os_action_payload?: {
    action_type?: string;
    target_identifier?: string;
    payload_data?: {
      script_body?: string;
      keystrokes?: string;
    };
  };
}

interface CockpitTelemetryProps {
  relayOnline?: boolean;
  devices?: DeviceNode[];
  systemStats?: {
    cpu?: { percent: number };
    memory?: { percent: number; used_gb: number; total_gb: number };
    battery?: { percent: number; charging: boolean; present: boolean };
  } | null;
  agentResponse?: TelemetryPacket | null;
  activeAgent?: string | null;
  activityLog?: { ts: number; msg: string; type: "info" | "action" | "error" | "success" }[];
}

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "#34d399",
  OPTIMAL: "#34d399",
  ONLINE: "#34d399",
  STANDBY: "#f59e0b",
  WARNING: "#f59e0b",
  CHARGING: "#22d3ee",
  OFFLINE: "#ef4444",
  CRITICAL: "#ef4444",
  UNKNOWN: "#6b7280",
};

function ArcGauge({
  value,
  max = 100,
  color,
  label,
  sublabel,
}: {
  value: number;
  max?: number;
  color: string;
  label: string;
  sublabel?: string;
}) {
  const pct = Math.min(value / max, 1);
  const radius = 28;
  const circumference = Math.PI * radius; // half circle
  const strokeDash = circumference * pct;
  const size = 72;
  const cx = size / 2;
  const cy = size * 0.7;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "2px" }}>
      <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${cy}`} overflow="visible">
        {/* Track */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="5"
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${strokeDash} ${circumference}`}
          style={{ transition: "stroke-dasharray 0.8s ease", filter: `drop-shadow(0 0 4px ${color}88)` }}
        />
        {/* Value text */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fill={color}
          fontSize="13"
          fontFamily="monospace"
          fontWeight="bold"
        >
          {Math.round(value)}%
        </text>
      </svg>
      <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.4)", letterSpacing: "0.08em" }}>
        {label}
      </span>
      {sublabel && (
        <span style={{ fontSize: "8px", fontFamily: "monospace", color: "rgba(255,255,255,0.2)" }}>
          {sublabel}
        </span>
      )}
    </div>
  );
}

function DeviceCard({ device, onAction }: { device: DeviceNode; onAction?: (id: string, action: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const statusColor = STATUS_COLORS[device.status] ?? "#6b7280";
  const isOnline = !["OFFLINE", "UNKNOWN"].includes(device.status);

  return (
    <div
      style={{
        borderRadius: "12px",
        border: `1px solid ${isOnline ? "rgba(255,255,255,0.1)" : "rgba(239,68,68,0.25)"}`,
        background: isOnline ? "rgba(255,255,255,0.05)" : "rgba(239,68,68,0.08)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
        transition: "all 0.3s cubic-bezier(0.16,1,0.3,1)",
        overflow: "hidden",
      }}
    >
      {/* Header row */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 10px",
          cursor: "pointer",
        }}
      >
        {/* Status dot */}
        <div
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: statusColor,
            boxShadow: isOnline ? `0 0 6px ${statusColor}` : "none",
            flexShrink: 0,
            animation: device.status === "ACTIVE" ? "status-pulse 2s ease-in-out infinite" : "none",
          }}
        />

        {/* Domain badge */}
        {device.domain && (
          <span
            style={{
              fontSize: "7px",
              fontFamily: "monospace",
              color: "rgba(255,255,255,0.3)",
              background: "rgba(255,255,255,0.05)",
              padding: "1px 5px",
              borderRadius: "3px",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              flexShrink: 0,
            }}
          >
            {device.domain}
          </span>
        )}

        <span
          style={{
            flex: 1,
            fontSize: "11px",
            fontFamily: "monospace",
            color: "rgba(255,255,255,0.75)",
            fontWeight: 600,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {device.name.toUpperCase()}
        </span>

        <span
          style={{
            fontSize: "9px",
            fontFamily: "monospace",
            color: statusColor,
            letterSpacing: "0.04em",
          }}
        >
          [{device.status}]
        </span>

        <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.2)" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div
          style={{
            padding: "0 10px 10px",
            borderTop: "1px solid rgba(255,255,255,0.04)",
          }}
        >
          {device.metrics && (
            <p
              style={{
                fontSize: "10px",
                fontFamily: "monospace",
                color: "rgba(255,255,255,0.35)",
                margin: "6px 0",
              }}
            >
              ├── {device.metrics}
            </p>
          )}

          {device.controls && device.controls.length > 0 && (
            <div>
              <p style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.2)", margin: "4px 0" }}>
                └── Actions:
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", paddingLeft: "8px" }}>
                {device.controls.map((ctrl) => (
                  <button
                    key={ctrl}
                    onClick={() => onAction?.(device.id, ctrl)}
                    style={{
                      padding: "3px 8px",
                      fontSize: "9px",
                      fontFamily: "monospace",
                      borderRadius: "4px",
                      border: "1px solid rgba(255,255,255,0.1)",
                      background: "rgba(255,255,255,0.04)",
                      color: "rgba(255,255,255,0.5)",
                      cursor: "pointer",
                      transition: "all 0.15s",
                    }}
                    onMouseEnter={(e) => {
                      (e.target as HTMLButtonElement).style.background = "rgba(52,211,153,0.1)";
                      (e.target as HTMLButtonElement).style.borderColor = "rgba(52,211,153,0.3)";
                      (e.target as HTMLButtonElement).style.color = "#34d399";
                    }}
                    onMouseLeave={(e) => {
                      (e.target as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)";
                      (e.target as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.1)";
                      (e.target as HTMLButtonElement).style.color = "rgba(255,255,255,0.5)";
                    }}
                  >
                    {ctrl}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Offline troubleshooting */}
          {!isOnline && (
            <div
              style={{
                marginTop: "6px",
                padding: "6px 8px",
                background: "rgba(239,68,68,0.06)",
                borderRadius: "4px",
                border: "1px solid rgba(239,68,68,0.15)",
              }}
            >
              <p style={{ fontSize: "9px", fontFamily: "monospace", color: "#f87171", margin: "0 0 4px" }}>
                ⚠ DEVICE UNREACHABLE
              </p>
              <p style={{ fontSize: "8px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)", margin: 0 }}>
                1. Verify device is powered and on-network
              </p>
              <p style={{ fontSize: "8px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)", margin: 0 }}>
                2. Check relay bridge connection
              </p>
              <p style={{ fontSize: "8px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)", margin: 0 }}>
                3. Run: JARVIS, rescan my network
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PlatformStats() {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const base = typeof window !== "undefined"
          ? (localStorage.getItem("backend_url") || "https://dgfhgjhj-jarvis-ai-brain.hf.space")
          : "";
        const [lat, vault, healing, grammar] = await Promise.allSettled([
          fetch(`${base}/api/platform/latency`).then(r => r.json()),
          fetch(`${base}/api/platform/vault`).then(r => r.json()),
          fetch(`${base}/api/platform/healing`).then(r => r.json()),
          fetch(`${base}/api/platform/grammars`).then(r => r.json()),
        ]);
        setStats({
          latency: lat.status === "fulfilled" ? lat.value : null,
          vault: vault.status === "fulfilled" ? vault.value : null,
          healing: healing.status === "fulfilled" ? healing.value : null,
          grammars: grammar.status === "fulfilled" ? grammar.value : null,
        });
      } catch {}
    };
    load();
    const i = setInterval(load, 8000);
    return () => clearInterval(i);
  }, []);

  if (!stats) return null;

  const sup = stats.latency?.supervisor || {};

  return (
    <div
      style={{
        padding: "8px 10px",
        background: "rgba(0,0,0,0.2)",
        borderRadius: "8px",
        border: "1px solid rgba(139,92,246,0.15)",
        flexShrink: 0,
      }}
    >
      <div style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.35)", letterSpacing: "0.08em", marginBottom: "6px" }}>
        PLATFORM
      </div>

      {/* Latency */}
      {sup && (
        <div style={{ display: "flex", gap: "12px", marginBottom: "4px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>
            Route: <span style={{ color: sup.current > 50 ? "#f59e0b" : "#34d399" }}>{sup.current || 0}ms</span>
          </span>
          <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
            P50: {sup.p50 || 0}ms
          </span>
          <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
            P95: <span style={{ color: sup.p95 > 50 ? "#f59e0b" : "#34d399" }}>{sup.p95 || 0}ms</span>
          </span>
          {stats.latency?.sla_violations > 0 && (
            <span style={{ fontSize: "9px", fontFamily: "monospace", color: "#f87171" }}>
              SLA breaks: {stats.latency.sla_violations}
            </span>
          )}
        </div>
      )}

      {/* Vault + Healing + Grammars */}
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
          Vault: <span style={{ color: "#22d3ee" }}>{stats.vault?.method || "—"}</span>
        </span>
        <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
          Tools: <span style={{ color: "#a78bfa" }}>{stats.healing?.total_tools || 0}</span>
        </span>
        <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
          Heals: <span style={{ color: stats.healing?.successful_heals > 0 ? "#34d399" : "rgba(255,255,255,0.3)" }}>{stats.healing?.successful_heals || 0}/{stats.healing?.total_attempts || 0}</span>
        </span>
        <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)" }}>
          Grammars: <span style={{ color: "#fbbf24" }}>{stats.grammars?.count || 0}</span>
        </span>
      </div>
    </div>
  );
}

export default function CockpitTelemetry({
  relayOnline = false,
  devices = [],
  systemStats,
  agentResponse,
  activeAgent,
  activityLog = [],
}: CockpitTelemetryProps) {
  const logEndRef = useRef<HTMLDivElement>(null);
  const [scanLine, setScanLine] = useState(0);

  // Animate scan line
  useEffect(() => {
    const interval = setInterval(() => {
      setScanLine((p) => (p + 1) % 100);
    }, 40);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activityLog]);

  const halResponse = agentResponse as TelemetryPacket | null;
  const networkState = halResponse?.network_state;
  const mutation = halResponse?.frontend_ui_mutation;
  const osState = halResponse?.system_state_update;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        gap: "8px",
        position: "relative",
      }}
    >
      {/* Relay status banner */}
      <div
        style={{
          padding: "12px 16px",
          borderRadius: "12px",
          border: `1px solid ${relayOnline ? "rgba(52,211,153,0.3)" : "rgba(239,68,68,0.4)"}`,
          background: relayOnline ? "rgba(52,211,153,0.08)" : "rgba(239,68,68,0.1)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          boxShadow: relayOnline ? "0 4px 20px rgba(52,211,153,0.1)" : "0 4px 20px rgba(239,68,68,0.15)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Scan line effect */}
        <div
          style={{
            position: "absolute",
            top: `${scanLine}%`,
            left: 0,
            right: 0,
            height: "1px",
            background: relayOnline
              ? "rgba(52,211,153,0.15)"
              : "rgba(239,68,68,0.1)",
            pointerEvents: "none",
            transition: "top 0.04s linear",
          }}
        />

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: relayOnline ? "#34d399" : "#ef4444",
              boxShadow: relayOnline ? "0 0 8px #34d399" : "0 0 8px #ef4444",
              animation: "status-pulse 2s ease-in-out infinite",
            }}
          />
          <span
            style={{
              fontSize: "10px",
              fontFamily: "monospace",
              color: relayOnline ? "#34d399" : "#ef4444",
              letterSpacing: "0.08em",
            }}
          >
            RELAY BRIDGE: {relayOnline ? "ONLINE" : "OFFLINE"}
          </span>
          {networkState && (
            <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.25)" }}>
              · {networkState.discovered_count ?? 0} devices
            </span>
          )}
        </div>

        {activeAgent && (
          <span
            style={{
              fontSize: "9px",
              fontFamily: "monospace",
              color: "rgba(255,255,255,0.3)",
              letterSpacing: "0.06em",
            }}
          >
            ACTIVE: {activeAgent}
          </span>
        )}
      </div>

      {/* System gauges */}
      {systemStats && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-around",
            padding: "14px 10px",
            background: "rgba(10,12,25,0.6)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            borderRadius: "12px",
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "inset 0 0 20px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)",
            flexShrink: 0,
          }}
        >
          {systemStats.cpu && (
            <ArcGauge
              value={systemStats.cpu.percent}
              color={systemStats.cpu.percent > 80 ? "#ef4444" : systemStats.cpu.percent > 60 ? "#f59e0b" : "#34d399"}
              label="CPU"
            />
          )}
          {systemStats.memory && (
            <ArcGauge
              value={systemStats.memory.percent}
              color={systemStats.memory.percent > 80 ? "#ef4444" : systemStats.memory.percent > 60 ? "#f59e0b" : "#22d3ee"}
              label="RAM"
              sublabel={`${systemStats.memory.used_gb.toFixed(1)}/${systemStats.memory.total_gb.toFixed(0)}GB`}
            />
          )}
          {systemStats.battery?.present && (
            <ArcGauge
              value={systemStats.battery.percent}
              color={systemStats.battery.percent < 20 ? "#ef4444" : systemStats.battery.charging ? "#34d399" : "#f59e0b"}
              label={systemStats.battery.charging ? "BAT ⚡" : "BAT"}
              sublabel={systemStats.battery.charging ? "Charging" : undefined}
            />
          )}
        </div>
      )}

      {/* OS agent state */}
      {osState && (
        <div
          style={{
            padding: "8px 10px",
            background: "rgba(0,0,0,0.2)",
            borderRadius: "8px",
            border: `1px solid ${osState.execution_status === "COMPLETED" ? "rgba(52,211,153,0.15)" : osState.execution_status === "CRITICAL_ERROR" ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.15)"}`,
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "4px" }}>
            <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.35)", letterSpacing: "0.08em" }}>
              OS AGENT
            </span>
            <span
              style={{
                fontSize: "9px",
                fontFamily: "monospace",
                color: osState.execution_status === "COMPLETED" ? "#34d399" : osState.execution_status === "CRITICAL_ERROR" ? "#ef4444" : "#f59e0b",
              }}
            >
              [{osState.execution_status}]
            </span>
          </div>
          {osState.active_application && (
            <p style={{ fontSize: "10px", fontFamily: "monospace", color: "rgba(255,255,255,0.5)", margin: "2px 0" }}>
              ├── App: {osState.active_application}
            </p>
          )}
          {osState.telemetry?.cpu_allocation && (
            <p style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)", margin: "2px 0" }}>
              └── CPU: {osState.telemetry.cpu_allocation} · RAM: {osState.telemetry.ram_allocation}
            </p>
          )}
          {osState.error_detail && (
            <p style={{ fontSize: "9px", fontFamily: "monospace", color: "#f87171", margin: "4px 0 0" }}>
              ⚠ {osState.error_detail}
            </p>
          )}
        </div>
      )}

      {/* Platform Stats — Latency, Vault, Healing */}
      <PlatformStats />

      {/* Device tree */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          minHeight: 0,
        }}
      >
        {devices.length === 0 ? (
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
            <span style={{ fontSize: "20px" }}>📡</span>
            <span style={{ fontSize: "10px", fontFamily: "monospace", color: "rgba(255,255,255,0.5)" }}>
              {relayOnline ? "Scanning network..." : "Relay offline — no devices"}
            </span>
          </div>
        ) : (
          devices.map((device) => <DeviceCard key={device.id} device={device} />)
        )}
      </div>

      {/* Activity log */}
      {activityLog.length > 0 && (
        <div
          style={{
            maxHeight: "100px",
            overflow: "auto",
            padding: "6px 8px",
            background: "rgba(0,0,0,0.3)",
            borderRadius: "6px",
            border: "1px solid rgba(255,255,255,0.04)",
            flexShrink: 0,
          }}
        >
          {activityLog.slice(-8).map((entry, i) => (
            <div key={i} style={{ display: "flex", gap: "6px", alignItems: "flex-start", marginBottom: "2px" }}>
              <span style={{ fontSize: "8px", fontFamily: "monospace", color: "rgba(255,255,255,0.2)", flexShrink: 0 }}>
                {new Date(entry.ts).toLocaleTimeString("en-GB", { hour12: false })}
              </span>
              <span
                style={{
                  fontSize: "9px",
                  fontFamily: "monospace",
                  color:
                    entry.type === "error" ? "#f87171" :
                    entry.type === "success" ? "#34d399" :
                    entry.type === "action" ? "#f59e0b" :
                    "rgba(255,255,255,0.4)",
                }}
              >
                {entry.msg}
              </span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}
