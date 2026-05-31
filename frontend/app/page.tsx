"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import HolographicNeuron from "@/components/HolographicNeuron";
import Sidebar from "@/components/Sidebar";
import { textChat } from "@/lib/api";

interface Message {
  role: string;
  content: string;
}

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const taskInputRef = useRef<HTMLInputElement>(null);
  const retryCountRef = useRef(0);

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);

  // Scan device on startup
  useEffect(() => {
    (async () => {
      setScanning(true);
      try {
        await fetch(`${BASE}/api/device/scan?user_id=local`, { method: "POST" });
        setMessages((p) => [...p, { role: "assistant", content: "Device scanned. I know your files, calendar, and system. Ask me anything." }]);
      } catch {}
      setScanning(false);
    })();
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
      // Pre-load then play immediately
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

  // ── Handle task response from user ─────────────────────────
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

  // ── Handle query (new message or task answer) ──────────────
  const handleQuery = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setMessages((p) => [...p, { role: "user", content: text }]);
    setSidebarOpen(true);
    setThinking(true);
    try {
      const res = await textChat(text);
      const reply = res.text;

      // Show action feedback
      if (res.action) {
        setActionFeedback(reply);
        setTimeout(() => setActionFeedback(null), 4000);
      } else if (!res.task) {
        speak(reply);
      }

      // Task flow
      if (res.task) {
        _handleTaskResponse(res.task);
      } else {
        setMessages((p) => [...p, { role: "assistant", content: reply }]);
      }
    } catch {
      setMessages((p) => [...p, { role: "assistant", content: "(backend unreachable)" }]);
    }
    setThinking(false);
  }, [speak]);

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
    } else if (data.type === "notify") {
      setActionFeedback(data.text);
      setTaskStep(data.step || 0);
      setTaskTotal(data.total || 0);
      if (data.next_action) {
        // Will show next ask automatically
      }
      setTimeout(() => setActionFeedback(null), 3000);
    } else if (data.type === "complete") {
      setTaskSession(null);
      setTaskQuestion(null);
      setTaskResult(data.text);
      setCollectedInfo(data.collected || {});
      setMessages((p) => [...p, { role: "assistant", content: `✅ ${data.text}` }]);
      speak("Task complete!");
    } else if (data.type === "error") {
      setMessages((p) => [...p, { role: "assistant", content: `⚠️ ${data.text}` }]);
      setTaskSession(null);
      setTaskQuestion(null);
    }
  }, [taskSession, speak]);

  // ── Speech (improved) ──────────────────────────────────────
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

      // Auto-stop after 1.5s of silence once we have final text
      if (final) {
        clearTimeout((r as any)._silenceTimer);
        (r as any)._silenceTimer = setTimeout(() => {
          r.stop();
          const text = final.trim();
          if (!text) return;
          setListening(false);
          setInterim("");
          retryCountRef.current = 0;
          if (taskQuestion) sendTaskResponse(text);
          else handleQuery(text);
        }, 1500);
      }
    };

    r.onerror = (e: any) => {
      if (e.error === "not-allowed") {
        setInterim("Microphone access denied");
        setListening(false);
        return;
      }
      if (e.error === "no-speech" && retryCountRef.current < 2) {
        retryCountRef.current++;
        r.start();
        return;
      }
      setListening(false);
      setInterim("");
    };

    r.onend = () => {
      setListening(false);
      if (!final) setInterim("");
    };

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

  // ── Text send ──────────────────────────────────────────────
  const sendText = useCallback(() => {
    const txt = textInput.trim();
    if (!txt) return;
    setTextInput("");
    if (taskQuestion) { sendTaskResponse(txt); setShowInput(false); }
    else { setShowInput(false); handleQuery(txt); }
  }, [textInput, taskQuestion, handleQuery, sendTaskResponse]);

  const handleOrbClick = useCallback(() => {
    if (listening) stopListening();
    else startListening();
  }, [listening, startListening, stopListening]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "/" && !showInput && !listening) { e.preventDefault(); setShowInput(true); setTimeout(() => inputRef.current?.focus(), 100); }
      if (e.key === "Escape") { setShowInput(false); stopListening(); }
      if (e.key === "Enter" && taskQuestion && !showInput) { sendTaskResponse(textInput); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [showInput, listening, stopListening, taskQuestion, textInput, sendTaskResponse]);

  const statusText = taskQuestion ? `step ${taskStep}/${taskTotal} — answering...` :
    listening ? (interim ? `"${interim}"` : "listening...") :
    thinking ? "jason is thinking..." :
    showInput ? "type and press Enter" : "tap the orb or press / to talk";

  return (
    <div className="relative h-screen w-full overflow-hidden bg-gray-950">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="stars" /><div className="stars2" /><div className="stars3" />
      </div>

      {/* Action toast */}
      <div className={`absolute top-20 left-1/2 -translate-x-1/2 z-30 transition-all duration-500 ${actionFeedback ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4 pointer-events-none"}`}>
        <div className="glass rounded-xl px-5 py-3 flex items-center gap-3 glow-purple">
          <span className="text-lg">⚡</span>
          <div>
            <p className="text-xs text-cyan-300 font-mono">Action executed</p>
            <p className="text-sm text-gray-200">{actionFeedback}</p>
          </div>
        </div>
      </div>

      {/* Reminder toast — removed; AI learns from device data now */}

      {/* Top-right */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
        {scanning && <span className="text-[10px] font-mono text-purple-500 animate-pulse">scanning device...</span>}
        <button onClick={() => setSidebarOpen((o) => !o)} className="text-gray-600 hover:text-gray-300 transition-colors p-2" title="Transcript">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
          </svg>
        </button>
      </div>

      {/* Center neuron */}
      <div className="absolute inset-0 flex items-center justify-center" style={{ marginTop: taskQuestion ? -60 : 0 }}>
        <HolographicNeuron listening={listening} speaking={thinking} onClick={handleOrbClick} />
      </div>

      {/* Task progress bar */}
      {taskTotal > 0 && taskStep > 0 && (
        <div className="absolute top-28 left-1/2 -translate-x-1/2 z-10 w-64">
          <div className="h-1 rounded-full bg-gray-800 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-purple-600 to-cyan-500 transition-all duration-500" style={{ width: `${(taskStep / taskTotal) * 100}%` }} />
          </div>
          <p className="text-[10px] font-mono text-gray-600 text-center mt-1">Step {taskStep} of {taskTotal}</p>
        </div>
      )}

      {/* Task follow-up question */}
      {taskQuestion && (
        <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
          <div className="glass rounded-2xl px-6 py-4 glow-purple">
            <p className="text-xs text-purple-400 font-mono mb-1">Jason needs to know</p>
            <p className="text-sm text-gray-200 mb-3">{taskQuestion}</p>
            <div className="flex gap-2">
              <input
                ref={taskInputRef}
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
                placeholder="Type your answer..."
                className="flex-1 bg-gray-800/80 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 outline-none focus:border-purple-500/50"
                autoFocus
              />
              <button onClick={sendText} className="px-4 py-2.5 bg-purple-600/20 border border-purple-600/30 rounded-lg text-sm text-purple-300 hover:bg-purple-600/30 transition-colors whitespace-nowrap">
                Send
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task result panel */}
      {taskResult && (
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-20 w-full max-w-lg px-4">
          <div className="glass rounded-2xl px-6 py-4 glow-purple">
            <p className="text-xs text-green-400 font-mono mb-1">✅ Task complete</p>
            <p className="text-sm text-gray-300 whitespace-pre-wrap">{taskResult}</p>
            {Object.keys(collectedInfo).length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <p className="text-[10px] text-gray-600 font-mono mb-1">Collected info</p>
                {Object.entries(collectedInfo).map(([k, v]) => (
                  <p key={k} className="text-xs text-gray-400"><span className="text-purple-400">{k}:</span> {v}</p>
                ))}
              </div>
            )}
            <button onClick={() => setTaskResult(null)} className="mt-3 text-xs text-gray-600 hover:text-gray-400 font-mono">Dismiss</button>
          </div>
        </div>
      )}

      {/* Reminder chips — removed; AI has full device context now */}

      {/* Text input (fallback) */}
      {!taskQuestion && (
        <div className={`absolute bottom-20 left-1/2 -translate-x-1/2 z-20 transition-all duration-300 ${showInput ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"}`}>
          <div className="glass rounded-full px-5 py-3 w-96 flex items-center gap-2 glow-purple">
            <input ref={inputRef} type="text" value={textInput} onChange={(e) => setTextInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") sendText(); }} placeholder="Ask Jason anything..." className="bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none flex-1" />
            <button onClick={sendText} className="text-purple-400 hover:text-purple-300 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" /></svg>
            </button>
          </div>
        </div>
      )}

      <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <footer className="absolute bottom-0 left-0 right-0 z-10 p-6">
        {/* Live transcript */}
        {listening && interim && (
          <div className="mb-4 text-center max-w-lg mx-auto">
            <div className="glass rounded-xl px-4 py-2">
              <p className="text-sm text-cyan-300 font-mono">{interim}</p>
              {confidence > 0 && (
                <div className="mt-1.5 h-0.5 rounded-full bg-gray-800 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-purple-600 to-cyan-400 transition-all duration-200" style={{ width: `${confidence}%` }} />
                </div>
              )}
            </div>
          </div>
        )}
        <div className="flex items-center justify-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full transition-colors ${listening ? "bg-green-500 animate-pulse" : thinking ? "bg-purple-500" : "bg-gray-700"}`} />
          <span className="text-xs font-mono text-gray-600">{statusText}</span>
        </div>
      </footer>
    </div>
  );
}
