"""
JARVIS Configuration
====================
Centralized configuration with environment variable support.
All hardcoded values should be moved here.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JARVISConfig:
    """Central configuration for all JARVIS services."""

    # ── Deployment ──────────────────────────────────────────────
    DEPLOYMENT_URL: str = os.getenv(
        "JARVIS_DEPLOYMENT_URL",
        "https://dgfhgjhj-jarvis-ai-brain.hf.space",
    )
    FRONTEND_DIR: str = os.getenv("JARVIS_FRONTEND_DIR", "")
    DEBUG: bool = os.getenv("JARVIS_DEBUG", "").lower() == "true"

    # ── LLM ─────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("JARVIS_LLM_MODEL", "llama-3.3-70b-versatile")
    LLM_FAST_MODEL: str = os.getenv("JARVIS_LLM_FAST_MODEL", "llama-3.1-8b-instant")

    # ── LiveKit ─────────────────────────────────────────────────
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")

    # ── Auth ────────────────────────────────────────────────────
    REQUIRE_AUTH: bool = os.getenv("JARVIS_REQUIRE_AUTH", "false").lower() == "true"
    JWT_SECRET: str = os.getenv("JARVIS_JWT_SECRET", "")
    JWT_EXPIRY_HOURS: int = int(os.getenv("JARVIS_JWT_EXPIRY_HOURS", "72"))
    ADMIN_USER: str = os.getenv("JARVIS_ADMIN_USER", "admin")
    ADMIN_PASS: str = os.getenv("JARVIS_ADMIN_PASS", "")

    # ── Rate Limiting ───────────────────────────────────────────
    RATE_LIMIT_RPS: float = float(os.getenv("JARVIS_RATE_LIMIT_RPS", "10"))
    RATE_LIMIT_BURST: int = int(os.getenv("JARVIS_RATE_LIMIT_BURST", "20"))
    STRICT_RATE_LIMIT_RPS: float = float(os.getenv("JARVIS_STRICT_RATE_LIMIT_RPS", "2"))
    STRICT_RATE_LIMIT_BURST: int = int(os.getenv("JARVIS_STRICT_RATE_LIMIT_BURST", "5"))

    # ── CORS ────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = field(default_factory=lambda: [
        o.strip() for o in os.getenv("JARVIS_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ])

    # ── Smart Home ──────────────────────────────────────────────
    TAPO_USERNAME: str = os.getenv("TAPO_USERNAME", "")
    TAPO_PASSWORD: str = os.getenv("TAPO_PASSWORD", "")
    HOME_ASSISTANT_URL: str = os.getenv("HOME_ASSISTANT_URL", "")
    HOME_ASSISTANT_TOKEN: str = os.getenv("HOME_ASSISTANT_TOKEN", "")

    # ── External APIs ───────────────────────────────────────────
    AMADEUS_API_KEY: str = os.getenv("AMADEUS_API_KEY", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    SKYSCANNER_API_KEY: str = os.getenv("SKYSCANNER_API_KEY", "")
    NAMECHEAP_API_USER: str = os.getenv("NAMECHEAP_API_USER", "")

    # ── Security ────────────────────────────────────────────────
    ALLOWED_DOMAINS: list = field(default_factory=lambda: [
        d.strip() for d in os.getenv(
            "JARVIS_ALLOWED_DOMAINS",
            "localhost,127.0.0.1,huggingface.co,github.com,groq.com,google.com"
        ).split(",") if d.strip()
    ])

    def is_cloud(self) -> bool:
        """Detect if running on cloud (HF Space)."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip.startswith("10.") or local_ip.startswith("172.") or local_ip.startswith("169.")
        except Exception:
            return True

    def get_deployment_url(self) -> str:
        """Get the deployment URL for relay instructions."""
        return self.DEPLOYMENT_URL


# Global config instance
_config: Optional[JARVISConfig] = None


def get_config() -> JARVISConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = JARVISConfig()
    return _config
