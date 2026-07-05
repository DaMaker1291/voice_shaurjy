"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";

const PulseMap = dynamic(() => import("@/components/cockpit/PulseMap"), { ssr: false });

const API = "";

interface Device {
  id: string;
  name: string;
  device_type: string;
  ip: string;
  mac: string;
  protocol: string;
  manufacturer: string;
  model: string;
  is_online: boolean;
  state: any;
}

const DEVICE_META: Record<string, { icon: string; color: string; label: string }> = {
  ROUTER: { icon: "🌐", color: "#667085", label: "Router" },
  SWITCH: { icon: "🔌", color: "#00FF66", label: "Smart Plug" },
  PRINTER: { icon: "🖨️", color: "#FFB300", label: "Printer" },
  PHONE: { icon: "📱", color: "#00FF66", label: "Phone" },
  SENSOR: { icon: "📡", color: "#667085", label: "Sensor" },
  HUB: { icon: "💻", color: "#667085", label: "Hub" },
  LIGHT: { icon: "💡", color: "#FFB300", label: "Light" },
  THERMOSTAT: { icon: "🌡️", color: "#FF3333", label: "Thermostat" },
  LOCK: { icon: "🔒", color: "#00FF66", label: "Lock" },
  CAMERA: { icon: "📷", color: "#FFB300", label: "Camera" },
  VACUUM: { icon: "🤖", color: "#667085", label: "Vacuum" },
  MEDIA_PLAYER: { icon: "📺", color: "#00FF66", label: "Media" },
  COVER: { icon: "🪟", color: "#667085", label: "Cover" },
};

const getMeta = (type: string) => DEVICE_META[type] || { icon: "📡", color: "#667085", label: type };

