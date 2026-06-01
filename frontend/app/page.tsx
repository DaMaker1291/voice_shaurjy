"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import HolographicNeuron from "@/components/HolographicNeuron";
import Sidebar from "@/components/Sidebar";
import SimulationPanel from "@/components/SimulationPanel";
import { textChat, entityProcess, getEntityState, generateStrategies, startWorkflow, advanceWorkflow, getWorkflowTemplates } from "@/lib/api";

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
  "dim the screen",
  "search Wikipedia quantum physics",
  "wake my desktop",
  "show my clipboard",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [textInput, setTextInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [interim, setInterim] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
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
  const [showEntityPanel, setShowEntityPanel] = useState(false);
  const [workflowExecutions, setWorkflowExecutions] = useState<Record<string, any>>({});
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null);
  const [entityMemory, setEntityMemory] = useState("");

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);

  // Scan device + fetch profile on startup
  useEffect(() => {
    (async () => {
      setScanning(true);
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
  }, []);

  const speak = useCallback(async (text: string) => {
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
      audio.onended = () => URL.revokeObjectURL(url);
      audio.load();
      await audio.play();
    } catch {
      const synth = synthRef.current;
      if (!synth) return;
      synth.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0; utterance.pitch = 0.9;
      const voices = synth.getVoices();
      const preferred = voices.find((v) => v.name.includes("Aria") || v.name.includes("Jenny") || v.name.includes("Zira"));
      if (preferred) utterance.voice = preferred;
      synth.speak(utterance);
    }
  }, []);

  // ── Task response ──────────────────────────────────────────
  const sendTaskResponse = useCallback(async (response: string) => {
    if (!taskSession || !response.trim()) return;
    setMessages((p) => [...p, { role: "user", content: response }]);
    setTaskQuestion(null);
    setThinking(true);
    try {
      const res = await fetch(`${BASE}/api/task/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: taskSession, response }),
      });
      const data = await res.json();
      _handleTaskResponse(data);
    } catch {
      setMessages((p) => [...p, { role: "assistant", content: "Task failed." }]);
      setTaskSession(null);
    }
    setThinking(false);
  }, [taskSession]);

  // ── Handle query through Entity Engine ─────────────────────
  const handleQuery = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setMessages((p) => [...p, { role: "user", content: text }]);
    setSidebarOpen(true);
    setThinking(true);
    setShowSuggestions(false);
    setStrategies(null);
    setFollowUpQuestions([]);
    setProactiveSuggestions([]);
    setSelectedStrategy(null);

    // Detect complex tasks for simulation
    const complexTriggers = ["essay","document","report","write","type","compose","holiday","vacation","trip","plan","research","investigate","create","make","build","set up","configure","scan","network scan","install","business","trading","homework","team page","workflow"];
    const lower = text.toLowerCase();
    const isComplex = complexTriggers.some(t => lower.includes(t)) && lower.split(" ").length >= 3;
    if (isComplex) setSimTask(text);

    try {
      // Use the entity engine for all queries
      const res = await entityProcess(text);
      const reply = res.text || "";

      // Handle strategies
      if (res.strategies?.strategies) {
        setStrategies(res.strategies.strategies);
        setFollowUpQuestions(res.strategies.follow_up_questions || []);
        setMessages((p) => [...p, {
          role: "assistant",
          content: `I've thought of a few approaches for that. Here are your options:\n\n${res.strategies.strategies.map((s: Strategy, i: number) => `${i+1}. **${s.name}** - ${s.description}`).join("\n")}\n\nWhich approach sounds best?`
        }]);
        speak(`I have ${res.strategies.strategies.length} strategies for this. Which approach do you prefer?`);
      }

      // Handle follow-up questions
      if (res.follow_up?.length > 0) {
        setFollowUpQuestions(res.follow_up);
      }

      // Handle proactive suggestions
      if (res.proactive?.length > 0) {
        setProactiveSuggestions(res.proactive);
      }

      // Handle actions
      if (res.action) {
        setActionFeedback(reply);
        setTimeout(() => setActionFeedback(null), 4000);
        if (simTask) setSimTask(null);
        setMessages((p) => [...p, { role: "assistant", content: reply }]);
      }
      // Handle tasks
      else if (res.task) {
        _handleTaskResponse(res.task);
      }
      // Handle workflow
      else if (res.task?.type === "workflow") {
        setMessages((p) => [...p, { role: "assistant", content: `🔄 ${res.task.text || "Starting workflow..."}` }]);
        if (res.task.execution_id) {
          setWorkflowExecutions(prev => ({ ...prev, [res.task.execution_id]: { status: "running" } }));
        }
      }
      // Regular response
      else if (reply) {
        speak(reply);
        setSimTask(null);
        setMessages((p) => [...p, { role: "assistant", content: reply }]);
      }

      // Update entity state
      if (res.entity_state) {
        setEntityState(res.entity_state);
        setEntityMemory(res.entity_state.memory_summary || "");
      }

    } catch (e) {
      setMessages((p) => [...p, { role: "assistant", content: "(backend unreachable)" }]);
    }
    setThinking(false);
  }, [speak, simTask]);

  // ── Select a strategy ──────────────────────────────────────
  const pickStrategy = useCallback(async (index: number) => {
    setSelectedStrategy(index);
    if (!strategies || !strategies[index]) return;
    const strat = strategies[index];
    setMessages((p) => [...p, { role: "assistant", content: `👍 Let's go with **${strat.name}**. I'll start working on it.\n\nSteps:\n${strat.key_steps.map((s, i) => `${i+1}. ${s}`).join("\n")}` }]);
    setStrategies(null);
    // Kick off first step via the entity
    const res = await entityProcess(`Execute strategy: ${strat.name}. ${strat.key_steps.join(", ")}`);
    if (res.text) {
      setMessages((p) => [...p, { role: "assistant", content: res.text }]);
    }
  }, [strategies]);

  // ── Follow-up click handler ────────────────────────────────
  const handleFollowUp = useCallback((q: string) => {
    handleQuery(q);
  }, [handleQuery]);

  // ── Proactive suggestion handler ───────────────────────────
  const handleProactive = useCallback((s: string) => {
    handleQuery(s);
  }, [handleQuery]);

  const _handleTaskResponse = useCallback((data: any) => {
    if (data.type === "ask") {
      setTaskSession(data.session_id || taskSession);
      setTaskQuestion(data.question);
      setTaskStep(data.step || 0);
      setTaskTotal(data.total || 0);
      setTaskResult(null);
      setMessages((p) => [...p, { role: "assistant", content: `❓ ${data.question}` }]);
      speak(data.question);
      setTimeout(() => taskInputRef.current?.focus(), 200);
    } else if (data.type === "notify" || data.type === "notify") {
      setActionFeedback(data.text);
      setTaskStep(data.step || 0);
      setTaskTotal(data.total || 0);
      setTimeout(() => setActionFeedback(null), 3000);
    } else if (data.type === "complete") {
      setTaskSession(null);
      setTaskQuestion(null);
      setTaskResult(data.text);
      setCollectedInfo(data.collected || {});
      setMessages((p) => [...p, { role: "assistant", content: `✅ ${data.text}` }]);
      speak("Task complete!");
    } else if (data.type === "workflow") {
      setMessages((p) => [...p, { role: "assistant", content: `🔄 ${data.text}` }]);
      if (data.execution_id) {
        setWorkflowExecutions(prev => ({ ...prev, [data.execution_id]: { status: "running" } }));
      }
    } else if (data?.workflow_result?.results) {
      for (const r of data.workflow_result.results) {
        if (r.type === "ask") {
          _handleTaskResponse({ type: "ask", question: r.question, session_id: data.execution_id });
        } else if (r.type === "notify") {
          setActionFeedback(r.text);
          setTimeout(() => setActionFeedback(null), 2000);
        } else if (r.type === "complete") {
          setMessages((p) => [...p, { role: "assistant", content: `✅ ${r.text}` }]);
          speak("Workflow complete!");
        }
      }
    } else if (data.type === "error") {
      setMessages((p) => [...p, { role: "assistant", content: `⚠️ ${data.text}` }]);
      setTaskSession(null);
      setTaskQuestion(null);
    }
  }, [taskSession, speak]);

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
    setInterim("");
    setConfidence(0);
  }, [taskQuestion, handleQuery, sendTaskResponse]);

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

  const statusText = taskQuestion ? `answer step ${taskStep}/${taskTotal}` :
    listening ? (interim ? `"${interim}"` : "listening") :
    thinking ? "processing" :
    showInput ? "type & enter" :
    entityState?.active_goals?.length ? `${entityState.active_goals.length} active goals` :
    "tap orb or press /";

  return (
    <div className="relative h-screen w-full overflow-hidden bg-gray-950 flex flex-row">
      {/* Background layers */}
      <div className="gradient-bg" />
      <div className="aurora" />
      <div className="scan-overlay" />
      <div className="particle-field" id="particles" />
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="stars" /><div className="stars2" /><div className="stars3" />
      </div>

      {/* ── LEFT: Chat interface ─────────────────────────────── */}
      <div className="flex-[3] relative min-w-0 flex flex-col">
        {/* Action toast */}
        <div className={`fixed top-20 left-1/4 -translate-x-1/2 z-30 transition-all duration-500 ${actionFeedback ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4 pointer-events-none"}`}>
          <div className="holo-card px-5 py-3 flex items-center gap-3">
            <span className="text-lg">⚡</span>
            <div>
              <p className="text-xs text-cyan-300 font-mono">Action</p>
              <p className="text-sm text-gray-200">{actionFeedback}</p>
            </div>
          </div>
        </div>

        {/* Top bar */}
        <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${listening ? "bg-green-500 recording-indicator" : thinking ? "bg-purple-500 animate-pulse" : "bg-gray-700"}`} />
            <span className="status-text">{scanning ? "scanning device..." : statusText}</span>
            {confidence > 0 && <span className="text-[10px] font-mono text-gray-600">{confidence}%</span>}
          </div>
          <div className="flex items-center gap-3">
            {profileInterests.length > 0 && (
              <div className="hidden md:flex items-center gap-1.5">
                {profileInterests.slice(0, 3).map((t, i) => (
                  <span key={i} className="text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-purple-900/20 text-purple-500/70 border border-purple-800/20">{t}</span>
                ))}
              </div>
            )}
            {entityMemory && (
              <button
                onClick={() => setShowEntityPanel((o) => !o)}
                className={`text-[9px] font-mono px-2 py-1 rounded-lg border transition-colors ${
                  showEntityPanel ? "bg-cyan-900/20 border-cyan-700/30 text-cyan-500" : "bg-gray-900/30 border-gray-800/30 text-gray-600 hover:text-gray-400"
                }`}
                title="Entity memory & goals"
              >
                🧠 {entityState?.active_goals?.length || 0} goals
              </button>
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
            <div className="h-0.5 rounded-full bg-gray-800 overflow-hidden">
              <div className="h-full bg-gradient-to-r from-purple-600 to-cyan-500 transition-all duration-500" style={{ width: `${(taskStep / taskTotal) * 100}%` }} />
            </div>
            <p className="text-[9px] font-mono text-gray-700 text-center mt-1">step {taskStep}/{taskTotal}</p>
          </div>
        )}

        {/* Center content */}
        <div className="flex-1 flex flex-col items-center justify-center">
          {/* Holographic neuron */}
          <div className="flex-shrink-0" style={{ marginTop: taskQuestion ? -80 : -40 }}>
            <HolographicNeuron listening={listening} speaking={thinking} onClick={handleOrbClick} />
          </div>

          {/* Suggestions */}
          {showSuggestions && messages.length <= 1 && (
            <div className="mt-6 max-w-lg w-full px-6">
              <p className="text-[10px] font-mono text-gray-700 text-center mb-3 tracking-[0.2em] uppercase">try saying</p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.slice(0, 8).map((s) => (
                  <button
                    key={s}
                    onClick={() => pickSuggestion(s)}
                    className="text-[11px] font-mono px-3 py-1.5 rounded-full bg-gray-900/60 border border-gray-800/50 text-gray-500 hover:text-purple-300 hover:border-purple-700/40 hover:bg-purple-900/10 transition-all duration-200"
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
              <p className="text-[10px] font-mono text-cyan-400 text-center mb-2 tracking-[0.2em] uppercase">strategies</p>
              <div className="space-y-2">
                {strategies.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => pickStrategy(i)}
                    className={`w-full text-left p-3 rounded-xl border transition-all duration-200 ${
                      selectedStrategy === i
                        ? "bg-purple-900/20 border-purple-600/40"
                        : "bg-gray-900/40 border-gray-800/40 hover:border-purple-700/30 hover:bg-purple-900/10"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-mono text-purple-300">{s.name}</span>
                      <span className="text-[9px] font-mono text-gray-600 bg-gray-800/50 px-1.5 py-0.5 rounded">
                        complexity {s.complexity}/10
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-500 font-mono mb-1.5">{s.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {s.pros.slice(0, 2).map((p, pi) => (
                        <span key={pi} className="text-[8px] font-mono text-green-500/60 bg-green-900/10 px-1.5 py-0.5 rounded-full">+ {p}</span>
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
              <p className="text-[10px] font-mono text-purple-500/70 text-center mb-2 tracking-[0.2em] uppercase">follow up</p>
              <div className="flex flex-wrap justify-center gap-2">
                {followUpQuestions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleFollowUp(q)}
                    className="text-[10px] font-mono px-2.5 py-1.5 rounded-full bg-gray-900/50 border border-gray-800/40 text-gray-500 hover:text-purple-400 hover:border-purple-700/30 hover:bg-purple-900/10 transition-all"
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
              <p className="text-[10px] font-mono text-amber-500/50 text-center mb-1.5 tracking-[0.2em] uppercase">proactive</p>
              <div className="flex flex-wrap justify-center gap-2">
                {proactiveSuggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleProactive(s)}
                    className="text-[9px] font-mono px-2 py-1 rounded-full bg-amber-900/10 border border-amber-800/20 text-amber-600/60 hover:text-amber-400 hover:border-amber-700/30 transition-all"
                  >
                    {s.length > 45 ? s.slice(0, 45) + "..." : s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Entity Memory Panel */}
        {showEntityPanel && entityState && (
          <div className="absolute bottom-40 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
            <div className="holo-card px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-mono text-cyan-400 tracking-wider">entity state</p>
                <button onClick={() => setShowEntityPanel(false)} className="text-[9px] text-gray-700 hover:text-gray-400">close</button>
              </div>
              <div className="text-[9px] font-mono text-gray-500 space-y-1 max-h-40 overflow-y-auto">
                <p className="text-gray-400">interactions: {entityState.interaction_count}</p>
                {entityState.active_goals?.length > 0 && (
                  <div>
                    <p className="text-purple-400/70 mt-1">active goals ({entityState.active_goals.length}):</p>
                    {entityState.active_goals.map((g, i) => (
                      <div key={i} className="flex items-center gap-2 ml-2">
                        <span className="w-1 h-1 rounded-full bg-purple-500/50" />
                        <span>{g.goal}</span>
                        <span className="text-gray-700">p{g.priority}</span>
                      </div>
                    ))}
                  </div>
                )}
                {Object.keys(entityState.preferences).length > 0 && (
                  <div>
                    <p className="text-amber-400/70 mt-1">preferences:</p>
                    {Object.entries(entityState.preferences).slice(0, 5).map(([k, v]) => (
                      <div key={k} className="ml-2 text-gray-600">{k}: {v.value}</div>
                    ))}
                  </div>
                )}
                <p className="text-gray-700/50 mt-1 text-[8px] leading-relaxed">{entityMemory.slice(0, 300)}</p>
              </div>
            </div>
          </div>
        )}

        {/* Task follow-up */}
        {taskQuestion && (
          <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
            <div className="holo-card px-6 py-4">
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
                  className="flex-1 bg-gray-800/50 border border-gray-700/50 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-700 outline-none focus:border-purple-600/50 transition-colors"
                  autoFocus
                />
                <button onClick={sendText} className="px-4 py-2.5 bg-purple-600/10 border border-purple-600/30 rounded-lg text-sm text-purple-400 hover:bg-purple-600/20 transition-colors whitespace-nowrap">Send</button>
              </div>
            </div>
          </div>
        )}

        {/* Task result */}
        {taskResult && (
          <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
            <div className="holo-card px-6 py-4">
              <p className="text-[10px] font-mono text-green-400 tracking-wider mb-1">Task complete</p>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">{taskResult}</p>
              {Object.keys(collectedInfo).length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-800/50">
                  {Object.entries(collectedInfo).map(([k, v]) => (
                    <p key={k} className="text-xs text-gray-500"><span className="text-purple-400">{k}:</span> {v}</p>
                  ))}
                </div>
              )}
              <button onClick={() => setTaskResult(null)} className="mt-3 text-[10px] text-gray-700 hover:text-gray-400 font-mono tracking-wider">Dismiss</button>
            </div>
          </div>
        )}

        {/* Text input */}
        {!taskQuestion && (
          <div className={`absolute bottom-16 left-1/2 -translate-x-1/2 z-20 transition-all duration-300 ${showInput ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"}`}>
            <div className="glass-strong rounded-full px-5 py-3 w-96 flex items-center gap-2 glow-purple">
              <input ref={inputRef} type="text" value={textInput} onChange={(e) => setTextInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") sendText(); }} placeholder="Ask Jason anything..." className="bg-transparent text-sm text-gray-200 placeholder-gray-700 outline-none flex-1" />
              <button onClick={sendText} className="text-purple-500 hover:text-purple-400 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" /></svg>
              </button>
            </div>
          </div>
        )}

        {/* Live transcript footer */}
        {listening && interim && (
          <div className="fixed bottom-0 left-0 right-0 z-20 p-4 pointer-events-none">
            <div className="max-w-lg mx-auto">
              <div className="holo-card px-4 py-2.5 text-center">
                <p className="text-sm text-cyan-300 font-mono cursor-blink">{interim}</p>
                {confidence > 0 && <div className="mt-1.5 confidence-bar" style={{ width: `${confidence}%` }} />}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── RIGHT: Simulation panel ──────────────────────────── */}
      {simTask && (
        <div className="flex-[2] relative min-w-0 border-l border-white/5 overflow-hidden">
          <SimulationPanel task={simTask} active={true} />
        </div>
      )}

      <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)} summary={profileSummary} interests={profileInterests} />
    </div>
  );
}
