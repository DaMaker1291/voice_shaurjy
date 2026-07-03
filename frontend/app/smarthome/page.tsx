"use client";
import { useState, useEffect, useCallback } from "react";
import { getSmartHomeDevices, controlSmartHomeDevice, getSmartHomeScenes, activateSmartHomeScene, discoverSmartHome } from "@/lib/api";
import type { SmartHomeDevice, SmartHomeScene } from "@/lib/types";

const DEVICE_LABELS: Record<string, string> = {
  light: "💡 Light", switch: "🔌 Switch", sensor: "📡 Sensor",
  thermostat: "🌡 Thermostat", lock: "🔒 Lock", cover: "🪟 Cover",
  camera: "📷 Camera", vacuum: "🤖 Vacuum", climate: "❄️ Climate",
  media_player: "📺 Media", hub: "🏠 Hub", alexa: "🔊 Alexa",
  speaker: "🔊 Speaker",
};

const DEVICE_CONTROLS: Record<string, { label: string; action: string; type: string }[]> = {
  light: [
    { label: "On", action: "on", type: "button" },
    { label: "Off", action: "off", type: "button" },
    { label: "Toggle", action: "toggle", type: "button" },
    { label: "Brightness", action: "brightness", type: "range" },
  ],
  switch: [
    { label: "On", action: "on", type: "button" },
    { label: "Off", action: "off", type: "button" },
    { label: "Toggle", action: "toggle", type: "button" },
  ],
  sensor: [
    { label: "Read", action: "read", type: "button" },
  ],
  thermostat: [
    { label: "Heat", action: "mode", type: "button", params: "heat" },
    { label: "Cool", action: "mode", type: "button", params: "cool" },
    { label: "Off", action: "off", type: "button" },
    { label: "Temp", action: "temperature_set", type: "range" },
  ],
  lock: [
    { label: "🔓 Unlock", action: "unlock", type: "button" },
    { label: "🔒 Lock", action: "lock", type: "button" },
  ],
  cover: [
    { label: "Open", action: "open", type: "button" },
    { label: "Close", action: "close", type: "button" },
    { label: "Stop", action: "stop", type: "button" },
    { label: "Position", action: "position", type: "range" },
  ],
  vacuum: [
    { label: "▶ Start", action: "start", type: "button" },
    { label: "⏹ Stop", action: "stop", type: "button" },
    { label: "⏸ Pause", action: "pause", type: "button" },
    { label: "🏠 Dock", action: "dock", type: "button" },
    { label: "Status", action: "status", type: "button" },
  ],
  media_player: [
    { label: "On", action: "on", type: "button" },
    { label: "Off", action: "off", type: "button" },
    { label: "Volume", action: "volume", type: "range" },
    { label: "Mute", action: "mute", type: "button" },
  ],
  alexa: [
    { label: "Volume", action: "volume", type: "range" },
    { label: "Speak", action: "speak", type: "text" },
  ],
  camera: [
    { label: "📸 Snapshot", action: "snapshot", type: "button" },
    { label: "Status", action: "status", type: "button" },
  ],
  climate: [
    { label: "On", action: "on", type: "button" },
    { label: "Off", action: "off", type: "button" },
    { label: "Temp", action: "temperature_set", type: "range" },
  ],
  hub: [
    { label: "Status", action: "status", type: "button" },
  ],
};

