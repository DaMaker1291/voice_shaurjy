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
}

export default function Sidebar({ messages, open, onClose }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 right-0 h-full w-[28rem] bg-gray-950/90 backdrop-blur-xl border-l border-gray-800/50 z-50 transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800/50">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
            <span className="text-sm font-mono text-gray-400">transcript</span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-600 hover:text-gray-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 h-[calc(100%-57px)] scrollbar-thin">
          {messages.length === 0 ? (
            <div className="text-center text-gray-700 text-sm pt-8">
              <p className="font-mono">Awaiting transmission...</p>
              <p className="text-xs mt-2">Tap the orb to speak with Jason</p>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className="animate-fade-in">
                <p className={`text-[10px] font-mono uppercase tracking-wider mb-1 ${m.role === "user" ? "text-cyan-500" : "text-purple-400"}`}>
                  {m.role === "user" ? "> you" : "> jason"}
                </p>
                <p className="text-base text-gray-300 leading-relaxed">{m.content}</p>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </aside>
    </>
  );
}
