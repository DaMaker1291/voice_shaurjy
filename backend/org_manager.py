"""
JARVIS Organization Manager

Manages the complete lifecycle of organizations, teams, seats, and nodes.
Handles tier enforcement, invitation flows, billing events, and seat provisioning.

Each organization gets isolated storage, isolated database, and isolated agent sandboxes.
"""
import os
import json
import time
import uuid
import sqlite3
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from tenant_context import (
    TenantSessionContext, OrgTier, TIER_LIMITS,
    Role, ROLE_HIERARCHY, ROLE_SCOPES,
    create_local_context, init_tenant_db,
)
from policy_engine import (
    PolicyEngine, PolicyRule, build_default_org_policies,
)

log = logging.getLogger("jarvis-org-manager")


@dataclass
class Organization:
    org_id: str
    name: str
    tier: str = OrgTier.FREE
    created_at: float = 0
    billing_email: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    total_transactions: int = 0
    storage_bytes: int = 0


@dataclass
class Seat:
    seat_id: str
    org_id: str
    user_id: str
    display_name: str = ""
    email: str = ""
    role: str = Role.STANDARD_USER
    scopes: List[str] = field(default_factory=list)
    team_id: str = ""
    is_active: bool = True
    created_at: float = 0
    last_active_at: float = 0


@dataclass
class Team:
    team_id: str
    org_id: str
    name: str
    description: str = ""
    created_at: float = 0
    member_seat_ids: List[str] = field(default_factory=list)


@dataclass
class OrgNode:
    node_id: str
    org_id: str
    node_type: str = "worker"
    status: str = "standby"
    assigned_seat_id: str = ""
    platform: str = ""
    ip_address: str = ""
    last_heartbeat: float = 0
    capabilities: List[str] = field(default_factory=list)
    created_at: float = 0


@dataclass
class Invitation:
    invite_id: str
    org_id: str
    email: str
    role: str
    team_id: str
    invited_by_seat_id: str
    created_at: float = 0
    expires_at: float = 0
    accepted: bool = False


