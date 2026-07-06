"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";

const TopBar = dynamic(() => import("@/components/cockpit/TopBar"), { ssr: false });
const AgentGraph = dynamic(() => import("@/components/cockpit/AgentGraph"), { ssr: false });
const TelemetryPanel = dynamic(() => import("@/components/cockpit/TelemetryPanel"), { ssr: false });
const InterceptBar = dynamic(() => import("@/components/cockpit/InterceptBar"), { ssr: false });
const KineticOrb = dynamic(() => import("@/components/cockpit/KineticOrb"), { ssr: false });
const Markdown = dynamic(() => import("@/components/cockpit/Markdown"), { ssr: false });
const ExecutionOverlay = dynamic(() => import("@/components/cockpit/ExecutionOverlay"), { ssr: false });
const CommandPalette = dynamic(() => import("@/components/CommandPalette").then(m => m.CommandPalette), { ssr: false });
const ShortcutsModal = dynamic(() => import("@/components/ShortcutsModal"), { ssr: false });

interface Message { role: string; content: string; ts: number; agent?: string }

const BASE = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

const SUGGESTIONS = [
  { text: "scan network", icon: "📡" },
  { text: "open VS Code", icon: "💻" },
  { text: "turn off lights", icon: "💡" },
  { text: "CPU usage", icon: "📊" },
  { text: "screenshot", icon: "📷" },
  { text: "what time is it", icon: "🕐" },
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [inputState, setInputState] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [executing, setExecuting] = useState(false);
  const [execAgent, setExecAgent] = useState("OS");
  const [execTask, setExecTask] = useState("");
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const newChat = useCallback(() => {
    setMessages([]);
    setShowSuggestions(true);
    setInput("");
    setThinking(false);
    setExecuting(false);
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (thinking) setInputState("thinking");
    else if (listening) setInputState("listening");
    else setInputState("idle");
  }, [thinking, listening]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const cmd = e.metaKey || e.ctrlKey;
      if (cmd && e.key === "k") { e.preventDefault(); setShowCommandPalette(p => !p); }
      if (cmd && e.key === "1") { e.preventDefault(); window.location.href = "/"; }
      if (cmd && e.key === "2") { e.preventDefault(); window.location.href = "/agents"; }
      if (cmd && e.key === "3") { e.preventDefault(); window.location.href = "/sovereign"; }
      if (cmd && e.key === "4") { e.preventDefault(); window.location.href = "/feed"; }
      if (cmd && e.key === "/") { e.preventDefault(); inputRef.current?.focus(); }
      if (cmd && e.shiftKey && e.key === "?") { e.preventDefault(); setShowShortcuts(p => !p); }
      if (cmd && e.key === "Escape") { e.preventDefault(); newChat(); }
      if (e.key === "Escape") { setShowCommandPalette(false); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [newChat]);

  const send = useCallback(async () => {
    const text = input.trim(); if (!text) return;
    setInput(""); setShowSuggestions(false);
    const userMsg = { role: "user", content: text, ts: Date.now() };
    setMessages(p => [...p, userMsg]);
    setThinking(true);

    // Show execution overlay for device/system commands
    const lowerText = text.toLowerCase();
    const isDeviceCmd = /turn|light|plug|switch|lock|unlock|screenshot|open|volume|brightness/.test(lowerText);
    if (isDeviceCmd) {
      setExecuting(true);
      setExecAgent(/turn|light|plug|switch/.test(lowerText) ? "HAL" : /screenshot|open/.test(lowerText) ? "OS" : "CORE");
      setExecTask(text);
    }

    // Build conversation history for context
    const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));

    try {
      const res = await fetch(`${BASE}/api/entity/process`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: text, user_id: "local", history }),
      });
      const data = await res.json();
      let reply = data?.text || data?.message || "Acknowledged.";
      // Strip raw cockpit/system blocks that shouldn't be shown to user
      reply = reply.replace(/={3,} COCKPIT BLOCK =={3,}[\s\S]*?(?==={3,}|$)/g, "").trim();
      reply = reply.replace(/={3,} COCKPIT =={3,}[\s\S]*?={3,} END COCKPIT =={3,}/g, "").trim();
      reply = reply.replace(/\[System State\][\s\S]*?(?=\n[A-Z]|\n\n|$)/g, "").trim();
      reply = reply.replace(/\[Your State\][\s\S]*?(?=\n[A-Z]|\n\n|$)/g, "").trim();
      reply = reply.replace(/\[Memory\][\s\S]*?(?=\n[A-Z]|\n\n|$)/g, "").trim();
      if (!reply) reply = "Acknowledged.";
      const agent = data?.routing?.target_agent || data?.agent || "CORE";
      setMessages(p => [...p, { role: "assistant", content: reply, ts: Date.now(), agent }]);
    } catch (err: any) {
      setMessages(p => [...p, { role: "assistant", content: `Error: ${err.message}`, ts: Date.now() }]);
    }
    setThinking(false);
    setTimeout(() => setExecuting(false), 1500);
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
      <TopBar onNewChat={newChat} onCommandPalette={() => setShowCommandPalette(true)} />
      <CommandPalette open={showCommandPalette} onClose={() => setShowCommandPalette(false)} onCommand={(cmd) => { setInput(cmd); }} />
      {showShortcuts && <ShortcutsModal onClose={() => setShowShortcuts(false)} />}
      <ExecutionOverlay active={executing} agent={execAgent} task={execTask} />

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
              <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
                <KineticOrb size={300} />
                <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em" }}>AWAITING INPUT</div>
                <div style={{ fontSize: 9, color: "var(--text-muted)", opacity: 0.4, fontFamily: "var(--font-mono)" }}>Move mouse over orb to interact</div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className="animate-fade" style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", marginBottom: 12 }}>
                <div style={{ maxWidth: "75%" }}>
                  <div style={{
                    padding: "12px 16px", fontSize: 13, lineHeight: 1.6,
                    fontFamily: "var(--font-mono)",
                    borderRadius: msg.role === "user" ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                    background: msg.role === "user" ? "rgba(0,255,102,0.06)" : "var(--surface)",
                    border: `1px solid ${msg.role === "user" ? "rgba(0,255,102,0.12)" : "var(--border)"}`,
                    color: msg.role === "user" ? "var(--text-primary)" : "var(--text-secondary)",
                  }}>
                    {msg.role === "assistant" && (
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                        <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 4px rgba(0,255,102,0.4)" }} />
                        <span style={{ fontSize: 8, color: "var(--neon-green)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", opacity: 0.8 }}>JARVIS</span>
                        {msg.agent && (
                          <span style={{ fontSize: 7, padding: "1px 4px", borderRadius: 2, background: "var(--surface-raised)", border: "1px solid var(--border)", color: "var(--steel)", fontFamily: "var(--font-mono)" }}>{msg.agent}</span>
                        )}
                      </div>
                    )}
                    {msg.role === "assistant" ? (
                      <Markdown content={msg.content} />
                    ) : (
                      msg.content
                    )}
                  </div>
                  <div style={{ fontSize: 8, color: "var(--text-muted)", opacity: 0.4, marginTop: 3, fontFamily: "var(--font-mono)", textAlign: msg.role === "user" ? "right" : "left", padding: "0 4px" }}>
                    {new Date(msg.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              </div>
            ))}

            {thinking && (
              <div className="animate-fade" style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
                <div style={{ padding: "12px 18px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px 8px 8px 2px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ display: "flex", gap: 3 }}>
                      {[0, 0.2, 0.4].map((d, i) => (
                        <div key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--neon-green)", animation: `glow-pulse 1.2s infinite ${d}s` }} />
                      ))}
                    </div>
                    <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>processing...</span>
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
                <button key={s.text} onClick={() => { setInput(s.text); setShowSuggestions(false); inputRef.current?.focus(); }}
                  style={{ padding: "5px 12px", borderRadius: 3, fontSize: 10, fontFamily: "var(--font-mono)", cursor: "pointer", background: "var(--surface)", color: "var(--text-muted)", border: "1px solid var(--border)", transition: "all 0.15s", letterSpacing: "0.03em", display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ fontSize: 11 }}>{s.icon}</span>
                  {s.text}
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
            {/* Keyboard hints */}
            <div style={{ display: "flex", gap: 12, marginTop: 6, paddingLeft: 4 }}>
              {[
                { key: "⌘K", label: "Commands" },
                { key: "⌘⇧?", label: "Shortcuts" },
                { key: "⌘/", label: "Focus" },
                { key: "⌘1-4", label: "Navigate" },
              ].map(h => (
                <div key={h.key} style={{ display: "flex", alignItems: "center", gap: 3 }}>
                  <span style={{ fontSize: 7, padding: "1px 4px", borderRadius: 2, background: "var(--surface-raised)", border: "1px solid var(--border)", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{h.key}</span>
                  <span style={{ fontSize: 7, color: "var(--text-muted)", opacity: 0.5 }}>{h.label}</span>
                </div>
              ))}
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
