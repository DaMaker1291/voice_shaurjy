"""
JARVIS Hardware Detection & AI Model Recommendation Engine
==========================================================
Dynamically detects user hardware and proposes the best local AI models
or API configurations for optimal performance.
"""

import os
import platform
import subprocess
import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HardwareProfile:
    """Complete hardware profile of the user's machine."""
    # CPU
    cpu_brand: str = "Unknown"
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_freq_ghz: float = 0.0
    cpu_arch: str = "x86_64"
    cpu_is_arm: bool = False

    # RAM
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0

    # GPU
    gpu_name: str = "None"
    gpu_vram_gb: float = 0.0
    gpu_brand: str = "None"  # NVIDIA, AMD, Apple, Intel, None
    gpu_driver: str = ""

    # Storage
    disk_total_gb: float = 0.0
    disk_free_gb: float = 0.0

    # Platform
    os_name: str = "Unknown"
    os_version: str = ""
    platform_raw: str = ""

    # Recommendations (filled by engine)
    recommended_models: list = field(default_factory=list)
    recommended_config: dict = field(default_factory=dict)
    performance_tier: str = "unknown"  # potato, low, mid, high, ultra, godlike

    def to_dict(self) -> dict:
        return {
            "cpu": {
                "brand": self.cpu_brand,
                "cores": self.cpu_cores,
                "threads": self.cpu_threads,
                "freq_ghz": self.cpu_freq_ghz,
                "arch": self.cpu_arch,
                "is_arm": self.cpu_is_arm,
            },
            "ram": {
                "total_gb": round(self.ram_total_gb, 1),
                "available_gb": round(self.ram_available_gb, 1),
            },
            "gpu": {
                "name": self.gpu_name,
                "vram_gb": round(self.gpu_vram_gb, 1),
                "brand": self.gpu_brand,
                "driver": self.gpu_driver,
            },
            "disk": {
                "total_gb": round(self.disk_total_gb, 1),
                "free_gb": round(self.disk_free_gb, 1),
            },
            "platform": {
                "os": self.os_name,
                "version": self.os_version,
                "raw": self.platform_raw,
            },
            "performance_tier": self.performance_tier,
            "recommended_models": self.recommended_models,
            "recommended_config": self.recommended_config,
        }


def detect_cpu() -> dict:
    """Detect CPU information across platforms."""
    info = {
        "brand": "Unknown", "cores": 0, "threads": 0,
        "freq_ghz": 0.0, "arch": platform.machine(), "is_arm": False,
    }

    info["arch"] = platform.machine()
    info["is_arm"] = info["arch"] in ("arm64", "aarch64")

    try:
        import psutil
        info["cores"] = psutil.cpu_count(logical=False) or 0
        info["threads"] = psutil.cpu_count(logical=True) or 0
        freq = psutil.cpu_freq()
        if freq:
            info["freq_ghz"] = round(freq.max / 1000, 2) if freq.max else round(freq.current / 1000, 2)
    except Exception:
        pass

    # Get CPU brand
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5,
            )
            info["brand"] = result.stdout.strip()
        elif system == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info["brand"] = line.split(":")[1].strip()
                        break
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "cpu", "get", "Name"],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "Name"]
            if lines:
                info["brand"] = lines[0]
    except Exception:
        info["brand"] = platform.processor() or "Unknown"

    # Apple Silicon detection
    if system == "Darwin" and info["is_arm"]:
        if "M1" in info["brand"]:
            info["brand"] = info["brand"] or "Apple M1"
        elif "M2" in info["brand"]:
            info["brand"] = info["brand"] or "Apple M2"
        elif "M3" in info["brand"]:
            info["brand"] = info["brand"] or "Apple M3"
        elif "M4" in info["brand"]:
            info["brand"] = info["brand"] or "Apple M4"

    return info


def detect_ram() -> dict:
    """Detect RAM information."""
    info = {"total_gb": 0.0, "available_gb": 0.0}
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["total_gb"] = round(mem.total / (1024**3), 1)
        info["available_gb"] = round(mem.available / (1024**3), 1)
    except Exception:
        pass
    return info