class OrgManager:
    """
    Central manager for organization lifecycle.
    
    In production, backed by a persistent database.
    In single-user mode, all org operations are no-ops (local context only).
    """

    def __init__(self):
        self._orgs: Dict[str, Organization] = {}
        self._seats: Dict[str, Seat] = {}
        self._teams: Dict[str, Team] = {}
        self._nodes: Dict[str, OrgNode] = {}
        self._invitations: Dict[str, Invitation] = {}
        self._policy_engine = PolicyEngine()
        self._db_path = os.path.join(
            os.path.expanduser("~"), ".jarvis", "orgs.db"
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS organizations (
                org_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tier TEXT DEFAULT 'free',
                created_at REAL,
                billing_email TEXT,
                settings TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                total_transactions INTEGER DEFAULT 0,
                storage_bytes INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS seats (
                seat_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                display_name TEXT,
                email TEXT,
                role TEXT DEFAULT 'STANDARD_USER',
                scopes TEXT DEFAULT '[]',
                team_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at REAL,
                last_active_at REAL,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id)
            );
            CREATE TABLE IF NOT EXISTS teams (
                team_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                created_at REAL,
                member_seat_ids TEXT DEFAULT '[]',
                FOREIGN KEY (org_id) REFERENCES organizations(org_id)
            );
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                node_type TEXT DEFAULT 'worker',
                status TEXT DEFAULT 'standby',
                assigned_seat_id TEXT,
                platform TEXT,
                ip_address TEXT,
                last_heartbeat REAL,
                capabilities TEXT DEFAULT '[]',
                created_at REAL,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id)
            );
            CREATE TABLE IF NOT EXISTS invitations (
                invite_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT,
                team_id TEXT,
                invited_by_seat_id TEXT,
                created_at REAL,
                expires_at REAL,
                accepted INTEGER DEFAULT 0,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id)
            );
            CREATE TABLE IF NOT EXISTS policy_rules (
                rule_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                rule_json TEXT NOT NULL,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id)
            );
            CREATE INDEX IF NOT EXISTS idx_seats_org ON seats(org_id);
            CREATE INDEX IF NOT EXISTS idx_seats_user ON seats(user_id);
            CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_org ON nodes(org_id);
            CREATE INDEX IF NOT EXISTS idx_invites_org ON invitations(org_id);
        """)
        conn.commit()
        conn.close()

    # ── Organization CRUD ─────────────────────────────────────────────

    def create_organization(
        self, name: str, tier: str = OrgTier.FREE,
        billing_email: str = "", creator_user_id: str = "local"
    ) -> Tuple[Organization, TenantSessionContext]:
        """Create a new organization and return the creator's admin context."""
        org_id = f"org_{uuid.uuid4().hex[:12]}"
        now = time.time()

        org = Organization(
            org_id=org_id, name=name, tier=tier,
            created_at=now, billing_email=billing_email,
        )
        self._orgs[org_id] = org

        # Persist to DB
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO organizations VALUES (?,?,?,?,?,?,1,0,0)",
            (org_id, name, tier, now, billing_email, "{}"),
        )
        conn.commit()
        conn.close()

        # Create default team
        default_team_id = f"team_{uuid.uuid4().hex[:8]}"
        team = Team(
            team_id=default_team_id, org_id=org_id,
            name="General", created_at=now,
        )
        self._teams[default_team_id] = team
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO teams VALUES (?,?,?,?,'[]')",
            (default_team_id, org_id, "General", now),
        )
        conn.commit()
        conn.close()

        # Create founding seat as ORG_ADMIN
        seat_id = self._create_seat(
            org_id=org_id, user_id=creator_user_id,
            display_name=creator_user_id, role=Role.ORG_ADMIN,
            team_id=default_team_id,
        )

        # Load default policies
        rules = build_default_org_policies(org_id, tier)
        self._policy_engine.load_org_rules(org_id, rules)

        # Return context
        ctx = TenantSessionContext(
            org_id=org_id, org_name=name, org_tier=tier,
            user_id=creator_user_id, seat_id=seat_id,
            display_name=creator_user_id,
            role=Role.ORG_ADMIN,
            scopes=ROLE_SCOPES[Role.ORG_ADMIN],
            team_id=default_team_id, team_name="General",
        )

        log.info(f"Created org '{name}' ({org_id}) tier={tier}")
        return org, ctx

    def get_organization(self, org_id: str) -> Optional[Organization]:
        if org_id in self._orgs:
            return self._orgs[org_id]
        # Try loading from DB
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM organizations WHERE org_id = ?", (org_id,)
        ).fetchone()
        conn.close()
        if row:
            org = Organization(
                org_id=row["org_id"], name=row["name"], tier=row["tier"],
                created_at=row["created_at"], billing_email=row["billing_email"],
                settings=json.loads(row["settings"]),
                is_active=bool(row["is_active"]),
                total_transactions=row["total_transactions"],
                storage_bytes=row["storage_bytes"],
            )
            self._orgs[org_id] = org
            return org
        return None

    def update_tier(self, org_id: str, new_tier: str) -> bool:
        org = self.get_organization(org_id)
        if not org:
            return False
        org.tier = new_tier
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE organizations SET tier = ? WHERE org_id = ?",
            (new_tier, org_id),
        )
        conn.commit()
        conn.close()
        # Reload policies with new tier limits
        rules = build_default_org_policies(org_id, new_tier)
        self._policy_engine.load_org_rules(org_id, rules)
        log.info(f"Org {org_id} upgraded to tier {new_tier}")
        return True

    # ── Seat Management ───────────────────────────────────────────────

    def _create_seat(
        self, org_id: str, user_id: str, display_name: str = "",
        role: str = Role.STANDARD_USER, team_id: str = "",
        email: str = "",
    ) -> str:
        seat_id = f"seat_{uuid.uuid4().hex[:10]}"
        now = time.time()
        scopes = ROLE_SCOPES.get(role, ROLE_SCOPES[Role.STANDARD_USER])

        seat = Seat(
            seat_id=seat_id, org_id=org_id, user_id=user_id,
            display_name=display_name or user_id, email=email,
            role=role, scopes=scopes, team_id=team_id,
            created_at=now, last_active_at=now,
        )
        self._seats[seat_id] = seat

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO seats VALUES (?,?,?,?,?,?,?,1,?,?)",
            (seat_id, org_id, user_id, display_name or user_id, email,
             role, json.dumps(scopes), now, now),
        )
        conn.commit()
        conn.close()
        return seat_id

    def invite_seat(
        self, org_id: str, email: str, role: str,
        team_id: str = "", invited_by_seat_id: str = "",
    ) -> Invitation:
        org = self.get_organization(org_id)
        if not org:
            raise ValueError(f"Org {org_id} not found")

        limits = TIER_LIMITS.get(org.tier, TIER_LIMITS[OrgTier.FREE])
        current_seats = len([
            s for s in self._seats.values()
            if s.org_id == org_id and s.is_active
        ])
        if limits["max_seats"] > 0 and current_seats >= limits["max_seats"]:
            raise ValueError(
                f"Seat limit reached ({limits['max_seats']}) for tier {org.tier}. "
                f"Upgrade to add more seats."
            )

        invite_id = f"inv_{uuid.uuid4().hex[:10]}"
        now = time.time()
        invite = Invitation(
            invite_id=invite_id, org_id=org_id, email=email,
            role=role, team_id=team_id,
            invited_by_seat_id=invited_by_seat_id,
            created_at=now, expires_at=now + 86400 * 7,
        )
        self._invitations[invite_id] = invite

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO invitations VALUES (?,?,?,?,?,?,?,0)",
            (invite_id, org_id, email, role, team_id,
             invited_by_seat_id, now, now + 86400 * 7),
        )
        conn.commit()
        conn.close()

        log.info(f"Invitation {invite_id} sent to {email} for org {org_id}")
        return invite

    def accept_invitation(self, invite_id: str, user_id: str) -> Optional[Seat]:
        invite = self._invitations.get(invite_id)
        if not invite or invite.accepted:
            return None
        if time.time() > invite.expires_at:
            return None

        invite.accepted = True
        seat_id = self._create_seat(
            org_id=invite.org_id, user_id=user_id,
            role=invite.role, team_id=invite.team_id,
            email=invite.email,
        )

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE invitations SET accepted = 1 WHERE invite_id = ?",
            (invite_id,),
        )
        conn.commit()
        conn.close()

        return self._seats.get(seat_id)

    def get_org_seats(self, org_id: str) -> List[Seat]:
        return [s for s in self._seats.values() if s.org_id == org_id]

    def get_seat(self, seat_id: str) -> Optional[Seat]:
        return self._seats.get(seat_id)

    def update_seat_role(self, seat_id: str, new_role: str) -> bool:
        seat = self._seats.get(seat_id)
        if not seat:
            return False
        seat.role = new_role
        seat.scopes = ROLE_SCOPES.get(new_role, ROLE_SCOPES[Role.STANDARD_USER])
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE seats SET role = ?, scopes = ? WHERE seat_id = ?",
            (new_role, json.dumps(seat.scopes), seat_id),
        )
        conn.commit()
        conn.close()
        return True

    def deactivate_seat(self, seat_id: str) -> bool:
        seat = self._seats.get(seat_id)
        if not seat:
            return False
        seat.is_active = False
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE seats SET is_active = 0 WHERE seat_id = ?", (seat_id,)
        )
        conn.commit()
        conn.close()
        return True

    # ── Team Management ───────────────────────────────────────────────

    def create_team(self, org_id: str, name: str, description: str = "") -> Team:
        team_id = f"team_{uuid.uuid4().hex[:8]}"
        now = time.time()
        team = Team(
            team_id=team_id, org_id=org_id,
            name=name, description=description, created_at=now,
        )
        self._teams[team_id] = team
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO teams VALUES (?,?,?,?,'[]')",
            (team_id, org_id, name, now),
        )
        conn.commit()
        conn.close()
        return team

    def get_org_teams(self, org_id: str) -> List[Team]:
        return [t for t in self._teams.values() if t.org_id == org_id]

    # ── Node Management ───────────────────────────────────────────────

    def register_node(
        self, org_id: str, node_type: str = "worker",
        platform: str = "", ip_address: str = "",
        capabilities: List[str] = None,
    ) -> OrgNode:
        org = self.get_organization(org_id)
        if not org:
            raise ValueError(f"Org {org_id} not found")

        limits = TIER_LIMITS.get(org.tier, TIER_LIMITS[OrgTier.FREE])
        current_nodes = len([
            n for n in self._nodes.values()
            if n.org_id == org_id
        ])
        if limits["max_nodes"] > 0 and current_nodes >= limits["max_nodes"]:
            raise ValueError(
                f"Node limit reached ({limits['max_nodes']}) for tier {org.tier}"
            )

        node_id = f"node_{uuid.uuid4().hex[:10]}"
        now = time.time()
        node = OrgNode(
            node_id=node_id, org_id=org_id,
            node_type=node_type, platform=platform,
            ip_address=ip_address,
            capabilities=capabilities or [],
            created_at=now, last_heartbeat=now,
        )
        self._nodes[node_id] = node

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,'[]',?)",
            (node_id, org_id, node_type, "standby",
             "", platform, ip_address, now, now),
        )
        conn.commit()
        conn.close()
        return node

    def get_org_nodes(self, org_id: str) -> List[OrgNode]:
        return [n for n in self._nodes.values() if n.org_id == org_id]

    def update_node_heartbeat(self, node_id: str, status: str = "active") -> bool:
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.status = status
        node.last_heartbeat = time.time()
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE nodes SET status = ?, last_heartbeat = ? WHERE node_id = ?",
            (status, node.last_heartbeat, node_id),
        )
        conn.commit()
        conn.close()
        return True

    def assign_node_to_seat(self, node_id: str, seat_id: str) -> bool:
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.assigned_seat_id = seat_id
        node.status = "active"
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE nodes SET assigned_seat_id = ?, status = 'active' WHERE node_id = ?",
            (seat_id, node_id),
        )
        conn.commit()
        conn.close()
        return True

    # ── Context Resolution ────────────────────────────────────────────

    def resolve_context(self, request) -> TenantSessionContext:
        """
        Full multi-tenant context resolution from an HTTP request.
        
        Priority:
        1. Authorization: Bearer <JWT>
        2. X-JARVIS-* headers (relay mode)
        3. Default local solo context
        """
        from tenant_context import resolve_from_request
        ctx = resolve_from_request(request)

        # If local mode, create a local org automatically
        if ctx.org_id == "local" and not self.get_organization("local"):
            self.create_organization(
                name="Local Workspace", tier=OrgTier.SOVEREIGN,
                creator_user_id=ctx.user_id,
            )

        return ctx

    def get_policy_engine(self) -> PolicyEngine:
        return self._policy_engine

    # ── Billing / Usage ───────────────────────────────────────────────

    def record_transaction(self, org_id: str, seat_id: str = "", node_id: str = ""):
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE organizations SET total_transactions = total_transactions + 1 WHERE org_id = ?",
            (org_id,),
        )
        conn.commit()
        conn.close()

        org = self.get_organization(org_id)
        if org:
            org.total_transactions += 1
            limits = TIER_LIMITS.get(org.tier, TIER_LIMITS[OrgTier.FREE])
            if (limits["max_daily_transactions"] > 0 and
                    org.total_transactions > limits["max_daily_transactions"]):
                log.warning(
                    f"Org {org_id} exceeded daily transaction limit "
                    f"({limits['max_daily_transactions']})"
                )

    def record_storage(self, org_id: str, bytes_used: int):
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE organizations SET storage_bytes = storage_bytes + ? WHERE org_id = ?",
            (bytes_used, org_id),
        )
        conn.commit()
        conn.close()
        org = self.get_organization(org_id)
        if org:
            org.storage_bytes += bytes_used

    def get_usage_summary(self, org_id: str) -> Dict[str, Any]:
        org = self.get_organization(org_id)
        if not org:
            return {}
        limits = TIER_LIMITS.get(org.tier, TIER_LIMITS[OrgTier.FREE])
        seats = self.get_org_seats(org_id)
        nodes = self.get_org_nodes(org_id)
        return {
            "org_id": org_id,
            "org_name": org.name,
            "tier": org.tier,
            "seats": {
                "used": len([s for s in seats if s.is_active]),
                "limit": limits["max_seats"],
            },
            "nodes": {
                "used": len(nodes),
                "limit": limits["max_nodes"],
            },
            "transactions": {
                "total": org.total_transactions,
                "daily_limit": limits["max_daily_transactions"],
            },
            "storage": {
                "bytes_used": org.storage_bytes,
                "mb_limit": limits["max_storage_mb"],
            },
        }

    # ── Serialization ─────────────────────────────────────────────────

    def export_org_config(self, org_id: str) -> Dict[str, Any]:
        org = self.get_organization(org_id)
        if not org:
            return {}
        return {
            "organization": {
                "org_id": org.org_id,
                "name": org.name,
                "tier": org.tier,
                "created_at": org.created_at,
                "billing_email": org.billing_email,
            },
            "teams": [
                {"team_id": t.team_id, "name": t.name, "description": t.description}
                for t in self.get_org_teams(org_id)
            ],
            "seats": [
                {
                    "seat_id": s.seat_id, "user_id": s.user_id,
                    "display_name": s.display_name, "role": s.role,
                    "team_id": s.team_id, "is_active": s.is_active,
                }
                for s in self.get_org_seats(org_id)
            ],
            "nodes": [
                {
                    "node_id": n.node_id, "node_type": n.node_type,
                    "status": n.status, "platform": n.platform,
                    "capabilities": n.capabilities,
                }
                for n in self.get_org_nodes(org_id)
            ],
            "usage": self.get_usage_summary(org_id),
        }


# ── Singleton ───────────────────────────────────────────────────────────

_org_manager: Optional[OrgManager] = None


def get_org_manager() -> OrgManager:
    global _org_manager
    if _org_manager is None:
        _org_manager = OrgManager()
    return _org_manager
