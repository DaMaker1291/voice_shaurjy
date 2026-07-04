"use client";

import { useState, useEffect, useCallback } from "react";
import { issueCommand, getAgentCommands, getAgentStatus, scanQuick, getPropagationStatus, getPropagationLogs, getSmartHomeDevices } from "@/lib/api";
import Navbar from "@/components/Navbar";

interface Cmd {
  id: number;
  command: string;
  target: string;
  status: string;
  issued: string;
  completed: string | null;
  result: any;
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
    s === "completed" ? "bg-emerald-400" : s === "dispatched" ? "bg-amber-400" : s === "pending" ? "bg-violet-400" : "bg-zinc-600";

  const tabs = [
    { id: "commands" as const, label: "Commands" },
    { id: "scan" as const, label: "Scan" },
    { id: "propagation" as const, label: "Propagation" },
    { id: "smarthome" as const, label: "Smart Home" },
  ];

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">JARVIS Agent Control</h1>
            {status && (
              <p className="text-xs text-zinc-500 font-mono mt-1">
                {status.completed || 0} completed &middot; {status.dispatched || 0} in flight &middot; {status.pending || 0} pending
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {quickCmds.map(c => (
              <button
                key={c}
                onClick={() => doIssue(c)}
                disabled={issuing === c}
                className="text-xs font-mono uppercase px-3 py-1.5 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors duration-150 disabled:opacity-40"
              >
                {issuing === c ? "..." : c}
              </button>
            ))}
          </div>
        </div>

        <div className="flex border-b border-white/[0.06] overflow-x-auto">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-150 whitespace-nowrap ${
                tab === t.id
                  ? "text-zinc-100 border-violet-500"
                  : "text-zinc-500 hover:text-zinc-300 border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "commands" && (
          <div>
            {commands.length === 0 ? (
              <div className="text-center py-20 text-zinc-600">
                <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-sm">No commands yet</p>
                <p className="text-xs text-zinc-600 mt-2">Click a quick command button above to issue one</p>
              </div>
            ) : (
              <div className="space-y-2">
                {commands.slice().reverse().map((cmd) => (
                  <div key={cmd.id} className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-2 h-2 rounded-full ${statusColor(cmd.status)}`} />
                        <span className="text-sm font-mono text-zinc-300">{cmd.command}</span>
                        {cmd.target && cmd.target !== "all" && (
                          <span className="text-xs font-mono text-zinc-500 bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.06]">
                            @{cmd.target}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono text-zinc-600 tracking-wider uppercase">{cmd.status}</span>
                        {cmd.issued && (
                          <span className="text-[10px] font-mono text-zinc-600">{new Date(cmd.issued).toLocaleTimeString()}</span>
                        )}
                      </div>
                    </div>
                    {cmd.result && (
                      <div className="mt-2 border-t border-white/[0.04] pt-2">
                        <pre className="text-xs font-mono text-zinc-500 leading-relaxed whitespace-pre-wrap max-h-24 overflow-y-auto">
                          {typeof cmd.result === "string" ? cmd.result : JSON.stringify(cmd.result, null, 2)}
                        </pre>
                      </div>
                    )}
                    {cmd.command === "scan" && cmd.result?.wifi && (
                      <div className="mt-2 flex gap-3 text-xs font-mono text-zinc-500">
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

        {tab === "scan" && (
          <div>
            <button
              onClick={doScan}
              disabled={loading.scan}
              className="mb-4 text-xs font-mono uppercase px-4 py-2 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors duration-150 disabled:opacity-40"
            >
              {loading.scan ? "Scanning..." : "Quick Scan"}
            </button>
            {scanData ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {scanData.wifi && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">WiFi</h3>
                    <p className="text-sm font-mono text-zinc-300">{scanData.wifi.ssid || scanData.wifi.current_ssid || "N/A"}</p>
                    <p className="text-xs font-mono text-zinc-500 mt-1">{scanData.wifi.interface || ""}</p>
                  </div>
                )}
                {scanData.lan && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">
                      LAN Devices ({scanData.lan.count || (scanData.lan.devices || []).length})
                    </h3>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {(scanData.lan.devices || []).slice(0, 20).map((d: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs font-mono">
                          <span className="w-2 h-2 rounded-full bg-emerald-400/40" />
                          <span className="text-zinc-400 w-16 truncate">{d.ip}</span>
                          <span className="text-zinc-500 flex-1 truncate">{d.hostname || d.mac || "unknown"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {scanData.processes && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">Top Processes</h3>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {(scanData.processes || []).slice(0, 10).map((p: any, i: number) => (
                        <div key={i} className="flex items-center justify-between text-xs font-mono">
                          <span className="text-zinc-400 truncate flex-1">{p.name}</span>
                          <span className="text-zinc-500 w-12 text-right">{p.cpu?.toFixed(1) || "?"}%</span>
                          <span className="text-zinc-600 w-12 text-right">{p.mem_mb?.toFixed(0) || "?"}MB</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {scanData.users && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">Users</h3>
                    <div className="space-y-1">
                      {(scanData.users || []).map((u: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-xs font-mono">
                          <span className="text-zinc-400">{u.name || u.username}</span>
                          <span className="text-zinc-600">{u.uid}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-20 text-zinc-600">
                <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <p className="text-sm">Run a scan to see results</p>
              </div>
            )}
          </div>
        )}

        {tab === "propagation" && (
          <div>
            <button
              onClick={doProp}
              disabled={loading.prop}
              className="mb-4 text-xs font-mono uppercase px-4 py-2 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors duration-150 disabled:opacity-40"
            >
              {loading.prop ? "Loading..." : "Refresh"}
            </button>
            {propData ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">Status</h3>
                  <pre className="text-xs font-mono text-zinc-400 leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                    {JSON.stringify(propData, null, 2)}
                  </pre>
                </div>
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">Logs ({propLogs.length})</h3>
                  <div className="space-y-1 max-h-60 overflow-y-auto">
                    {(propLogs || []).slice().reverse().map((l: any, i: number) => (
                      <div key={i} className="text-[10px] font-mono text-zinc-500 leading-tight flex gap-2">
                        <span className="text-zinc-600 shrink-0">
                          {l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ""}
                        </span>
                        <span className={l.level === "error" ? "text-red-400/60" : "text-zinc-500"}>
                          {l.message || JSON.stringify(l)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-20 text-zinc-600">
                <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.858 15.355-5.858 21.213 0" />
                </svg>
                <p className="text-sm">No propagation data yet</p>
              </div>
            )}
          </div>
        )}

        {tab === "smarthome" && (
          <div>
            <button
              onClick={doSH}
              disabled={loading.sh}
              className="mb-4 text-xs font-mono uppercase px-4 py-2 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors duration-150 disabled:opacity-40"
            >
              {loading.sh ? "Loading..." : "Refresh"}
            </button>
            {shDevices.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {shDevices.map((d: any, i: number) => (
                  <div
                    key={i}
                    className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 animate-fade-in"
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-mono text-zinc-300 truncate">{d.name || d.ip || "Device"}</h3>
                      <span className={`w-2 h-2 rounded-full ${d.status === "on" || d.status === "online" ? "bg-emerald-400" : "bg-zinc-600"}`} />
                    </div>
                    <p className="text-[10px] font-mono text-zinc-500 truncate">{d.ip}</p>
                    <p className="text-[10px] font-mono text-zinc-600">{d.type || d.protocol || "unknown"}</p>
                    {d.ports && (
                      <p className="text-[10px] font-mono text-zinc-600 mt-1">ports: {(d.ports || []).join(", ")}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-20 text-zinc-600">
                <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
                <p className="text-sm">No smart home devices discovered</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
