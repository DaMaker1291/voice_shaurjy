"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const STEPS = [
  {
    id: "welcome",
    title: "Welcome to J.A.R.V.I.S.",
    subtitle: "Your sovereign AI command center",
    icon: "⬡",
  },
  {
    id: "relay",
    title: "Connect Your Machine",
    subtitle: "Install the relay agent to control your devices",
    icon: "🔗",
  },
  {
    id: "devices",
    title: "Discover Devices",
    subtitle: "Scan your network for smart devices",
    icon: "📡",
  },
  {
    id: "done",
    title: "System Ready",
    subtitle: "All systems operational",
    icon: "✓",
  },
];

export default function WelcomePage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [devicesFound, setDevicesFound] = useState(0);
  const [relayConnected, setRelayConnected] = useState(false);
  const [glitch, setGlitch] = useState(false);

  useEffect(() => {
    const i = setInterval(async () => {
      try {
        const res = await fetch("/api/relay/devices");
        const data = await res.json();
        const online = data.devices?.filter((d: any) => d.is_online)?.length || 0;
        setRelayConnected(online > 0);
      } catch {}
    }, 2000);
    return () => clearInterval(i);
  }, []);

  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await fetch("/api/scan/full", { method: "POST" });
      const data = await res.json();
      setDevicesFound(data.count || 0);
    } catch {}
    setScanning(false);
    setTimeout(() => setStep(3), 1500);
  };

  const skip = () => router.push("/");

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
      position: "relative", overflow: "hidden",
    }}>
      {/* Ambient grid */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.03,
        backgroundImage: "linear-gradient(rgba(0,255,102,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,102,0.3) 1px, transparent 1px)",
        backgroundSize: "60px 60px",
      }} />

      {/* Radial glow */}
      <div style={{
        position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
        width: 600, height: 600, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(0,255,102,0.06) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      <div style={{ position: "relative", zIndex: 1, width: "100%", maxWidth: 480, padding: "0 24px" }}>
        {/* Progress dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 40 }}>
          {STEPS.map((s, i) => (
            <div key={s.id} style={{
              width: i === step ? 24 : 6, height: 6, borderRadius: 3,
              background: i <= step ? "#00FF66" : "#1a1d23",
              transition: "all 0.4s cubic-bezier(0.16,1,0.3,1)",
            }} />
          ))}
        </div>

        {/* Icon */}
        <div style={{
          textAlign: "center", fontSize: 48, marginBottom: 24,
          animation: "pulse 2s ease-in-out infinite",
        }}>
          {STEPS[step].icon}
        </div>

        {/* Title */}
        <h1 style={{
          textAlign: "center", fontSize: 24, fontWeight: 700, marginBottom: 8,
          background: "linear-gradient(135deg, #00FF66, #FFB300)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          letterSpacing: "-0.02em",
        }}>
          {STEPS[step].title}
        </h1>
        <p style={{ textAlign: "center", fontSize: 13, color: "#667085", marginBottom: 32 }}>
          {STEPS[step].subtitle}
        </p>

        {/* Step content */}
        {step === 0 && (
          <div style={{ textAlign: "center" }}>
            <div style={{
              padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23",
              marginBottom: 24, fontSize: 12, color: "#667085", lineHeight: 1.8,
            }}>
              <div style={{ color: "#00FF66", marginBottom: 8, fontWeight: 600 }}>CAPABILITIES</div>
              <div>⬡ Autonomous AI agents — never stop until task is done</div>
              <div>⬡ Control all WiFi devices — Echo, Tapo, Hue, WLED, gates</div>
              <div>⬡ Headless browser automation — no mouse hijacking</div>
              <div>⬡ Email scanning — flights, check-ins, passport photos</div>
              <div>⬡ Parallel task execution — run multiple agents</div>
            </div>
            <button onClick={() => setStep(1)} style={{
              width: "100%", padding: "12px 0", borderRadius: 6, fontSize: 12, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", letterSpacing: "0.05em",
            }}>
              BEGIN SETUP →
            </button>
            <button onClick={skip} style={{
              width: "100%", padding: "10px 0", marginTop: 8, borderRadius: 6, fontSize: 11,
              fontFamily: "inherit", cursor: "pointer", background: "transparent", color: "#667085",
              border: "1px solid #1a1d23",
            }}>
              Skip for now
            </button>
          </div>
        )}

        {step === 1 && (
          <div>
            <div style={{
              padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23",
              marginBottom: 16,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: relayConnected ? "#00FF66" : "#FF3333" }} />
                <span style={{ fontSize: 11, color: relayConnected ? "#00FF66" : "#FF3333", fontWeight: 600 }}>
                  {relayConnected ? "RELAY CONNECTED" : "RELAY OFFLINE"}
                </span>
              </div>
              <div style={{ fontSize: 11, color: "#667085", lineHeight: 1.6 }}>
                Run this on your Mac to connect:
              </div>
              <div style={{
                marginTop: 8, padding: 10, borderRadius: 4, background: "#030303",
                border: "1px solid #1a1d23", fontSize: 11, color: "#00FF66",
                fontFamily: "monospace", wordBreak: "break-all",
              }}>
                curl -sL 'https://dgfhgjhj-jarvis-ai-brain.hf.space/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user shaurjeshbasu
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setStep(2)} style={{
                flex: 1, padding: "12px 0", borderRadius: 6, fontSize: 12, fontWeight: 600,
                fontFamily: "inherit", cursor: "pointer", background: relayConnected ? "#00FF66" : "#1a1d23",
                color: relayConnected ? "#030303" : "#667085", border: "none",
                opacity: relayConnected ? 1 : 0.5,
              }}>
                {relayConnected ? "CONTINUE →" : "Waiting for relay..."}
              </button>
              <button onClick={skip} style={{
                padding: "12px 16px", borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                cursor: "pointer", background: "transparent", color: "#667085",
                border: "1px solid #1a1d23",
              }}>
                Skip
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <div style={{
              padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23",
              marginBottom: 16, textAlign: "center",
            }}>
              {scanning ? (
                <div>
                  <div style={{ fontSize: 24, marginBottom: 8, animation: "spin 1s linear infinite" }}>⟳</div>
                  <div style={{ fontSize: 11, color: "#00FF66" }}>Scanning network...</div>
                </div>
              ) : devicesFound > 0 ? (
                <div>
                  <div style={{ fontSize: 24, marginBottom: 8, color: "#00FF66" }}>✓</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{devicesFound} devices found</div>
                  <div style={{ fontSize: 10, color: "#667085" }}>Tapo plugs, Echo, phones, and more</div>
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>📡</div>
                  <div style={{ fontSize: 11, color: "#667085" }}>Scan your WiFi for all smart devices</div>
                </div>
              )}
            </div>
            <button onClick={handleScan} disabled={scanning} style={{
              width: "100%", padding: "12px 0", borderRadius: 6, fontSize: 12, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", opacity: scanning ? 0.5 : 1,
            }}>
              {scanning ? "SCANNING..." : devicesFound > 0 ? "RESCAN" : "SCAN NETWORK"}
            </button>
          </div>
        )}

        {step === 3 && (
          <div style={{ textAlign: "center" }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%", background: "rgba(0,255,102,0.1)",
              border: "2px solid #00FF66", display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 20px", fontSize: 28, color: "#00FF66",
            }}>
              ✓
            </div>
            <div style={{ fontSize: 13, color: "#667085", marginBottom: 24, lineHeight: 1.6 }}>
              All systems are online. J.A.R.V.I.S. is ready to execute.
            </div>
            <button onClick={() => router.push("/")} style={{
              width: "100%", padding: "12px 0", borderRadius: 6, fontSize: 12, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", background: "#00FF66", color: "#030303",
              border: "none", letterSpacing: "0.05em",
            }}>
              ENTER COMMAND CENTER →
            </button>
          </div>
        )}
      </div>

      <style jsx global>{`
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
