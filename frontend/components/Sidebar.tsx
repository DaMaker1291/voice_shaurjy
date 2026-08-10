"use client";

import { useEffect, useRef } from "react";

interface Message { role: string; content: string; image?: string; link?: string }

interface Props {
  messages: Message[];
  open: boolean;
  onClose: () => void;
  summary?: string;
  interests?: string[];
}

function formatContent(content: string): string {
  return content;
}

function linkLabel(url: string): { text: string; icon: JSX.Element } {
  const u = url.toLowerCase();
  if (u.includes("/relay") || u.includes("relay_agent"))
    return {
      text: "Download Relay Agent",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    };
  if (u.includes("wa.me") || u.includes("whatsapp") || u.includes("wa_link"))
    return {
      text: "Open WhatsApp",
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
        </svg>
      ),
    };
  return {
    text: "Open Link",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
    ),
  };
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
                      {m.role === "user" ? "you" : "jarvis"}
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
                  {m.image && (
                    <img src={m.image} alt="QR code" className="w-36 h-36 rounded-lg border border-gray-800/50 mt-2" />
                  )}
                  {m.link && (() => {
                    const lbl = linkLabel(m.link);
                    return (
                      <a
                        href={m.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 mt-2 px-4 py-2 text-sm font-mono bg-purple-900/20 border border-purple-800/30 rounded-xl hover:bg-purple-900/40 transition-all active:scale-95 text-purple-400"
                      >
                        {lbl.icon}
                        {lbl.text}
                      </a>
                    );
                  })()}
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
