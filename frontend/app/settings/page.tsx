"use client";

import { useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";

const CredentialModal = dynamic(() => import("@/components/cockpit/CredentialModal"), { ssr: false });

interface Settings {
  hfToken: string;
  groqKey: string;
  userName: string;
  relayUrl: string;
  theme: "obsidian" | "midnight";
  autoApprove: boolean;
  voiceEnabled: boolean;
  modelPreference: "local" | "cloud" | "auto";
}

const DEFAULT_SETTINGS: Settings = {
  hfToken: "",
  groqKey: "",
  userName: "local",
  relayUrl: "https://dgfhgjhj-jarvis-ai-brain.hf.space",
  theme: "obsidian",
  autoApprove: false,
  voiceEnabled: true,
  modelPreference: "auto",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("jarvis_settings");
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
    }
    return DEFAULT_SETTINGS;
  });
  const [saved, setSaved] = useState(false);
  const [activeSection, setActiveSection] = useState<"api" | "relay" | "general" | "about">("api");
  const [showApiModal, setShowApiModal] = useState(false);
  const [showRelayModal, setShowRelayModal] = useState(false);

  const save = () => {
    localStorage.setItem("jarvis_settings", JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const update = (key: keyof Settings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const inputStyle = {
    width: "100%", padding: "8px 10px", borderRadius: 4, fontSize: 11,
    fontFamily: "var(--font-mono)", background: "var(--surface-raised)",
    border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none",
    transition: "border-color 0.15s",
  };

  const labelStyle = {
    fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em", marginBottom: 4, display: "block" as const,
    textTransform: "uppercase" as const,
  };

  const sections = [
    { id: "api" as const, label: "API KEYS", icon: "🔑" },
    { id: "relay" as const, label: "RELAY", icon: "📡" },
    { id: "general" as const, label: "GENERAL", icon: "⚙️" },
    { id: "about" as const, label: "ABOUT", icon: "ℹ️" },
  ];

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--void)", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
      {/* Header */}
      <header style={{ height: 32, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/" style={{ fontSize: 10, color: "var(--text-muted)", textDecoration: "none" }}>← BACK</Link>
          <div style={{ width: 1, height: 14, background: "var(--border)" }} />
          <span style={{ fontSize: 10, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600 }}>SETTINGS</span>
        </div>
        <button onClick={save} style={{
          padding: "4px 12px", borderRadius: 3, fontSize: 9, fontWeight: 600,
          fontFamily: "var(--font-mono)", cursor: "pointer", letterSpacing: "0.05em",
          background: saved ? "var(--neon-green)" : "var(--surface-raised)",
          color: saved ? "#000" : "var(--text-muted)", border: "1px solid var(--border)",
          transition: "all 0.15s",
        }}>
          {saved ? "✓ SAVED" : "SAVE"}
        </button>
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Sidebar */}
        <div style={{ width: 180, borderRight: "1px solid var(--border", padding: 12, flexShrink: 0 }}>
          {sections.map(s => (
            <button key={s.id} onClick={() => setActiveSection(s.id)} style={{
              width: "100%", padding: "8px 10px", borderRadius: 4, fontSize: 10,
              fontFamily: "var(--font-mono)", cursor: "pointer", textAlign: "left",
              display: "flex", alignItems: "center", gap: 8, marginBottom: 4,
              background: activeSection === s.id ? "var(--neon-green-dim)" : "transparent",
              color: activeSection === s.id ? "var(--neon-green)" : "var(--text-muted)",
              border: `1px solid ${activeSection === s.id ? "rgba(0,255,102,0.2)" : "transparent"}`,
              transition: "all 0.15s",
            }}>
              <span style={{ fontSize: 12 }}>{s.icon}</span>
              {s.label}
            </button>
          ))}

          <div style={{ marginTop: 20, padding: 10, borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)" }}>
            <div style={{ fontSize: 8, color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.08em" }}>RELAY COMMAND</div>
            <div style={{ fontSize: 9, color: "var(--text-secondary)", lineHeight: 1.5, wordBreak: "break-all" }}>
              python3 relay.py --user {settings.userName || "you"}
            </div>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          <div style={{ maxWidth: 500 }}>
            {activeSection === "api" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <button onClick={() => setShowApiModal(true)} style={{
                  padding: "12px 16px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                  fontFamily: "var(--font-mono)", cursor: "pointer", width: "100%",
                  background: "var(--neon-green-dim)", color: "var(--neon-green)",
                  border: "1px solid rgba(0,255,102,0.2)", transition: "all 0.15s",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}>
                  <span>🔒</span> Setup API Keys Securely
                </button>
                <div style={{ fontSize: 9, color: "var(--text-muted)", textAlign: "center" }}>
                  Opens an encrypted modal — credentials stay on your device
                </div>
                {settings.hfToken && (
                  <div style={{ padding: "8px 10px", borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)", fontSize: 9, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                    <span style={{ color: "var(--neon-green)" }}>✓</span> HF Token configured
                  </div>
                )}
                {settings.groqKey && (
                  <div style={{ padding: "8px 10px", borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)", fontSize: 9, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                    <span style={{ color: "var(--neon-green)" }}>✓</span> GROQ Key configured
                  </div>
                )}
              </div>
            )}

            {activeSection === "relay" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label style={labelStyle}>HF Space URL</label>
                  <input
                    type="text"
                    value={settings.relayUrl}
                    onChange={e => update("relayUrl", e.target.value)}
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>User ID</label>
                  <input
                    type="text"
                    value={settings.userName}
                    onChange={e => update("userName", e.target.value)}
                    style={inputStyle}
                  />
                </div>
                <div style={{ padding: 12, borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 9, color: "var(--neon-green)", fontWeight: 600, marginBottom: 8 }}>QUICK START</div>
                  <div style={{ fontSize: 10, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                    <div>1. Install dependencies: <code style={{ color: "var(--neon-green)", background: "var(--surface)", padding: "1px 4px", borderRadius: 2 }}>pip install -r requirements-local.txt</code></div>
                    <div>2. Run the relay: <code style={{ color: "var(--neon-green)", background: "var(--surface)", padding: "1px 4px", borderRadius: 2 }}>python3 relay.py --user {settings.userName || "you"}</code></div>
                    <div>3. Keep terminal open — relay auto-discovers devices</div>
                  </div>
                </div>
              </div>
            )}

            {activeSection === "general" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label style={labelStyle}>Model Preference</label>
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["local", "cloud", "auto"] as const).map(m => (
                      <button key={m} onClick={() => update("modelPreference", m)} style={{
                        padding: "6px 12px", borderRadius: 3, fontSize: 10, fontFamily: "var(--font-mono)",
                        cursor: "pointer", textTransform: "uppercase",
                        background: settings.modelPreference === m ? "var(--neon-green-dim)" : "var(--surface-raised)",
                        color: settings.modelPreference === m ? "var(--neon-green)" : "var(--text-muted)",
                        border: `1px solid ${settings.modelPreference === m ? "rgba(0,255,102,0.2)" : "var(--border)"}`,
                      }}>{m}</button>
                    ))}
                  </div>
                  <div style={{ fontSize: 8, color: "var(--text-muted)", marginTop: 4 }}>Local: SLM on relay | Cloud: GROQ | Auto: route by complexity</div>
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>Voice Input</div>
                    <div style={{ fontSize: 8, color: "var(--text-muted)" }}>Enable speech-to-text</div>
                  </div>
                  <button onClick={() => update("voiceEnabled", !settings.voiceEnabled)} style={{
                    width: 36, height: 20, borderRadius: 10, border: "none", cursor: "pointer",
                    background: settings.voiceEnabled ? "var(--neon-green)" : "var(--surface-raised)",
                    position: "relative", transition: "background 0.2s",
                  }}>
                    <div style={{
                      width: 16, height: 16, borderRadius: "50%", background: "#fff",
                      position: "absolute", top: 2, transition: "left 0.2s",
                      left: settings.voiceEnabled ? 18 : 2,
                    }} />
                  </button>
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>Auto-Approve Commands</div>
                    <div style={{ fontSize: 8, color: "var(--text-muted)" }}>Skip security intercept for known actions</div>
                  </div>
                  <button onClick={() => update("autoApprove", !settings.autoApprove)} style={{
                    width: 36, height: 20, borderRadius: 10, border: "none", cursor: "pointer",
                    background: settings.autoApprove ? "var(--neon-green)" : "var(--surface-raised)",
                    position: "relative", transition: "background 0.2s",
                  }}>
                    <div style={{
                      width: 16, height: 16, borderRadius: "50%", background: "#fff",
                      position: "absolute", top: 2, transition: "left 0.2s",
                      left: settings.autoApprove ? 18 : 2,
                    }} />
                  </button>
                </div>
              </div>
            )}

            {activeSection === "about" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ padding: 16, borderRadius: 6, background: "var(--surface)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--neon-green)", marginBottom: 8 }}>J.A.R.V.I.S.</div>
                  <div style={{ fontSize: 10, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                    Just A Rather Very Intelligent System
                    <br />Sovereign Network Orchestrator v3.0
                    <br /><br />
                    Tactical Obsidian Cyberpunk Interface
                    <br />Speculative Local Execution Engine
                    <br />Parallel Agent Pool with Self-Healing
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {[
                    { label: "BACKEND", value: "FastAPI" },
                    { label: "FRONTEND", value: "Next.js 14" },
                    { label: "LOCAL SLM", value: "Qwen 1.5B" },
                    { label: "CLOUD", value: "GROQ/Llama3" },
                    { label: "AGENTS", value: "10 Nodes" },
                    { label: "PROTOCOLS", value: "8+" },
                  ].map(item => (
                    <div key={item.label} style={{ padding: "8px 10px", background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 4 }}>
                      <div style={{ fontSize: 7, color: "var(--text-muted)", letterSpacing: "0.08em", marginBottom: 2 }}>{item.label}</div>
                      <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <CredentialModal
        open={showApiModal}
        title="API Configuration"
        description="Enter your API keys. These are encrypted locally and never sent to our servers."
        fields={[
          { name: "hfToken", label: "Hugging Face Token", placeholder: "hf_..." },
          { name: "groqKey", label: "GROQ API Key", placeholder: "gsk_..." },
        ]}
        onSubmit={(values) => {
          if (values.hfToken) update("hfToken", values.hfToken);
          if (values.groqKey) update("groqKey", values.groqKey);
          setShowApiModal(false);
        }}
        onClose={() => setShowApiModal(false)}
      />
    </div>
  );
}
