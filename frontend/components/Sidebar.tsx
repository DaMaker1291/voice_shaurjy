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

export default function Sidebar({ messages, open, onClose }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  return (
    <>
      {/* Mobile backdrop only */}
      {open && <div className="fixed inset-0 bg-black/40 z-40 md:hidden" onClick={onClose} />}

      <aside
        className={`fixed top-0 right-0 h-full w-[24rem] max-w-[90vw] z-50 transition-all duration-400 ease-out ${
          open ? "translate-x-0 opacity-100" : "translate-x-full opacity-0 pointer-events-none"
        }`}
        style={{
          background: "rgba(5, 5, 20, 0.88)",
          backdropFilter: "blur(30px)",
          WebkitBackdropFilter: "blur(30px)",
          borderLeft: "1px solid rgba(120, 60, 220, 0.1)",
          boxShadow: "-10px 0 40px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-800/20">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse shadow-lg shadow-purple-500/20" />
            <span className="text-[10px] font-mono text-gray-500 tracking-[0.2em] uppercase">transcript</span>
            <span className="text-[9px] font-mono text-gray-700 ml-1">{messages.length} msgs</span>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 transition-colors p-1.5 rounded-lg hover:bg-gray-800/30">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="overflow-y-auto px-5 py-4 space-y-4 scrollbar-thin" style={{ height: "calc(100% - 53px)" }}>
          {messages.length === 0 ? (
            <div className="text-center pt-16">
              <div className="w-8 h-8 mx-auto mb-4 rounded-full border border-gray-800/30 flex items-center justify-center">
                <span className="text-xs text-gray-700 font-mono">...</span>
              </div>
              <p className="text-xs font-mono text-gray-700 tracking-[0.2em] uppercase">awaiting transmission</p>
              <p className="text-[11px] mt-2 text-gray-700/50 font-mono">Speak or type to begin</p>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className="message-enter">
                <p className={`text-[9px] font-mono tracking-[0.2em] uppercase mb-1.5 ${
                  m.role === "user" ? "text-cyan-600" : "text-purple-500/80"
                }`}>
                  {m.role === "user" ? "> you" : "> jason"}
                </p>
                <p className="text-sm text-gray-300 leading-relaxed font-normal">{m.content}</p>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </aside>
    </>
  );
}
