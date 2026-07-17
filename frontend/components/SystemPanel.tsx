"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { getSystemStats, getSystemProcesses, getClipboard, takeScreenshot, runAction, setVolume, setBrightness, sendNotification, webSearch, getWeather, computerRunTask, computerTaskStatus, computerStopTask } from "@/lib/api";

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

interface Stats { cpu: { percent: number; cores: number[]; count: number }; memory: { percent: number; used_gb: number; total_gb: number; free_gb: number }; battery: { percent: number | null; charging: boolean | null; present: boolean }; disk: { percent: number; free_gb: number; total_gb: number; used_gb: number }; network: { bytes_sent_mb: number; bytes_recv_mb: number }; uptime_h: number; boot_time: string }
interface Proc { pid: number; name: string; cpu: number; mem: number; mem_mb: number }

const BS = ({ p }: { p: number }) => (
  <div className="w-full h-1.5 rounded-full bg-gray-800/60 overflow-hidden">
    <div className="h-full rounded-full transition-all duration-500" style={{ width: `${p}%`, background: p > 80 ? "linear-gradient(90deg,#ef4444,#dc2626)" : p > 50 ? "linear-gradient(90deg,#f59e0b,#d97706)" : "linear-gradient(90deg,#22c55e,#16a34a)" }} />
  </div>
);

