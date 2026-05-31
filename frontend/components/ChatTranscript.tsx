"use client";

import { useEffect, useRef } from "react";
import ChatBubble from "./ChatBubble";

interface Message {
  role: string;
  content: string;
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
        <ChatBubble key={i} role={m.role} content={m.content} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
