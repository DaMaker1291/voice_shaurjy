"use client";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";

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
};

interface SmartDevice {
  id: string; name: string; type: string; ip: string; port: number;
  protocol: string; status: string; room: string; manufacturer: string;
  model: string; capabilities: string[]; state: Record<string,unknown>;
  brightness?: number; temperature?: number;
}

const CONTROLS: Record<string, { label: string; action: string; type: string; params?: string }[]> = {
  light: [
    { label: "ON", action: "on", type: "power" },
    { label: "OFF", action: "off", type: "power" },
    { label: "↺", action: "toggle", type: "icon" },
    { label: "Brightness", action: "brightness", type: "range" },
    { label: "Color", action: "color", type: "text" },
  ],
  switch: [
    { label: "ON", action: "on", type: "power" },
    { label: "OFF", action: "off", type: "power" },
    { label: "↺", action: "toggle", type: "icon" },
  ],
  sensor: [{ label: "📊 Read", action: "read", type: "read" }],
  thermostat: [
    { label: "🔥 Heat", action: "mode", type: "mode", params: "heat" },
    { label: "❄️ Cool", action: "mode", type: "mode", params: "cool" },
    { label: "OFF", action: "off", type: "power" },
    { label: "Temp", action: "temperature_set", type: "range" },
  ],
  lock: [
    { label: "🔒 LOCK", action: "lock", type: "lock" },
    { label: "🔓 UNLOCK", action: "unlock", type: "unlock" },
  ],
  cover: [
    { label: "▲ OPEN", action: "open", type: "cover" },
    { label: "▼ CLOSE", action: "close", type: "cover" },
    { label: "■ STOP", action: "stop", type: "icon" },
  ],
  camera: [
    { label: "📸 SNAPSHOT", action: "snapshot", type: "action" },
  ],
  doorbell: [
    { label: "📸 SNAPSHOT", action: "snapshot", type: "action" },
    { label: "🎙 SPEAK", action: "speak", type: "text" },
  ],
  vacuum: [
    { label: "▶ START", action: "start", type: "action" },
    { label: "⏹ STOP", action: "stop", type: "stop" },
    { label: "🏠 DOCK", action: "dock", type: "dock" },
  ],
  media_player: [
    { label: "ON", action: "on", type: "power" },
    { label: "OFF", action: "off", type: "power" },
    { label: "Vol", action: "volume", type: "range" },
  ],
  alexa: [
    { label: "Vol", action: "volume", type: "range" },
    { label: "Speak", action: "speak", type: "text" },
  ],
  climate: [
    { label: "ON", action: "on", type: "power" },
    { label: "OFF", action: "off", type: "power" },
    { label: "Temp", action: "temperature_set", type: "range" },
  ],
  hub: [{ label: "📊 Status", action: "status", type: "read" }],
};

function ParticleBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    c.width = window.innerWidth; c.height = window.innerHeight;
    const particles: { x: number; y: number; vx: number; vy: number; r: number }[] = [];
    for (let i = 0; i < 40; i++) {
      particles.push({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - 0.5) * 0.5, vy: (Math.random() - 0.5) * 0.5, r: Math.random() * 1.5 + 0.5 });
    }
    let anim: number;
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > c.width) p.vx *= -1;
        if (p.y < 0 || p.y > c.height) p.vy *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
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