def detect_gpu() -> dict:
    """Detect GPU information across platforms."""
    info = {"name": "None", "vram_gb": 0.0, "brand": "None", "driver": ""}

    # Try nvidia-smi first (NVIDIA GPUs)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 2:
                info["name"] = parts[0].strip()
                info["vram_gb"] = round(float(parts[1].strip()) / 1024, 1)
                info["brand"] = "NVIDIA"
                if len(parts) >= 3:
                    info["driver"] = parts[2].strip()
                return info
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try rocm-smi (AMD GPUs)
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--csv"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            info["brand"] = "AMD"
            info["name"] = "AMD GPU"
            return info
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # macOS: Check for Apple Silicon GPU
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout
            if "Apple M" in output:
                # Apple Silicon - GPU is unified with CPU
                chip = "Apple Silicon"
                for line in output.split("\n"):
                    if "Chipset Model:" in line:
                        chip = line.split(":")[1].strip()
                        break
                info["name"] = chip
                info["brand"] = "Apple"
                # Unified memory - estimate VRAM from total RAM
                try:
                    import psutil
                    total_ram = psutil.virtual_memory().total / (1024**3)
                    # Apple Silicon can use up to ~60-70% of RAM as VRAM
                    info["vram_gb"] = round(total_ram * 0.65, 1)
                except Exception:
                    info["vram_gb"] = 8.0  # Conservative default
                return info
            elif "AMD" in output or "Radeon" in output:
                for line in output.split("\n"):
                    if "Chipset Model:" in line or "Chipset:" in line:
                        info["name"] = line.split(":")[1].strip()
                        break
                info["brand"] = "AMD"
                return info
            elif "Intel" in output:
                for line in output.split("\n"):
                    if "Chipset Model:" in line or "Chipset:" in line:
                        info["name"] = line.split(":")[1].strip()
                        break
                info["brand"] = "Intel"
                return info
        except Exception:
            pass

    # Windows: Try wmic
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM"],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "AdapterRAM  Name"]
            if lines:
                parts = lines[0].split("  ")
                if len(parts) >= 2:
                    vram_bytes = int(parts[0]) if parts[0].isdigit() else 0
                    info["name"] = parts[1].strip()
                    info["vram_gb"] = round(vram_bytes / (1024**3), 1) if vram_bytes else 0
                    if "NVIDIA" in info["name"].upper():
                        info["brand"] = "NVIDIA"
                    elif "AMD" in info["name"].upper() or "RADEON" in info["name"].upper():
                        info["brand"] = "AMD"
                    elif "INTEL" in info["name"].upper():
                        info["brand"] = "Intel"
                    return info
        except Exception:
            pass

    # Linux: Try lspci
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "VGA" in line or "3D" in line:
                    info["name"] = line.split(":")[-1].strip()
                    if "NVIDIA" in info["name"].upper():
                        info["brand"] = "NVIDIA"
                    elif "AMD" in info["name"].upper() or "RADEON" in info["name"].upper():
                        info["brand"] = "AMD"
                    elif "INTEL" in info["name"].upper():
                        info["brand"] = "Intel"
                    break
        except Exception:
            pass

    return info


def detect_disk() -> dict:
    """Detect disk information."""
    info = {"total_gb": 0.0, "free_gb": 0.0}
    try:
        import psutil
        disk = psutil.disk_usage("/")
        info["total_gb"] = round(disk.total / (1024**3), 1)
        info["free_gb"] = round(disk.free / (1024**3), 1)
    except Exception:
        pass
    return info


