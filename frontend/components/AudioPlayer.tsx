"use client";

import { useEffect, useRef } from "react";

interface Props {
  audioB64: string;
}

export default function AudioPlayer({ audioB64 }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (audioB64 && audioRef.current) {
      audioRef.current.src = `data:audio/mp3;base64,${audioB64}`;
      audioRef.current.play();
    }
  }, [audioB64]);

  return <audio ref={audioRef} controls className="w-full h-8 mt-1" />;
}
