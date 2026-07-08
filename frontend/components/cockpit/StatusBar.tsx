"use client";

import { useEffect, useState } from "react";

interface SystemStatus {
  tier: string;
  ram_percent: number;
  ram_available_mb: number;
  cpu_percent: number;
  agents_paused: boolean;
  warnings: { level: string; message: string }[];
}

export default function StatusBar() {
  const [relay, setRelay] = useState(false);
  const [agents, setAgents] = useState(0);
  const [devices, setDevices] = useState(0);
  const [sys, setSys] = useState<SystemStatus | null>(null);
  const [deviceInfo, setDeviceInfo] = useState<{ platform?: string; hostname?: string }>({});

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await window.fetch("/api/health");
        const data = await res.json();
        setRelay(!!data.relay);
      } catch {}
      try {
        const res = await window.fetch("/api/autonomous/tasks");
        const data = await res.json();
        setAgents((data.tasks || []).filter((t: any) => t.status === "running").length);
      } catch {}
      try {
        const res = await window.fetch("/api/relay/devices?user_id=local");
        const data = await res.json();
        const devs = data.devices || [];
        setDevices(devs.length);
        if (devs.length > 0 && devs[0].platform) {
          setDeviceInfo({ platform: devs[0].platform, hostname: devs[0].hostname });
        }
      } catch {}
      try {
        const res = await window.fetch("/api/system/status");
        const data = await res.json();
        setSys(data);
      } catch {}
    };
    poll();
    const i = setInterval(poll, 6000);
    return () => clearInterval(i);
  }, []);

  const tierColors: Record<string, string> = {
    potato: "#FF3333", low: "#FFB300", mid: "#00B4D8", high: "#00FF66", ultra: "#A855F7",
  };

  const hasDanger = sys?.warnings?.some(w => w.level === "danger");

  return (
    <div style={{
      height: 22, background: "#08090c", borderTop: "1px solid #1a1d23",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 12px", fontFamily: "var(--font-mono)", fontSize: 8,
      color: "var(--text-muted)", flexShrink: 0, letterSpacing: "0.04em",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* Relay Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: relay ? "#00FF66" : "#FF3333", boxShadow: `0 0 4px ${relay ? "rgba(0,255,102,0.4)" : "rgba(255,51,51,0.4)"}` }} />
          <span style={{ color: relay ? "#00FF66" : "#FF3333" }}>RELAY {relay ? "ONLINE" : "OFFLINE"}</span>
          {relay && deviceInfo.platform && (
            <span style={{ color: "#667085" }}>{deviceInfo.platform}</span>
          )}
        </div>

        {/* Agent Count */}
        {agents > 0 && (
          <span style={{ color: "#FFB300" }}>{agents} AGENT{agents > 1 ? "S" : ""}</span>
        )}

        {/* Devices */}
        {devices > 0 && (
          <span>{devices} DEV</span>
        )}

        {/* Agents Paused Warning */}
        {sys?.agents_paused && (
          <span style={{ color: "#FFB300", animation: "glow-pulse 1s ease-in-out infinite" }}>PAUSED</span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* System Tier */}
        {sys?.tier && (
          <span style={{ color: tierColors[sys.tier] || "#667085", fontWeight: 600 }}>
            {sys.tier.toUpperCase()}
          </span>
        )}

        {/* RAM */}
        {sys?.ram_percent !== undefined && (
          <span style={{ color: sys.ram_percent > 85 ? "#FF3333" : sys.ram_percent > 70 ? "#FFB300" : "#667085" }}>
            RAM {Math.round(sys.ram_percent)}%
          </span>
        )}

        {/* CPU */}
        {sys?.cpu_percent !== undefined && (
          <span style={{ color: sys.cpu_percent > 90 ? "#FF3333" : sys.cpu_percent > 70 ? "#FFB300" : "#667085" }}>
            CPU {Math.round(sys.cpu_percent)}%
          </span>
        )}

        {/* Danger indicator */}
        {hasDanger && (
          <span style={{ color: "#FF3333", animation: "glow-pulse 0.8s ease-in-out infinite" }}>⚠ HIGH LOAD</span>
        )}

        <span>GROQ</span>
        <span style={{ color: "#00FF66" }}>JARVIS v3.0</span>
      </div>
    </div>
  );
}
