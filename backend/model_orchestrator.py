"""JARVIS Model Orchestrator — Route tasks to the best available model.

Instead of depending on one LLM, JARVIS selects the optimal model
for each task based on capabilities, cost, latency, and availability.

Architecture:
    Task → Analyze Requirements → Select Model → Execute → Verify

Model hierarchy:
    - Coding tasks → Codex / Claude / DeepSeek
    - Vision tasks → GPT-4V / Claude / Gemini
    - Fast/simple → Llama 3 / Groq
    - Complex reasoning → Claude / GPT-4
    - Budget → Open-source (Llama, Mistral, Qwen)
"""

import os
import json
import time
import logging
import hashlib
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("model_orchestrator")


class TaskType(Enum):
    CHAT = "chat"
    CODING = "coding"
    VISION = "vision"
    REASONING = "reasoning"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"
    EMBEDDING = "embedding"
    PLANNING = "planning"


class ModelCapability(Enum):
    TEXT = "text"
    VISION = "vision"
    CODE = "code"
    FUNCTION_CALL = "function_call"
    LONG_CONTEXT = "long_context"
    FAST = "fast"
    CHEAP = "cheap"
    REASONING = "reasoning"


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    provider: str
    capabilities: List[ModelCapability] = field(default_factory=list)
    max_tokens: int = 8192
    cost_per_1k_tokens: float = 0.0
    latency_ms: int = 1000
    available: bool = False
    api_key_env: str = ""
    base_url: str = ""
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelSelection:
    """Result of model selection for a task."""
    model_id: str
    provider: str
    reason: str
    estimated_cost: float = 0.0
    estimated_latency_ms: int = 0


