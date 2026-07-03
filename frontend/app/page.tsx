"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import BotSwarm from "@/components/BotSwarm";
import Sidebar from "@/components/Sidebar";
import Link from "next/link";
import { entityProcess } from "@/lib/api";

interface Message { role: string; content: string; image?: string; link?: string }

interface Strategy {
  name: string; description: string; pros: string[]; cons: string[];
  complexity: number; key_steps: string[];
}

interface EntityState {
  memory_summary: string;
  active_goals: { goal: string; priority: number; progress: number }[];
  preferences: Record<string, { value: string }>;
  interaction_count: number;
}

interface BotEvent { type: string; label: string; timestamp: number }

interface SystemStats {
  cpu?: { percent: number; count: number };
  memory?: { percent: number; used_gb: number; total_gb: number };
  battery?: { percent: number; charging: boolean; present: boolean };
  uptime_h?: number;
}

const BASE = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

const SUGGESTIONS = [
  "play some music", "what's the time", "scan my network",
  "volume to 50", "lock my PC", "take a screenshot",
  "open Spotify", "battery status",
];

const NAV_ITEMS = [
  { href: "/", label: "Chat", icon: "💬" },
  { href: "/acc", label: "ACC", icon: "🎮" },
  { href: "/dashboard", label: "Brain", icon: "🧠" },
  { href: "/smarthome", label: "Home", icon: "🏠" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

function SystemStatsWidget({ stats }: { stats: SystemStats | null }) {
  if (!stats) return null;
  return (
    <div className="flex items-center gap-4 text-[9px] font-mono">
      {stats.cpu && (
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-900/50 border border-gray-800/30">
          <span className="text-gray-600">CPU</span>
          <span className={stats.cpu.percent > 80 ? "text-red-400" : stats.cpu.percent > 50 ? "text-yellow-400" : "text-green-400"}>
            {stats.cpu.percent}%
          </span>
        </div>
      )}
      {stats.memory && (
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-900/50 border border-gray-800/30">
          <span className="text-gray-600">RAM</span>
          <span className={stats.memory.percent > 80 ? "text-red-400" : stats.memory.percent > 50 ? "text-yellow-400" : "text-green-400"}>
            {stats.memory.used_gb.toFixed(1)}/{stats.memory.total_gb.toFixed(0)}GB
          </span>
        </div>
      )}
      {stats.battery?.present && (
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-900/50 border border-gray-800/30">
          <span className="text-gray-600">BAT</span>
          <span className={stats.battery.percent < 20 ? "text-red-400" : stats.battery.charging ? "text-green-400" : "text-yellow-400"}>
            {stats.battery.percent}%{stats.battery.charging ? " ⚡" : ""}
          </span>
        </div>
      )}
    </div>
  );
}

function ParticleBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    c.width = window.innerWidth; c.height = window.innerHeight;
    const particles: { x: number; y: number; vx: number; vy: number; r: number }[] = [];
    for (let i = 0; i < 50; i++) {
      particles.push({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4, r: Math.random() * 1.5 + 0.5 });
    }
    const connections: { a: number; b: number }[] = [];
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        if (Math.random() < 0.08) connections.push({ a: i, b: j });
      }
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
        ctx.fillStyle = "rgba(120, 60, 220, 0.25)";
        ctx.fill();
      });
      connections.forEach(cn => {
        const a = particles[cn.a], b = particles[cn.b];
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = "rgba(120, 60, 220, 0.06)";
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });
      anim = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(anim);
  }, []);
  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [actionType, setActionType] = useState<string>("action");
  const [taskSession, setTaskSession] = useState<string | null>(null);
  const [taskQuestion, setTaskQuestion] = useState<string | null>(null);
  const [taskStep, setTaskStep] = useState(0);
  const [taskTotal, setTaskTotal] = useState(0);
  const [taskResult, setTaskResult] = useState<string | null>(null);
  const [collectedInfo, setCollectedInfo] = useState<Record<string, string>>({});
  const [scanning, setScanning] = useState(false);
  const [profileSummary, setProfileSummary] = useState("");
  const [profileInterests, setProfileInterests] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [botEvents, setBotEvents] = useState<BotEvent[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const taskInputRef = useRef<HTMLInputElement>(null);
  const retryCountRef = useRef(0);
  const [strategies, setStrategies] = useState<Strategy[] | null>(null);
  const [followUpQuestions, setFollowUpQuestions] = useState<string[]>([]);
  const [proactiveSuggestions, setProactiveSuggestions] = useState<string[]>([]);
  const [entityState, setEntityState] = useState<EntityState | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null);
  const [entityMemory, setEntityMemory] = useState("");
  const [activityIntensity, setActivityIntensity] = useState(0);
  const [voice, setVoice] = useState<string>("en-GB-RyanNeural");
  const [entityMood, setEntityMood] = useState("curious");
  const [entityMoodEmoji, setEntityMoodEmoji] = useState("🔍");
  const [entityThought, setEntityThought] = useState("");
  const [centerOverlay, setCenterOverlay] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<string>("");
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [accDeviceCount, setAccDeviceCount] = useState(0);
  const [accOnlineCount, setAccOnlineCount] = useState(0);
  const overlayTimerRef = useRef<NodeJS.Timeout | null>(null);

  const showCenterOverlay = useCallback((content: string) => {
    setCenterOverlay(content);
    if (overlayTimerRef.current) clearTimeout(overlayTimerRef.current);
    overlayTimerRef.current = setTimeout(() => setCenterOverlay(null), 10000);
  }, []);

  const dismissOverlay = useCallback(() => {
    setCenterOverlay(null);
    if (overlayTimerRef.current) { clearTimeout(overlayTimerRef.current); overlayTimerRef.current = null; }
  }, []);

  const addBotEvent = useCallback((type: string, label: string) => {
    setBotEvents(prev => [...prev.slice(-8), { type, label, timestamp: Date.now() }]);
  }, []);

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);

  // Poll system stats
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [sysRes, accRes] = await Promise.allSettled([
          fetch(`${BASE}/api/system/stats`),
          fetch(`${BASE}/api/acc/devices`),
        ]);
        if (sysRes.status === "fulfilled") {
          const data = await sysRes.value.json();
          setSystemStats({ cpu: data.cpu, memory: data.memory, battery: data.battery, uptime_h: data.uptime_h });
        }
        if (accRes.status === "fulfilled") {
          const data = await accRes.value.json();
          setAccDeviceCount(data.total || 0);
          setAccOnlineCount(data.online || 0);
        }
      } catch {}
    };
    fetchStats();
    const i = setInterval(fetchStats, 10000);
    return () => clearInterval(i);
  }, []);

  // Poll entity state
  useEffect(() => {
    const i = setInterval(async () => {
      try {
        const res = await fetch(`${BASE}/api/entity/state?user_id=local`);
        const data = await res.json();
        if (data.mood) setEntityMood(data.mood);
        if (data.mood_emoji) setEntityMoodEmoji(data.mood_emoji);
        if (data.current_thought) setEntityThought(data.current_thought);
      } catch {}
    }, 2000);
    return () => clearInterval(i);
  }, []);

  // Initial scan
  useEffect(() => {
    (async () => {
      setScanning(true);
      addBotEvent("action", "scanning device");
      fetch(`${BASE}/api/device/scan?user_id=local`, { method: "POST" }).catch(() => {});
      try {
        const res = await fetch(`${BASE}/api/profile?user_id=local`);
        const data = await res.json();
        setProfileSummary(data.summary || "");
        setProfileInterests(data.profile?.interests?.slice(0, 8).map((i: any) => i.topic) || []);
      } catch {}
      setScanning(false);
      addBotEvent("action", "scan complete");
      setMessages((p) => [...p, {
        role: "assistant",
        content: "Welcome back. I'm ready — ask me anything, or tap the orb to speak."
      }]);
      setTimeout(async () => {
        try {
          const res = await fetch(`${BASE}/api/profile?user_id=local`);
          const data = await res.json();
          if (data?.profile?.device?.installed_apps?.length > 0 || data?.profile?.interests?.length > 0) {
            setProfileSummary(data.summary || "");
            setProfileInterests(data.profile?.interests?.slice(0, 8).map((i: any) => i.topic) || []);
          }
        } catch {}
      }, 5000);
    })();
    const interval = setInterval(async () => {
      try {
        await fetch(`${BASE}/api/device/scan?user_id=local`, { method: "POST" });
        const res = await fetch(`${BASE}/api/profile?user_id=local`);
        const data = await res.json();
        setProfileSummary(data.summary || "");
        setProfileInterests(data.profile?.interests?.slice(0, 8).map((i: any) => i.topic) || []);
      } catch {}
    }, 600000);
    return () => clearInterval(interval);
  }, [addBotEvent]);

  const speak = useCallback(async (text: string) => {
    setSpeaking(true);
    addBotEvent("action", "speaking response");
    const voiceName = voice || "en-US-AriaNeural";
    try {
      const res = await fetch(`${BASE}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: voiceName }),
      });
      if (!res.ok) throw new Error("TTS failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); setSpeaking(false); };
      audio.load();
      await audio.play();
    } catch {
      const synth = synthRef.current;
      if (!synth) { setSpeaking(false); return; }
      synth.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05; utterance.pitch = 1.0;
      utterance.onend = () => setSpeaking(false);
      const voices = synth.getVoices();
      const preferred = voices.find((v) => v.name.includes(voiceName.split("-")[1] || "Ryan") || v.name.includes("Ryan") || v.name.includes("Aria") || v.name.includes("Jenny"));
      if (preferred) utterance.voice = preferred;
      synth.speak(utterance);
    }
  }, [addBotEvent, voice]);

  const sendTaskResponse = useCallback(async (response: string) => {
    if (!taskSession || !response.trim()) return;
    setMessages((p) => [...p, { role: "user", content: response }]);
    setTaskQuestion(null);
    setThinking(true);
    addBotEvent("workflow", "processing task response");
    try {
      const res = await fetch(`${BASE}/api/task/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: taskSession, response }),
      });
      const data = await res.json();
      _handleTaskResponse(data);
    } catch {
      addBotEvent("error", "task failed");
      setMessages((p) => [...p, { role: "assistant", content: "Task failed." }]);
      setTaskSession(null);
    }
    setThinking(false);
  }, [taskSession, addBotEvent]);

  const pollRelayResult = useCallback(async (relayId: string) => {
    let attempts = 0;
    const maxAttempts = 60;
    const poll = async () => {
      if (attempts >= maxAttempts) return;
      attempts++;
      try {
        const { relayStatus } = await import("@/lib/api");
        const res = await relayStatus(relayId);
        if (res.status === "done" || res.status === "failed") {
          const resultText = res.result || (res.status === "done" ? "✅ Done" : "❌ Failed");
          setMessages((p) => {
            const updated = [...p];
            const last = updated[updated.length - 1];
            if (last && last.role === "assistant") last.content = resultText;
            return updated;
          });
          setLastResponse(resultText);
          setActionFeedback(resultText);
          if (resultText && resultText.length > 20) showCenterOverlay(resultText);
          setTimeout(() => setActionFeedback(null), 5000);
          return;
        }
        setTimeout(poll, 1000);
      } catch { setTimeout(poll, 2000); }
    };
    poll();
  }, [showCenterOverlay]);

  const handleQuery = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setMessages((p) => [...p, { role: "user", content: text }]);
    setSidebarOpen(true);
    setThinking(true);
    setSpeaking(false);
    setShowSuggestions(false);
    setLastResponse("");
    setStrategies(null);
    setFollowUpQuestions([]);
    setProactiveSuggestions([]);
    setSelectedStrategy(null);
    setActivityIntensity(1);
    addBotEvent("thinking", "processing query");

    try {
      const res = await entityProcess(text);
      const reply = res.text || "";

      if (res.strategies?.strategies) {
        addBotEvent("planning", `generated ${res.strategies.strategies.length} strategies`);
        setStrategies(res.strategies.strategies);
        setFollowUpQuestions(res.strategies.follow_up_questions || []);
        setMessages((p) => [...p, {
          role: "assistant",
          content: `I've thought of a few approaches for that. Here are your options:\n\n${res.strategies.strategies.map((s: Strategy, i: number) => `${i+1}. **${s.name}** - ${s.description}`).join("\n")}\n\nWhich approach sounds best?`
        }]);
      }

      if (res.follow_up?.length > 0) setFollowUpQuestions(res.follow_up);
      if (res.proactive?.length > 0) setProactiveSuggestions(res.proactive);

      if (res.action) {
        addBotEvent("action", reply.slice(0, 60));
        setActionFeedback(reply);
        setActionType(res.action_type || "action");

        if (res.action === "__needs_relay__") {
          setMessages((p) => [...p, { role: "assistant", content: reply }]);
          setLastResponse(reply);
          setTimeout(() => setActionFeedback(null), 8000);
          speak(reply);
          return;
        }

        if (res.qr_image) {
          setMessages((p) => [...p, { role: "assistant", content: reply, image: `data:image/png;base64,${res.qr_image}`, link: res.wa_link || "https://wa.me/" }]);
          setLastResponse(reply);
          speak("Scan this QR code with your phone to link WhatsApp Web");
          setTimeout(() => setActionFeedback(null), 4000);
          return;
        }

        if (res.wa_link) {
          setMessages((p) => [...p, { role: "assistant", content: reply, link: res.wa_link }]);
          setLastResponse(reply);
          setTimeout(() => setActionFeedback(null), 4000);
          setTimeout(() => { window.location.href = res.wa_link; }, 300);
          return;
        }

        if (res.link) {
          setMessages((p) => [...p, { role: "assistant", content: reply, link: res.link }]);
          setLastResponse(reply);
          setTimeout(() => setActionFeedback(null), 4000);
          setTimeout(() => { window.location.href = res.link; }, 300);
          return;
        }

        if (res.image) {
          setMessages((p) => [...p, { role: "assistant", content: reply, image: `data:image/png;base64,${res.image}` }]);
          setLastResponse(reply);
          setTimeout(() => setActionFeedback(null), 4000);
          return;
        }

        const lines = reply.split("\n");
        const mainPart = lines.slice(1).join("\n").trim();
        if (mainPart && mainPart.length > 20) showCenterOverlay(mainPart);

        if (res.async && res.relay_id) {
          setMessages((p) => [...p, { role: "assistant", content: reply }]);
          setLastResponse(reply);
          pollRelayResult(res.relay_id);
        } else {
          setMessages((p) => [...p, { role: "assistant", content: reply }]);
          setLastResponse(reply);
          setTimeout(() => setActionFeedback(null), 4000);
        }
      } else if (res.task) {
        addBotEvent("workflow", "task started");
        _handleTaskResponse(res.task);
      } else if (reply) {
        addBotEvent("action", "responding");
        speak(reply);
        setLastResponse(reply);
        setMessages((p) => [...p, { role: "assistant", content: reply }]);
      }

      if (res.entity_state) {
        setEntityState(res.entity_state);
        setEntityMemory(res.entity_state.memory_summary || "");
      }
      if (res.mood) setEntityMood(res.mood);
      if (res.mood_emoji) setEntityMoodEmoji(res.mood_emoji);
      if (res.thought) setEntityThought(res.thought);
    } catch (e) {
      addBotEvent("error", "backend unreachable");
      setLastResponse("(backend unreachable)");
      setMessages((p) => [...p, { role: "assistant", content: "(backend unreachable)" }]);
    }
    setThinking(false);
    setTimeout(() => setActivityIntensity(0.3), 2000);
  }, [speak, addBotEvent]);

  const pickStrategy = useCallback(async (index: number) => {
    setSelectedStrategy(index);
    if (!strategies || !strategies[index]) return;
    const strat = strategies[index];
    addBotEvent("planning", `selected strategy: ${strat.name}`);
    setMessages((p) => [...p, { role: "assistant", content: `👍 Let's go with **${strat.name}**. I'll start working on it.\n\nSteps:\n${strat.key_steps.map((s, i) => `${i+1}. ${s}`).join("\n")}` }]);
    setStrategies(null);
    const res = await entityProcess(`Execute strategy: ${strat.name}. ${strat.key_steps.join(", ")}`);
    if (res.text) {
      setLastResponse(res.text);
      setMessages((p) => [...p, { role: "assistant", content: res.text }]);
    }
  }, [strategies, addBotEvent]);

  const handleFollowUp = useCallback(async (q: string) => {
    setMessages((p) => [...p, { role: "user", content: q }]);
    if (messages.length === 0) setSidebarOpen(true);
    setThinking(true);
    setShowSuggestions(false);
    setStrategies(null);
    setFollowUpQuestions([]);
    setProactiveSuggestions([]);
    addBotEvent("thinking", "following up");
    try {
      const res = await entityProcess(`(follow-up) ${q}`);
      const reply = res.text || "";
      if (res.entity_state) { setEntityState(res.entity_state); setEntityMemory(res.entity_state.memory_summary || ""); }
      if (reply) { speak(reply); setLastResponse(reply); setMessages((p) => [...p, { role: "assistant", content: reply }]); }
    } catch { setMessages((p) => [...p, { role: "assistant", content: "(follow-up failed)" }]); }
    setThinking(false);
  }, [speak, addBotEvent]);

  const handleProactive = useCallback(async (s: string) => {
    setMessages((p) => [...p, { role: "user", content: s }]);
    setThinking(true);
    addBotEvent("thinking", "proactive action");
    try {
      const res = await entityProcess(`(proactive) ${s}`);
      const reply = res.text || "";
      if (res.entity_state) { setEntityState(res.entity_state); setEntityMemory(res.entity_state.memory_summary || ""); }
      if (reply) { setLastResponse(reply); setMessages((p) => [...p, { role: "assistant", content: reply }]); }
    } catch { setMessages((p) => [...p, { role: "assistant", content: "(action failed)" }]); }
    setThinking(false);
  }, [addBotEvent]);

  const _handleTaskResponse = useCallback((data: any) => {
    if (data.type === "ask") {
      setTaskSession(data.session_id || taskSession);
      setTaskQuestion(data.question);
      setTaskStep(data.step || 0);
      setTaskTotal(data.total || 0);
      setTaskResult(null);
      addBotEvent("workflow", `asking: ${(data.question || "").slice(0, 40)}`);
      setMessages((p) => [...p, { role: "assistant", content: `❓ ${data.question}` }]);
      speak(data.question);
      setTimeout(() => taskInputRef.current?.focus(), 200);
    } else if (data.type === "notify") {
      addBotEvent("action", data.text);
      setActionFeedback(data.text);
      setActionType("workflow");
      setTaskStep(data.step || 0);
      setTaskTotal(data.total || 0);
      setTimeout(() => setActionFeedback(null), 3000);
    } else if (data.type === "complete") {
      addBotEvent("action", "task complete");
      setTaskSession(null);
      setTaskQuestion(null);
      setTaskResult(data.text);
      setCollectedInfo(data.collected || {});
      const msgLink = data.link || data.wa_link || "";
      setMessages((p) => [...p, { role: "assistant", content: `✅ ${data.text}`, link: msgLink }]);
      if (msgLink) setTimeout(() => { window.location.href = msgLink; }, 500);
      speak("Task complete!");
    } else if (data.type === "workflow") {
      addBotEvent("workflow", data.text);
      setMessages((p) => [...p, { role: "assistant", content: `🔄 ${data.text}` }]);
    } else if (data?.workflow_result?.results) {
      for (const r of data.workflow_result.results) {
        if (r.type === "ask") _handleTaskResponse({ type: "ask", question: r.question, session_id: data.execution_id });
        else if (r.type === "notify") { setActionFeedback(r.text); setTimeout(() => setActionFeedback(null), 2000); }
        else if (r.type === "complete") { addBotEvent("action", "workflow complete"); setMessages((p) => [...p, { role: "assistant", content: `✅ ${r.text}` }]); }
      }
    } else if (data.type === "error") {
      addBotEvent("error", data.text);
      setMessages((p) => [...p, { role: "assistant", content: `⚠️ ${data.text}` }]);
      setTaskSession(null);
      setTaskQuestion(null);
    }
  }, [taskSession, speak, addBotEvent]);

  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setTimeout(() => inputRef.current?.focus(), 100); return; }
    const r = new SR();
    r.lang = "en-US";
    r.interimResults = true;
    r.continuous = true;
    r.maxAlternatives = 3;
    let final = "";

    r.onresult = (e: any) => {
      let bestConfidence = 0;
      let bestInterim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) { final += (final ? " " : "") + transcript; bestConfidence = Math.max(bestConfidence, result[0].confidence); }
        else { bestInterim += (bestInterim ? " " : "") + transcript; bestConfidence = Math.max(bestConfidence, result[0].confidence); }
      }
      const displayText = bestInterim || final;
      setInterim(displayText);
      (r as any)._capturedText = displayText;
      setConfidence(Math.round(bestConfidence * 100));
      if (final) {
        clearTimeout((r as any)._silenceTimer);
        (r as any)._silenceTimer = setTimeout(() => {
          r.stop();
          const t = final.trim();
          if (!t) return;
          setListening(false);
          setInterim("");
          retryCountRef.current = 0;
          setShowSuggestions(false);
          if (taskQuestion) sendTaskResponse(t);
          else handleQuery(t);
        }, 1500);
      }
    };

    r.onerror = (e: any) => {
      if (e.error === "not-allowed") { setInterim("Mic blocked"); setListening(false); return; }
      if (e.error === "no-speech" && retryCountRef.current < 2) { retryCountRef.current++; r.start(); return; }
      setListening(false); setInterim("");
    };
    r.onend = () => { setListening(false); if (!final) setInterim(""); };
    retryCountRef.current = 0;
    recognitionRef.current = r;
    r.start();
    setListening(true);
    addBotEvent("listening", "listening...");
    setInterim("");
    setConfidence(0);
  }, [taskQuestion, handleQuery, sendTaskResponse, addBotEvent]);

  const stopListening = useCallback(() => {
    clearTimeout((recognitionRef.current as any)?._silenceTimer);
    recognitionRef.current?.stop();
    setListening(false);
    const t = ((recognitionRef.current as any)?._capturedText || "").trim();
    setInterim("");
    if (t) {
      setShowSuggestions(false);
      if (taskQuestion) sendTaskResponse(t);
      else handleQuery(t);
    }
  }, [taskQuestion, handleQuery, sendTaskResponse]);

  const sendText = useCallback(() => {
    const txt = textInput.trim();
    if (!txt) return;
    setTextInput("");
    setShowSuggestions(false);
    if (taskQuestion) { sendTaskResponse(txt); }
    else { handleQuery(txt); }
  }, [textInput, taskQuestion, handleQuery, sendTaskResponse]);

  const handleOrbClick = useCallback(() => {
    if (listening) stopListening();
    else startListening();
  }, [listening, startListening, stopListening]);

  const pickSuggestion = useCallback((s: string) => {
    setShowSuggestions(false);
    handleQuery(s);
  }, [handleQuery]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape" && listening) { stopListening(); }
      if (e.key === "Enter" && taskQuestion) { sendTaskResponse(textInput); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [listening, stopListening, taskQuestion, textInput, sendTaskResponse]);

  const orbState = listening ? "listening" : thinking ? "thinking" : speaking ? "speaking" : "idle";

  return (
    <div className="relative h-screen w-full overflow-hidden flex flex-col" style={{ backgroundColor: '#05081a' }}>
      <div className="gradient-bg" />
      <div className="grid-overlay" />
      <div className="stars" />
      <div className="stars2" />
      <div className="stars3" />
      <div className="aurora" />
      <ParticleBg />

      {/* ── Top Navigation Bar ─────────────────────────────────── */}
      <header className="relative z-30 flex items-center justify-between px-4 md:px-6 py-2.5 border-b border-purple-900/20 bg-[#05081a]/70 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className={`w-2.5 h-2.5 rounded-full transition-all duration-500 shadow-lg ${
              listening ? "bg-green-400 shadow-green-500/50" :
              thinking ? "bg-purple-400 shadow-purple-500/50" :
              speaking ? "bg-cyan-400 shadow-cyan-500/50" :
              "bg-gray-600"
            }`} />
            <span className="text-sm font-bold bg-gradient-to-r from-purple-300 via-cyan-300 to-purple-300 bg-clip-text text-transparent">
              J.A.R.V.I.S.
            </span>
            <span className="text-[9px] font-mono text-gray-600 tracking-[0.2em] hidden sm:inline">
              {orbState === "listening" ? "LISTENING" : orbState === "thinking" ? "PROCESSING" : orbState === "speaking" ? "SPEAKING" : entityMood.toUpperCase()}
            </span>
          </div>
          <SystemStatsWidget stats={systemStats} />
        </div>
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map(item => (
            <Link key={item.href} href={item.href}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-mono text-gray-500 hover:text-purple-400 hover:bg-purple-900/10 rounded-lg transition-all duration-200">
              <span>{item.icon}</span>
              <span className="hidden md:inline">{item.label}</span>
            </Link>
          ))}
          <button onClick={() => setSidebarOpen(o => !o)}
            className="ml-1 p-1.5 text-gray-600 hover:text-purple-400 hover:bg-purple-900/10 rounded-lg transition-all duration-200">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
            </svg>
          </button>
        </nav>
      </header>

      {/* ── Main Content ──────────────────────────────────────── */}
      <div className="relative z-10 flex-1 flex min-h-0">
        <div className="flex-1 flex flex-col min-w-0">

          {/* Dashboard / Suggestions area */}
          {showSuggestions && messages.length <= 1 && !listening && !thinking && !speaking && !taskQuestion && (
            <div className="flex-1 flex flex-col items-center justify-center px-4">
              <div className="animate-fade-in text-center space-y-8 max-w-2xl w-full">
                {/* Dashboard widgets */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-xl mx-auto">
                  <div className="glass-card rounded-2xl p-4 text-center">
                    <div className="text-2xl mb-1">{accOnlineCount > 0 ? "🟢" : "⚪"}</div>
                    <div className="text-lg font-bold text-gray-200 font-mono">{accDeviceCount}</div>
                    <div className="text-[8px] font-mono text-gray-600 tracking-widest uppercase mt-0.5">Devices</div>
                  </div>
                  <div className="glass-card rounded-2xl p-4 text-center">
                    <div className="text-2xl mb-1">🧠</div>
                    <div className="text-lg font-bold text-gray-200 font-mono">{messages.length}</div>
                    <div className="text-[8px] font-mono text-gray-600 tracking-widest uppercase mt-0.5">Messages</div>
                  </div>
                  <div className="glass-card rounded-2xl p-4 text-center">
                    <div className="text-2xl mb-1">
                      {systemStats?.battery?.present
                        ? (systemStats.battery.charging ? "⚡" : systemStats.battery.percent < 20 ? "🔴" : "🔋")
                        : "💻"}
                    </div>
                    <div className="text-lg font-bold text-gray-200 font-mono">
                      {systemStats?.memory ? `${systemStats.memory.percent}%` : "--"}
                    </div>
                    <div className="text-[8px] font-mono text-gray-600 tracking-widest uppercase mt-0.5">RAM</div>
                  </div>
                  <div className="glass-card rounded-2xl p-4 text-center">
                    <div className="text-2xl mb-1">🔗</div>
                    <div className="text-lg font-bold text-gray-200 font-mono">
                      {systemStats?.cpu ? `${systemStats.cpu.percent}%` : "--"}
                    </div>
                    <div className="text-[8px] font-mono text-gray-600 tracking-widest uppercase mt-0.5">CPU</div>
                  </div>
                </div>

                {/* Suggestions */}
                <div className="glass-card rounded-2xl p-5 max-w-lg mx-auto relative">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-1 h-1 rounded-full bg-purple-500/40" />
                    <span className="text-[8px] font-mono text-gray-700 tracking-[0.2em] uppercase">quick actions</span>
                    <div className="flex-1 h-px bg-gradient-to-r from-purple-800/20 to-transparent" />
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s, i) => (
                      <button key={s} onClick={() => pickSuggestion(s)}
                        className="suggestion-btn" style={{ animationDelay: `${i * 50}ms` }}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Chat / Interaction area */}
          {(!showSuggestions || messages.length > 1 || listening || thinking || speaking || taskQuestion) && (
            <div className="flex-1 flex flex-col items-center justify-center relative px-4">
              {/* Center overlay */}
              {centerOverlay && (
                <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-none" onClick={dismissOverlay}>
                  <div className="pointer-events-auto center-overlay max-w-xl w-full mx-6 max-h-[60vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[9px] font-mono tracking-[0.25em] uppercase text-cyan-500/70">result</span>
                      <button onClick={dismissOverlay} className="text-gray-600 hover:text-gray-300 transition-colors text-[10px] font-mono tracking-wider">✕ dismiss</button>
                    </div>
                    <pre className="text-sm text-gray-200 font-mono leading-relaxed whitespace-pre-wrap">{centerOverlay}</pre>
                  </div>
                  <div className="absolute inset-0 -z-10" onClick={dismissOverlay} />
                </div>
              )}

              {/* Ambient glow */}
              <div className={`absolute w-[300px] h-[300px] sm:w-[400px] sm:h-[400px] rounded-full -z-10 transition-all duration-700 ${
                listening ? 'ambient-glow-listening' : thinking ? 'ambient-glow-thinking' : speaking ? 'ambient-glow-speaking' : 'ambient-glow-idle'
              }`} style={{ marginTop: taskQuestion ? -80 : -40 }} />

              {/* Status ring */}
              {(listening || thinking || speaking) && (
                <div className={`absolute w-[200px] h-[200px] sm:w-[300px] sm:h-[300px] rounded-full ${
                  listening ? 'status-ring-listening' : thinking ? 'status-ring-thinking' : 'status-ring-speaking'
                }`} style={{ marginTop: taskQuestion ? -80 : -40 }} />
              )}

              {/* BotSwarm orb */}
              <div className={`w-[180px] h-[180px] sm:w-[260px] sm:h-[260px] rounded-full overflow-hidden border border-blue-800/20 shadow-2xl cursor-pointer transition-all duration-500 ${
                listening ? 'shadow-[0_0_60px_rgba(34,197,94,0.15)]' :
                thinking ? 'shadow-[0_0_60px_rgba(168,85,247,0.2)]' :
                speaking ? 'shadow-[0_0_60px_rgba(6,182,212,0.15)]' :
                'shadow-blue-900/30'
              } ${centerOverlay ? 'opacity-20 scale-95 blur-sm' : 'opacity-100 scale-100'}`} style={{ marginTop: taskQuestion ? -80 : -40 }} onClick={handleOrbClick}>
                <BotSwarm listening={listening} thinking={thinking} speaking={speaking} activity={activityIntensity} botEvents={botEvents} centered />
              </div>

              {!listening && !thinking && !speaking && !taskQuestion && messages.length <= 1 && (
                <div className="mt-3 text-center animate-fade-in">
                  <p className="text-[10px] font-mono text-blue-400/50 tracking-[0.2em]">tap the orb or type below</p>
                </div>
              )}

              {/* Strategies */}
              {strategies && strategies.length > 0 && (
                <div className="mt-6 max-w-lg w-full px-4">
                  <div className="space-y-2.5">
                    {strategies.map((s, i) => (
                      <button key={i} onClick={() => pickStrategy(i)}
                        className={`strategy-card w-full text-left p-4 ${selectedStrategy === i ? "selected" : ""}`}
                        style={{ animationDelay: `${i * 80}ms` }}>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="strategy-name">{s.name}</span>
                          <span className="strategy-complexity">CX {s.complexity}/10</span>
                        </div>
                        <p className="strategy-desc mb-2">{s.description}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {s.pros.slice(0, 2).map((p, pi) => (
                            <span key={pi} className="strategy-pro">+ {p}</span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-up questions */}
              {followUpQuestions.length > 0 && !strategies && (
                <div className="mt-6 max-w-lg w-full px-4">
                  <div className="flex flex-wrap justify-center gap-2">
                    {followUpQuestions.map((q, i) => (
                      <button key={i} onClick={() => handleFollowUp(q)}
                        className="followup-btn" style={{ animationDelay: `${i * 60}ms` }}>
                        {q.length > 50 ? q.slice(0, 50) + "..." : q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Proactive suggestions */}
              {proactiveSuggestions.length > 0 && !strategies && (
                <div className="mt-4 max-w-lg w-full px-4">
                  <div className="flex flex-wrap justify-center gap-2">
                    {proactiveSuggestions.map((s, i) => (
                      <button key={i} onClick={() => handleProactive(s)}
                        className="proactive-btn" style={{ animationDelay: `${i * 60}ms` }}>
                        {s.length > 45 ? s.slice(0, 45) + "..." : s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Last response card */}
              {lastResponse && !listening && !thinking && !speaking && (
                <div className="mt-6 max-w-2xl w-full px-6 message-enter">
                  <div className="holo-card glow-card px-5 py-4 relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-purple-500/40 to-cyan-500/40" />
                    <div className="flex items-center gap-2 mb-2.5">
                      <div className="w-2 h-2 rounded-full bg-purple-500/60 shadow-[0_0_8px_rgba(168,85,247,0.3)]" />
                      <span className="text-[9px] font-mono tracking-[0.2em] uppercase bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent font-semibold">jarvis</span>
                      <div className="flex-1 h-px bg-gradient-to-r from-purple-800/20 to-transparent" />
                    </div>
                    <p className="text-sm text-gray-200 font-light leading-relaxed whitespace-pre-wrap">{lastResponse}</p>
                  </div>
                </div>
              )}

              {/* Task progress */}
              {taskTotal > 0 && taskStep > 0 && (
                <div className="mt-4 w-72">
                  <div className="task-progress-bar">
                    <div className="task-progress-fill" style={{ width: `${(taskStep / taskTotal) * 100}%` }} />
                  </div>
                  <p className="text-[9px] font-mono text-gray-600/60 text-center mt-1 tracking-wider">step {taskStep} / {taskTotal}</p>
                </div>
              )}
            </div>
          )}

          {/* ── Bottom Input Bar ────────────────────────────────── */}
          {!taskQuestion ? (
            <div className="relative z-20 px-4 pb-4 pt-2">
              <div className="max-w-lg mx-auto relative group">
                <div className="absolute -inset-[1px] rounded-2xl bg-gradient-to-r from-purple-600/20 via-cyan-500/20 to-purple-600/20 opacity-0 group-hover:opacity-100 transition-opacity duration-700 blur-sm" />
                <div className="input-bar relative flex items-center gap-2 px-5 py-3">
                  <input
                    ref={inputRef}
                    type="text"
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
                    placeholder="Ask Jason anything..."
                    className="bg-transparent text-sm text-gray-200 placeholder-gray-700/50 outline-none flex-1 font-mono"
                  />
                  <button onClick={handleOrbClick}
                    className={`p-2 rounded-full transition-all duration-300 ${
                      listening
                        ? "bg-green-500/20 text-green-400 shadow-[0_0_12px_rgba(34,197,94,0.3)]"
                        : "text-gray-500 hover:text-purple-400 hover:bg-purple-900/20"
                    }`}>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m-4 0h8" />
                    </svg>
                  </button>
                  <button onClick={sendText} className="send-btn p-2 rounded-full transition-all duration-200 hover:bg-purple-900/20">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Task question input */
            <div className="relative z-20 px-4 pb-4 pt-2">
              <div className="max-w-lg mx-auto glass-card px-6 py-5">
                <p className="text-[10px] font-mono text-purple-400/80 tracking-[0.25em] uppercase mb-2">Jason needs to know</p>
                <p className="text-sm text-gray-200 mb-4 leading-relaxed">{taskQuestion}</p>
                <div className="flex gap-2.5">
                  <input ref={taskInputRef} type="text" value={textInput} onChange={(e) => setTextInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") sendText(); }} placeholder="Type your answer..."
                    className="task-input flex-1" autoFocus />
                  <button onClick={sendText} className="task-send-btn">Send</button>
                </div>
              </div>
            </div>
          )}

          {/* Task result */}
          {taskResult && (
            <div className="relative z-20 px-4 pb-4">
              <div className="max-w-lg mx-auto glass-card px-6 py-5">
                <p className="text-[10px] font-mono text-green-400/80 tracking-[0.25em] uppercase mb-2">
                  <span className="inline-block mr-1.5">✓</span> Task complete
                </p>
                <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{taskResult}</p>
                {Object.keys(collectedInfo).length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-800/30 space-y-1.5">
                    {Object.entries(collectedInfo).map(([k, v]) => (
                      <p key={k} className="text-xs text-gray-500"><span className="text-purple-400/70">{k}:</span> <span className="text-gray-400">{v}</span></p>
                    ))}
                  </div>
                )}
                <button onClick={() => setTaskResult(null)} className="mt-3 text-[9px] text-gray-700/50 hover:text-gray-400 font-mono tracking-[0.15em] uppercase transition-colors">dismiss</button>
              </div>
            </div>
          )}

          {/* Live transcript */}
          {listening && interim && (
            <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4 pointer-events-none">
              <div className="glass-card px-5 py-3 text-center">
                <p className="text-sm text-cyan-300/80 font-mono cursor-blink">{interim}</p>
                {confidence > 0 && (
                  <div className="mt-2 flex items-center gap-2 justify-center">
                    <div className="w-24 h-1 rounded-full bg-gray-800/50 overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-purple-500 to-cyan-400 transition-all duration-300" style={{ width: `${confidence}%` }} />
                    </div>
                    <span className="text-[9px] font-mono text-gray-500">{confidence}%</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)}
          summary={profileSummary} interests={profileInterests} />
      </div>
    </div>
  );
}
