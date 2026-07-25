"""
JARVIS Authentication & Authorization Middleware
================================================
JWT-based auth with API key fallback for machine-to-machine communication.
"""

import os
import time
import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JARVIS_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JARVIS_JWT_EXPIRY_HOURS", "72"))

# API keys stored in env: JARVIS_API_KEY_<NAME>=<key>
# Users can have multiple API keys for different devices/services
API_KEYS_ENV_PREFIX = "JARVIS_API_KEY_"

security = HTTPBearer(auto_error=False)


def _get_api_keys() -> dict[str, str]:
    """Collect all API keys from environment variables."""
    keys = {}
    for key, value in os.environ.items():
        if key.startswith(API_KEYS_ENV_PREFIX) and value:
            label = key[len(API_KEYS_ENV_PREFIX):].lower()
            keys[value] = label
    return keys


def _hash_api_key(key: str) -> str:
    """Hash an API key for safe comparison."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def create_jwt_token(user_id: str, scopes: list[str] | None = None,
                     tenant_id: str = "default") -> str:
    """Create a signed JWT token."""
    if not JWT_AVAILABLE:
        raise RuntimeError("PyJWT not installed. Run: pip install PyJWT")

    payload = {
        "sub": user_id,
        "scopes": scopes or ["read", "write"],
        "tenant_id": tenant_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    if not JWT_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT not available")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


class AuthContext:
    """Holds authenticated user context for the request."""
    def __init__(self, user_id: str, auth_method: str,
                 scopes: list[str] | None = None, tenant_id: str = "default"):
        self.user_id = user_id
        self.auth_method = auth_method
        self.scopes = scopes or ["read", "write"]
        self.tenant_id = tenant_id

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.scopes

    def can_access(self, resource_user_id: str) -> bool:
        """Check if this auth context can access a resource."""
        return self.user_id == resource_user_id or "admin" in self.scopes


def _extract_token_from_request(request: Request) -> Optional[str]:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def _extract_api_key_from_request(request: Request) -> Optional[str]:
    """Extract API key from X-API-Key header or query param."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key
    # Fallback to query parameter (for relay agents)
    return request.query_params.get("api_key")


async def authenticate(request: Request) -> AuthContext:
    """
    Main authentication dependency.
    Tries: JWT -> API Key -> anonymous (for local dev).
    """
    # 1. Try JWT token
    token = _extract_token_from_request(request)
    if token:
        payload = decode_jwt_token(token)
        return AuthContext(
            user_id=payload.get("sub", "unknown"),
            auth_method="jwt",
            scopes=payload.get("scopes", []),
            tenant_id=payload.get("tenant_id", "default"),
        )

    # 2. Try API key
    api_key = _extract_api_key_from_request(request)
    if api_key:
        api_keys = _get_api_keys()
        if api_key in api_keys:
            return AuthContext(
                user_id=api_keys[api_key],
                auth_method="api_key",
                scopes=["read", "write"],
            )
        # Also try env var JARVIS_API_KEY (single key)
        master_key = os.getenv("JARVIS_API_KEY")
        if master_key and api_key == master_key:
            return AuthContext(
                user_id="admin",
                auth_method="api_key",
                scopes=["read", "write", "admin"],
            )
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 3. Check if auth is required
    require_auth = os.getenv("JARVIS_REQUIRE_AUTH", "false").lower() == "true"
    if require_auth:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide JWT or API key.",
        )

    # 4. Anonymous (dev mode) — default to local user
    return AuthContext(
        user_id="local",
        auth_method="anonymous",
        scopes=["read", "write"],
    )


async def require_admin(auth: AuthContext = Depends(authenticate)) -> AuthContext:
    """Dependency that requires admin scope."""
    if not auth.has_scope("admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return auth


async def require_write(auth: AuthContext = Depends(authenticate)) -> AuthContext:
    """Dependency that requires write scope."""
    if not auth.has_scope("write"):
        raise HTTPException(status_code=403, detail="Write access required")
    return auth


# Token refresh endpoint helper
def refresh_token(old_token: str) -> str:
    """Refresh a token that's about to expire."""
    payload = decode_jwt_token(old_token)
    return create_jwt_token(
        user_id=payload["sub"],
        scopes=payload.get("scopes"),
        tenant_id=payload.get("tenant_id", "default"),
    )
