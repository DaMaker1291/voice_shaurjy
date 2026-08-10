"""
SDR Ingest
Processes IQ radio signals or synthesizes mock FFT spectrum data.
Writes output to ~/JARVIS_Vault/Esoteric/RF_Payload.bin.
"""
import os
import struct
import logging
import numpy as np
from typing import Optional, Dict, Any

logger = logging.getLogger("sdr_ingest")

VAULT_DIR = os.path.expanduser("~/JARVIS_Vault/Esoteric")
RF_PAYLOAD_PATH = os.path.join(VAULT_DIR, "RF_Payload.bin")
SAMPLE_RATE = 2048000
CENTER_FREQ = 100_000_000
FFT_SIZE = 1024


def _ensure_vault_dir() -> str:
    os.makedirs(VAULT_DIR, exist_ok=True)
    return VAULT_DIR


def synthesize_iq_samples(num_samples: int = SAMPLE_RATE) -> bytes:
    """Generate mock IQ samples as raw binary (interleaved I, Q int16)."""
    t = np.arange(num_samples, dtype=np.float64) / SAMPLE_RATE
    iq_signal = np.sin(2 * np.pi * 1000 * t) * 0.5
    iq_int16 = (iq_signal * 32767).astype(np.int16)
    return iq_int16.tobytes()


def synthesize_fft_spectrum(num_bins: int = FFT_SIZE) -> bytes:
    """Generate mock FFT spectrum data as float32 binary."""
    freqs = np.linspace(0, SAMPLE_RATE / 2, num_bins)
    spectrum = np.abs(np.fft.fft(np.sin(2 * np.pi * 1000 * np.arange(num_bins) / SAMPLE_RATE)))
    spectrum = spectrum.astype(np.float32)
    return spectrum.tobytes()


def save_rf_payload(data: bytes, output_path: Optional[str] = None) -> str:
    """Save RF payload binary to disk."""
    path = output_path or RF_PAYLOAD_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    size = os.path.getsize(path)
    logger.info(f"RF payload saved to {path} ({size} bytes)")
    return path


def generate_rf_payload(
    mode: str = "iq",
    num_samples: int = SAMPLE_RATE,
    output_path: Optional[str] = None,
) -> str:
    """Generate and save an RF payload file."""
    _ensure_vault_dir()

    if mode == "iq":
        data = synthesize_iq_samples(num_samples=num_samples)
    elif mode == "fft":
        data = synthesize_fft_spectrum(num_bins=num_samples)
    else:
        data = synthesize_iq_samples(num_samples=num_samples)

    return save_rf_payload(data, output_path=output_path)


def read_rf_payload(path: Optional[str] = None) -> bytes:
    """Read an existing RF payload file."""
    path = path or RF_PAYLOAD_PATH
    with open(path, "rb") as f:
        return f.read()


def get_payload_info(path: Optional[str] = None) -> Dict[str, Any]:
    """Get metadata about the RF payload file."""
    path = path or RF_PAYLOAD_PATH
    if not os.path.exists(path):
        return {"exists": False, "path": path}
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        header = f.read(16)
    return {
        "exists": True,
        "path": path,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "header_hex": header.hex(),
        "sample_rate": SAMPLE_RATE,
        "center_freq_hz": CENTER_FREQ,
        "fft_size": FFT_SIZE,
    }