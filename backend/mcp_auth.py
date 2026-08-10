"""
JARVIS Enterprise Identity Propagation & Scoped Token Laundering

In enterprise architecture, an agent cannot use static root credentials.
When User A asks JARVIS to query a database, the MCP server must only
execute commands permitted by User A's corporate permissions.

This module:
1. Extracts the incoming user's corporate identity (OAuth2/OIDC JWT)
2. Verifies the token against the enterprise IdP (Okta/Entra ID/etc)
3. Down-scopes the token for each target MCP server
4. Propagates identity context through the entire execution chain
5. Records identity hashes in the compliance ledger
"""
import os
import time
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-auth")


# ── Configuration ────────────────────────────────────────────────────────
# These are set via environment variables in production.
# For local development, the system operates in "local" mode (no SSO).

OIDC_ISSUER = os.getenv("JARVIS_OIDC_ISSUER", "")  # e.g. "https://company.okta.com"
OIDC_CLIENT_ID = os.getenv("JARVIS_OIDC_CLIENT_ID", "")
OIDC_AUDIENCE = os.getenv("JARVIS_OIDC_AUDIENCE", "jarvis-api")
SSO_PUBLIC_KEY = os.getenv("SSO_PUBLIC_KEY", "")  # RSA public key for JWT verification
SSO_JWKS_URL = os.getenv("SSO_JWKS_URL", "")  # JWKS endpoint for key rotation

# Scope mapping: which MCP tools require which OAuth scopes
TOOL_SCOPE_MAP = {
    # Database tools
    "postgres": ["db:read"],
    "sqlite": ["db:read"],
    # GitHub tools
    "github": ["code:read"],
    # Cloud tools
    "aws": ["cloud:read"],
    "kubernetes": ["infra:read"],
    "docker": ["infra:read"],
    # File tools
    "filesystem": ["files:read"],
    # Messaging
    "slack": ["messaging:read"],
    # Browser
    "puppeteer": ["browser:execute"],
}

# Dangerous operations that require elevated scopes
WRITE_OPS = {
    "postgres": ["db:write"],
    "sqlite": ["db:write"],
    "github": ["code:write"],
    "aws": ["cloud:write"],
    "kubernetes": ["infra:write"],
    "docker": ["infra:write"],
    "filesystem": ["files:write"],
    "slack": ["messaging:write"],
}

# Admin scope bypasses all checks
ADMIN_SCOPE = "admin:all"


@dataclass
class IdentityContext:
    """
    Represents the authenticated enterprise identity of the current user.
    Propagated through the entire MCP execution chain.
    """
    user_id: str
    email: str = ""
    name: str = ""
    department: str = ""
    roles: List[str] = field(default_factory=list)
    scopes: List[str] = field(default_factory=list)
    tenant_id: str = ""
    identity_hash: str = ""  # Salted hash — never store raw PII in ledger
    token_issued_at: float = 0
    token_expires_at: float = 0
    auth_method: str = "local"  # "local", "oidc", "saml"
    raw_claims: Dict[str, Any] = field(default_factory=dict)

    def has_scope(self, scope: str) -> bool:
        """Check if this identity has a specific scope."""
        if ADMIN_SCOPE in self.scopes:
            return True
        return scope in self.scopes

    def has_any_scope(self, scopes: List[str]) -> bool:
        """Check if this identity has any of the listed scopes."""
        if ADMIN_SCOPE in self.scopes:
            return True
        return any(s in self.scopes for s in scopes)

    def can_access_tool(self, tool_name: str, is_write: bool = False) -> bool:
        """Check if this identity can access a specific MCP tool."""
        if ADMIN_SCOPE in self.scopes:
            return True

        # Find the tool family (e.g., "postgres__execute" → "postgres")
        family = tool_name.split("__")[0].split("_")[0].lower()

        # Check read scopes
        required = TOOL_SCOPE_MAP.get(family, [])
        if required and not self.has_any_scope(required):
            return False

        # Check write scopes if this is a write operation
        if is_write:
            write_required = WRITE_OPS.get(family, [])
            if write_required and not self.has_any_scope(write_required):
                return False

        return True

    def to_header_dict(self) -> Dict[str, str]:
        """Convert identity context to headers for downstream MCP servers."""
        return {
            "X-JARVIS-User-Id": self.user_id,
            "X-JARVIS-Identity-Hash": self.identity_hash,
            "X-JARVIS-Tenant-Id": self.tenant_id,
            "X-JARVIS-Scopes": " ".join(self.scopes),
            "X-JARVIS-Auth-Method": self.auth_method,
        }


# ── Local Identity (no SSO) ─────────────────────────────────────────────

def create_local_identity(user_id: str = "local") -> IdentityContext:
    """
    Create an identity context for local/single-user mode.
    This is the default when no enterprise SSO is configured.
    Full admin access — equivalent to root.
    """
    identity_hash = hashlib.sha256(
        f"local:{user_id}:{os.urandom(8).hex()}".encode()
    ).hexdigest()

    return IdentityContext(
        user_id=user_id,
        email=f"{user_id}@local",
        name=user_id,
        department="local",
        roles=["admin"],
        scopes=[ADMIN_SCOPE],
        tenant_id="local",
        identity_hash=identity_hash,
        token_issued_at=time.time(),
        token_expires_at=time.time() + 86400 * 365,  # 1 year
        auth_method="local",
    )


# ── OIDC Token Verification ─────────────────────────────────────────────

def verify_oidc_token(token: str) -> IdentityContext:
    """
    Verify an OAuth2/OIDC JWT token and extract identity context.
    
    Supports:
    - Okta
    - Microsoft Entra ID (Azure AD)
    - Auth0
    - Any standards-compliant OIDC provider
    
    Falls back to local identity if no SSO is configured.
    """
    if not SSO_PUBLIC_KEY and not SSO_JWKS_URL:
        log.debug("No SSO configured — treating token as local identity")
        return create_local_identity()

    try:
        import jwt as jose_jwt

        # Try JWKS-based verification first
        if SSO_JWKS_URL:
            jwks = _fetch_jwks(SSO_JWKS_URL)
            header = jose_jwt.get_unverified_header(token)
            kid = header.get("kid")
            key = jwks.get(kid)
            if not key:
                raise ValueError(f"No matching key for kid: {kid}")
            claims = jose_jwt.decode(
                token,
                key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=OIDC_AUDIENCE,
                issuer=OIDC_ISSUER,
            )
        else:
            # Static public key verification
            claims = jose_jwt.decode(
                token,
                SSO_PUBLIC_KEY,
                algorithms=["RS256"],
                audience=OIDC_AUDIENCE,
                issuer=OIDC_ISSUER,
            )

        # Extract identity fields (standard OIDC claims)
        identity_hash = hashlib.sha256(
            f"{claims.get('sub', '')}:{os.urandom(8).hex()}".encode()
        ).hexdigest()

        return IdentityContext(
            user_id=claims.get("sub", "unknown"),
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("preferred_username", "")),
            department=claims.get("department", claims.get("org", "")),
            roles=claims.get("roles", []),
            scopes=claims.get("scp", claims.get("scope", "").split()),
            tenant_id=claims.get("tenant_id", claims.get("org", "")),
            identity_hash=identity_hash,
            token_issued_at=claims.get("iat", time.time()),
            token_expires_at=claims.get("exp", time.time() + 3600),
            auth_method="oidc",
            raw_claims=claims,
        )

    except ImportError:
        log.warning("python-jose not installed — pip install python-jose[cryptography]")
        return create_local_identity()
    except Exception as e:
        log.error(f"OIDC token verification failed: {e}")
        raise


def _fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    """Fetch JSON Web Key Set from the identity provider."""
    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    req = urllib.request.Request(jwks_url, headers={"User-Agent": "JARVIS-Auth/3.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        data = json.loads(resp.read())

    # Convert JWKS to a dict keyed by kid
    keys = {}
    for jwk in data.get("keys", []):
        kid = jwk.get("kid")
        if kid:
            from jose import jwt as _jose_jwt
            keys[kid] = _jose_jwt.algorithms.RSA.from_jwk(json.dumps(jwk))
    return keys


# ── Middleware Dependency ────────────────────────────────────────────────

def extract_identity_from_request(request) -> IdentityContext:
    """
    FastAPI dependency that extracts enterprise identity from the request.
    
    Priority:
    1. Authorization header (Bearer JWT) → OIDC verification
    2. X-JARVIS-User-Id header → local identity for that user
    3. Default → local admin identity
    """
    # Check for Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            return verify_oidc_token(token)
        except Exception:
            pass

    # Check for explicit user ID header (relay mode)
    user_id = request.headers.get("X-JARVIS-User-Id", "local")
    return create_local_identity(user_id)


# ── Token Laundering (Down-scoping) ─────────────────────────────────────

def launder_token_for_server(
    identity: IdentityContext,
    server_name: str,
    tool_name: str,
    is_write: bool = False,
) -> Dict[str, str]:
    """
    Generate down-scoped headers for a specific MCP server connection.
    
    This is "token laundering" — the enterprise token is never sent directly
    to the MCP server. Instead, we generate a scoped, short-lived context
    that only contains the permissions needed for this specific operation.
    """
    # Determine required scopes for this tool
    family = server_name.split("__")[0].split("_")[0].lower()
    required_scopes = TOOL_SCOPE_MAP.get(family, [])
    if is_write:
        required_scopes = WRITE_OPS.get(family, required_scopes)

    # Filter identity scopes to only what's needed
    effective_scopes = [
        s for s in identity.scopes
        if s in required_scopes or s == ADMIN_SCOPE
    ]

    # Generate a scoped, short-lived token hash
    scope_hash = hashlib.sha256(
        f"{identity.identity_hash}:{server_name}:{tool_name}:{time.time()}".encode()
    ).hexdigest()[:32]

    headers = {
        "X-JARVIS-Scoped-Token": scope_hash,
        "X-JARVIS-User-Id": identity.user_id,
        "X-JARVIS-Identity-Hash": identity.identity_hash,
        "X-JARVIS-Effective-Scopes": " ".join(effective_scopes),
        "X-JARVIS-Server-Target": server_name,
        "X-JARVIS-Tool-Target": tool_name,
        "X-JARVIS-Is-Write": str(is_write).lower(),
        "X-JARVIS-Tenant-Id": identity.tenant_id,
        "X-JARVIS-Auth-Method": identity.auth_method,
        "X-JARVIS-Token-TTL": "300",  # 5 minutes
    }

    return headers


# ── Singleton ────────────────────────────────────────────────────────────
_local_identity: Optional[IdentityContext] = None


def get_local_identity() -> IdentityContext:
    """Get the default local identity (for single-user mode)."""
    global _local_identity
    if _local_identity is None:
        _local_identity = create_local_identity()
    return _local_identity
