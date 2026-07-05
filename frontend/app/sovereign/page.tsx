"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

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
  ROUTER: { icon: "🌐", color: "#6366f1", label: "Router" },
  SWITCH: { icon: "🔌", color: "#a78bfa", label: "Smart Plug" },
  PRINTER: { icon: "🖨️", color: "#f59e0b", label: "Printer" },
  PHONE: { icon: "📱", color: "#ec4899", label: "Phone" },
  SENSOR: { icon: "📡", color: "#22c55e", label: "Sensor" },
  HUB: { icon: "💻", color: "#06b6d4", label: "Hub" },
  LIGHT: { icon: "💡", color: "#eab308", label: "Light" },
  THERMOSTAT: { icon: "🌡️", color: "#ef4444", label: "Thermostat" },
  LOCK: { icon: "🔒", color: "#22c55e", label: "Lock" },
  CAMERA: { icon: "📷", color: "#f59e0b", label: "Camera" },
  VACUUM: { icon: "🤖", color: "#a78bfa", label: "Vacuum" },
  MEDIA_PLAYER: { icon: "📺", color: "#ec4899", label: "Media" },
  COVER: { icon: "🪟", color: "#06b6d4", label: "Cover" },
};

const getMeta = (type: string) => DEVICE_META[type] || { icon: "📡", color: "#71717a", label: type };

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
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-primary)", color: "var(--text-primary)", fontFamily: "var(--font-inter), system-ui, sans-serif" }}>
      <style jsx global>{`
        @keyframes fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .device-card { animation: fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) both; }
        .device-card:nth-child(1) { animation-delay: 0ms; }
        .device-card:nth-child(2) { animation-delay: 30ms; }
        .device-card:nth-child(3) { animation-delay: 60ms; }
        .device-card:nth-child(4) { animation-delay: 90ms; }
        .device-card:nth-child(5) { animation-delay: 120ms; }
        .card-hover { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
        .card-hover:hover { border-color: rgba(139,92,246,0.2); background: rgba(139,92,246,0.03); }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.2); border-radius: 2px; }
      `}</style>

      {/* Header */}
      <header style={{ position: "sticky", top: 0, zIndex: 100, borderBottom: "1px solid var(--border-subtle)", background: "rgba(9,9,11,0.85)", backdropFilter: "blur(20px) saturate(180%)" }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <Link href="/" style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 32, height: 32, borderRadius: 8, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)", textDecoration: "none", transition: "all 0.15s", fontSize: 14 }}>
              ←
            </Link>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: online.length > 0 ? "var(--success)" : "var(--error)", boxShadow: `0 0 12px ${online.length > 0 ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)"}`, transition: "all 0.3s" }} />
              <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>Network</span>
            </div>
            <span style={{ fontSize: 11, color: "var(--text-muted)", padding: "3px 8px", borderRadius: 6, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)" }}>
              {online.length} online · {devices.length} total
            </span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {msg && <span style={{ fontSize: 11, color: "var(--accent)", fontWeight: 500 }}>{msg}</span>}
            <button onClick={scan} disabled={scanning} style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", opacity: scanning ? 0.5 : 1, transition: "all 0.15s", display: "flex", alignItems: "center", gap: 6 }}>
              {scanning && <span style={{ width: 12, height: 12, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />}
              Scan
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main style={{ flex: 1, overflow: "auto", padding: 24 }}>
        {devices.length === 0 && !loading && (
          <div style={{ textAlign: "center", padding: "80px 20px", animation: "fade-up 0.4s ease both" }}>
            <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.2 }}>📡</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>No devices found</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 20 }}>Run the relay on your machine to discover real devices</div>
            <button onClick={scan} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Scan Network</button>
          </div>
        )}

        {devices.length > 0 && (
          <div style={{ maxWidth: 900, margin: "0 auto" }}>
            {/* Online devices */}
            {online.length > 0 && (
              <div style={{ marginBottom: 32 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)" }} />
                  Online ({online.length})
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                  {online.map(device => {
                    const meta = getMeta(device.device_type);
                    const isOn = device.state?.is_on ?? device.state?.power_on ?? null;
                    return (
                      <div key={device.id} className="device-card card-hover" style={{ padding: "16px 18px", borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)" }}>
                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div style={{ width: 36, height: 36, borderRadius: 10, background: `${meta.color}10`, border: `1px solid ${meta.color}20`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>{meta.icon}</div>
                            <div>
                              <div style={{ fontSize: 13, fontWeight: 600 }}>{device.name}</div>
                              <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "monospace" }}>{device.ip}</div>
                            </div>
                          </div>
                          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--success)", boxShadow: "0 0 8px rgba(34,197,94,0.4)" }} />
                        </div>

                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
                          {device.device_type === "SWITCH" && (
                            <>
                              <button onClick={() => cmd(device, "turn_on")} style={{ flex: 1, padding: "7px 0", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer", background: "var(--success-dim)", color: "var(--success)", border: "1px solid rgba(34,197,94,0.2)" }}>ON</button>
                              <button onClick={() => cmd(device, "turn_off")} style={{ flex: 1, padding: "7px 0", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer", background: "var(--error-dim)", color: "var(--error)", border: "1px solid rgba(239,68,68,0.2)" }}>OFF</button>
                            </>
                          )}
                          {device.device_type === "PHONE" && (
                            <>
                              <button onClick={() => cmd(device, "battery")} style={{ padding: "7px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--bg-tertiary)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>🔋 Battery</button>
                              <button onClick={() => cmd(device, "lock")} style={{ padding: "7px 12px", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--bg-tertiary)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>🔒 Lock</button>
                            </>
                          )}
                          {device.device_type === "PRINTER" && (
                            <button onClick={() => cmd(device, "status")} style={{ flex: 1, padding: "7px 0", borderRadius: 6, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "var(--bg-tertiary)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>Status</button>
                          )}
                        </div>

                        <div style={{ display: "flex", gap: 6, fontSize: 10, color: "var(--text-muted)" }}>
                          <span style={{ padding: "2px 6px", borderRadius: 4, background: "var(--bg-tertiary)" }}>{meta.label}</span>
                          <span style={{ padding: "2px 6px", borderRadius: 4, background: "var(--bg-tertiary)" }}>{device.protocol}</span>
                          {device.manufacturer && <span style={{ padding: "2px 6px", borderRadius: 4, background: "var(--bg-tertiary)" }}>{device.manufacturer}</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Offline devices */}
            {offline.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--text-muted)" }} />
                  Offline ({offline.length})
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                  {offline.map(device => {
                    const meta = getMeta(device.device_type);
                    return (
                      <div key={device.id} className="device-card card-hover" style={{ padding: "16px 18px", borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", opacity: 0.5 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--bg-tertiary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, opacity: 0.5 }}>{meta.icon}</div>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-muted)" }}>{device.name}</div>
                            <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "monospace" }}>{device.ip}</div>
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
              <div style={{ marginTop: 24, padding: 18, borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", animation: "fade-up 0.25s ease both" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{result.who}</span>
                    <span style={{ fontSize: 11, color: "var(--accent)", padding: "2px 8px", borderRadius: 5, background: "var(--accent-dim)" }}>{result.action}</span>
                  </div>
                  <button onClick={() => setResult(null)} style={{ padding: "4px 8px", borderRadius: 4, fontSize: 11, cursor: "pointer", background: "var(--bg-tertiary)", color: "var(--text-muted)", border: "1px solid var(--border-subtle)" }}>✕</button>
                </div>
                <pre style={{ fontSize: 11, color: "var(--text-secondary)", fontFamily: "monospace", whiteSpace: "pre-wrap", lineHeight: 1.6, margin: 0, padding: 12, borderRadius: 8, background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)" }}>
                  {result.error ? `Error: ${result.error}` : JSON.stringify(result.data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {loading && (
          <div style={{ textAlign: "center", padding: "80px 20px" }}>
            <div style={{ width: 24, height: 24, border: "2px solid var(--border-subtle)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 12px" }} />
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading devices...</div>
          </div>
        )}
      </main>
    </div>
  );
}
