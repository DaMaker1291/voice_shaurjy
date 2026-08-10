"""JARVIS Model Provider — Single Interface for All AI.

Don't build:
  OpenAI integration
  Anthropic integration
  Gemini integration
  Groq integration
  ...

throughout the codebase.

Instead, one clean interface:

    ModelProvider
        .generate(prompt)      -> text
        .vision(image, prompt) -> text
        .reason(prompt)        -> text
        .code(prompt)          -> code
        .classify(text, labels) -> label
        .embed(text)           -> vector

Then a router selects the provider.
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

log = logging.getLogger("model_provider")


class TaskType(Enum):
    """Task types for model selection."""
    GENERATE = "generate"
    REASON = "reason"
    VISION = "vision"
    CODE = "code"
    CLASSIFY = "classify"
    EMBED = "embed"
    SUMMARIZE = "summarize"


@dataclass
class ModelResponse:
    """Universal response from any model."""
    text: str
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    latency_ms: float = 0
    cached: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
            "error": self.error,
        }


class ModelProvider(ABC):
    """Abstract interface for AI model providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available."""
        ...

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 1000,
                 temperature: float = 0.7, **kwargs) -> ModelResponse:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def vision(self, image_bytes: bytes, prompt: str,
               max_tokens: int = 1000) -> ModelResponse:
        """Analyze an image with a prompt."""
        ...

    @abstractmethod
    def code(self, prompt: str, language: str = "python",
             max_tokens: int = 2000) -> ModelResponse:
        """Generate code."""
        ...

    @abstractmethod
    def classify(self, text: str, labels: List[str]) -> ModelResponse:
        """Classify text into one of the given labels."""
        ...

    def reason(self, prompt: str, max_tokens: int = 2000) -> ModelResponse:
        """Reason through a complex problem (default: same as generate with higher tokens)."""
        return self.generate(prompt, max_tokens=max_tokens, temperature=0.3)

    def summarize(self, text: str, max_tokens: int = 500) -> ModelResponse:
        """Summarize text."""
        return self.generate(
            f"Summarize concisely:\n\n{text}",
            max_tokens=max_tokens,
            temperature=0.3,
        )

    def embed(self, text: str) -> ModelResponse:
        """Get embeddings (default: unsupported)."""
        return ModelResponse(text="", error="Embeddings not supported by this provider")


# ══════════════════════════════════════════════════════════════
#  GROQ PROVIDER (Free, fast)
# ══════════════════════════════════════════════════════════════

class GroqProvider(ModelProvider):
    """Groq — Free tier, fast inference."""

    def __init__(self):
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self._model = "llama-3.1-8b-instant"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, prompt: str, max_tokens: int = 1000,
                 temperature: float = 0.7, **kwargs) -> ModelResponse:
        try:
            from groq import Groq
            client = Groq(api_key=self._api_key)
            start = time.time()
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return ModelResponse(
                text=response.choices[0].message.content,
                model=self._model,
                provider="groq",
                tokens_used=response.usage.total_tokens if response.usage else 0,
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ModelResponse(text="", error=str(e), provider="groq")

    def vision(self, image_bytes: bytes, prompt: str,
               max_tokens: int = 1000) -> ModelResponse:
        # Groq vision support is limited; use generate with description
        return self.generate(prompt, max_tokens=max_tokens)

    def code(self, prompt: str, language: str = "python",
             max_tokens: int = 2000) -> ModelResponse:
        return self.generate(
            f"Write {language} code:\n{prompt}",
            max_tokens=max_tokens,
            temperature=0.2,
        )

    def classify(self, text: str, labels: List[str]) -> ModelResponse:
        labels_str = ", ".join(labels)
        return self.generate(
            f"Classify the following text into exactly one of: [{labels_str}]\n\nText: {text}\n\nRespond with ONLY the label.",
            max_tokens=50,
            temperature=0.1,
        )


# ══════════════════════════════════════════════════════════════
#  LOCAL GGUF PROVIDER (Offline, free)
# ══════════════════════════════════════════════════════════════

class LocalProvider(ModelProvider):
    """Local GGUF models via llama-cpp-python."""

    def __init__(self):
        self._model = None
        self._model_path = None
        self._find_model()

    def _find_model(self):
        """Find available GGUF model."""
        models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        if os.path.exists(models_dir):
            for f in os.listdir(models_dir):
                if f.endswith(".gguf"):
                    self._model_path = os.path.join(models_dir, f)
                    break

    def is_available(self) -> bool:
        if not self._model_path:
            return False
        try:
            from llama_cpp import Llama
            return True
        except ImportError:
            return False

    def _get_model(self):
        """Lazy-load the model."""
        if self._model is None:
            from llama_cpp import Llama
            self._model = Llama(model_path=self._model_path, n_ctx=4096, verbose=False)
        return self._model

    def generate(self, prompt: str, max_tokens: int = 1000,
                 temperature: float = 0.7, **kwargs) -> ModelResponse:
        try:
            model = self._get_model()
            start = time.time()
            output = model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["</s>", "\n\n"],
            )
            text = output["choices"][0]["text"]
            return ModelResponse(
                text=text,
                model=os.path.basename(self._model_path),
                provider="local",
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ModelResponse(text="", error=str(e), provider="local")

    def vision(self, image_bytes: bytes, prompt: str,
               max_tokens: int = 1000) -> ModelResponse:
        return ModelResponse(text="", error="Local GGUF does not support vision")

    def code(self, prompt: str, language: str = "python",
             max_tokens: int = 2000) -> ModelResponse:
        return self.generate(
            f"Write {language} code:\n{prompt}",
            max_tokens=max_tokens,
            temperature=0.2,
        )

    def classify(self, text: str, labels: List[str]) -> ModelResponse:
        labels_str = ", ".join(labels)
        return self.generate(
            f"Classify into one of: [{labels_str}]\nText: {text}\nLabel:",
            max_tokens=50,
            temperature=0.1,
        )


# ══════════════════════════════════════════════════════════════
#  HYPERLOCAL PROVIDER (Zero ML, pure algorithms)
# ══════════════════════════════════════════════════════════════

class HyperLocalProvider(ModelProvider):
    """Zero-ML local provider using TF-IDF, BM25, regex.

    Works with zero API keys, zero models, zero RAM.
    """

    def is_available(self) -> bool:
        return True  # Always available

    def generate(self, prompt: str, max_tokens: int = 1000,
                 temperature: float = 0.7, **kwargs) -> ModelResponse:
        # Use regex-based responses for simple queries
        from hyperlocal_ai import get_hyperlocal
        engine = get_hyperlocal()
        results = engine.search(prompt)
        if results:
            return ModelResponse(
                text=str(results[0].get("content", "")),
                provider="hyperlocal",
            )
        return ModelResponse(text="I can help with that. Please provide more details.")

    def vision(self, image_bytes: bytes, prompt: str,
               max_tokens: int = 1000) -> ModelResponse:
        return ModelResponse(text="Vision requires a cloud provider", provider="hyperlocal")

    def code(self, prompt: str, language: str = "python",
             max_tokens: int = 2000) -> ModelResponse:
        return ModelResponse(text="", error="Code generation requires a model provider")

    def classify(self, text: str, labels: List[str]) -> ModelResponse:
        # Simple keyword-based classification
        text_lower = text.lower()
        best_label = labels[0] if labels else ""
        best_score = 0
        for label in labels:
            score = sum(1 for word in label.lower().split() if word in text_lower)
            if score > best_score:
                best_score = score
                best_label = label
        return ModelResponse(text=best_label, provider="hyperlocal")


# ══════════════════════════════════════════════════════════════
#  MODEL ROUTER — Selects the best provider
# ══════════════════════════════════════════════════════════════

class ModelRouter:
    """Routes requests to the best available model provider.

    Priority:
      1. Groq (free, fast)
      2. Local GGUF (offline, free)
      3. HyperLocal (zero ML, always available)
    """

    def __init__(self):
        self._providers: List[ModelProvider] = []
        self._init_providers()

    def _init_providers(self):
        """Initialize providers in priority order."""
        # Always add HyperLocal as fallback
        self._providers.append(HyperLocalProvider())

        # Try Local GGUF
        local = LocalProvider()
        if local.is_available():
            self._providers.insert(0, local)

        # Try Groq (highest priority if available)
        groq = GroqProvider()
        if groq.is_available():
            self._providers.insert(0, groq)

        log.info(f"[MODEL] Router initialized with {len(self._providers)} providers: "
                 f"{[type(p).__name__ for p in self._providers]}")

    def select_provider(self, task_type: TaskType = TaskType.GENERATE) -> ModelProvider:
        """Select the best provider for a task type."""
        for provider in self._providers:
            if provider.is_available():
                return provider
        return HyperLocalProvider()  # Ultimate fallback

    def generate(self, prompt: str, max_tokens: int = 1000,
                 temperature: float = 0.7, **kwargs) -> ModelResponse:
        """Generate text using the best available provider."""
        provider = self.select_provider(TaskType.GENERATE)
        return provider.generate(prompt, max_tokens, temperature, **kwargs)

    def vision(self, image_bytes: bytes, prompt: str,
               max_tokens: int = 1000) -> ModelResponse:
        """Analyze image using the best available provider."""
        # Try providers that support vision
        for provider in self._providers:
            if provider.is_available():
                result = provider.vision(image_bytes, prompt, max_tokens)
                if not result.error:
                    return result
        return ModelResponse(text="", error="No vision provider available")

    def code(self, prompt: str, language: str = "python",
             max_tokens: int = 2000) -> ModelResponse:
        """Generate code using the best available provider."""
        provider = self.select_provider(TaskType.CODE)
        return provider.code(prompt, language, max_tokens)

    def reason(self, prompt: str, max_tokens: int = 2000) -> ModelResponse:
        """Reason through complex problems."""
        provider = self.select_provider(TaskType.REASON)
        return provider.reason(prompt, max_tokens)

    def classify(self, text: str, labels: List[str]) -> ModelResponse:
        """Classify text."""
        provider = self.select_provider(TaskType.CLASSIFY)
        return provider.classify(text, labels)

    def get_status(self) -> Dict[str, Any]:
        """Get provider status."""
        return {
            "providers": [
                {
                    "name": type(p).__name__,
                    "available": p.is_available(),
                }
                for p in self._providers
            ],
            "active": type(self.select_provider()).__name__,
        }


# ── Singleton ──
_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def generate(prompt: str, **kwargs) -> str:
    """Convenience function for text generation."""
    router = get_model_router()
    response = router.generate(prompt, **kwargs)
    return response.text


def vision(image_bytes: bytes, prompt: str, **kwargs) -> str:
    """Convenience function for vision analysis."""
    router = get_model_router()
    response = router.vision(image_bytes, prompt, **kwargs)
    return response.text
