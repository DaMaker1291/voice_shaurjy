"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Navbar from "@/components/Navbar";
import BotSwarm from "@/components/BotSwarm";
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

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [textInput, setTextInput] = useState("");
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [confidence, setConfidence] = useState(0);
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
  const [voice] = useState("en-GB-RyanNeural");
  const [cockpitTab, setCockpitTab] = useState<"router" | "telemetry">("router");
  const [mobileView, setMobileView] = useState<"chat" | "telemetry">("chat");

  const inputRef = useRef<HTMLTextAreaElement>(null);
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
          setMessages(p => [...p, { role: "assistant", content: "Task complete." }]);
        } else {
          setMessages(p => [...p, { role: "assistant", content: data.text || data.message || "Done." }]);
          setTaskQuestion(null); setTaskSession(null);
        }
      } catch (e: any) {
        setMessages(p => [...p, { role: "assistant", content: `Error: ${e.message}` }]);
      }
      setThinking(false); return;
    }

    let routed = false;
    try {
      const routerResult = await dispatchToRouter(text);
      if (routerResult?.target_agent && routerResult?.agent_response) {
        routed = true;
        const resp = routerResult.agent_response;
        const target = routerResult.target_agent;
        let reply = "";
        if (target === "HAL_AGENT") {
          const devices = resp.device_telemetry_payload || [];
          const status = resp.execution_status || "PENDING";
          reply = resp.frontend_ui_mutation?.display_text
            || (devices.length > 0
              ? `Devices: ${devices.map((d: any) => `${d.device_alias || d.unique_id} → ${d.method_signature}`).join(", ")}`
              : `Hardware task ${status}. ${resp.frontend_ui_mutation?.troubleshooting_steps?.join(" ") || ""}`);
        } else if (target === "OS_AGENT") {
          const action = resp.os_action_payload;
          reply = resp.frontend_ui_mutation?.display_text
            || (action ? `${action.action_type}: ${action.target_identifier}` : `OS task: ${resp.system_state_update?.execution_status || "PENDING"}`);
        } else if (target === "WEB_AGENT") {
          reply = resp.frontend_ui_mutation?.display_text
            || (resp.web_operation_payload?.url ? `Opening ${resp.web_operation_payload.url}` : "Web task queued.");
        } else {
          reply = resp.text || resp.message || "Task routed to " + target;
        }
        setMessages(p => [...p, { role: "assistant", content: reply }]);
        addLog(`→ ${target} | ${Math.round((routerResult.routing?.routing_confidence ?? 0) * 100)}% | ${routerResult.latency_ms?.total}ms`, "success");
        if (reply.length < 300) speak(reply).catch(() => {});
      }
    } catch {}

    if (!routed) {
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
    }
    setThinking(false);
  }, [textInput, taskSession, taskQuestion, dispatchToRouter, speak, addBotEvent, addLog]);

  const handleVoiceClick = useCallback(() => {
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
    <div className="flex flex-col h-screen bg-[#09090b] text-zinc-100">
      <div className="ambient-glow" />

      <Navbar entityMood={entityMood} entityMoodEmoji={entityMoodEmoji} />

      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Chat Panel */}
        <div className={`flex-1 flex flex-col min-w-0 ${mobileView === "telemetry" ? "hidden lg:flex" : "flex"}`}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`animate-fade-in flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[75%] px-4 py-3 text-[14px] leading-relaxed ${
                    msg.role === "user"
                      ? "bg-violet-500/8 rounded-2xl rounded-br-md text-zinc-100"
                      : "bg-transparent text-zinc-400"
                  }`}
                >
                  {msg.content}
                  {msg.link && (
                    <a
                      href={msg.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block mt-1 text-[12px] text-violet-400 no-underline"
                    >
                      {msg.link.slice(0, 40)}...
                    </a>
                  )}
                </div>
              </div>
            ))}

            {thinking && (
              <div className="flex justify-start animate-fade-in">
                <div className="px-4 py-3 bg-transparent">
                  <div className="flex gap-1 items-center h-4">
                    {[0, 0.2, 0.4].map((d, i) => (
                      <div
                        key={i}
                        className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse"
                        style={{ animationDelay: `${d}s` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions */}
          {showSuggestions && messages.length <= 1 && (
            <div className="px-6 pb-3 flex flex-wrap gap-2">
              {SUGGESTIONS.slice(0, 4).map(s => (
                <button
                  key={s}
                  onClick={() => { setTextInput(s); setShowSuggestions(false); inputRef.current?.focus(); }}
                  className="px-3 py-1.5 text-[12px] text-zinc-400 bg-white/[0.04] border border-white/[0.06] rounded-full hover:bg-white/[0.06] hover:text-zinc-200 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Task question */}
          {taskQuestion && (
            <div className="px-6 pb-3">
              <div className="px-4 py-3 rounded-lg bg-violet-500/[0.06] border border-violet-500/10">
                <p className="text-[11px] font-medium text-violet-400 mb-1">
                  Step {taskStep}/{taskTotal}
                </p>
                <p className="text-[13px] text-zinc-400">{taskQuestion}</p>
              </div>
            </div>
          )}

          {/* Interim speech */}
          {listening && interim && (
            <div className="px-6 pb-2">
              <p className="text-[12px] text-violet-400/70 animate-pulse font-mono">{interim}</p>
            </div>
          )}

          {/* Input area */}
          <div className="px-6 pb-6 pt-2">
            <div className="command-input flex items-end gap-3 p-3">
              <BotSwarm
                listening={agentState === "listening"}
                thinking={agentState === "thinking"}
                speaking={agentState === "speaking"}
                botEvents={botEvents}
              />
              <textarea
                ref={inputRef}
                value={textInput}
                onChange={e => { setTextInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px"; }}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(); } }}
                placeholder="Issue a command..."
                rows={1}
                className="flex-1 bg-transparent border-none outline-none text-[14px] text-zinc-100 placeholder-zinc-600 resize-none leading-relaxed py-1 max-h-[120px]"
              />
              <button
                onClick={handleVoiceClick}
                className={`p-2 rounded-lg transition-all shrink-0 ${
                  listening
                    ? "bg-violet-500/15 text-violet-400"
                    : "text-zinc-600 hover:text-zinc-400"
                }`}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </button>
              <button
                onClick={sendText}
                disabled={!textInput.trim()}
                className={`w-9 h-9 rounded-full flex items-center justify-center transition-all shrink-0 ${
                  textInput.trim()
                    ? "bg-violet-500 text-white hover:bg-violet-400 shadow-lg shadow-violet-500/20"
                    : "bg-white/[0.06] text-zinc-600 cursor-default"
                }`}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Telemetry Panel */}
        <div className={`${mobileView === "chat" ? "hidden lg:flex" : "flex"} flex-col w-full lg:w-[380px] border-l border-white/[0.06] bg-[#09090b] overflow-hidden`}>
          {/* Panel tabs */}
          <div className="flex items-center gap-1 px-4 py-3 border-b border-white/[0.06] shrink-0">
            {(["router", "telemetry"] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setCockpitTab(tab)}
                className={`px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors ${
                  cockpitTab === tab
                    ? "bg-violet-500/10 text-violet-400"
                    : "text-zinc-600 hover:text-zinc-400"
                }`}
              >
                {tab === "router" ? "Router" : "Telemetry"}
              </button>
            ))}
            {isDispatching && (
              <div className="ml-auto flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-[11px] text-amber-400">Routing</span>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* System Stats */}
            {systemStats && (
              <div className="space-y-3">
                <p className="text-[11px] font-medium text-zinc-600 uppercase tracking-wider">System</p>
                <div className="grid grid-cols-2 gap-3">
                  {systemStats.cpu && (
                    <div className="stat-card">
                      <p className="text-[11px] text-zinc-600 mb-1">CPU</p>
                      <p className="text-[20px] font-medium text-zinc-100">{systemStats.cpu.percent}%</p>
                      <div className="progress-track mt-2">
                        <div className="progress-fill" style={{ width: `${systemStats.cpu.percent}%` }} />
                      </div>
                    </div>
                  )}
                  {systemStats.memory && (
                    <div className="stat-card">
                      <p className="text-[11px] text-zinc-600 mb-1">Memory</p>
                      <p className="text-[20px] font-medium text-zinc-100">{systemStats.memory.percent}%</p>
                      <p className="text-[11px] text-zinc-600 mt-1">{systemStats.memory.used_gb} / {systemStats.memory.total_gb} GB</p>
                    </div>
                  )}
                  {systemStats.battery && systemStats.battery.present && (
                    <div className="stat-card">
                      <p className="text-[11px] text-zinc-600 mb-1">Battery</p>
                      <p className="text-[20px] font-medium text-zinc-100">{systemStats.battery.percent}%</p>
                      <p className="text-[11px] text-zinc-600 mt-1">{systemStats.battery.charging ? "Charging" : "On battery"}</p>
                    </div>
                  )}
                  {systemStats.uptime_h != null && (
                    <div className="stat-card">
                      <p className="text-[11px] text-zinc-600 mb-1">Uptime</p>
                      <p className="text-[20px] font-medium text-zinc-100">{Math.floor(systemStats.uptime_h)}h</p>
                      <p className="text-[11px] text-zinc-600 mt-1">{Math.round((systemStats.uptime_h % 1) * 60)}m</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Entity State */}
            <div className="space-y-3">
              <p className="text-[11px] font-medium text-zinc-600 uppercase tracking-wider">Entity</p>
              <div className="stat-card space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-zinc-400">Mood</span>
                  <span className="text-[12px] text-zinc-100">{entityMoodEmoji} {entityMood}</span>
                </div>
                {entityThought && (
                  <div>
                    <p className="text-[11px] text-zinc-600 mb-1">Current thought</p>
                    <p className="text-[13px] text-zinc-400 leading-relaxed">{entityThought}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Agent Router */}
            {cockpitTab === "router" && (
              <AgentRouter
                routingData={routerPayload as any}
                isDispatching={isDispatching}
                userText={messages.filter(m => m.role === "user").slice(-1)[0]?.content}
              />
            )}

            {/* Telemetry */}
            {cockpitTab === "telemetry" && (
              <CockpitTelemetry
                relayOnline={relayOnline}
                devices={devices}
                systemStats={systemStats}
                agentResponse={routerPayload?.agent_response ?? null}
                activeAgent={activeAgent}
                activityLog={activityLog}
              />
            )}
          </div>
        </div>
      </div>

      {/* Mobile view toggle */}
      <div className="lg:hidden fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex bg-[#18181b] border border-white/[0.08] rounded-full p-1 shadow-xl shadow-black/40">
        <button
          onClick={() => setMobileView("chat")}
          className={`px-4 py-2 text-[12px] font-medium rounded-full transition-colors ${
            mobileView === "chat" ? "bg-violet-500/15 text-violet-400" : "text-zinc-600"
          }`}
        >
          Chat
        </button>
        <button
          onClick={() => setMobileView("telemetry")}
          className={`px-4 py-2 text-[12px] font-medium rounded-full transition-colors ${
            mobileView === "telemetry" ? "bg-violet-500/15 text-violet-400" : "text-zinc-600"
          }`}
        >
          Telemetry
        </button>
      </div>

      {/* Task result overlay */}
      {taskResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#09090b]/80 backdrop-blur-sm" onClick={() => setTaskResult(null)}>
          <div onClick={e => e.stopPropagation()} className="max-w-md w-[90%] p-6 bg-[#111113] border border-white/[0.08] rounded-2xl animate-scale-in">
            <p className="text-[11px] font-medium text-violet-400 mb-2 uppercase tracking-wider">Task Complete</p>
            <p className="text-[14px] text-zinc-400 whitespace-pre-wrap leading-relaxed">{taskResult}</p>
            {Object.keys(collectedInfo).length > 0 && (
              <div className="mt-4 pt-3 border-t border-white/[0.06] space-y-1">
                {Object.entries(collectedInfo).map(([k, v]) => (
                  <p key={k} className="text-[12px] text-zinc-600">
                    <span className="text-violet-400">{k}:</span> {v}
                  </p>
                ))}
              </div>
            )}
            <button
              onClick={() => setTaskResult(null)}
              className="mt-4 text-[12px] text-zinc-600 hover:text-zinc-400 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
