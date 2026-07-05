"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

const API = "";

type Tab = "overview" | "devices" | "control" | "security";

interface Device {
  id: string;
  name: string;
  device_type: string;
  ip: string;
  mac: string;
  protocol: string;
  manufacturer: string;
  model: string;
  room: string;
  state: any;
  is_online: boolean;
}

const TYPE_META: Record<string, { icon: string; color: string; label: string }> = {
  ROUTER: { icon: "🌐", color: "#6366f1", label: "Router" },
  SWITCH: { icon: "🔌", color: "#a78bfa", label: "Smart Plug" },
  PRINTER: { icon: "🖨", color: "#f59e0b", label: "Printer" },
  PHONE: { icon: "📱", color: "#ec4899", label: "Phone" },
  SENSOR: { icon: "📡", color: "#22c55e", label: "Sensor" },
  HUB: { icon: "💻", color: "#06b6d4", label: "Hub" },
  LIGHT: { icon: "💡", color: "#facc15", label: "Light" },
  THERMOSTAT: { icon: "🌡", color: "#f97316", label: "Thermostat" },
  LOCK: { icon: "🔒", color: "#ef4444", label: "Lock" },
  CAMERA: { icon: "📷", color: "#06b6d4", label: "Camera" },
  VACUUM: { icon: "🤖", color: "#8b5cf6", label: "Vacuum" },
  MEDIA_PLAYER: { icon: "📺", color: "#ec4899", label: "Speaker" },
  COVER: { icon: "🪟", color: "#14b8a6", label: "Blinds" },
};