function DeviceCard({ device, onControl }: { device: SmartDevice; onControl: (d: SmartDevice, a: string, p?: string) => void }) {
  const meta = DEVICE_META[device.type] || { icon: "📦", label: device.type, gradient: "from-gray-400/20 to-gray-500/10" };
  const controls = CONTROLS[device.type] || CONTROLS.switch;
  const isOnline = device.status === "online";
  const [rangeVal, setRangeVal] = useState("50");

  return (
    <div className={`relative group rounded-2xl border transition-all duration-500 overflow-hidden ${
      isOnline
        ? "bg-gray-900/60 border-gray-700/30 hover:border-purple-500/40 hover:shadow-[0_0_30px_rgba(120,60,220,0.15)]"
        : "bg-gray-900/30 border-gray-800/20 opacity-50"
    }`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${meta.gradient} opacity-30 group-hover:opacity-50 transition-opacity duration-700`} />
      <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
      <div className="relative p-5 space-y-4">
        {/* Header */}
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
          <div className="flex items-center gap-2">
            {device.brightness !== undefined && device.type === "light" && (
              <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-yellow-900/20 border border-yellow-800/20">
                <span className="text-[8px] text-yellow-500 font-mono">{device.brightness}%</span>
                <div className="w-8 h-1 rounded-full bg-gray-800 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-yellow-400 to-orange-400" style={{ width: `${device.brightness}%` }} />
                </div>
              </div>
            )}
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${
              isOnline ? "bg-green-900/25 border border-green-800/25" : "bg-gray-800/30 border border-gray-700/20"
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isOnline ? "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]" : "bg-gray-600"}`} />
              <span className="text-[8px] font-mono tracking-widest uppercase">{isOnline ? "LIVE" : "OFF"}</span>
            </div>
          </div>
        </div>

        {/* State indicators */}
        {device.temperature !== undefined && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-900/10 border border-red-800/15">
            <span className="text-sm">🌡</span>
            <span className="text-xs text-red-300 font-mono">{device.temperature}°C</span>
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-wrap gap-1.5">
          {controls.map((ctl, ci) => {
            if (ctl.type === "power") {
              const isGreen = ctl.action === "on";
              return (
                <button key={ci} onClick={() => onControl(device, ctl.action)}
                  className={`px-4 py-2 text-[10px] font-mono tracking-widest rounded-xl border transition-all duration-200 active:scale-95 ${
                    isGreen
                      ? "bg-green-600/15 border-green-600/25 text-green-400 hover:bg-green-600/25 hover:shadow-[0_0_12px_rgba(74,222,128,0.2)]"
                      : "bg-red-600/15 border-red-600/25 text-red-400 hover:bg-red-600/25 hover:shadow-[0_0_12px_rgba(248,113,113,0.2)]"
                  }`}>
                  {ctl.label}
                </button>
              );
            }
            if (ctl.type === "action" || ctl.type === "read") {
              const colors: Record<string, string> = {
                start: "bg-cyan-600/15 border-cyan-600/25 text-cyan-400 hover:bg-cyan-600/25",
                stop: "bg-red-600/15 border-red-600/25 text-red-400 hover:bg-red-600/25",
                dock: "bg-purple-600/15 border-purple-600/25 text-purple-400 hover:bg-purple-600/25",
                snapshot: "bg-violet-600/15 border-violet-600/25 text-violet-400 hover:bg-violet-600/25",
                lock: "bg-orange-600/15 border-orange-600/25 text-orange-400 hover:bg-orange-600/25",
                unlock: "bg-emerald-600/15 border-emerald-600/25 text-emerald-400 hover:bg-emerald-600/25",
                cover: "bg-indigo-600/15 border-indigo-600/25 text-indigo-400 hover:bg-indigo-600/25",
                mode: "bg-amber-600/15 border-amber-600/25 text-amber-400 hover:bg-amber-600/25",
              };
              return (
                <button key={ci} onClick={() => onControl(device, ctl.action, ctl.params)}
                  className={`px-4 py-2 text-[10px] font-mono tracking-widest rounded-xl border transition-all duration-200 active:scale-95 ${
                    colors[ctl.action] || "bg-gray-700/30 border-gray-600/30 text-gray-300 hover:bg-gray-600/30"
                  }`}>
                  {ctl.label}
                </button>
              );
            }
            if (ctl.type === "icon") {
              return (
                <button key={ci} onClick={() => onControl(device, ctl.action)}
                  className="w-9 h-9 flex items-center justify-center text-xs rounded-xl bg-gray-800/40 border border-gray-700/30 text-gray-400 hover:bg-gray-700/40 hover:text-gray-200 transition-all active:scale-95">
                  {ctl.label}
                </button>
              );
            }
            if (ctl.type === "range") {
              return (
                <div key={ci} className="flex items-center gap-2 w-full mt-1 px-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-[9px] text-gray-600 font-mono uppercase tracking-wider">{ctl.label}</span>
                  </div>
                  <input type="range" min={ctl.action === "temperature_set" ? 10 : 0}
                    max={ctl.action === "temperature_set" ? 35 : 100} value={rangeVal}
                    onChange={e => setRangeVal(e.target.value)}
                    onMouseUp={() => onControl(device, ctl.action, rangeVal)}
                    onTouchEnd={() => onControl(device, ctl.action, rangeVal)}
                    className="flex-1 h-1 appearance-none bg-gray-800 rounded-full outline-none
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                      [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500
                      [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(120,60,220,0.5)]
                      [&::-webkit-slider-thumb]:cursor-pointer" />
                  <span className="text-[10px] text-gray-500 font-mono w-7 text-right">{rangeVal}</span>
                </div>
              );
            }
            if (ctl.type === "text") {
              return (
                <div key={ci} className="flex items-center gap-1.5 w-full mt-1">
                  <span className="text-[9px] text-gray-600 font-mono">{ctl.label}</span>
                  <input type="text" placeholder="text..."
                    className="flex-1 px-2.5 py-1.5 text-[10px] bg-gray-800/60 border border-gray-700/50 rounded-xl text-gray-300 placeholder-gray-700 font-mono focus:outline-none focus:border-purple-500/40"
                    onKeyDown={e => e.key === "Enter" && onControl(device, ctl.action, (e.target as HTMLInputElement).value)} />
                </div>
              );
            }
            return null;
          })}
        </div>
      </div>
    </div>
  );
}

export default function SmartHomePage() {
  const [devices, setDevices] = useState<SmartDevice[]>([]);
  const [scenes, setScenes] = useState<{ id: string; name: string; icon?: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [selectedType, setSelectedType] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/smarthome/dashboard");
      const data = await res.json();
      setDevices(data.devices || []);
      setScenes(data.scenes || []);
    } catch {
      try {
        const res = await fetch("/api/smarthome/devices");
        const data = await res.json();
        setDevices(data.devices || []);
      } catch {}
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleControl = useCallback(async (dev: SmartDevice, action: string, params = "") => {
    await fetch("/api/smarthome/control", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: dev.id, ip: dev.ip, action, params }),
    });
    load();
  }, [load]);

  const handleDiscover = useCallback(async () => {
    setDiscovering(true);
    await fetch("/api/smarthome/discover", { method: "POST" });
    await load();
    setDiscovering(false);
  }, [load]);

  const handleScene = useCallback(async (name: string) => {
    await fetch("/api/smarthome/scenes/activate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  }, []);

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

  const typeOrder = ["light", "switch", "sensor", "camera", "doorbell", "vacuum", "lock", "thermostat", "climate", "cover", "media_player", "alexa", "speaker", "hub"];

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#050510] via-[#0a0a1a] to-[#100620] relative">
      <ParticleBg />
      <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-purple-900/40 border border-purple-700/30 flex items-center justify-center text-lg shadow-[0_0_20px_rgba(120,60,220,0.2)]">
                🏠
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-purple-300 via-cyan-300 to-purple-300 bg-clip-text text-transparent">Smart Home Command Center</h1>
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
            <button onClick={handleDiscover} disabled={discovering}
              className="px-5 py-2.5 text-[10px] font-mono tracking-widest uppercase rounded-xl border transition-all duration-300 active:scale-95
                bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border-purple-500/30 text-purple-300
                hover:from-purple-600/30 hover:to-cyan-600/30 hover:shadow-[0_0_20px_rgba(120,60,220,0.2)]
                disabled:opacity-40 disabled:cursor-not-allowed">
              {discovering ? "⚡ Scanning..." : "⚡ Discover"}
            </button>
          </div>
        </div>

        {/* Stats bar */}
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

        {/* Scenes carousel */}
        {scenes.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[10px] font-mono text-gray-600 tracking-[0.2em] uppercase">🎬 Scenes</span>
              <div className="flex-1 h-px bg-gradient-to-r from-gray-800/50 to-transparent" />
            </div>
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
              {scenes.map((s, i) => (
                <button key={i} onClick={() => handleScene(s.name)}
                  className="shrink-0 px-5 py-3 text-xs font-mono rounded-xl border transition-all duration-200 active:scale-95
                    bg-gradient-to-br from-purple-900/20 to-cyan-900/10 border-purple-800/25 text-purple-300
                    hover:from-purple-900/30 hover:to-cyan-900/20 hover:border-purple-600/40
                    hover:shadow-[0_0_20px_rgba(120,60,220,0.15)]">
                  {s.icon || "🎬"} {s.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Devices grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1,2,3,4,5,6].map(i => (
              <div key={i} className="rounded-2xl bg-gray-900/30 border border-gray-800/20 h-48 animate-pulse relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-purple-900/10 to-transparent -skew-x-12 animate-shimmer" />
              </div>
            ))}
          </div>
        ) : filtered.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((d, i) => (
              <DeviceCard key={d.id || i} device={d} onControl={handleControl} />
            ))}
          </div>
        ) : (
          <div className="text-center py-24">
            <div className="text-6xl mb-6 opacity-30">🏠</div>
            <p className="text-gray-600 text-sm font-mono">No devices found</p>
            <p className="text-gray-700 text-xs mt-2 font-mono">Click <span className="text-purple-500">Discover</span> to scan your network</p>
          </div>
        )}
      </div>
    </div>
  );
}
