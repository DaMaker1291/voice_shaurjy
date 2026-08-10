"use client";

import { useState, useEffect } from "react";

type Platform = "windows" | "mac" | "linux" | "unknown";

const RELAY_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const INSTALL_HOST = process.env.NEXT_PUBLIC_INSTALL_URL || "";

const INSTALL_COMMANDS: Record<Platform, { label: string; icon: string; cmd: string; note: string }> = {
  windows: {
    label: "Windows",
    icon: "🪟",
    cmd: INSTALL_HOST ? `irm ${INSTALL_HOST}/install.ps1 | iex` : "Set env NEXT_PUBLIC_INSTALL_URL to your server",
    note: "Run in PowerShell as Administrator",
  },
  mac: {
    label: "macOS",
    icon: "🍎",
    cmd: `curl -sL '${RELAY_BASE}/relay' | python3 - --user`,
    note: "Run in Terminal",
  },
  linux: {
    label: "Linux",
    icon: "🐧",
    cmd: `curl -sL '${RELAY_BASE}/relay' | python3 - --user`,
    note: "Run in Terminal (may need sudo)",
  },
  unknown: {
    label: "Your OS",
    icon: "💻",
    cmd: "",
    note: "Detecting...",
  },
};

export default function InstallPage() {
  const [platform, setPlatform] = useState<Platform>("unknown");
  const [copied, setCopied] = useState(false);
  const [hovering, setHovering] = useState(false);

  useEffect(() => {
    const ua = navigator.userAgent.toLowerCase();
    if (ua.includes("win")) setPlatform("windows");
    else if (ua.includes("mac")) setPlatform("mac");
    else setPlatform("linux");
  }, []);

  const info = INSTALL_COMMANDS[platform];

  const copyCmd = () => {
    navigator.clipboard.writeText(info.cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      minHeight: "100dvh", display: "flex", flexDirection: "column",
      background: "#030303", color: "#e5e5e5",
      fontFamily: "'JetBrains Mono', monospace",
      alignItems: "center", justifyContent: "center",
      position: "relative", overflow: "hidden", padding: 32,
    }}>
      {/* Background grid */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(0,255,102,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,102,0.03) 1px, transparent 1px)",
        backgroundSize: "40px 40px", opacity: 0.4,
      }} />

      {/* Radial glow */}
      <div style={{
        position: "absolute", top: "30%", left: "50%", transform: "translate(-50%, -50%)",
        width: 700, height: 700, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(0,255,102,0.05) 0%, transparent 50%)",
        pointerEvents: "none",
      }} />

      <style jsx>{`
        @keyframes fade-in { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes glow { 0%,100% { box-shadow: 0 0 20px rgba(0,255,102,0.15); } 50% { box-shadow: 0 0 50px rgba(0,255,102,0.3); } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
        @keyframes ring { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes ring-rev { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        .fade { animation: fade-in 0.6s cubic-bezier(0.16,1,0.3,1) both; }
        .fade-d1 { animation-delay: 0.1s; }
        .fade-d2 { animation-delay: 0.2s; }
        .fade-d3 { animation-delay: 0.3s; }
        .fade-d4 { animation-delay: 0.4s; }
        .glow { animation: glow 3s ease-in-out infinite; }
        .float { animation: float 3s ease-in-out infinite; }
        .ring-anim { animation: ring 10s linear infinite; }
        .ring-rev-anim { animation: ring-rev 7s linear infinite; }
        .pulse { animation: pulse 2s ease-in-out infinite; }
      `}</style>

      {/* Logo */}
      <div className="float fade" style={{ marginBottom: 40 }}>
        <div style={{ width: 120, height: 120, position: "relative" }}>
          <div className="ring-anim" style={{ position: "absolute", inset: 0, borderRadius: "50%", border: "1px solid rgba(0,255,102,0.12)" }} />
          <div className="ring-rev-anim" style={{ position: "absolute", inset: 16, borderRadius: "50%", border: "1px solid rgba(0,255,102,0.18)" }} />
          <div className="ring-anim" style={{ position: "absolute", inset: 32, borderRadius: "50%", border: "1px dashed rgba(0,255,102,0.1)", animationDuration: "15s" }} />
          <div style={{
            position: "absolute", inset: 44, borderRadius: "50%",
            background: "radial-gradient(circle, rgba(0,255,102,0.15) 0%, transparent 70%)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <div className="glow" style={{ width: 16, height: 16, borderRadius: "50%", background: "#00FF66" }} />
          </div>
        </div>
      </div>

      {/* Title */}
      <div className="fade fade-d1" style={{ textAlign: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 32, fontWeight: 700, letterSpacing: "0.15em", background: "linear-gradient(135deg, #00FF66, #00B4D8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          JARVIS
        </div>
        <div style={{ fontSize: 10, color: "#667085", letterSpacing: "0.25em", marginBottom: 4 }}>
          SOVEREIGN NETWORK ORCHESTRATOR
        </div>
      </div>

      {/* Tagline */}
      <div className="fade fade-d2" style={{ textAlign: "center", maxWidth: 480, marginBottom: 40 }}>
        <div style={{ fontSize: 13, color: "#999", lineHeight: 1.8, marginBottom: 4 }}>
          Control every device. Automate every task. Own your intelligence.
        </div>
        <div style={{ fontSize: 10, color: "#555" }}>
          Install JARVIS on your {info.label} machine in 30 seconds.
        </div>
      </div>

      {/* Install card */}
      <div className="fade fade-d3" style={{
        maxWidth: 560, width: "100%", background: "#0a0c10",
        border: "1px solid #1a1d23", borderRadius: 12, overflow: "hidden",
      }}>
        {/* Card header */}
        <div style={{
          padding: "16px 20px", borderBottom: "1px solid #1a1d23",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 20 }}>{info.icon}</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5" }}>
                Install for {info.label}
              </div>
              <div style={{ fontSize: 9, color: "#667085" }}>
                {info.note}
              </div>
            </div>
          </div>
          <div style={{
            display: "flex", alignItems: "center", gap: 4,
            padding: "4px 10px", borderRadius: 20,
            background: "rgba(0,255,102,0.06)", border: "1px solid rgba(0,255,102,0.12)",
          }}>
            <div className="pulse" style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66" }} />
            <span style={{ fontSize: 8, color: "#00FF66", letterSpacing: "0.05em" }}>FREE</span>
          </div>
        </div>

        {/* Command box */}
        <div style={{ padding: 16 }}>
          <div style={{
            background: "#030303", border: "1px solid #1a1d23", borderRadius: 8,
            padding: "14px 16px", position: "relative",
          }}>
            <div style={{ fontSize: 8, color: "#667085", marginBottom: 8, letterSpacing: "0.1em" }}>
              {platform === "windows" ? "POWERSHELL" : "TERMINAL"}
            </div>
            <code style={{
              fontSize: 11, color: "#00FF66", lineHeight: 1.7,
              display: "block", wordBreak: "break-all", userSelect: "all",
            }}>
              {info.cmd}
            </code>
            <button
              onClick={copyCmd}
              style={{
                position: "absolute", top: 12, right: 12,
                padding: "6px 14px", borderRadius: 6,
                background: copied ? "rgba(0,255,102,0.15)" : "rgba(255,255,255,0.04)",
                border: `1px solid ${copied ? "rgba(0,255,102,0.3)" : "rgba(255,255,255,0.08)"}`,
                color: copied ? "#00FF66" : "#888",
                fontSize: 9, fontFamily: "inherit", cursor: "pointer",
                transition: "all 0.2s", fontWeight: 600, letterSpacing: "0.05em",
              }}
              onMouseEnter={() => setHovering(true)}
              onMouseLeave={() => setHovering(false)}
            >
              {copied ? "✓ COPIED" : "COPY"}
            </button>
          </div>
        </div>

        {/* Features */}
        <div style={{ padding: "0 16px 16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
            {[
              { icon: "🔒", label: "Encrypted", desc: "End-to-end" },
              { icon: "⚡", label: "Instant", desc: "30 seconds" },
              { icon: "🔄", label: "Auto-Update", desc: "Always latest" },
            ].map((f, i) => (
              <div key={f.label} style={{
                padding: "10px 12px", borderRadius: 8, background: "#030303",
                border: "1px solid #111318", textAlign: "center",
              }}>
                <div style={{ fontSize: 16, marginBottom: 4 }}>{f.icon}</div>
                <div style={{ fontSize: 9, fontWeight: 600, color: "#ccc", marginBottom: 2 }}>{f.label}</div>
                <div style={{ fontSize: 8, color: "#667085" }}>{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* What it does */}
      <div className="fade fade-d4" style={{ maxWidth: 560, width: "100%", marginTop: 32 }}>
        <div style={{ fontSize: 10, color: "#667085", letterSpacing: "0.1em", marginBottom: 12, textAlign: "center" }}>
          WHAT HAPPENS NEXT
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { step: "1", text: "Install Python + dependencies automatically" },
            { step: "2", text: "Download the relay agent to ~/.jarvis" },
            { step: "3", text: "Create Desktop & Start Menu shortcuts" },
            { step: "4", text: "Relay pairs with JARVIS cloud brain" },
            { step: "5", text: "Device discovery, control, and automation begin" },
          ].map((s, i) => (
            <div key={s.step} style={{
              display: "flex", alignItems: "center", gap: 12, padding: "10px 16px",
              borderRadius: 8, background: "#0a0c10", border: "1px solid #111318",
              animation: `fade-in 0.4s cubic-bezier(0.16,1,0.3,1) ${0.5 + i * 0.08}s both`,
            }}>
              <div style={{
                width: 24, height: 24, borderRadius: 6, display: "flex",
                alignItems: "center", justifyContent: "center", fontSize: 10,
                fontWeight: 700, color: "#030303", background: "#00FF66",
                flexShrink: 0,
              }}>
                {s.step}
              </div>
              <div style={{ fontSize: 11, color: "#bbb" }}>{s.text}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom link */}
      <div className="fade fade-d4" style={{ marginTop: 32, textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "#444" }}>
          Already installed?{" "}
          <a href="/" style={{ color: "#00FF66", textDecoration: "none" }}>
            Open JARVIS →
          </a>
        </div>
      </div>

      {/* Footer */}
      <div style={{ position: "absolute", bottom: 16, fontSize: 8, color: "#333", letterSpacing: "0.1em" }}>
        JARVIS v3.0 · SOVEREIGN NETWORK ORCHESTRATOR
      </div>
    </div>
  );
}
