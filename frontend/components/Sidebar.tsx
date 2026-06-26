"use client";

import { useEffect, useRef } from "react";

interface Message { role: string; content: string }

interface Props {
  messages: Message[];
  open: boolean;
  onClose: () => void;
  summary?: string;
  interests?: string[];
}

function formatContent(content: string): string {
  // Bold **text** → doesn't render in plain text, keep as-is for monospace display
  return content;
}

function isDataContent(content: string): boolean {
  return content.includes("──") || content.includes("──") ||
    (content.includes(":") && content.split("\n").length > 3) ||
    content.startsWith("OS:") || content.startsWith("CPU:") || content.startsWith("RAM:") ||
    content.includes("Device Scan") || content.includes("Memory Cleanup") ||
    content.includes("Installed apps") || content.includes("Running processes");
}

export default function Sidebar({ messages, open, onClose }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/40 z-40 md:hidden" onClick={onClose} />}

      <aside
        className={`fixed top-0 right-0 h-full w-full sm:w-[26rem] max-w-[92vw] z-50 transition-all duration-400 ease-out ${
          open ? "translate-x-0 opacity-100" : "translate-x-full opacity-0 pointer-events-none"
        }`}
        style={{
          background: "rgba(5, 5, 20, 0.92)",
          backdropFilter: "blur(35px)",
          WebkitBackdropFilter: "blur(35px)",
          borderLeft: "1px solid rgba(120, 60, 220, 0.12)",
          boxShadow: "-15px 0 50px rgba(0,0,0,0.5), -5px 0 30px rgba(120,60,220,0.05)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-800/15">
          <div className="flex items-center gap-2.5">
            <div className="relative flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-purple-500/70" />
              <div className="absolute w-4 h-4 rounded-full bg-purple-500/20 animate-ping" style={{ animationDuration: '3s' }} />
            </div>
            <span className="text-[10px] font-mono text-gray-500 tracking-[0.2em] uppercase">transcript</span>
            <span className="text-[9px] font-mono text-gray-700/50 ml-0.5">{messages.length} msg{messages.length !== 1 ? 's' : ''}</span>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 transition-colors p-1.5 rounded-lg hover:bg-gray-800/30" title="Close sidebar">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="overflow-y-auto px-4 py-3 space-y-2.5 scrollbar-thin" style={{ height: "calc(100% - 53px)" }}>
          {messages.length === 0 ? (
            <div className="text-center pt-16">
              <div className="w-10 h-10 mx-auto mb-4 rounded-full border border-gray-800/20 flex items-center justify-center bg-gray-900/30">
                <span className="text-sm text-gray-700 font-mono">~</span>
              </div>
              <p className="text-xs font-mono text-gray-700 tracking-[0.2em] uppercase">awaiting transmission</p>
              <p className="text-[11px] mt-2 text-gray-700/50 font-mono">Speak or type to begin</p>
            </div>
          ) : (
            messages.map((m, i) => {
              const isData = isDataContent(m.content);
              return (
                <div
                  key={i}
                  className={`message-enter rounded-xl px-4 py-3 ${
                    m.role === "user"
                      ? "bg-cyan-900/10 border border-cyan-900/15"
                      : isData
                        ? "bg-gray-900/40 border border-blue-900/15"
                        : ""
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      m.role === "user" ? "bg-cyan-500/60" : "bg-purple-500/60"
                    }`} />
                    <p className={`text-[9px] font-mono tracking-[0.15em] uppercase ${
                      m.role === "user" ? "text-cyan-600/70" : "text-purple-500/60"
                    }`}>
                      {m.role === "user" ? "you" : "jason"}
                    </p>
                    {isData && (
                      <span className="text-[7px] font-mono text-blue-500/40 tracking-[0.15em] uppercase ml-auto">data</span>
                    )}
                  </div>
                  <p className={`leading-relaxed ${
                    isData
                      ? "font-mono text-[11px] text-cyan-200/70 leading-relaxed"
                      : m.role === "user"
                        ? "text-sm text-gray-200 font-normal"
                        : "text-sm text-gray-300 font-light"
                  }`}>{m.content}</p>
                </div>
              );
            })
          )}
          <div ref={bottomRef} />
        </div>
      </aside>
    </>
  );
}