export default function SovereignPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [result, setResult] = useState<any>(null);
  const [scanning, setScanning] = useState(false);

  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/sovereign/devices`);
      const data = await res.json();
      setDevices(data.devices || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDevices();
    const i = setInterval(fetchDevices, 5000);
    return () => clearInterval(i);
  }, [fetchDevices]);

  async function scan() {
    setScanning(true);
    setMsg("Scanning network...");
    try {
      const res = await fetch(`${API}/api/real/scan`, { method: "POST" });
      const data = await res.json();
      setMsg(`Found ${data.tapo_found || 0} plugs, ${data.phones_found || 0} phones, ${data.printers_found || 0} printers`);
      fetchDevices();
    } catch (e: any) {
      setMsg(e.message);
    }
    setTimeout(() => { setMsg(""); setScanning(false); }, 4000);
  }

  async function cmd(device: Device, action: string) {
    const p = device.protocol.toLowerCase();
    let url = "";
    if (p === "tapo" || device.device_type === "SWITCH") url = `/api/real/tapo/${action}?ip=${device.ip}`;
    else if (device.device_type === "PRINTER") url = `/api/real/printer/status?ip=${device.ip}`;
    else if (device.device_type === "PHONE") url = `/api/real/phone/${action}?ip=${device.ip}`;
    if (!url) return;
    try {
      const m = ["status", "info", "battery", "screen", "ink"].includes(action) ? "GET" : "POST";
      const res = await fetch(`${API}${url}`, { method: m });
      setResult({ who: device.name, action, data: await res.json() });
    } catch (e: any) {
      setResult({ who: device.name, action, error: e.message });
    }
  }

  const online = devices.filter(d => d.is_online);
  const offline = devices.filter(d => !d.is_online);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--void)", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        @keyframes node-activate { 0% { box-shadow: 0 0 0 0 rgba(0,255,102,0.4); } 100% { box-shadow: 0 0 0 8px rgba(0,255,102,0); } }
        .animate-fade { animation: fade-in 0.25s cubic-bezier(0.16,1,0.3,1) both; }
        .device-node { animation: fade-in 0.3s cubic-bezier(0.16,1,0.3,1) both; }
        .device-node:nth-child(1) { animation-delay: 0ms; }
        .device-node:nth-child(2) { animation-delay: 30ms; }
        .device-node:nth-child(3) { animation-delay: 60ms; }
        .device-node:nth-child(4) { animation-delay: 90ms; }
        .device-node:nth-child(5) { animation-delay: 120ms; }
        .device-node:nth-child(6) { animation-delay: 150ms; }
        .device-node:nth-child(7) { animation-delay: 180ms; }
        .device-node:nth-child(8) { animation-delay: 210ms; }
        .device-node:nth-child(9) { animation-delay: 240ms; }
        .device-node:nth-child(10) { animation-delay: 270ms; }
      `}</style>

      {/* Header */}
      <header style={{ height: 32, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/" style={{ fontSize: 10, color: "var(--text-muted)", textDecoration: "none" }}>← BACK</Link>
          <div style={{ width: 1, height: 14, background: "var(--border)" }} />
          <span style={{ fontSize: 10, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600 }}>NETWORK</span>
          <span style={{ fontSize: 9, color: "var(--text-muted)" }}>{online.length}/{devices.length}</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {msg && <span style={{ fontSize: 9, color: "var(--neon-green)" }}>{msg}</span>}
          <button onClick={scan} disabled={scanning} style={{ padding: "3px 10px", borderRadius: 3, fontSize: 9, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: scanning ? "var(--neon-green-dim)" : "var(--surface-raised)", color: scanning ? "var(--neon-green)" : "var(--text-muted)", border: "1px solid var(--border)", letterSpacing: "0.05em", opacity: scanning ? 0.5 : 1 }}>
            {scanning ? "SCAN..." : "SCAN"}
          </button>
          <Link href="/agents" style={{ padding: "3px 8px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-muted)", textDecoration: "none", border: "1px solid var(--border)", background: "var(--surface-raised)" }}>AGENTS →</Link>
        </div>
      </header>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          {/* Empty state */}
          {devices.length === 0 && !loading && (
            <div style={{ textAlign: "center", padding: "80px 20px" }}>
              <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>📡</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600 }}>NO DEVICES DETECTED</div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", opacity: 0.6, marginBottom: 16 }}>Run the relay on your machine to discover real devices</div>
              <button onClick={scan} style={{ padding: "6px 16px", borderRadius: 4, fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--neon-green)", color: "#000", border: "none" }}>SCAN NETWORK</button>
            </div>
          )}

          {/* Pulse Map */}
          {devices.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 6px rgba(0,255,102,0.4)" }} />
                NETWORK PULSE MAP
              </div>
              <PulseMap devices={devices} size={360} />
            </div>
          )}

          {/* Online */}
          {online.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 9, color: "var(--neon-green)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 6px rgba(0,255,102,0.4)" }} />
                ONLINE ({online.length})
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
                {online.map(device => {
                  const meta = getMeta(device.device_type);
                  return (
                    <div key={device.id} className="device-node" style={{ padding: 14, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div style={{ width: 32, height: 32, borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>{meta.icon}</div>
                          <div>
                            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)" }}>{device.name}</div>
                            <div style={{ fontSize: 9, color: "var(--text-muted)" }}>{device.ip}</div>
                          </div>
                        </div>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 6px rgba(0,255,102,0.4)", animation: "node-activate 2s ease infinite" }} />
                      </div>

                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                        {device.device_type === "SWITCH" && (
                          <>
                            <button onClick={() => cmd(device, "turn_on")} style={{ flex: 1, padding: "5px 0", borderRadius: 3, fontSize: 9, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--neon-green-dim)", color: "var(--neon-green)", border: "1px solid rgba(0,255,102,0.2)" }}>ON</button>
                            <button onClick={() => cmd(device, "turn_off")} style={{ flex: 1, padding: "5px 0", borderRadius: 3, fontSize: 9, fontWeight: 600, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--crimson-dim)", color: "var(--crimson)", border: "1px solid rgba(255,51,51,0.2)" }}>OFF</button>
                          </>
                        )}
                        {device.device_type === "PHONE" && (
                          <>
                            <button onClick={() => cmd(device, "battery")} style={{ padding: "5px 8px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--surface-raised)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>🔋 BATT</button>
                            <button onClick={() => cmd(device, "lock")} style={{ padding: "5px 8px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--surface-raised)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>🔒 LOCK</button>
                          </>
                        )}
                        {device.device_type === "PRINTER" && (
                          <button onClick={() => cmd(device, "status")} style={{ flex: 1, padding: "5px 0", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--surface-raised)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>STATUS</button>
                        )}
                      </div>

                      <div style={{ display: "flex", gap: 4, fontSize: 8, color: "var(--text-muted)" }}>
                        <span style={{ padding: "2px 5px", borderRadius: 3, background: "var(--surface-raised)", border: "1px solid var(--border)" }}>{meta.label}</span>
                        <span style={{ padding: "2px 5px", borderRadius: 3, background: "var(--surface-raised)", border: "1px solid var(--border)" }}>{device.protocol}</span>
                        {device.manufacturer && <span style={{ padding: "2px 5px", borderRadius: 3, background: "var(--surface-raised)", border: "1px solid var(--border)" }}>{device.manufacturer}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Offline */}
          {offline.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.1em", fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--steel)" }} />
                OFFLINE ({offline.length})
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
                {offline.map(device => {
                  const meta = getMeta(device.device_type);
                  return (
                    <div key={device.id} className="device-node" style={{ padding: 14, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, opacity: 0.4 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 4, background: "var(--surface-raised)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, opacity: 0.5 }}>{meta.icon}</div>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-muted)" }}>{device.name}</div>
                          <div style={{ fontSize: 9, color: "var(--text-muted)" }}>{device.ip}</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Command Result */}
          {result && (
            <div style={{ padding: 14, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 600 }}>{result.who}</span>
                  <span style={{ fontSize: 8, padding: "2px 6px", borderRadius: 3, background: "var(--neon-green-dim)", color: "var(--neon-green)", fontWeight: 600 }}>{result.action}</span>
                </div>
                <button onClick={() => setResult(null)} style={{ padding: "3px 6px", borderRadius: 3, fontSize: 9, cursor: "pointer", background: "var(--surface-raised)", color: "var(--text-muted)", border: "1px solid var(--border)", fontFamily: "var(--font-mono)" }}>✕</button>
              </div>
              <pre style={{ fontSize: 10, color: "var(--text-secondary)", fontFamily: "var(--font-mono)", whiteSpace: "pre-wrap", lineHeight: 1.6, margin: 0, padding: 10, borderRadius: 4, background: "var(--surface-raised)", border: "1px solid var(--border)" }}>
                {result.error ? `Error: ${result.error}` : JSON.stringify(result.data, null, 2)}
              </pre>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div style={{ textAlign: "center", padding: "60px 20px" }}>
              <div style={{ width: 18, height: 18, border: "2px solid var(--border)", borderTopColor: "var(--neon-green)", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 10px" }} />
              <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Scanning...</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
