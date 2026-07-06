"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

const API = "";

interface Device {
  ip: string;
  name: string;
  type: string;
  protocol: string;
  mac?: string;
  is_online?: boolean;
  state?: Record<string, any>;
}

const DEVICE_ICONS: Record<string, string> = {
  ALEXA: "🔊", TAPO_PLUG: "🔌", SONOS: "🎵", HUE_BRIDGE: "💡",
  WLED: "🌈", ESPHOME: "⚙️", CHROMECAST: "📺", ROUTER: "🌐",
  CAMERA: "📷", RASPBERRY_PI: "🍓", SAMSUNG_TV: "📺",
  HTTP_DEVICE: "🖥", MQTT_BROKER: "📡", UNKNOWN: "📱",
};

const DEVICE_COLORS: Record<string, string> = {
  ALEXA: "#00B4D8", TAPO_PLUG: "#00FF66", SONOS: "#FFB300", HUE_BRIDGE: "#FFB300",
  WLED: "#A855F7", ESPHOME: "#F97316", CHROMECAST: "#FF3333", ROUTER: "#667085",
};

export default function SovereignPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [scanning, setScanning] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [filter, setFilter] = useState("all");
  const [alexaSpeaking, setAlexaSpeaking] = useState("");

  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/relay/devices?user_id=local`);
      const data = await res.json();
      setDevices(data.devices || []);
    } catch {}
  }, []);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);
  useEffect(() => {
    const i = setInterval(fetchDevices, 5000);
    return () => clearInterval(i);
  }, [fetchDevices]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API}/api/relay/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }),
      });
      setTimeout(fetchDevices, 3000);
    } catch {}
    setScanning(false);
  };

  const handleControl = async (ip: string, action: string) => {
    try {
      await fetch(`${API}/api/real/tapo/turn_${action}?ip=${ip}`, { method: "POST" });
      fetchDevices();
    } catch {}
  };

  const handleAlexa = async (cmd: string) => {
    setAlexaSpeaking(cmd);
    try {
      await fetch(`${API}/api/relay/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: "alexa_speak", params: cmd, user_id: "local" }),
      });
    } catch {}
    setTimeout(() => setAlexaSpeaking(""), 3000);
  };

  const filtered = filter === "all" ? devices : devices.filter(d => d.type === filter);
  const deviceTypes = Array.from(new Set(devices.map(d => d.type)));

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        .af { animation: fade-in 0.25s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Header */}
      <header style={{ height: 40, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
          <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
          <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>DEVICE CONTROL CENTER</span>
          <span style={{ fontSize: 9, color: "#667085" }}>{devices.length} devices</span>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          style={{
            padding: "5px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
            cursor: "pointer", background: scanning ? "#1a1d23" : "rgba(0,255,102,0.1)",
            color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)",
          }}
        >
          {scanning ? "SCANNING..." : "SCAN"}
        </button>
      </header>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 4, padding: "8px 16px", borderBottom: "1px solid #1a1d23", overflow: "auto" }}>
        <button onClick={() => setFilter("all")} style={{
          padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit", cursor: "pointer",
          background: filter === "all" ? "rgba(0,255,102,0.15)" : "transparent",
          color: filter === "all" ? "#00FF66" : "#667085", border: `1px solid ${filter === "all" ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
        }}>
          ALL ({devices.length})
        </button>
        {deviceTypes.map(t => (
          <button key={t} onClick={() => setFilter(t)} style={{
            padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit", cursor: "pointer",
            background: filter === t ? "rgba(0,255,102,0.15)" : "transparent",
            color: filter === t ? "#00FF66" : "#667085", border: `1px solid ${filter === t ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
          }}>
            {DEVICE_ICONS[t] || "📱"} {t} ({devices.filter(d => d.type === t).length})
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          {/* Device Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
            {filtered.map((d, i) => (
              <div
                key={`${d.ip}-${i}`}
                className="af"
                onClick={() => setSelectedDevice(selectedDevice?.ip === d.ip ? null : d)}
                style={{
                  background: "#0d0f12", border: `1px solid ${selectedDevice?.ip === d.ip ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
                  borderRadius: 8, padding: 16, cursor: "pointer", transition: "all 0.15s",
                  position: "relative", overflow: "hidden",
                }}
              >
                {/* Color accent */}
                <div style={{
                  position: "absolute", top: 0, left: 0, right: 0, height: 2,
                  background: DEVICE_COLORS[d.type] || "#667085",
                }} />

                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                  <span style={{ fontSize: 20 }}>{DEVICE_ICONS[d.type] || "📱"}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 500 }}>{d.name}</div>
                    <div style={{ fontSize: 9, color: "#667085" }}>{d.ip}</div>
                  </div>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#00FF66" }} />
                </div>

                <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
                  <span style={{ padding: "2px 6px", borderRadius: 3, fontSize: 8, background: "#1a1d23", color: "#667085" }}>
                    {d.protocol}
                  </span>
                  <span style={{ padding: "2px 6px", borderRadius: 3, fontSize: 8, background: "#1a1d23", color: "#667085" }}>
                    {d.type}
                  </span>
                </div>

                {/* Controls */}
                {d.type === "TAPO_PLUG" && (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button onClick={e => { e.stopPropagation(); handleControl(d.ip, "on"); }} style={{ flex: 1, padding: "6px 0", borderRadius: 4, fontSize: 10, fontFamily: "inherit", cursor: "pointer", background: "rgba(0,255,102,0.1)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)" }}>ON</button>
                    <button onClick={e => { e.stopPropagation(); handleControl(d.ip, "off"); }} style={{ flex: 1, padding: "6px 0", borderRadius: 4, fontSize: 10, fontFamily: "inherit", cursor: "pointer", background: "rgba(255,51,51,0.1)", color: "#FF3333", border: "1px solid rgba(255,51,51,0.2)" }}>OFF</button>
                  </div>
                )}

                {d.type === "ALEXA" && (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button onClick={e => { e.stopPropagation(); handleAlexa("hello"); }} style={{ flex: 1, padding: "6px 0", borderRadius: 4, fontSize: 10, fontFamily: "inherit", cursor: "pointer", background: "rgba(0,180,216,0.1)", color: "#00B4D8", border: "1px solid rgba(0,180,216,0.2)" }}>SPEAK</button>
                    <button onClick={e => { e.stopPropagation(); handleAlexa("alexa play"); }} style={{ flex: 1, padding: "6px 0", borderRadius: 4, fontSize: 10, fontFamily: "inherit", cursor: "pointer", background: "rgba(0,180,216,0.1)", color: "#00B4D8", border: "1px solid rgba(0,180,216,0.2)" }}>PLAY</button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {devices.length === 0 && (
            <div style={{ textAlign: "center", padding: "80px 20px" }}>
              <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>📡</div>
              <div style={{ fontSize: 12, color: "#667085" }}>No devices discovered. Click SCAN to find devices on your network.</div>
            </div>
          )}
        </div>
      </div>

      {/* Alexa Quick Controls - Fixed bottom bar */}
      <div style={{ borderTop: "1px solid #1a1d23", background: "#0d0f12", padding: "8px 16px", display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
        <span style={{ fontSize: 9, color: "#667085", letterSpacing: "0.08em" }}>ALEXA:</span>
        {["Say hello", "Play music", "Pause", "Volume 50", "Timer 5 min", "DND on"].map(cmd => (
          <button
            key={cmd}
            onClick={() => handleAlexa(cmd.toLowerCase())}
            style={{
              padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit",
              cursor: "pointer", background: alexaSpeaking === cmd.toLowerCase() ? "rgba(0,180,216,0.2)" : "#1a1d23",
              color: alexaSpeaking === cmd.toLowerCase() ? "#00B4D8" : "#667085",
              border: `1px solid ${alexaSpeaking === cmd.toLowerCase() ? "rgba(0,180,216,0.3)" : "#252830"}`,
            }}
          >
            {cmd}
          </button>
        ))}
      </div>
    </div>
  );
}
