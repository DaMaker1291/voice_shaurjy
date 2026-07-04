"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import BotSwarm from "@/components/BotSwarm";
import Sidebar from "@/components/Sidebar";
import AgentStatusBar from "@/components/AgentStatusBar";
import AgentRouter from "@/components/AgentRouter";
import CockpitTelemetry from "@/components/CockpitTelemetry";
import { entityProcess } from "@/lib/api";

interface Message { role: string; content: string; image?: string; link?: string }
interface Strategy { name: string; description: string; pros: string[]; cons: string[]; complexity: number; key_steps: string[] }
interface EntityState { memory_summary: string; active_goals: { goal: string; priority: number; progress: number }[]; preferences: Record<string, { value: string }>; interaction_count: number }
interface BotEvent { type: string; label: string; timestamp: number }
interface SystemStats { cpu?: { percent: number; count: number }; memory?: { percent: number; used_gb: number; total_gb: number }; battery?: { percent: number; charging: boolean; present: boolean }; uptime_h?: number }
interface ActivityEntry { ts: number; msg: string; type: "info" | "action" | "error" | "success" }
interface RouterPayload { routing?: { target_agent?: string; routing_confidence?: number; extracted_intent?: string; execution_context?: Record<string, unknown> }; agent_response?: Record<string, unknown>; latency_ms?: { supervisor?: number; worker?: number; total?: number }; target_agent?: string }
interface DeviceNode { id: string; name: string; status: "ACTIVE" | "STANDBY" | "CHARGING" | "OFFLINE" | "UNKNOWN" | "OPTIMAL" | "WARNING" | "CRITICAL"; domain?: string; metrics?: string; controls?: string[] }

const BASE = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

const SUGGESTIONS = [
  "scan my network", "turn off all lights", "open VS Code",
  "book a flight to Tokyo", "take a screenshot", "what's my CPU usage?",
  "volume to 60%", "search for weather today",
];

const NAV_ITEMS = [
  { href: "/", label: "Command", icon: "⚡" },
  { href: "/dashboard", label: "Brain", icon: "🧠" },
  { href: "/life", label: "Life OS", icon: "🫀" },
  { href: "/trading", label: "Trading", icon: "📈" },
  { href: "/secretary", label: "Secretary", icon: "📋" },
  { href: "/agent", label: "Agent", icon: "🤖" },
  { href: "/reminders", label: "Reminders", icon: "⏰" },
  { href: "/marketplace", label: "Plugins", icon: "🧩" },
  { href: "/settings", label: "Config", icon: "⚙" },
];

function ParticleBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvasRef.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    c.width = window.innerWidth; c.height = window.innerHeight;
    const particles = Array.from({ length: 60 }, () => ({
      x: Math.random() * c.width, y: Math.random() * c.height,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 1.2 + 0.3,
    }));
    let anim: number;
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > c.width) p.vx *= -1;
        if (p.y < 0 || p.y > c.height) p.vy *= -1;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(52,211,153,0.15)"; ctx.fill();
      });
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(52,211,153,${0.04 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5; ctx.stroke();
          }
        }
      }
      anim = requestAnimationFrame(draw);
    };
    draw(); return () => cancelAnimationFrame(anim);
  }, []);
  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

