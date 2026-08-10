"""
JARVIS Wake Word Detection — "Hey JARVIS"
==========================================
Local, always-on wake word detection using:
- OpenWakeWord (lightweight neural network)
- Vosk (offline speech recognition)
- Keyword spotter fallback (energy-based)
- Configurable sensitivity and custom wake phrases
"""

import os
import io
import json
import time
import struct
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("jarvis-wakeword")


class WakeWordEngine(str, Enum):
    OPEN_WAKE_WORD = "openwakeword"
    VOSK = "vosk"
    KEYWORD_SPOTTER = "keyword_spotter"
    WEB_SPEECH = "web_speech"


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""
    wake_phrase: str = "hey jarvis"
    alternative_phrases: list = field(default_factory=lambda: [
        "hey jarvis", "ok jarvis", "jarvis", "hey computer",
    ])
    sensitivity: float = 0.5  # 0.0 - 1.0
    engine: WakeWordEngine = WakeWordEngine.KEYWORD_SPOTTER
    sample_rate: int = 16000
    chunk_size: int = 1280  # 80ms at 16kHz
    cooldown_seconds: float = 2.0  # Minimum time between detections
    enabled: bool = True


@dataclass
class WakeWordEvent:
    """A detected wake word event."""
    timestamp: float
    phrase: str
    confidence: float
    engine: str
    audio_rms: float = 0.0


class KeywordSpotter:
    """
    Lightweight energy-based keyword spotter.
    Uses zero-crossing rate and energy thresholds for basic detection.
    Falls back when ML engines are unavailable.
    """

    def __init__(self, sensitivity: float = 0.5):
        self.sensitivity = sensitivity
        self._energy_threshold = 0.01 * (1.0 - sensitivity * 0.7)
        self._zcr_threshold = 0.1

    def detect(self, audio_chunk: bytes) -> Dict[str, Any]:
        """
        Analyze audio chunk for speech-like energy patterns.
        Returns detection result with confidence.
        """
        if len(audio_chunk) < 2:
            return {"detected": False, "confidence": 0.0}

        # Parse 16-bit PCM samples
        samples = struct.unpack(f"<{len(audio_chunk) // 2}h", audio_chunk)

        if not samples:
            return {"detected": False, "confidence": 0.0}

        # Calculate RMS energy
        sum_squares = sum(s * s for s in samples)
        rms = (sum_squares / len(samples)) ** 0.5 / 32768.0

        # Calculate zero-crossing rate
        crossings = sum(
            1 for i in range(1, len(samples))
            if (samples[i] >= 0) != (samples[i - 1] >= 0)
        )
        zcr = crossings / len(samples)

        # Speech detection heuristics
        has_energy = rms > self._energy_threshold
        has_speech_zcr = 0.02 < zcr < 0.3  # Typical speech ZCR range

        confidence = 0.0
        if has_energy:
            confidence += 0.4 * min(rms / 0.1, 1.0)
        if has_speech_zcr:
            confidence += 0.3
        if has_energy and has_speech_zcr:
            confidence += 0.3

        return {
            "detected": has_energy and has_speech_zcr,
            "confidence": min(confidence, 1.0),
            "rms": rms,
            "zcr": zcr,
            "energy_threshold": self._energy_threshold,
        }


class OpenWakeWordEngine:
    """
    OpenWakeWord integration for neural wake word detection.
    Uses pre-trained models for "hey jarvis" detection.
    """

    def __init__(self, model_path: Optional[str] = None):
        self._model = None
        self._available = False
        self._model_path = model_path
        self._init_model()

    def _init_model(self):
        """Attempt to load OpenWakeWord model."""
        try:
            from openwakeword import Model as OWWModel
            self._model = OWWModel(
                wakeword_names=["hey_jarvis"],
                inference_framework="onnx",
            )
            self._available = True
            log.info("OpenWakeWord engine initialized")
        except ImportError:
            log.info("OpenWakeWord not available, using fallback")
        except Exception as e:
            log.warning(f"OpenWakeWord init failed: {e}")

    def detect(self, audio_chunk: bytes) -> Dict[str, Any]:
        """Process audio chunk through OpenWakeWord."""
        if not self._available or not self._model:
            return {"detected": False, "confidence": 0.0, "engine": "openwakeword_unavailable"}

        try:
            prediction = self._model.predict(audio_chunk)
            scores = prediction.get("hey_jarvis", 0.0)
            return {
                "detected": scores > 0.5,
                "confidence": float(scores),
                "engine": "openwakeword",
            }
        except Exception as e:
            return {"detected": False, "confidence": 0.0, "error": str(e)}