class ModelOrchestrator:
    """Selects and routes to the best model for each task."""

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._load_default_models()
        self._check_availability()

    def _load_default_models(self):
        """Register all known models."""
        defaults = [
            ModelInfo(
                id="groq-llama3-70b",
                name="Llama 3 70B",
                provider="groq",
                capabilities=[ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FAST],
                max_tokens=8192,
                cost_per_1k_tokens=0.0,
                latency_ms=200,
                api_key_env="GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1",
                extra_params={"model": "llama3-70b-8192"},
            ),
            ModelInfo(
                id="groq-llama3-8b",
                name="Llama 3 8B",
                provider="groq",
                capabilities=[ModelCapability.TEXT, ModelCapability.FAST],
                max_tokens=8192,
                cost_per_1k_tokens=0.0,
                latency_ms=100,
                api_key_env="GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1",
                extra_params={"model": "llama3-8b-8192"},
            ),
            ModelInfo(
                id="groq-mixtral",
                name="Mixtral 8x7B",
                provider="groq",
                capabilities=[ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FAST],
                max_tokens=32768,
                cost_per_1k_tokens=0.0,
                latency_ms=150,
                api_key_env="GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1",
                extra_params={"model": "mixtral-8x7b-32768"},
            ),
            ModelInfo(
                id="openai-gpt4",
                name="GPT-4 Turbo",
                provider="openai",
                capabilities=[ModelCapability.TEXT, ModelCapability.VISION, ModelCapability.CODE,
                             ModelCapability.REASONING, ModelCapability.LONG_CONTEXT],
                max_tokens=128000,
                cost_per_1k_tokens=0.01,
                latency_ms=2000,
                api_key_env="OPENAI_API_KEY",
                base_url="https://api.openai.com/v1",
                extra_params={"model": "gpt-4-turbo-preview"},
            ),
            ModelInfo(
                id="openai-gpt4o",
                name="GPT-4o",
                provider="openai",
                capabilities=[ModelCapability.TEXT, ModelCapability.VISION, ModelCapability.CODE,
                             ModelCapability.REASONING, ModelCapability.LONG_CONTEXT, ModelCapability.FAST],
                max_tokens=128000,
                cost_per_1k_tokens=0.005,
                latency_ms=800,
                api_key_env="OPENAI_API_KEY",
                base_url="https://api.openai.com/v1",
                extra_params={"model": "gpt-4o"},
            ),
            ModelInfo(
                id="anthropic-claude-3.5",
                name="Claude 3.5 Sonnet",
                provider="anthropic",
                capabilities=[ModelCapability.TEXT, ModelCapability.VISION, ModelCapability.CODE,
                             ModelCapability.REASONING, ModelCapability.LONG_CONTEXT],
                max_tokens=200000,
                cost_per_1k_tokens=0.015,
                latency_ms=1500,
                api_key_env="ANTHROPIC_API_KEY",
                extra_params={"model": "claude-3-5-sonnet-20241022", "max_tokens": 8192},
            ),
            ModelInfo(
                id="anthropic-claude-3-opus",
                name="Claude 3 Opus",
                provider="anthropic",
                capabilities=[ModelCapability.TEXT, ModelCapability.VISION, ModelCapability.CODE,
                             ModelCapability.REASONING, ModelCapability.LONG_CONTEXT],
                max_tokens=200000,
                cost_per_1k_tokens=0.075,
                latency_ms=2000,
                api_key_env="ANTHROPIC_API_KEY",
                extra_params={"model": "claude-3-opus-20240229", "max_tokens": 4096},
            ),
            ModelInfo(
                id="google-gemini-pro",
                name="Gemini 1.5 Pro",
                provider="google",
                capabilities=[ModelCapability.TEXT, ModelCapability.VISION, ModelCapability.CODE,
                             ModelCapability.REASONING, ModelCapability.LONG_CONTEXT],
                max_tokens=1000000,
                cost_per_1k_tokens=0.00125,
                latency_ms=1200,
                api_key_env="GOOGLE_API_KEY",
                extra_params={"model": "gemini-1.5-pro"},
            ),
            ModelInfo(
                id="deepseek-coder",
                name="DeepSeek Coder",
                provider="deepseek",
                capabilities=[ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.REASONING],
                max_tokens=16384,
                cost_per_1k_tokens=0.00014,
                latency_ms=800,
                api_key_env="DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com/v1",
                extra_params={"model": "deepseek-coder"},
            ),
            ModelInfo(
                id="ollama-local",
                name="Local (Ollama)",
                provider="ollama",
                capabilities=[ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.FAST],
                max_tokens=8192,
                cost_per_1k_tokens=0.0,
                latency_ms=500,
                base_url="http://localhost:11434/v1",
                extra_params={"model": "llama3.1:70b"},
            ),
            ModelInfo(
                id="local-embeddings",
                name="Local Embeddings",
                provider="local",
                capabilities=[ModelCapability.TEXT],
                max_tokens=8192,
                cost_per_1k_tokens=0.0,
                latency_ms=50,
                extra_params={"model": "BAAI/bge-small-en-v1.5"},
            ),
        ]

        for model in defaults:
            self._models[model.id] = model

    def _check_availability(self):
        """Check which models have API keys configured."""
        for model_id, model in self._models.items():
            if model.provider == "ollama" or model.provider == "local":
                # Check if local server is running
                model.available = self._check_local_available(model)
            elif model.api_key_env:
                api_key = os.environ.get(model.api_key_env, "")
                model.available = bool(api_key)
                if model.available:
                    log.info(f"[ORCHESTRATOR] Model available: {model_id} ({model.provider})")

    def _check_local_available(self, model: ModelInfo) -> bool:
        """Check if a local model server is running."""
        try:
            import httpx
            resp = httpx.get(f"{model.base_url}/models", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def select_model(self, task_type: TaskType, prefer_capabilities: List[ModelCapability] = None,
                    max_cost: float = None, prefer_fast: bool = False) -> Optional[ModelSelection]:
        """Select the best model for a task."""
        candidates = []

        for model_id, model in self._models.items():
            if not model.available:
                continue

            # Check task compatibility
            score = self._score_model(model, task_type, prefer_capabilities, prefer_fast)
            if score <= 0:
                continue

            # Check cost constraint
            if max_cost and model.cost_per_1k_tokens > max_cost:
                continue

            candidates.append((score, model))

        if not candidates:
            # Fallback to first available model
            for model_id, model in self._models.items():
                if model.available:
                    return ModelSelection(
                        model_id=model_id,
                        provider=model.provider,
                        reason="Fallback (no ideal match)",
                        estimated_cost=model.cost_per_1k_tokens,
                        estimated_latency_ms=model.latency_ms,
                    )
            return None

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]

        return ModelSelection(
            model_id=best.id,
            provider=best.provider,
            reason=f"Best match for {task_type.value} (score: {candidates[0][0]:.1f})",
            estimated_cost=best.cost_per_1k_tokens,
            estimated_latency_ms=best.latency_ms,
        )

    def _score_model(self, model: ModelInfo, task_type: TaskType,
                    prefer_capabilities: List[ModelCapability] = None,
                    prefer_fast: bool = False) -> float:
        """Score a model for a given task. Higher = better match."""
        score = 0.0

        # Capability matching for task type
        task_capability_map = {
            TaskType.CODING: ModelCapability.CODE,
            TaskType.VISION: ModelCapability.VISION,
            TaskType.REASONING: ModelCapability.REASONING,
            TaskType.CREATIVE: ModelCapability.TEXT,
            TaskType.ANALYSIS: ModelCapability.REASONING,
            TaskType.SUMMARIZATION: ModelCapability.TEXT,
            TaskType.PLANNING: ModelCapability.REASONING,
            TaskType.CHAT: ModelCapability.TEXT,
            TaskType.EMBEDDING: ModelCapability.TEXT,
        }

        required_cap = task_capability_map.get(task_type)
        if required_cap and required_cap in model.capabilities:
            score += 10.0
        elif required_cap == ModelCapability.TEXT and ModelCapability.TEXT not in model.capabilities:
            return 0.0  # Can't do text tasks without text capability

        # Preferred capabilities
        if prefer_capabilities:
            for cap in prefer_capabilities:
                if cap in model.capabilities:
                    score += 5.0

        # Speed bonus
        if prefer_fast and ModelCapability.FAST in model.capabilities:
            score += 3.0

        # Cost bonus (prefer cheaper)
        if model.cost_per_1k_tokens == 0:
            score += 2.0  # Free models get bonus
        else:
            score += max(0, 1.0 - (model.cost_per_1k_tokens * 100))

        # Latency bonus
        if model.latency_ms < 500:
            score += 2.0
        elif model.latency_ms < 1000:
            score += 1.0

        return score

    async def call_model(self, model_id: str, messages: List[dict], **kwargs) -> dict:
        """Call a specific model with messages."""
        model = self._models.get(model_id)
        if not model:
            return {"error": f"Model {model_id} not found"}

        if not model.available:
            return {"error": f"Model {model_id} not available"}

        try:
            if model.provider == "groq":
                return await self._call_groq(model, messages, **kwargs)
            elif model.provider == "openai":
                return await self._call_openai(model, messages, **kwargs)
            elif model.provider == "anthropic":
                return await self._call_anthropic(model, messages, **kwargs)
            elif model.provider == "deepseek":
                return await self._call_openai_compatible(model, messages, **kwargs)
            elif model.provider == "ollama":
                return await self._call_openai_compatible(model, messages, **kwargs)
            else:
                return {"error": f"Unknown provider: {model.provider}"}
        except Exception as e:
            log.error(f"[ORCHESTRATOR] Model call failed ({model_id}): {e}")
            return {"error": str(e)}

    async def _call_groq(self, model: ModelInfo, messages: List[dict], **kwargs) -> dict:
        """Call Groq API."""
        import httpx

        api_key = os.environ.get("GROQ_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model.extra_params.get("model", "llama3-70b-8192"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 8192),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "text": data["choices"][0]["message"]["content"],
                    "model": model.id,
                    "provider": "groq",
                    "usage": data.get("usage", {}),
                }
            return {"error": f"Groq API error: {resp.status_code}"}

    async def _call_openai(self, model: ModelInfo, messages: List[dict], **kwargs) -> dict:
        """Call OpenAI API."""
        import httpx

        api_key = os.environ.get("OPENAI_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model.extra_params.get("model", "gpt-4"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "text": data["choices"][0]["message"]["content"],
                    "model": model.id,
                    "provider": "openai",
                    "usage": data.get("usage", {}),
                }
            return {"error": f"OpenAI API error: {resp.status_code}"}

    async def _call_openai_compatible(self, model: ModelInfo, messages: List[dict], **kwargs) -> dict:
        """Call any OpenAI-compatible API."""
        import httpx

        api_key = os.environ.get(model.api_key_env, "")
        base_url = model.base_url
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model.extra_params.get("model", ""),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "text": data["choices"][0]["message"]["content"],
                    "model": model.id,
                    "provider": model.provider,
                    "usage": data.get("usage", {}),
                }
            return {"error": f"API error: {resp.status_code}"}

    async def _call_anthropic(self, model: ModelInfo, messages: List[dict], **kwargs) -> dict:
        """Call Anthropic API."""
        import httpx

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Separate system message
        system_msg = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                filtered_messages.append(msg)

        payload = {
            "model": model.extra_params.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": filtered_messages,
        }
        if system_msg:
            payload["system"] = system_msg

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        text += block["text"]
                return {
                    "text": text,
                    "model": model.id,
                    "provider": "anthropic",
                    "usage": data.get("usage", {}),
                }
            return {"error": f"Anthropic API error: {resp.status_code}"}

    def get_available_models(self) -> List[dict]:
        """Get list of available models with their capabilities."""
        return [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "capabilities": [c.value for c in m.capabilities],
                "available": m.available,
                "cost_per_1k": m.cost_per_1k_tokens,
                "latency_ms": m.latency_ms,
            }
            for m in self._models.values()
        ]

    def get_model_info(self, model_id: str) -> Optional[dict]:
        """Get detailed info about a specific model."""
        model = self._models.get(model_id)
        if not model:
            return None
        return {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "capabilities": [c.value for c in model.capabilities],
            "max_tokens": model.max_tokens,
            "cost_per_1k": model.cost_per_1k_tokens,
            "latency_ms": model.latency_ms,
            "available": model.available,
            "base_url": model.base_url,
        }


# Global instance
_orchestrator = None


def get_orchestrator() -> ModelOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ModelOrchestrator()
    return _orchestrator
