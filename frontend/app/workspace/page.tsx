"use client";

import { useState, useCallback } from "react";
import Link from "next/link";

type Tab = "workspace" | "worksheets" | "console" | "devices";

interface FileNode {
  name: string;
  type: "file" | "folder";
  children?: FileNode[];
  content?: string;
  icon?: string;
}

const FILE_TREE: FileNode[] = [
  {
    name: "jarvis", type: "folder", children: [
      { name: "config.json", type: "file", icon: "⚙️", content: '{\n  "model": "groq/llama-3.3-70b",\n  "relay": "localhost:9880",\n  "sandbox": "airgapped",\n  "theme": "obsidian-cyberpunk"\n}' },
      { name: "credentials.enc", type: "file", icon: "🔒", content: "# AES-256-GCM encrypted vault\n# DO NOT EDIT MANUALLY" },
      {
        name: "agents", type: "folder", children: [
          { name: "email-agent.json", type: "file", icon: "📧", content: '{\n  "name": "Email Scanner",\n  "type": "autonomous",\n  "steps": ["scan-inbox", "parse-headers", "extract-flights", "summarize"]\n}' },
          { name: "device-agent.json", type: "file", icon: "📡", content: '{\n  "name": "Device Controller",\n  "type": "sovereign",\n  "capabilities": ["tapo", "alexa", "universal"]\n}' },
          { name: "browser-agent.json", type: "file", icon: "🌐", content: '{\n  "name": "Web Navigator",\n  "type": "headless",\n  "browser": "chrome-cdp",\n  "port": 9222\n}' },
        ],
      },
      {
        name: "devices", type: "folder", children: [
          { name: "tapo-plugs.json", type: "file", icon: "💡", content: '[\n  {"name": "Desk Lamp", "ip": "192.168.0.150", "model": "P100"},\n  {"name": "Monitor Light", "ip": "192.168.0.151", "model": "P100"},\n  {"name": "Bedroom Plug", "ip": "192.168.0.152", "model": "P110"}\n]' },
          { name: "echo-devices.json", type: "file", icon: "🔊", content: '[\n  {"name": "Echo Dot", "ip": "192.168.0.120", "type": "alexa"},\n  {"name": "Echo Show", "ip": "192.168.0.121", "type": "alexa"}\n]' },
          { name: "network.json", type: "file", icon: "🌐", content: '{\n  "gateway": "192.168.0.1",\n  "router": "Sky SR213",\n  "subnet": "192.168.0.0/24",\n  "extender": "TP-Link RE200"\n}' },
        ],
      },
      {
        name: "logs", type: "folder", children: [
          { name: "system.log", type: "file", icon: "📋", content: "[2024-01-15 09:30:12] System initialized\n[2024-01-15 09:30:15] Relay connected\n[2024-01-15 09:30:20] 5 devices discovered\n[2024-01-15 09:31:00] Agent spawned: email-scanner" },
          { name: "agent-runs.log", type: "file", icon: "🤖", content: "[2024-01-15 10:15:00] Task: check-email-for-flights\n  Step 1: Scanning inbox... ✓\n  Step 2: Parsing 47 emails... ✓\n  Step 3: Found 2 flight confirmations ✓\n  Status: COMPLETED" },
        ],
      },
    ],
  },
];