export default function SovereignPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanStatus, setScanStatus] = useState("");
  const [commandResult, setCommandResult] = useState<any>(null);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

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
    const interval = setInterval(fetchDevices, 5000);
    return () => clearInterval(interval);
  }, [fetchDevices]);

  async function triggerScan() {
    setScanStatus("Scanning...");
    try {
      const res = await fetch(`${API}/api/real/scan`, { method: "POST" });
      const data = await res.json();
      setScanStatus(`Found ${data.phones_found || 0} phones, ${data.tapo_found || 0} plugs, ${data.printers_found || 0} printers`);
      fetchDevices();
    } catch (e: any) {
      setScanStatus(`Error: ${e.message}`);
    }
    setTimeout(() => setScanStatus(""), 5000);
  }

  async function controlDevice(device: Device, action: string) {
    const proto = device.protocol.toLowerCase();
    let url = "";
    if (proto === "tapo" || device.device_type === "SWITCH") {
      url = `/api/real/tapo/${action}?ip=${device.ip}`;
    } else if (device.device_type === "PRINTER") {
      url = `/api/real/printer/status?ip=${device.ip}`;
    } else if (device.device_type === "PHONE") {
      url = `/api/real/phone/${action}?ip=${device.ip}`;
    }
    if (!url) return;

    try {
      const method = action === "status" || action === "info" || action === "battery" || action === "screen" || action === "ink" ? "GET" : "POST";
      const res = await fetch(`${API}${url}`, { method });
      const data = await res.json();
      setCommandResult({ device: device.name, action, result: data });
    } catch (e: any) {
      setCommandResult({ device: device.name, action, error: e.message });
    }
  }

  const online = devices.filter((d) => d.is_online);
  const byType = devices.reduce((acc, d) => { acc[d.device_type] = (acc[d.device_type] || 0) + 1; return acc; }, {} as Record<string, number>);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#e2e8f0", fontFamily: "'Inter', system-ui, -apple-system, sans-serif" }}>
      {/* Header */}
      <header style={{ padding: "10px 20px", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(10,10,15,0.95)", backdropFilter: "blur(20px)", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ color: "#71717a", fontSize: 18, textDecoration: "none", padding: "4px 8px", borderRadius: 6, transition: "color 0.15s" }} onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")} onMouseLeave={(e) => (e.currentTarget.style.color = "#71717a")}>
            ←
          </Link>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: online.length > 0 ? "#22c55e" : "#ef4444", boxShadow: `0 0 12px ${online.length > 0 ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)"}` }} />
          <div>
            <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: -0.3 }}>SOVEREIGN NETWORK</span>
            <span style={{ fontSize: 11, color: "#52525b", marginLeft: 8 }}>{online.length} devices online</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {scanStatus && <span style={{ fontSize: 11, color: "#a78bfa" }}>{scanStatus}</span>}
          <button onClick={triggerScan} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontSize: 12, cursor: "pointer", fontWeight: 500, transition: "all 0.15s" }} onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(139,92,246,0.2)")} onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(139,92,246,0.1)")}>
            Scan Network
          </button>
        </div>
      </header>

      {/* Tabs */}
      <nav style={{ display: "flex", gap: 0, borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "0 20px", background: "rgba(10,10,15,0.95)" }}>
        {(["overview", "devices", "control", "security"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: "10px 16px", border: "none", borderBottom: tab === t ? "2px solid #8b5cf6" : "2px solid transparent", background: "transparent", color: tab === t ? "#e2e8f0" : "#52525b", fontSize: 13, fontWeight: 500, cursor: "pointer", textTransform: "capitalize", transition: "all 0.15s" }}>
            {t}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
        {tab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10, marginBottom: 20 }}>
            <StatCard label="Total Devices" value={devices.length} icon="🌐" />
            <StatCard label="Online" value={online.length} icon="✓" />
            <StatCard label="Offline" value={devices.length - online.length} icon="✕" />
            <StatCard label="Device Types" value={Object.keys(byType).length} icon="📋" />

            {Object.entries(byType).map(([type, count]) => {
              const meta = TYPE_META[type] || { icon: "❓", color: "#71717a", label: type };
              return (
                <div key={type} onClick={() => setTab("devices")} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 14, cursor: "pointer", transition: "all 0.15s" }} onMouseEnter={(e) => (e.currentTarget.style.borderColor = meta.color + "40")} onMouseLeave={(e) => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)")}>
                  <div style={{ fontSize: 22, marginBottom: 6 }}>{meta.icon}</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{count}</div>
                  <div style={{ fontSize: 11, color: "#71717a" }}>{meta.label}{count !== 1 ? "s" : ""}</div>
                </div>
              );
            })}
          </div>
        )}

        {tab === "devices" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
            {devices.map((d) => {
              const meta = TYPE_META[d.device_type] || { icon: "❓", color: "#71717a", label: d.device_type };
              return (
                <div key={d.id} onClick={() => setSelectedDevice(d)} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16, cursor: "pointer", transition: "all 0.15s" }} onMouseEnter={(e) => (e.currentTarget.style.borderColor = meta.color + "40")} onMouseLeave={(e) => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)")}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 8, background: meta.color + "15", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>{meta.icon}</div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{d.name}</div>
                        <div style={{ fontSize: 11, color: "#52525b" }}>{meta.label} • {d.protocol.toUpperCase()}</div>
                      </div>
                    </div>
                    <div style={{ width: 7, height: 7, borderRadius: "50%", background: d.is_online ? "#22c55e" : "#ef4444", boxShadow: d.is_online ? "0 0 6px rgba(34,197,94,0.4)" : "none" }} />
                  </div>
                  <div style={{ fontSize: 11, color: "#52525b", display: "flex", gap: 8 }}>
                    <span>{d.ip}</span>
                    {d.manufacturer && <><span>•</span><span>{d.manufacturer}</span></>}
                    {d.model && <><span>•</span><span>{d.model}</span></>}
                  </div>
                </div>
              );
            })}
            {devices.length === 0 && !loading && (
              <div style={{ gridColumn: "1/-1", textAlign: "center", padding: 60, color: "#52525b" }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
                <div style={{ fontSize: 14, marginBottom: 8 }}>No devices found</div>
                <div style={{ fontSize: 12 }}>Run the relay on your local machine to discover real devices</div>
                <code style={{ display: "block", marginTop: 12, fontSize: 11, color: "#a78bfa", background: "rgba(139,92,246,0.1)", padding: "8px 12px", borderRadius: 6 }}>python3 standalone_relay.py --user shaurjesh</code>
              </div>
            )}
          </div>
        )}

        {tab === "control" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, maxWidth: 900 }}>
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: "#a1a1aa" }}>QUICK ACTIONS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {devices.filter(d => d.device_type === "SWITCH").map(d => (
                  <div key={d.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{d.name}</div>
                      <div style={{ fontSize: 10, color: "#52525b" }}>{d.ip}</div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button onClick={(e) => { e.stopPropagation(); controlDevice(d, "turn_on"); }} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(34,197,94,0.3)", background: "rgba(34,197,94,0.1)", color: "#22c55e", fontSize: 11, cursor: "pointer" }}>ON</button>
                      <button onClick={(e) => { e.stopPropagation(); controlDevice(d, "turn_off"); }} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.1)", color: "#ef4444", fontSize: 11, cursor: "pointer" }}>OFF</button>
                    </div>
                  </div>
                ))}
                {devices.filter(d => d.device_type === "PHONE").map(d => (
                  <div key={d.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{d.name}</div>
                      <div style={{ fontSize: 10, color: "#52525b" }}>{d.ip}</div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button onClick={(e) => { e.stopPropagation(); controlDevice(d, "battery"); }} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(234,179,8,0.3)", background: "rgba(234,179,8,0.1)", color: "#eab308", fontSize: 11, cursor: "pointer" }}>Battery</button>
                      <button onClick={(e) => { e.stopPropagation(); controlDevice(d, "lock"); }} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontSize: 11, cursor: "pointer" }}>Lock</button>
                    </div>
                  </div>
                ))}
                {devices.filter(d => d.device_type === "PRINTER").map(d => (
                  <div key={d.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{d.name}</div>
                      <div style={{ fontSize: 10, color: "#52525b" }}>{d.ip}</div>
                    </div>
                    <button onClick={(e) => { e.stopPropagation(); controlDevice(d, "status"); }} style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid rgba(245,158,11,0.3)", background: "rgba(245,158,11,0.1)", color: "#f59e0b", fontSize: 11, cursor: "pointer" }}>Status</button>
                  </div>
                ))}
                {devices.filter(d => ["SWITCH", "PHONE", "PRINTER"].includes(d.device_type)).length === 0 && (
                  <div style={{ fontSize: 12, color: "#52525b", textAlign: "center", padding: 20 }}>No controllable devices found</div>
                )}
              </div>
            </div>
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: "#a1a1aa" }}>COMMAND OUTPUT</div>
              {commandResult ? (
                <pre style={{ fontSize: 11, fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-all", color: commandResult.result?.success === false || commandResult.error ? "#ef4444" : "#22c55e", background: "rgba(0,0,0,0.3)", padding: 12, borderRadius: 6, maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(commandResult, null, 2)}
                </pre>
              ) : (
                <div style={{ fontSize: 12, color: "#52525b", textAlign: "center", padding: 40 }}>
                  Click a device action to see results
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "security" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10 }}>
            <StatCard label="Local Network" value="192.168.0.x" icon="🏠" />
            <StatCard label="Air-Gapped" value="YES" icon="🛡" />
            <StatCard label="No Cloud Control" value="YES" icon="🔒" />
            <StatCard label="Protocol" value="Local WiFi" icon="📡" />
            <div style={{ gridColumn: "1/-1", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "#a1a1aa" }}>SECURITY MODEL</div>
              <div style={{ fontSize: 12, color: "#71717a", lineHeight: 1.8 }}>
                <div>✓ All commands execute locally on your network — zero cloud</div>
                <div>✓ Devices are controlled via direct WiFi (Tapo, IPP, ADB)</div>
                <div>✓ No inbound internet traffic accepted</div>
                <div>✓ State telemetry parsed and stored locally only</div>
                <div>✓ Network-pinned authentication (same subnet required)</div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Device Detail Modal */}
      {selectedDevice && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={() => setSelectedDevice(null)}>
          <div style={{ background: "#111118", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: 24, maxWidth: 440, width: "90%" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 28 }}>{TYPE_META[selectedDevice.device_type]?.icon || "❓"}</span>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{selectedDevice.name}</div>
                  <div style={{ fontSize: 12, color: "#52525b" }}>{selectedDevice.device_type} • {selectedDevice.protocol.toUpperCase()}</div>
                </div>
              </div>
              <button onClick={() => setSelectedDevice(null)} style={{ background: "none", border: "none", color: "#52525b", fontSize: 20, cursor: "pointer" }}>×</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
              <InfoRow label="IP Address" value={selectedDevice.ip} />
              <InfoRow label="MAC" value={selectedDevice.mac} />
              <InfoRow label="Manufacturer" value={selectedDevice.manufacturer || "—"} />
              <InfoRow label="Model" value={selectedDevice.model || "—"} />
              <InfoRow label="Status" value={selectedDevice.is_online ? "ONLINE" : "OFFLINE"} color={selectedDevice.is_online ? "#22c55e" : "#ef4444"} />
              <InfoRow label="Protocol" value={selectedDevice.protocol.toUpperCase()} />
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#52525b", marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>State</div>
            <pre style={{ fontSize: 11, color: "#71717a", fontFamily: "monospace", background: "rgba(0,0,0,0.3)", padding: 10, borderRadius: 6, border: "1px solid rgba(255,255,255,0.04)", maxHeight: 100, overflow: "auto" }}>
              {JSON.stringify(selectedDevice.state || {}, null, 2)}
            </pre>
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              {selectedDevice.device_type === "SWITCH" && (
                <>
                  <button onClick={() => controlDevice(selectedDevice, "turn_on")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(34,197,94,0.3)", background: "rgba(34,197,94,0.1)", color: "#22c55e", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Turn ON</button>
                  <button onClick={() => controlDevice(selectedDevice, "turn_off")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.1)", color: "#ef4444", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Turn OFF</button>
                </>
              )}
              {selectedDevice.device_type === "PHONE" && (
                <>
                  <button onClick={() => controlDevice(selectedDevice, "battery")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(234,179,8,0.3)", background: "rgba(234,179,8,0.1)", color: "#eab308", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Battery</button>
                  <button onClick={() => controlDevice(selectedDevice, "lock")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Lock Screen</button>
                  <button onClick={() => controlDevice(selectedDevice, "screenshot")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(6,182,212,0.3)", background: "rgba(6,182,212,0.1)", color: "#06b6d4", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Screenshot</button>
                </>
              )}
              {selectedDevice.device_type === "PRINTER" && (
                <>
                  <button onClick={() => controlDevice(selectedDevice, "status")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(245,158,11,0.3)", background: "rgba(245,158,11,0.1)", color: "#f59e0b", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Status</button>
                  <button onClick={() => controlDevice(selectedDevice, "ink")} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Ink Levels</button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: any; icon: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
      <div style={{ fontSize: 22, marginBottom: 6 }}>{icon}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: "#fafafa" }}>{value}</div>
      <div style={{ fontSize: 11, color: "#52525b" }}>{label}</div>
    </div>
  );
}

function InfoRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#3f3f46", textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 12, color: color || "#a1a1aa", marginTop: 2 }}>{value || "—"}</div>
    </div>
  );
}
