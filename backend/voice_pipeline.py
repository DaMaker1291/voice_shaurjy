"""Local STT (faster-whisper tiny.en) + TTS (Piper).
Zero cloud, zero API keys needed."""

import os
import base64
import tempfile
import numpy as np
import soundfile as sf

_STT = None
_TTS = None
_TTS_MODEL = None


def _get_stt():
    global _STT
    if _STT is None:
        from faster_whisper import WhisperModel
        _STT = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return _STT


def _get_tts():
    global _TTS, _TTS_MODEL
    if _TTS is None:
        from piper import PiperVoice
        import json
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download(
            "rhasspy/piper-voices",
            "en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        )
        config_path = model_path.replace(".onnx", ".json")
        _TTS = PiperVoice.load(model_path, config_path=config_path)
    return _TTS


def stt_transcribe(audio_b64: str) -> str:
    model = _get_stt()
    audio_bytes = base64.b64decode(audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        segments, _ = model.transcribe(tmp, language="en")
        return " ".join(s.text.strip() for s in segments)
    finally:
        try:
            os.unlink(tmp)
        except PermissionError:
            pass


def tts_speak(text: str) -> bytes:
    voice = _get_tts()
    buf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        voice.synthesize(text, buf)
        buf.seek(0)
        data, sr = sf.read(buf.name)
        sf.write(buf.name, data, sr)
        with open(buf.name, "rb") as f:
            return f.read()
    finally:
        buf.close()
        try:
            os.unlink(buf.name)
        except PermissionError:
            pass


async def tts_speak_b64(text: str) -> str:
    audio = tts_speak(text)
    return base64.b64encode(audio).decode("utf-8")
