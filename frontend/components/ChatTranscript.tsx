"use client";

import { useEffect, useRef, ReactElement } from "react";
import ChatBubble from "./ChatBubble";

function linkLabel(url: string): { text: string; icon: ReactElement } {
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
  if (u.includes("wa.me") || u.includes("whatsapp"))
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

interface Message {
  role: string;
  content: string;
  image?: string;
  link?: string;
}

interface Props {
  messages: Message[];
}

export default function ChatTranscript({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-600">
        <p className="text-center">
          Say "Hey JARVIS, what's on my exam tomorrow?"<br />
          <span className="text-sm">Upload documents in the Dashboard to build your Second Brain.</span>
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-3 py-4 scrollbar-thin">
      {messages.map((m, i) => (
        <div key={i}>
          <ChatBubble role={m.role} content={m.content} />
          {m.image && (
            <div className="flex justify-start mt-1 mb-2">
              <img src={m.image} alt="QR code" className="w-48 h-48 rounded-xl border border-gray-800/50" />
            </div>
          )}
          {m.link && (() => {
            const lbl = linkLabel(m.link);
            return (
              <div className="flex justify-start mt-1 mb-2">
                <a
                  href={m.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-mono bg-purple-900/20 border border-purple-800/30 rounded-xl hover:bg-purple-900/40 transition-all active:scale-95 text-purple-400"
                >
                  {lbl.icon}
                  {lbl.text}
                </a>
              </div>
            );
          })()}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
