"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { modKey } from "@/hooks/useModKey";
import { BASE, safeJson } from "@/lib/api";

type Step = "welcome" | "os-detect" | "relay" | "devices" | "permissions" | "ready";

interface OSInfo {
  platform: string;
  name: string;
  icon: string;
  relayCmd: string;
  relayCmdLabel: string;
  installNote: string;
}

const OS_MAP: Record<string, OSInfo> = {
  windows: {
    platform: "windows", name: "Windows", icon: "🪟",
    relayCmd: `curl.exe -sL '${typeof window !== "undefined" ? BASE : "https://dgfhgjhj-jarvis-ai-brain.hf.space"}/relay' -o $env:TEMP\\relay.py; python $env:TEMP\\relay.py --user`,
    relayCmdLabel: "PowerShell (Run as Admin)",
    installNote: "Windows Defender may ask for permission — allow it.",
  },
  mac: {
    platform: "mac", name: "macOS", icon: "🍎",
    relayCmd: `curl -sL '${typeof window !== "undefined" ? BASE : "https://dgfhgjhj-jarvis-ai-brain.hf.space"}/relay' | python3 - --user`,
    relayCmdLabel: "Terminal",
    installNote: "Grant Accessibility permissions when prompted.",
  },
  linux: {
    platform: "linux", name: "Linux", icon: "🐧",
    relayCmd: `curl -sL '${typeof window !== "undefined" ? BASE : "https://dgfhgjhj-jarvis-ai-brain.hf.space"}/relay' | python3 - --user`,
    relayCmdLabel: "Terminal",
    installNote: "May need sudo for full device access.",
  },
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("welcome");
  const [relayOnline, setRelayOnline] = useState(false);
  const [deviceCount, setDeviceCount] = useState(0);
  const [devices, setDevices] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const [userName, setUserName] = useState("");
  const [osInfo, setOsInfo] = useState<OSInfo>(OS_MAP.windows);
  const [stepVisible, setStepVisible] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const done = localStorage.getItem("jarvis-onboarded");
    if (done) router.push("/");
  }, [router]);

  // Detect OS from relay
  useEffect(() => {
    const detectOS = async () => {
      try {
        const res = await fetch(`${BASE}/api/device/current?user_id=local`);
        const data = await safeJson(res);
        const platform = (data.platform || "").toLowerCase();
        if (platform.includes("win")) setOsInfo(OS_MAP.windows);
        else if (platform.includes("darwin") || platform.includes("mac")) setOsInfo(OS_MAP.mac);
        else setOsInfo(OS_MAP.linux);
      } catch {
        // Try to detect from user agent
        const ua = navigator.userAgent.toLowerCase();
        if (ua.includes("win")) setOsInfo(OS_MAP.windows);
        else if (ua.includes("mac")) setOsInfo(OS_MAP.mac);
        else setOsInfo(OS_MAP.linux);
      }
    };
    detectOS();
  }, []);

  const checkRelay = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/health`);
        const data = await safeJson(res);
      setRelayOnline(!!data.relay);
      return !!data.relay;
    } catch { return false; }
  }, []);

  useEffect(() => {
    if (step !== "relay") return;
    const i = setInterval(async () => {
      const online = await checkRelay();
      if (online) setTimeout(() => transitionTo("devices"), 600);
    }, 3000);
    checkRelay();
    return () => clearInterval(i);
  }, [step, checkRelay]);

  const transitionTo = (next: Step) => {
    setStepVisible(false);
    setTimeout(() => { setStep(next); setStepVisible(true); }, 300);
  };

  const scanDevices = async () => {
    setScanning(true);
    try {
      await fetch(`${BASE}/api/relay/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }),
      });
      await new Promise(r => setTimeout(r, 5000));
      const res = await fetch(`${BASE}/api/relay/devices?user_id=local`);
        const data = await safeJson(res);
      setDevices(data.devices || []);
      setDeviceCount((data.devices || []).length);
    } catch {}
    setScanning(false);
  };

  const completeOnboarding = () => {
    localStorage.setItem("jarvis-onboarded", "1");
    if (userName) localStorage.setItem("jarvis-user", JSON.stringify({ name: userName, email: `${userName.toLowerCase()}@jarvis.local` }));
    router.push("/");
  };

  const copyCommand = () => {
    const cmd = `${osInfo.relayCmd} ${userName || "local"}`;
    navigator.clipboard.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const stepIndex = { welcome: 0, "os-detect": 1, relay: 2, devices: 3, permissions: 4, ready: 5 }[step];

  return (
    <div style={{
      height: "100dvh", display: "flex", flexDirection: "column",
      background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace",
      alignItems: "center", justifyContent: "center", position: "relative", overflow: "hidden",
    }}>
      {/* Animated background */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(0,255,102,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,102,0.03) 1px, transparent 1px)",
        backgroundSize: "40px 40px", opacity: 0.4,
      }} />
      <div style={{
        position: "absolute", top: "20%", left: "50%", transform: "translate(-50%, -50%)",
        width: 600, height: 600, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(0,255,102,0.04) 0%, transparent 60%)",
        pointerEvents: "none",
      }} />

      <style jsx>{`
        @keyframes step-in { from { opacity:0; transform:translateY(24px) scale(0.95); filter:blur(4px); } to { opacity:1; transform:translateY(0) scale(1); filter:blur(0); } }
        @keyframes step-out { from { opacity:1; transform:translateY(0) scale(1); } to { opacity:0; transform:translateY(-16px) scale(0.97); filter:blur(2px); } }
        @keyframes pulse-dot { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.3; transform:scale(0.85); } }
        @keyframes scan-sweep { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes check-pop { 0% { transform: scale(0) rotate(-45deg); } 60% { transform: scale(1.15) rotate(5deg); } 100% { transform: scale(1) rotate(0); } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
        @keyframes glow-breathe { 0%,100% { box-shadow: 0 0 20px rgba(0,255,102,0.2); } 50% { box-shadow: 0 0 40px rgba(0,255,102,0.4); } }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
        @keyframes ring-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes ring-spin-reverse { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
        .step-enter { animation: step-in 0.5s cubic-bezier(0.16,1,0.3,1) both; }
        .step-exit { animation: step-out 0.3s cubic-bezier(0.16,1,0.3,1) both; }
        .pulse { animation: pulse-dot 1.5s ease-in-out infinite; }
        .sweep { animation: scan-sweep 2s linear infinite; }
        .check { animation: check-pop 0.5s cubic-bezier(0.16,1,0.3,1) both; }
        .shimmer { background: linear-gradient(90deg, transparent 0%, rgba(0,255,102,0.08) 50%, transparent 100%); background-size: 200% 100%; animation: shimmer 2s linear infinite; }
        .glow { animation: glow-breathe 3s ease-in-out infinite; }
        .float { animation: float 3s ease-in-out infinite; }
        .ring { animation: ring-spin 8s linear infinite; }
        .ring-rev { animation: ring-spin-reverse 6s linear infinite; }
      `}</style>

      {/* Progress bar */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: "#0d0f12" }}>
        <div style={{
          height: "100%", background: "linear-gradient(90deg, #00FF66, #00B4D8)",
          transition: "width 0.6s cubic-bezier(0.16,1,0.3,1)",
          width: `${((stepIndex + 1) / 6) * 100}%`,
          boxShadow: "0 0 12px rgba(0,255,102,0.4)",
        }} />
      </div>

      {/* Step indicators */}
      <div style={{ position: "absolute", top: 24, display: "flex", gap: 6, alignItems: "center" }}>
        {["welcome", "os", "relay", "devices", "permissions", "ready"].map((s, i) => (
          <div key={s} style={{
            width: i <= stepIndex ? 20 : 6, height: 6, borderRadius: 3,
            transition: "all 0.4s cubic-bezier(0.16,1,0.3,1)",
            background: i <= stepIndex ? "#00FF66" : "#1a1d23",
            boxShadow: i === stepIndex ? "0 0 8px rgba(0,255,102,0.5)" : "none",
          }} />
        ))}
      </div>

      {/* Step content */}
      <div style={{ opacity: stepVisible ? 1 : 0, transform: stepVisible ? "translateY(0)" : "translateY(-16px)", transition: "all 0.3s cubic-bezier(0.16,1,0.3,1)" }}>

        {/* ═══ WELCOME ═══ */}
        {step === "welcome" && (
          <div className="step-enter" style={{ textAlign: "center", maxWidth: 500, padding: 32 }}>
            {/* Animated orb */}
            <div className="float" style={{ marginBottom: 32, display: "flex", justifyContent: "center" }}>
              <div style={{ width: 140, height: 140, position: "relative" }}>
                <div className="ring" style={{ position: "absolute", inset: 0, borderRadius: "50%", border: "1px solid rgba(0,255,102,0.12)" }} />
                <div className="ring-rev" style={{ position: "absolute", inset: 18, borderRadius: "50%", border: "1px solid rgba(0,255,102,0.18)" }} />
                <div className="ring" style={{ position: "absolute", inset: 36, borderRadius: "50%", border: "1px dashed rgba(0,255,102,0.1)", animationDuration: "12s" }} />
                <div style={{
                  position: "absolute", inset: 48, borderRadius: "50%",
                  background: "radial-gradient(circle, rgba(0,255,102,0.15) 0%, transparent 70%)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <div className="glow" style={{ width: 20, height: 20, borderRadius: "50%", background: "#00FF66" }} />
                </div>
              </div>
            </div>

            <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 6, letterSpacing: "0.12em", background: "linear-gradient(135deg, #00FF66, #00B4D8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              JARVIS
            </div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 8, letterSpacing: "0.2em" }}>SOVEREIGN NETWORK ORCHESTRATOR</div>
            <div style={{ fontSize: 11, color: "#5f6368", marginBottom: 28, lineHeight: 1.7, maxWidth: 360, margin: "0 auto 28px" }}>
              Your AI brain. Control every device, automate every task, own your intelligence.
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center", marginBottom: 32 }}>
              {["Real Device Control", "Autonomous Agents", "Encrypted Vault", "Zero Cloud"].map((f, i) => (
                <span key={f} style={{
                  padding: "5px 14px", borderRadius: 20, fontSize: 9, letterSpacing: "0.04em",
                  background: "rgba(0,255,102,0.06)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.12)",
                  animation: `step-in 0.4s cubic-bezier(0.16,1,0.3,1) ${0.1 + i * 0.08}s both`,
                }}>
                  {f}
                </span>
              ))}
            </div>

            <input
              value={userName}
              onChange={e => setUserName(e.target.value)}
              placeholder="What should I call you?"
              style={{
                width: 280, padding: "12px 18px", borderRadius: 8, fontSize: 13,
                background: "#0d0f12", color: "#e5e5e5", fontFamily: "inherit",
                border: "1px solid #1a1d23", outline: "none", textAlign: "center",
                transition: "border-color 0.3s",
              }}
              onFocus={e => e.target.style.borderColor = "rgba(0,255,102,0.3)"}
              onBlur={e => e.target.style.borderColor = "#1a1d23"}
              onKeyDown={e => e.key === "Enter" && transitionTo("os-detect")}
            />

            <button onClick={() => transitionTo("os-detect")} style={{
              marginTop: 20, padding: "14px 40px", borderRadius: 8, fontSize: 12, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", letterSpacing: "0.1em", transition: "all 0.2s",
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 30px rgba(0,255,102,0.3)"; }}
            onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "none"; }}
            >
              BEGIN SETUP →
            </button>
          </div>
        )}

        {/* ═══ OS DETECT ═══ */}
        {step === "os-detect" && (
          <div className="step-enter" style={{ textAlign: "center", maxWidth: 500, padding: 32 }}>
            <div className="check" style={{
              width: 64, height: 64, borderRadius: 16, margin: "0 auto 20px",
              background: "rgba(0,255,102,0.08)", border: "1px solid rgba(0,255,102,0.2)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32,
            }}>
              {osInfo.icon}
            </div>

            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
              Detected: {osInfo.name}
            </div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 24, lineHeight: 1.6 }}>
              I'll tailor the setup for your operating system.
            </div>

            <div style={{
              background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
              padding: 16, marginBottom: 20, textAlign: "left",
            }}>
              <div style={{ fontSize: 8, color: "#667085", marginBottom: 8, letterSpacing: "0.1em" }}>
                {osInfo.relayCmdLabel}
              </div>
              <code style={{ fontSize: 10, color: "#00FF66", lineHeight: 1.6, display: "block", wordBreak: "break-all" }}>
                {osInfo.relayCmd} {userName || "local"}
              </code>
            </div>

            <div style={{ fontSize: 9, color: "#FFB300", marginBottom: 20, padding: "8px 12px", borderRadius: 6, background: "rgba(255,179,0,0.06)", border: "1px solid rgba(255,179,0,0.15)" }}>
              {osInfo.installNote}
            </div>

            <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
              <button onClick={() => transitionTo("relay")} style={{
                padding: "10px 28px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
                border: "none", letterSpacing: "0.06em",
              }}>
                CONTINUE
              </button>
              <button onClick={() => transitionTo("relay")} style={{
                padding: "10px 20px", borderRadius: 6, fontSize: 9,
                fontFamily: "inherit", cursor: "pointer", background: "transparent",
                color: "#667085", border: "1px solid #1a1d23",
              }}>
                Skip
              </button>
            </div>
          </div>
        )}

        {/* ═══ RELAY PAIRING ═══ */}
        {step === "relay" && (
          <div className="step-enter" style={{ textAlign: "center", maxWidth: 520, padding: 32 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Connect Your Machine</div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 20 }}>
              Run this in your {osInfo.name} {osInfo.relayCmdLabel}:
            </div>

            <div style={{
              background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
              padding: 16, marginBottom: 16, textAlign: "left", position: "relative",
            }}>
              <div style={{ fontSize: 8, color: "#667085", marginBottom: 8, letterSpacing: "0.1em" }}>
                {osInfo.relayCmdLabel}
              </div>
              <code style={{ fontSize: 10, color: "#00FF66", lineHeight: 1.6, display: "block", wordBreak: "break-all" }}>
                {osInfo.relayCmd} {userName || "local"}
              </code>
              <button onClick={copyCommand} style={{
                position: "absolute", top: 8, right: 8, padding: "4px 10px", borderRadius: 4,
                background: copied ? "rgba(0,255,102,0.15)" : "rgba(255,255,255,0.05)",
                border: `1px solid ${copied ? "rgba(0,255,102,0.3)" : "rgba(255,255,255,0.08)"}`,
                color: copied ? "#00FF66" : "#667085", fontSize: 8, fontFamily: "inherit",
                cursor: "pointer", transition: "all 0.2s",
              }}>
                {copied ? "COPIED" : "COPY"}
              </button>
            </div>

            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "14px 24px", borderRadius: 8,
              background: relayOnline ? "rgba(0,255,102,0.06)" : "rgba(255,179,0,0.06)",
              border: `1px solid ${relayOnline ? "rgba(0,255,102,0.2)" : "rgba(255,179,0,0.15)"}`,
              transition: "all 0.4s",
            }}>
              <div className={relayOnline ? "check" : "pulse"} style={{
                width: 10, height: 10, borderRadius: "50%",
                background: relayOnline ? "#00FF66" : "#FFB300",
                boxShadow: `0 0 10px ${relayOnline ? "rgba(0,255,102,0.5)" : "rgba(255,179,0,0.4)"}`,
              }} />
              <span style={{ fontSize: 11, fontWeight: 500, color: relayOnline ? "#00FF66" : "#FFB300" }}>
                {relayOnline ? "RELAY CONNECTED" : "Waiting for relay connection..."}
              </span>
            </div>

            <div style={{ marginTop: 12, fontSize: 8, color: "#5f6368" }}>
              Auto-checking every 3 seconds
            </div>

            <button onClick={() => transitionTo("devices")} style={{
              marginTop: 20, padding: "8px 20px", borderRadius: 4, fontSize: 9,
              fontFamily: "inherit", cursor: "pointer", background: "transparent",
              color: "#667085", border: "1px solid #1a1d23",
            }}>
              Skip for now →
            </button>
          </div>
        )}

        {/* ═══ DEVICE DISCOVERY ═══ */}
        {step === "devices" && (
          <div className="step-enter" style={{ textAlign: "center", maxWidth: 540, padding: 32 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Discover Your Network</div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>
              Scan for smart plugs, speakers, phones, and more.
            </div>

            {!scanning && devices.length === 0 && (
              <button onClick={scanDevices} style={{
                padding: "14px 32px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
                border: "none", letterSpacing: "0.08em", transition: "all 0.2s",
              }}
              onMouseEnter={e => e.currentTarget.style.boxShadow = "0 8px 30px rgba(0,255,102,0.3)"}
              onMouseLeave={e => e.currentTarget.style.boxShadow = "none"}
              >
                SCAN NETWORK
              </button>
            )}

            {scanning && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
                <div style={{ width: 70, height: 70, position: "relative" }}>
                  <div className="sweep" style={{ position: "absolute", inset: 0, borderRadius: "50%", border: "2px solid transparent", borderTopColor: "#00FF66", borderRightColor: "rgba(0,255,102,0.3)" }} />
                  <div style={{ position: "absolute", inset: 12, borderRadius: "50%", border: "1px solid rgba(0,255,102,0.15)" }} />
                  <div style={{ position: "absolute", inset: 24, borderRadius: "50%", background: "rgba(0,255,102,0.05)" }} />
                </div>
                <div style={{ fontSize: 12, color: "#FFB300", fontWeight: 500 }}>Scanning network...</div>
                <div className="shimmer" style={{ width: 200, height: 3, borderRadius: 2 }} />
                <div style={{ fontSize: 8, color: "#5f6368" }}>ARP sweep + port scan + UPnP discovery</div>
              </div>
            )}

            {devices.length > 0 && (
              <div style={{ textAlign: "left" }}>
                <div style={{ fontSize: 9, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 10 }}>
                  FOUND {devices.length} DEVICE{devices.length !== 1 ? "S" : ""}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 20, maxHeight: 240, overflowY: "auto" }}>
                  {devices.map((d, i) => (
                    <div key={i} style={{
                      padding: "10px 12px", borderRadius: 6, background: "#0d0f12",
                      border: "1px solid #1a1d23", display: "flex", alignItems: "center", gap: 8,
                      animation: `step-in 0.3s cubic-bezier(0.16,1,0.3,1) ${i * 0.05}s both`,
                    }}>
                      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66", flexShrink: 0 }} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 10, color: "#e5e5e5", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name || d.ip}</div>
                        <div style={{ fontSize: 8, color: "#667085" }}>{d.ip} · {d.type || "device"}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <button onClick={() => transitionTo("permissions")} style={{
                  width: "100%", padding: "12px 0", borderRadius: 8, fontSize: 11, fontWeight: 600,
                  fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
                  border: "none", letterSpacing: "0.06em",
                }}>
                  CONTINUE ({devices.length} devices)
                </button>
              </div>
            )}

            {!scanning && devices.length === 0 && (
              <button onClick={() => transitionTo("permissions")} style={{
                marginTop: 16, padding: "8px 20px", borderRadius: 4, fontSize: 9,
                fontFamily: "inherit", cursor: "pointer", background: "transparent",
                color: "#667085", border: "1px solid #1a1d23",
              }}>
                Skip — I'll scan later
              </button>
            )}
          </div>
        )}

        {/* ═══ PERMISSIONS ═══ */}
        {step === "permissions" && (
          <div className="step-enter" style={{ textAlign: "center", maxWidth: 500, padding: 32 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>System Permissions</div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>
              JARVIS needs these to control your {osInfo.name} system.
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24, textAlign: "left" }}>
              {[
                { name: "Accessibility", desc: "Keyboard/mouse automation", icon: "⌨️", required: osInfo.platform !== "windows" },
                { name: "Screen Recording", desc: "Screenshot & vision", icon: "🖥", required: osInfo.platform === "mac" },
                { name: "Network Access", desc: "Device discovery & control", icon: "🌐", required: true },
                { name: "Notifications", desc: "Proactive alerts", icon: "🔔", required: false },
              ].map((perm, i) => (
                <div key={perm.name} style={{
                  padding: "12px 16px", borderRadius: 8, background: "#0d0f12",
                  border: "1px solid #1a1d23", display: "flex", alignItems: "center", gap: 12,
                  animation: `step-in 0.4s cubic-bezier(0.16,1,0.3,1) ${i * 0.08}s both`,
                }}>
                  <span style={{ fontSize: 18 }}>{perm.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 2 }}>{perm.name}</div>
                    <div style={{ fontSize: 9, color: "#667085" }}>{perm.desc}</div>
                  </div>
                  <span style={{
                    fontSize: 7, padding: "2px 8px", borderRadius: 10,
                    background: perm.required ? "rgba(255,179,0,0.1)" : "rgba(102,112,133,0.1)",
                    color: perm.required ? "#FFB300" : "#667085", border: `1px solid ${perm.required ? "rgba(255,179,0,0.2)" : "rgba(102,112,133,0.15)"}`,
                  }}>
                    {perm.required ? "REQUIRED" : "OPTIONAL"}
                  </span>
                </div>
              ))}
            </div>

            <button onClick={() => transitionTo("ready")} style={{
              padding: "12px 32px", borderRadius: 8, fontSize: 11, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", letterSpacing: "0.06em",
            }}>
              GRANT & CONTINUE
            </button>
          </div>
        )}

        {/* ═══ READY ═══ */}
        {step === "ready" && (
          <div className="step-enter" style={{ textAlign: "center", maxWidth: 500, padding: 32 }}>
            <div className="check glow" style={{
              width: 72, height: 72, borderRadius: "50%", margin: "0 auto 24px",
              background: "rgba(0,255,102,0.08)", border: "2px solid #00FF66",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32,
            }}>
              ✓
            </div>

            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>
              {userName ? `Welcome, ${userName}` : "You're All Set"}
            </div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 28, lineHeight: 1.6 }}>
              JARVIS is ready. Press <span style={{ color: "#00FF66", fontWeight: 600 }}>{modKey()}K</span> anywhere for commands.
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 24, textAlign: "left" }}>
              {[
                { icon: "💬", label: "Start Chatting", desc: "Ask me anything", action: "/" },
                { icon: "🤖", label: "Spawn Agent", desc: "Run autonomous tasks", action: "/agents" },
                { icon: "📡", label: "Control Devices", desc: "Manage your network", action: "/sovereign" },
                { icon: "🖥", label: "Virtual Desktop", desc: "Headless workstation", action: "/" },
              ].map((card, i) => (
                <div key={card.label} style={{
                  padding: "14px 16px", borderRadius: 8, background: "#0d0f12",
                  border: "1px solid #1a1d23", cursor: "pointer", transition: "all 0.2s",
                  animation: `step-in 0.4s cubic-bezier(0.16,1,0.3,1) ${0.1 + i * 0.08}s both`,
                }}
                onClick={() => { localStorage.setItem("jarvis-onboarded", "1"); router.push(card.action); }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(0,255,102,0.2)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "#1a1d23"; e.currentTarget.style.transform = "translateY(0)"; }}
                >
                  <div style={{ fontSize: 18, marginBottom: 6 }}>{card.icon}</div>
                  <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 2 }}>{card.label}</div>
                  <div style={{ fontSize: 9, color: "#667085" }}>{card.desc}</div>
                </div>
              ))}
            </div>

            <button onClick={completeOnboarding} style={{
              padding: "14px 40px", borderRadius: 8, fontSize: 12, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", letterSpacing: "0.1em", transition: "all 0.2s",
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 30px rgba(0,255,102,0.3)"; }}
            onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "none"; }}
            >
              LAUNCH JARVIS →
            </button>
          </div>
        )}
      </div>

      {/* Bottom branding */}
      <div style={{ position: "absolute", bottom: 20, fontSize: 8, color: "#333", letterSpacing: "0.1em" }}>
        JARVIS v3.0 · SOVEREIGN NETWORK ORCHESTRATOR
      </div>
    </div>
  );
}