def detect_hardware() -> HardwareProfile:
    """Detect complete hardware profile."""
    profile = HardwareProfile()

    # Detect all components
    cpu = detect_cpu()
    ram = detect_ram()
    gpu = detect_gpu()
    disk = detect_disk()

    # Fill profile
    profile.cpu_brand = cpu["brand"]
    profile.cpu_cores = cpu["cores"]
    profile.cpu_threads = cpu["threads"]
    profile.cpu_freq_ghz = cpu["freq_ghz"]
    profile.cpu_arch = cpu["arch"]
    profile.cpu_is_arm = cpu["is_arm"]

    profile.ram_total_gb = ram["total_gb"]
    profile.ram_available_gb = ram["available_gb"]

    profile.gpu_name = gpu["name"]
    profile.gpu_vram_gb = gpu["vram_gb"]
    profile.gpu_brand = gpu["brand"]
    profile.gpu_driver = gpu["driver"]

    profile.disk_total_gb = disk["total_gb"]
    profile.disk_free_gb = disk["free_gb"]

    profile.os_name = platform.system()
    profile.os_version = platform.version()
    profile.platform_raw = platform.platform()

    # Calculate performance tier
    profile.performance_tier = _calculate_tier(profile)

    # Get model recommendations
    profile.recommended_models = _recommend_models(profile)
    profile.recommended_config = _recommend_config(profile)

    return profile


def _calculate_tier(profile: HardwareProfile) -> str:
    """Calculate a performance tier based on hardware specs."""
    score = 0

    # CPU score
    if profile.cpu_is_arm:
        # Apple Silicon scoring
        brand = profile.cpu_brand.upper()
        if "M4" in brand: score += 90
        elif "M3" in brand: score += 80
        elif "M3 PRO" in brand or "M3 MAX" in brand: score += 85
        elif "M2" in brand: score += 70
        elif "M2 PRO" in brand or "M2 MAX" in brand: score += 75
        elif "M1" in brand: score += 60
        elif "M1 PRO" in brand or "M1 MAX" in brand: score += 65
    else:
        # x86 scoring
        if profile.cpu_cores >= 16: score += 40
        elif profile.cpu_cores >= 8: score += 30
        elif profile.cpu_cores >= 4: score += 20
        else: score += 10

        if profile.cpu_freq_ghz >= 5.0: score += 25
        elif profile.cpu_freq_ghz >= 4.0: score += 20
        elif profile.cpu_freq_ghz >= 3.0: score += 15
        else: score += 5

    # RAM score
    if profile.ram_total_gb >= 128: score += 35
    elif profile.ram_total_gb >= 64: score += 30
    elif profile.ram_total_gb >= 32: score += 25
    elif profile.ram_total_gb >= 16: score += 15
    elif profile.ram_total_gb >= 8: score += 10
    else: score += 5

    # GPU score
    if profile.gpu_brand == "NVIDIA":
        if profile.gpu_vram_gb >= 24: score += 40
        elif profile.gpu_vram_gb >= 16: score += 35
        elif profile.gpu_vram_gb >= 12: score += 30
        elif profile.gpu_vram_gb >= 8: score += 25
        elif profile.gpu_vram_gb >= 6: score += 20
        else: score += 10
    elif profile.gpu_brand == "Apple":
        if profile.gpu_vram_gb >= 48: score += 40
        elif profile.gpu_vram_gb >= 32: score += 35
        elif profile.gpu_vram_gb >= 16: score += 30
        elif profile.gpu_vram_gb >= 8: score += 20
        else: score += 10
    elif profile.gpu_brand == "AMD":
        if profile.gpu_vram_gb >= 16: score += 30
        elif profile.gpu_vram_gb >= 8: score += 25
        else: score += 10
    elif profile.gpu_vram_gb > 0:
        score += 10

    # Determine tier
    if score >= 160: return "godlike"
    if score >= 130: return "ultra"
    if score >= 100: return "high"
    if score >= 70: return "mid"
    if score >= 40: return "low"
    return "potato"


# ═══════════════════════════════════════════════════════════════════
# AI Model Recommendation Database
# ═══════════════════════════════════════════════════════════════════