export default function Home() {
  const pathname = usePathname();
  const [messages, setMessages] = useState<Message[]>([]);
  const [textInput, setTextInput] = useState("");
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [taskQuestion, setTaskQuestion] = useState<string | null>(null);
  const [taskSession, setTaskSession] = useState<string | null>(null);
  const [taskResult, setTaskResult] = useState<string | null>(null);
  const [taskStep, setTaskStep] = useState(0);
  const [taskTotal, setTaskTotal] = useState(0);
  const [collectedInfo, setCollectedInfo] = useState<Record<string, string>>({});
  const [isDispatching, setIsDispatching] = useState(false);
  const [routerPayload, setRouterPayload] = useState<RouterPayload | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [devices, setDevices] = useState<DeviceNode[]>([]);
  const [relayOnline, setRelayOnline] = useState(false);
  const [botEvents, setBotEvents] = useState<BotEvent[]>([]);
  const [entityMood, setEntityMood] = useState("curious");
  const [entityMoodEmoji, setEntityMoodEmoji] = useState("🔍");
  const [entityThought, setEntityThought] = useState("");
  const [profileSummary, setProfileSummary] = useState("");
  const [profileInterests, setProfileInterests] = useState<string[]>([]);
  const [voice, setVoice] = useState("en-GB-RyanNeural");
  const [cockpitTab, setCockpitTab] = useState<"router" | "telemetry">("router");
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [mobileCockpit, setMobileCockpit] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const retryCountRef = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((msg: string, type: ActivityEntry["type"] = "info") => {
    setActivityLog(prev => [...prev.slice(-30), { ts: Date.now(), msg, type }]);
  }, []);

  const addBotEvent = useCallback((type: string, label: string) => {
    setBotEvents(prev => [...prev.slice(-8), { type, label, timestamp: Date.now() }]);
  }, []);

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [sysRes, accRes, relayRes] = await Promise.allSettled([
          fetch(`${BASE}/api/system/stats`),
          fetch(`${BASE}/api/acc/devices`),
          fetch(`${BASE}/health`),
        ]);
        if (sysRes.status === "fulfilled" && sysRes.value.ok) {
          const d = await sysRes.value.json();
          setSystemStats({ cpu: d.cpu, memory: d.memory, battery: d.battery, uptime_h: d.uptime_h });
        }
        if (accRes.status === "fulfilled" && accRes.value.ok) {
          const d = await accRes.value.json();
          if (d.devices) setDevices(d.devices);
          setRelayOnline(true);
        }
        if (relayRes.status === "fulfilled" && relayRes.value.ok) setRelayOnline(true);
      } catch { setRelayOnline(false); }
    };
    fetchStats(); const i = setInterval(fetchStats, 10000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    const i = setInterval(async () => {
      try {
        const res = await fetch(`${BASE}/api/entity/state?user_id=local`);
        const d = await res.json();
        if (d.mood) setEntityMood(d.mood);
        if (d.mood_emoji) setEntityMoodEmoji(d.mood_emoji);
        if (d.current_thought) setEntityThought(d.current_thought);
      } catch {}
    }, 2000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    (async () => {
      addLog("JARVIS cognitive architecture initialising...", "info");
      fetch(`${BASE}/api/device/scan?user_id=local`, { method: "POST" }).catch(() => {});
      try {
        const res = await fetch(`${BASE}/api/profile?user_id=local`);
        const d = await res.json();
        setProfileSummary(d.summary || "");
        setProfileInterests(d.profile?.interests?.slice(0, 8).map((i: any) => i.topic) || []);
      } catch {}
      addLog("System boot complete. Multi-agent router ONLINE.", "success");
      setMessages([{ role: "assistant", content: "Systems online. Multi-agent cognitive architecture active — Supervisor Router, OS Agent, HAL Agent, and Web Agent standing by. Issue a command." }]);
    })();
  }, [addLog]);

  const speak = useCallback(async (text: string) => {
    setSpeaking(true); addBotEvent("action", "speaking response");
    try {
      const res = await fetch(`${BASE}/api/tts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice }),
      });
      if (!res.ok) throw new Error("TTS failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); setSpeaking(false); };
      audio.load(); await audio.play();
    } catch {
      const synth = synthRef.current; if (!synth) { setSpeaking(false); return; }
      synth.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05; utterance.pitch = 1.0;
      utterance.onend = () => setSpeaking(false);
      const voices = synth.getVoices();
      const preferred = voices.find(v => v.name.includes("Ryan") || v.name.includes("Aria"));
      if (preferred) utterance.voice = preferred;
      synth.speak(utterance);
    }
  }, [addBotEvent, voice]);

  const dispatchToRouter = useCallback(async (text: string) => {
    setIsDispatching(true);
    setRouterPayload(null);
    setActiveAgent(null);
    addLog(`Dispatching: "${text.slice(0, 60)}..."`, "action");
    addBotEvent("action", "routing intent");
    try {
      const res = await fetch(`${BASE}/api/router/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_text: text, user_id: "local", relay_context: {} }),
      });
      if (!res.ok) throw new Error(`Router error: ${res.status}`);
      const data: RouterPayload = await res.json();
      setRouterPayload(data);
      setActiveAgent(data.target_agent ?? null);
      addLog(`→ ${data.target_agent} | confidence ${Math.round((data.routing?.routing_confidence ?? 0) * 100)}% | ${data.latency_ms?.total}ms`, "success");
      setCockpitTab("router");
      return data;
    } catch (err: any) {
      addLog(`Router error: ${err.message}`, "error");
      return null;
    } finally {
      setIsDispatching(false);
    }
  }, [addBotEvent, addLog]);

  const sendText = useCallback(async () => {
    const text = textInput.trim(); if (!text) return;
    setTextInput(""); setShowSuggestions(false);
    setMessages(p => [...p, { role: "user", content: text }]);
    setThinking(true); addBotEvent("action", "processing");
    dispatchToRouter(text);
    if (taskSession && taskQuestion) {
      try {
        const res = await fetch(`${BASE}/api/task/respond`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: taskSession, response: text }),
        });
        const data = await res.json();
        if (data.type === "ask") {
          setTaskQuestion(data.question); setTaskStep(data.step || 0); setTaskTotal(data.total || 0);
          setMessages(p => [...p, { role: "assistant", content: data.question }]);
        } else if (data.type === "complete") {
          setTaskResult(data.text || data.collected ? JSON.stringify(data.collected, null, 2) : "Task complete.");
          setCollectedInfo(data.collected || {}); setTaskQuestion(null); setTaskSession(null);
          setMessages(p => [...p, { role: "assistant", content: "Task complete ✓" }]);
        } else {
          setMessages(p => [...p, { role: "assistant", content: data.text || data.message || "Done." }]);
          setTaskQuestion(null); setTaskSession(null);
        }
      } catch (e: any) {
        setMessages(p => [...p, { role: "assistant", content: `Error: ${e.message}` }]);
      }
      setThinking(false); return;
    }
    try {
      const data = await entityProcess(text, "local");
      const reply = data?.text || data?.message || "Acknowledged.";
      setMessages(p => [...p, { role: "assistant", content: reply }]);
      addLog("Response received", "success");
      if (data?.type === "ask" && data?.session_id) {
        setTaskSession(data.session_id); setTaskQuestion(data.question);
        setTaskStep(data.step || 0); setTaskTotal(data.total || 0);
      }
      if (data?.action_feedback) addBotEvent("action", data.action_feedback);
      if (reply.length < 300) speak(reply).catch(() => {});
    } catch (err: any) {
      const errMsg = `Connection error: ${err.message}`;
      setMessages(p => [...p, { role: "assistant", content: errMsg }]);
      addLog(errMsg, "error");
      retryCountRef.current += 1;
    }
    setThinking(false);
  }, [textInput, taskSession, taskQuestion, dispatchToRouter, speak, addBotEvent, addLog]);

  const handleOrbClick = useCallback(() => {
    if (listening) {
      recognitionRef.current?.stop(); setListening(false); return;
    }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { alert("Speech recognition not supported in this browser."); return; }
    const rec = new SR();
    rec.continuous = false; rec.interimResults = true; rec.lang = "en-GB";
    rec.onresult = (e: any) => {
      let interim_t = "", final_t = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          final_t += e.results[i][0].transcript;
          setConfidence(Math.round(e.results[i][0].confidence * 100));
        } else { interim_t += e.results[i][0].transcript; }
      }
      setInterim(interim_t || final_t);
      if (final_t) { setTextInput(final_t); setInterim(""); }
    };
    rec.onend = () => { setListening(false); };
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    rec.start(); setListening(true);
    addBotEvent("action", "listening");
  }, [listening, addBotEvent]);

  const agentState = thinking ? "thinking" : listening ? "listening" : speaking ? "speaking" : "idle";

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#030512]">
      <ParticleBg />
      <div className="cockpit-grid fixed inset-0 pointer-events-none z-0" />

      <div className="relative z-10 flex flex-col h-full">
        {/* Top nav */}
        <nav className="glass-strong flex items-center justify-between px-3 sm:px-6 py-3 border-b border-[#34d399]/10 flex-shrink-0 z-20">
          <Link href="/" className="flex items-center gap-2.5 shrink-0">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500/20 to-purple-500/20 border border-emerald-500/20 flex items-center justify-center shadow-[0_0_12px_rgba(52,211,153,0.15)]">
              <span className="text-sm">🌌</span>
            </div>
            <div className="hidden sm:block">
              <span className="text-xs font-mono font-bold text-[#34d399] tracking-[0.1em]">J.A.R.V.I.S</span>
              <span className="block text-[8px] font-mono text-white/20 tracking-[0.12em]">COGNITIVE ARCHITECTURE v3.0</span>
            </div>
          </Link>

          <div className="hidden lg:flex items-center gap-1">
            {NAV_ITEMS.map((n) => {
              const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[10px] font-mono tracking-wide transition-all nav-link ${
                    active
                      ? "text-[#34d399] bg-[#34d399]/[0.08] border border-[#34d399]/15"
                      : "text-white/30 hover:text-white/50 border border-transparent"
                  }`}
                >
                  <span>{n.icon}</span><span>{n.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            {entityThought && (
              <span className="hidden md:block text-[9px] font-mono text-white/20 max-w-[140px] truncate">{entityThought.slice(0, 50)}</span>
            )}
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full border border-white/[0.06] bg-white/[0.02]">
              <span className="text-[10px]">{entityMoodEmoji}</span>
              <span className="text-[9px] font-mono text-white/30 tracking-wide">{entityMood}</span>
            </div>

            <div className="lg:hidden dropdown relative">
              <button className="text-white/40 hover:text-white/60 p-1.5 rounded-md border border-white/[0.06] transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              </button>
              <div className="dropdown-menu hidden absolute right-0 top-full mt-1 w-48 glass-strong rounded-xl border border-purple-900/20 py-1 z-50 shadow-xl shadow-black/30">
                {NAV_ITEMS.map((n) => {
                  const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
                  return (
                    <Link key={n.href} href={n.href} className={`flex items-center gap-2 px-3 py-2 text-xs font-mono transition-colors ${active ? "text-[#34d399] bg-[#34d399]/[0.06]" : "text-white/40 hover:text-white/60 hover:bg-white/[0.03]"}`}>
                      <span>{n.icon}</span><span>{n.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>

            <Link href="/settings" className="text-white/30 hover:text-white/50 p-1.5 rounded-md border border-white/[0.06] hover:border-[#a78bfa]/20 transition-all hidden sm:flex items-center justify-center">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </Link>
          </div>
        </nav>

        <AgentStatusBar routingData={routerPayload} isDispatching={isDispatching} />

        {/* Mobile toggle */}
        <div className="lg:hidden flex border-b border-gray-800/30">
          <button onClick={() => setMobileCockpit(false)} className={`flex-1 py-2 text-[10px] font-mono tracking-wider transition-all ${!mobileCockpit ? "text-[#34d399] border-b-2 border-[#34d399]" : "text-gray-600"}`}>
            💬 Chat
          </button>
          <button onClick={() => setMobileCockpit(true)} className={`flex-1 py-2 text-[10px] font-mono tracking-wider transition-all ${mobileCockpit ? "text-[#34d399] border-b-2 border-[#34d399]" : "text-gray-600"}`}>
            📡 Cockpit
          </button>
        </div>

        {/* Main content */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Chat panel */}
          <div className={`${mobileCockpit ? "hidden lg:flex" : "flex"} flex-col w-full lg:w-[42%] lg:min-w-[320px] lg:max-w-[560px] lg:border-r border-gray-800/20 bg-[#050814]/55 backdrop-blur-2xl relative overflow-hidden z-15 shrink-0 transition-all duration-400`}>
            <button
              onClick={() => setChatCollapsed(!chatCollapsed)}
              className="hidden lg:flex absolute top-1/2 -right-3 -translate-y-1/2 z-30 w-5 h-10 rounded-r-lg bg-white/5 border border-l-0 border-white/[0.06] text-white/30 cursor-pointer items-center justify-center text-[10px] hover:bg-white/10 transition-all"
            >
              {chatCollapsed ? "›" : "‹"}
            </button>

            {!chatCollapsed ? (
              <>
                <div className="px-3 py-2.5 border-b border-white/[0.04] flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-white/30 tracking-[0.1em]">COMMAND INTERFACE</span>
                    <BotSwarm listening={agentState === "listening"} thinking={agentState === "thinking"} speaking={agentState === "speaking"} botEvents={botEvents} />
                  </div>
                </div>

                <div className="cockpit-scroll flex-1 overflow-auto p-3 flex flex-col gap-2">
                  {messages.map((msg, i) => (
                    <div key={i} className="animate-fade-in flex gap-2 items-end" style={{ flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>
                      {msg.role === "assistant" && (
                        <div className="w-[18px] h-[18px] rounded-full bg-[#34d399]/15 border border-[#34d399]/20 shrink-0 flex items-center justify-center text-[8px]">⚡</div>
                      )}
                      <div className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
                        msg.role === "user"
                          ? "bg-[#34d399]/[0.08] border border-[#34d399]/15 text-[#34d399]/90 font-mono rounded-br-sm"
                          : "bg-white/[0.03] border border-white/[0.05] text-white/80 rounded-bl-sm"
                      }`}>
                        {msg.content}
                        {msg.link && (
                          <a href={msg.link} target="_blank" rel="noopener noreferrer" className="block mt-1 text-[10px] text-[#a78bfa] no-underline">
                            → {msg.link.slice(0, 40)}...
                          </a>
                        )}
                      </div>
                    </div>
                  ))}

                  {thinking && (
                    <div className="flex gap-2 items-end animate-fade-in">
                      <div className="w-[18px] h-[18px] rounded-full bg-[#a78bfa]/15 border border-[#a78bfa]/20 shrink-0 flex items-center justify-center text-[8px]">⚡</div>
                      <div className="px-3 py-2 rounded-xl rounded-bl-sm bg-white/[0.03] border border-white/[0.05]">
                        <div className="flex gap-1 items-center">
                          {[0, 0.2, 0.4].map((d, i) => (
                            <div key={i} className="w-1 h-1 rounded-full bg-[#a78bfa] animate-pulse" style={{ animationDelay: `${d}s` }} />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {showSuggestions && messages.length <= 1 && (
                  <div className="px-3 py-2 flex-shrink-0">
                    <div className="flex flex-wrap gap-1">
                      {SUGGESTIONS.slice(0, 4).map(s => (
                        <button key={s} onClick={() => { setTextInput(s); setShowSuggestions(false); inputRef.current?.focus(); }}
                          className="suggestion-btn">
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {taskQuestion && (
                  <div className="px-3 py-2 flex-shrink-0">
                    <div className="px-3 py-2.5 rounded-lg bg-[#a78bfa]/[0.06] border border-[#a78bfa]/15">
                      <p className="text-[8px] font-mono text-[#a78bfa] mb-1 tracking-[0.1em]">STEP {taskStep}/{taskTotal} — NEEDS INPUT</p>
                      <p className="text-[11px] text-white/70">{taskQuestion}</p>
                    </div>
                  </div>
                )}

                {listening && interim && (
                  <div className="px-3 py-1 flex-shrink-0">
                    <p className="text-[11px] font-mono text-[#22d3ee]/70 animate-pulse">›{interim}</p>
                  </div>
                )}

                <div className="px-3 py-2.5 border-t border-white/[0.04] flex-shrink-0 flex items-center gap-2">
                  <div className="flex-1 flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.07] focus-within:border-[#a78bfa]/20 transition-colors">
                    <input
                      ref={inputRef}
                      type="text"
                      value={textInput}
                      onChange={e => setTextInput(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") sendText(); }}
                      placeholder="Issue a command..."
                      className="flex-1 bg-transparent border-none outline-none text-xs font-mono text-white/85 tracking-wide placeholder-white/20"
                    />
                    <button
                      onClick={handleOrbClick}
                      className={`p-1 rounded-md transition-all shrink-0 ${
                        listening ? "bg-green-500/15 text-[#4ade80] shadow-[0_0_8px_rgba(34,197,94,0.3)]" : "text-white/20 hover:text-white/40"
                      }`}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                      </svg>
                    </button>
                  </div>
                  <button
                    onClick={sendText}
                    disabled={!textInput.trim()}
                    className={`px-3.5 py-2 rounded-xl border text-[11px] font-mono tracking-[0.06em] transition-all shrink-0 ${
                      textInput.trim()
                        ? "border-[#34d399]/20 bg-[#34d399]/10 text-[#34d399] cursor-pointer shadow-[0_0_10px_rgba(52,211,153,0.1)]"
                        : "border-white/[0.06] bg-white/[0.02] text-white/15 cursor-default"
                    }`}
                  >
                    SEND
                  </button>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center pt-4 gap-3">
                <span className="writing-mode-vertical text-white/10 text-[9px] font-mono tracking-[0.12em]">CHAT</span>
              </div>
            )}
          </div>

          {/* Cockpit panel */}
          <div className={`${mobileCockpit ? "flex" : "hidden lg:flex"} flex-1 flex-col p-3 gap-2.5 overflow-hidden min-w-0`}>
            <div className="flex items-center justify-between flex-shrink-0">
              <div className="flex gap-1">
                {(["router", "telemetry"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setCockpitTab(tab)}
                    className={`px-3 py-1.5 text-[9px] font-mono tracking-[0.1em] uppercase rounded-md transition-all border ${
                      cockpitTab === tab
                        ? "border-[#34d399]/30 bg-[#34d399]/[0.08] text-[#34d399]"
                        : "border-white/[0.06] text-white/25 hover:text-white/40"
                    }`}
                  >
                    {tab === "router" ? "⚡ Router" : "📡 Telemetry"}
                  </button>
                ))}
              </div>
              {isDispatching && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] animate-pulse" />
                  <span className="text-[9px] font-mono text-[#f59e0b] tracking-[0.08em]">ROUTING...</span>
                </div>
              )}
            </div>

            {cockpitTab === "router" && (
              <div className="flex-1 min-h-0">
                <AgentRouter routingData={routerPayload as any} isDispatching={isDispatching} userText={messages.filter(m => m.role === "user").slice(-1)[0]?.content} />
              </div>
            )}

            {cockpitTab === "telemetry" && (
              <div className="flex-1 min-h-0 overflow-hidden">
                <CockpitTelemetry relayOnline={relayOnline} devices={devices} systemStats={systemStats} agentResponse={routerPayload?.agent_response ?? null} activeAgent={activeAgent} activityLog={activityLog} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Task result overlay */}
      {taskResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#030512]/80 backdrop-blur-lg" onClick={() => setTaskResult(null)}>
          <div onClick={e => e.stopPropagation()} className="max-w-[480px] w-[90%] p-6 glass-strong rounded-2xl border border-[#34d399]/20 shadow-[0_0_40px_rgba(52,211,153,0.1)] animate-fade-in">
            <p className="text-[9px] font-mono text-[#34d399] tracking-[0.15em] mb-2">✓ TASK COMPLETE</p>
            <p className="text-xs text-white/80 whitespace-pre-wrap leading-relaxed">{taskResult}</p>
            {Object.keys(collectedInfo).length > 0 && (
              <div className="mt-3 pt-3 border-t border-white/[0.06]">
                {Object.entries(collectedInfo).map(([k, v]) => (
                  <p key={k} className="text-[10px] font-mono text-white/40 mb-0.5">
                    <span className="text-[#a78bfa]">{k}:</span> {v}
                  </p>
                ))}
              </div>
            )}
            <button onClick={() => setTaskResult(null)} className="mt-4 text-[9px] font-mono text-white/20 tracking-[0.1em] bg-transparent border-none cursor-pointer hover:text-white/40 transition-colors">
              DISMISS ×
            </button>
          </div>
        </div>
      )}

      <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)} summary={profileSummary} interests={profileInterests} />
    </div>
  );
}
