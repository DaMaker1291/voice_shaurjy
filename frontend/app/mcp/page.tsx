"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { BASE, safeJson, getMCPTools, getMCPStatus, callMCPTool, getMCPGuardrails, getMCPRegistry, getMCPCompliance, getMCPWSUrl } from "@/lib/api";

type Tab = "servers" | "tools" | "execute" | "guardrails" | "compliance";

interface MCPServer {
  name: string;
  transport: string;
  connected: boolean;
  tool_count: number;
}

interface MCPTool {
  name: string;
  description: string;
  server: string;
  input_schema: Record<string, any>;
}

interface GuardrailRule {
  id: string;
  name: string;
  risk_level: string;
  hits: number;
}

interface ComplianceEntry {
  timestamp: string;
  tool_name: string;
  server_name: string;
  duration_ms: number;
  is_error: boolean;
  identity_hash: string;
}

export default function MCPPage() {
  const [tab, setTab] = useState<Tab>("servers");
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [guardrails, setGuardrails] = useState<any>(null);
  const [compliance, setCompliance] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [wsConnected, setWsConnected] = useState(false);

  // Execute state
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
  const [toolArgs, setToolArgs] = useState("{}");
  const [execResult, setExecResult] = useState<any>(null);
  const [executing, setExecuting] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statusRes, toolsRes, guardRes, compRes] = await Promise.allSettled([
        getMCPStatus(),
        getMCPTools(),
        getMCPGuardrails(),
        getMCPCompliance(),
      ]);

      if (statusRes.status === "fulfilled") {
        const s = statusRes.value;
        setServers(s.servers || []);
      }
      if (toolsRes.status === "fulfilled") {
        setTools(toolsRes.value.tools || []);
      }
      if (guardRes.status === "fulfilled") {
        setGuardrails(guardRes.value);
      }
      if (compRes.status === "fulfilled") {
        setCompliance(compRes.value);
      }
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // WebSocket for live MCP
  useEffect(() => {
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(getMCPWSUrl());
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "tool_result" || msg.type === "tool_error") {
            setExecResult(msg);
            setExecuting(false);
          }
          if (msg.type === "tools_list") {
            setTools(msg.tools || []);
          }
          if (msg.type === "mcp_status") {
            setServers(msg.servers || []);
          }
        } catch {}
      };
    } catch {}
    wsRef.current = ws;
    return () => { ws?.close(); };
  }, []);

  const executeTool = async () => {
    if (!selectedTool) return;
    setExecuting(true);
    setExecResult(null);
    try {
      let args = {};
      try { args = JSON.parse(toolArgs); } catch {}

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "call", tool: selectedTool.name, arguments: args }));
      } else {
        const result = await callMCPTool(selectedTool.name, args);
        setExecResult(result);
        setExecuting(false);
      }
    } catch (e: any) {
      setExecResult({ type: "tool_error", error: e.message });
      setExecuting(false);
    }
  };

  const sendWSText = (msg: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  };

  const connectedCount = servers.filter(s => s.connected).length;
  const totalTools = tools.length;

  return (
    <div style={{ minHeight: "100vh", background: "#09090b", color: "#e4e4e7", fontFamily: "var(--font-sans, system-ui, sans-serif)", padding: "20px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <Link href="/" style={{ fontSize: 12, color: "#52525b", textDecoration: "none" }}>← Back to JARVIS</Link>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: "4px 0 0", color: "#fff" }}>MCP Gateway</h1>
          <p style={{ fontSize: 13, color: "#71717a", margin: "2px 0 0" }}>Model Context Protocol — Tool orchestration, security & compliance</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: wsConnected ? "#00FF66" : "#FF3333", boxShadow: wsConnected ? "0 0 8px rgba(0,255,102,0.4)" : "none" }} />
            <span style={{ color: wsConnected ? "#00FF66" : "#FF3333" }}>{wsConnected ? "LIVE" : "OFFLINE"}</span>
          </div>
          <button onClick={fetchAll} style={{ padding: "6px 14px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#a1a1aa", border: "1px solid rgba(255,255,255,0.1)", cursor: "pointer", fontSize: 12 }}>↻ Refresh</button>
        </div>
      </div>

      {/* Stats Banner */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <StatBox label="Servers" value={`${connectedCount}/${servers.length}`} color="#00B4D8" />
        <StatBox label="Tools" value={`${totalTools}`} color="#00FF66" />
        <StatBox label="Guardrails" value={`${guardrails?.total_rules || 0}`} color="#FFB300" />
        <StatBox label="Audit Entries" value={`${compliance?.total_entries || 0}`} color="#A855F7" />
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20, flexWrap: "wrap" }}>
        {(["servers", "tools", "execute", "guardrails", "compliance"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: "8px 16px", borderRadius: 8, fontSize: 12, fontWeight: 500, border: "none", cursor: "pointer", textTransform: "capitalize",
              background: tab === t ? "rgba(0,180,216,0.15)" : "rgba(255,255,255,0.03)",
              color: tab === t ? "#00B4D8" : "#71717a", transition: "all 0.2s" }}>
            {t === "servers" ? "🖥️ Servers" : t === "tools" ? "🔧 Tools" : t === "execute" ? "▶️ Execute" : t === "guardrails" ? "🛡️ Guardrails" : "📋 Compliance"}
          </button>
        ))}
      </div>

      {loading && <div style={{ color: "#71717a", fontSize: 13, padding: 40, textAlign: "center" }}>Loading MCP data...</div>}
      {error && <div style={{ color: "#FF3333", fontSize: 13, padding: 12, background: "rgba(255,51,51,0.1)", borderRadius: 8 }}>{error}</div>}

      {/* Servers Tab */}
      {!loading && tab === "servers" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Connected Servers</h2>
            <button onClick={() => sendWSText({ type: "status" })} style={{ padding: "4px 12px", borderRadius: 6, background: "rgba(0,180,216,0.1)", color: "#00B4D8", border: "1px solid rgba(0,180,216,0.2)", cursor: "pointer", fontSize: 11 }}>Ping WS</button>
          </div>
          {servers.length === 0 ? (
            <EmptyState message="No MCP servers discovered. Check your MCP config files." />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
              {servers.map((s, i) => (
                <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 600 }}>{s.name}</span>
                    <span style={{ fontSize: 9, padding: "2px 8px", borderRadius: 4, background: s.connected ? "rgba(0,255,102,0.1)" : "rgba(255,51,51,0.1)", color: s.connected ? "#00FF66" : "#FF3333", fontWeight: 600 }}>
                      {s.connected ? "CONNECTED" : "DISCONNECTED"}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "#71717a", marginBottom: 4 }}>Transport: {s.transport}</div>
                  <div style={{ fontSize: 11, color: "#71717a" }}>Tools: {s.tool_count}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tools Tab */}
      {!loading && tab === "tools" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Available Tools ({tools.length})</h2>
            <button onClick={() => sendWSText({ type: "list_tools" })} style={{ padding: "4px 12px", borderRadius: 6, background: "rgba(0,255,102,0.1)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)", cursor: "pointer", fontSize: 11 }}>Refresh via WS</button>
          </div>
          {tools.length === 0 ? (
            <EmptyState message="No tools discovered. MCP servers may not be connected." />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 12 }}>
              {tools.map((t, i) => (
                <div key={i} onClick={() => { setSelectedTool(t); setTab("execute"); setToolArgs("{}"); }}
                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16, cursor: "pointer", transition: "border-color 0.2s" }}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(0,180,216,0.3)")}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)")}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "#00B4D8" }}>{t.name}</span>
                    <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "rgba(255,255,255,0.05)", color: "#71717a" }}>{t.server}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "#a1a1aa", lineHeight: 1.4 }}>{t.description || "No description"}</div>
                  {t.input_schema && Object.keys(t.input_schema).length > 0 && (
                    <div style={{ marginTop: 8, fontSize: 10, color: "#52525b" }}>
                      Params: {Object.keys(t.input_schema).join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Execute Tab */}
      {!loading && tab === "execute" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Left: Tool selection + args */}
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Execute Tool</h2>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 11, color: "#71717a", display: "block", marginBottom: 4 }}>Select Tool</label>
              <select value={selectedTool?.name || ""} onChange={e => {
                const t = tools.find(x => x.name === e.target.value);
                setSelectedTool(t || null);
                setToolArgs(t?.input_schema ? JSON.stringify(Object.fromEntries(Object.keys(t.input_schema).map(k => [k, ""])), null, 2) : "{}");
              }}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#e4e4e7", border: "1px solid rgba(255,255,255,0.1)", fontSize: 12, fontFamily: "var(--font-mono, monospace)" }}>
                <option value="">-- Select a tool --</option>
                {tools.map(t => <option key={t.name} value={t.name}>{t.name} ({t.server})</option>)}
              </select>
            </div>
            {selectedTool && (
              <>
                <div style={{ padding: 12, background: "rgba(0,180,216,0.05)", borderRadius: 8, border: "1px solid rgba(0,180,216,0.15)", marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: "#00B4D8", fontWeight: 600, marginBottom: 4 }}>{selectedTool.name}</div>
                  <div style={{ fontSize: 11, color: "#a1a1aa" }}>{selectedTool.description}</div>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 11, color: "#71717a", display: "block", marginBottom: 4 }}>Arguments (JSON)</label>
                  <textarea value={toolArgs} onChange={e => setToolArgs(e.target.value)}
                    style={{ width: "100%", minHeight: 120, padding: "8px 12px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#e4e4e7", border: "1px solid rgba(255,255,255,0.1)", fontSize: 12, fontFamily: "var(--font-mono, monospace)", resize: "vertical" }} />
                </div>
                <button onClick={executeTool} disabled={executing}
                  style={{ width: "100%", padding: "10px 16px", borderRadius: 8, background: executing ? "rgba(0,180,216,0.3)" : "#00B4D8", color: "#000", border: "none", cursor: executing ? "wait" : "pointer", fontSize: 13, fontWeight: 600 }}>
                  {executing ? "Executing..." : "▶ Execute Tool"}
                </button>
              </>
            )}
            {!selectedTool && <EmptyState message="Select a tool from the list above or the Tools tab." />}
          </div>

          {/* Right: Result */}
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Result</h2>
            {execResult ? (
              <div style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${execResult.type === "tool_error" ? "rgba(255,51,51,0.2)" : "rgba(0,255,102,0.2)"}`, borderRadius: 10, padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: execResult.type === "tool_error" ? "#FF3333" : "#00FF66" }}>
                    {execResult.type === "tool_error" ? "❌ Error" : "✅ Success"}
                  </span>
                  {execResult.duration_ms && (
                    <span style={{ fontSize: 10, color: "#71717a" }}>{execResult.duration_ms}ms</span>
                  )}
                </div>
                <pre style={{ fontSize: 11, color: "#a1a1aa", lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 400, overflow: "auto", fontFamily: "var(--font-mono, monospace)" }}>
                  {JSON.stringify(execResult.result || execResult.error || execResult, null, 2)}
                </pre>
              </div>
            ) : (
              <EmptyState message="Execute a tool to see results here." />
            )}
          </div>
        </div>
      )}

      {/* Guardrails Tab */}
      {!loading && tab === "guardrails" && (
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>🛡️ Guardrail Rules</h2>
          {guardrails ? (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 20 }}>
                <StatBox label="Total Rules" value={`${guardrails.total_rules || 0}`} color="#00B4D8" />
                <StatBox label="Active" value={`${guardrails.active_rules || 0}`} color="#00FF66" />
                <StatBox label="Total Blocks" value={`${guardrails.total_blocks || 0}`} color="#FF3333" />
                <StatBox label="Risk Levels" value={`${guardrails.risk_levels?.length || 0}`} color="#FFB300" />
              </div>
              {guardrails.rules && guardrails.rules.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))", gap: 12 }}>
                  {guardrails.rules.map((rule: any, i: number) => (
                    <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{rule.name || rule.id}</span>
                        <RiskBadge level={rule.risk_level} />
                      </div>
                      <div style={{ fontSize: 11, color: "#a1a1aa", lineHeight: 1.4 }}>{rule.description || rule.pattern || "—"}</div>
                      {rule.hits !== undefined && (
                        <div style={{ fontSize: 10, color: "#52525b", marginTop: 6 }}>Hits: {rule.hits}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {guardrails.risk_levels && (
                <div style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Risk Levels</h3>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {guardrails.risk_levels.map((level: string) => <RiskBadge key={level} level={level} />)}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <EmptyState message="Guardrail data not available." />
          )}
        </div>
      )}

      {/* Compliance Tab */}
      {!loading && tab === "compliance" && (
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>📋 Compliance Audit Trail</h2>
          {compliance ? (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 20 }}>
                <StatBox label="Total Entries" value={`${compliance.total_entries || 0}`} color="#A855F7" />
                <StatBox label="Errors" value={`${compliance.error_count || 0}`} color="#FF3333" />
                <StatBox label="Avg Duration" value={`${compliance.avg_duration_ms || 0}ms`} color="#00B4D8" />
                <StatBox label="Chain Valid" value={compliance.chain_valid ? "✅" : "❌"} color={compliance.chain_valid ? "#00FF66" : "#FF3333"} />
              </div>
              {compliance.recent && compliance.recent.length > 0 && (
                <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, overflow: "hidden" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                        {["Time", "Tool", "Server", "Duration", "Status"].map(h => (
                          <th key={h} style={{ padding: "10px 12px", textAlign: "left", color: "#71717a", fontWeight: 500 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {compliance.recent.map((entry: any, i: number) => (
                        <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                          <td style={{ padding: "8px 12px", color: "#a1a1aa" }}>{entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : "—"}</td>
                          <td style={{ padding: "8px 12px", color: "#00B4D8" }}>{entry.tool_name}</td>
                          <td style={{ padding: "8px 12px", color: "#a1a1aa" }}>{entry.server_name}</td>
                          <td style={{ padding: "8px 12px", color: "#a1a1aa" }}>{entry.duration_ms}ms</td>
                          <td style={{ padding: "8px 12px" }}>
                            <span style={{ color: entry.is_error ? "#FF3333" : "#00FF66" }}>{entry.is_error ? "❌" : "✅"}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {compliance.report && (
                <pre style={{ marginTop: 16, fontSize: 11, color: "#71717a", lineHeight: 1.5, whiteSpace: "pre-wrap", fontFamily: "var(--font-mono, monospace)", padding: 16, background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.06)" }}>
                  {compliance.report}
                </pre>
              )}
            </div>
          ) : (
            <EmptyState message="Compliance data not available." />
          )}
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: "14px 16px" }}>
      <div style={{ fontSize: 10, color: "#71717a", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    LOW: { bg: "rgba(0,255,102,0.1)", text: "#00FF66" },
    MEDIUM: { bg: "rgba(255,179,0,0.1)", text: "#FFB300" },
    HIGH: { bg: "rgba(255,102,0,0.1)", text: "#FF6600" },
    CRITICAL: { bg: "rgba(255,51,51,0.1)", text: "#FF3333" },
  };
  const c = colors[level] || colors.LOW;
  return <span style={{ fontSize: 9, padding: "2px 8px", borderRadius: 4, background: c.bg, color: c.text, fontWeight: 600 }}>{level}</span>;
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ padding: 40, textAlign: "center", color: "#52525b", fontSize: 13 }}>
      {message}
    </div>
  );
}
