"use client";

import { useEffect, useRef } from "react";
import ChatBubble from "./ChatBubble";

interface Message {
  role: string;
  content: string;
  image?: string;
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
          Say "Hey Jason, what's on my exam tomorrow?"<br />
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
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
