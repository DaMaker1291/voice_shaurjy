"use client";

import { useEffect, useRef } from "react";

interface Message {
  role: string;
  content: string;
}

interface Props {
  messages: Message[];
  open: boolean;
  onClose: () => void;
  summary?: string;
  interests?: string[];
}

export default function Sidebar({ messages, open, onClose, summary, interests }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/20 z-40 md:hidden" onClick={onClose} />}
      <aside
        className={`fixed top-0 right-0 h-full w-[28rem] z-50 transition-all duration-400 ease-out ${
          open ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"
        }`}
        style={{
          background: "rgba(5, 5, 20, 0.85)",
          backdropFilter: "blur(30px)",
          WebkitBackdropFilter: "blur(30px)",
          borderLeft: "1px solid rgba(120, 60, 220, 0.1)",
          boxShadow: "-10px 0 40px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-800/30">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse shadow-lg shadow-purple-500/20" />
            <span className="text-xs font-mono text-gray-500 tracking-[0.2em] uppercase">transcript</span>
            <span className="text-[10px] font-mono text-gray-800">{messages.length} msgs</span>
          </div>
          <button onClick={onClose} className="text-gray-700 hover:text-gray-400 transition-colors p-1 rounded hover:bg-gray-800/30">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Profile */}
        {interests && interests.length > 0 && (
          <div className="px-5 py-3 border-b border-gray-800/20" style={{ background: "rgba(120, 60, 220, 0.03)" }}>
            <p className="text-[9px] font-mono text-purple-600 tracking-[0.2em] uppercase mb-2">User profile</p>
            <div className="flex flex-wrap gap-1.5">
              {interests.map((topic, i) => (
                <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{
                  background: "rgba(120, 60, 220, 0.08)",
                  color: "rgba(168, 85, 247, 0.7)",
                  border: "1px solid rgba(120, 60, 220, 0.12)",
                }}>
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 h-[calc(100%-57px)] scrollbar-thin">
          {messages.length === 0 ? (
            <div className="text-center pt-12">
              <p className="text-xs font-mono text-gray-800 tracking-[0.2em] uppercase">Awaiting transmission</p>
              <p className="text-[11px] mt-2 text-gray-800">Speak or type to begin</p>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className="message-enter">
                <p className={`text-[9px] font-mono tracking-[0.2em] uppercase mb-1.5 ${
                  m.role === "user" ? "text-cyan-700" : "text-purple-600"
                }`}>
                  {m.role === "user" ? "> you" : "> jason"}
                </p>
                <p className="text-sm text-gray-300 leading-relaxed">{m.content}</p>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </aside>
    </>
  );
}
