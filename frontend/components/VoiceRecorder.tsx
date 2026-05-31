"use client";

import { useRef, useState } from "react";
import { Room } from "livekit-client";

interface Props {
  room: Room | null;
}

export default function VoiceRecorder({ room }: Props) {
  const [muted, setMuted] = useState(false);

  const toggleMute = async () => {
    if (!room) return;
    const pub = room.localParticipant;
    if (muted) {
      await pub.setMicrophoneEnabled(true);
      setMuted(false);
    } else {
      await pub.setMicrophoneEnabled(false);
      setMuted(true);
    }
  };

  if (!room) return null;

  return (
    <div className="flex justify-center">
      <button
        onClick={toggleMute}
        className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${
          muted ? "bg-gray-700" : "bg-purple-600 animate-pulse"
        }`}
      >
        {muted ? (
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14a3 3 0 003-3V5a3 3 0 00-6 0v6a3 3 0 003 3z" />
            <path d="M17 11a5 5 0 01-10 0H5a7 7 0 0014 0h-2z" />
            <line x1="3" y1="3" x2="21" y2="21" stroke="#fff" strokeWidth="2" />
          </svg>
        ) : (
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14a3 3 0 003-3V5a3 3 0 00-6 0v6a3 3 0 003 3z" />
            <path d="M17 11a5 5 0 01-10 0H5a7 7 0 0014 0h-2z" />
          </svg>
        )}
      </button>
    </div>
  );
}
