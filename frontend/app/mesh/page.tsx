"use client";

import { useEffect, useState } from "react";
import { BASE } from "@/lib/api";

const API = BASE;

export default function MeshPage() {
  const [topology, setTopology] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [devices, setDevices] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [cmdInput, setCmdInput] = useState("");
  const [cmdTarget, setCmdTarget] = useState("");
  const [cmdResult, setCmdResult] = useState<any>(null);

  useEffect(() => { fetchData(); }, []);

  async function fetchData() {
    try {
      const [t, s, d, h] = await Promise.all([
        fetch(`${API}/api/mesh/topology`).then(r => r.json()),
        fetch(`${API}/api/mesh/stats`).then(r => r.json()),
        fetch(`${API}/api/mesh/devices`).then(r => r.json()),
        fetch(`${API}/api/mesh/history`).then(r => r.json()),
      ]);
      setTopology(t);
      setStats(s);
      setDevices(d.devices || []);
      setHistory(h.history || []);
    } catch {}
  }

  async function sendCommand() {
    if (!cmdInput.trim()) return;
    try {
      const r = await fetch(`${API}/api/mesh/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmdInput, target_device_id: cmdTarget || undefined }),
      });
      setCmdResult(await r.json());
      setCmdInput("");
      fetchData();
    } catch { setCmdResult({ error: "failed" }); }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#080a0d", color: "#e5e5e5", padding: "24px 32px", fontFamily: "'JetBrains Mono', monospace" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: "#00FF66" }}>Device Mesh Network</h1>
        <p style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>Cross-device orchestration, failover, and coordination</p>

        {/* Stats */}
        {stats && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
            <StatCard label="Total Devices" value={stats.devices?.total || 0} color="#00FF66" />
            <StatCard label="Online" value={stats.devices?.online || 0} color="#00FF66" />
            <StatCard label="Offline" value={stats.devices?.offline || 0} color="#ef4444" />
            <StatCard label="Commands" value={stats.commands?.total || 0} color="#3b82f6" />
            <StatCard label="Avg Latency" value={`${stats.commands?.avg_latency_ms || 0}ms`} color="#fbbf24" />
          </div>
        )}

        {/* Mesh Topology */}
        <Section title="Mesh Topology">
          {!topology?.nodes?.length ? <Empty text="No devices in mesh" /> : (
            <div style={{ position: "relative", padding: 20, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23", overflow: "hidden" }}>
              <svg width="100%" height="300" style={{ overflow: "visible" }}>
                {topology.edges.map((e: any, i: number) => {
                  const fromNode = topology.nodes.find((n: any) => n.id === e.from);
                  const toNode = topology.nodes.find((n: any) => n.id === e.to);
                  if (!fromNode || !toNode) return null;
                  const fi = topology.nodes.indexOf(fromNode);
                  const ti = topology.nodes.indexOf(toNode);
                  const x1 = 100 + (fi % 5) * 180, y1 = 60 + Math.floor(fi / 5) * 100;
                  const x2 = 100 + (ti % 5) * 180, y2 = 60 + Math.floor(ti / 5) * 100;
                  return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(0,255,102,0.15)" strokeWidth="1" />;
                })}
                {topology.nodes.map((n: any, i: number) => {
                  const x = 100 + (i % 5) * 180, y = 60 + Math.floor(i / 5) * 100;
                  return (
                    <g key={n.id}>
                      <circle cx={x} cy={y} r={20} fill={n.status === "online" ? "rgba(0,255,102,0.15)" : "rgba(239,68,68,0.15)"}
                        stroke={n.status === "online" ? "#00FF66" : "#ef4444"} strokeWidth="1.5" />
                      <text x={x} y={y + 4} textAnchor="middle" fill="#e5e5e5" fontSize="9" fontFamily="JetBrains Mono">{n.type?.slice(0, 3).toUpperCase()}</text>
                      <text x={x} y={y + 35} textAnchor="middle" fill="#667085" fontSize="7" fontFamily="JetBrains Mono">{n.label}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </Section>

        {/* Devices */}
        <Section title="Connected Devices">
          {devices.length === 0 ? <Empty text="No devices registered" /> : (
            <div style={{ display: "grid", gap: 6 }}>
              {devices.map(d => (
                <div key={d.id} style={{ display: "grid", gridTemplateColumns: "1fr 120px 80px 80px 1fr", gap: 12, alignItems: "center", padding: "10px 14px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 11 }}>
                  <span style={{ fontWeight: 600 }}>{d.name}</span>
                  <span style={{ color: "#667085" }}>{d.type}</span>
                  <span style={{ color: d.status === "online" ? "#00FF66" : "#ef4444" }}>{d.status}</span>
                  <span style={{ color: "#667085" }}>{d.zone}</span>
                  <span style={{ color: "#667085", fontSize: 9 }}>{d.ip_address || "no ip"}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Command Console */}
        <Section title="Command Console">
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input value={cmdInput} onChange={e => setCmdInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendCommand()}
              placeholder="Enter command..." style={{ flex: 1, padding: "8px 12px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", color: "#e5e5e5", fontSize: 11, fontFamily: "inherit", outline: "none" }} />
            <input value={cmdTarget} onChange={e => setCmdTarget(e.target.value)} placeholder="Target device ID"
              style={{ width: 160, padding: "8px 12px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", color: "#e5e5e5", fontSize: 11, fontFamily: "inherit", outline: "none" }} />
            <button onClick={sendCommand} style={{ padding: "8px 16px", borderRadius: 6, background: "#00FF66", color: "#000", fontSize: 11, fontWeight: 700, border: "none", cursor: "pointer" }}>Send</button>
          </div>
          {cmdResult && (
            <div style={{ padding: 10, borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10, color: cmdResult.error ? "#ef4444" : "#00FF66", fontFamily: "inherit" }}>
              {JSON.stringify(cmdResult, null, 2)}
            </div>
          )}
        </Section>

        {/* Command History */}
        <Section title="Command History">
          {history.length === 0 ? <Empty text="No commands yet" /> : (
            <div style={{ display: "grid", gap: 4 }}>
              {history.slice(0, 20).map((h, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 12px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10 }}>
                  <span style={{ color: "#e5e5e5" }}>{h.command}</span>
                  <span style={{ color: h.status === "success" ? "#00FF66" : "#ef4444" }}>{h.status}</span>
                  <span style={{ color: "#667085" }}>{h.latency_ms?.toFixed(1)}ms</span>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={{ marginBottom: 24 }}><h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>{title.toUpperCase()}</h2>{children}</div>;
}
function StatCard({ label, value, color }: { label: string; value: any; color: string }) {
  return <div style={{ padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23", textAlign: "center" }}><div style={{ fontSize: 9, color: "#667085", marginBottom: 4 }}>{label}</div><div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div></div>;
}
function Empty({ text }: { text: string }) {
  return <div style={{ padding: 20, textAlign: "center", color: "#667085", fontSize: 10, background: "#0d0f12", borderRadius: 6, border: "1px solid #1a1d23" }}>{text}</div>;
}
