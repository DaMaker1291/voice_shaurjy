"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import BotSwarm from "@/components/BotSwarm";
import Sidebar from "@/components/Sidebar";
import AgentStatusBar from "@/components/AgentStatusBar";
import AgentRouter from "@/components/AgentRouter";
import CockpitTelemetry from "@/components/CockpitTelemetry";
import Link from "next/link";
import { entityProcess } from "@/lib/api";

/* ─────────────────────────── Types ──────────────────────────── */
interface Message { role: string; content: string; image?: string; link?: string }
interface Strategy { name: string; description: string; pros: string[]; cons: string[]; complexity: number; key_steps: string[] }
interface EntityState { memory_summary: string; active_goals: { goal: string; priority: number; progress: number }[]; preferences: Record<string, { value: string }>; interaction_count: number }
interface BotEvent { type: string; label: string; timestamp: number }
interface SystemStats { cpu?: { percent: number; count: number }; memory?: { percent: number; used_gb: number; total_gb: number }; battery?: { percent: number; charging: boolean; present: boolean }; uptime_h?: number }
interface ActivityEntry { ts: number; msg: string; type: "info" | "action" | "error" | "success" }
interface RouterPayload { routing?: { target_agent?: string; routing_confidence?: number; extracted_intent?: string; execution_context?: Record<string, unknown> }; agent_response?: Record<string, unknown>; latency_ms?: { supervisor?: number; worker?: number; total?: number }; target_agent?: string }
interface DeviceNode { id: string; name: string; status: "ACTIVE" | "STANDBY" | "CHARGING" | "OFFLINE" | "UNKNOWN" | "OPTIMAL" | "WARNING" | "CRITICAL"; domain?: string; metrics?: string; controls?: string[] }

/* ─────────────────────────── Config ─────────────────────────── */
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
  { href: "/acc", label: "ACC", icon: "🎮" },
  { href: "/dashboard", label: "Brain", icon: "🧠" },
  { href: "/smarthome", label: "HAL", icon: "🏠" },
  { href: "/settings", label: "Config", icon: "⚙" },
];

/* ─────────────────────────── Particle BG ────────────────────── */
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
      // Draw connections
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

