"use client";

import { useState, useEffect, useCallback } from "react";
import { issueCommand, getAgentCommands, getAgentStatus, scanQuick, getPropagationStatus, getPropagationLogs, getSmartHomeDevices } from "@/lib/api";

interface Cmd {
  id: number; command: string; target: string; status: string; issued: string; completed: string | null; result: any;
}

export default function AgentPage() {
  const [tab, setTab] = useState<"commands" | "scan" | "propagation" | "smarthome">("commands");
  const [commands, setCommands] = useState<Cmd[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [scanData, setScanData] = useState<any>(null);
  const [propData, setPropData] = useState<any>(null);
  const [propLogs, setPropLogs] = useState<any[]>([]);
  const [shDevices, setShDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [issuing, setIssuing] = useState<string | null>(null);

  const BASE = typeof window !== "undefined" &&
    (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

  const refresh = useCallback(async () => {
    try {
      const cmds = await getAgentCommands();
      setCommands(cmds.commands || []);
      setStatus(await getAgentStatus());
    } catch {}
  }, []);

  useEffect(() => { refresh(); const i = setInterval(refresh, 4000); return () => clearInterval(i); }, [refresh]);

  const doScan = useCallback(async () => {
    setLoading(s => ({ ...s, scan: true }));
    try { setScanData(await scanQuick()); } catch {}
    setLoading(s => ({ ...s, scan: false }));
  }, []);

  const doProp = useCallback(async () => {
    setLoading(s => ({ ...s, prop: true }));
    try { setPropData(await getPropagationStatus()); } catch {}
    try { const logs = await getPropagationLogs(); setPropLogs(logs.logs || logs || []); } catch {}
    setLoading(s => ({ ...s, prop: false }));
  }, []);

  const doSH = useCallback(async () => {
    setLoading(s => ({ ...s, sh: true }));
    try { const d = await getSmartHomeDevices(); setShDevices(d.devices || []); } catch {}
    setLoading(s => ({ ...s, sh: false }));
  }, []);

  const doIssue = useCallback(async (command: string) => {
    setIssuing(command);
    try { await issueCommand(command); setTimeout(refresh, 1000); } catch {}
    setIssuing(null);
  }, [refresh]);

  const quickCmds = ["scan", "propagate", "smarthome", "status"];

  const statusColor = (s: string) =>
    s === "completed" ? "#22c55e" : s === "dispatched" ? "#f59e0b" : s === "pending" ? "#6366f1" : "#6b7280";

  return (
    <div className="min-h-screen pt-14 px-4 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-bold tracking-wider text-purple-400/80">JARVIS Agent Control</h1>
          {status && (
            <p className="text-[10px] font-mono text-gray-600 mt-1">
              {status.completed || 0} completed &middot; {status.dispatched || 0} in flight &middot; {status.pending || 0} pending
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {quickCmds.map(c => (
            <button
              key={c}
              onClick={() => doIssue(c)}
              disabled={issuing === c}
              className="text-[9px] font-mono tracking-wider uppercase px-3 py-1.5 rounded-lg border border-purple-500/20 text-purple-400/60 hover:text-purple-400 hover:border-purple-500/40 transition-all disabled:opacity-40"
            >
              {issuing === c ? "..." : c}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 mb-6 border-b border-gray-800/30">
        {[
          { id: "commands" as const, label: "Commands", icon: "⌨" },
          { id: "scan" as const, label: "Scan", icon: "🔍" },
          { id: "propagation" as const, label: "Propagation", icon: "📡" },
          { id: "smarthome" as const, label: "Smart Home", icon: "🏠" },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-[10px] font-mono tracking-wider transition-all ${
              tab === t.id
                ? "text-purple-400 border-b-2 border-purple-500"
                : "text-gray-600 hover:text-gray-400 border-b-2 border-transparent"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Commands Tab */}
      {tab === "commands" && (
        <div>
          {commands.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-3xl mb-3 opacity-30">⌨</p>
              <p className="text-xs font-mono text-gray-700">No commands yet</p>
              <p className="text-[9px] font-mono text-gray-800 mt-2">Click a quick command button above to issue one</p>
            </div>
          ) : (
            <div className="space-y-2">
              {commands.slice().reverse().map((cmd) => (
                <div key={cmd.id} className="glass-card p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: statusColor(cmd.status) }} />
                      <span className="text-xs font-mono text-gray-300">{cmd.command}</span>
                      {cmd.target && cmd.target !== "all" && (
                        <span className="text-[9px] font-mono text-gray-600 bg-gray-800/40 px-2 py-0.5 rounded">@{cmd.target}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[8px] font-mono text-gray-700 tracking-wider uppercase">{cmd.status}</span>
                      {cmd.issued && (
                        <span className="text-[8px] font-mono text-gray-700">{new Date(cmd.issued).toLocaleTimeString()}</span>
                      )}
                    </div>
                  </div>
                  {cmd.result && (
                    <div className="mt-2 border-t border-gray-800/20 pt-2">
                      <pre className="text-[9px] font-mono text-gray-500 leading-relaxed whitespace-pre-wrap max-h-24 overflow-y-auto">
                        {typeof cmd.result === "string" ? cmd.result : JSON.stringify(cmd.result, null, 2)}
                      </pre>
                    </div>
                  )}
                  {cmd.command === "scan" && cmd.result?.wifi && (
                    <div className="mt-2 flex gap-3 text-[9px] font-mono text-gray-600">
                      <span>WiFi: {cmd.result.wifi}</span>
                      <span>LAN: {cmd.result.lan_devices} devices</span>
                      <span>Processes: {cmd.result.processes}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Scan Tab */}
      {tab === "scan" && (
        <div>
          <div className="flex gap-2 mb-4">
            <button
              onClick={doScan}
              disabled={loading.scan}
              className="text-[9px] font-mono tracking-wider uppercase px-4 py-2 rounded-lg border border-purple-500/20 text-purple-400/60 hover:text-purple-400 hover:border-purple-500/40 transition-all disabled:opacity-40"
            >
              {loading.scan ? "Scanning..." : "Quick Scan"}
            </button>
          </div>
          {scanData ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {scanData.wifi && (
                <div className="glass-card p-4">
                  <h3 className="text-[9px] font-mono text-purple-400/60 tracking-[0.2em] uppercase mb-2">WiFi</h3>
                  <p className="text-sm font-mono text-gray-300">{scanData.wifi.ssid || scanData.wifi.current_ssid || "N/A"}</p>
                  <p className="text-[9px] font-mono text-gray-600 mt-1">{scanData.wifi.interface || ""}</p>
                </div>
              )}
              {scanData.lan && (
                <div className="glass-card p-4">
                  <h3 className="text-[9px] font-mono text-purple-400/60 tracking-[0.2em] uppercase mb-2">LAN Devices ({scanData.lan.count || (scanData.lan.devices || []).length})</h3>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {(scanData.lan.devices || []).slice(0, 20).map((d: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-[9px] font-mono">
                        <span className="w-2 h-2 rounded-full bg-green-500/40" />
                        <span className="text-gray-400 w-16 truncate">{d.ip}</span>
                        <span className="text-gray-600 flex-1 truncate">{d.hostname || d.mac || "unknown"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {scanData.processes && (
                <div className="glass-card p-4">
                  <h3 className="text-[9px] font-mono text-purple-400/60 tracking-[0.2em] uppercase mb-2">Top Processes</h3>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {(scanData.processes || []).slice(0, 10).map((p: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-[9px] font-mono">
                        <span className="text-gray-400 truncate flex-1">{p.name}</span>
                        <span className="text-gray-600 w-12 text-right">{p.cpu?.toFixed(1) || "?"}%</span>
                        <span className="text-gray-700 w-12 text-right">{p.mem_mb?.toFixed(0) || "?"}MB</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {scanData.users && (
                <div className="glass-card p-4">
                  <h3 className="text-[9px] font-mono text-purple-400/60 tracking-[0.2em] uppercase mb-2">Users</h3>
                  <div className="space-y-1">
                    {(scanData.users || []).map((u: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-[9px] font-mono">
                        <span className="text-gray-400">{u.name || u.username}</span>
                        <span className="text-gray-700">{u.uid}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-16">
              <p className="text-3xl mb-3 opacity-30">🔍</p>
              <p className="text-xs font-mono text-gray-700">Run a scan to see results</p>
              <p className="text-[9px] font-mono text-gray-800 mt-2">Click "Quick Scan" above or issue the scan command</p>
            </div>
          )}
        </div>
      )}

      {/* Propagation Tab */}
      {tab === "propagation" && (
        <div>
          <div className="flex gap-2 mb-4">
            <button
              onClick={doProp}
              disabled={loading.prop}
              className="text-[9px] font-mono tracking-wider uppercase px-4 py-2 rounded-lg border border-purple-500/20 text-purple-400/60 hover:text-purple-400 hover:border-purple-500/40 transition-all disabled:opacity-40"
            >
              {loading.prop ? "Loading..." : "Refresh"}
            </button>
          </div>
          {propData ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="glass-card p-4">
                <h3 className="text-[9px] font-mono text-purple-400/60 tracking-[0.2em] uppercase mb-2">Status</h3>
                <pre className="text-[10px] font-mono text-gray-400 leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                  {JSON.stringify(propData, null, 2)}
                </pre>
              </div>
              <div className="glass-card p-4">
                <h3 className="text-[9px] font-mono text-purple-400/60 tracking-[0.2em] uppercase mb-2">Logs ({propLogs.length})</h3>
                <div className="space-y-1 max-h-60 overflow-y-auto">
                  {(propLogs || []).slice().reverse().map((l: any, i: number) => (
                    <div key={i} className="text-[8px] font-mono text-gray-600 leading-tight flex gap-2">
                      <span className="text-gray-700 shrink-0">{l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ""}</span>
                      <span className={l.level === "error" ? "text-red-400/60" : "text-gray-600"}>{l.message || JSON.stringify(l)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-16">
              <p className="text-3xl mb-3 opacity-30">📡</p>
              <p className="text-xs font-mono text-gray-700">No propagation data yet</p>
              <p className="text-[9px] font-mono text-gray-800 mt-2">Issue a "propagate" command to start</p>
            </div>
          )}
        </div>
      )}

      {/* Smart Home Tab */}
      {tab === "smarthome" && (
        <div>
          <div className="flex gap-2 mb-4">
            <button
              onClick={doSH}
              disabled={loading.sh}
              className="text-[9px] font-mono tracking-wider uppercase px-4 py-2 rounded-lg border border-purple-500/20 text-purple-400/60 hover:text-purple-400 hover:border-purple-500/40 transition-all disabled:opacity-40"
            >
              {loading.sh ? "Loading..." : "Refresh"}
            </button>
          </div>
          {shDevices.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {shDevices.map((d: any, i: number) => (
                <div key={i} className="glass-card p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-[10px] font-mono text-gray-300 truncate">{d.name || d.ip || "Device"}</h3>
                    <span className={`w-2 h-2 rounded-full ${d.status === "on" || d.status === "online" ? "bg-green-500" : "bg-gray-600"}`} />
                  </div>
                  <p className="text-[8px] font-mono text-gray-600 truncate">{d.ip}</p>
                  <p className="text-[8px] font-mono text-gray-700">{d.type || d.protocol || "unknown"}</p>
                  {d.ports && (
                    <p className="text-[8px] font-mono text-gray-700 mt-1">ports: {(d.ports || []).join(", ")}</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-16">
              <p className="text-3xl mb-3 opacity-30">🏠</p>
              <p className="text-xs font-mono text-gray-700">No smart home devices discovered</p>
              <p className="text-[9px] font-mono text-gray-800 mt-2">Issue a "smarthome" command to scan your network</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
