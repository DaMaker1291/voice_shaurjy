"use client";

import { useState } from "react";
import Link from "next/link";
import CredentialModal from "@/components/cockpit/CredentialModal";

type Tab = "general" | "devices" | "security" | "advanced";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [showCredModal, setShowCredModal] = useState(false);

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "general", label: "GENERAL", icon: "⚙️" },
    { id: "devices", label: "DEVICES", icon: "📡" },
    { id: "security", label: "SECURITY", icon: "🔒" },
    { id: "advanced", label: "ADVANCED", icon: "🛠️" },
  ];

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        .sf { animation: fade-in 0.2s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Header */}
      <header style={{ height: 40, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", padding: "0 16px", gap: 12, flexShrink: 0 }}>
        <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
        <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
        <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>SETTINGS</span>
      </header>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #1a1d23", padding: "0 16px", flexShrink: 0 }}>
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
            padding: "10px 16px", fontSize: 10, fontWeight: 500, fontFamily: "inherit", cursor: "pointer",
            background: "transparent", border: "none", borderBottom: `2px solid ${activeTab === tab.id ? "#00FF66" : "transparent"}`,
            color: activeTab === tab.id ? "#00FF66" : "#667085", transition: "all 0.15s", letterSpacing: "0.06em",
          }}>
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
        <div style={{ maxWidth: 600, margin: "0 auto" }}>

          {activeTab === "general" && (
            <div className="sf" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <SectionTitle>Identity</SectionTitle>
              <SettingRow label="Product" value="JARVIS AI Brain" />
              <SettingRow label="Version" value="v3.0 Sovereign Network" />
              <SettingRow label="Interface" value="Cursor-style Tactical Cockpit" />

              <SectionTitle>Backend</SectionTitle>
              <SettingRow label="Cloud Model" value="GROQ Llama 3.3 70B" accent />
              <SettingRow label="Local Model" value="Qwen 2.5 1.5B (optional)" />
              <SettingRow label="Agent Mode" value="Autonomous Multi-Step" accent />
              <SettingRow label="Browser" value="Headless Chrome (CDP)" />

              <SectionTitle>Navigation</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[
                  { href: "/", label: "CHAT", desc: "⌘1" },
                  { href: "/agents", label: "AGENTS", desc: "⌘2" },
                  { href: "/sovereign", label: "DEVICES", desc: "⌘3" },
                  { href: "/feed", label: "FEED", desc: "⌘4" },
                ].map(item => (
                  <Link key={item.href} href={item.href} style={{
                    padding: "10px 14px", borderRadius: 6, textDecoration: "none",
                    background: "#0d0f12", border: "1px solid #1a1d23", transition: "all 0.15s",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                  }}>
                    <span style={{ fontSize: 11, color: "#e5e5e5" }}>{item.label}</span>
                    <span style={{ fontSize: 8, color: "#667085", padding: "2px 6px", borderRadius: 3, background: "#1a1d23" }}>{item.desc}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {activeTab === "devices" && (
            <div className="sf" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <SectionTitle>Network Scanner</SectionTitle>
              <SettingRow label="Relay Status" value="Running on localhost:9880" accent />
              <SettingRow label="ARP Scan" value="Enabled — discovers all local devices" />
              <SettingRow label="Protocol Cascade" value="HTTP → MQTT → UPnP → WLED → Tapo" />
              <SettingRow label="Alexa Discovery" value="SSDP + Amazon MAC OUI lookup" />

              <SectionTitle>Device Types</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[
                  { icon: "💡", label: "Smart Plugs", desc: "Tapo P100/P110", color: "#00B4D8" },
                  { icon: "🔊", label: "Smart Speakers", desc: "Amazon Echo", color: "#00B4D8" },
                  { icon: "🖨️", label: "Printers", desc: "HP LaserJet", color: "#F97316" },
                  { icon: "📱", label: "Phones", desc: "Samsung/ADB", color: "#A855F7" },
                  { icon: "📷", label: "Cameras", desc: "RTSP/ONVIF", color: "#FF3333" },
                  { icon: "🌐", label: "Routers", desc: "Sky/TP-Link", color: "#FFB300" },
                ].map(d => (
                  <div key={d.label} style={{
                    padding: "10px 14px", borderRadius: 6, background: "#0d0f12",
                    border: "1px solid #1a1d23", borderLeft: `3px solid ${d.color}`,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span>{d.icon}</span>
                      <span style={{ fontSize: 11, color: "#e5e5e5" }}>{d.label}</span>
                    </div>
                    <div style={{ fontSize: 9, color: "#667085" }}>{d.desc}</div>
                  </div>
                ))}
              </div>

              <SectionTitle>Credentials</SectionTitle>
              <div style={{ padding: "14px 16px", borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23" }}>
                <div style={{ fontSize: 10, color: "#9ca3af", marginBottom: 8 }}>
                  Set Tapo device credentials for plug control. Stored encrypted on your machine only.
                </div>
                <button onClick={() => setShowCredModal(true)} style={{
                  padding: "8px 16px", borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                  cursor: "pointer", background: "rgba(0,255,102,0.1)", color: "#00FF66",
                  border: "1px solid rgba(0,255,102,0.2)", fontWeight: 500,
                }}>
                  🔐 Set Device Credentials
                </button>
              </div>
            </div>
          )}

          {activeTab === "security" && (
            <div className="sf" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <SectionTitle>Threat Model</SectionTitle>
              <div style={{ padding: "14px 16px", borderRadius: 8, background: "rgba(0,255,102,0.05)", border: "1px solid rgba(0,255,102,0.15)" }}>
                <div style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, marginBottom: 6 }}>TIER 5 — MAXIMUM HARDENING</div>
                <div style={{ fontSize: 10, color: "#9ca3af", lineHeight: 1.6 }}>
                  • Sandbox isolation with zero ingress/egress by default<br />
                  • Per-execution MAC address rotation<br />
                  • Encrypted local vault for all credentials<br />
                  • 50+ attack vector real-time monitoring<br />
                  • Human-in-the-loop for all destructive actions
                </div>
              </div>

              <SectionTitle>Sandbox</SectionTitle>
              <SettingRow label="Status" value="AIRGAPPED" accent />
              <SettingRow label="Filesystem" value="Read-only base, writable overlay" />
              <SettingRow label="Network" value="Simulated eth0 (no real egress)" />
              <SettingRow label="Process Limit" value="512 concurrent" />

              <SectionTitle>Crypto</SectionTitle>
              <SettingRow label="Key Derivation" value="PBKDF2-SHA256" />
              <SettingRow label="Encryption" value="AES-256-GCM" />
              <SettingRow label="Local Vault" value="AES-256-GCM" accent />
            </div>
          )}

          {activeTab === "advanced" && (
            <div className="sf" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <SectionTitle>Autonomous Agent</SectionTitle>
              <SettingRow label="Mode" value="Multi-Step Autonomous" accent />
              <SettingRow label="Max Steps" value="Unlimited (never stops until done)" />
              <SettingRow label="Evaluation" value="Auto-evaluate completion per step" />
              <SettingRow label="Follow-up" value="Adds more steps if task incomplete" />

              <SectionTitle>Headless Browser</SectionTitle>
              <SettingRow label="Mode" value="Chrome --headless=new (CDP)" accent />
              <SettingRow label="Port" value="9222 (local WebSocket)" />
              <SettingRow label="Scope" value="Background — no mouse/keyboard hijack" />
              <SettingRow label="Control" value="Navigate, Click, Type, Screenshot, JS Eval" />

              <SectionTitle>Relay</SectionTitle>
              <SettingRow label="Protocol" value="WebSocket (9880)" />
              <SettingRow label="Heartbeat" value="30s interval" />
              <SettingRow label="Auto-register" value="Re-registers on heartbeat failure" accent />

              <SectionTitle>Danger Zone</SectionTitle>
              <div style={{ padding: "14px 16px", borderRadius: 8, background: "rgba(255,51,51,0.05)", border: "1px solid rgba(255,51,51,0.15)" }}>
                <div style={{ fontSize: 10, color: "#FF3333", marginBottom: 8 }}>These actions cannot be undone.</div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={{
                    padding: "6px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                    cursor: "pointer", background: "rgba(255,51,51,0.1)", color: "#FF3333",
                    border: "1px solid rgba(255,51,51,0.2)",
                  }}>
                    Reset All Devices
                  </button>
                  <button style={{
                    padding: "6px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                    cursor: "pointer", background: "rgba(255,51,51,0.1)", color: "#FF3333",
                    border: "1px solid rgba(255,51,51,0.2)",
                  }}>
                    Clear Credentials
                  </button>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      {showCredModal && (
        <CredentialModal
          open={showCredModal}
          title="Device Credentials"
          description="Set Tapo device credentials for smart plug control. Stored encrypted locally."
          fields={[
            { name: "username", label: "Username", placeholder: "your@email.com" },
            { name: "password", label: "Password", type: "password" },
          ]}
          onSubmit={async (values) => {
            try {
              await fetch("/api/entity/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  text: `set device credentials ${values.username} ${values.password}`,
                  user_id: "local",
                  session_id: "settings",
                }),
              });
            } catch {}
            setShowCredModal(false);
          }}
          onClose={() => setShowCredModal(false)}
        />
      )}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, fontWeight: 600, color: "#667085", letterSpacing: "0.1em", textTransform: "uppercase" as any, marginTop: 8 }}>
      {children}
    </div>
  );
}

function SettingRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "10px 14px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23",
    }}>
      <span style={{ fontSize: 11, color: "#9ca3af" }}>{label}</span>
      <span style={{ fontSize: 11, color: accent ? "#00FF66" : "#e5e5e5", fontWeight: accent ? 500 : 400 }}>
        {value}
      </span>
    </div>
  );
}
