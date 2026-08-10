"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { BASE, safeJson } from "@/lib/api";

type Tab = "workspace" | "worksheets" | "console" | "devices";

interface Device {
  name: string;
  ip: string;
  type: string;
  status: string;
  icon: string;
}

const DEVICE_ICONS: Record<string, string> = {
  tapo: "💡", alexa: "🔊", printer: "🖨️", phone: "📱", laptop: "💻", desktop: "🖥️",
  router: "🌐", camera: "📷", tv: "📺", speaker: "🔊", default: "📡",
};

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  online: { bg: "rgba(0,255,102,0.1)", fg: "#00FF66" },
  offline: { bg: "rgba(255,68,68,0.1)", fg: "#FF4444" },
  idle: { bg: "rgba(255,179,0,0.1)", fg: "#FFB300" },
  gateway: { bg: "rgba(0,150,255,0.1)", fg: "#0096FF" },
  repeating: { bg: "rgba(0,150,255,0.1)", fg: "#0096FF" },
};

export default function WorkspacePage() {
  const [activeTab, setActiveTab] = useState<Tab>("console");
  const [devices, setDevices] = useState<Device[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [consoleLines, setConsoleLines] = useState<string[]>([
    "$ jarvis --version",
    "JARVIS v4.0 Sovereign Network Orchestrator",
    "$ relay status",
    "Checking relay...",
    "$ _",
  ]);
  const [consoleInput, setConsoleInput] = useState("");
  const [scanning, setScanning] = useState(false);

  // Fetch real devices
  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/relay/devices?user_id=local`);
      const data = await safeJson(res);
      const devs = (data?.devices || []).map((d: any) => ({
        name: d.name || d.hostname || "Unknown Device",
        ip: d.ip || d.address || "0.0.0.0",
        type: d.type || d.device_type || d.model || "Unknown",
        status: d.status || "online",
        icon: DEVICE_ICONS[(d.type || "").toLowerCase()] || DEVICE_ICONS.default,
      }));
      setDevices(devs);
    } catch { /* relay may not be connected */ }
  }, []);

  // Fetch real tasks
  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/autonomous/tasks`);
      const data = await safeJson(res);
      setTasks(data?.tasks || []);
    } catch { /* ok */ }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchDevices();
    fetchTasks();
    const interval = setInterval(() => { fetchDevices(); fetchTasks(); }, 10000);
    return () => clearInterval(interval);
  }, [fetchDevices, fetchTasks]);

  // Check relay status on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${BASE}/api/health`);
        const data = await safeJson(res);
        const relayUp = data?.relay === "alive" || data?.relay_alive;
        setConsoleLines(prev => [
          prev[0], prev[1],
          `$ relay status`,
          relayUp ? "Relay: ONLINE" : "Relay: OFFLINE (start relay.py on your machine)",
          `$ _`,
        ]);
      } catch {
        setConsoleLines(prev => [
          prev[0], prev[1],
          `$ relay status`,
          "Relay: OFFLINE (backend unreachable)",
          `$ _`,
        ]);
      }
    })();
  }, []);

  const handleConsoleCommand = async (cmd: string) => {
    if (!cmd.trim()) return;
    setConsoleLines(prev => [...prev.slice(0, -1), `$ ${cmd}`, ""]);
    setConsoleInput("");

    const lower = cmd.toLowerCase().trim();
    if (lower === "help") {
      setConsoleLines(prev => [...prev.slice(0, -1), "Commands: help, status, devices, scan, clear, agents, tasks, health"]);
    } else if (lower === "status") {
      try {
        const res = await fetch(`${BASE}/api/health`);
        const data = await safeJson(res);
        const relay = data?.relay === "alive" ? "ONLINE" : "OFFLINE";
        setConsoleLines(prev => [...prev.slice(0, -1), `Relay: ${relay} | Model: ${data?.model || 'GROQ'} | Agents: ${data?.agents || 0} active`]);
      } catch { setConsoleLines(prev => [...prev.slice(0, -1), "Backend unreachable"]); }
    } else if (lower === "devices") {
      if (devices.length === 0) {
        setConsoleLines(prev => [...prev.slice(0, -1), "No devices found. Run 'scan' to discover."]);
      } else {
        setConsoleLines(prev => [...prev.slice(0, -1), `${devices.length} devices:`, ...devices.map(d => `  ${d.icon} ${d.name} (${d.ip}) [${d.status}]`)]);
      }
    } else if (lower === "scan") {
      setScanning(true);
      setConsoleLines(prev => [...prev.slice(0, -1), "Scanning network..."]);
      try {
        await fetch(`${BASE}/api/relay/action`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }),
        });
        await new Promise(r => setTimeout(r, 3000));
        await fetchDevices();
        setConsoleLines(prev => [...prev.slice(0, -1), `Scan complete. ${devices.length} devices found.`]);
      } catch { setConsoleLines(prev => [...prev.slice(0, -1), "Scan failed — relay may be offline"]); }
      setScanning(false);
    } else if (lower === "clear") {
      setConsoleLines(["$ _"]);
    } else if (lower === "agents" || lower === "tasks") {
      if (tasks.length === 0) {
        setConsoleLines(prev => [...prev.slice(0, -1), "No active tasks."]);
      } else {
        setConsoleLines(prev => [...prev.slice(0, -1), `${tasks.length} tasks:`, ...tasks.map((t: any) => `  [${t.status}] ${t.intent || t.task || "unnamed"}`)]);
      }
    } else if (lower === "health") {
      try {
        const res = await fetch(`${BASE}/api/system/stats`);
        const data = await safeJson(res);
        setConsoleLines(prev => [...prev.slice(0, -1), `CPU: ${data?.cpu_percent || '?'}% | RAM: ${data?.memory_gb || '?'}GB | Disk: ${data?.disk_percent || '?'}%`]);
      } catch { setConsoleLines(prev => [...prev.slice(0, -1), "Could not fetch system stats"]); }
    } else {
      setConsoleLines(prev => [...prev.slice(0, -1), `Unknown: ${cmd}. Type 'help'.`]);
    }
    setConsoleLines(prev => [...prev, "$ _"]);
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        .wf { animation: fade-in 0.2s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      <header style={{ height: 36, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
          <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
          <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>WORKSPACE</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {(["console", "devices", "workspace", "worksheets"] as Tab[]).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              padding: "4px 10px", borderRadius: 3, fontSize: 9, fontWeight: 600,
              fontFamily: "inherit", cursor: "pointer", letterSpacing: "0.06em",
              background: activeTab === tab ? "rgba(0,255,102,0.12)" : "transparent",
              color: activeTab === tab ? "#00FF66" : "#667085", border: "none",
            }}>
              {tab.toUpperCase()}
            </button>
          ))}
        </div>
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {activeTab === "console" && (
          <div className="wf" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, overflow: "auto", padding: 16, background: "#08090c" }}>
              {consoleLines.map((line, i) => (
                <div key={i} style={{
                  fontSize: 11, lineHeight: 1.6,
                  color: line.startsWith("$") ? "#00FF66" : line.startsWith("  ") ? "#667085" : "#9ca3af",
                  fontFamily: "inherit",
                }}>
                  {line}
                </div>
              ))}
            </div>
            <div style={{ padding: "8px 16px", borderTop: "1px solid #1a1d23", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: "#00FF66" }}>$</span>
              <input
                value={consoleInput}
                onChange={e => setConsoleInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") handleConsoleCommand(consoleInput); }}
                placeholder="Type a command... (help, status, devices, scan, tasks, health)"
                style={{
                  flex: 1, background: "transparent", border: "none", outline: "none",
                  fontSize: 11, color: "#e5e5e5", fontFamily: "inherit",
                }}
              />
            </div>
          </div>
        )}

        {activeTab === "devices" && (
          <div className="wf" style={{ flex: 1, overflow: "auto", padding: 24 }}>
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Device Registry</div>
                <button onClick={async () => {
                  setScanning(true);
                  await fetch(`${BASE}/api/relay/action`, {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }),
                  });
                  await new Promise(r => setTimeout(r, 3000));
                  await fetchDevices();
                  setScanning(false);
                }} disabled={scanning} style={{
                  padding: "6px 12px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: scanning ? "rgba(0,255,102,0.05)" : "rgba(0,255,102,0.12)",
                  color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)", cursor: scanning ? "wait" : "pointer",
                }}>
                  {scanning ? "SCANNING..." : "SCAN NETWORK"}
                </button>
              </div>
              {devices.length === 0 ? (
                <div style={{ textAlign: "center", padding: 40, color: "#667085" }}>
                  <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.3 }}>📡</div>
                  <div style={{ fontSize: 12 }}>No devices found</div>
                  <div style={{ fontSize: 10, marginTop: 4 }}>Click "Scan Network" or ensure relay is running</div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {devices.map((d, i) => {
                    const sc = STATUS_COLORS[d.status] || STATUS_COLORS.online;
                    return (
                      <div key={i} style={{
                        display: "flex", alignItems: "center", gap: 12, padding: "10px 14px",
                        background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 6,
                      }}>
                        <span style={{ fontSize: 18 }}>{d.icon}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 11, fontWeight: 500 }}>{d.name}</div>
                          <div style={{ fontSize: 9, color: "#667085" }}>{d.ip} · {d.type}</div>
                        </div>
                        <span style={{
                          padding: "2px 8px", borderRadius: 3, fontSize: 8, letterSpacing: "0.06em",
                          background: sc.bg, color: sc.fg,
                        }}>
                          {d.status.toUpperCase()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "workspace" && (
          <div className="wf" style={{ flex: 1, overflow: "auto", padding: 24 }}>
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>System Overview</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 24 }}>
                {[
                  { label: "DEVICES", value: devices.length, icon: "📡", color: "#00FF66" },
                  { label: "TASKS", value: tasks.length, icon: "🤖", color: "#FFB300" },
                  { label: "RELAY", value: "CHECK", icon: "🔗", color: "#0096FF" },
                ].map(s => (
                  <div key={s.label} style={{
                    background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
                    padding: 16, textAlign: "center",
                  }}>
                    <div style={{ fontSize: 18, marginBottom: 4 }}>{s.icon}</div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: s.color }}>{s.value}</div>
                    <div style={{ fontSize: 8, color: "#667085", letterSpacing: "0.1em", marginTop: 2 }}>{s.label}</div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Active Tasks</div>
              {tasks.length === 0 ? (
                <div style={{ color: "#667085", fontSize: 11 }}>No active tasks. Use the chat to spawn agents.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {tasks.map((t: any, i: number) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                      background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 6,
                    }}>
                      <span style={{ fontSize: 12 }}>🤖</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 11 }}>{t.intent || t.task || "Unnamed task"}</div>
                        <div style={{ fontSize: 9, color: "#667085" }}>{t.status} · {t.agent || "auto"}</div>
                      </div>
                      {t.progress !== undefined && (
                        <div style={{ width: 60, height: 4, background: "#1a1d23", borderRadius: 2, overflow: "hidden" }}>
                          <div style={{ width: `${t.progress}%`, height: "100%", background: "#00FF66", borderRadius: 2 }} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "worksheets" && (
          <div className="wf" style={{ flex: 1, overflow: "auto", padding: 24 }}>
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Autonomous Worksheets</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[
                  { title: "Network Discovery", icon: "📡", desc: "Scan all devices on your network", prompt: "scan my entire network and list all devices", status: "ready" },
                  { title: "Device Health Check", icon: "🩺", desc: "Check status of all connected devices", prompt: "check the status of all my devices", status: "ready" },
                  { title: "Smart Home Control", icon: "🏠", desc: "Control lights, plugs, and speakers", prompt: "turn on all lights", status: "ready" },
                  { title: "System Monitor", icon: "📊", desc: "Monitor CPU, RAM, disk usage", prompt: "show me system resource usage", status: "ready" },
                ].map(ws => (
                  <div key={ws.title} onClick={async () => {
                    try {
                      await fetch(`${BASE}/api/autonomous/start`, {
                        method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ intent: ws.prompt, user_id: "local" }),
                      });
                      await fetchTasks();
                    } catch { /* ok */ }
                  }} style={{
                    background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
                    padding: 16, cursor: "pointer", transition: "all 0.15s",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 18 }}>{ws.icon}</span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 500 }}>{ws.title}</div>
                        <div style={{ fontSize: 9, color: "#667085" }}>{ws.desc}</div>
                      </div>
                    </div>
                    <div style={{
                      display: "inline-block", padding: "2px 8px", borderRadius: 3, fontSize: 8,
                      background: "rgba(0,255,102,0.1)", color: "#00FF66", letterSpacing: "0.06em",
                    }}>
                      CLICK TO RUN
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
