"use client";

import AudioPlayer from "./AudioPlayer";

interface Props {
  role: string;
  content: string;
  audio?: string;
}

export default function ChatBubble({ role, content, audio }: Props) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2 ${
          isUser ? "bg-purple-700 text-white" : "bg-gray-800 text-gray-100"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">{content}</p>
        {audio && <AudioPlayer audioB64={audio} />}
      </div>
    </div>
  );
}
