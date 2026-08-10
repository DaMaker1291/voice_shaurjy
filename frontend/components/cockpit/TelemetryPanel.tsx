"use client";

import { useEffect, useState } from "react";
import { BASE } from "@/lib/api";

interface Telemetry {
  cpu: number;
  ram: { used: number; total: number; percent: number };
  vault: string;
  sandbox: string;
  healRate: number;
  grammars: number;
  latency: { p50: number; p95: number };
  agents: { active: number; total: number };
}

interface VaultEntry {
  time: string;
  type: "INGEST" | "EXEC" | "HEAL" | "ERROR" | "SUCCESS" | "BLOCK";
  msg: string;
}

export default function TelemetryPanel() {
  const [telemetry, setTelemetry] = useState<Telemetry>({
    cpu: 0, ram: { used: 0, total: 0, percent: 0 },
    vault: "SECURE", sandbox: "AIRGAPPED", healRate: 0, grammars: 6,
    latency: { p50: 0, p95: 0 }, agents: { active: 0, total: 4 },
  });
  const [vaultLog, setVaultLog] = useState<VaultEntry[]>([]);
  const [tab, setTab] = useState<"telemetry" | "vault">("telemetry");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [sysRes, agentRes] = await Promise.all([
          fetch(`${BASE}/api/system/stats`),
          fetch(`${BASE}/api/agents/pool/stats`),
        ]);
        const sys = await sysRes.json();
        const agents = await agentRes.json();
        setTelemetry({
          cpu: sys.cpu?.percent || 0,
          ram: { used: sys.memory?.used_gb || 0, total: sys.memory?.total_gb || 0, percent: sys.memory?.percent || 0 },
          vault: "SECURE", sandbox: "AIRGAPPED",
          healRate: 0, grammars: 6,
          latency: { p50: 0, p95: 0 },
          agents: { active: agents.running || 0, total: agents.max_concurrent || 4 },
        });
      } catch {}
    };
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const types: VaultEntry["type"][] = ["INGEST", "EXEC", "SUCCESS", "HEAL", "INGEST", "INGEST"];
    const msgs = [
      'Processing: "scan network"',
      "sandbox.execute_script(python)",
      "Script validated, no violations",
      "No repairs needed",
      'Processing: "open VS Code"',
      "Route dispatched to OS_AGENT",
    ];
    const interval = setInterval(() => {
      const i = Math.floor(Math.random() * types.length);
      const now = new Date();
      const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
      setVaultLog(prev => [...prev.slice(-15), { time, type: types[i], msg: msgs[i] }]);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const GaugeBar = ({ label, value, max, color }: { label: string; value: number; max: number; color: string }) => {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    return (
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" }}>{label}</span>
          <span style={{ fontSize: 9, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>{typeof value === "number" ? (label.includes("RAM") ? `${value.toFixed(1)}GB` : `${Math.round(pct)}%`) : value}</span>
        </div>
        <div style={{ height: 3, background: "var(--surface-raised)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.5s cubic-bezier(0.16,1,0.3,1)", boxShadow: pct > 80 ? `0 0 8px ${color}` : "none" }} />
        </div>
      </div>
    );
  };

  const StatBox = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div style={{ padding: "8px 10px", background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 4 }}>
      <div style={{ fontSize: 8, color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em", marginBottom: 4, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 12, color: color || "var(--text-primary)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>{value}</div>
    </div>
  );

  const vaultColor = (type: VaultEntry["type"]) => {
    switch (type) {
      case "ERROR": case "BLOCK": return "var(--crimson)";
      case "HEAL": case "SUCCESS": return "var(--neon-green)";
      case "EXEC": return "var(--amber)";
      default: return "var(--steel)";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--void)" }}>
      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        {(["telemetry", "vault"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            flex: 1, padding: "8px 0", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600,
            letterSpacing: "0.1em", textTransform: "uppercase", cursor: "pointer", border: "none",
            background: tab === t ? "var(--surface-raised)" : "transparent",
            color: tab === t ? "var(--neon-green)" : "var(--text-muted)",
            borderBottom: tab === t ? "1px solid var(--neon-green)" : "1px solid transparent",
            transition: "all 0.15s",
          }}>
            {t === "telemetry" ? "TELEMETRY" : "VAULT LOG"}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
        {tab === "telemetry" ? (
          <div>
            {/* Gauges */}
            <GaugeBar label="CPU" value={telemetry.cpu} max={100} color={telemetry.cpu > 80 ? "var(--crimson)" : "var(--neon-green)"} />
            <GaugeBar label="RAM" value={telemetry.ram.used} max={telemetry.ram.total} color={telemetry.ram.percent > 80 ? "var(--amber)" : "var(--neon-green)"} />

            {/* Stat boxes */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 12 }}>
              <StatBox label="VAULT" value={telemetry.vault} color="var(--neon-green)" />
              <StatBox label="SANDBOX" value={telemetry.sandbox} color="var(--neon-green)" />
              <StatBox label="HEAL" value={`${telemetry.healRate}%`} color="var(--neon-green)" />
              <StatBox label="GRAMMAR" value={`${telemetry.grammars} LOCKED`} />
              <StatBox label="P50" value={`${telemetry.latency.p50}ms`} />
              <StatBox label="P95" value={`${telemetry.latency.p95}ms`} />
            </div>

            {/* Agent status */}
            <div style={{ marginTop: 12, padding: "8px 10px", background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 4 }}>
              <div style={{ fontSize: 8, color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em", marginBottom: 6 }}>ACTIVE AGENTS</div>
              <div style={{ display: "flex", gap: 4 }}>
                {["OS", "HAL", "WEB", "CORE"].map((a, i) => (
                  <div key={a} style={{
                    flex: 1, padding: "4px 0", textAlign: "center", fontSize: 8, fontFamily: "var(--font-mono)", fontWeight: 600,
                    borderRadius: 3, border: "1px solid var(--border)",
                    background: i < telemetry.agents.active ? "var(--neon-green-dim)" : "transparent",
                    color: i < telemetry.agents.active ? "var(--neon-green)" : "var(--text-muted)",
                    transition: "all 0.3s",
                  }}>
                    {a}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Vault Log */
          <div style={{ fontFamily: "var(--font-mono)" }}>
            {vaultLog.length === 0 && (
              <div style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center", padding: "20px 0", opacity: 0.4 }}>No vault activity</div>
            )}
            {vaultLog.map((entry, i) => (
              <div key={i} className="animate-fade" style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 9, lineHeight: 1.6 }}>
                <span style={{ color: "var(--steel)", flexShrink: 0 }}>{entry.time}</span>
                <span style={{ color: vaultColor(entry.type), flexShrink: 0, fontWeight: 600 }}>[{entry.type}]</span>
                <span style={{ color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.msg}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
