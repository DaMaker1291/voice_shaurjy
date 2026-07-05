"use client";

import { useEffect, useState } from "react";

interface SystemStatus {
  network: string;
  supervisorMs: number;
  model: string;
  vaultStatus: string;
  sandboxStatus: string;
  uptime: string;
}

export default function TopBar() {
  const [status, setStatus] = useState<SystemStatus>({
    network: "OPTIMAL",
    supervisorMs: 0,
    model: "CLOUD_GROQ",
    vaultStatus: "SECURE",
    sandboxStatus: "AIRGAPPED",
    uptime: "00:00:00",
  });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
      setTick(t => t + 1);
      const elapsed = Math.floor((Date.now() - start) / 1000);
      const h = String(Math.floor(elapsed / 3600)).padStart(2, "0");
      const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
      const s = String(elapsed % 60).padStart(2, "0");
      setStatus(p => ({ ...p, uptime: `${h}:${m}:${s}` }));
    }, 1000);

    const fetchStatus = async () => {
      try {
        const res = await fetch("/api/health");
        const data = await res.json();
        setStatus(p => ({
          ...p,
          network: data.relay ? "OPTIMAL" : "STANDBY",
          model: data.models?.llm || "CLOUD_GROQ",
        }));
      } catch {}
    };
    fetchStatus();
    const statusInterval = setInterval(fetchStatus, 10000);

    return () => { clearInterval(interval); clearInterval(statusInterval); };
  }, []);

  const Item = ({ label, value, color = "var(--text-muted)" }: { label: string; value: string; color?: string }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>{label}</span>
      <span style={{ fontSize: 10, color, fontFamily: "var(--font-mono)", fontWeight: 500 }}>{value}</span>
    </div>
  );

  return (
    <header style={{ height: 32, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 8px rgba(0,255,102,0.4)", animation: "glow-pulse 2s ease-in-out infinite" }} />
          <span style={{ fontSize: 10, color: "var(--neon-green)", fontWeight: 600, letterSpacing: "0.08em" }}>SYSTEM_SECURE</span>
        </div>
        <div style={{ width: 1, height: 14, background: "var(--border)" }} />
        <Item label="NET" value={status.network} color="var(--neon-green)" />
        <div style={{ width: 1, height: 14, background: "var(--border)" }} />
        <Item label="SPV" value={`${status.supervisorMs || "—"}ms`} />
        <div style={{ width: 1, height: 14, background: "var(--border)" }} />
        <Item label="MODEL" value={status.model} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Item label="VAULT" value={status.vaultStatus} color="var(--neon-green)" />
        <div style={{ width: 1, height: 14, background: "var(--border)" }} />
        <Item label="SANDBOX" value={status.sandboxStatus} color="var(--neon-green)" />
        <div style={{ width: 1, height: 14, background: "var(--border)" }} />
        <Item label="UPTIME" value={status.uptime} />
      </div>
    </header>
  );
}
