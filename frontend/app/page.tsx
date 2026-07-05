"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";

const TopBar = dynamic(() => import("@/components/cockpit/TopBar"), { ssr: false });
const AgentGraph = dynamic(() => import("@/components/cockpit/AgentGraph"), { ssr: false });
const TelemetryPanel = dynamic(() => import("@/components/cockpit/TelemetryPanel"), { ssr: false });
const InterceptBar = dynamic(() => import("@/components/cockpit/InterceptBar"), { ssr: false });

interface Message { role: string; content: string; ts: number }

const BASE = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

const SUGGESTIONS = ["scan network", "open VS Code", "turn off lights", "CPU usage"];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [inputState, setInputState] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (thinking) setInputState("thinking");
    else if (listening) setInputState("listening");
    else setInputState("idle");
  }, [thinking, listening]);

  const send = useCallback(async () => {
    const text = input.trim(); if (!text) return;
    setInput(""); setShowSuggestions(false);
    setMessages(p => [...p, { role: "user", content: text, ts: Date.now() }]);
    setThinking(true);

    try {
      const res = await fetch(`${BASE}/api/entity/process`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: text, user_id: "local" }),
      });
      const data = await res.json();
      const reply = data?.text || data?.message || "Acknowledged.";
      setMessages(p => [...p, { role: "assistant", content: reply, ts: Date.now() }]);
    } catch (err: any) {
      setMessages(p => [...p, { role: "assistant", content: `Error: ${err.message}`, ts: Date.now() }]);
    }
    setThinking(false);
  }, [input]);

  const handleVoice = useCallback(() => {
    if (listening) { setListening(false); return; }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.continuous = false; rec.interimResults = true; rec.lang = "en-GB";
    rec.onresult = (e: any) => {
      let interim = "", final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      setInterim(interim || final);
      if (final) { setInput(final); setInterim(""); }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    rec.start(); setListening(true);
  }, [listening]);

  const handleApprove = async (id: string) => { await fetch(`${BASE}/api/sovereign/approve/${id}`, { method: "POST" }); };
  const handleDeny = async (id: string) => { await fetch(`${BASE}/api/sovereign/deny/${id}`, { method: "POST" }); };

  const inputBorderColor = inputState === "listening" ? "var(--neon-green)" : inputState === "thinking" ? "var(--amber)" : "var(--border)";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--void)", color: "var(--text-primary)", overflow: "hidden" }}>
      <TopBar />

      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        {/* Left Panel — Agent Graph */}
        <div style={{ width: 400, borderRight: "1px solid var(--border)", flexShrink: 0, overflow: "hidden" }}>
          <AgentGraph />
        </div>

        {/* Center Canvas — Command Omni-Box */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", position: "relative", overflow: "hidden" }}>
          {/* Grid background */}
          <div className="grid-bg" style={{ position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.5 }} />

          {/* Scan line */}
          <div className="scan-line" style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />

          {/* Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 32px", position: "relative", zIndex: 1 }}>
            {messages.length === 0 && (
              <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
                {/* Kinetic Orb */}
                <div style={{ position: "relative", width: 80, height: 80 }}>
                  <div style={{
                    width: 80, height: 80, borderRadius: "50%",
                    background: "radial-gradient(circle, rgba(0,255,102,0.12) 0%, transparent 70%)",
                    border: "1px solid rgba(0,255,102,0.15)",
                    animation: "orb-breathe 3s ease-in-out infinite",
                    boxShadow: "0 0 40px rgba(0,255,102,0.08)",
                  }} />
                  <div style={{
                    position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
                    width: 40, height: 40, borderRadius: "50%",
                    background: "radial-gradient(circle, rgba(0,255,102,0.2) 0%, transparent 70%)",
                    animation: "orb-breathe 3s ease-in-out infinite 0.5s",
                  }} />
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em" }}>AWAITING INPUT</div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className="animate-fade" style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", marginBottom: 12 }}>
                <div style={{
                  maxWidth: "70%", padding: "10px 16px", fontSize: 13, lineHeight: 1.6,
                  fontFamily: "var(--font-mono)",
                  borderRadius: msg.role === "user" ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                  background: msg.role === "user" ? "rgba(0,255,102,0.06)" : "var(--surface)",
                  border: `1px solid ${msg.role === "user" ? "rgba(0,255,102,0.12)" : "var(--border)"}`,
                  color: msg.role === "user" ? "var(--text-primary)" : "var(--text-secondary)",
                }}>
                  {msg.role === "assistant" && (
                    <div style={{ fontSize: 8, color: "var(--neon-green)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", marginBottom: 4, opacity: 0.6 }}>JARVIS</div>
                  )}
                  {msg.content}
                </div>
              </div>
            ))}

            {thinking && (
              <div className="animate-fade" style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
                <div style={{ padding: "12px 18px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px 8px 8px 2px" }}>
                  <div style={{ display: "flex", gap: 4 }}>
                    {[0, 0.2, 0.4].map((d, i) => (
                      <div key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--neon-green)", animation: `glow-pulse 1.2s infinite ${d}s` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions */}
          {showSuggestions && messages.length === 0 && (
            <div style={{ padding: "0 32px 12px", display: "flex", flexWrap: "wrap", gap: 6, position: "relative", zIndex: 1 }}>
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => { setInput(s); setShowSuggestions(false); inputRef.current?.focus(); }}
                  style={{ padding: "5px 12px", borderRadius: 3, fontSize: 10, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--surface)", color: "var(--text-muted)", border: "1px solid var(--border)", transition: "all 0.15s", letterSpacing: "0.03em" }}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Interim speech */}
          {listening && interim && (
            <div style={{ padding: "0 32px 8px", position: "relative", zIndex: 1 }}>
              <div style={{ fontSize: 11, color: "var(--neon-green)", fontFamily: "var(--font-mono)", opacity: 0.7 }}>{interim}</div>
            </div>
          )}

          {/* Command Omni-Box */}
          <div style={{ padding: "12px 32px 20px", position: "relative", zIndex: 1 }}>
            <div style={{
              display: "flex", alignItems: "flex-end", gap: 8, padding: "10px 14px",
              background: "var(--surface)", borderRadius: 6,
              border: `1px solid ${inputBorderColor}`,
              transition: "border-color 0.3s",
              boxShadow: inputState === "listening" ? "var(--glow-green)" : inputState === "thinking" ? "var(--glow-amber)" : "none",
            }}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 80) + "px"; }}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder="Issue a command..."
                rows={1}
                style={{ flex: 1, background: "transparent", border: "none", outline: "none", fontSize: 13, color: "var(--text-primary)", resize: "none", lineHeight: 1.5, maxHeight: 80, fontFamily: "var(--font-mono)" }}
              />
              <button onClick={handleVoice} style={{
                padding: 6, borderRadius: 4, border: "none", cursor: "pointer", flexShrink: 0,
                background: listening ? "var(--neon-green-dim)" : "transparent",
                color: listening ? "var(--neon-green)" : "var(--text-muted)",
                transition: "all 0.15s",
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </button>
              <button onClick={send} disabled={!input.trim()} style={{
                width: 30, height: 30, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center",
                border: "none", cursor: "pointer", flexShrink: 0, transition: "all 0.15s",
                background: input.trim() ? "var(--neon-green)" : "var(--surface-raised)",
                color: input.trim() ? "#000" : "var(--text-muted)",
                opacity: input.trim() ? 1 : 0.4,
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel — Telemetry */}
        <div style={{ width: 320, borderLeft: "1px solid var(--border)", flexShrink: 0, overflow: "hidden" }}>
          <TelemetryPanel />
        </div>
      </div>

      <InterceptBar onApprove={handleApprove} onDeny={handleDeny} />
    </div>
  );
}
