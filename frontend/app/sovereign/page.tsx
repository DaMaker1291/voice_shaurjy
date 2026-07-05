"use client";

import { useEffect, useState, useRef } from "react";

const API = "";

interface Device {
  id: string;
  name: string;
  device_type: string;
  ip: string;
  mac: string;
  protocol: string;
  manufacturer: string;
  room: string;
  state: any;
  is_online: boolean;
  last_seen: number;
  signal_strength: number;
}

interface CommandLog {
  id: number;
  device_id: string;
  action: string;
  status: string;
  latency_ms: number;
  timestamp: number;
}

interface NetworkStats {
  total_devices: number;
  alive_devices: number;
  scans_completed: number;
  last_scan_duration_ms: number;
  subnet: string;
  local_ip: string;
}

interface SecurityStats {
  keys: any[];
  network_auth: { active_sessions: number; blocked_ips: number };
  local_ip: string;
  local_subnet: string;
}

interface DashboardData {
  devices: { total: number; online: number; offline: number };
  by_type: Record<string, number>;
  by_room: Record<string, number>;
  by_protocol: Record<string, number>;
  commands: { total: number; successful: number; success_rate: number; avg_latency_ms: number };
  recent_commands: CommandLog[];
  network: NetworkStats;
  security: SecurityStats;
}

const TYPE_ICONS: Record<string, string> = {
  LIGHT: "💡", SWITCH: "🔌", THERMOSTAT: "🌡", LOCK: "🔒", CAMERA: "📷",
  VACUUM: "🤖", CLIMATE: "❄️", MEDIA_PLAYER: "📺", SENSOR: "📡",
  HUB: "🏠", COVER: "🪟", SCENE: "🎬", ROUTER: "🌐", UNKNOWN: "❓",
};

const TYPE_COLORS: Record<string, string> = {
  LIGHT: "#facc15", SWITCH: "#a78bfa", THERMOSTAT: "#f97316", LOCK: "#ef4444",
  CAMERA: "#06b6d4", VACUUM: "#8b5cf6", CLIMATE: "#3b82f6", MEDIA_PLAYER: "#ec4899",
  SENSOR: "#22c55e", HUB: "#f59e0b", COVER: "#14b8a6", ROUTER: "#6366f1",
};