export default function SystemPanel({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"stats" | "procs" | "actions" | "search" | "weather" | "tools" | "computer">("stats");
  const [computerTask, setComputerTask] = useState("");
  const [computerStatus, setComputerStatus] = useState<any>(null);
  const [computerRunning, setComputerRunning] = useState(false);
  const computerPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [procs, setProcs] = useState<Proc[]>([]);
  const [clipText, setClipText] = useState("");
  const [screenshotB64, setScreenshotB64] = useState("");
  const [actions, setActions] = useState<Record<string, { label: string; tip: string }>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ title: string; url: string; snippet: string }[]>([]);
  const [searching, setSearching] = useState(false);
  const [weatherCity, setWeatherCity] = useState("");
  const [weatherData, setWeatherData] = useState<any>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [notifMsg, setNotifMsg] = useState("");
  const [timerSecs, setTimerSecs] = useState(60);
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerRemaining, setTimerRemaining] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await getSystemStats();
      setStats(s);
      const p = await getSystemProcesses(10);
      setProcs(p.processes || []);
      const c = await getClipboard();
      setClipText(c.text || "");
    } catch {}
  }, []);

  useEffect(() => { refresh(); const i = setInterval(refresh, 3000); return () => clearInterval(i); }, [refresh]);

  useEffect(() => {
    (async () => {
      try {
        const a = await safeJson(await fetch(`http://localhost:8000/api/actions`));
        setActions(a.actions || {});
      } catch {}
    })();
  }, []);

  const doAction = async (id: string) => {
    try {
      await runAction(id);
      if (onClose) onClose();
    } catch {}
  };

  const doScreenshot = async () => {
    try {
      const r = await takeScreenshot();
      if (r.image) setScreenshotB64(`data:image/png;base64,${r.image}`);
    } catch {}
  };

  const tabs = [
    { id: "stats" as const, label: "Stats" },
    { id: "procs" as const, label: "Procs" },
    { id: "actions" as const, label: "Actions" },
    { id: "search" as const, label: "Search" },
    { id: "weather" as const, label: "Weather" },
    { id: "tools" as const, label: "Tools" },
    { id: "computer" as const, label: "Computer" },
  ];

  const quickActions = [
    { id: "vol_up", icon: " 🔊", label: "Vol Up" },
    { id: "vol_down", icon: " 🔉", label: "Vol Down" },
    { id: "vol_mute", icon: " 🔇", label: "Mute" },
    { id: "brightness_up", icon: " ☀️", label: "Bright+" },
    { id: "brightness_down", icon: " 🌙", label: "Bright-" },
    { id: "lock", icon: " 🔒", label: "Lock" },
    { id: "screenshot", icon: " 📸", label: "SS" },
    { id: "media_next", icon: " ⏭️", label: "Next" },
    { id: "media_prev", icon: " ⏮️", label: "Prev" },
    { id: "media_play", icon: " ▶️", label: "Play" },
    { id: "media_pause", icon: " ⏸️", label: "Pause" },
    { id: "process_list", icon: " 📋", label: "Procs" },
  ];

  return (
    <div className="absolute right-0 top-9 z-50 w-[28rem] max-w-[90vw] animate-fade-in" style={{ maxHeight: "80vh" }}>
      <div className="glass-card overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800/20">
          <span className="text-[9px] font-mono text-purple-400/60 tracking-[0.25em] uppercase">System Control</span>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 transition-colors p-1 rounded hover:bg-gray-800/30"><svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-800/20">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`flex-1 text-[9px] font-mono tracking-[0.15em] py-2 transition-colors ${tab === t.id ? "text-purple-400 border-b border-purple-500/40" : "text-gray-600 hover:text-gray-400"}`}>{t.label}</button>
          ))}
        </div>

        {/* Tab content */}
        <div className="overflow-y-auto" style={{ maxHeight: "calc(80vh - 80px)" }}>
          {tab === "stats" && stats && (
            <div className="p-4 space-y-3">
              {/* Quick actions grid */}
              <div className="grid grid-cols-6 gap-1.5 pb-3 border-b border-gray-800/20">
                {quickActions.map(a => (
                  <button key={a.id} onClick={() => doAction(a.id)} className="text-[9px] font-mono text-gray-500 hover:text-purple-400 py-1.5 px-1 rounded-lg hover:bg-purple-900/10 border border-transparent hover:border-purple-500/20 transition-all" title={a.label}>
                    <div className="text-center"><span className="text-xs">{a.icon.split(" ")[1] || a.icon}</span></div>
                  </button>
                ))}
              </div>

              {/* CPU */}
              <div><div className="flex justify-between text-[10px] font-mono mb-1"><span className="text-gray-500">CPU</span><span className="text-gray-400">{stats.cpu.percent}%</span></div><BS p={stats.cpu.percent} /></div>

              {/* Memory */}
              <div><div className="flex justify-between text-[10px] font-mono mb-1"><span className="text-gray-500">RAM</span><span className="text-gray-400">{stats.memory.used_gb}/{stats.memory.total_gb}GB</span></div><BS p={stats.memory.percent} /></div>

              {/* Disk */}
              <div><div className="flex justify-between text-[10px] font-mono mb-1"><span className="text-gray-500">Disk</span><span className="text-gray-400">{stats.disk.used_gb}/{stats.disk.total_gb}GB</span></div><BS p={stats.disk.percent} /></div>

              {/* Battery */}
              {stats.battery.present && (
                <div><div className="flex justify-between text-[10px] font-mono mb-1"><span className="text-gray-500">Battery</span><span className="text-gray-400">{stats.battery.percent}% {stats.battery.charging ? "⚡" : "🔋"}</span></div><BS p={stats.battery.percent ?? 0} /></div>
              )}

              {/* Info grid */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-800/20">
                <div className="text-[9px] font-mono text-gray-600"><span className="block text-gray-500/60 text-[8px] tracking-wider">UPTIME</span>{stats.uptime_h}h</div>
                <div className="text-[9px] font-mono text-gray-600"><span className="block text-gray-500/60 text-[8px] tracking-wider">CORES</span>{stats.cpu.count}</div>
                <div className="text-[9px] font-mono text-gray-600"><span className="block text-gray-500/60 text-[8px] tracking-wider">NET SENT</span>{stats.network.bytes_sent_mb}MB</div>
                <div className="text-[9px] font-mono text-gray-600"><span className="block text-gray-500/60 text-[8px] tracking-wider">NET RECV</span>{stats.network.bytes_recv_mb}MB</div>
              </div>

              {/* Clipboard */}
              <div className="pt-2 border-t border-gray-800/20">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[8px] font-mono text-gray-600 tracking-[0.2em] uppercase">Clipboard</span>
                  <button onClick={() => doAction("clipboard_clear")} className="text-[8px] font-mono text-gray-700 hover:text-gray-400 transition-colors">clear</button>
                </div>
                <p className="text-[10px] font-mono text-gray-500 bg-gray-900/40 rounded-lg px-3 py-2 truncate">{clipText || "empty"}</p>
              </div>

              {/* Screenshot */}
              <div className="pt-2 border-t border-gray-800/20">
                <button onClick={doScreenshot} className="w-full text-[9px] font-mono text-gray-500 hover:text-purple-400 py-2 rounded-lg border border-dashed border-gray-800/30 hover:border-purple-500/30 transition-all text-center">
                  📸 Take Screenshot
                </button>
                {screenshotB64 && (
                  <div className="mt-2 rounded-lg overflow-hidden border border-gray-800/30">
                    <img src={screenshotB64} alt="screenshot" className="w-full" />
                    <button onClick={() => setScreenshotB64("")} className="w-full text-[8px] font-mono text-gray-700 hover:text-gray-400 py-1 transition-colors">dismiss</button>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === "procs" && (
            <div className="p-3">
              <div className="flex justify-between text-[8px] font-mono text-gray-600 tracking-wider uppercase px-2 pb-1.5 border-b border-gray-800/20">
                <span className="w-7">PID</span>
                <span className="flex-1 ml-2">Name</span>
                <span className="w-10 text-right">CPU%</span>
                <span className="w-12 text-right">Mem MB</span>
              </div>
              <div className="space-y-0.5 mt-1">
                {procs.map(p => (
                  <div key={p.pid} className="flex items-center text-[10px] font-mono text-gray-500 px-2 py-1 rounded hover:bg-gray-800/20 transition-colors">
                    <span className="w-7 text-gray-600">{p.pid}</span>
                    <span className="flex-1 ml-2 truncate">{p.name}</span>
                    <span className="w-10 text-right" style={{ color: p.cpu > 10 ? "#ef4444" : p.cpu > 5 ? "#f59e0b" : "#6b7280" }}>{p.cpu.toFixed(1)}</span>
                    <span className="w-12 text-right text-gray-600">{p.mem_mb.toFixed(0)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === "search" && (
            <div className="p-3">
              <div className="flex gap-2 mb-3">
                <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={async e => { if (e.key === "Enter" && searchQuery.trim()) { setSearching(true); try { const r = await webSearch(searchQuery); setSearchResults(r.results || []); } catch {} setSearching(false); } }} placeholder="Search the web..." className="flex-1 text-[10px] font-mono bg-gray-900/40 border border-gray-800/30 rounded-lg px-3 py-1.5 text-gray-400 outline-none focus:border-purple-500/30 transition-colors" />
                <button onClick={async () => { if (!searchQuery.trim()) return; setSearching(true); try { const r = await webSearch(searchQuery); setSearchResults(r.results || []); } catch {} setSearching(false); }} disabled={searching} className="text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all">{searching ? "..." : "Go"}</button>
              </div>
              <div className="space-y-2">
                {searchResults.map((r, i) => (
                  <div key={i} className="border border-gray-800/20 rounded-lg p-2.5 hover:border-purple-500/20 transition-colors">
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-[10px] font-mono text-purple-400/80 hover:text-purple-300 line-clamp-1 block">{r.title || r.url.slice(0, 60)}</a>
                    {r.snippet && <p className="text-[9px] font-mono text-gray-600 mt-1 line-clamp-2">{r.snippet.slice(0, 200)}</p>}
                    <span className="text-[7px] font-mono text-gray-700 mt-1 block truncate">{r.url}</span>
                  </div>
                ))}
                {searchResults.length === 0 && !searching && <p className="text-[10px] font-mono text-gray-700 text-center py-8">Type a query and press Enter</p>}
              </div>
            </div>
          )}

          {tab === "weather" && (
            <div className="p-3">
              <div className="flex gap-2 mb-3">
                <input type="text" value={weatherCity} onChange={e => setWeatherCity(e.target.value)} onKeyDown={async e => { if (e.key === "Enter" && weatherCity.trim()) { setWeatherLoading(true); try { const w = await getWeather(weatherCity); setWeatherData(w); } catch {} setWeatherLoading(false); } }} placeholder="City name..." className="flex-1 text-[10px] font-mono bg-gray-900/40 border border-gray-800/30 rounded-lg px-3 py-1.5 text-gray-400 outline-none focus:border-purple-500/30 transition-colors" />
                <button onClick={async () => { if (!weatherCity.trim()) return; setWeatherLoading(true); try { const w = await getWeather(weatherCity); setWeatherData(w); } catch {} setWeatherLoading(false); }} disabled={weatherLoading} className="text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all">{weatherLoading ? "..." : "Go"}</button>
              </div>
              {weatherData && !weatherData.error && (
                <div className="space-y-2">
                  <div className="text-center py-3">
                    <p className="text-[11px] font-mono text-gray-400">{weatherData.location}</p>
                    <p className="text-3xl font-mono text-gray-200 mt-1">{weatherData.temp_c}°C</p>
                    <p className="text-[10px] font-mono text-gray-500 mt-0.5">feels like {weatherData.feels_like}°C</p>
                    <p className="text-[10px] font-mono text-purple-400/60 mt-1">{weatherData.condition}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="text-[9px] font-mono text-gray-600 bg-gray-900/30 rounded-lg p-2"><span className="block text-gray-500/60 text-[8px] tracking-wider">HUMIDITY</span>{weatherData.humidity}%</div>
                    <div className="text-[9px] font-mono text-gray-600 bg-gray-900/30 rounded-lg p-2"><span className="block text-gray-500/60 text-[8px] tracking-wider">WIND</span>{weatherData.wind_kph} kph {weatherData.wind_dir}</div>
                    <div className="text-[9px] font-mono text-gray-600 bg-gray-900/30 rounded-lg p-2"><span className="block text-gray-500/60 text-[8px] tracking-wider">UV</span>{weatherData.uv}</div>
                    <div className="text-[9px] font-mono text-gray-600 bg-gray-900/30 rounded-lg p-2"><span className="block text-gray-500/60 text-[8px] tracking-wider">VISIBILITY</span>{weatherData.visibility} km</div>
                  </div>
                  <div className="text-[9px] font-mono text-center"><span className="text-gray-600">{weatherData.temp_f}°F</span></div>
                </div>
              )}
              {weatherData?.error && <p className="text-[10px] font-mono text-red-400/60 text-center py-4">Could not find weather</p>}
              {!weatherData && !weatherLoading && <p className="text-[10px] font-mono text-gray-700 text-center py-8">Enter a city to check weather</p>}
            </div>
          )}

          {tab === "tools" && (
            <div className="p-3 space-y-3">
              {/* Notification sender */}
              <div>
                <span className="text-[8px] font-mono text-gray-600 tracking-[0.2em] uppercase block mb-1.5">Send Notification</span>
                <div className="flex gap-2">
                  <input type="text" value={notifMsg} onChange={e => setNotifMsg(e.target.value)} onKeyDown={async e => { if (e.key === "Enter" && notifMsg.trim()) { try { await sendNotification(notifMsg); setNotifMsg(""); } catch {} } }} placeholder="Message to send..." className="flex-1 text-[10px] font-mono bg-gray-900/40 border border-gray-800/30 rounded-lg px-3 py-1.5 text-gray-400 outline-none focus:border-purple-500/30 transition-colors" />
                  <button onClick={async () => { if (!notifMsg.trim()) return; try { await sendNotification(notifMsg); setNotifMsg(""); } catch {} }} className="text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all">Send</button>
                </div>
              </div>

              {/* Timer */}
              <div className="pt-2 border-t border-gray-800/20">
                <span className="text-[8px] font-mono text-gray-600 tracking-[0.2em] uppercase block mb-1.5">Timer</span>
                <div className="flex gap-2 items-center">
                  <input type="number" value={timerSecs} onChange={e => setTimerSecs(parseInt(e.target.value) || 60)} min={1} max={3600} className="w-20 text-[10px] font-mono bg-gray-900/40 border border-gray-800/30 rounded-lg px-2.5 py-1.5 text-gray-400 outline-none focus:border-purple-500/30 transition-colors" />
                  <span className="text-[9px] font-mono text-gray-600">sec</span>
                  <button onClick={() => {
                    if (timerRunning) {
                      if (timerRef.current) clearInterval(timerRef.current);
                      setTimerRunning(false);
                    } else {
                      setTimerRemaining(timerSecs);
                      setTimerRunning(true);
                      timerRef.current = setInterval(() => {
                        setTimerRemaining(p => {
                          if (p <= 1) { clearInterval(timerRef.current!); setTimerRunning(false); return 0; }
                          return p - 1;
                        });
                      }, 1000);
                    }
                  }} className="text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all">{timerRunning ? "Stop" : "Start"}</button>
                </div>
                {(timerRunning || timerRemaining > 0) && (
                  <div className="mt-2">
                    <div className="w-full h-2 rounded-full bg-gray-800/60 overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${(timerRemaining / timerSecs) * 100}%`, background: "linear-gradient(90deg,#22c55e,#16a34a)" }} />
                    </div>
                    <p className="text-center text-lg font-mono text-gray-400 mt-1">{Math.floor(timerRemaining / 60)}:{(timerRemaining % 60).toString().padStart(2, "0")}</p>
                  </div>
                )}
              </div>

              {/* Math eval */}
              <div className="pt-2 border-t border-gray-800/20">
                <span className="text-[8px] font-mono text-gray-600 tracking-[0.2em] uppercase block mb-1.5">Quick Math</span>
                <button onClick={async () => {
                  const expr = prompt("Enter expression:");
                  if (expr) { try { const r = await runAction("math_eval", expr); alert(r.result || r.error); } catch {} }
                }} className="text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all w-full text-center">Calculate</button>
              </div>

              {/* Public IP */}
              <div className="pt-2 border-t border-gray-800/20">
                <button onClick={async () => {
                  try { const r = await runAction("public_ip"); alert(r.result || r.error); } catch {}
                }} className="text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all w-full text-center">Check Public IP</button>
              </div>
            </div>
          )}

          {tab === "computer" && (
            <div className="p-3 space-y-3">
              <span className="text-[8px] font-mono text-gray-600 tracking-[0.2em] uppercase block">AI Computer Agent</span>
              <p className="text-[9px] font-mono text-gray-600 leading-relaxed">The AI can see your screen and control the mouse/keyboard to complete visual tasks — filling forms, using OneNote, navigating apps, etc.</p>
              <textarea value={computerTask} onChange={e => setComputerTask(e.target.value)} rows={3} placeholder="Describe a task for the AI to do on your computer... e.g. Open OneNote and create a new page called Weekly Notes" className="w-full text-[10px] font-mono bg-gray-900/40 border border-gray-800/30 rounded-lg px-3 py-2 text-gray-400 outline-none focus:border-purple-500/30 transition-colors resize-none" />
              <div className="flex gap-2">
                <button onClick={async () => {
                  if (!computerTask.trim()) return;
                  setComputerRunning(true);
                  setComputerStatus({ status: "running" });
                  try {
                    const r = await computerRunTask(computerTask);
                    setComputerStatus((prev: any) => ({ ...prev, task_id: r.task_id }));
                    // Poll status
                    if (computerPollRef.current) clearInterval(computerPollRef.current);
                    computerPollRef.current = setInterval(async () => {
                      try {
                        const s = await computerTaskStatus(r.task_id);
                        setComputerStatus(s);
                        if (s.status === "done" || s.status === "failed" || s.status === "stopped") {
                          setComputerRunning(false);
                          if (computerPollRef.current) clearInterval(computerPollRef.current);
                        }
                      } catch {}
                    }, 2000);
                  } catch { setComputerRunning(false); }
                }} disabled={computerRunning} className="flex-1 text-[9px] font-mono text-purple-400/60 hover:text-purple-400 px-3 py-2 rounded-lg border border-purple-500/20 hover:border-purple-500/40 transition-all disabled:opacity-40">{computerRunning ? "Running..." : "▶ Run Task"}</button>
                <button onClick={async () => {
                  try { await computerStopTask(); setComputerRunning(false); setComputerStatus({ status: "stopped" }); if (computerPollRef.current) clearInterval(computerPollRef.current); } catch {}
                }} disabled={!computerRunning} className="text-[9px] font-mono text-red-400/60 hover:text-red-400 px-3 py-2 rounded-lg border border-red-500/20 hover:border-red-500/40 transition-all disabled:opacity-40">Stop</button>
              </div>
              {computerStatus && (
                <div className="bg-gray-900/30 rounded-lg p-2.5 border border-gray-800/20">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${computerStatus.status === "running" ? "bg-green-500 animate-pulse" : computerStatus.status === "done" ? "bg-green-500" : computerStatus.status === "failed" ? "bg-red-500" : "bg-gray-600"}`} />
                    <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider">{computerStatus.status}</span>
                  </div>
                  {computerStatus.summary && <p className="text-[9px] font-mono text-gray-400 mt-1">{computerStatus.summary}</p>}
                  {computerStatus.steps > 0 && <p className="text-[8px] font-mono text-gray-600 mt-1">{computerStatus.steps} steps in {computerStatus.duration_sec}s</p>}
                  {computerStatus.log && computerStatus.log.length > 0 && (
                    <div className="mt-2 space-y-0.5 max-h-24 overflow-y-auto">
                      {computerStatus.log.map((l: string, i: number) => (
                        <p key={i} className="text-[7px] font-mono text-gray-700 leading-tight truncate">{l}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === "actions" && (
            <div className="p-3">
              <input type="text" placeholder="Search actions..." className="w-full text-[10px] font-mono bg-gray-900/40 border border-gray-800/30 rounded-lg px-3 py-1.5 text-gray-400 outline-none focus:border-purple-500/30 transition-colors mb-3" onChange={async (e) => {
                const q = e.target.value;
                if (!q) { try { const a = await safeJson(await fetch(`http://localhost:8000/api/actions`)); setActions(a.actions || {}); } catch {} return; }
                try { const a = await safeJson(await fetch(`http://localhost:8000/api/actions/search?q=${encodeURIComponent(q)}`)); setActions(a.actions || {}); } catch {}
              }} />
              <div className="grid grid-cols-3 gap-1">
                {Object.entries(actions).slice(0, 90).map(([id, info]) => (
                  <button key={id} onClick={() => doAction(id)} className="text-[8px] font-mono text-gray-500 hover:text-purple-400 truncate px-2 py-1 rounded hover:bg-purple-900/10 transition-all text-left" title={info.tip || id}>
                    {info.label || id}
                  </button>
                ))}
              </div>
              {Object.keys(actions).length > 90 && <p className="text-[8px] font-mono text-gray-700 text-center mt-2">{Object.keys(actions).length} total actions</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