class VoskWakeEngine:
    """
    Vosk-based wake word detection.
    Uses offline speech recognition to detect "hey jarvis" in audio.
    """

    def __init__(self, model_path: Optional[str] = None):
        self._rec = None
        self._available = False
        self._init_model(model_path)

    def _init_model(self, model_path: Optional[str] = None):
        try:
            from vosk import Model, KaldiRecognizer
            if model_path and os.path.exists(model_path):
                self._model = Model(model_path)
            else:
                # Try default model location
                default_path = os.path.join(
                    os.path.expanduser("~"), ".jarvis", "models", "vosk-model-small-en-us"
                )
                if os.path.exists(default_path):
                    self._model = Model(default_path)
                else:
                    return

            self._rec = KaldiRecognizer(self._model, 16000)
            self._available = True
            log.info("Vosk wake word engine initialized")
        except ImportError:
            log.info("Vosk not available")
        except Exception as e:
            log.warning(f"Vosk init failed: {e}")

    def detect(self, audio_chunk: bytes) -> Dict[str, Any]:
        """Process audio chunk through Vosk."""
        if not self._available or not self._rec:
            return {"detected": False, "confidence": 0.0, "engine": "vosk_unavailable"}

        try:
            if self._rec.AcceptWaveform(audio_chunk):
                result = json.loads(self._rec.Result())
                text = result.get("text", "").lower()
                if any(phrase in text for phrase in ["hey jarvis", "ok jarvis", "jarvis"]):
                    return {
                        "detected": True,
                        "confidence": 0.9,
                        "text": text,
                        "engine": "vosk",
                    }
            return {"detected": False, "confidence": 0.0, "engine": "vosk"}
        except Exception as e:
            return {"detected": False, "confidence": 0.0, "error": str(e)}


class WakeWordDetector:
    """
    Unified wake word detection engine.
    Tries multiple engines in priority order and returns the best result.
    """

    def __init__(self, config: Optional[WakeWordConfig] = None):
        self._config = config or WakeWordConfig()
        self._engines = []
        self._spotter = KeywordSpotter(self._config.sensitivity)
        self._last_detection = 0.0
        self._detection_callbacks: list = []
        self._init_engines()

    def _init_engines(self):
        """Initialize available wake word engines."""
        # Always have keyword spotter as fallback
        self._engines.append(("keyword_spotter", self._spotter))

        # Try OpenWakeWord
        try:
            oww = OpenWakeWordEngine()
            if oww._available:
                self._engines.insert(0, ("openwakeword", oww))
        except Exception:
            pass

        # Try Vosk
        try:
            vosk = VoskWakeEngine()
            if vosk._available:
                self._engines.insert(0 if len(self._engines) > 0 else 0, ("vosk", vosk))
        except Exception:
            pass

        log.info(f"Wake word engines: {[e[0] for e in self._engines]}")

    def on_detection(self, callback: Callable[[WakeWordEvent], None]):
        """Register a callback for wake word detection."""
        self._detection_callbacks.append(callback)

    async def process_audio_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
    ) -> AsyncGenerator[WakeWordEvent, None]:
        """
        Process a continuous audio stream for wake word detection.
        Yields WakeWordEvent when wake phrase is detected.
        """
        buffer = b""
        required_bytes = self._config.chunk_size * 2  # 16-bit PCM

        async for chunk in audio_stream:
            if not self._config.enabled:
                continue

            buffer += chunk

            while len(buffer) >= required_bytes:
                audio_chunk = buffer[:required_bytes]
                buffer = buffer[required_bytes:]

                # Run through all engines
                for engine_name, engine in self._engines:
                    try:
                        result = engine.detect(audio_chunk)
                    except Exception as e:
                        log.debug(f"Engine {engine_name} error: {e}")
                        continue

                    if result.get("detected") and result.get("confidence", 0) > self._config.sensitivity:
                        # Cooldown check
                        now = time.time()
                        if now - self._last_detection < self._config.cooldown_seconds:
                            continue

                        self._last_detection = now

                        event = WakeWordEvent(
                            timestamp=now,
                            phrase=result.get("text", self._config.wake_phrase),
                            confidence=result.get("confidence", 0.0),
                            engine=engine_name,
                            audio_rms=result.get("rms", 0.0),
                        )

                        # Notify callbacks
                        for cb in self._detection_callbacks:
                            try:
                                cb(event)
                            except Exception:
                                pass

                        yield event
                        break  # Only yield once per chunk

    def detect_sync(self, audio_chunk: bytes) -> Dict[str, Any]:
        """Synchronous detection for single audio chunks."""
        if not self._config.enabled:
            return {"detected": False}

        now = time.time()
        if now - self._last_detection < self._config.cooldown_seconds:
            return {"detected": False, "reason": "cooldown"}

        for engine_name, engine in self._engines:
            try:
                result = engine.detect(audio_chunk)
                if result.get("detected") and result.get("confidence", 0) > self._config.sensitivity:
                    self._last_detection = now
                    result["engine"] = engine_name
                    return result
            except Exception:
                continue

        return {"detected": False}

    def set_sensitivity(self, sensitivity: float):
        """Update detection sensitivity."""
        self._config.sensitivity = max(0.0, min(1.0, sensitivity))
        self._spotter.sensitivity = self._config.sensitivity

    def set_wake_phrase(self, phrase: str):
        """Update the wake phrase."""
        self._config.wake_phrase = phrase.lower()
        if phrase.lower() not in self._config.alternative_phrases:
            self._config.alternative_phrases.append(phrase.lower())

    def enable(self):
        """Enable wake word detection."""
        self._config.enabled = True

    def disable(self):
        """Disable wake word detection."""
        self._config.enabled = False

    def get_status(self) -> Dict[str, Any]:
        """Get wake word detector status."""
        return {
            "enabled": self._config.enabled,
            "wake_phrase": self._config.wake_phrase,
            "sensitivity": self._config.sensitivity,
            "engines": [e[0] for e in self._engines],
            "last_detection": self._last_detection,
            "cooldown_seconds": self._config.cooldown_seconds,
        }


# ── Singleton ────────────────────────────────────────────────────────────
_detector: Optional[WakeWordDetector] = None


def get_wake_word_detector() -> WakeWordDetector:
    global _detector
    if _detector is None:
        _detector = WakeWordDetector()
    return _detector