export default function SovereignPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [scanning, setScanning] = useState(false);
  const [commandTarget, setCommandTarget] = useState("");
  const [commandAction, setCommandAction] = useState("");
  const [commandParams, setCommandParams] = useState("{}");
  const [commandResult, setCommandResult] = useState<any>(null);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState<"overview" | "devices" | "commands" | "security">("overview");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetchDashboard();
    fetchDevices();
    const interval = setInterval(() => {
      fetchDashboard();
      fetchDevices();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  async function fetchDashboard() {
    try {
      const res = await fetch(`${API}/api/sovereign/dashboard`);
      const json = await res.json();
      setData(json);
    } catch {}
  }

  async function fetchDevices() {
    try {
      const res = await fetch(`${API}/api/sovereign/devices`);
      const json = await res.json();
      setDevices(json.devices || []);
    } catch {}
  }

  async function triggerScan() {
    setScanning(true);
    try {
      await fetch(`${API}/api/sovereign/network/scan`);
      await fetchDevices();
      await fetchDashboard();
    } catch {}
    setScanning(false);
  }

  async function executeCommand() {
    if (!commandTarget || !commandAction) return;
    try {
      const params = JSON.parse(commandParams);
      const res = await fetch(
        `${API}/api/sovereign/command?device_id=${commandTarget}&action=${commandAction}&initiated_by=user`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params) }
      );
      const json = await res.json();
      setCommandResult(json);
    } catch (e: any) {
      setCommandResult({ status: "error", error: e.message });
    }
  }

  async function startDaemon() {
    try {
      await fetch(`${API}/api/sovereign/network/start?scan_interval=30`, { method: "POST" });
    } catch {}
  }

  const filteredDevices = filter === "all" ? devices
    : filter === "online" ? devices.filter((d) => d.is_online)
    : devices.filter((d) => d.device_type === filter);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#09090b", color: "#e2e8f0", fontFamily: "system-ui, -apple-system, sans-serif", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "12px 24px", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#09090b" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: data?.devices?.online ? "#22c55e" : "#ef4444", boxShadow: `0 0 8px ${data?.devices?.online ? "#22c55e" : "#ef4444"}` }} />
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: -0.5 }}>SOVEREIGN NETWORK</span>
          <span style={{ fontSize: 11, color: "#71717a", background: "rgba(139,92,246,0.12)", padding: "2px 8px", borderRadius: 4 }}>v2.0</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={triggerScan} disabled={scanning} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid rgba(139,92,246,0.3)", background: scanning ? "rgba(139,92,246,0.05)" : "rgba(139,92,246,0.12)", color: "#e2e8f0", fontSize: 12, cursor: scanning ? "wait" : "pointer", fontWeight: 500 }}>
            {scanning ? "⟳ Scanning..." : "⟳ Scan Network"}
          </button>
          <button onClick={startDaemon} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid rgba(34,197,94,0.3)", background: "rgba(34,197,94,0.12)", color: "#22c55e", fontSize: 12, cursor: "pointer", fontWeight: 500 }}>
            ▶ Start Daemon
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "0 24px" }}>
        {(["overview", "devices", "commands", "security"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: "10px 18px", border: "none", borderBottom: tab === t ? "2px solid #8b5cf6" : "2px solid transparent", background: "transparent", color: tab === t ? "#e2e8f0" : "#71717a", fontSize: 13, fontWeight: 500, cursor: "pointer", textTransform: "capitalize" }}>
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
        {tab === "overview" && data && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            <StatCard label="Total Devices" value={data.devices.total} icon="🌐" color="#8b5cf6" />
            <StatCard label="Online" value={data.devices.online} icon="✓" color="#22c55e" />
            <StatCard label="Commands Run" value={data.commands.total} icon="⚡" color="#3b82f6" />
            <StatCard label="Success Rate" value={`${data.commands.success_rate}%`} icon="🎯" color="#f59e0b" />

            <div style={{ gridColumn: "span 2", background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "#a1a1aa" }}>DEVICE TYPES</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {Object.entries(data.by_type).map(([type, count]) => (
                  <div key={type} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 6, background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.15)" }}>
                    <span>{TYPE_ICONS[type] || "❓"}</span>
                    <span style={{ fontSize: 12, color: "#e2e8f0" }}>{type}</span>
                    <span style={{ fontSize: 11, color: "#71717a" }}>×{count}</span>
                  </div>
                ))}
                {Object.keys(data.by_type).length === 0 && (
                  <span style={{ fontSize: 12, color: "#71717a" }}>No devices registered yet. Run a scan to discover devices.</span>
                )}
              </div>
            </div>

            <div style={{ gridColumn: "span 2", background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "#a1a1aa" }}>PROTOCOLS</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {Object.entries(data.by_protocol).map(([proto, count]) => (
                  <div key={proto} style={{ padding: "4px 10px", borderRadius: 6, background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.15)", fontSize: 12 }}>
                    {proto} ×{count}
                  </div>
                ))}
                {Object.keys(data.by_protocol).length === 0 && (
                  <span style={{ fontSize: 12, color: "#71717a" }}>No protocol data yet.</span>
                )}
              </div>
            </div>

            <div style={{ gridColumn: "span 4", background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "#a1a1aa" }}>RECENT COMMANDS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {data.recent_commands.length > 0 ? data.recent_commands.map((cmd) => (
                  <div key={cmd.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 10px", borderRadius: 4, background: "rgba(255,255,255,0.02)" }}>
                    <span style={{ fontSize: 11, color: cmd.status === "success" ? "#22c55e" : cmd.status === "error" ? "#ef4444" : "#eab308", width: 8 }}>{cmd.status === "success" ? "●" : cmd.status === "error" ? "●" : "●"}</span>
                    <span style={{ fontSize: 12, color: "#e2e8f0", minWidth: 80 }}>{cmd.action}</span>
                    <span style={{ fontSize: 11, color: "#71717a", flex: 1 }}>{cmd.device_id}</span>
                    <span style={{ fontSize: 11, color: "#a1a1aa" }}>{cmd.latency_ms.toFixed(0)}ms</span>
                  </div>
                )) : (
                  <span style={{ fontSize: 12, color: "#71717a" }}>No commands executed yet.</span>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === "devices" && (
          <div>
            <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
              {["all", "online", ...Object.keys(TYPE_ICONS)].map((f) => (
                <button key={f} onClick={() => setFilter(f)} style={{ padding: "4px 12px", borderRadius: 20, border: filter === f ? "1px solid #8b5cf6" : "1px solid rgba(255,255,255,0.08)", background: filter === f ? "rgba(139,92,246,0.15)" : "transparent", color: filter === f ? "#e2e8f0" : "#71717a", fontSize: 11, cursor: "pointer", textTransform: "capitalize" }}>
                  {TYPE_ICONS[f] ? `${TYPE_ICONS[f]} ${f}` : f}
                </button>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
              {filteredDevices.map((d) => (
                <DeviceCard key={d.id} device={d} onClick={() => setSelectedDevice(d)} />
              ))}
              {filteredDevices.length === 0 && (
                <div style={{ gridColumn: "1/-1", textAlign: "center", padding: 40, color: "#71717a" }}>
                  No devices found. Run a network scan to discover devices.
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "commands" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: "#a1a1aa" }}>EXECUTE COMMAND</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <select value={commandTarget} onChange={(e) => setCommandTarget(e.target.value)} style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "#09090b", color: "#e2e8f0", fontSize: 13 }}>
                  <option value="">Select device...</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>{d.name || d.id} ({d.device_type})</option>
                  ))}
                </select>
                <input value={commandAction} onChange={(e) => setCommandAction(e.target.value)} placeholder="Action (e.g. TURN_ON, SET_BRIGHTNESS)" style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "#09090b", color: "#e2e8f0", fontSize: 13 }} />
                <textarea value={commandParams} onChange={(e) => setCommandParams(e.target.value)} placeholder='{"brightness": 80}' rows={3} style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", background: "#09090b", color: "#e2e8f0", fontSize: 13, fontFamily: "monospace", resize: "vertical" }} />
                <button onClick={executeCommand} style={{ padding: "10px 16px", borderRadius: 6, border: "none", background: "#8b5cf6", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                  ⚡ Execute Command
                </button>
              </div>
            </div>
            <div style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: "#a1a1aa" }}>RESULT</div>
              {commandResult ? (
                <pre style={{ fontSize: 12, color: commandResult.status === "success" ? "#22c55e" : "#ef4444", fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                  {JSON.stringify(commandResult, null, 2)}
                </pre>
              ) : (
                <span style={{ fontSize: 12, color: "#71717a" }}>No command executed yet.</span>
              )}
            </div>
          </div>
        )}

        {tab === "security" && data?.security && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            <StatCard label="Local IP" value={data.security.local_ip} icon="🏠" color="#8b5cf6" />
            <StatCard label="Subnet" value={data.security.local_subnet} icon="🌐" color="#3b82f6" />
            <StatCard label="Active Sessions" value={data.security.network_auth?.active_sessions || 0} icon="🔒" color="#22c55e" />
            <StatCard label="Blocked IPs" value={data.security.network_auth?.blocked_ips || 0} icon="🚫" color="#ef4444" />
            <StatCard label="Security Keys" value={data.security.keys?.length || 0} icon="🔑" color="#f59e0b" />
            <StatCard label="Air-Gapped" value="YES" icon="🛡" color="#22c55e" />
            <div style={{ gridColumn: "span 3", background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "#a1a1aa" }}>SECURITY KEYS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {data.security.keys?.length > 0 ? data.security.keys.map((k: any, i: number) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 10px", borderRadius: 4, background: "rgba(255,255,255,0.02)" }}>
                    <span style={{ fontSize: 11, color: "#22c55e" }}>●</span>
                    <span style={{ fontSize: 12, color: "#e2e8f0", minWidth: 100 }}>{k.purpose}</span>
                    <span style={{ fontSize: 11, color: "#71717a" }}>{k.key_id}</span>
                    {k.is_expired && <span style={{ fontSize: 10, color: "#ef4444", background: "rgba(239,68,68,0.12)", padding: "1px 6px", borderRadius: 3 }}>EXPIRED</span>}
                  </div>
                )) : (
                  <span style={{ fontSize: 12, color: "#71717a" }}>No keys generated yet.</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Device Detail Modal */}
      {selectedDevice && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={() => setSelectedDevice(null)}>
          <div style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: 24, maxWidth: 480, width: "90%" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 24 }}>{TYPE_ICONS[selectedDevice.device_type] || "❓"}</span>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{selectedDevice.name || selectedDevice.id}</div>
                  <div style={{ fontSize: 12, color: "#71717a" }}>{selectedDevice.device_type} • {selectedDevice.protocol}</div>
                </div>
              </div>
              <button onClick={() => setSelectedDevice(null)} style={{ background: "none", border: "none", color: "#71717a", fontSize: 18, cursor: "pointer" }}>✕</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
              <InfoRow label="IP" value={selectedDevice.ip} />
              <InfoRow label="MAC" value={selectedDevice.mac} />
              <InfoRow label="Manufacturer" value={selectedDevice.manufacturer} />
              <InfoRow label="Room" value={selectedDevice.room} />
              <InfoRow label="Status" value={selectedDevice.is_online ? "ONLINE" : "OFFLINE"} color={selectedDevice.is_online ? "#22c55e" : "#ef4444"} />
              <InfoRow label="Signal" value={selectedDevice.signal_strength > 0 ? `${selectedDevice.signal_strength}dBm` : "N/A"} />
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#a1a1aa", marginBottom: 8 }}>STATE</div>
            <pre style={{ fontSize: 11, color: "#a1a1aa", fontFamily: "monospace", background: "#09090b", padding: 10, borderRadius: 6, border: "1px solid rgba(255,255,255,0.06)", maxHeight: 120, overflow: "auto" }}>
              {JSON.stringify(selectedDevice.state || {}, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: any; icon: string; color: string }) {
  return (
    <div style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>{icon}</div>
      <div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#fafafa" }}>{value}</div>
        <div style={{ fontSize: 11, color: "#71717a" }}>{label}</div>
      </div>
    </div>
  );
}

function DeviceCard({ device, onClick }: { device: Device; onClick: () => void }) {
  const color = TYPE_COLORS[device.device_type] || "#71717a";
  return (
    <div onClick={onClick} style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: 14, cursor: "pointer", transition: "border-color 0.15s" }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = color)}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)")}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 20 }}>{TYPE_ICONS[device.device_type] || "❓"}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{device.name || device.id}</div>
            <div style={{ fontSize: 11, color: "#71717a" }}>{device.device_type}</div>
          </div>
        </div>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: device.is_online ? "#22c55e" : "#ef4444" }} />
      </div>
      <div style={{ display: "flex", gap: 8, fontSize: 11, color: "#71717a" }}>
        <span>{device.ip}</span>
        <span>•</span>
        <span>{device.protocol}</span>
        {device.manufacturer && <><span>•</span><span>{device.manufacturer}</span></>}
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
        {Object.entries(device.state || {}).slice(0, 3).map(([k, v]) => (
          <span key={k} style={{ fontSize: 10, color: "#a1a1aa", background: "rgba(255,255,255,0.04)", padding: "2px 6px", borderRadius: 3 }}>
            {k}: {String(v).slice(0, 20)}
          </span>
        ))}
      </div>
    </div>
  );
}

function InfoRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: "4px 0" }}>
      <div style={{ fontSize: 10, color: "#52525b" }}>{label}</div>
      <div style={{ fontSize: 12, color: color || "#e2e8f0" }}>{value || "—"}</div>
    </div>
  );
}
