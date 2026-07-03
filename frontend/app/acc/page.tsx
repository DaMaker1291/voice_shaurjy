"use client";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";

interface AccDevice {
  id: string; name: string; type: string; ip: string; port: number;
  protocol: string; status: string; room: string; manufacturer: string;
  model: string; capabilities: string[]; state: Record<string,unknown>;
  icon?: string;
}

interface ParseResult {
  ok: boolean; parsed: string; action: string; params: string; explanation: string;
}

interface ExecResult {
  ok: boolean; result: string;
}

const DEVICE_META: Record<string, { icon: string; label: string; gradient: string }> = {
  light: { icon: "💡", label: "Light", gradient: "from-yellow-400/20 to-orange-500/10" },
  switch: { icon: "🔌", label: "Switch", gradient: "from-blue-400/20 to-cyan-500/10" },
  sensor: { icon: "📡", label: "Sensor", gradient: "from-green-400/20 to-emerald-500/10" },
  thermostat: { icon: "🌡", label: "Thermostat", gradient: "from-red-400/20 to-orange-500/10" },
  lock: { icon: "🔒", label: "Lock", gradient: "from-gray-400/20 to-slate-500/10" },
  cover: { icon: "🪟", label: "Cover", gradient: "from-indigo-400/20 to-purple-500/10" },
  camera: { icon: "📷", label: "Camera", gradient: "from-violet-400/20 to-purple-500/10" },
  doorbell: { icon: "🔔", label: "Doorbell", gradient: "from-rose-400/20 to-pink-500/10" },
  vacuum: { icon: "🤖", label: "Vacuum", gradient: "from-cyan-400/20 to-blue-500/10" },
  climate: { icon: "❄️", label: "Climate", gradient: "from-sky-400/20 to-blue-500/10" },
  media_player: { icon: "📺", label: "Media", gradient: "from-pink-400/20 to-rose-500/10" },
  hub: { icon: "🏠", label: "Hub", gradient: "from-amber-400/20 to-yellow-500/10" },
  alexa: { icon: "🔊", label: "Alexa", gradient: "from-teal-400/20 to-cyan-500/10" },
  speaker: { icon: "🔊", label: "Speaker", gradient: "from-fuchsia-400/20 to-purple-500/10" },
  system: { icon: "🖥", label: "System", gradient: "from-blue-400/20 to-indigo-500/10" },
  computer: { icon: "💻", label: "Computer", gradient: "from-cyan-400/20 to-teal-500/10" },
};

function ParticleBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    c.width = window.innerWidth; c.height = window.innerHeight;
    const p: { x: number; y: number; vx: number; vy: number; r: number }[] = [];
    for (let i = 0; i < 40; i++) {
      p.push({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - 0.5) * 0.5, vy: (Math.random() - 0.5) * 0.5, r: Math.random() * 1.5 + 0.5 });
    }
    let anim: number;
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      p.forEach(pt => {
        pt.x += pt.vx; pt.y += pt.vy;
        if (pt.x < 0 || pt.x > c.width) pt.vx *= -1;
        if (pt.y < 0 || pt.y > c.height) pt.vy *= -1;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(120, 60, 220, 0.3)";
        ctx.fill();
      });
      anim = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(anim);
  }, []);
  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

