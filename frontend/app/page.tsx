"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Orb from "@/components/Orb";
import Sidebar from "@/components/Sidebar";
import { textChat, getHealth, getLiveKitToken } from "@/lib/api";
import { connectToLiveKit, type TranscriptMessage, type OrbState } from "@/lib/livekit";

interface Message {
  role: string;
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [orbState, setOrbState] = useState<OrbState>("idle");
  const [liveKitReady, setLiveKitReady] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const roomRef = useRef<Awaited<ReturnType<typeof connectToLiveKit>> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── On mount: check backend health & LiveKit availability ──
  useEffect(() => {
    (async () => {
      try {
        const h = await getHealth();
        setLiveKitReady(h.livekit);
      } catch {
        setLiveKitReady(false);
      }
    })();
  }, []);

  // ── LiveKit connection ─────────────────────────────────────
  const connectVoice = useCallback(async () => {
    try {
      const tk = await getLiveKitToken();
      if (!tk) throw new Error("no livekit token");

      setOrbState("listening");
      const room = await connectToLiveKit(tk.url, tk.token, {
        onTranscript: (msg: TranscriptMessage) => {
          setMessages((p) => [...p, { role: msg.role, content: msg.text }]);
          setSidebarOpen(true);
        },
        onState: (state: OrbState) => setOrbState(state),
        onConnected: () => setOrbState("idle"),
        onDisconnected: () => {
          setOrbState("idle");
          roomRef.current = null;
        },
      });
      roomRef.current = room;
    } catch {
      setOrbState("idle");
      setShowInput(true);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, []);

  // ── Disconnect ─────────────────────────────────────────────
  const disconnectVoice = useCallback(async () => {
    roomRef.current?.disconnect();
    roomRef.current = null;
    setOrbState("idle");
  }, []);

  // ── Text chat fallback ─────────────────────────────────────
  const sendText = useCallback(async () => {
    const txt = textInput.trim();
    if (!txt) return;
    setTextInput("");
    setMessages((p) => [...p, { role: "user", content: txt }]);
    setSidebarOpen(true);
    try {
      const res = await textChat(txt);
      setMessages((p) => [...p, { role: "assistant", content: res.text }]);
    } catch {
      setMessages((p) => [...p, { role: "assistant", content: "(backend unreachable — ensure uvicorn is running)" }]);
    }
  }, [textInput]);

  // ── Orb click ──────────────────────────────────────────────
  const handleOrbClick = useCallback(() => {
    if (roomRef.current) {
      disconnectVoice();
    } else if (liveKitReady) {
      connectVoice();
    } else {
      setShowInput((o) => !o);
      if (!showInput) setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [liveKitReady, connectVoice, disconnectVoice, showInput]);

  // ── Keyboard shortcut ──────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && !showInput) {
        setShowInput(true);
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showInput]);

  const connected = orbState !== "idle" || !!roomRef.current;
  const statusText =
    orbState === "listening" ? "orb is listening..." :
    orbState === "speaking" ? "jason is responding..." :
    roomRef.current ? "connected — tap orb to disconnect" :
    liveKitReady ? "tap the orb" :
    showInput ? "type a message (press Enter)" :
    "tap the orb or press / to type";

  return (
    <div className="relative h-screen w-full overflow-hidden bg-gray-950">
      {/* Starfield */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="stars" /><div className="stars2" /><div className="stars3" />
      </div>

      {/* Top bar */}
      <header className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-6">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
          <span className="text-sm font-mono text-gray-500 tracking-wide">second_brain v1</span>
        </div>
        <button
          onClick={() => setSidebarOpen((o) => !o)}
          className="text-gray-600 hover:text-gray-300 transition-colors"
          title="Toggle transcript"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h7" />
          </svg>
        </button>
      </header>

      {/* Center orb */}
      <div className="absolute inset-0 flex items-center justify-center" style={{ marginTop: showInput ? -30 : 0 }}>
        <Orb
          listening={orbState === "listening"}
          speaking={orbState === "speaking"}
          onClick={handleOrbClick}
        />
      </div>

      {/* Text input (slide-in from bottom) */}
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
          <div className={`w-1.5 h-1.5 rounded-full transition-colors ${connected ? "bg-green-500" : "bg-gray-700"}`} />
          <span className="text-xs font-mono text-gray-600">{statusText}</span>
        </div>
      </footer>
    </div>
  );
}
