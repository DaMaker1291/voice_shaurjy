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

export default function TopBar({ onNewChat, onCommandPalette, onToggleLivePanel, showLivePanel, rateLimited, rateLimitRetry }: {
  onNewChat?: () => void;
  onCommandPalette?: () => void;
  onToggleLivePanel?: () => void;
  showLivePanel?: boolean;
  rateLimited?: boolean;
  rateLimitRetry?: number;
}) {
  const pathname = usePathname();
  const [status, setStatus] = useState<SystemStatus>({
    network: "OPTIMAL",
    supervisorMs: 0,
    model: "CLOUD_GROQ",
    vaultStatus: "SECURE",
    sandboxStatus: "AIRGAPPED",
    uptime: "00:00:00",
  });
  const [agentCount, setAgentCount] = useState(0);
  const [deviceCount, setDeviceCount] = useState(0);

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
      try {
        const res = await fetch("/api/autonomous/tasks");
        const data = await res.json();
        setAgentCount((data.tasks || []).filter((t: any) => t.status === "running").length);
      } catch {}
      try {
        const res = await fetch("/api/relay/devices?user_id=local");
        const data = await res.json();
        setDeviceCount((data.devices || []).length);
      } catch {}
    };
    fetchStatus();
    const statusInterval = setInterval(fetchStatus, 10000);

    // Cmd+K listener
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onCommandPalette?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => { clearInterval(interval); clearInterval(statusInterval); window.removeEventListener("keydown", handleKeyDown); };
  }, [onCommandPalette]);

  const navItems = [
    { href: "/", label: "CHAT", icon: "💬", shortcut: "⌘1" },
    { href: "/agents", label: "AGENTS", icon: "🤖", shortcut: "⌘2" },
    { href: "/sovereign", label: "DEVICES", icon: "📡", shortcut: "⌘3" },
    { href: "/feed", label: "FEED", icon: "📋", shortcut: "⌘4" },
    { href: "/settings", label: "CONFIG", icon: "⚙️" },
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
            display: "flex", alignItems: "center", gap: 4,
            background: pathname === item.href ? "var(--neon-green-dim)" : "transparent",
            color: pathname === item.href ? "var(--neon-green)" : "var(--text-muted)",
          }}>
            {item.label}
            {item.shortcut && (
              <span style={{ fontSize: 7, opacity: 0.4, marginLeft: 2 }}>{item.shortcut}</span>
            )}
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

      {/* Right: Status + Cmd+K */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {/* Rate Limit Indicator */}
        {rateLimited && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 3, background: "rgba(255,179,0,0.1)", border: "1px solid rgba(255,179,0,0.2)" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#FFB300", animation: "glow-pulse 1s ease-in-out infinite" }} />
            <span style={{ fontSize: 8, color: "#FFB300", fontVariantNumeric: "tabular-nums" }}>RATE LIMITED {rateLimitRetry}s</span>
          </div>
        )}
        {/* Live Panel Toggle */}
        {agentCount > 0 && (
          <button onClick={onToggleLivePanel} style={{
            display: "flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 4,
            background: showLivePanel ? "rgba(0,255,102,0.12)" : "var(--surface-raised)",
            border: `1px solid ${showLivePanel ? "rgba(0,255,102,0.3)" : "var(--border)"}`,
            cursor: "pointer", fontFamily: "var(--font-mono)",
          }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#00FF66", animation: "glow-pulse 1.5s ease-in-out infinite" }} />
            <span style={{ fontSize: 8, color: showLivePanel ? "#00FF66" : "var(--text-muted)" }}>LIVE</span>
          </button>
        )}
        {/* Command Palette Trigger */}
        <button onClick={onCommandPalette} style={{
          display: "flex", alignItems: "center", gap: 6, padding: "3px 8px", borderRadius: 4,
          background: "var(--surface-raised)", border: "1px solid var(--border)",
          cursor: "pointer", fontFamily: "var(--font-mono)",
        }}>
          <span style={{ fontSize: 8, color: "var(--text-muted)" }}>⌘K</span>
          <span style={{ fontSize: 8, color: "var(--text-muted)" }}>Commands</span>
        </button>
        {/* Live Agent Count */}
        {agentCount > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 6px", borderRadius: 3, background: "rgba(0,255,102,0.1)", border: "1px solid rgba(0,255,102,0.2)" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#00FF66", animation: "glow-pulse 1.5s ease-in-out infinite" }} />
            <span style={{ fontSize: 8, color: "#00FF66", letterSpacing: "0.06em" }}>{agentCount} AGENT{agentCount > 1 ? "S" : ""}</span>
          </div>
        )}
        {/* Device Count */}
        {deviceCount > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: 8, color: "var(--text-muted)" }}>{deviceCount} DEV</span>
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: status.network === "OPTIMAL" ? "var(--neon-green)" : "var(--amber)", boxShadow: `0 0 6px ${status.network === "OPTIMAL" ? "rgba(0,255,102,0.4)" : "rgba(255,179,0,0.4)"}` }} />
          <span style={{ fontSize: 8, color: status.network === "OPTIMAL" ? "var(--neon-green)" : "var(--amber)", letterSpacing: "0.08em" }}>
            {status.network === "OPTIMAL" ? "ONLINE" : "STANDBY"}
          </span>
        </div>
        <span style={{ fontSize: 8, color: "var(--text-muted)" }}>{status.model}</span>
        <span style={{ fontSize: 8, color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>{status.uptime}</span>
      </div>
    </header>
  );
}
