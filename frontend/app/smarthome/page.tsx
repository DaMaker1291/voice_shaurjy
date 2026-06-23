"use client";
import { useState, useEffect, useCallback } from "react";
import { getSmartHomeDevices, controlSmartHomeDevice, getSmartHomeScenes, activateSmartHomeScene } from "@/lib/api";
import type { SmartHomeDevice, SmartHomeScene } from "@/lib/types";
import { SkeletonCard } from "@/components/LoadingSkeleton";

export default function SmartHomePage() {
  const [devices, setDevices] = useState<SmartHomeDevice[]>([]);
  const [scenes, setScenes] = useState<SmartHomeScene[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [d, s] = await Promise.allSettled([getSmartHomeDevices(), getSmartHomeScenes()]);
    if (d.status === "fulfilled") setDevices(d.value?.devices || d.value || []);
    if (s.status === "fulfilled") setScenes(s.value?.scenes || s.value || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleControl = useCallback(async (ip: string, action: string) => {
    await controlSmartHomeDevice(ip, action);
    const d = await getSmartHomeDevices();
    setDevices(d?.devices || d || []);
  }, []);

  const handleScene = useCallback(async (name: string) => {
    await activateSmartHomeScene(name);
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div><h1 className="text-xl font-bold text-purple-400">Smart Home</h1><p className="text-xs text-gray-500 mt-0.5">Control your connected devices</p></div>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : (
        <>
          {scenes.length > 0 && (
            <div>
              <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider mb-3">Scenes</h2>
              <div className="flex gap-2 mb-6">
                {scenes.map((s, i) => (
                  <button key={i} onClick={() => handleScene(s.name)} className="px-4 py-2 bg-purple-900/20 border border-purple-800/30 rounded-xl text-xs text-purple-400 hover:bg-purple-900/30">{s.name}</button>
                ))}
              </div>
            </div>
          )}
          {devices.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {devices.map((d, i) => (
                <div key={i} className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm text-gray-200">{d.name}</h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${d.status === "online" ? "bg-green-900/30 text-green-400" : "bg-gray-800/50 text-gray-600"}`}>{d.status}</span>
                  </div>
                  <p className="text-[10px] text-gray-600 font-mono">{d.type} • {d.room}</p>
                  {d.brightness !== undefined && (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-500">Brightness: {d.brightness}%</span>
                      <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                        <div className="h-full rounded-full bg-yellow-400" style={{ width: `${d.brightness}%` }} />
                      </div>
                    </div>
                  )}
                  <div className="flex gap-2 pt-2">
                    {d.status === "online" && (
                      <>
                        <button onClick={() => handleControl(d.ip, "on")} className="flex-1 px-3 py-1.5 bg-green-600/20 hover:bg-green-600/30 border border-green-700/30 text-green-400 text-xs rounded-lg">On</button>
                        <button onClick={() => handleControl(d.ip, "off")} className="flex-1 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 border border-red-700/30 text-red-400 text-xs rounded-lg">Off</button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-20 text-gray-600 text-sm">No devices discovered. Run discovery from the chat.</div>
          )}
        </>
      )}
    </div>
  );
}
