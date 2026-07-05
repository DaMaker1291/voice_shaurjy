"""
Local GGUF Model Deployment and Inference Engine for JARVIS.

Provides a singleton `LocalModelEngine` that manages downloading, loading,
and running inference on GGUF quantized models via llama-cpp-python.
Supports grammar-constrained decoding (GBNF) for structured output routing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
_GRAMMAR_DIRS = [
    os.path.join(os.path.dirname(__file__), "grammars"),
    os.path.join(os.path.dirname(__file__), "..", "grammars"),
]

# Preferred model download order (repo_id, filename fragment, quantization)
# Tiered by hardware capability: smallest first for consumer laptops
_PREFERRED_MODELS = [
    # Tier 1: Ultra-light (< 1.5GB RAM) — any laptop, any age
    {
        "repo_id": "bartowski/Qwen2.5-1.5B-Instruct-GGUF",
        "filename": "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
        "quantization": "Q4_K_M",
        "tier": 1,
        "ram_required_mb": 1200,
        "description": "Qwen 1.5B — instant routing, <10ms TTFT",
    },
    # Tier 2: Light (< 2.5GB RAM) — standard office laptops
    {
        "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "quantization": "Q4_K_M",
        "tier": 2,
        "ram_required_mb": 2200,
        "description": "Llama 3.2 3B — balanced speed/quality",
    },
    # Tier 3: Medium (< 5GB RAM) — modern laptops with 8GB+ RAM
    {
        "repo_id": "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "filename": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "quantization": "Q4_K_M",
        "tier": 3,
        "ram_required_mb": 4500,
        "description": "Qwen 7B — strong reasoning, needs 8GB+ RAM",
    },
    # Tier 4: Heavy (< 6GB RAM) — machines with 16GB+ RAM
    {
        "repo_id": "bartowski/Meta-Llama-3-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
        "quantization": "Q4_K_M",
        "tier": 4,
        "ram_required_mb": 5500,
        "description": "Llama 3 8B — full capability, needs 16GB+ RAM",
    },
]


def _get_available_ram_mb() -> int:
    """Return available system RAM in MB."""
    try:
        import psutil
        return psutil.virtual_memory().total // (1024 * 1024)
    except ImportError:
        return 8192  # assume 8GB if psutil unavailable


def _select_model_for_hardware() -> list[dict]:
    """Return preferred models sorted by fit for current hardware.
    
    Picks the largest model that fits comfortably in available RAM,
    with a 20% headroom buffer.
    """
    ram_mb = _get_available_ram_mb()
    usable_mb = int(ram_mb * 0.8)  # 20% headroom for OS + other apps
    
    # Filter models that fit, sort by tier (largest first)
    candidates = [
        m for m in _PREFERRED_MODELS
        if m["ram_required_mb"] <= usable_mb
    ]
    candidates.sort(key=lambda m: m["tier"], reverse=True)
    
    if candidates:
        logger.info(
            "Hardware: %dMB RAM, %dMB usable → selecting tier %d model (%s)",
            ram_mb, usable_mb, candidates[0]["tier"], candidates[0]["description"]
        )
        return candidates
    
    # Fallback: smallest model regardless of RAM
    logger.warning("Low RAM (%dMB), falling back to smallest model", ram_mb)
    return [_PREFERRED_MODELS[0]]


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _resolve_model_path(model_dir: str, name: str) -> str:
    """Return an absolute path for *name* inside *model_dir*."""
    return str(Path(model_dir).resolve() / name)


def _format_size(size_bytes: int) -> str:
    """Human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    return f"{size_bytes / (1024 ** 3):.2f} GB"


def _parse_quantization(filename: str) -> str:
    """Extract quantization tag from a GGUF filename like `Model-Q4_K_M.gguf`."""
    stem = Path(filename).stem
    for tag in ("Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S", "Q5_0", "Q4_K_M", "Q4_K_S", "Q4_0", "Q3_K_M", "Q3_K_S", "IQ4_XS", "IQ3_XXS", "IQ2_XXS"):
        if tag in stem:
            return tag
    return "unknown"