export default function WorkspacePage() {
  const [activeTab, setActiveTab] = useState<Tab>("workspace");
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(FILE_TREE[0].children?.[0] || null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(["jarvis", "agents", "devices", "logs"]));
  const [consoleLines, setConsoleLines] = useState<string[]>([
    "$ jarvis --version",
    "JARVIS v3.0 Sovereign Network Orchestrator",
    "$ relay status",
    "Relay: Online (localhost:9880)",
    "Devices: 5 connected",
    "$ _",
  ]);
  const [consoleInput, setConsoleInput] = useState("");
  const [sidebarWidth, setSidebarWidth] = useState(220);

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  };

  const handleConsoleCommand = async (cmd: string) => {
    if (!cmd.trim()) return;
    setConsoleLines(prev => [...prev, `$ ${cmd}`]);
    setConsoleInput("");

    // Process command
    const lower = cmd.toLowerCase().trim();
    if (lower === "help") {
      setConsoleLines(prev => [...prev, "Commands: help, status, devices, scan, clear, agents"]);
    } else if (lower === "status") {
      setConsoleLines(prev => [...prev, "Relay: Online | Model: GROQ | Agents: 0 active"]);
    } else if (lower === "devices") {
      try {
        const res = await fetch("/api/relay/devices?user_id=local");
        const data = await res.json();
        const devs = data.devices || [];
        setConsoleLines(prev => [...prev, `${devs.length} devices found:`, ...devs.map((d: any) => `  ${d.name} (${d.ip})`)]);
      } catch { setConsoleLines(prev => [...prev, "Error fetching devices"]); }
    } else if (lower === "scan") {
      setConsoleLines(prev => [...prev, "Scanning network..."]);
      try {
        await fetch("/api/relay/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }) });
        setConsoleLines(prev => [...prev, "Scan complete. Run 'devices' to see results."]);
      } catch { setConsoleLines(prev => [...prev, "Scan failed"]); }
    } else if (lower === "clear") {
      setConsoleLines([]);
    } else if (lower === "agents") {
      try {
        const res = await fetch("/api/autonomous/tasks");
        const data = await res.json();
        const tasks = data.tasks || [];
        setConsoleLines(prev => [...prev, `${tasks.length} tasks:`, ...tasks.map((t: any) => `  [${t.status}] ${t.intent}`)]);
      } catch { setConsoleLines(prev => [...prev, "Error fetching agents"]); }
    } else {
      setConsoleLines(prev => [...prev, `Unknown command: ${cmd}. Type 'help' for commands.`]);
    }
  };

  const renderTree = (nodes: FileNode[], path = "") => {
    return nodes.map(node => {
      const fullPath = `${path}/${node.name}`;
      const isExpanded = expandedFolders.has(fullPath);
      const isSelected = selectedFile?.name === node.name && selectedFile?.type === node.type;

      return (
        <div key={fullPath}>
          <div
            onClick={() => {
              if (node.type === "folder") toggleFolder(fullPath);
              else setSelectedFile(node);
            }}
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "4px 8px", cursor: "pointer",
              paddingLeft: `${8 + (path.split("/").length - 2) * 12}px`,
              background: isSelected ? "rgba(0,255,102,0.08)" : "transparent",
              borderLeft: isSelected ? "2px solid #00FF66" : "2px solid transparent",
              transition: "all 0.1s",
            }}
          >
            {node.type === "folder" && (
              <span style={{ fontSize: 8, color: "#667085", width: 12 }}>{isExpanded ? "▼" : "▶"}</span>
            )}
            <span style={{ fontSize: 12 }}>{node.icon || (node.type === "folder" ? "📁" : "📄")}</span>
            <span style={{
              fontSize: 11, color: isSelected ? "#00FF66" : "#9ca3af",
              fontWeight: isSelected ? 500 : 400,
            }}>
              {node.name}
            </span>
          </div>
          {node.type === "folder" && isExpanded && node.children && (
            <div>{renderTree(node.children, fullPath)}</div>
          )}
        </div>
      );
    });
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        .wf { animation: fade-in 0.2s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Header */}
      <header style={{ height: 36, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
          <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
          <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>WORKSPACE</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {(["workspace", "worksheets", "console", "devices"] as Tab[]).map(tab => (
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

      {/* Content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {activeTab === "workspace" && (
          <>
            {/* File Tree Sidebar */}
            <div style={{ width: sidebarWidth, borderRight: "1px solid #1a1d23", overflow: "auto", flexShrink: 0, background: "#08090c" }}>
              <div style={{ padding: "8px 12px", fontSize: 8, color: "#667085", letterSpacing: "0.1em", borderBottom: "1px solid #1a1d23" }}>
                EXPLORER
              </div>
              {renderTree(FILE_TREE)}
            </div>

            {/* Editor */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              {/* File tabs */}
              <div style={{ height: 32, background: "#08090c", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", padding: "0 8px" }}>
                {selectedFile && (
                  <div style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "4px 12px",
                    background: "#0d0f12", borderRadius: "4px 4px 0 0", borderBottom: "1px solid #00FF66",
                    fontSize: 10, color: "#e5e5e5",
                  }}>
                    <span>{selectedFile.icon || "📄"}</span>
                    <span>{selectedFile.name}</span>
                    <span onClick={() => setSelectedFile(null)} style={{ cursor: "pointer", color: "#667085", fontSize: 8, marginLeft: 4 }}>✕</span>
                  </div>
                )}
              </div>

              {/* Editor content */}
              <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
                {selectedFile ? (
                  <div className="wf">
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                      <span style={{ fontSize: 14 }}>{selectedFile.icon || "📄"}</span>
                      <span style={{ fontSize: 13, fontWeight: 500 }}>{selectedFile.name}</span>
                      <span style={{ fontSize: 8, color: "#667085", padding: "2px 6px", borderRadius: 3, background: "#1a1d23" }}>
                        {selectedFile.name.split(".").pop()?.toUpperCase()}
                      </span>
                    </div>
                    <pre style={{
                      background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 6,
                      padding: 16, fontSize: 12, lineHeight: 1.6, color: "#9ca3af",
                      overflow: "auto", whiteSpace: "pre-wrap",
                    }}>
                      {selectedFile.content || "# No content"}
                    </pre>
                  </div>
                ) : (
                  <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>📁</div>
                      <div style={{ fontSize: 11, color: "#667085" }}>Select a file to view</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {activeTab === "worksheets" && (
          <div className="wf" style={{ flex: 1, overflow: "auto", padding: 24 }}>
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Worksheets</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[
                  { title: "Flight Check-in", icon: "✈️", status: "ready", lastRun: "Never", steps: ["Scan email for confirmation", "Navigate to airline site", "Enter booking reference", "Select seats", "Download boarding pass"] },
                  { title: "Morning Brief", icon: "☀️", status: "ready", lastRun: "Never", steps: ["Check calendar for today", "Scan emails for priorities", "Weather report", "News summary", "Device status check"] },
                  { title: "Device Audit", icon: "📡", status: "ready", lastRun: "Never", steps: ["ARP scan network", "Identify new devices", "Check security posture", "Update device registry", "Generate report"] },
                  { title: "Email Triage", icon: "📧", status: "ready", lastRun: "Never", steps: ["Fetch unread emails", "Classify by priority", "Extract action items", "Draft responses", "Summarize inbox"] },
                ].map(ws => (
                  <div key={ws.title} style={{
                    background: "#0d0f12", border: "1px solid #1a1d23", borderRadius: 8,
                    padding: 16, cursor: "pointer", transition: "all 0.15s",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                      <span style={{ fontSize: 18 }}>{ws.icon}</span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 500 }}>{ws.title}</div>
                        <div style={{ fontSize: 8, color: "#667085" }}>Last run: {ws.lastRun}</div>
                      </div>
                      <span style={{
                        marginLeft: "auto", padding: "2px 6px", borderRadius: 3, fontSize: 8,
                        background: "rgba(0,255,102,0.1)", color: "#00FF66",
                      }}>
                        {ws.status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      {ws.steps.map((step, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#1a1d23", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 7, color: "#667085" }}>
                            {i + 1}
                          </div>
                          <span style={{ fontSize: 9, color: "#9ca3af" }}>{step}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "console" && (
          <div className="wf" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, overflow: "auto", padding: 16, background: "#08090c" }}>
              {consoleLines.map((line, i) => (
                <div key={i} style={{
                  fontSize: 11, lineHeight: 1.6,
                  color: line.startsWith("$") ? "#00FF66" : line.startsWith("  ") ? "#667085" : "#9ca3af",
                  fontFamily: "var(--font-mono)",
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
                placeholder="Type a command..."
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
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Device Registry</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { name: "Desk Lamp", ip: "192.168.0.150", type: "Tapo P100", status: "online", icon: "💡" },
                  { name: "Monitor Light", ip: "192.168.0.151", type: "Tapo P100", status: "online", icon: "💡" },
                  { name: "Bedroom Plug", ip: "192.168.0.152", type: "Tapo P110", status: "online", icon: "💡" },
                  { name: "Echo Dot", ip: "192.168.0.120", type: "Amazon Alexa", status: "online", icon: "🔊" },
                  { name: "Echo Show", ip: "192.168.0.121", type: "Amazon Alexa", status: "online", icon: "🔊" },
                  { name: "HP Printer", ip: "192.168.0.130", type: "HP LaserJet", status: "idle", icon: "🖨️" },
                  { name: "Sky Router", ip: "192.168.0.1", type: "Sky SR213", status: "gateway", icon: "🌐" },
                  { name: "TP-Link Extender", ip: "192.168.0.2", type: "RE200", status: "repeating", icon: "📡" },
                ].map(d => (
                  <div key={d.name} style={{
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
                      background: d.status === "online" ? "rgba(0,255,102,0.1)" : "rgba(255,179,0,0.1)",
                      color: d.status === "online" ? "#00FF66" : "#FFB300",
                    }}>
                      {d.status.toUpperCase()}
                    </span>
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
