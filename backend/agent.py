"""
LiveKit WebRTC Agent — fully local voice pipeline.
Sends transcript as JSON via data channel for the frontend sidebar.

Pipeline: VAD → faster-whisper → SmolLM2-360M-4bit → Piper TTS

Data channel messages:
  {"type":"transcript","role":"user","text":"..."}
  {"type":"transcript","role":"assistant","text":"..."}
  {"type":"status","state":"listening"|"speaking"|"idle"}

Run:  python backend/agent.py
"""

import asyncio
import base64
import json
import logging
import os

import torch
from dotenv import load_dotenv
from livekit import rtc

from ai_agent import generate_response
from voice_pipeline import stt_transcribe, tts_speak

load_dotenv()
logger = logging.getLogger("second-brain")
logging.basicConfig(level=logging.INFO)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_TOKEN = os.getenv("LIVEKIT_TOKEN", "")
ROOM_NAME = "second-brain"


# ── VAD ───────────────────────────────────────────────────────
def _vad():
    try:
        m, _ = torch.hub.load("snakers4/silero-vad", "silero_vad", force_reload=False, onnx=True)
        return m
    except Exception:
        logger.warning("VAD unavailable — passthrough")
        return None


_VAD = _vad()


def _has_speech(audio: bytes, sr: int = 16000) -> bool:
    if _VAD is None:
        return True
    t = torch.frombuffer(audio, dtype=torch.float32).unsqueeze(0)
    if sr != 16000:
        import torchaudio
        t = torchaudio.functional.resample(t, sr, 16000)
    return _VAD(t, 16000).item() > 0.5


# ── Helpers ───────────────────────────────────────────────────
def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


async def _send(room: rtc.Room, msg: dict):
    payload = json.dumps(msg).encode("utf-8")
    await room.local_participant.publish_data(payload)


# ── Agent ─────────────────────────────────────────────────────
async def main():
    room = rtc.Room()

    @room.on("track_subscribed")
    def on_track(track, pub, participant):
        if track.kind == rtc.TrackKind.K_AUDIO:
            asyncio.ensure_future(_process_audio(track, room))

    @room.on("data_received")
    def on_data(payload: rtc.DataPacket):
        try:
            msg = json.loads(payload.data)
            if msg.get("type") == "ping":
                asyncio.ensure_future(_send(room, {"type": "pong"}))
        except Exception:
            pass

    await room.connect(LIVEKIT_URL, LIVEKIT_TOKEN)
    await _send(room, {"type": "status", "state": "idle"})
    logger.info("Agent ready in room %s", ROOM_NAME)
    await asyncio.Event().wait()


async def _process_audio(track: rtc.Track, room: rtc.Room):
    stream = rtc.AudioStream(track)
    buf = bytearray()

    async for frame in stream:
        buf.extend(frame.data.tobytes())
        if len(buf) < 32000:
            continue
        if not _has_speech(bytes(buf[-32000:])):
            continue

        await _send(room, {"type": "status", "state": "listening"})
        text = stt_transcribe(_b64(bytes(buf)))
        buf.clear()
        logger.info("User: %s", text)
        await _send(room, {"type": "transcript", "role": "user", "text": text})

        await _send(room, {"type": "status", "state": "speaking"})
        reply = generate_response("lk-user", text, "premium")
        logger.info("Jason: %s", reply)
        await _send(room, {"type": "transcript", "role": "assistant", "text": reply})

        audio = tts_speak(reply)
        source = rtc.AudioSource(rtc.AudioSourceOptions(num_channels=1, sample_rate=22050))
        await room.local_participant.publish_track(source)
        await _send(room, {"type": "status", "state": "idle"})


if __name__ == "__main__":
    asyncio.run(main())
