"use client";

import { useEffect, useState } from "react";
import { useIsMobile } from "@/hooks/useIsMobile";
import { BASE } from "@/lib/api";
import dynamic from "next/dynamic";

const WakeWordIndicator = dynamic(() => import("./WakeWordIndicator"), { ssr: false });

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

interface SystemStatus {
  tier: string;
  ram_percent: number;
  ram_available_mb: number;
  cpu_percent: number;
  agents_paused: boolean;
  warnings: { level: string; message: string }[];
}

interface CurrentDevice {
  hostname: string;
  platform: string;
  os: string;
  os_icon: string;
  version: string;
  username: string;
  ram_gb: number | null;
  cpu_cores: number | null;
  app_count: number;
  last_seen: number;
}

export default function StatusBar() {
  const isMobile = useIsMobile();
  const [relay, setRelay] = useState(false);
  const [agents, setAgents] = useState(0);
  const [devices, setDevices] = useState(0);
  const [sys, setSys] = useState<SystemStatus | null>(null);
  const [device, setDevice] = useState<CurrentDevice | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await window.fetch(`${BASE}/api/health`);
        const data = await safeJson(res);
        setRelay(!!data.relay);
      } catch {}
      try {
        const res = await window.fetch(`${BASE}/api/autonomous/tasks`);
        const data = await safeJson(res);
        setAgents((data.tasks || []).filter((t: any) => t.status === "running").length);
      } catch {}
      try {
        const res = await window.fetch(`${BASE}/api/relay/devices?user_id=local`);
        const data = await safeJson(res);
        setDevices((data.devices || []).length);
      } catch {}
      try {
        const res = await window.fetch(`${BASE}/api/device/current?user_id=local`);
        const data = await safeJson(res);
        if (data.hostname) setDevice(data);
      } catch {}
      try {
        const res = await window.fetch(`${BASE}/api/system/status`);
        const data = await safeJson(res);
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

  const deviceRecentlyActive = device && device.last_seen > 0 && (Date.now() / 1000 - device.last_seen) < 120;
  const showRelayOnline = relay || deviceRecentlyActive;

  return (
    <div style={{
      height: isMobile ? 28 : 22, background: "#08090c", borderTop: "1px solid #1a1d23",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: isMobile ? "0 8px" : "0 12px", fontFamily: "var(--font-mono)", fontSize: isMobile ? 7 : 8,
      color: "var(--text-muted)", flexShrink: 0, letterSpacing: "0.04em",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 6 : 12 }}>
        {!isMobile && <WakeWordIndicator />}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: showRelayOnline ? "#00FF66" : "#FF3333", boxShadow: `0 0 4px ${showRelayOnline ? "rgba(0,255,102,0.4)" : "rgba(255,51,51,0.4)"}` }} />
          <span style={{ color: showRelayOnline ? "#00FF66" : "#FF3333" }}>
            {showRelayOnline ? (isMobile ? "ONLINE" : "RELAY ONLINE") : (isMobile ? "OFFLINE" : "RELAY OFFLINE")}
          </span>
        </div>

        {!isMobile && device && device.hostname && (
          <div style={{ display: "flex", alignItems: "center", gap: 3, padding: "0 6px", border: "1px solid #1a1d23", borderRadius: 3 }}>
            <span>{device.os_icon}</span>
            <span style={{ color: "#00B4D8" }}>{device.hostname}</span>
            <span style={{ color: "#667085" }}>{device.os}</span>
            {device.app_count > 0 && (
              <span style={{ color: "#667085" }}>{device.app_count} apps</span>
            )}
          </div>
        )}

        {agents > 0 && (
          <span style={{ color: "#FFB300" }}>{agents} AGENT{agents > 1 ? "S" : ""}</span>
        )}

        {devices > 0 && !isMobile && (
          <span>{devices} DEV</span>
        )}

        {sys?.agents_paused && (
          <span style={{ color: "#FFB300", animation: "glow-pulse 1s ease-in-out infinite" }}>PAUSED</span>
        )}
      </div>

      {!isMobile && (
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {sys?.tier && (
            <span style={{ color: tierColors[sys.tier] || "#667085", fontWeight: 600 }}>
              {sys.tier.toUpperCase()}
            </span>
          )}
          {sys?.ram_percent !== undefined && (
            <span style={{ color: sys.ram_percent > 85 ? "#FF3333" : sys.ram_percent > 70 ? "#FFB300" : "#667085" }}>
              RAM {Math.round(sys.ram_percent)}%
            </span>
          )}
          {sys?.cpu_percent !== undefined && (
            <span style={{ color: sys.cpu_percent > 90 ? "#FF3333" : sys.cpu_percent > 70 ? "#FFB300" : "#667085" }}>
              CPU {Math.round(sys.cpu_percent)}%
            </span>
          )}
          {hasDanger && (
            <span style={{ color: "#FF3333", animation: "glow-pulse 0.8s ease-in-out infinite" }}>⚠ HIGH LOAD</span>
          )}
          <span>GROQ</span>
          <span style={{ color: "#00FF66" }}>JARVIS v3.0</span>
        </div>
      )}
    </div>
  );
}