MODELS_DB = [
    # ── Tier: Potato (2-4GB RAM, no GPU) ────────────────────────
    {
        "name": "Phi-3 Mini (3.8B)",
        "type": "local",
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "quant": "Q4_K_M",
        "size_gb": 2.3,
        "ram_required_gb": 4,
        "gpu_required": False,
        "gpu_brand": None,
        "min_vram_gb": 0,
        "tier": ["potato", "low"],
        "speed": "~15 tokens/sec on CPU",
        "quality": "Good for basic Q&A and writing",
        "use_case": "Quick tasks, low-power machines",
        "license": "MIT",
        "url": "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf",
    },
    {
        "name": "TinyLlama 1.1B",
        "type": "local",
        "repo": "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 0.7,
        "ram_required_gb": 2,
        "gpu_required": False,
        "gpu_brand": None,
        "min_vram_gb": 0,
        "tier": ["potato"],
        "speed": "~25 tokens/sec on CPU",
        "quality": "Basic but fast",
        "use_case": "Ultra-light machines, quick responses",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
    },

    # ── Tier: Low (8GB RAM, iGPU) ──────────────────────────────
    {
        "name": "Gemma 2B",
        "type": "local",
        "repo": "bartowski/gemma-2-2b-it-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 1.6,
        "ram_required_gb": 4,
        "gpu_required": False,
        "gpu_brand": None,
        "min_vram_gb": 0,
        "tier": ["low", "mid"],
        "speed": "~12 tokens/sec on CPU, ~20 on GPU",
        "quality": "Google quality, great instruction following",
        "use_case": "General assistant, coding help",
        "license": "Gemma License",
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF",
    },
    {
        "name": "Phi-3 Small (7B)",
        "type": "local",
        "repo": "microsoft/Phi-3-small-8k-instruct-gguf",
        "quant": "Q4_K_M",
        "size_gb": 4.0,
        "ram_required_gb": 8,
        "gpu_required": False,
        "gpu_brand": None,
        "min_vram_gb": 0,
        "tier": ["low", "mid"],
        "speed": "~8 tokens/sec on CPU",
        "quality": "Excellent reasoning and coding",
        "use_case": "Productivity, coding, analysis",
        "license": "MIT",
        "url": "https://huggingface.co/microsoft/Phi-3-small-8k-instruct-gguf",
    },

    # ── Tier: Mid (16-32GB RAM, dedicated GPU) ─────────────────
    {
        "name": "Llama 3.1 8B",
        "type": "local",
        "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 4.9,
        "ram_required_gb": 10,
        "gpu_required": True,
        "gpu_brand": None,
        "min_vram_gb": 6,
        "tier": ["mid", "high"],
        "speed": "~30 tokens/sec on 8GB VRAM",
        "quality": "Meta's best 8B model, excellent all-around",
        "use_case": "Daily assistant, writing, analysis",
        "license": "Llama 3.1 Community",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
    },
    {
        "name": "Mistral 7B v0.3",
        "type": "local",
        "repo": "TheBloke/Mistral-7B-v0.3-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 4.1,
        "ram_required_gb": 8,
        "gpu_required": True,
        "gpu_brand": None,
        "min_vram_gb": 6,
        "tier": ["mid"],
        "speed": "~35 tokens/sec on 8GB VRAM",
        "quality": "Fast and capable, great for coding",
        "use_case": "Coding, fast inference, general tasks",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/TheBloke/Mistral-7B-v0.3-GGUF",
    },
    {
        "name": "Qwen2 7B",
        "type": "local",
        "repo": "bartowski/Qwen2-7B-Instruct-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 4.4,
        "ram_required_gb": 10,
        "gpu_required": True,
        "gpu_brand": None,
        "min_vram_gb": 6,
        "tier": ["mid", "high"],
        "speed": "~28 tokens/sec on 8GB VRAM",
        "quality": "Multilingual, excellent reasoning",
        "use_case": "Multilingual tasks, complex reasoning",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/bartowski/Qwen2-7B-Instruct-GGUF",
    },

    # ── Tier: High (32GB+ RAM, 12GB+ VRAM) ─────────────────────
    {
        "name": "Llama 3.1 8B (Q8)",
        "type": "local",
        "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "quant": "Q8_0",
        "size_gb": 8.5,
        "ram_required_gb": 16,
        "gpu_required": True,
        "gpu_brand": None,
        "min_vram_gb": 10,
        "tier": ["high", "ultra"],
        "speed": "~20 tokens/sec on 12GB VRAM",
        "quality": "Near-lossless quality from 8B model",
        "use_case": "High-quality output, creative writing",
        "license": "Llama 3.1 Community",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
    },
    {
        "name": "Mixtral 8x7B",
        "type": "local",
        "repo": "TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 26.0,
        "ram_required_gb": 32,
        "gpu_required": True,
        "gpu_brand": None,
        "min_vram_gb": 24,
        "tier": ["high", "ultra"],
        "speed": "~15 tokens/sec on 24GB VRAM",
        "quality": "Mixture of experts, exceptional quality",
        "use_case": "Complex reasoning, professional tasks",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF",
    },
    {
        "name": "DeepSeek Coder V2 Lite",
        "type": "local",
        "repo": "bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 9.0,
        "ram_required_gb": 16,
        "gpu_required": True,
        "gpu_brand": None,
        "min_vram_gb": 10,
        "tier": ["high"],
        "speed": "~25 tokens/sec on 12GB VRAM",
        "quality": "Best coding model in its size class",
        "use_case": "Software development, code generation",
        "license": "MIT",
        "url": "https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF",
    },

    # ── Tier: Ultra (64GB+ RAM, 24GB+ VRAM) ────────────────────
    {
        "name": "Llama 3.1 70B (Q4)",
        "type": "local",
        "repo": "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 40.0,
        "ram_required_gb": 64,
        "gpu_required": True,
        "gpu_brand": "NVIDIA",
        "min_vram_gb": 40,
        "tier": ["ultra", "godlike"],
        "speed": "~8 tokens/sec on 2x24GB VRAM",
        "quality": "Near-GPT-4 quality, exceptional",
        "use_case": "Enterprise tasks, complex analysis",
        "license": "Llama 3.1 Community",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
    },
    {
        "name": "Qwen2 72B (Q4)",
        "type": "local",
        "repo": "bartowski/Qwen2-72B-Instruct-GGUF",
        "quant": "Q4_K_M",
        "size_gb": 42.0,
        "ram_required_gb": 64,
        "gpu_required": True,
        "gpu_brand": "NVIDIA",
        "min_vram_gb": 40,
        "tier": ["ultra", "godlike"],
        "speed": "~7 tokens/sec on 2x24GB VRAM",
        "quality": "Multilingual powerhouse, near-GPT-4",
        "use_case": "Multilingual enterprise, research",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/bartowski/Qwen2-72B-Instruct-GGUF",
    },

    # ── Tier: Godlike (128GB+ RAM, 48GB+ VRAM) ─────────────────
    {
        "name": "Llama 3.1 70B (Q8)",
        "type": "local",
        "repo": "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
        "quant": "Q8_0",
        "size_gb": 73.0,
        "ram_required_gb": 96,
        "gpu_required": True,
        "gpu_brand": "NVIDIA",
        "min_vram_gb": 80,
        "tier": ["godlike"],
        "speed": "~5 tokens/sec on 4x24GB VRAM",
        "quality": "Near-lossless, GPT-4 class",
        "use_case": "Maximum quality, research, enterprise",
        "license": "Llama 3.1 Community",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
    },
    {
        "name": "Qwen2.5 72B (Q8)",
        "type": "local",
        "repo": "bartowski/Qwen2.5-72B-Instruct-GGUF",
        "quant": "Q8_0",
        "size_gb": 75.0,
        "ram_required_gb": 96,
        "gpu_required": True,
        "gpu_brand": "NVIDIA",
        "min_vram_gb": 80,
        "tier": ["godlike"],
        "speed": "~4 tokens/sec on 4x24GB VRAM",
        "quality": "Best open-source model available",
        "use_case": "Ultimate quality, everything",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF",
    },

    # ── Apple Silicon Optimized ──────────────────────────────────
    {
        "name": "Llama 3.1 8B (MLX)",
        "type": "local",
        "repo": "mlx-community/Meta-Llama-3.1-8B-Instruct",
        "quant": "mlx",
        "size_gb": 4.9,
        "ram_required_gb": 8,
        "gpu_required": True,
        "gpu_brand": "Apple",
        "min_vram_gb": 8,
        "tier": ["mid", "high"],
        "speed": "~40 tokens/sec on M1, ~60 on M2",
        "quality": "Optimized for Apple Silicon, blazing fast",
        "use_case": "Mac users, daily assistant",
        "license": "Llama 3.1 Community",
        "url": "https://huggingface.co/mlx-community/Meta-Llama-3.1-8B-Instruct",
    },
    {
        "name": "Qwen2 72B (MLX, M2/M3 Max)",
        "type": "local",
        "repo": "mlx-community/Qwen2-72B-Instruct-4bit",
        "quant": "mlx",
        "size_gb": 36.0,
        "ram_required_gb": 48,
        "gpu_required": True,
        "gpu_brand": "Apple",
        "min_vram_gb": 48,
        "tier": ["ultra", "godlike"],
        "speed": "~15 tokens/sec on M2 Max",
        "quality": "Best quality on Mac, full 72B",
        "use_case": "Apple Silicon power users",
        "license": "Apache 2.0",
        "url": "https://huggingface.co/mlx-community/Qwen2-72B-Instruct-4bit",
    },

    # ── Cloud API Recommendations (when local isn't viable) ─────
    {
        "name": "Groq (Llama 3.3 70B)",
        "type": "cloud_api",
        "repo": "groq",
        "cost": "Free tier: 30 req/min, 14,400 req/day",
        "speed": "~300 tokens/sec (fastest cloud)",
        "quality": "Excellent, near-GPT-4",
        "use_case": "When local hardware is insufficient",
        "requires": {"api_key": True, "env_var": "GROQ_API_KEY"},
        "tier": ["potato", "low", "mid", "high", "ultra", "godlike"],
        "url": "https://console.groq.com/keys",
        "setup": "Get free API key at console.groq.com, set GROQ_API_KEY in .env",
    },
    {
        "name": "OpenAI (GPT-4o)",
        "type": "cloud_api",
        "repo": "openai",
        "cost": "$2.50/1M input, $10/1M output",
        "speed": "~100 tokens/sec",
        "quality": "Best overall quality",
        "use_case": "Premium quality when cost is no concern",
        "requires": {"api_key": True, "env_var": "OPENAI_API_KEY"},
        "tier": ["potato", "low", "mid", "high", "ultra", "godlike"],
        "url": "https://platform.openai.com/api-keys",
    },
    {
        "name": "Anthropic (Claude 3.5 Sonnet)",
        "type": "cloud_api",
        "repo": "anthropic",
        "cost": "$3/1M input, $15/1M output",
        "speed": "~80 tokens/sec",
        "quality": "Best for long documents and analysis",
        "use_case": "Research, document analysis, coding",
        "requires": {"api_key": True, "env_var": "ANTHROPIC_API_KEY"},
        "tier": ["potato", "low", "mid", "high", "ultra", "godlike"],
        "url": "https://console.anthropic.com/",
    },
    {
        "name": "Google (Gemini 2.0 Flash)",
        "type": "cloud_api",
        "repo": "google",
        "cost": "Free tier: 15 RPM, 1M tokens/day",
        "speed": "~150 tokens/sec",
        "quality": "Fast, multimodal, free tier available",
        "use_case": "Fast responses, image understanding",
        "requires": {"api_key": True, "env_var": "GOOGLE_API_KEY"},
        "tier": ["potato", "low", "mid", "high", "ultra", "godlike"],
        "url": "https://aistudio.google.com/apikey",
    },
]


