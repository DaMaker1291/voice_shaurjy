"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { getVoiceWSUrl } from "./api";

export type VoiceState = "idle" | "listening" | "processing" | "speaking";

export interface VoiceCallbacks {
  onTranscript?: (role: "user" | "assistant", text: string) => void;
  onState?: (state: VoiceState) => void;
  onAudio?: (base64Wav: string) => void;
  onError?: (message: string) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export interface VoiceConnection {
  sendText: (text: string) => void;
  sendAudio: (pcmData: ArrayBuffer) => void;
  disconnect: () => void;
  connected: boolean;
  state: VoiceState;
}

export function useVoiceWS(callbacks: VoiceCallbacks = {}): VoiceConnection {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState<VoiceState>("idle");
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let reconnectDelay = 1000;

    const connect = () => {
      try {
        ws = new WebSocket(getVoiceWSUrl());
        ws.binaryType = "arraybuffer";

        ws.onopen = () => {
          setConnected(true);
          reconnectDelay = 1000;
          callbacksRef.current.onConnect?.();
          // Configure audio params
          ws?.send(JSON.stringify({ type: "config", sample_rate: 16000 }));
        };

        ws.onclose = () => {
          setConnected(false);
          setState("idle");
          callbacksRef.current.onDisconnect?.();
          // Auto-reconnect
          reconnectTimer = setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
            connect();
          }, reconnectDelay);
        };

        ws.onerror = () => {
          ws?.close();
        };

        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(typeof e.data === "string" ? e.data : new TextDecoder().decode(e.data));
            switch (msg.type) {
              case "transcript":
                callbacksRef.current.onTranscript?.(msg.role, msg.text);
                break;
              case "status":
                setState(msg.state);
                callbacksRef.current.onState?.(msg.state);
                break;
              case "audio":
                callbacksRef.current.onAudio?.(msg.data);
                break;
              case "error":
                callbacksRef.current.onError?.(msg.message);
                break;
            }
          } catch {}
        };
      } catch {}
    };

    connect();
    wsRef.current = ws;

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  const sendText = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "text", text }));
    }
  }, []);

  const sendAudio = useCallback((pcmData: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(pcmData);
    }
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { sendText, sendAudio, disconnect, connected, state };
}
