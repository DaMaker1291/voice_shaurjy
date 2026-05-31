"""
Setup — pre-downloads all local models.

                     Disk
LLM  Qwen2.5-0.5B   1.9 GB
STT  faster-whisper  75 MB
TTS  Piper           45 MB
EMB  bge-small       33 MB
VAD  Silero           2 MB
                  ───────
                  ~2 GB  (one-time download)
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

LLM_ID = "Qwen/Qwen2.5-0.5B-Instruct"


def download_llm():
    print(f"Downloading {LLM_ID} (1.9 GB float32)...")
    tok = AutoTokenizer.from_pretrained(LLM_ID)
    model = AutoModelForCausalLM.from_pretrained(LLM_ID, low_cpu_mem_usage=True, torch_dtype=torch.float32)
    print(f"  {model.num_parameters() / 1e6:.0f}M params @ float32 ≈ {model.num_parameters() * 4 / 1e6:.0f} MB RAM")


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
    torch.hub.load("snakers4/silero-vad", "silero_vad", force_reload=False, onnx=True, trust_repo=True)


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
