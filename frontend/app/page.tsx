"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import HolographicNeuron from "@/components/HolographicNeuron";
import BotSwarm from "@/components/BotSwarm";
import Sidebar from "@/components/Sidebar";
import { entityProcess } from "@/lib/api";

interface Message {
  role: string;
  content: string;
}

interface Strategy {
  name: string;
  description: string;
  pros: string[];
  cons: string[];
  complexity: number;
  key_steps: string[];
}

interface EntityState {
  memory_summary: string;
  active_goals: { goal: string; priority: number; progress: number }[];
  preferences: Record<string, { value: string }>;
  interaction_count: number;
}

interface BotEvent {
  type: string;
  label: string;
  timestamp: number;
}

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SUGGESTIONS = [
  "play some music",
  "what's the time",
  "scan my network",
  "volume to 50",
  "lock my PC",
  "take a screenshot",
  "open Spotify",
  "battery status",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
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
    try {
      const res = await fetch(`${BASE}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: "en-US-AriaNeural" }),
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
      utterance.rate = 1.0; utterance.pitch = 0.9;
      utterance.onend = () => setSpeaking(false);
      const voices = synth.getVoices();
      const preferred = voices.find((v) => v.name.includes("Aria") || v.name.includes("Jenny") || v.name.includes("Zira"));
      if (preferred) utterance.voice = preferred;
      synth.speak(utterance);
    }
  }, [addBotEvent]);

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

  const handleFollowUp = useCallback((q: string) => { handleQuery(q); }, [handleQuery]);
  const handleProactive = useCallback((s: string) => { handleQuery(s); }, [handleQuery]);

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
      setInterim(bestInterim || final);
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
    setInterim("");
  }, []);

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
      if (e.key === "Escape") { setShowInput(false); stopListening(); }
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
    "tap orb or press /";

  return (
    <div className="relative h-screen w-full overflow-hidden bg-gray-950 flex flex-row">
      {/* ── Bot Swarm Background ── */}
      <BotSwarm
        listening={listening}
        thinking={thinking}
        speaking={speaking}
        activity={activityIntensity}
        botEvents={botEvents}
      />

      {/* ── Main content ── */}
      <div className="relative z-10 flex-[3] min-w-0 flex flex-col">
        {/* Action notification — animated bot event toast */}
        <div className={`fixed top-6 left-1/2 -translate-x-1/2 z-30 transition-all duration-500 ${actionFeedback ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-6 pointer-events-none"}`}>
          <div className="bot-toast flex items-center gap-3 px-5 py-2.5">
            <span className={`bot-toast-dot ${actionType === "workflow" ? "bg-blue-500" : actionType === "error" ? "bg-red-500" : "bg-cyan-500"}`} />
            <div>
              <p className="text-[9px] font-mono text-cyan-400/70 tracking-widest uppercase">{actionType}</p>
              <p className="text-xs text-gray-200 font-mono">{actionFeedback}</p>
            </div>
          </div>
        </div>

        {/* Top bar */}
        <div className="top-bar flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className={`status-dot ${listening ? "listening" : thinking ? "thinking" : speaking ? "speaking" : "idle"}`} />
            <span className="status-text">{scanning ? "scanning device..." : statusText}</span>
            {confidence > 0 && <span className="text-[10px] font-mono text-gray-700">{confidence}%</span>}
          </div>
          <div className="flex items-center gap-3">
            {profileInterests.length > 0 && (
              <div className="hidden md:flex items-center gap-1.5">
                {profileInterests.slice(0, 3).map((t, i) => (
                  <span key={i} className="interest-tag">{t}</span>
                ))}
              </div>
            )}
            <button onClick={() => setSidebarOpen((o) => !o)} className="text-gray-600 hover:text-gray-300 transition-colors p-1.5 rounded-lg hover:bg-gray-800/30">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Task progress */}
        {taskTotal > 0 && taskStep > 0 && (
          <div className="absolute top-14 left-1/2 -translate-x-1/2 z-10 w-64">
            <div className="task-progress-bar">
              <div className="task-progress-fill" style={{ width: `${(taskStep / taskTotal) * 100}%` }} />
            </div>
            <p className="text-[9px] font-mono text-gray-700/50 text-center mt-1">step {taskStep}/{taskTotal}</p>
          </div>
        )}

        {/* Center content */}
        <div className="flex-1 flex flex-col items-center justify-center">
          {/* Holographic neuron */}
          <div className="flex-shrink-0" style={{ marginTop: taskQuestion ? -80 : -40 }}>
            <HolographicNeuron listening={listening} speaking={thinking || speaking} onClick={handleOrbClick} />
          </div>

          {/* Suggestions */}
          {showSuggestions && messages.length <= 1 && !listening && !thinking && (
            <div className="mt-6 max-w-lg w-full px-6">
              <p className="suggestions-header">try saying</p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => pickSuggestion(s)}
                    className="suggestion-btn"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Strategies */}
          {strategies && strategies.length > 0 && (
            <div className="mt-4 max-w-lg w-full px-6">
              <p className="strategies-header">strategies</p>
              <div className="space-y-2">
                {strategies.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => pickStrategy(i)}
                    className={`strategy-card ${selectedStrategy === i ? "selected" : ""}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="strategy-name">{s.name}</span>
                      <span className="strategy-complexity">complexity {s.complexity}/10</span>
                    </div>
                    <p className="strategy-desc">{s.description}</p>
                    <div className="flex flex-wrap gap-1">
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
            <div className="mt-4 max-w-lg w-full px-6">
              <p className="followup-header">follow up</p>
              <div className="flex flex-wrap justify-center gap-2">
                {followUpQuestions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleFollowUp(q)}
                    className="followup-btn"
                  >
                    {q.length > 50 ? q.slice(0, 50) + "..." : q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Proactive suggestions */}
          {proactiveSuggestions.length > 0 && !strategies && (
            <div className="mt-3 max-w-lg w-full px-6">
              <p className="proactive-header">proactive</p>
              <div className="flex flex-wrap justify-center gap-2">
                {proactiveSuggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleProactive(s)}
                    className="proactive-btn"
                  >
                    {s.length > 45 ? s.slice(0, 45) + "..." : s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Entity Memory Chip */}
        {entityState && entityMemory && (
          <div className="absolute bottom-36 left-4 z-20">
            <div className="entity-chip">
              <span className="text-[10px] font-mono text-purple-400/60">
                🧠 {entityState.active_goals?.length || 0} goals · {entityState.interaction_count} ints
              </span>
            </div>
          </div>
        )}

        {/* Task follow-up */}
        {taskQuestion && (
          <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
            <div className="glass-card px-6 py-4">
              <p className="text-[10px] font-mono text-purple-400 tracking-wider mb-1">Jason needs to know</p>
              <p className="text-sm text-gray-200 mb-3">{taskQuestion}</p>
              <div className="flex gap-2">
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
          <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
            <div className="glass-card px-6 py-4">
              <p className="text-[10px] font-mono text-green-400 tracking-wider mb-1">✓ Task complete</p>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">{taskResult}</p>
              {Object.keys(collectedInfo).length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-800/50">
                  {Object.entries(collectedInfo).map(([k, v]) => (
                    <p key={k} className="text-xs text-gray-500"><span className="text-purple-400">{k}:</span> {v}</p>
                  ))}
                </div>
              )}
              <button onClick={() => setTaskResult(null)} className="mt-3 text-[9px] text-gray-700/50 hover:text-gray-400 font-mono tracking-wider">dismiss</button>
            </div>
          </div>
        )}

        {/* Text input */}
        {!taskQuestion && (
          <div className={`absolute bottom-16 left-1/2 -translate-x-1/2 z-20 transition-all duration-300 ${showInput ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"}`}>
            <div className="input-bar glow-input flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
                placeholder="Ask Jason anything..."
                className="bg-transparent text-sm text-gray-200 placeholder-gray-700 outline-none flex-1"
              />
              <button onClick={sendText} className="text-purple-500 hover:text-purple-400 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" /></svg>
              </button>
            </div>
          </div>
        )}

        {/* Live transcript */}
        {listening && interim && (
          <div className="fixed bottom-0 left-0 right-0 z-20 p-4 pointer-events-none">
            <div className="max-w-lg mx-auto">
              <div className="glass-card px-4 py-2.5 text-center">
                <p className="text-sm text-cyan-300/80 font-mono cursor-blink">{interim}</p>
                {confidence > 0 && <div className="mt-1.5 confidence-bar" style={{ width: `${confidence}%` }} />}
              </div>
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
