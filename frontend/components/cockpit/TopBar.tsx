"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface SystemStatus {
  network: string;
  supervisorMs: number;
  model: string;
  vaultStatus: string;
  sandboxStatus: string;
  uptime: string;
}

export default function TopBar({ onNewChat }: { onNewChat?: () => void }) {
  const pathname = usePathname();
  const [status, setStatus] = useState<SystemStatus>({
    network: "OPTIMAL",
    supervisorMs: 0,
    model: "CLOUD_GROQ",
    vaultStatus: "SECURE",
    sandboxStatus: "AIRGAPPED",
    uptime: "00:00:00",
  });

  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
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

  const navItems = [
    { href: "/", label: "CHAT" },
    { href: "/agents", label: "AGENTS" },
    { href: "/sovereign", label: "NETWORK" },
    { href: "/settings", label: "CONFIG" },
  ];

  return (
    <header style={{ height: 36, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
      {/* Left: Logo + Nav */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 6, textDecoration: "none" }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 8px rgba(0,255,102,0.4)" }} />
          <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.1em" }}>JARVIS</span>
        </Link>
        <div style={{ width: 1, height: 16, background: "var(--border)" }} />
        {navItems.map(item => (
          <Link key={item.href} href={item.href} style={{
            padding: "3px 8px", borderRadius: 3, fontSize: 9, fontWeight: 600, textDecoration: "none",
            fontFamily: "var(--font-mono)", letterSpacing: "0.08em", transition: "all 0.15s",
            background: pathname === item.href ? "var(--neon-green-dim)" : "transparent",
            color: pathname === item.href ? "var(--neon-green)" : "var(--text-muted)",
          }}>
            {item.label}
          </Link>
        ))}
        {pathname === "/" && onNewChat && (
          <>
            <div style={{ width: 1, height: 16, background: "var(--border)" }} />
            <button onClick={onNewChat} style={{
              padding: "3px 8px", borderRadius: 3, fontSize: 9, fontWeight: 600,
              fontFamily: "var(--font-mono)", letterSpacing: "0.08em", cursor: "pointer",
              background: "var(--surface-raised)", color: "var(--text-muted)",
              border: "1px solid var(--border)", transition: "all 0.15s",
            }}>
              + NEW
            </button>
          </>
        )}
      </div>

      {/* Right: Status */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 6px rgba(0,255,102,0.4)" }} />
          <span style={{ fontSize: 8, color: "var(--neon-green)", letterSpacing: "0.08em" }}>SECURE</span>
        </div>
        <span style={{ fontSize: 8, color: "var(--text-muted)" }}>NET {status.network}</span>
        <span style={{ fontSize: 8, color: "var(--text-muted)" }}>{status.model}</span>
        <span style={{ fontSize: 8, color: "var(--text-muted)" }}>VAULT {status.vaultStatus}</span>
        <span style={{ fontSize: 8, color: "var(--text-muted)" }}>{status.uptime}</span>
      </div>
    </header>
  );
}