def _recommend_models(profile: HardwareProfile) -> list:
    """Recommend models based on hardware profile."""
    recommendations = []
    tier = profile.performance_tier

    for model in MODELS_DB:
        # Check if model matches this tier
        if tier not in model.get("tier", []):
            continue

        # Check RAM requirement
        if profile.ram_total_gb < model.get("ram_required_gb", 0):
            continue

        # Check GPU requirement
        if model.get("gpu_required", False):
            if profile.gpu_vram_gb < model.get("min_vram_gb", 0):
                # For cloud models, always include
                if model.get("type") == "cloud_api":
                    pass
                else:
                    continue

            # Check GPU brand compatibility
            model_gpu_brand = model.get("gpu_brand")
            if model_gpu_brand and model_gpu_brand != profile.gpu_brand:
                continue

        # Calculate fit score
        fit_score = 100
        ram_ratio = profile.ram_total_gb / max(model.get("ram_required_gb", 1), 1)
        if ram_ratio < 1.2:
            fit_score -= 20  # Tight on RAM
        elif ram_ratio > 3:
            fit_score += 10  # Plenty of headroom

        if profile.gpu_vram_gb > 0 and model.get("gpu_required"):
            vram_ratio = profile.gpu_vram_gb / max(model.get("min_vram_gb", 1), 1)
            if vram_ratio < 1.2:
                fit_score -= 15
            elif vram_ratio > 2:
                fit_score += 10

        recommendations.append({
            **model,
            "fit_score": min(fit_score, 100),
            "recommended": fit_score >= 90,
        })

    # Sort: recommended first, then by fit score
    recommendations.sort(key=lambda x: (-x.get("recommended", False), -x.get("fit_score", 0)))

    return recommendations


