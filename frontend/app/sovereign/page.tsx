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

const ICONS: Record<string, string> = {
  ROUTER: "🌐", SWITCH: "🔌", PRINTER: "🖨", PHONE: "📱",
  SENSOR: "📡", HUB: "💻", LIGHT: "💡", THERMOSTAT: "🌡",
  LOCK: "🔒", CAMERA: "📷", VACUUM: "🤖", MEDIA_PLAYER: "📺", COVER: "🪟",
};

const COLORS: Record<string, string> = {
  ROUTER: "#6366f1", SWITCH: "#a78bfa", PRINTER: "#f59e0b", PHONE: "#ec4899",
  SENSOR: "#22c55e", HUB: "#06b6d4",
};

export default function SovereignPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [result, setResult] = useState<any>(null);

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
    setMsg("Scanning...");
    try {
      const res = await fetch(`${API}/api/real/scan`, { method: "POST" });
      const data = await res.json();
      setMsg(`Found ${data.tapo_found || 0} plugs, ${data.phones_found || 0} phones, ${data.printers_found || 0} printers`);
      fetchDevices();
    } catch (e: any) { setMsg(e.message); }
    setTimeout(() => setMsg(""), 4000);
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
    } catch (e: any) { setResult({ who: device.name, action, error: e.message }); }
  }

  const online = devices.filter(d => d.is_online);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Header */}
      <header style={{ padding: "10px 20px", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(10,10,15,0.95)", backdropFilter: "blur(20px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ color: "#52525b", fontSize: 18, textDecoration: "none" }}>←</Link>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: online.length > 0 ? "#22c55e" : "#ef4444", boxShadow: `0 0 10px ${online.length > 0 ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)"}` }} />
          <span style={{ fontSize: 14, fontWeight: 600 }}>Devices</span>
          <span style={{ fontSize: 11, color: "#52525b" }}>{online.length} online</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {msg && <span style={{ fontSize: 11, color: "#a78bfa" }}>{msg}</span>}
          <button onClick={scan} style={{ padding: "5px 12px", borderRadius: 6, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontSize: 12, cursor: "pointer" }}>Scan</button>
        </div>
      </header>

      {/* Device list */}
      <main style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {devices.length === 0 && !loading && (
          <div style={{ textAlign: "center", padding: 60, color: "#52525b" }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>🔍</div>
            <div style={{ fontSize: 13, marginBottom: 6 }}>No devices found</div>
            <code style={{ fontSize: 11, color: "#a78bfa", background: "rgba(139,92,246,0.1)", padding: "6px 10px", borderRadius: 6 }}>python3 standalone_relay.py --user shaurjesh</code>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {devices.map(d => {
            const icon = ICONS[d.device_type] || "❓";
            const color = COLORS[d.device_type] || "#52525b";
            const isPlug = d.device_type === "SWITCH";
            const isPhone = d.device_type === "PHONE";
            const isPrinter = d.device_type === "PRINTER";

            return (
              <div key={d.id} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: "12px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 8, background: color + "15", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>{icon}</div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{d.name}</div>
                    <div style={{ fontSize: 11, color: "#52525b" }}>{d.ip} • {d.protocol.toUpperCase()}</div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {isPlug && (
                    <>
                      <button onClick={() => cmd(d, "turn_on")} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(34,197,94,0.3)", background: "rgba(34,197,94,0.1)", color: "#22c55e", fontSize: 11, cursor: "pointer" }}>ON</button>
                      <button onClick={() => cmd(d, "turn_off")} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.1)", color: "#ef4444", fontSize: 11, cursor: "pointer" }}>OFF</button>
                    </>
                  )}
                  {isPhone && (
                    <>
                      <button onClick={() => cmd(d, "battery")} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(234,179,8,0.3)", background: "rgba(234,179,8,0.1)", color: "#eab308", fontSize: 11, cursor: "pointer" }}>Battery</button>
                      <button onClick={() => cmd(d, "lock")} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontSize: 11, cursor: "pointer" }}>Lock</button>
                    </>
                  )}
                  {isPrinter && (
                    <button onClick={() => cmd(d, "status")} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(245,158,11,0.3)", background: "rgba(245,158,11,0.1)", color: "#f59e0b", fontSize: 11, cursor: "pointer" }}>Status</button>
                  )}
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: d.is_online ? "#22c55e" : "#ef4444" }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Result */}
        {result && (
          <div style={{ marginTop: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: "#a78bfa" }}>{result.who} → {result.action}</span>
              <button onClick={() => setResult(null)} style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer", fontSize: 14 }}>×</button>
            </div>
            <pre style={{ fontSize: 11, fontFamily: "monospace", color: result.error ? "#ef4444" : "#22c55e", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
              {JSON.stringify(result.data || result.error, null, 2)}
            </pre>
          </div>
        )}
      </main>
    </div>
  );
}
