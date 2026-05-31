"""
Setup — pre-downloads all local models.

                     Disk        RAM
LLM  SmolLM2-360M (4-bit)   720 MB*   180 MB   ← "insanely good"
STT  faster-whisper tiny.en  75 MB     75 MB
TTS  Piper (lessac-medium)   45 MB     45 MB
EMB  bge-small-en-v1.5       33 MB     33 MB
VAD  Silero                   2 MB      2 MB
                          ─────────  ───────
                            ~875 MB*   335 MB
* 720 MB is a one-time download; 4-bit in RAM is 180 MB.
"""

import torch
from optimum.quanto import qint4, quantize, freeze
from transformers import AutoModelForCausalLM, AutoTokenizer

LLM_ID = "HuggingFaceTB/SmolLM2-360M-Instruct"


def download_llm():
    print(f"Downloading {LLM_ID} (720 MB float16 → 180 MB int4 RAM)...")
    tok = AutoTokenizer.from_pretrained(LLM_ID)
    model = AutoModelForCausalLM.from_pretrained(LLM_ID, low_cpu_mem_usage=True, torch_dtype=torch.float16)
    quantize(model, weights=qint4)
    freeze(model)
    print(f"  {model.num_parameters() / 1e6:.0f}M params @ 4-bit ≈ {model.num_parameters() * 4 / 8 / 1e6:.0f} MB RAM")


def download_stt():
    print("Priming faster-whisper tiny.en (75 MB)...")
    from faster_whisper import WhisperModel
    WhisperModel("tiny.en", device="cpu", compute_type="int8")


def download_emb():
    print("Downloading BAAI/bge-small-en-v1.5 (33 MB)...")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer("BAAI/bge-small-en-v1.5")


def download_tts():
    print("Downloading Piper lessac-medium (45 MB)...")
    from huggingface_hub import hf_hub_download
    hf_hub_download("rhasspy/piper-voices", "en/en_US/lessac/medium/en_US-lessac-medium.onnx")


def download_vad():
    print("Priming Silero VAD (2 MB)...")
    torch.hub.load("snakers4/silero-vad", "silero_vad", force_reload=False, onnx=True)


if __name__ == "__main__":
    print("=" * 50)
    print("Second Brain — Local Model Setup")
    print("=" * 50)
    download_llm()
    download_stt()
    download_emb()
    download_tts()
    download_vad()
    print("\nAll models cached. Ready to run!")
    print("  uvicorn backend.main:app --reload")
    print("  python backend/agent.py")