def _recommend_config(profile: HardwareProfile) -> dict:
    """Recommend optimal JARVIS configuration based on hardware."""
    config = {
        "local_model_enabled": False,
        "cloud_fallback": True,
        "max_concurrent_agents": 2,
        "voice_engine": "edge-tts",
        "rag_enabled": True,
        "headless_workstation": False,
        "proactive_monitoring": True,
    }

    tier = profile.performance_tier

    # Local model configuration
    if tier in ("mid", "high", "ultra", "godlike"):
        config["local_model_enabled"] = True
        config["local_model_threads"] = min(profile.cpu_threads, 8)
        config["local_model_batch_size"] = 512

        if profile.gpu_brand == "NVIDIA" and profile.gpu_vram_gb >= 8:
            config["local_model_gpu_layers"] = -1  # Offload all to GPU
            config["local_model_gpu_backend"] = "cuda"
        elif profile.gpu_brand == "Apple":
            config["local_model_gpu_backend"] = "metal"
            config["local_model_gpu_layers"] = -1
        elif profile.gpu_brand == "AMD":
            config["local_model_gpu_backend"] = "vulkan"
            config["local_model_gpu_layers"] = -1
        else:
            config["local_model_gpu_layers"] = 0  # CPU only
    else:
        config["local_model_enabled"] = False
        config["cloud_fallback"] = True

    # Voice engine
    if tier in ("mid", "high", "ultra", "godlike"):
        config["voice_engine"] = "kokoro-onnx"
    else:
        config["voice_engine"] = "edge-tts"

    # Concurrent agents
    if tier == "godlike":
        config["max_concurrent_agents"] = 10
    elif tier == "ultra":
        config["max_concurrent_agents"] = 6
    elif tier == "high":
        config["max_concurrent_agents"] = 4
    elif tier == "mid":
        config["max_concurrent_agents"] = 2
    else:
        config["max_concurrent_agents"] = 1

    # Headless workstation
    if tier in ("high", "ultra", "godlike") and profile.ram_total_gb >= 16:
        config["headless_workstation"] = True

    return config


# Global singleton
_profile: Optional[HardwareProfile] = None


def get_hardware_profile() -> HardwareProfile:
    """Get or detect the hardware profile."""
    global _profile
    if _profile is None:
        _profile = detect_hardware()
    return _profile


def refresh_hardware_profile() -> HardwareProfile:
    """Force re-detection of hardware."""
    global _profile
    _profile = detect_hardware()
    return _profile
