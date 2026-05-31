"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import HolographicNeuron from "@/components/HolographicNeuron";
import Sidebar from "@/components/Sidebar";
import { textChat, createReminder, listReminders } from "@/lib/api";

interface Message {
  role: string;
  content: string;
}

interface Reminder {
  id: string;
  title: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [showReminders, setShowReminders] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);

  useEffect(() => {
    synthRef.current = window.speechSynthesis;
  }, []);

  // Load reminders
  useEffect(() => {
    (async () => {
      try {
        const r = await listReminders();
        setReminders(r.reminders.filter((rm: any) => !rm.completed).slice(0, 5));
      } catch {}
    })();
  }, []);

  // ── Web Speech API: Speech-to-Text ─────────────────────────
  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setShowInput(true);
      setTimeout(() => inputRef.current?.focus(), 100);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setListening(false);
      handleQuery(text);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  // ── Web Speech API: Text-to-Speech ─────────────────────────
  const speak = useCallback((text: string) => {
    const synth = synthRef.current;
    if (!synth) return;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 0.9;
    synth.speak(utterance);
  }, []);

  // ── Send query ─────────────────────────────────────────────
  const handleQuery = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setMessages((p) => [...p, { role: "user", content: text }]);
    setSidebarOpen(true);
    setThinking(true);
    try {
      const res = await textChat(text);
      const reply = res.text;
      setMessages((p) => [...p, { role: "assistant", content: reply }]);
      speak(reply);

      // Auto-create reminders from certain patterns
      const lower = text.toLowerCase();
      if (res.reminder) {
        await createReminder(res.reminder.title, res.reminder.description || text, res.reminder.due_date || "");
        const r = await listReminders();
        setReminders(r.reminders.filter((rm: any) => !rm.completed).slice(0, 5));
        setShowReminders(true);
        setTimeout(() => setShowReminders(false), 5000);
      }
    } catch {
      setMessages((p) => [...p, { role: "assistant", content: "(backend unreachable)" }]);
    }
    setThinking(false);
  }, [speak]);

  // ── Text input send ────────────────────────────────────────
  const sendText = useCallback(async () => {
    const txt = textInput.trim();
    if (!txt) return;
    setTextInput("");
    setShowInput(false);
    handleQuery(txt);
  }, [textInput, handleQuery]);

  // ── Orb click ──────────────────────────────────────────────
  const handleOrbClick = useCallback(() => {
    if (listening) stopListening();
    else startListening();
  }, [listening, startListening, stopListening]);

  // ── Keyboard ───────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && !showInput && !listening) {
        e.preventDefault();
        setShowInput(true);
        setTimeout(() => inputRef.current?.focus(), 100);
      }
      if (e.key === "Escape") { setShowInput(false); stopListening(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showInput, listening, stopListening]);

  const statusText =
    listening ? "listening — tap orb to stop" :
    thinking ? "jason is thinking..." :
    showInput ? "type and press Enter" :
    "tap the orb or press / to talk";

  return (
    <div className="relative h-screen w-full overflow-hidden bg-gray-950">
      {/* Starfield */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="stars" /><div className="stars2" /><div className="stars3" />
      </div>

      {/* Reminder toast */}
      <div className={`absolute top-20 left-1/2 -translate-x-1/2 z-30 transition-all duration-500 ${
        showReminders ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4 pointer-events-none"
      }`}>
        <div className="glass rounded-xl px-5 py-3 flex items-center gap-3 glow-purple">
          <span className="text-lg">⏰</span>
          <div>
            <p className="text-xs text-purple-300 font-mono">Reminder created</p>
            <p className="text-sm text-gray-200">{reminders[0]?.title}</p>
          </div>
        </div>
      </div>

      {/* Top-right buttons */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
        <button
          onClick={() => setSidebarOpen((o) => !o)}
          className="text-gray-600 hover:text-gray-300 transition-colors p-2"
          title="Transcript"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
          </svg>
        </button>
      </div>

      {/* Center neuron */}
      <div className="absolute inset-0 flex items-center justify-center">
        <HolographicNeuron
          listening={listening}
          speaking={thinking}
          onClick={handleOrbClick}
        />
      </div>

      {/* Reminder chips */}
      {reminders.length > 0 && (
        <div className="absolute bottom-32 left-1/2 -translate-x-1/2 z-10 flex gap-2 max-w-md flex-wrap justify-center">
          {reminders.map((r) => (
            <div key={r.id} className="glass rounded-full px-3 py-1 text-xs text-gray-400 font-mono truncate max-w-[160px]">
              ⏰ {r.title}
            </div>
          ))}
        </div>
      )}

      {/* Text input */}
      <div className={`absolute bottom-20 left-1/2 -translate-x-1/2 z-20 transition-all duration-300 ${
        showInput ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"
      }`}>
        <div className="glass rounded-full px-5 py-3 w-96 flex items-center gap-2 glow-purple">
          <input
            ref={inputRef}
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
            placeholder="Ask Jason anything..."
            className="bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none flex-1"
          />
          <button onClick={sendText} className="text-purple-400 hover:text-purple-300 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Sidebar */}
      <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Status */}
      <footer className="absolute bottom-0 left-0 right-0 z-10 p-6">
        <div className="flex items-center justify-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full transition-colors ${listening || thinking ? "bg-purple-500" : "bg-gray-700"}`} />
          <span className="text-xs font-mono text-gray-600">{statusText}</span>
        </div>
      </footer>
    </div>
  );
}