export default function SmartHomePage() {
  const [devices, setDevices] = useState<SmartHomeDevice[]>([]);
  const [scenes, setScenes] = useState<SmartHomeScene[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0 });
  const [selectedType, setSelectedType] = useState<string>("all");
  const [renamingDevice, setRenamingDevice] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${window.location.protocol}//${window.location.host}/api/smarthome/dashboard`);
      const data = await res.json();
      setDevices(data.devices || []);
      setScenes(data.scenes || []);
      setStats({ total: data.total || 0, online: data.online || 0, offline: data.offline || 0 });
    } catch {
      const [d, s] = await Promise.allSettled([getSmartHomeDevices(), getSmartHomeScenes()]);
      if (d.status === "fulfilled") setDevices(d.value?.devices || d.value || []);
      if (s.status === "fulfilled") setScenes(s.value?.scenes || s.value || []);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleControl = useCallback(async (dev: SmartHomeDevice, action: string, params = "") => {
    const res = await fetch(`${window.location.protocol}//${window.location.host}/api/smarthome/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: dev.id,
        ip: dev.ip,
        action,
        params: params || dev.brightness?.toString() || "",
      }),
    });
    const data = await res.json();
    load();
    return data;
  }, [load]);

  const handleDiscover = useCallback(async () => {
    setDiscovering(true);
    try {
      await discoverSmartHome();
      await load();
    } catch {
      const res = await fetch(`${window.location.protocol}//${window.location.host}/api/smarthome/discover`, { method: "POST" });
      if (res.ok) await load();
    }
    setDiscovering(false);
  }, [load]);

  const handleScene = useCallback(async (name: string) => {
    await activateSmartHomeScene(name);
  }, []);

  const handleRename = useCallback(async (deviceId: string) => {
    if (!renameValue.trim()) return;
    await fetch(`${window.location.protocol}//${window.location.host}/api/smarthome/device/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, name: renameValue.trim() }),
    });
    setRenamingDevice(null);
    load();
  }, [renameValue, load]);

  const filteredDevices = selectedType === "all"
    ? devices
    : devices.filter(d => d.type === selectedType);

  const types = ["all", ...new Set(devices.map(d => d.type))];

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-purple-400">🏠 Smart Home</h1>
          <p className="text-[10px] text-gray-600 mt-0.5 font-mono">
            {stats.online} online · {stats.offline} offline · {stats.total} total devices
          </p>
        </div>
        <button onClick={handleDiscover} disabled={discovering}
          className="px-4 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-700/30 text-cyan-400 text-xs rounded-xl font-mono tracking-wider disabled:opacity-40">
          {discovering ? "🔍 Scanning..." : "🔍 Discover"}
        </button>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries({
          light: "💡", switch: "🔌", sensor: "📡", camera: "📷",
          vacuum: "🤖", climate: "❄️", media_player: "📺", alexa: "🔊",
        }).map(([type, icon]) => {
          const count = devices.filter(d => d.type === type).length;
          const online = devices.filter(d => d.type === type && d.status === "online").length;
          if (count === 0) return null;
          return (
            <button key={type} onClick={() => setSelectedType(type)}
              className={`bg-gray-900/40 border rounded-xl p-3 text-left transition-all ${
                selectedType === type ? "border-cyan-500/40 ring-1 ring-cyan-500/20" : "border-gray-800/30"
              }`}>
              <div className="flex items-center gap-2">
                <span className="text-lg">{icon}</span>
                <span className="text-[10px] font-mono text-gray-500 uppercase">{type}</span>
              </div>
              <div className="flex gap-3 mt-1">
                <span className="text-xs text-green-400">{online} on</span>
                <span className="text-xs text-gray-600">{count} total</span>
              </div>
            </button>
          );
        })}
        <button onClick={() => setSelectedType("all")}
          className={`bg-gray-900/40 border rounded-xl p-3 text-left transition-all ${
            selectedType === "all" ? "border-purple-500/40 ring-1 ring-purple-500/20" : "border-gray-800/30"
          }`}>
          <div className="text-lg mb-1">📊</div>
          <div className="text-[10px] font-mono text-gray-500">All Devices</div>
          <div className="text-xs text-gray-400 mt-1">{devices.length} total</div>
        </button>
      </div>

      {/* Scenes */}
      {scenes.length > 0 && (
        <div>
          <h2 className="text-sm font-mono text-gray-500 uppercase tracking-wider mb-3">🎬 Scenes</h2>
          <div className="flex flex-wrap gap-2">
            {scenes.map((s, i) => (
              <button key={i} onClick={() => handleScene(s.name)}
                className="px-4 py-2 bg-purple-900/20 border border-purple-800/30 rounded-xl text-xs text-purple-400 hover:bg-purple-900/30 transition-all active:scale-95">
                {s.icon || "🎬"} {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Type filter tabs */}
      {types.length > 2 && (
        <div className="flex gap-1 flex-wrap">
          {types.map(t => (
            <button key={t} onClick={() => setSelectedType(t)}
              className={`px-3 py-1 text-[10px] font-mono rounded-lg transition-all ${
                selectedType === t
                  ? "bg-purple-900/30 text-purple-300 border border-purple-700/30"
                  : "text-gray-600 hover:text-gray-400 border border-transparent"
              }`}>
              {DEVICE_LABELS[t] || t} ({devices.filter(d => d.type === t).length})
            </button>
          ))}
        </div>
      )}

      {/* Device grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="bg-gray-900/20 border border-gray-800/20 rounded-xl h-32 animate-pulse" />
          ))}
        </div>
      ) : filteredDevices.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDevices.map((d, i) => {
            const controls = DEVICE_CONTROLS[d.type] || DEVICE_CONTROLS.switch;
            return (
              <div key={d.id || i}
                className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-4 space-y-3 hover:border-gray-700/40 transition-all">
                {/* Device header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm text-gray-200 font-medium truncate">{d.name}</h3>
                      {renamingDevice === d.id ? (
                        <div className="flex gap-1">
                          <input value={renameValue} onChange={e => setRenameValue(e.target.value)}
                            className="w-24 px-1 py-0.5 text-[10px] bg-gray-800 border border-gray-700 rounded text-gray-200"
                            autoFocus onKeyDown={e => e.key === "Enter" && handleRename(d.id)} />
                          <button onClick={() => handleRename(d.id)}
                            className="text-[9px] text-cyan-400">save</button>
                        </div>
                      ) : (
                        <button onClick={() => { setRenamingDevice(d.id); setRenameValue(d.name); }}
                          className="text-[9px] text-gray-600 hover:text-gray-400 opacity-0 group-hover:opacity-100">✎</button>
                      )}
                    </div>
                    <p className="text-[10px] text-gray-600 font-mono mt-0.5">
                      {DEVICE_LABELS[d.type] || d.type} · {d.protocol || "http"} · {d.room || "no room"}
                    </p>
                  </div>
                  <span className={`shrink-0 text-[9px] px-2 py-0.5 rounded-full font-mono ${
                    d.status === "online" ? "bg-green-900/30 text-green-400" : "bg-gray-800/50 text-gray-600"
                  }`}>
                    {d.status === "online" ? "● LIVE" : "○ OFF"}
                  </span>
                </div>

                {/* Device state details */}
                {d.brightness !== undefined && d.type === "light" && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-yellow-500">☀</span>
                    <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-yellow-400 to-orange-400"
                        style={{ width: `${d.brightness}%` }} />
                    </div>
                    <span className="text-[10px] text-gray-500 w-8 text-right">{d.brightness}%</span>
                  </div>
                )}

                {d.temperature !== undefined && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-red-400">🌡</span>
                    <span className="text-xs text-gray-300">{d.temperature}°C</span>
                  </div>
                )}

                {/* Control buttons */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {controls.map((ctl, ci) => {
                    if (ctl.type === "button") {
                      return (
                        <button key={ci} onClick={() => handleControl(d, ctl.action, ctl.params)}
                          className={`px-3 py-1.5 text-[10px] font-mono rounded-lg border transition-all active:scale-95 ${
                            ctl.action === "on" || ctl.action === "start" || ctl.action === "open" || ctl.action === "unlock"
                              ? "bg-green-600/15 border-green-700/25 text-green-400 hover:bg-green-600/25"
                              : ctl.action === "off" || ctl.action === "close" || ctl.action === "lock" || ctl.action === "stop"
                              ? "bg-red-600/15 border-red-700/25 text-red-400 hover:bg-red-600/25"
                              : "bg-gray-800/40 border-gray-700/30 text-gray-400 hover:bg-gray-700/40"
                          }`}>
                          {ctl.label}
                        </button>
                      );
                    }
                    if (ctl.type === "range") {
                      return (
                        <div key={ci} className="flex items-center gap-2 w-full mt-1">
                          <span className="text-[9px] text-gray-600 font-mono uppercase">{ctl.label}</span>
                          <input type="range" min={ctl.action === "temperature_set" ? 10 : 0}
                            max={ctl.action === "temperature_set" ? 35 : 100}
                            defaultValue={ctl.action === "temperature_set" ? 22 : 50}
                            onChange={e => handleControl(d, ctl.action, e.target.value)}
                            className="flex-1 h-1 accent-cyan-500" />
                        </div>
                      );
                    }
                    if (ctl.type === "text") {
                      return (
                        <div key={ci} className="flex items-center gap-1 w-full mt-1">
                          <span className="text-[9px] text-gray-600 font-mono">{ctl.label}</span>
                          <input type="text" placeholder="text..."
                            className="flex-1 px-2 py-1 text-[10px] bg-gray-800/60 border border-gray-700/50 rounded text-gray-300"
                            onKeyDown={e => e.key === "Enter" && handleControl(d, ctl.action, (e.target as HTMLInputElement).value)} />
                        </div>
                      );
                    }
                    return null;
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-20">
          <div className="text-4xl mb-4">🏠</div>
          <p className="text-gray-600 text-sm">No devices discovered yet</p>
          <p className="text-gray-700 text-xs mt-1 font-mono">Click "Discover" to scan your network</p>
        </div>
      )}
    </div>
  );
}
