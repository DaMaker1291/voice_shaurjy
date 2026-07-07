"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

type Step = "welcome" | "relay" | "devices" | "ready";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("welcome");
  const [relayOnline, setRelayOnline] = useState(false);
  const [deviceCount, setDeviceCount] = useState(0);
  const [devices, setDevices] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const [userName, setUserName] = useState("");
  const [progress, setProgress] = useState(0);
  const [checking, setChecking] = useState(false);

  // Check if already onboarded
  useEffect(() => {
    const done = localStorage.getItem("jarvis-onboarded");
    if (done) router.push("/");
  }, [router]);

  // Check relay status
  const checkRelay = useCallback(async () => {
    setChecking(true);
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      setRelayOnline(!!data.relay);
      return !!data.relay;
    } catch { return false; }
    setChecking(false);
  }, []);

  // Auto-check relay on relay step
  useEffect(() => {
    if (step !== "relay") return;
    const i = setInterval(async () => {
      const online = await checkRelay();
      if (online) {
        setProgress(100);
        setTimeout(() => setStep("devices"), 800);
      }
    }, 3000);
    checkRelay();
    return () => clearInterval(i);
  }, [step, checkRelay]);

  // Scan devices
  const scanDevices = async () => {
    setScanning(true);
    try {
      // Trigger scan on backend
      await fetch("/api/relay/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }),
      });
      // Wait for scan
      await new Promise(r => setTimeout(r, 5000));
      // Fetch results
      const res = await fetch("/api/relay/devices?user_id=local");
      const data = await res.json();
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

  const stepIndex = { welcome: 0, relay: 1, devices: 2, ready: 3 }[step];

  return (
    <div style={{
      height: "100vh", display: "flex", flexDirection: "column",
      background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace",
      alignItems: "center", justifyContent: "center", position: "relative",
    }}>
      {/* Background grid */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.4,
        backgroundImage: "linear-gradient(rgba(0,255,102,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,102,0.03) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      {/* Ambient glow */}
      <div style={{
        position: "absolute", top: "20%", left: "50%", transform: "translate(-50%, -50%)",
        width: 600, height: 600, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(0,255,102,0.04) 0%, transparent 60%)",
        pointerEvents: "none",
      }} />

      <style jsx>{`
        @keyframes step-in { from { opacity:0; transform:translateY(20px) scale(0.96); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes pulse-dot { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
        @keyframes scan-sweep { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes check-pop { 0% { transform: scale(0); } 50% { transform: scale(1.2); } 100% { transform: scale(1); } }
        .step-anim { animation: step-in 0.5s cubic-bezier(0.16,1,0.3,1) both; }
        .pulse { animation: pulse-dot 1.5s ease-in-out infinite; }
        .sweep { animation: scan-sweep 2s linear infinite; }
        .check { animation: check-pop 0.4s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Progress dots */}
      <div style={{ position: "absolute", top: 32, display: "flex", gap: 8 }}>
        {["welcome", "relay", "devices", "ready"].map((s, i) => (
          <div key={s} style={{
            width: i <= stepIndex ? 24 : 8, height: 8, borderRadius: 4, transition: "all 0.3s",
            background: i <= stepIndex ? "#00FF66" : "#1a1d23",
            boxShadow: i === stepIndex ? "0 0 8px rgba(0,255,102,0.4)" : "none",
          }} />
        ))}
      </div>

      {/* Step: Welcome */}
      {step === "welcome" && (
        <div className="step-anim" style={{ textAlign: "center", maxWidth: 480, padding: 32 }}>
          {/* Orb */}
          <div style={{ marginBottom: 28, display: "flex", justifyContent: "center" }}>
            <div style={{ width: 120, height: 120, position: "relative" }}>
              {/* Outer ring */}
              <div style={{
                position: "absolute", inset: 0, borderRadius: "50%",
                border: "1px solid rgba(0,255,102,0.15)", animation: "sweep 4s linear infinite",
              }} />
              {/* Middle ring */}
              <div style={{
                position: "absolute", inset: 15, borderRadius: "50%",
                border: "1px solid rgba(0,255,102,0.2)",
                animation: "sweep 3s linear infinite reverse",
              }} />
              {/* Core */}
              <div style={{
                position: "absolute", inset: 35, borderRadius: "50%",
                background: "radial-gradient(circle, rgba(0,255,102,0.2) 0%, transparent 70%)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 20px rgba(0,255,102,0.6)" }} />
              </div>
            </div>
          </div>

          <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 8, letterSpacing: "0.08em" }}>JARVIS</div>
          <div style={{ fontSize: 11, color: "#667085", marginBottom: 24, lineHeight: 1.6 }}>
            Your sovereign AI brain.<br />
            Control every device. Automate every task. Own your intelligence.
          </div>

          {/* Feature pills */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center", marginBottom: 32 }}>
            {["Real Device Control", "Autonomous Agents", "Encrypted Vault", "Zero Cloud Dependency"].map(f => (
              <span key={f} style={{
                padding: "4px 12px", borderRadius: 20, fontSize: 9, letterSpacing: "0.04em",
                background: "rgba(0,255,102,0.08)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.15)",
              }}>
                {f}
              </span>
            ))}
          </div>

          <div style={{ marginBottom: 16 }}>
            <input
              value={userName}
              onChange={e => setUserName(e.target.value)}
              placeholder="What should I call you?"
              style={{
                width: 260, padding: "10px 16px", borderRadius: 6, fontSize: 12,
                background: "#0d0f12", color: "#e5e5e5", fontFamily: "inherit",
                border: "1px solid #1a1d23", outline: "none", textAlign: "center",
              }}
              onKeyDown={e => e.key === "Enter" && setStep("relay")}
            />
          </div>

          <button onClick={() => setStep("relay")} style={{
            padding: "12px 32px", borderRadius: 6, fontSize: 11, fontWeight: 600,
            fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
            border: "none", letterSpacing: "0.08em",
          }}>
            BEGIN SETUP →
          </button>
        </div>
      )}

      {/* Step: Relay Pairing */}
      {step === "relay" && (
        <div className="step-anim" style={{ textAlign: "center", maxWidth: 480, padding: 32 }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Connect Your Machine</div>
          <div style={{ fontSize: 10, color: "#667085", marginBottom: 24, lineHeight: 1.6 }}>
            Run this command on your Mac to pair your devices:
          </div>

          {/* Command box */}
          <div style={{
            background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
            padding: 16, marginBottom: 16, textAlign: "left",
          }}>
            <div style={{ fontSize: 8, color: "#667085", marginBottom: 8, letterSpacing: "0.08em" }}>TERMINAL</div>
            <code style={{ fontSize: 11, color: "#00FF66", lineHeight: 1.6, display: "block", whiteSpace: "pre-wrap" }}>
              curl -sL 'https://dgfhgjhj-jarvis-ai-brain.hf.space/relay'<br />
              {"  "}| python3 - --user {userName || "your_username"}
            </code>
          </div>

          {/* Status */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            padding: "12px 20px", borderRadius: 6,
            background: relayOnline ? "rgba(0,255,102,0.08)" : "rgba(255,179,0,0.08)",
            border: `1px solid ${relayOnline ? "rgba(0,255,102,0.2)" : "rgba(255,179,0,0.2)"}`,
          }}>
            <div className={relayOnline ? "check" : "pulse"} style={{
              width: 8, height: 8, borderRadius: "50%",
              background: relayOnline ? "#00FF66" : "#FFB300",
              boxShadow: `0 0 8px ${relayOnline ? "rgba(0,255,102,0.4)" : "rgba(255,179,0,0.4)"}`,
            }} />
            <span style={{ fontSize: 10, color: relayOnline ? "#00FF66" : "#FFB300" }}>
              {relayOnline ? "RELAY CONNECTED" : "Waiting for relay..."}
            </span>
          </div>

          <div style={{ marginTop: 16, fontSize: 9, color: "#667085" }}>
            Auto-checking every 3 seconds
          </div>

          <button onClick={() => setStep("devices")} style={{
            marginTop: 20, padding: "8px 20px", borderRadius: 4, fontSize: 9,
            fontFamily: "inherit", cursor: "pointer", background: "transparent",
            color: "#667085", border: "1px solid #1a1d23",
          }}>
            Skip for now →
          </button>
        </div>
      )}

      {/* Step: Device Discovery */}
      {step === "devices" && (
        <div className="step-anim" style={{ textAlign: "center", maxWidth: 520, padding: 32 }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Discover Your Network</div>
          <div style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>
            Scan for all WiFi devices — smart plugs, speakers, phones, and more.
          </div>

          {!scanning && devices.length === 0 && (
            <button onClick={scanDevices} style={{
              padding: "12px 28px", borderRadius: 6, fontSize: 11, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", letterSpacing: "0.08em",
            }}>
              SCAN NETWORK
            </button>
          )}

          {scanning && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div style={{ width: 60, height: 60, position: "relative" }}>
                <div className="sweep" style={{
                  position: "absolute", inset: 0, borderRadius: "50%",
                  border: "2px solid transparent",
                  borderTopColor: "#00FF66",
                }} />
                <div style={{
                  position: "absolute", inset: 15, borderRadius: "50%",
                  border: "1px solid rgba(0,255,102,0.2)",
                }} />
              </div>
              <div style={{ fontSize: 11, color: "#FFB300" }}>Scanning network...</div>
              <div style={{ fontSize: 9, color: "#667085" }}>ARP sweep + port scan + UPnP discovery</div>
            </div>
          )}

          {devices.length > 0 && (
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: 9, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>
                FOUND {devices.length} DEVICE{devices.length !== 1 ? "S" : ""}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 20 }}>
                {devices.map((d, i) => (
                  <div key={i} style={{
                    padding: "10px 12px", borderRadius: 6, background: "#0d0f12",
                    border: "1px solid #1a1d23", display: "flex", alignItems: "center", gap: 8,
                  }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66" }} />
                    <div>
                      <div style={{ fontSize: 10, color: "#e5e5e5" }}>{d.name || d.ip}</div>
                      <div style={{ fontSize: 8, color: "#667085" }}>{d.ip} · {d.type || "unknown"}</div>
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={() => setStep("ready")} style={{
                width: "100%", padding: "12px 0", borderRadius: 6, fontSize: 11, fontWeight: 600,
                fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
                border: "none", letterSpacing: "0.08em",
              }}>
                CONTINUE ({devices.length} devices found)
              </button>
            </div>
          )}

          {!scanning && devices.length === 0 && (
            <div style={{ marginTop: 16 }}>
              <button onClick={() => setStep("ready")} style={{
                padding: "8px 20px", borderRadius: 4, fontSize: 9,
                fontFamily: "inherit", cursor: "pointer", background: "transparent",
                color: "#667085", border: "1px solid #1a1d23",
              }}>
                Skip — I'll scan later
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step: Ready */}
      {step === "ready" && (
        <div className="step-anim" style={{ textAlign: "center", maxWidth: 480, padding: 32 }}>
          <div style={{
            width: 64, height: 64, borderRadius: "50%", margin: "0 auto 20px",
            background: "rgba(0,255,102,0.1)", border: "2px solid #00FF66",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 30px rgba(0,255,102,0.2)",
          }}>
            <div className="check" style={{ fontSize: 28 }}>✓</div>
          </div>

          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>You're All Set</div>
          <div style={{ fontSize: 10, color: "#667085", marginBottom: 24, lineHeight: 1.6 }}>
            JARVIS is ready. Press <span style={{ color: "#00FF66" }}>⌘K</span> anywhere for commands.
          </div>

          {/* Quick start cards */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 24, textAlign: "left" }}>
            {[
              { icon: "💬", label: "Start Chatting", desc: "Ask me anything", action: "/" },
              { icon: "🤖", label: "Spawn Agent", desc: "Run autonomous tasks", action: "/agents" },
              { icon: "📡", label: "Control Devices", desc: "Manage your network", action: "/sovereign" },
              { icon: "📋", label: "View Feed", desc: "See all events", action: "/feed" },
            ].map(card => (
              <div key={card.label} style={{
                padding: "12px 14px", borderRadius: 8, background: "#0d0f12",
                border: "1px solid #1a1d23", cursor: "pointer", transition: "all 0.15s",
              }} onClick={() => { localStorage.setItem("jarvis-onboarded", "1"); router.push(card.action); }}>
                <div style={{ fontSize: 16, marginBottom: 6 }}>{card.icon}</div>
                <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 2 }}>{card.label}</div>
                <div style={{ fontSize: 9, color: "#667085" }}>{card.desc}</div>
              </div>
            ))}
          </div>

          <button onClick={completeOnboarding} style={{
            padding: "12px 32px", borderRadius: 6, fontSize: 11, fontWeight: 600,
            fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
            border: "none", letterSpacing: "0.08em",
          }}>
            ENTER JARVIS →
          </button>
        </div>
      )}
    </div>
  );
}