/* ─────────────────────────── Main ───────────────────────────── */
export default function Home() {
  // Chat state
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

  // Multi-agent state
  const [isDispatching, setIsDispatching] = useState(false);
  const [routerPayload, setRouterPayload] = useState<RouterPayload | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);

  // System state
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

  // Layout
  const [cockpitTab, setCockpitTab] = useState<"router" | "telemetry">("router");
  const [chatCollapsed, setChatCollapsed] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const taskInputRef = useRef<HTMLInputElement>(null);
  const retryCountRef = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  /* ── Helpers ───────────────────────────────────────────────── */
  const addLog = useCallback((msg: string, type: ActivityEntry["type"] = "info") => {
    setActivityLog(prev => [...prev.slice(-30), { ts: Date.now(), msg, type }]);
  }, []);

  const addBotEvent = useCallback((type: string, label: string) => {
    setBotEvents(prev => [...prev.slice(-8), { type, label, timestamp: Date.now() }]);
  }, []);

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  /* ── System stats polling ──────────────────────────────────── */
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

  /* ── Entity mood polling ───────────────────────────────────── */
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

  /* ── Initial boot ──────────────────────────────────────────── */
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

  /* ── TTS ───────────────────────────────────────────────────── */
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

  /* ── Multi-agent router dispatch ───────────────────────────── */
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
      addLog(
        `→ ${data.target_agent} | confidence ${Math.round((data.routing?.routing_confidence ?? 0) * 100)}% | ${data.latency_ms?.total}ms`,
        "success"
      );

      // Switch to router tab to show the result
      setCockpitTab("router");

      return data;
    } catch (err: any) {
      addLog(`Router error: ${err.message}`, "error");
      return null;
    } finally {
      setIsDispatching(false);
    }
  }, [addBotEvent, addLog]);

  /* ── Primary send handler ──────────────────────────────────── */
  const sendText = useCallback(async () => {
    const text = textInput.trim(); if (!text) return;
    setTextInput(""); setShowSuggestions(false);
    setMessages(p => [...p, { role: "user", content: text }]);
    setThinking(true); addBotEvent("action", "processing");

    // Fire router dispatch in parallel (non-blocking telemetry)
    dispatchToRouter(text);

    // Handle task session continuation
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

    // Standard entity processing
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

      // TTS for short replies
      if (reply.length < 300) speak(reply).catch(() => {});
    } catch (err: any) {
      const errMsg = `Connection error: ${err.message}`;
      setMessages(p => [...p, { role: "assistant", content: errMsg }]);
      addLog(errMsg, "error");
      retryCountRef.current += 1;
    }
    setThinking(false);
  }, [textInput, taskSession, taskQuestion, dispatchToRouter, speak, addBotEvent, addLog]);

  /* ── Voice ─────────────────────────────────────────────────── */
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

  /* ── Status ─────────────────────────────────────────────────── */
  const agentState = thinking ? "thinking" : listening ? "listening" : speaking ? "speaking" : "idle";

  /* ─────────────────────────── Render ─────────────────────────── */
  return (
    <div className="fixed inset-0 overflow-hidden" style={{ background: "#030512" }}>
      <ParticleBg />

      {/* Background grid */}
      <div className="cockpit-grid fixed inset-0 pointer-events-none z-0" />

      {/* Main Layout */}
      <div className="relative z-10 flex flex-col h-full">

        {/* ── Top nav bar ────────────────────────────────────────── */}
        <div
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "8px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)",
            background: "rgba(3,5,18,0.9)", backdropFilter: "blur(16px)",
            flexShrink: 0, zIndex: 20,
          }}
        >
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              onClick={() => setSidebarOpen(true)}
              style={{
                width: "28px", height: "28px", borderRadius: "8px",
                background: "linear-gradient(135deg, rgba(52,211,153,0.2), rgba(167,139,250,0.2))",
                border: "1px solid rgba(52,211,153,0.2)", display: "flex",
                alignItems: "center", justifyContent: "center", cursor: "pointer",
                boxShadow: "0 0 12px rgba(52,211,153,0.15)",
              }}
            >
              <span style={{ fontSize: "14px" }}>🌌</span>
            </div>
            <div>
              <span style={{ fontSize: "13px", fontFamily: "monospace", fontWeight: 700, color: "#34d399", letterSpacing: "0.1em" }}>
                J.A.R.V.I.S
              </span>
              <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.2)", display: "block", letterSpacing: "0.12em" }}>
                COGNITIVE ARCHITECTURE v3.0
              </span>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ display: "flex", gap: "4px" }}>
            {NAV_ITEMS.map(n => (
              <Link key={n.href} href={n.href}
                style={{
                  display: "flex", alignItems: "center", gap: "4px",
                  padding: "4px 10px", borderRadius: "6px", fontSize: "10px",
                  fontFamily: "monospace", color: n.href === "/" ? "#34d399" : "rgba(255,255,255,0.3)",
                  background: n.href === "/" ? "rgba(52,211,153,0.08)" : "transparent",
                  border: n.href === "/" ? "1px solid rgba(52,211,153,0.15)" : "1px solid transparent",
                  textDecoration: "none", letterSpacing: "0.05em",
                  transition: "all 0.2s",
                }}
              >
                <span>{n.icon}</span>{n.label}
              </Link>
            ))}
          </nav>

          {/* Entity mood chip */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {entityThought && (
              <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.2)", maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {entityThought.slice(0, 60)}
              </span>
            )}
            <div style={{
              display: "flex", alignItems: "center", gap: "5px",
              padding: "3px 8px", borderRadius: "20px",
              border: "1px solid rgba(255,255,255,0.08)",
              background: "rgba(255,255,255,0.02)",
            }}>
              <span style={{ fontSize: "10px" }}>{entityMoodEmoji}</span>
              <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)", letterSpacing: "0.06em" }}>{entityMood}</span>
            </div>
          </div>
        </div>

        {/* ── Agent Pipeline Status Bar ───────────────────────────── */}
        <AgentStatusBar routingData={routerPayload} isDispatching={isDispatching} />

        {/* ── Main content area ───────────────────────────────────── */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>

          {/* ── LEFT: Chat Panel ──────────────────────────────────── */}
          <div
            style={{
              width: chatCollapsed ? "48px" : "42%",
              minWidth: chatCollapsed ? "48px" : "320px",
              maxWidth: chatCollapsed ? "48px" : "560px",
              flexShrink: 0,
              display: "flex",
              flexDirection: "column",
              borderRight: "1px solid rgba(255,255,255,0.05)",
              background: "rgba(3,5,18,0.6)",
              backdropFilter: "blur(8px)",
              transition: "width 0.3s ease, min-width 0.3s ease",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {/* Collapse toggle */}
            <button
              onClick={() => setChatCollapsed(!chatCollapsed)}
              style={{
                position: "absolute", top: "50%", right: "-12px",
                transform: "translateY(-50%)", zIndex: 30,
                width: "20px", height: "40px", borderRadius: "0 8px 8px 0",
                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.06)",
                borderLeft: "none", color: "rgba(255,255,255,0.3)",
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "10px", transition: "all 0.2s",
              }}
            >
              {chatCollapsed ? "›" : "‹"}
            </button>

            {!chatCollapsed && (
              <>
                {/* Chat header */}
                <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)", flexShrink: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: "10px", fontFamily: "monospace", color: "rgba(255,255,255,0.3)", letterSpacing: "0.1em" }}>
                      COMMAND INTERFACE
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {/* Agent orb */}
                      <BotSwarm
                        listening={agentState === "listening"}
                        thinking={agentState === "thinking"}
                        speaking={agentState === "speaking"}
                        botEvents={botEvents}
                      />
                    </div>
                  </div>
                </div>

                {/* Messages */}
                <div
                  className="cockpit-scroll"
                  style={{ flex: 1, overflow: "auto", padding: "12px", display: "flex", flexDirection: "column", gap: "8px" }}
                >
                  {messages.map((msg, i) => (
                    <div
                      key={i}
                      style={{
                        animation: "fadeInUp 0.25s ease",
                        display: "flex",
                        flexDirection: msg.role === "user" ? "row-reverse" : "row",
                        gap: "8px", alignItems: "flex-end",
                      }}
                    >
                      {msg.role === "assistant" && (
                        <div style={{ width: "18px", height: "18px", borderRadius: "50%", background: "rgba(52,211,153,0.15)", border: "1px solid rgba(52,211,153,0.2)", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "8px" }}>
                          ⚡
                        </div>
                      )}
                      <div
                        style={{
                          maxWidth: "85%", padding: "8px 12px", borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                          background: msg.role === "user" ? "rgba(52,211,153,0.08)" : "rgba(255,255,255,0.03)",
                          border: msg.role === "user" ? "1px solid rgba(52,211,153,0.15)" : "1px solid rgba(255,255,255,0.05)",
                          fontSize: "12px", lineHeight: "1.6",
                          color: msg.role === "user" ? "rgba(52,211,153,0.9)" : "rgba(220,220,240,0.85)",
                          fontFamily: msg.role === "user" ? "monospace" : "inherit",
                        }}
                      >
                        {msg.content}
                        {msg.link && (
                          <a href={msg.link} target="_blank" rel="noopener noreferrer"
                            style={{ display: "block", marginTop: "4px", fontSize: "10px", color: "#a78bfa", textDecoration: "none" }}>
                            → {msg.link.slice(0, 40)}...
                          </a>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Thinking indicator */}
                  {thinking && (
                    <div style={{ display: "flex", gap: "8px", alignItems: "flex-end", animation: "fadeInUp 0.2s ease" }}>
                      <div style={{ width: "18px", height: "18px", borderRadius: "50%", background: "rgba(167,139,250,0.15)", border: "1px solid rgba(167,139,250,0.2)", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "8px" }}>⚡</div>
                      <div style={{ padding: "8px 12px", borderRadius: "12px 12px 12px 2px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
                        <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                          {[0, 0.2, 0.4].map((d, i) => (
                            <div key={i} style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#a78bfa", animation: `status-pulse 1.2s ease-in-out ${d}s infinite` }} />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Suggestions */}
                {showSuggestions && messages.length <= 1 && (
                  <div style={{ padding: "8px 12px", flexShrink: 0 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                      {SUGGESTIONS.slice(0, 4).map(s => (
                        <button key={s} onClick={() => { setTextInput(s); setShowSuggestions(false); inputRef.current?.focus(); }}
                          style={{
                            padding: "3px 8px", fontSize: "9px", fontFamily: "monospace",
                            borderRadius: "4px", border: "1px solid rgba(255,255,255,0.07)",
                            background: "rgba(255,255,255,0.02)", color: "rgba(255,255,255,0.35)",
                            cursor: "pointer", transition: "all 0.15s", letterSpacing: "0.04em",
                          }}
                          onMouseEnter={e => { (e.target as HTMLElement).style.borderColor = "rgba(52,211,153,0.2)"; (e.target as HTMLElement).style.color = "#34d399"; }}
                          onMouseLeave={e => { (e.target as HTMLElement).style.borderColor = "rgba(255,255,255,0.07)"; (e.target as HTMLElement).style.color = "rgba(255,255,255,0.35)"; }}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Task flow */}
                {taskQuestion && (
                  <div style={{ padding: "8px 12px", flexShrink: 0 }}>
                    <div style={{ padding: "10px 12px", borderRadius: "8px", background: "rgba(167,139,250,0.06)", border: "1px solid rgba(167,139,250,0.15)" }}>
                      <p style={{ fontSize: "8px", fontFamily: "monospace", color: "#a78bfa", marginBottom: "4px", letterSpacing: "0.1em" }}>
                        STEP {taskStep}/{taskTotal} — NEEDS INPUT
                      </p>
                      <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.7)", marginBottom: "0" }}>{taskQuestion}</p>
                    </div>
                  </div>
                )}

                {/* Interim voice text */}
                {listening && interim && (
                  <div style={{ padding: "4px 12px", flexShrink: 0 }}>
                    <p style={{ fontSize: "11px", fontFamily: "monospace", color: "rgba(34,211,238,0.7)", animation: "data-flicker 0.5s infinite" }}>
                      ›{interim}
                    </p>
                  </div>
                )}

                {/* Input bar */}
                <div
                  style={{
                    padding: "10px 12px", borderTop: "1px solid rgba(255,255,255,0.04)", flexShrink: 0,
                    display: "flex", alignItems: "center", gap: "8px",
                  }}
                >
                  <div
                    style={{
                      flex: 1, display: "flex", alignItems: "center", gap: "6px",
                      padding: "8px 12px", borderRadius: "10px",
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.07)",
                      transition: "border-color 0.2s",
                    }}
                    onFocus={() => {}}
                  >
                    <input
                      ref={inputRef}
                      type="text"
                      value={textInput}
                      onChange={e => setTextInput(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") sendText(); }}
                      placeholder="Issue a command..."
                      style={{
                        background: "transparent", border: "none", outline: "none",
                        flex: 1, fontSize: "12px", fontFamily: "monospace",
                        color: "rgba(220,220,240,0.85)",
                        letterSpacing: "0.02em",
                      }}
                    />
                    {/* Voice btn */}
                    <button
                      onClick={handleOrbClick}
                      style={{
                        padding: "4px", borderRadius: "6px", border: "none",
                        background: listening ? "rgba(34,197,94,0.15)" : "transparent",
                        color: listening ? "#4ade80" : "rgba(255,255,255,0.2)",
                        cursor: "pointer", flexShrink: 0, transition: "all 0.2s",
                        boxShadow: listening ? "0 0 8px rgba(34,197,94,0.3)" : "none",
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                      </svg>
                    </button>
                  </div>

                  {/* Send */}
                  <button
                    onClick={sendText}
                    disabled={!textInput.trim()}
                    style={{
                      padding: "8px 14px", borderRadius: "10px", border: "1px solid rgba(52,211,153,0.2)",
                      background: textInput.trim() ? "rgba(52,211,153,0.1)" : "rgba(255,255,255,0.02)",
                      color: textInput.trim() ? "#34d399" : "rgba(255,255,255,0.15)",
                      fontSize: "11px", fontFamily: "monospace", cursor: textInput.trim() ? "pointer" : "default",
                      transition: "all 0.2s", letterSpacing: "0.06em",
                      boxShadow: textInput.trim() ? "0 0 10px rgba(52,211,153,0.1)" : "none",
                      flexShrink: 0,
                    }}
                  >
                    SEND
                  </button>
                </div>
              </>
            )}

            {chatCollapsed && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: "16px", gap: "12px" }}>
                <span style={{ writingMode: "vertical-rl", color: "rgba(255,255,255,0.1)", fontSize: "9px", fontFamily: "monospace", letterSpacing: "0.12em" }}>CHAT</span>
              </div>
            )}
          </div>

          {/* ── RIGHT: Cockpit Panel ────────────────────────────────── */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              padding: "12px",
              gap: "10px",
              overflow: "hidden",
              minWidth: 0,
            }}
          >
            {/* Cockpit tab switcher */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div style={{ display: "flex", gap: "4px" }}>
                {(["router", "telemetry"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setCockpitTab(tab)}
                    style={{
                      padding: "5px 14px", fontSize: "9px", fontFamily: "monospace",
                      borderRadius: "6px", letterSpacing: "0.1em", textTransform: "uppercase",
                      border: "1px solid",
                      borderColor: cockpitTab === tab ? "rgba(52,211,153,0.3)" : "rgba(255,255,255,0.06)",
                      background: cockpitTab === tab ? "rgba(52,211,153,0.08)" : "transparent",
                      color: cockpitTab === tab ? "#34d399" : "rgba(255,255,255,0.25)",
                      cursor: "pointer", transition: "all 0.2s",
                    }}
                  >
                    {tab === "router" ? "⚡ Router" : "📡 Telemetry"}
                  </button>
                ))}
              </div>

              {/* Live dispatch indicator */}
              {isDispatching && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#f59e0b", animation: "status-pulse 0.6s ease-in-out infinite" }} />
                  <span style={{ fontSize: "9px", fontFamily: "monospace", color: "#f59e0b", letterSpacing: "0.08em" }}>
                    ROUTING...
                  </span>
                </div>
              )}
            </div>

            {/* ── Router tab ── */}
            {cockpitTab === "router" && (
              <div style={{ flex: 1, minHeight: 0 }}>
                <AgentRouter
                  routingData={routerPayload as any}
                  isDispatching={isDispatching}
                  userText={messages.filter(m => m.role === "user").slice(-1)[0]?.content}
                />
              </div>
            )}


            {/* ── Telemetry tab ── */}
            {cockpitTab === "telemetry" && (
              <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
                <CockpitTelemetry
                  relayOnline={relayOnline}
                  devices={devices}
                  systemStats={systemStats}
                  agentResponse={routerPayload?.agent_response ?? null}
                  activeAgent={activeAgent}
                  activityLog={activityLog}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Task result overlay */}
      {taskResult && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center",
            background: "rgba(3,5,18,0.8)", backdropFilter: "blur(8px)",
          }}
          onClick={() => setTaskResult(null)}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              maxWidth: "480px", width: "90%", padding: "24px",
              background: "rgba(10,15,30,0.95)", borderRadius: "16px",
              border: "1px solid rgba(52,211,153,0.2)",
              boxShadow: "0 0 40px rgba(52,211,153,0.1)",
              animation: "fadeInUp 0.3s ease",
            }}
          >
            <p style={{ fontSize: "9px", fontFamily: "monospace", color: "#34d399", letterSpacing: "0.15em", marginBottom: "8px" }}>
              ✓ TASK COMPLETE
            </p>
            <p style={{ fontSize: "12px", color: "rgba(220,220,240,0.8)", whiteSpace: "pre-wrap", lineHeight: "1.6" }}>{taskResult}</p>
            {Object.keys(collectedInfo).length > 0 && (
              <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                {Object.entries(collectedInfo).map(([k, v]) => (
                  <p key={k} style={{ fontSize: "10px", fontFamily: "monospace", color: "rgba(255,255,255,0.4)", marginBottom: "2px" }}>
                    <span style={{ color: "#a78bfa" }}>{k}:</span> {v}
                  </p>
                ))}
              </div>
            )}
            <button
              onClick={() => setTaskResult(null)}
              style={{ marginTop: "16px", fontSize: "9px", fontFamily: "monospace", color: "rgba(255,255,255,0.2)", letterSpacing: "0.1em", background: "none", border: "none", cursor: "pointer" }}
            >
              DISMISS ×
            </button>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)}
        summary={profileSummary} interests={profileInterests} />
    </div>
  );
}
