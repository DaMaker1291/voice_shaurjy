"use client";

import { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/Navbar";
import { BASE } from "@/lib/api";

interface SmartDevice {
  id: string;
  name: string;
  type: string;
  ip: string;
  protocol: string;
  status: string;
  manufacturer?: string;
  model?: string;
}

interface CommandLog {
  device_id: string;
  device_ip: string;
  protocol: string;
  command: any;
  status: string;
  latency_ms: number;
  timestamp: number;
  error?: string;
}

const DEVICE_ICONS: Record<string, string> = {
  light: "💡",
  thermostat: "🌡️",
  tv: "📺",
  speaker: "🔊",
  camera: "📷",
  lock: "🔒",
  plug: "🔌",
  sensor: "📡",
  hub: "🏠",
  router: "📶",
  printer: "🖨️",
  hubitat: "🏠",
};

const TYPE_COLORS: Record<string, string> = {
  light: "text-amber-400",
  thermostat: "text-emerald-400",
  tv: "text-blue-400",
  speaker: "text-purple-400",
  camera: "text-rose-400",
  lock: "text-emerald-400",
  plug: "text-emerald-400",
  sensor: "text-cyan-400",
};

export default function DevicesPage() {
  const [devices, setDevices] = useState<SmartDevice[]>([]);
  const [logs, setLogs] = useState<CommandLog[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<SmartDevice | null>(null);
  const [loading, setLoading] = useState(false);
  const [nlInput, setNlInput] = useState("");
  const [nlResult, setNlResult] = useState<any>(null);
  const [controlling, setControlling] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"devices" | "nl" | "log">("devices");

  const refreshDevices = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/api/smart-home/devices`);
      const data = await r.json();
      setDevices(data.devices || []);
    } catch {}
  }, []);

  const refreshLogs = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/api/devices/command-log?limit=30`);
      const data = await r.json();
      setLogs(data.commands || []);
    } catch {}
  }, []);

  useEffect(() => {
    refreshDevices();
    refreshLogs();
    const i = setInterval(() => {
      refreshDevices();
      refreshLogs();
    }, 8000);
    return () => clearInterval(i);
  }, [refreshDevices, refreshLogs]);

  const controlDevice = async (device: SmartDevice, action: string) => {
    setControlling(device.id);
    try {
      const r = await fetch(`${BASE}/api/devices/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: device.id,
          command: { state: action },
        }),
      });
      const data = await r.json();
      if (data.status === "success") {
        refreshDevices();
      }
      setTimeout(refreshLogs, 500);
    } catch {}
    setControlling(null);
  };

  const parseNL = async () => {
    if (!nlInput.trim()) return;
    try {
      const r = await fetch(`${BASE}/api/nl/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: nlInput }),
      });
      setNlResult(await r.json());
    } catch {}
  };

  const executeNL = async () => {
    if (!nlInput.trim()) return;
    try {
      const r = await fetch(`${BASE}/api/nl/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: nlInput }),
      });
      setNlResult(await r.json());
      setTimeout(() => {
        refreshDevices();
        refreshLogs();
      }, 500);
    } catch {}
  };

  const timeAgo = (ts: number) => {
    if (!ts) return "";
    const diff = (Date.now() / 1000) - ts;
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-4 md:p-6 max-w-7xl mx-auto w-full">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Device Control</h1>
            <p className="text-xs text-zinc-500 font-mono mt-0.5">
              {devices.length} devices discovered — {logs.length} commands logged
            </p>
          </div>
          <button
            onClick={() => { refreshDevices(); refreshLogs(); }}
            className="text-xs font-mono uppercase px-3 py-1.5 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors"
          >
            Refresh
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-white/[0.06] mb-6 overflow-x-auto">
          {[
            { id: "devices" as const, label: "Devices" },
            { id: "nl" as const, label: "Natural Language" },
            { id: "log" as const, label: "Command Log" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-150 whitespace-nowrap ${
                activeTab === t.id
                  ? "text-zinc-100 border-violet-500"
                  : "text-zinc-500 hover:text-zinc-300 border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Devices Tab */}
        {activeTab === "devices" && (
          <div>
            {devices.length === 0 ? (
              <div className="text-center py-20 text-zinc-600 border border-dashed border-white/[0.06] rounded-xl">
                <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
                <p className="text-sm">No devices discovered</p>
                <p className="text-xs text-zinc-600 mt-2">Run a network scan to find devices on your WiFi</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {devices.map((device) => (
                  <div
                    key={device.id}
                    onClick={() => setSelectedDevice(device)}
                    className={`bg-[#111113] border rounded-xl p-4 cursor-pointer transition-all duration-150 ${
                      selectedDevice?.id === device.id
                        ? "border-violet-500/30 bg-violet-500/[0.04]"
                        : "border-white/[0.06] hover:border-white/[0.12]"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        <span className="text-lg">{DEVICE_ICONS[device.type] || "📡"}</span>
                        <div>
                          <h3 className="text-sm font-medium text-zinc-200">{device.name}</h3>
                          <p className="text-[10px] font-mono text-zinc-500 mt-0.5">{device.type}</p>
                        </div>
                      </div>
                      <span className={`w-2 h-2 rounded-full ${
                        device.status === "online" || device.status === "on" ? "bg-emerald-400" : "bg-zinc-600"
                      }`} />
                    </div>

                    <div className="text-[10px] font-mono text-zinc-500 space-y-0.5 mb-3">
                      <p>IP: {device.ip || "—"}</p>
                      <p>Protocol: {device.protocol || "—"}</p>
                      {device.manufacturer && <p>Mfg: {device.manufacturer}</p>}
                    </div>

                    <div className="flex gap-1.5">
                      {device.type === "light" || device.type === "plug" ? (
                        <>
                          <button
                            onClick={(e) => { e.stopPropagation(); controlDevice(device, "on"); }}
                            disabled={controlling === device.id}
                            className="flex-1 text-[10px] font-mono uppercase px-2 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40"
                          >
                            On
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); controlDevice(device, "off"); }}
                            disabled={controlling === device.id}
                            className="flex-1 text-[10px] font-mono uppercase px-2 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] transition-colors disabled:opacity-40"
                          >
                            Off
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={(e) => { e.stopPropagation(); controlDevice(device, "on"); }}
                          disabled={controlling === device.id}
                          className="flex-1 text-[10px] font-mono uppercase px-2 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors disabled:opacity-40"
                        >
                          {controlling === device.id ? "..." : "Control"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* NL Tab */}
        {activeTab === "nl" && (
          <div className="space-y-4">
            <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
              <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Device Control via Natural Language</h3>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder='e.g. "turn on the living room lights" or "set kitchen temperature to 72"'
                  value={nlInput}
                  onChange={(e) => setNlInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && parseNL()}
                  className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-xs font-mono text-zinc-300 outline-none focus:border-violet-500/30 placeholder:text-zinc-600 transition-colors"
                />
                <button
                  onClick={parseNL}
                  className="text-xs font-mono uppercase px-4 py-2 rounded-lg border border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.06] transition-colors"
                >
                  Parse
                </button>
                <button
                  onClick={executeNL}
                  className="text-xs font-mono uppercase px-4 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors"
                >
                  Execute
                </button>
              </div>
            </div>

            {nlResult && (
              <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Result</h3>
                {nlResult.parsed && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase">Intent</span>
                      <p className="text-sm font-mono text-zinc-200 mt-1">{nlResult.parsed.intent}</p>
                    </div>
                    <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase">Device</span>
                      <p className="text-sm font-mono text-zinc-200 mt-1">{nlResult.parsed.device_type || nlResult.parsed.device_name || "—"}</p>
                    </div>
                    <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase">Action</span>
                      <p className="text-sm font-mono text-zinc-200 mt-1">{nlResult.parsed.action || "—"}</p>
                    </div>
                    <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase">Confidence</span>
                      <p className="text-sm font-mono text-zinc-200 mt-1">{(nlResult.parsed.confidence * 100).toFixed(0)}%</p>
                    </div>
                  </div>
                )}
                <pre className="text-[10px] font-mono text-zinc-500 whitespace-pre-wrap max-h-60 overflow-y-auto bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                  {JSON.stringify(nlResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Log Tab */}
        {activeTab === "log" && (
          <div>
            {logs.length === 0 ? (
              <div className="text-center py-20 text-zinc-600 border border-dashed border-white/[0.06] rounded-xl">
                <p className="text-sm">No commands executed yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {logs.slice().reverse().map((log, i) => (
                  <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-2 h-2 rounded-full ${
                          log.status === "success" ? "bg-emerald-400" : log.status === "failed" ? "bg-red-400" : "bg-zinc-600"
                        }`} />
                        <span className="text-xs font-mono text-zinc-300">{log.device_id}</span>
                        <span className="text-[10px] font-mono text-zinc-600 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
                          {log.protocol}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono text-zinc-600">{log.latency_ms}ms</span>
                        <span className="text-[10px] font-mono text-zinc-600">{timeAgo(log.timestamp)}</span>
                      </div>
                    </div>
                    <pre className="text-[10px] font-mono text-zinc-500 mt-2 whitespace-pre-wrap max-h-16 overflow-y-auto">
                      {JSON.stringify(log.command, null, 2)}
                    </pre>
                    {log.error && (
                      <p className="text-[10px] font-mono text-red-400/60 mt-1">{log.error}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
