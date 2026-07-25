"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import CredentialModal from "@/components/cockpit/CredentialModal";
import { modKey } from "@/hooks/useModKey";
import { BASE, safeJson } from "@/lib/api";

type Tab = "general" | "devices" | "security" | "account";

interface UserProfile {
  name: string;
  email: string;
  avatar?: string;
  created: string;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [showCredModal, setShowCredModal] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [toast, setToast] = useState("");

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  // Load profile from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("jarvis_profile");
      if (saved) setProfile(JSON.parse(saved));
      else {
        const p = { name: "User", email: "", created: new Date().toISOString() };
        setProfile(p);
        localStorage.setItem("jarvis_profile", JSON.stringify(p));
      }
    } catch {
      const p = { name: "User", email: "", created: new Date().toISOString() };
      setProfile(p);
    }
  }, []);

  // Fetch health on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${BASE}/api/health`);
        setHealth(await safeJson(res));
      } catch { /* ok */ }
    })();
  }, []);

  const saveProfile = useCallback((updates: Partial<UserProfile>) => {
    if (!profile) return;
    const updated = { ...profile, ...updates };
    setProfile(updated);
    localStorage.setItem("jarvis_profile", JSON.stringify(updated));
    showToast("Profile saved");
  }, [profile]);

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "general", label: "GENERAL", icon: "⚙️" },
    { id: "devices", label: "DEVICES", icon: "📡" },
    { id: "security", label: "SECURITY", icon: "🔒" },
    { id: "account", label: "ACCOUNT", icon: "👤" },
  ];

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        @keyframes toast-in { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        .sf { animation: fade-in 0.2s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {toast && (
        <div style={{
          position: "fixed", bottom: 20, right: 20, zIndex: 9999,
          padding: "10px 16px", borderRadius: 6, fontSize: 11, fontWeight: 500,
          background: "rgba(0,255,102,0.15)", color: "#00FF66",
          border: "1px solid rgba(0,255,102,0.3)", animation: "toast-in 0.2s ease",
        }}>
          ✓ {toast}
        </div>
      )}

      <header style={{ height: 40, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", padding: "0 16px", gap: 12, flexShrink: 0 }}>
        <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
        <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
        <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>SETTINGS</span>
      </header>

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

      <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
        <div style={{ maxWidth: 600, margin: "0 auto" }}>

          {activeTab === "general" && (
            <div className="sf" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <SectionTitle>System</SectionTitle>
              <SettingRow label="Product" value="JARVIS AI Brain" />
              <SettingRow label="Version" value="v4.0 Sovereign Network" accent />
              <SettingRow label="LLM" value={health?.model || "GROQ Llama 3.3 70B"} accent />
              <SettingRow label="Relay" value={health?.relay === "alive" ? "ONLINE" : "OFFLINE"} accent={health?.relay === "alive"} />
              <SettingRow label="TTS" value={health?.tts || "kokoro-onnx (am_michael)"} />
              <SettingRow label="Memory" value={health?.memory?.substring(0, 30) || "Checking..."} />

              <SectionTitle>Navigation</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[
                  { href: "/", label: "CHAT", desc: `${modKey()}1` },
                  { href: "/agents", label: "AGENTS", desc: `${modKey()}2` },
                  { href: "/sovereign", label: "DEVICES", desc: `${modKey()}3` },
                  { href: "/feed", label: "FEED", desc: `${modKey()}4` },
                  { href: "/workspace", label: "WORKSPACE", desc: "Console" },
                  { href: "/welcome", label: "SETUP", desc: "Onboarding" },
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
              <SettingRow label="Relay Status" value={health?.relay === "alive" ? "ONLINE" : "OFFLINE (start relay.py)"} accent={health?.relay === "alive"} />
              <SettingRow label="ARP Scan" value="Enabled — discovers all local devices" />
              <SettingRow label="Protocol" value="HTTP → MQTT → UPnP → WLED → Tapo" />
              <SettingRow label="Discovery" value="SSDP + Amazon MAC OUI lookup" />

              <SectionTitle>Credentials</SectionTitle>
              <div style={{ padding: "14px 16px", borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23" }}>
                <div style={{ fontSize: 10, color: "#9ca3af", marginBottom: 8 }}>
                  Set Tapo device credentials for smart plug control. Stored encrypted locally.
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
                  • Encrypted local vault for all credentials<br />
                  • 50+ attack vector real-time monitoring<br />
                  • Human-in-the-loop for all destructive actions
                </div>
              </div>

              <SectionTitle>Encryption</SectionTitle>
              <SettingRow label="Key Derivation" value="PBKDF2-SHA256" />
              <SettingRow label="Encryption" value="AES-256-GCM" accent />
              <SettingRow label="Vault" value="Encrypted at rest" accent />
            </div>
          )}

          {activeTab === "account" && (
            <div className="sf" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <SectionTitle>Profile</SectionTitle>
              <div style={{ padding: "16px", borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
                  <div style={{
                    width: 56, height: 56, borderRadius: "50%",
                    background: "linear-gradient(135deg, rgba(0,255,102,0.2), rgba(0,150,255,0.2))",
                    border: "2px solid rgba(0,255,102,0.3)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 22, fontWeight: 700, color: "#00FF66",
                  }}>
                    {profile?.name?.[0]?.toUpperCase() || "U"}
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{profile?.name || "User"}</div>
                    <div style={{ fontSize: 10, color: "#667085" }}>{profile?.email || "No email set"}</div>
                    <div style={{ fontSize: 9, color: "#667085", marginTop: 2 }}>
                      Member since {profile?.created ? new Date(profile.created).toLocaleDateString() : "—"}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 10, color: "#9ca3af", width: 80 }}>Name</span>
                    {editingName ? (
                      <div style={{ display: "flex", gap: 6, flex: 1 }}>
                        <input
                          value={nameInput}
                          onChange={e => setNameInput(e.target.value)}
                          onKeyDown={e => { if (e.key === "Enter") { saveProfile({ name: nameInput }); setEditingName(false); } }}
                          autoFocus
                          style={{
                            flex: 1, padding: "4px 8px", borderRadius: 4, fontSize: 11,
                            background: "#1a1d23", border: "1px solid #252830", color: "#e5e5e5",
                            fontFamily: "inherit", outline: "none",
                          }}
                        />
                        <button onClick={() => { saveProfile({ name: nameInput }); setEditingName(false); }}
                          style={{ padding: "4px 10px", borderRadius: 4, fontSize: 10, background: "rgba(0,255,102,0.15)", color: "#00FF66", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
                          Save
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                        <span style={{ fontSize: 11, color: "#e5e5e5" }}>{profile?.name || "—"}</span>
                        <button onClick={() => { setNameInput(profile?.name || ""); setEditingName(true); }}
                          style={{ padding: "2px 8px", borderRadius: 3, fontSize: 9, background: "#1a1d23", color: "#667085", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
                          Edit
                        </button>
                      </div>
                    )}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 10, color: "#9ca3af", width: 80 }}>Email</span>
                    <span style={{ fontSize: 11, color: "#e5e5e5", flex: 1 }}>{profile?.email || "Not set"}</span>
                    <button onClick={() => {
                      const email = prompt("Enter your email:", profile?.email || "");
                      if (email !== null) saveProfile({ email });
                    }}
                      style={{ padding: "2px 8px", borderRadius: 3, fontSize: 9, background: "#1a1d23", color: "#667085", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
                      Edit
                    </button>
                  </div>
                </div>
              </div>

              <SectionTitle>Local Storage</SectionTitle>
              <div style={{ padding: "14px 16px", borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 11, color: "#9ca3af" }}>Stored data</span>
                  <span style={{ fontSize: 11, color: "#e5e5e5" }}>
                    {typeof window !== "undefined" ? `${(JSON.stringify(localStorage).length / 1024).toFixed(1)} KB` : "..."}
                  </span>
                </div>
                <button onClick={() => {
                  if (confirm("Clear all local data? This cannot be undone.")) {
                    localStorage.clear();
                    showToast("Local data cleared");
                  }
                }} style={{
                  padding: "6px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                  cursor: "pointer", background: "rgba(255,51,51,0.1)", color: "#FF3333",
                  border: "1px solid rgba(255,51,51,0.2)",
                }}>
                  Clear Local Data
                </button>
              </div>

              <SectionTitle>Danger Zone</SectionTitle>
              <div style={{ padding: "14px 16px", borderRadius: 8, background: "rgba(255,51,51,0.05)", border: "1px solid rgba(255,51,51,0.15)" }}>
                <div style={{ fontSize: 10, color: "#FF3333", marginBottom: 8 }}>These actions cannot be undone.</div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={async () => {
                    if (!confirm("Reset all discovered devices?")) return;
                    try {
                      await fetch(`${BASE}/api/device/scan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: "local", reset: true }) });
                      showToast("Devices reset");
                    } catch { showToast("Reset failed"); }
                  }} style={{
                    padding: "6px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
                    cursor: "pointer", background: "rgba(255,51,51,0.1)", color: "#FF3333",
                    border: "1px solid rgba(255,51,51,0.2)",
                  }}>
                    Reset All Devices
                  </button>
                  <button onClick={async () => {
                    if (!confirm("Clear all stored credentials?")) return;
                    try {
                      await fetch(`${BASE}/api/entity/process`, {
                        method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ text: "clear all credentials", user_id: "local" }),
                      });
                      showToast("Credentials cleared");
                    } catch { showToast("Clear failed"); }
                  }} style={{
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
              await fetch(`${BASE}/api/entity/process`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  text: `set device credentials ${values.username} ${values.password}`,
                  user_id: "local",
                  session_id: "settings",
                }),
              });
              showToast("Credentials saved");
            } catch { showToast("Failed to save"); }
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
