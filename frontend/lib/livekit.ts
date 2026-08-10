import { Room, RoomEvent } from "livekit-client";

export interface TranscriptMessage {
  role: "user" | "assistant";
  text: string;
}

export type OrbState = "idle" | "listening" | "speaking";

export interface LiveKitCallbacks {
  onTranscript: (msg: TranscriptMessage) => void;
  onState: (state: OrbState) => void;
  onConnected: () => void;
  onDisconnected: () => void;
}

export async function connectToLiveKit(
  url: string,
  token: string,
  callbacks: LiveKitCallbacks
): Promise<Room> {
  const room = new Room({
    adaptiveStream: true,
    dynacast: true,
  });

  room.on(RoomEvent.Connected, () => {
    callbacks.onConnected();
  });

  room.on(RoomEvent.Disconnected, () => {
    callbacks.onDisconnected();
  });

  room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
    try {
      const msg = JSON.parse(new TextDecoder().decode(payload));
      if (msg.type === "transcript") {
        callbacks.onTranscript({ role: msg.role, text: msg.text });
      } else if (msg.type === "status") {
        callbacks.onState(msg.state);
      }
    } catch {
      // ignore
    }
  });

  room.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === "audio") {
      const el = new Audio();
      el.srcObject = new MediaStream([track.mediaStreamTrack]);
      el.play();
    }
  });

  await room.connect(url, token);
  await room.localParticipant.setMicrophoneEnabled(true);

  return room;
}
