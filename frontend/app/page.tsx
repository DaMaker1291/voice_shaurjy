"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Navbar from "@/components/Navbar";

interface Message { role: string; content: string; link?: string }

const BASE = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

const SUGGESTIONS = [
  "scan my network", "turn off all lights", "open VS Code",
  "what's my CPU usage?", "volume to 60%", "search for weather",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [textInput, setTextInput] = useState("");
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [taskQuestion, setTaskQuestion] = useState<string | null>(null);
  const [taskSession, setTaskSession] = useState<string | null>(null);
  const [taskStep, setTaskStep] = useState(0);
  const [taskTotal, setTaskTotal] = useState(0);
  const [voice] = useState("en-GB-RyanNeural");

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { synthRef.current = window.speechSynthesis; }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const speak = useCallback(async (text: string) => {
    setSpeaking(true);
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
  }, [voice]);

  const sendText = useCallback(async () => {
    const text = textInput.trim(); if (!text) return;
    setTextInput(""); setShowSuggestions(false);
    setMessages(p => [...p, { role: "user", content: text }]);
    setThinking(true);

    // Handle task follow-up
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
        } else {
          setTaskQuestion(null); setTaskSession(null);
          setMessages(p => [...p, { role: "assistant", content: data.text || "Task complete." }]);
        }
      } catch (e: any) {
        setMessages(p => [...p, { role: "assistant", content: `Error: ${e.message}` }]);
      }
      setThinking(false); return;
    }

    // Normal message — try entity process (which includes router internally)
    try {
      const res = await fetch(`${BASE}/api/entity/process`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: text, user_id: "local" }),
      });
      const data = await res.json();
      const reply = data?.text || data?.message || "Acknowledged.";
      setMessages(p => [...p, { role: "assistant", content: reply }]);
      if (data?.type === "ask" && data?.session_id) {
        setTaskSession(data.session_id); setTaskQuestion(data.question);
        setTaskStep(data.step || 0); setTaskTotal(data.total || 0);
      }
      if (reply.length < 300) speak(reply).catch(() => {});
    } catch (err: any) {
      setMessages(p => [...p, { role: "assistant", content: `Connection error: ${err.message}` }]);
    }
    setThinking(false);
  }, [textInput, taskSession, taskQuestion, speak]);

  const handleVoiceClick = useCallback(() => {
    if (listening) { recognitionRef.current?.stop(); setListening(false); return; }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { alert("Speech recognition not supported in this browser."); return; }
    const rec = new SR();
    rec.continuous = false; rec.interimResults = true; rec.lang = "en-GB";
    rec.onresult = (e: any) => {
      let interim_t = "", final_t = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final_t += e.results[i][0].transcript;
        else interim_t += e.results[i][0].transcript;
      }
      setInterim(interim_t || final_t);
      if (final_t) { setTextInput(final_t); setInterim(""); }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    rec.start(); setListening(true);
  }, [listening]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg-primary)", color: "var(--text-primary)", fontFamily: "var(--font-inter), system-ui, sans-serif" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .msg-animate { animation: fade-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) both; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.2); border-radius: 2px; }
      `}</style>

      <div className="ambient-glow" />
      <Navbar />

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 20px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", padding: "80px 0 40px", animation: "fade-in 0.5s ease both" }}>
              <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.15 }}>⚡</div>
              <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>JARVIS</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Speak or type a command</div>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className="msg-animate" style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", marginBottom: 12 }}>
              <div style={{
                maxWidth: "75%", padding: "10px 16px", fontSize: 14, lineHeight: 1.6, borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                background: msg.role === "user" ? "rgba(139,92,246,0.08)" : "var(--bg-secondary)",
                border: `1px solid ${msg.role === "user" ? "rgba(139,92,246,0.15)" : "var(--border-subtle)"}`,
                color: msg.role === "user" ? "var(--text-primary)" : "var(--text-secondary)",
              }}>
                {msg.content}
                {msg.link && <a href={msg.link} target="_blank" rel="noopener noreferrer" style={{ display: "block", marginTop: 4, fontSize: 11, color: "var(--accent)" }}>{msg.link.slice(0, 40)}…</a>}
              </div>
            </div>
          ))}
          {thinking && (
            <div className="msg-animate" style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
              <div style={{ padding: "12px 18px", background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: "16px 16px 16px 4px" }}>
                <div style={{ display: "flex", gap: 4 }}>
                  {[0, 0.2, 0.4].map((d, i) => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", animation: `pulse-dot 1.2s infinite ${d}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Suggestions */}
      {showSuggestions && messages.length === 0 && (
        <div style={{ padding: "0 20px 12px", maxWidth: 720, margin: "0 auto", width: "100%", display: "flex", flexWrap: "wrap", gap: 6 }}>
          {SUGGESTIONS.map(s => (
            <button key={s} onClick={() => { setTextInput(s); setShowSuggestions(false); inputRef.current?.focus(); }}
              style={{ padding: "6px 14px", borderRadius: 20, fontSize: 12, cursor: "pointer", background: "var(--bg-secondary)", color: "var(--text-muted)", border: "1px solid var(--border-subtle)", transition: "all 0.15s" }}>
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Task question */}
      {taskQuestion && (
        <div style={{ padding: "0 20px 12px", maxWidth: 720, margin: "0 auto", width: "100%" }}>
          <div style={{ padding: "10px 14px", borderRadius: 10, background: "var(--accent-dim)", border: "1px solid rgba(139,92,246,0.15)" }}>
            <div style={{ fontSize: 10, color: "var(--accent)", marginBottom: 4, fontWeight: 500 }}>Step {taskStep}/{taskTotal}</div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{taskQuestion}</div>
          </div>
        </div>
      )}

      {/* Interim speech */}
      {listening && interim && (
        <div style={{ padding: "0 20px 8px", maxWidth: 720, margin: "0 auto", width: "100%" }}>
          <div style={{ fontSize: 12, color: "var(--accent)", opacity: 0.7, fontFamily: "monospace" }}>{interim}</div>
        </div>
      )}

      {/* Input */}
      <div style={{ padding: "12px 20px 20px", maxWidth: 720, margin: "0 auto", width: "100%" }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8, padding: "10px 14px", borderRadius: 14, background: "var(--bg-secondary)", border: "1px solid var(--border-default)", transition: "border-color 0.15s" }}>
          <textarea
            ref={inputRef}
            value={textInput}
            onChange={e => { setTextInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px"; }}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(); } }}
            placeholder="Issue a command..."
            rows={1}
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", fontSize: 14, color: "var(--text-primary)", resize: "none", lineHeight: 1.5, maxHeight: 100, fontFamily: "inherit" }}
          />
          <button onClick={handleVoiceClick} style={{ padding: 6, borderRadius: 8, background: listening ? "var(--accent-dim)" : "transparent", color: listening ? "var(--accent)" : "var(--text-muted)", border: "none", cursor: "pointer", transition: "all 0.15s", flexShrink: 0 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>
          <button onClick={sendText} disabled={!textInput.trim()} style={{
            width: 34, height: 34, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", border: "none", cursor: "pointer", flexShrink: 0, transition: "all 0.15s",
            background: textInput.trim() ? "var(--accent)" : "var(--bg-tertiary)",
            color: textInput.trim() ? "#fff" : "var(--text-muted)",
            opacity: textInput.trim() ? 1 : 0.5,
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