# ---------------------------------------------------------------------------
# LocalModelEngine
# ---------------------------------------------------------------------------

class LocalModelEngine:
    """Singleton engine for managing and running local GGUF models.

    Thread-safety model:
      - ``_load_lock`` serialises model load / unload operations.
      - Concurrent ``inference`` calls are allowed because llama-cpp-python's
        ``Llama`` instance is safe for concurrent ``__call__`` when
        ``n_threads`` is set appropriately.
    """

    def __init__(self, model_dir: str = _DEFAULT_MODEL_DIR) -> None:
        self._model_dir = os.path.abspath(model_dir)
        os.makedirs(self._model_dir, exist_ok=True)

        self._llama: Any = None          # Llama instance (lazily imported)
        self._model_name: Optional[str] = None
        self._model_path: Optional[str] = None
        self._model_meta: dict[str, Any] = {}
        self._loaded = False
        self._load_lock = threading.Lock()

        # Grammar cache: path_str -> LlamaGrammar
        self._grammar_cache: dict[str, Any] = {}

        # Performance stats
        self._stats: dict[str, Any] = {
            "total_inferences": 0,
            "total_tokens_generated": 0,
            "total_latency_ms": 0.0,
            "tokens_per_second_history": [],
            "load_events": [],
        }
        self._stats_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def model_dir(self) -> str:
        return self._model_dir

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------

    def list_available_models(self) -> list[dict]:
        """Scan the model directory for ``*.gguf`` files.

        Returns a list of dicts with keys:
            ``name``, ``path``, ``size_bytes``, ``size_human``, ``quantization``.
        """
        models: list[dict] = []
        for entry in sorted(Path(self._model_dir).iterdir()):
            if entry.suffix.lower() == ".gguf" and entry.is_file():
                size = entry.stat().st_size
                models.append({
                    "name": entry.name,
                    "path": str(entry.resolve()),
                    "size_bytes": size,
                    "size_human": _format_size(size),
                    "quantization": _parse_quantization(entry.name),
                })
        return models

    # ------------------------------------------------------------------
    # Model download
    # ------------------------------------------------------------------

    def download_model(
        self,
        repo_id: str,
        filename: str | None = None,
        quantization: str = "Q4_K_M",
    ) -> str:
        """Download a GGUF file from HuggingFace Hub.

        If *filename* is ``None`` the first file matching *quantization* in the
        repo is selected.  Returns the local path of the downloaded file.

        Requires ``huggingface_hub`` (``pip install huggingface_hub``).
        """
        try:
            from huggingface_hub import hf_hub_download, HfApi  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "huggingface_hub is required for model downloads.  "
                "Install it with: pip install huggingface_hub"
            ) from exc

        if filename is None:
            api = HfApi()
            files = api.list_repo_files(repo_id)
            candidates = [
                f for f in files
                if f.endswith(".gguf") and quantization.upper() in f.upper()
            ]
            if not candidates:
                raise FileNotFoundError(
                    f"No GGUF file with quantization '{quantization}' found in {repo_id}"
                )
            filename = candidates[0]

        dest_path = _resolve_model_path(self._model_dir, filename)
        if os.path.isfile(dest_path):
            logger.info("Model already downloaded: %s", dest_path)
            return dest_path

        logger.info("Downloading %s/%s ...", repo_id, filename)
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=self._model_dir,
            local_dir_use_symlinks=False,
        )
        # HF may download into a cache dir; move to model_dir if needed
        if os.path.abspath(downloaded) != dest_path:
            import shutil
            shutil.move(downloaded, dest_path)
        logger.info("Downloaded to %s", dest_path)
        return dest_path

    # ------------------------------------------------------------------
    # Auto-download helper
    # ------------------------------------------------------------------

    def _ensure_model_available(self) -> Optional[str]:
        """Return a model path, auto-downloading the best model for current hardware."""
        models = self.list_available_models()
        if models:
            # Try to pick the best model for current hardware
            hw_models = _select_model_for_hardware()
            for pref in hw_models:
                for m in models:
                    if m["name"] == pref["filename"]:
                        return m["path"]
            # If no hardware-matched model, return largest available
            models.sort(key=lambda m: m.get("size_bytes", 0), reverse=True)
            return models[0]["path"]

        # No models found – download best model for hardware
        hw_models = _select_model_for_hardware()
        logger.info("No local GGUF models found. Downloading model for current hardware...")
        for pref in hw_models:
            try:
                path = self.download_model(
                    repo_id=pref["repo_id"],
                    filename=pref["filename"],
                    quantization=pref["quantization"],
                )
                logger.info("Auto-downloaded %s (%s)", pref["filename"], pref["description"])
                return path
            except Exception as exc:
                logger.warning("Failed to download %s: %s", pref["filename"], exc)
        return None

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    def load_model(self, model_name: str | None = None) -> bool:
        """Load a GGUF model into memory.

        If *model_name* is ``None`` the best available model is auto-selected.
        Returns ``True`` on success, ``False`` if no model could be loaded.
        """
        with self._load_lock:
            if self._loaded:
                logger.info("Model already loaded: %s", self._model_name)
                return True

            try:
                from llama_cpp import Llama  # type: ignore[import-untyped]
            except ImportError as exc:
                logger.error(
                    "llama-cpp-python is required. Install with: "
                    "pip install llama-cpp-python"
                )
                return False

            # Resolve model path
            if model_name:
                path = _resolve_model_path(self._model_dir, model_name)
                if not os.path.isfile(path):
                    logger.error("Model file not found: %s", path)
                    return False
            else:
                path = self._ensure_model_available()
                if path is None:
                    logger.warning("No local model available for loading.")
                    return False

            logger.info("Loading model from %s ...", path)
            t0 = time.perf_counter()

            try:
                n_ctx = int(os.environ.get("LOCAL_MODEL_CTX", "4096"))
                n_threads = int(os.environ.get("LOCAL_MODEL_THREADS", "4"))
                
                # Auto-tune threads based on CPU cores
                try:
                    import multiprocessing
                    cpu_count = multiprocessing.cpu_count()
                    if n_threads == 4 and cpu_count <= 4:
                        n_threads = max(2, cpu_count - 1)
                    elif n_threads == 4 and cpu_count > 8:
                        n_threads = min(8, cpu_count // 2)
                except Exception:
                    pass

                # Detect model size and adjust context window
                model_size_gb = os.path.getsize(path) / (1024 ** 3)
                if model_size_gb < 2.0:
                    # Small model (< 2GB): use larger context for routing
                    n_ctx = min(n_ctx, 8192)
                elif model_size_gb < 4.0:
                    # Medium model: standard context
                    n_ctx = min(n_ctx, 4096)
                
                self._llama = Llama(
                    model_path=path,
                    n_ctx=n_ctx,
                    n_threads=n_threads,
                    verbose=False,
                )
            except Exception as exc:
                logger.error("Failed to load model %s: %s", path, exc)
                self._llama = None
                return False

            elapsed = (time.perf_counter() - t0) * 1000
            self._model_name = os.path.basename(path)
            self._model_path = path
            self._model_meta = {
                "name": self._model_name,
                "path": path,
                "n_ctx": n_ctx,
                "n_threads": n_threads,
                "quantization": _parse_quantization(self._model_name),
                "size_bytes": os.path.getsize(path),
                "size_human": _format_size(os.path.getsize(path)),
            }
            self._loaded = True

            with self._stats_lock:
                self._stats["load_events"].append({
                    "model": self._model_name,
                    "timestamp": time.time(),
                    "load_time_ms": round(elapsed, 1),
                })

            logger.info("Model loaded in %.0f ms", elapsed)
            return True

    def unload_model(self) -> None:
        """Free the currently loaded model from memory."""
        with self._load_lock:
            if not self._loaded:
                return
            name = self._model_name
            self._llama = None
            self._model_name = None
            self._model_path = None
            self._model_meta = {}
            self._loaded = False
            logger.info("Unloaded model: %s", name)

    def is_loaded(self) -> bool:
        return self._loaded

    def get_model_info(self) -> dict:
        """Return metadata about the currently loaded model (or empty dict)."""
        return dict(self._model_meta) if self._loaded else {}

    # ------------------------------------------------------------------
    # Grammar helpers
    # ------------------------------------------------------------------

    def _resolve_grammar(self, grammar: Any) -> Any:
        """Accept a LlamaGrammar, a file path string, or a grammar name."""
        if grammar is None:
            return None

        # Already a grammar object
        if hasattr(grammar, "rules"):
            return grammar

        # String path
        grammar_str = str(grammar)
        if os.path.isfile(grammar_str):
            return self._load_grammar_file(grammar_str)

        # Try as a name in the grammar directories
        for gdir in _GRAMMAR_DIRS:
            candidate = os.path.join(gdir, grammar_str)
            if os.path.isfile(candidate):
                return self._load_grammar_file(candidate)
            # Also try with .gbnf extension
            candidate_gbnf = candidate if candidate.endswith(".gbnf") else candidate + ".gbnf"
            if os.path.isfile(candidate_gbnf):
                return self._load_grammar_file(candidate_gbnf)

        logger.warning("Grammar not found: %s. Proceeding without grammar.", grammar)
        return None

    def _load_grammar_file(self, path: str) -> Any:
        """Load and cache a GBNF grammar from disk."""
        if path in self._grammar_cache:
            return self._grammar_cache[path]
        try:
            from llama_cpp import LlamaGrammar  # type: ignore[import-untyped]
            grammar_text = Path(path).read_text(encoding="utf-8")
            grammar = LlamaGrammar.from_string(grammar_text)
            self._grammar_cache[path] = grammar
            return grammar
        except Exception as exc:
            logger.warning("Failed to load grammar %s: %s", path, exc)
            return None

    # ------------------------------------------------------------------
    # Stats helpers
    # ------------------------------------------------------------------

    def _record_inference(self, tokens: int, latency_ms: float) -> None:
        tps = (tokens / (latency_ms / 1000)) if latency_ms > 0 else 0.0
        with self._stats_lock:
            self._stats["total_inferences"] += 1
            self._stats["total_tokens_generated"] += tokens
            self._stats["total_latency_ms"] += latency_ms
            self._stats["tokens_per_second_history"].append(round(tps, 1))

    def get_stats(self) -> dict:
        """Return aggregate performance statistics."""
        with self._stats_lock:
            hist = self._stats["tokens_per_second_history"]
            avg_tps = round(sum(hist) / len(hist), 1) if hist else 0.0
            ram_mb = _get_available_ram_mb()
            return {
                "model_loaded": self._loaded,
                "model_name": self._model_name,
                "total_inferences": self._stats["total_inferences"],
                "total_tokens_generated": self._stats["total_tokens_generated"],
                "total_latency_ms": round(self._stats["total_latency_ms"], 1),
                "avg_tokens_per_second": avg_tps,
                "best_tokens_per_second": max(hist) if hist else 0.0,
                "load_events": list(self._stats["load_events"]),
                "hardware": {
                    "ram_total_mb": ram_mb,
                    "ram_total_human": _format_size(ram_mb * 1024 * 1024),
                },
                "model_tier": self._get_model_tier(),
            }
    
    def _get_model_tier(self) -> dict:
        """Return tier info for the currently loaded model."""
        if not self._model_name:
            return {"tier": 0, "description": "no model loaded"}
        for pref in _PREFERRED_MODELS:
            if pref["filename"] in self._model_name:
                return {
                    "tier": pref["tier"],
                    "description": pref["description"],
                    "ram_required_mb": pref["ram_required_mb"],
                }
        return {"tier": 0, "description": self._model_name}
    
    def is_local_routing_available(self) -> bool:
        """Check if local routing is ready (model loaded + grammar available)."""
        if not self._loaded or self._llama is None:
            return False
        try:
            self._resolve_grammar("router")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def inference(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.1,
        grammar: Any = None,
    ) -> dict:
        """Run a chat-completion style inference.

        Returns::

            {
                "text": str,                # generated response
                "tokens_generated": int,
                "latency_ms": float,
                "tokens_per_second": float,
                "model": str,               # loaded model name
            }

        Raises ``RuntimeError`` if no model is loaded.
        """
        if not self._loaded or self._llama is None:
            raise RuntimeError(
                "No model loaded. Call load_model() first or check is_loaded()."
            )

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        grammar_obj = self._resolve_grammar(grammar)

        t0 = time.perf_counter()
        try:
            kwargs: dict[str, Any] = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if grammar_obj is not None:
                kwargs["grammar"] = grammar_obj

            response = self._llama.create_chat_completion(**kwargs)
        except Exception as exc:
            logger.error("Inference failed: %s", exc)
            raise

        latency_ms = (time.perf_counter() - t0) * 1000

        text = response["choices"][0]["message"]["content"] or ""
        usage = response.get("usage", {})
        tokens_generated = usage.get("completion_tokens", 0) or len(text.split())

        tps = (tokens_generated / (latency_ms / 1000)) if latency_ms > 0 else 0.0
        self._record_inference(tokens_generated, latency_ms)

        return {
            "text": text,
            "tokens_generated": tokens_generated,
            "latency_ms": round(latency_ms, 1),
            "tokens_per_second": round(tps, 1),
            "model": self._model_name or "",
        }

    # ------------------------------------------------------------------
    # Intent routing (structured output)
    # ------------------------------------------------------------------

    def route_intent(self, user_text: str) -> dict:
        """Fast routing inference using the ``router`` GBNF grammar.
        
        Optimized for small models (1.5B-3B): uses minimal tokens,
        temperature=0.0 for deterministic output, and tight grammar constraints.

        Returns the parsed JSON dict produced by the grammar-constrained model.
        Falls back to a simple text response if grammar is unavailable.
        """
        system = (
            "You are an intent router for JARVIS. Analyse the user's text and "
            "produce a JSON object matching the provided grammar schema. "
            "Keep reasoning minimal; output only the JSON."
        )
        result = self.inference(
            prompt=user_text,
            system=system,
            max_tokens=64,  # Small models: keep output tight
            temperature=0.0,  # Deterministic routing
            grammar="router",
        )
        raw = result["text"].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from the text
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    parsed = {"intent": "unknown", "raw": raw}
            else:
                parsed = {"intent": "unknown", "raw": raw}

        parsed["_meta"] = {
            "latency_ms": result["latency_ms"],
            "tokens_per_second": result["tokens_per_second"],
            "model": result["model"],
            "local_routing": True,
        }
        return parsed

    # ------------------------------------------------------------------
    # Worker agent inference
    # ------------------------------------------------------------------

    def worker_inference(self, agent_type: str, prompt: str) -> dict:
        """Run inference scoped to a specific worker agent type.

        Automatically applies the matching GBNF grammar if one exists for
        *agent_type* (e.g. ``"hal_agent"``, ``"os_agent"``, ``"web_agent"``).
        """
        grammar_name = f"{agent_type}.gbnf" if not agent_type.endswith(".gbnf") else agent_type

        system_prompts = {
            "hal_agent": (
                "You are HAL, the system-level agent for JARVIS. "
                "Respond with structured JSON following the grammar rules."
            ),
            "os_agent": (
                "You are the OS Agent for JARVIS. "
                "Produce JSON output matching the provided grammar."
            ),
            "web_agent": (
                "You are the Web Agent for JARVIS. "
                "Produce JSON output matching the provided grammar."
            ),
        }
        system = system_prompts.get(agent_type, f"You are the {agent_type} agent for JARVIS.")

        result = self.inference(
            prompt=prompt,
            system=system,
            max_tokens=512,
            temperature=0.1,
            grammar=grammar_name,
        )

        raw = result["text"].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    parsed = {"response": raw, "parse_error": True}
            else:
                parsed = {"response": raw, "parse_error": True}

        parsed["_meta"] = {
            "agent_type": agent_type,
            "latency_ms": result["latency_ms"],
            "tokens_per_second": result["tokens_per_second"],
            "model": result["model"],
        }
        return parsed


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

engine = LocalModelEngine()
