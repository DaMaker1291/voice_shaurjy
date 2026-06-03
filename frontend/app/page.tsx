"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import BotSwarm from "@/components/BotSwarm";
import Sidebar from "@/components/Sidebar";
import SystemPanel from "@/components/SystemPanel";
import { entityProcess } from "@/lib/api";

interface Message { role: string; content: string }

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

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SUGGESTIONS = [
  "play some music", "what's the time", "scan my network",
  "volume to 50", "lock my PC", "take a screenshot",
  "open Spotify", "battery status",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [showInput, setShowInput] = useState(false);
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
  const [simTask, setSimTask] = useState<string | null>(null);
  const [strategies, setStrategies] = useState<Strategy[] | null>(null);
  const [followUpQuestions, setFollowUpQuestions] = useState<string[]>([]);
  const [proactiveSuggestions, setProactiveSuggestions] = useState<string[]>([]);
  const [entityState, setEntityState] = useState<EntityState | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null);
  const [entityMemory, setEntityMemory] = useState("");
  const [activityIntensity, setActivityIntensity] = useState(0);
  const [voice, setVoice] = useState<string>(() => {
    if (typeof window === "undefined") return "en-US-AriaNeural";
    return localStorage.getItem("tts_voice") || "en-US-AriaNeural";
  });
  const [showVoicePicker, setShowVoicePicker] = useState(false);
  const [showSystemPanel, setShowSystemPanel] = useState(false);
  const capturedTextRef = useRef("");

  const addBotEvent = useCallback((type: string, label: string) => {
    setBotEvents(prev => [...prev.slice(-8), { type, label, timestamp: Date.now() }]);
  }, []);

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);

  // Scan device on startup
  useEffect(() => {
    (async () => {
      setScanning(true);
      addBotEvent("action", "scanning device");
      try { await fetch(`${BASE}/api/device/scan?user_id=local`, { method: "POST" }); } catch {}
      try {
        const res = await fetch(`${BASE}/api/profile?user_id=local`);
        const data = await res.json();
        setProfileSummary(data.summary || "");
        setProfileInterests(data.profile?.interests?.slice(0, 8).map((i: any) => i.topic) || []);
        setMessages((p) => [...p, {
          role: "assistant",
          content: `Device scanned. I see ${data.profile?.device?.installed_apps?.length || 0} apps, ${data.profile?.interests?.length || 0} interest areas. Ask me anything — or try a suggestion below.`
        }]);
      } catch {}
      setScanning(false);
      addBotEvent("action", "scan complete");
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
      const preferred = voices.find((v) => v.name.includes(voiceName.split("-")[1] || "Aria") || v.name.includes("Aria") || v.name.includes("Jenny"));
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

  const handleQuery = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setMessages((p) => [...p, { role: "user", content: text }]);
    setSidebarOpen(true);
    setThinking(true);
    setSpeaking(false);
    setShowSuggestions(false);
    setStrategies(null);
    setFollowUpQuestions([]);
    setProactiveSuggestions([]);
    setSelectedStrategy(null);
    setActivityIntensity(1);
    addBotEvent("thinking", "processing query");

    const complexTriggers = ["essay","document","report","write","type","compose","explain","analyze","holiday","vacation","trip","plan","research","investigate","create","make","build","set up","configure","scan","network scan","install","business","trading","homework","team page","workflow"];
    const lower = text.toLowerCase();
    const isComplex = complexTriggers.some(t => lower.includes(t)) && lower.split(" ").length >= 3;

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

      if (res.follow_up?.length > 0) {
        setFollowUpQuestions(res.follow_up);
      }

      if (res.proactive?.length > 0) {
        setProactiveSuggestions(res.proactive);
      }

      if (res.action) {
        addBotEvent("action", reply.slice(0, 60));
        setActionFeedback(reply);
        setActionType(res.action_type || "action");
        setSimTask(null);
        setMessages((p) => [...p, { role: "assistant", content: reply }]);
        setTimeout(() => setActionFeedback(null), 4000);
      }
      else if (res.task) {
        addBotEvent("workflow", "task started");
        _handleTaskResponse(res.task);
      }
      else if (reply) {
        addBotEvent("action", "responding");
        speak(reply);
        setSimTask(null);
        setMessages((p) => [...p, { role: "assistant", content: reply }]);
      }

      if (res.entity_state) {
        setEntityState(res.entity_state);
        setEntityMemory(res.entity_state.memory_summary || "");
      }

    } catch (e) {
      addBotEvent("error", "backend unreachable");
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
      setMessages((p) => [...p, { role: "assistant", content: res.text }]);
    }
  }, [strategies, addBotEvent]);

  const handleFollowUp = useCallback(async (q: string) => {
    // Wrap follow-up so it's not treated as a new command (avoids accidental action triggers like "play", "search")
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
      if (reply) { speak(reply); setMessages((p) => [...p, { role: "assistant", content: reply }]); }
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
      if (reply) { setMessages((p) => [...p, { role: "assistant", content: reply }]); }
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
      setMessages((p) => [...p, { role: "assistant", content: `✅ ${data.text}` }]);
      speak("Task complete!");
    } else if (data.type === "workflow") {
      addBotEvent("workflow", data.text);
      setMessages((p) => [...p, { role: "assistant", content: `🔄 ${data.text}` }]);
    } else if (data?.workflow_result?.results) {
      for (const r of data.workflow_result.results) {
        if (r.type === "ask") {
          _handleTaskResponse({ type: "ask", question: r.question, session_id: data.execution_id });
        } else if (r.type === "notify") {
          setActionFeedback(r.text);
          setActionType("workflow");
          setTimeout(() => setActionFeedback(null), 2000);
        } else if (r.type === "complete") {
          addBotEvent("action", "workflow complete");
          setMessages((p) => [...p, { role: "assistant", content: `✅ ${r.text}` }]);
        }
      }
    } else if (data.type === "error") {
      addBotEvent("error", data.text);
      setMessages((p) => [...p, { role: "assistant", content: `⚠️ ${data.text}` }]);
      setTaskSession(null);
      setTaskQuestion(null);
    }
  }, [taskSession, speak, addBotEvent]);

  // ── Speech ─────────────────────────────────────────────────
  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setShowInput(true); setTimeout(() => inputRef.current?.focus(), 100); return; }
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
        if (result.isFinal) {
          final += (final ? " " : "") + transcript;
          bestConfidence = Math.max(bestConfidence, result[0].confidence);
        } else {
          bestInterim += (bestInterim ? " " : "") + transcript;
          bestConfidence = Math.max(bestConfidence, result[0].confidence);
        }
      }
      const displayText = bestInterim || final;
      setInterim(displayText);
      capturedTextRef.current = displayText;
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
    const t = capturedTextRef.current.trim();
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
    if (taskQuestion) { sendTaskResponse(txt); setShowInput(false); }
    else { setShowInput(false); handleQuery(txt); }
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
      if (e.key === "/" && !showInput && !listening) { e.preventDefault(); setShowInput(true); setTimeout(() => inputRef.current?.focus(), 100); }
      if (e.key === "Escape") { setShowInput(false); if (listening) { stopListening(); } }
      if (e.key === "Enter" && taskQuestion && !showInput) { sendTaskResponse(textInput); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [showInput, listening, stopListening, taskQuestion, textInput, sendTaskResponse]);

  const statusText = taskQuestion ? `answering step ${taskStep}/${taskTotal}` :
    listening ? (interim ? `"${interim.slice(0, 40)}"` : "listening") :
    thinking ? "processing" :
    speaking ? "speaking" :
    showInput ? "type & enter" :
    entityState?.active_goals?.length ? `${entityState.active_goals.length} active goals` :
    "tap to speak or press /";

  return (
    <div className="relative h-screen w-full overflow-hidden flex flex-row" style={{ backgroundColor: '#05081a' }}>
      {/* ── Background layers ── */}
      <div className="gradient-bg" />
      <div className="grid-overlay" />
      <div className="stars" />
      <div className="stars2" />
      <div className="stars3" />

      {/* ── Main content ── */}
      <div className="relative z-10 flex-[3] min-w-0 flex flex-col px-4">
        {/* Action notification */}
        <div className={`fixed top-6 left-1/2 -translate-x-1/2 z-30 transition-all duration-500 ${actionFeedback ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-8 pointer-events-none"}`}>
          <div className="bot-toast flex items-center gap-3 px-5 py-2.5">
            <span className={`bot-toast-dot ${actionType === "workflow" ? "bg-blue-400" : actionType === "error" ? "bg-red-400" : "bg-cyan-400"}`} />
            <div>
              <p className="text-[9px] font-mono tracking-[0.25em] uppercase" style={{ color: actionType === "workflow" ? "rgba(96,165,250,0.7)" : actionType === "error" ? "rgba(248,113,113,0.7)" : "rgba(34,211,238,0.7)" }}>{actionType}</p>
              <p className="text-xs text-gray-200 font-mono">{actionFeedback}</p>
            </div>
          </div>
        </div>

        {/* Top bar */}
        <div className="top-bar flex items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-8 h-8">
              <div className={`status-dot ${listening ? "listening" : thinking ? "thinking" : speaking ? "speaking" : "idle"}`} />
              {listening && <div className="absolute inset-0 rounded-full status-ring-listening" />}
              {thinking && <div className="absolute inset-0 rounded-full status-ring-thinking" />}
              {speaking && <div className="absolute inset-0 rounded-full status-ring-speaking" />}
            </div>
            <div className="flex flex-col">
              <span className="status-text">{scanning ? "scanning device..." : statusText}</span>
              {entityState && (
                <span className="text-[8px] font-mono text-purple-500/40 tracking-[0.15em] mt-0.5">
                  {entityState.active_goals?.length || 0} goals &middot; {entityState.interaction_count} interactions
                </span>
              )}
            </div>
            {confidence > 0 && (
              <div className="ml-2 flex items-center gap-1.5">
                <div className="w-12 h-1 rounded-full bg-gray-800/50 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-purple-500 to-cyan-400 transition-all duration-300" style={{ width: `${confidence}%` }} />
                </div>
                <span className="text-[9px] font-mono text-gray-600">{confidence}%</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {profileInterests.length > 0 && (
              <div className="hidden md:flex items-center gap-1.5 mr-2">
                {profileInterests.slice(0, 3).map((t, i) => (
                  <span key={i} className="interest-tag">{t}</span>
                ))}
              </div>
            )}
            <div className="relative">
              <button
                onClick={() => { setShowVoicePicker((o) => !o); setShowSystemPanel(false); }}
                className="control-btn flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
                title="TTS Voice"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
                <span className="text-[9px] font-mono tracking-wider">{voice.replace("en-US-", "").replace("Neural", "").replace("en-GB-", "UK-").replace("en-AU-", "AU-")}</span>
              </button>
              {showVoicePicker && (
                <div className="absolute right-0 top-9 z-50 w-44 bg-gray-900/95 backdrop-blur-xl border border-gray-800/50 rounded-xl p-1.5 shadow-2xl animate-fade-in">
                  {[
                    { id: "en-US-AriaNeural", label: "Aria (US Female)" },
                    { id: "en-US-JennyNeural", label: "Jenny (US Friendly)" },
                    { id: "en-US-GuyNeural", label: "Guy (US Male)" },
                    { id: "en-US-DavisNeural", label: "Davis (US Calm)" },
                    { id: "en-GB-SoniaNeural", label: "Sonia (UK Female)" },
                    { id: "en-GB-RyanNeural", label: "Ryan (UK Male)" },
                    { id: "en-AU-NatashaNeural", label: "Natasha (AU Fem.)" },
                  ].map((v) => (
                    <button
                      key={v.id}
                      onClick={() => { setVoice(v.id); setShowVoicePicker(false); localStorage.setItem("tts_voice", v.id); }}
                      className={`w-full text-left text-[10px] font-mono px-2.5 py-1.5 rounded-lg transition-colors ${
                        voice === v.id ? "bg-purple-900/20 text-purple-400" : "text-gray-500 hover:text-gray-300 hover:bg-gray-800/30"
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="relative">
              <button onClick={() => { setShowSystemPanel(o => !o); setShowVoicePicker(false); }} className="control-btn p-1.5 rounded-lg" title="System Control">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6V6m0 0a2 2 0 100-4 2 2 0 000 4zm0 0v4m0 0a2 2 0 100 4 2 2 0 000-4zm0 0v4m0 0a2 2 0 100 4 2 2 0 000-4z" /></svg>
              </button>
              {showSystemPanel && <SystemPanel onClose={() => setShowSystemPanel(false)} />}
            </div>
            <button onClick={() => setSidebarOpen((o) => !o)} className="control-btn p-1.5 rounded-lg">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Task progress */}
        {taskTotal > 0 && taskStep > 0 && (
          <div className="absolute top-14 left-1/2 -translate-x-1/2 z-10 w-72 animate-fade-in">
            <div className="task-progress-bar">
              <div className="task-progress-fill" style={{ width: `${(taskStep / taskTotal) * 100}%` }} />
            </div>
            <p className="text-[9px] font-mono text-gray-600/60 text-center mt-1 tracking-wider">step {taskStep} / {taskTotal}</p>
          </div>
        )}

        {/* Center content */}
        <div className="flex-1 flex flex-col items-center justify-center relative">
          {/* Centered BotSwarm agents */}
          <div className="w-[420px] h-[420px] rounded-full overflow-hidden border border-blue-800/20 shadow-2xl shadow-blue-900/30 cursor-pointer" style={{ marginTop: taskQuestion ? -80 : -40 }} onClick={handleOrbClick}>
            <BotSwarm
              listening={listening}
              thinking={thinking}
              speaking={speaking}
              activity={activityIntensity}
              botEvents={botEvents}
              centered
            />
          </div>

          {/* Subtle prompt below agents when idle */}
          {!listening && !thinking && !speaking && !taskQuestion && messages.length <= 1 && (
            <div className="mt-4 text-center animate-fade-in">
              <p className="text-[10px] font-mono text-blue-400/50 tracking-[0.2em]">tap the orb to speak</p>
              <p className="text-[8px] font-mono text-blue-600/40 mt-1.5 tracking-wider">press <span className="px-1.5 py-0.5 rounded bg-blue-900/30 text-blue-500/50 text-[7px]">/</span> to type</p>
            </div>
          )}

          {/* Suggestions */}
          {showSuggestions && messages.length <= 1 && !listening && !thinking && !speaking && (
            <div className="mt-6 max-w-lg w-full px-6 animate-fade-in">
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={s}
                    onClick={() => pickSuggestion(s)}
                    className="suggestion-btn"
                    style={{ animationDelay: `${i * 50}ms` }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Strategies */}
          {strategies && strategies.length > 0 && (
            <div className="mt-6 max-w-lg w-full px-4 animate-fade-in">
              <div className="space-y-2.5">
                {strategies.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => pickStrategy(i)}
                    className={`strategy-card w-full text-left p-4 ${selectedStrategy === i ? "selected" : ""}`}
                    style={{ animationDelay: `${i * 80}ms` }}
                  >
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
            <div className="mt-6 max-w-lg w-full px-4 animate-fade-in">
              <div className="flex flex-wrap justify-center gap-2">
                {followUpQuestions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleFollowUp(q)}
                    className="followup-btn"
                    style={{ animationDelay: `${i * 60}ms` }}
                  >
                    {q.length > 50 ? q.slice(0, 50) + "..." : q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Proactive suggestions */}
          {proactiveSuggestions.length > 0 && !strategies && (
            <div className="mt-4 max-w-lg w-full px-4 animate-fade-in">
              <div className="flex flex-wrap justify-center gap-2">
                {proactiveSuggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleProactive(s)}
                    className="proactive-btn"
                    style={{ animationDelay: `${i * 60}ms` }}
                  >
                    {s.length > 45 ? s.slice(0, 45) + "..." : s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Task follow-up */}
        {taskQuestion && (
          <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4 animate-fade-in">
            <div className="glass-card px-6 py-5">
              <p className="text-[10px] font-mono text-purple-400/80 tracking-[0.25em] uppercase mb-2">Jason needs to know</p>
              <p className="text-sm text-gray-200 mb-4 leading-relaxed">{taskQuestion}</p>
              <div className="flex gap-2.5">
                <input
                  ref={taskInputRef}
                  type="text"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
                  placeholder="Type your answer..."
                  className="task-input flex-1"
                  autoFocus
                />
                <button onClick={sendText} className="task-send-btn">Send</button>
              </div>
            </div>
          </div>
        )}

        {/* Task result */}
        {taskResult && (
          <div className="absolute bottom-32 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4 animate-fade-in">
            <div className="glass-card px-6 py-5">
              <p className="text-[10px] font-mono text-green-400/80 tracking-[0.25em] uppercase mb-2">
                <span className="inline-block mr-1.5">&#10003;</span> Task complete
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

        {/* Text input */}
        {!taskQuestion && (
          <div className={`absolute bottom-20 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4 transition-all duration-400 ${
            showInput ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6 pointer-events-none"
          }`}>
            <div className="input-bar flex items-center gap-2 px-5 py-2.5">
              <input
                ref={inputRef}
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
                placeholder="Ask Jason anything..."
                className="bg-transparent text-sm text-gray-200 placeholder-gray-700/50 outline-none flex-1 font-mono"
              />
              <button onClick={sendText} className="send-btn p-1.5 rounded-full transition-all duration-200">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" /></svg>
              </button>
            </div>
          </div>
        )}

        {/* Live transcript */}
        {listening && interim && (
          <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4 animate-fade-in pointer-events-none">
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

      <Sidebar
        messages={messages}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        summary={profileSummary}
        interests={profileInterests}
      />
    </div>
  );
}
