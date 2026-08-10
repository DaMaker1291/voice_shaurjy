"""
JARVIS Rate Limiter Middleware
==============================
Token bucket rate limiting with per-user tracking.
Prevents abuse and ensures fair resource usage.
"""

import time
import os
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass, field
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    @property
    def retry_after(self) -> float:
        """Seconds until next token is available."""
        if self.tokens >= 1:
            return 0.0
        return max(0, (1 - self.tokens) / self.refill_rate)


class RateLimiter:
    """Per-user rate limiter with configurable limits."""
    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._default_rate = float(os.getenv("JARVIS_RATE_LIMIT_RPS", "10"))
        self._default_capacity = int(os.getenv("JARVIS_RATE_LIMIT_BURST", "20"))
        # Stricter limits for expensive endpoints
        self._strict_rate = float(os.getenv("JARVIS_STRICT_RATE_LIMIT_RPS", "2"))
        self._strict_capacity = int(os.getenv("JARVIS_STRICT_RATE_LIMIT_BURST", "5"))
        self._strict_paths = {
            "/api/router/dispatch",
            "/api/entity/process",
            "/api/computer/run",
            "/api/task/stream",
            "/api/agent/autonomous",
        }

    def _get_or_create_bucket(self, key: str, rate: float, capacity: int) -> TokenBucket:
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(capacity=capacity, refill_rate=rate)
        return self._buckets[key]

    def check(self, user_id: str, path: str) -> tuple[bool, float]:
        """Check rate limit. Returns (allowed, retry_after_seconds)."""
        is_strict = path in self._strict_paths
        rate = self._strict_rate if is_strict else self._default_rate
        capacity = self._strict_capacity if is_strict else self._default_capacity
        bucket_key = f"{user_id}:{'strict' if is_strict else 'normal'}"
        bucket = self._get_or_create_bucket(bucket_key, rate, capacity)
        allowed = bucket.consume()
        return allowed, bucket.retry_after if not allowed else 0.0

    def cleanup(self, max_age: float = 3600):
        """Remove stale buckets to prevent memory leaks."""
        now = time.time()
        stale = [k for k, v in self._buckets.items()
                 if now - v.last_refill > max_age]
        for k in stale:
            del self._buckets[k]

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "active_buckets": len(self._buckets),
            "default_rps": self._default_rate,
            "default_burst": self._default_capacity,
            "strict_rps": self._strict_rate,
            "strict_burst": self._strict_capacity,
            "strict_paths": list(self._strict_paths),
        }


_rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces rate limits on all API routes."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for non-API routes and health checks
        path = request.url.path
        # WebSocket upgrade requests must not be intercepted by BaseHTTPMiddleware
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        if not path.startswith("/api/") or path in ("/api/health", "/health"):
            return await call_next(request)

        # Extract user identity from request
        user_id = request.headers.get("x-user-id", "anonymous")
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            user_id = f"apikey:{api_key[:8]}"

        allowed, retry_after = _rate_limiter.check(user_id, path)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": round(retry_after, 2),
                    "user_id": user_id,
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(_rate_limiter._default_capacity),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        bucket_key = f"{user_id}:normal"
        if path in _rate_limiter._strict_paths:
            bucket_key = f"{user_id}:strict"
        bucket = _rate_limiter._buckets.get(bucket_key)
        if bucket:
            response.headers["X-RateLimit-Limit"] = str(bucket.capacity)
            response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))

        return response


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter
