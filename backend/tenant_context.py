"""
JARVIS Multi-Tenant Identity Context

Isolates users based on Organization, Team, and Seat profile.
Data never bleeds between tenants. Each organization gets its own
isolated database, memory graph, and agent execution sandbox.

Hierarchy:
  Organization → Teams → Seats → Agents → Actions

Every action carries full tenant context through the execution chain.
"""
import os
import json
import time
import hashlib
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("jarvis-tenant")


# ── Organization Tiers ──────────────────────────────────────────────────
class OrgTier(str):
    FREE = "free"
    PRO = "pro"
    GROUP = "group"
    ENTERPRISE = "enterprise"
    SOVEREIGN = "sovereign"


TIER_LIMITS = {
    OrgTier.FREE: {
        "max_seats": 1,
        "max_nodes": 1,
        "max_daily_transactions": 100,
        "max_storage_mb": 50,
        "agent_domains": ["CORE_AGENT"],
        "mcp_servers": ["filesystem", "fetch"],
        "compliance_retention_days": 7,
    },
    OrgTier.PRO: {
        "max_seats": 1,
        "max_nodes": 3,
        "max_daily_transactions": 1000,
        "max_storage_mb": 500,
        "agent_domains": ["CORE_AGENT", "OS_AGENT", "HAL_AGENT"],
        "mcp_servers": ["filesystem", "fetch", "github", "postgres", "sqlite"],
        "compliance_retention_days": 30,
    },
    OrgTier.GROUP: {
        "max_seats": 25,
        "max_nodes": 10,
        "max_daily_transactions": 10000,
        "max_storage_mb": 5000,
        "agent_domains": ["CORE_AGENT", "OS_AGENT", "HAL_AGENT", "WEB_AGENT"],
        "mcp_servers": ["*"],  # All servers
        "compliance_retention_days": 90,
    },
    OrgTier.ENTERPRISE: {
        "max_seats": 500,
        "max_nodes": 100,
        "max_daily_transactions": 100000,
        "max_storage_mb": 50000,
        "agent_domains": ["CORE_AGENT", "OS_AGENT", "HAL_AGENT", "WEB_AGENT", "INFRA_AGENT"],
        "mcp_servers": ["*"],
        "compliance_retention_days": 365,
    },
    OrgTier.SOVEREIGN: {
        "max_seats": -1,  # Unlimited
        "max_nodes": -1,
        "max_daily_transactions": -1,
        "max_storage_mb": -1,
        "agent_domains": ["*"],
        "mcp_servers": ["*"],
        "compliance_retention_days": -1,  # Permanent
    },
}


# ── Role Definitions ────────────────────────────────────────────────────
class Role:
    GLOBAL_ADMIN = "GLOBAL_ADMIN"
    ORG_ADMIN = "ORG_ADMIN"
    TEAM_LEAD = "TEAM_LEAD"
    SYSTEM_ENGINEER = "SYSTEM_ENGINEER"
    DEVOPS = "DEVOPS"
    STANDARD_USER = "STANDARD_USER"
    VIEWER = "VIEWER"
    GUEST = "GUEST"


ROLE_HIERARCHY = {
    Role.GLOBAL_ADMIN: 100,
    Role.ORG_ADMIN: 90,
    Role.TEAM_LEAD: 70,
    Role.SYSTEM_ENGINEER: 60,
    Role.DEVOPS: 55,
    Role.STANDARD_USER: 40,
    Role.VIEWER: 20,
    Role.GUEST: 10,
}

# Default scopes per role
ROLE_SCOPES = {
    Role.GLOBAL_ADMIN: ["*"],  # All permissions
    Role.ORG_ADMIN: [
        "org:manage", "seats:manage", "nodes:manage", "billing:manage",
        "agent:execute:*", "mcp:use:*", "files:read", "files:write",
        "db:read", "db:write", "cloud:read", "cloud:write",
        "infra:read", "infra:write", "compliance:read",
    ],
    Role.TEAM_LEAD: [
        "team:manage", "seats:invite",
        "agent:execute:core", "agent:execute:os", "agent:execute:web",
        "mcp:use:filesystem", "mcp:use:fetch", "mcp:use:github",
        "files:read", "files:write", "db:read", "compliance:read",
    ],
    Role.SYSTEM_ENGINEER: [
        "agent:execute:*", "mcp:use:*",
        "files:read", "files:write", "db:read", "db:write",
        "cloud:read", "cloud:write", "infra:read", "infra:write",
    ],
    Role.DEVOPS: [
        "agent:execute:core", "agent:execute:os", "agent:execute:infra",
        "mcp:use:*", "files:read", "files:write",
        "db:read", "db:write", "infra:read", "infra:write",
    ],
    Role.STANDARD_USER: [
        "agent:execute:core", "agent:execute:web",
        "mcp:use:filesystem", "mcp:use:fetch",
        "files:read", "db:read",
    ],
    Role.VIEWER: [
        "agent:execute:core",
        "files:read", "db:read", "compliance:read",
    ],
    Role.GUEST: [
        "files:read",
    ],
}


@dataclass
class TenantSessionContext:
    """
    The complete multi-tenant identity context.
    Carried through every API call, MCP invocation, and compliance record.
    """
    # Organization
    org_id: str
    org_name: str = ""
    org_tier: str = OrgTier.FREE
    org_created_at: float = 0

    # User / Seat
    user_id: str = ""
    seat_id: str = ""
    display_name: str = ""
    email: str = ""
    role: str = Role.GUEST
    scopes: List[str] = field(default_factory=list)

    # Team
    team_id: str = ""
    team_name: str = ""

    # Node (which worker node this request routes to)
    node_id: str = ""

    # Identity verification
    auth_method: str = "local"  # "local", "oidc", "api_key"
    identity_hash: str = ""
    token_issued_at: float = 0
    token_expires_at: float = 0

    # Tier limits
    tier_limits: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tier_limits:
            self.tier_limits = TIER_LIMITS.get(self.org_tier, TIER_LIMITS[OrgTier.FREE])
        if not self.identity_hash:
            self.identity_hash = hashlib.sha256(
                f"{self.org_id}:{self.user_id}:{os.urandom(8).hex()}".encode()
            ).hexdigest()

    def has_scope(self, scope: str) -> bool:
        """Check if this identity has a specific scope."""
        if "*" in self.scopes:
            return True
        if scope in self.scopes:
            return True
        # Check wildcard patterns
        parts = scope.split(":")
        for i in range(len(parts)):
            wildcard = ":".join(parts[:i] + ["*"])
            if wildcard in self.scopes:
                return True
        return False

    def has_any_scope(self, scopes: List[str]) -> bool:
        return any(self.has_scope(s) for s in scopes)

    def can_use_agent_domain(self, domain: str) -> bool:
        """Check if this org tier allows this agent domain."""
        allowed = self.tier_limits.get("agent_domains", [])
        if "*" in allowed:
            return True
        return domain in allowed

    def can_use_mcp_server(self, server_name: str) -> bool:
        """Check if this org tier allows this MCP server."""
        allowed = self.tier_limits.get("mcp_servers", [])
        if "*" in allowed:
            return True
        return server_name in allowed

    def get_db_path(self) -> str:
        """Get the isolated database path for this organization."""
        base = os.path.join(os.path.expanduser("~"), ".jarvis", "tenants")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, f"org_{self.org_id}.db")

    def get_isolated_db(self) -> sqlite3.Connection:
        """Get a dedicated, isolated SQLite connection for this organization."""
        db_path = self.get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def get_storage_path(self) -> str:
        """Get the isolated storage path for this organization."""
        base = os.path.join(os.path.expanduser("~"), ".jarvis", "tenants", self.org_id, "storage")
        os.makedirs(base, exist_ok=True)
        return base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org_id": self.org_id,
            "org_name": self.org_name,
            "org_tier": self.org_tier,
            "user_id": self.user_id,
            "seat_id": self.seat_id,
            "display_name": self.display_name,
            "email": self.email,
            "role": self.role,
            "scopes": self.scopes,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "node_id": self.node_id,
            "auth_method": self.auth_method,
            "identity_hash": self.identity_hash[:16] + "...",
            "tier_limits": self.tier_limits,
        }

    def to_header_dict(self) -> Dict[str, str]:
        """Headers for downstream services."""
        return {
            "X-JARVIS-Org-Id": self.org_id,
            "X-JARVIS-User-Id": self.user_id,
            "X-JARVIS-Seat-Id": self.seat_id,
            "X-JARVIS-Role": self.role,
            "X-JARVIS-Scopes": " ".join(self.scopes),
            "X-JARVIS-Team-Id": self.team_id,
            "X-JARVIS-Node-Id": self.node_id,
            "X-JARVIS-Identity-Hash": self.identity_hash,
            "X-JARVIS-Tier": self.org_tier,
            "X-JARVIS-Auth-Method": self.auth_method,
        }


# ── Local / Single-User Fallback ────────────────────────────────────────

def create_local_context(user_id: str = "local") -> TenantSessionContext:
    """
    Create a local/solo context for single-user mode.
    Full admin access — equivalent to GLOBAL_ADMIN on an unlimited SOVEREIGN tier.
    """
    return TenantSessionContext(
        org_id="local",
        org_name="Local Workspace",
        org_tier=OrgTier.SOVEREIGN,
        user_id=user_id,
        seat_id=f"{user_id}_seat_0",
        display_name=user_id,
        email=f"{user_id}@local",
        role=Role.GLOBAL_ADMIN,
        scopes=["*"],
        team_id="default",
        team_name="Default",
        node_id="local_node",
        auth_method="local",
        tier_limits=TIER_LIMITS[OrgTier.SOVEREIGN],
    )


# ── JWT Token Resolution ────────────────────────────────────────────────

def resolve_from_jwt(token: str, secret: str = None) -> TenantSessionContext:
    """
    Resolve a multi-tenant context from a JWT token.
    
    Expected JWT claims:
    {
      "sub": "user_123",
      "org_id": "org_abc",
      "org_name": "Acme Corp",
      "org_tier": "enterprise",
      "role": "ORG_ADMIN",
      "scopes": ["agent:execute:*", "db:read"],
      "team_id": "team_marketing",
      "team_name": "Marketing",
      "seat_id": "seat_42",
      "email": "john@acme.com",
      "name": "John Smith",
      "node_id": "node_01",
      "iat": 1700000000,
      "exp": 1700003600
    }
    """
    secret = secret or os.getenv("JARVIS_JWT_SECRET", "jarvis-local-dev-secret")
    try:
        import jwt as jose_jwt
        claims = jose_jwt.decode(token, secret, algorithms=["HS256", "RS256"])

        org_tier = claims.get("org_tier", OrgTier.FREE)
        tier_limits = TIER_LIMITS.get(org_tier, TIER_LIMITS[OrgTier.FREE])

        return TenantSessionContext(
            org_id=claims.get("org_id", "unknown"),
            org_name=claims.get("org_name", ""),
            org_tier=org_tier,
            user_id=claims.get("sub", "unknown"),
            seat_id=claims.get("seat_id", ""),
            display_name=claims.get("name", claims.get("preferred_username", "")),
            email=claims.get("email", ""),
            role=claims.get("role", Role.GUEST),
            scopes=claims.get("scopes", []),
            team_id=claims.get("team_id", ""),
            team_name=claims.get("team_name", ""),
            node_id=claims.get("node_id", ""),
            auth_method="oidc",
            token_issued_at=claims.get("iat", time.time()),
            token_expires_at=claims.get("exp", time.time() + 3600),
            tier_limits=tier_limits,
        )
    except ImportError:
        log.warning("python-jose not installed — falling back to local context")
        return create_local_context()
    except Exception as e:
        log.error(f"JWT resolution failed: {e}")
        raise


# ── Request-based Resolution ────────────────────────────────────────────

def resolve_from_request(request) -> TenantSessionContext:
    """
    Resolve tenant context from an incoming HTTP request.
    
    Priority:
    1. Authorization: Bearer <JWT> header
    2. X-JARVIS-Org-Id + X-JARVIS-User-Id headers (relay mode)
    3. Default local context
    """
    # Try JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            return resolve_from_jwt(token)
        except Exception:
            pass

    # Try explicit headers (relay mode)
    org_id = request.headers.get("X-JARVIS-Org-Id", "")
    user_id = request.headers.get("X-JARVIS-User-Id", "local")
    if org_id:
        return TenantSessionContext(
            org_id=org_id,
            user_id=user_id,
            role=Role.STANDARD_USER,
            scopes=ROLE_SCOPES[Role.STANDARD_USER],
            auth_method="header",
        )

    # Default local
    return create_local_context(user_id)


# ── Database Initialization ─────────────────────────────────────────────

def init_tenant_db(conn: sqlite3.Connection):
    """Initialize the tenant database schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seats (
            seat_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'STANDARD_USER',
            scopes TEXT DEFAULT '[]',
            team_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at REAL,
            last_active_at REAL
        );

        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            description TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS nodes (
            node_id TEXT PRIMARY KEY,
            node_type TEXT DEFAULT 'worker',
            status TEXT DEFAULT 'standby',
            assigned_seat_id TEXT,
            platform TEXT,
            ip_address TEXT,
            last_heartbeat REAL,
            capabilities TEXT DEFAULT '[]',
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id TEXT PRIMARY KEY,
            seat_id TEXT,
            agent_domain TEXT,
            action_type TEXT,
            tool_name TEXT,
            status TEXT DEFAULT 'pending',
            result_summary TEXT,
            started_at REAL,
            completed_at REAL,
            duration_ms REAL,
            is_error INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS billing_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,
            seat_id TEXT,
            node_id TEXT,
            transaction_count INTEGER DEFAULT 0,
            storage_bytes INTEGER DEFAULT 0,
            timestamp REAL
        );

        CREATE INDEX IF NOT EXISTS idx_seats_user ON seats(user_id);
        CREATE INDEX IF NOT EXISTS idx_seats_team ON seats(team_id);
        CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
        CREATE INDEX IF NOT EXISTS idx_runs_seat ON agent_runs(seat_id);
        CREATE INDEX IF NOT EXISTS idx_runs_domain ON agent_runs(agent_domain);
    """)
    conn.commit()
