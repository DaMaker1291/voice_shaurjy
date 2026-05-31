"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Orb from "@/components/Orb";
import Sidebar from "@/components/Sidebar";
import { textChat } from "@/lib/api";

interface Message {
  role: string;
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef(window.speechSynthesis);

  // ── Web Speech API: Speech-to-Text ─────────────────────────
  const startListening = useCallback(() => {
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
    synthRef.current.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 0.9;
    const voices = synthRef.current.getVoices();
    const deep = voices.find((v) => v.name.includes("Female") || v.name.includes("Google UK"));
    if (deep) utterance.voice = deep;
    synthRef.current.speak(utterance);
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
    } catch {
      setMessages((p) => [...p, { role: "assistant", content: "(backend unreachable — ensure uvicorn is running)" }]);
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
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  }, [listening, startListening, stopListening]);

  // ── Keyboard shortcut ──────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && !showInput && !listening) {
        e.preventDefault();
        setShowInput(true);
        setTimeout(() => inputRef.current?.focus(), 100);
      }
      if (e.key === "Escape") {
        setShowInput(false);
        stopListening();
      }
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

      {/* Sidebar toggle */}
      <button
        onClick={() => setSidebarOpen((o) => !o)}
        className="absolute top-4 right-4 z-10 text-gray-600 hover:text-gray-300 transition-colors"
        title="Toggle transcript"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
        </svg>
      </button>

      {/* Center orb */}
      <div className="absolute inset-0 flex items-center justify-center" style={{ marginTop: showInput ? -30 : 0 }}>
        <Orb
          listening={listening}
          speaking={thinking}
          onClick={handleOrbClick}
        />
      </div>

      {/* Text input (slide-in) */}
      <div
        className={`absolute bottom-20 left-1/2 -translate-x-1/2 z-20 transition-all duration-300 ${
          showInput
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-4 pointer-events-none"
        }`}
      >
        <div className="flex items-center gap-2 bg-gray-900/80 backdrop-blur-xl border border-gray-800 rounded-full px-4 py-2 w-96">
          <input
            ref={inputRef}
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") sendText(); }}
            placeholder="Ask Jason anything..."
            className="bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none flex-1"
          />
          <button
            onClick={sendText}
            className="text-purple-400 hover:text-purple-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Sidebar */}
      <Sidebar messages={messages} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Bottom status */}
      <footer className="absolute bottom-0 left-0 right-0 z-10 p-6">
        <div className="flex items-center justify-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full transition-colors ${listening || thinking ? "bg-green-500" : "bg-gray-700"}`} />
          <span className="text-xs font-mono text-gray-600">{statusText}</span>
        </div>
      </footer>
    </div>
  );
}