function CommandTerminal({ device, onClose }: { device: AccDevice; onClose: () => void }) {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<{ role: string; text: string; ok?: boolean }[]>([]);
  const [parsing, setParsing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [history]);
  useEffect(() => { setTimeout(() => inputRef.current?.focus(), 100); }, []);

  const meta = DEVICE_META[device.type] || { icon: device.icon || "📦", label: device.type, gradient: "" };

  const sendCommand = useCallback(async (cmd: string) => {
    if (!cmd.trim()) return;
    setHistory(h => [...h, { role: "user", text: cmd }]);
    setInput("");
    setParsing(true);

    try {
      const parseRes = await fetch("/api/acc/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: device.id,
          device_type: device.type,
          device_name: device.name,
          device_protocol: device.protocol,
          command: cmd,
          capabilities: device.capabilities,
        }),
      });
      const parseData: ParseResult = await parseRes.json();

      if (!parseData.ok) {
        setHistory(h => [...h, { role: "assistant", text: `❌ Not possible\n${parseData.explanation}`, ok: false }]);
        setParsing(false);
        return;
      }

      setHistory(h => [...h, { role: "assistant", text: `✅ OK — ${parseData.explanation}`, ok: true }]);
      setExecuting(true);

      const execRes = await fetch("/api/acc/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: device.id,
          device_ip: device.ip,
          device_type: device.type,
          action: parseData.action,
          params: parseData.params,
        }),
      });
      const execData: ExecResult = await execRes.json();

      if (execData.ok) {
        setHistory(h => [...h, { role: "assistant", text: `✅ Executed — ${execData.result}`, ok: true }]);
      } else {
        setHistory(h => [...h, { role: "assistant", text: `❌ Execution failed — ${execData.result}`, ok: false }]);
      }
    } catch {
      setHistory(h => [...h, { role: "assistant", text: "❌ Backend unreachable", ok: false }]);
    }
    setParsing(false);
    setExecuting(false);
  }, [device]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div className="cmd-terminal w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-purple-700/20">
          <div className="flex items-center gap-3">
            <span className="text-xl">{meta.icon}</span>
            <div>
              <h3 className="text-sm font-semibold text-gray-100">{device.name}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[9px] font-mono text-gray-600 uppercase tracking-wider">{device.protocol}</span>
                <span className="text-gray-700">·</span>
                <span className={`text-[9px] font-mono ${device.status === "online" ? "text-green-500" : "text-gray-600"}`}>{device.status}</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 text-lg leading-none transition-colors duration-200">&times;</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2 min-h-[200px] max-h-[50vh]" style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
          {history.length === 0 && (
            <div className="text-center py-8">
              <p className="text-[10px] font-mono text-gray-700">Type a command for this device</p>
              <p className="text-[9px] font-mono text-gray-800 mt-2">e.g. "turn on", "set brightness to 50%", "lock the door"</p>
            </div>
          )}
          {history.map((h, i) => (
            <div key={i} className={`flex gap-2 ${h.role === "user" ? "justify-end" : "justify-start"} message-enter`}>
              <div className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed whitespace-pre-wrap ${
                h.role === "user"
                  ? "bg-purple-900/30 border border-purple-800/30 text-purple-200"
                  : h.ok === false
                    ? "result-fail bg-red-900/20 border border-red-800/25 text-red-300"
                    : "result-ok bg-gray-900/60 border border-gray-800/40 text-gray-300"
              }`}>
                {h.text}
              </div>
            </div>
          ))}
          {parsing && (
            <div className="flex justify-start">
              <div className="px-3 py-2 rounded-xl bg-gray-900/60 border border-gray-800/40 text-gray-500 text-xs flex items-center gap-1.5">
                <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                <span className="ml-1">parsing</span>
              </div>
            </div>
          )}
          {executing && (
            <div className="flex justify-start">
              <div className="px-3 py-2 rounded-xl bg-gray-900/60 border border-gray-800/40 text-gray-500 text-xs flex items-center gap-1.5">
                <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                <span className="ml-1">executing</span>
              </div>
            </div>
          )}
          {device.capabilities && device.capabilities.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-800/30">
              <p className="text-[8px] font-mono text-gray-700 uppercase tracking-widest mb-2">Available actions</p>
              <div className="flex flex-wrap gap-1.5">
                {device.capabilities.map((cap, i) => (
                  <span key={i} className="cap-tag">
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="p-3 border-t border-gray-800/50">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !parsing && !executing) sendCommand(input); }}
              placeholder={`What should ${device.name} do?`}
              disabled={parsing || executing}
              className="flex-1 px-4 py-2.5 text-xs font-mono bg-gray-900/60 border border-gray-800/40 rounded-xl text-gray-300 placeholder-gray-700 focus:outline-none focus:border-purple-500/40 transition-all disabled:opacity-50"
            />
            <button onClick={() => sendCommand(input)} disabled={parsing || executing || !input.trim()}
              className="px-4 py-2.5 text-[10px] font-mono tracking-widest uppercase rounded-xl border transition-all duration-200 active:scale-95 disabled:opacity-40 bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border-purple-500/30 text-purple-300 hover:from-purple-600/30 hover:to-cyan-600/30">
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DeviceCard({ device, onSelect }: { device: AccDevice; onSelect: (d: AccDevice) => void }) {
  const meta = DEVICE_META[device.type] || { icon: device.icon || "📦", label: device.type, gradient: "from-gray-400/20 to-gray-500/10" };
  const isOnline = device.status === "online";
  const capCount = device.capabilities?.length || 0;

  return (
    <div onClick={() => onSelect(device)}
      className={`device-card ${isOnline ? "online" : "offline"}`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${meta.gradient} opacity-30 group-hover:opacity-50 transition-opacity duration-700`} />
      <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
      <div className="relative p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg ${
              isOnline ? "bg-purple-900/30 border border-purple-700/30" : "bg-gray-800/30 border border-gray-700/20"
            }`}>
              {meta.icon}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-gray-100 truncate tracking-wide">{device.name}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[9px] font-mono text-gray-600 uppercase tracking-wider">{device.protocol}</span>
                {device.room && device.room !== "unknown" && (
                  <><span className="text-gray-700">·</span><span className="text-[9px] font-mono text-gray-600">{device.room}</span></>
                )}
              </div>
            </div>
          </div>
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${
            isOnline ? "bg-green-900/25 border border-green-800/25" : "bg-gray-800/30 border border-gray-700/20"
          }`}>
            <div className={`status-pulse w-1.5 h-1.5 rounded-full ${isOnline ? "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]" : "bg-gray-600"}`} />
            <span className="text-[8px] font-mono tracking-widest uppercase">{isOnline ? "LIVE" : "OFF"}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[9px] font-mono text-gray-700">
          <span>{device.manufacturer || device.type}</span>
          {capCount > 0 && <><span className="text-gray-800">·</span><span className="text-gray-600">{capCount} actions</span></>}
        </div>
        {capCount > 0 && (
          <div className="flex flex-wrap gap-1">
            {device.capabilities.slice(0, 4).map((cap, i) => (
              <span key={i} className="cap-tag">
                {cap}
              </span>
            ))}
            {capCount > 4 && <span className="text-[7px] font-mono text-gray-700 px-1.5 py-0.5">+{capCount - 4}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ACCPage() {
  const [devices, setDevices] = useState<AccDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDevice, setSelectedDevice] = useState<AccDevice | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/acc/devices");
      const data = await res.json();
      setDevices(data.devices || []);
    } catch {
      try {
        const res = await fetch("http://localhost:8000/api/acc/devices");
        const data = await res.json();
        setDevices(data.devices || []);
      } catch {}
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const stats = useMemo(() => {
    const online = devices.filter(d => d.status === "online").length;
    const byType: Record<string, { total: number; online: number }> = {};
    devices.forEach(d => {
      if (!byType[d.type]) byType[d.type] = { total: 0, online: 0 };
      byType[d.type].total++;
      if (d.status === "online") byType[d.type].online++;
    });
    return { total: devices.length, online, offline: devices.length - online, byType };
  }, [devices]);

  const filtered = useMemo(() => {
    let d = devices;
    if (selectedType !== "all") d = d.filter(x => x.type === selectedType);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      d = d.filter(x => x.name.toLowerCase().includes(q) || x.ip.includes(q) || x.type.includes(q) || x.room.includes(q));
    }
    return d;
  }, [devices, selectedType, searchQuery]);

  const typeOrder = ["light", "switch", "sensor", "camera", "doorbell", "vacuum", "lock", "thermostat", "climate", "cover", "media_player", "alexa", "speaker", "hub", "system", "computer"];

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#050510] via-[#0a0a1a] to-[#100620] relative">
      <ParticleBg />
      <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-purple-900/40 border border-purple-700/30 flex items-center justify-center text-lg shadow-[0_0_20px_rgba(120,60,220,0.2)]">
                🎮
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-purple-300 via-cyan-300 to-purple-300 bg-clip-text text-transparent">
                  Agent Command Center
                </h1>
                <p className="text-[9px] font-mono text-gray-700 tracking-[0.25em] uppercase mt-0.5">
                  {stats.online} online · {stats.offline} offline · {stats.total} nodes
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-700 text-[10px]">🔍</span>
              <input type="text" placeholder="Search devices..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                className="w-44 pl-7 pr-3 py-2 text-[10px] font-mono bg-gray-900/60 border border-gray-800/40 rounded-xl text-gray-300 placeholder-gray-700 focus:outline-none focus:border-purple-500/40 transition-all" />
            </div>
            <button onClick={load} disabled={loading}
              className="px-5 py-2.5 text-[10px] font-mono tracking-widest uppercase rounded-xl border transition-all duration-300 active:scale-95
                bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border-purple-500/30 text-purple-300
                hover:from-purple-600/30 hover:to-cyan-600/30 hover:shadow-[0_0_20px_rgba(120,60,220,0.2)]
                disabled:opacity-40 disabled:cursor-not-allowed">
              {loading ? "⟳ Loading..." : "⟳ Refresh"}
            </button>
          </div>
        </div>

        {/* Type filter bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 lg:grid-cols-9 gap-2">
          {typeOrder.map(type => {
            const s = stats.byType[type];
            if (!s || s.total === 0) return null;
            const meta = DEVICE_META[type] || { icon: "📦", label: type, gradient: "" };
            const sel = selectedType === type;
            return (
              <button key={type} onClick={() => setSelectedType(sel ? "all" : type)}
                className={`relative px-3 py-2.5 rounded-xl border transition-all duration-300 text-left overflow-hidden ${
                  sel ? "border-purple-500/50 bg-purple-900/20 shadow-[0_0_15px_rgba(120,60,220,0.15)]" : "border-gray-800/30 bg-gray-900/40 hover:border-gray-700/40"
                }`}>
                {sel && <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-purple-500 to-cyan-500" />}
                <div className="flex items-center gap-2">
                  <span className="text-base">{meta.icon}</span>
                  <span className="text-[9px] font-mono text-gray-600 uppercase">{meta.label}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-green-400 font-mono">{s.online}</span>
                  <span className="text-[9px] text-gray-700">/</span>
                  <span className="text-[9px] text-gray-600 font-mono">{s.total}</span>
                </div>
              </button>
            );
          })}
          <button onClick={() => setSelectedType("all")}
            className={`px-3 py-2.5 rounded-xl border transition-all duration-300 ${
              selectedType === "all" ? "border-purple-500/50 bg-purple-900/10" : "border-gray-800/30 bg-gray-900/40 hover:border-gray-700/40"
            }`}>
            <div className="text-base mb-0.5">📊</div>
            <div className="text-[8px] font-mono text-gray-600 uppercase tracking-wider">All</div>
            <div className="text-[10px] text-gray-400 font-mono mt-0.5">{stats.total}</div>
          </button>
        </div>

        {/* Devices grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1,2,3,4,5,6].map(i => (
              <div key={i} className="rounded-2xl bg-gray-900/30 border border-gray-800/20 h-44 animate-pulse" />
            ))}
          </div>
        ) : filtered.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((d, i) => (
              <DeviceCard key={d.id || i} device={d} onSelect={setSelectedDevice} />
            ))}
          </div>
        ) : (
          <div className="text-center py-24">
            <div className="text-6xl mb-6 opacity-30">🎮</div>
            <p className="text-gray-600 text-sm font-mono">No devices found</p>
            <p className="text-gray-700 text-xs mt-2 font-mono">Discover smart home devices or install the relay agent</p>
          </div>
        )}

        {/* Usage hint */}
        {filtered.length > 0 && !selectedDevice && (
          <div className="text-center pb-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-900/10 border border-purple-800/20">
              <span className="text-[10px] text-purple-400/60">💡</span>
              <span className="text-[10px] font-mono text-gray-600">Click any device to open the command terminal</span>
            </div>
          </div>
        )}
      </div>

      {/* Command terminal modal */}
      {selectedDevice && (
        <CommandTerminal device={selectedDevice} onClose={() => setSelectedDevice(null)} />
      )}
    </div>
  );
}
