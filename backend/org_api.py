"""
JARVIS Multi-Tenant API Router

All API calls flow through this router for tenant isolation.
Every request carries full tenant context through the execution chain.

Routes:
  /api/org/*          — Organization management
  /api/org/teams/*    — Team management
  /api/org/seats/*    — Seat/invitation management
  /api/org/nodes/*    — Node management
  /api/org/billing/*  — Usage and billing
  /api/org/policy/*   — Policy management
"""
import os
import json
import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field

from tenant_context import (
    TenantSessionContext, OrgTier, TIER_LIMITS,
    Role, ROLE_SCOPES, create_local_context,
)
from org_manager import get_org_manager, OrgManager
from policy_engine import (
    PolicyEngine, Verdict, build_default_org_policies,
    rules_to_json, rules_from_json,
)

log = logging.getLogger("jarvis-org-api")

router = APIRouter(prefix="/api/org", tags=["org"])


# ── Dependency: Resolve tenant context ──────────────────────────────────

async def get_tenant(request: Request) -> TenantSessionContext:
    """Extract tenant context from every incoming request."""
    mgr = get_org_manager()
    return mgr.resolve_context(request)


def require_role(*allowed_roles):
    """Dependency factory: require specific roles."""
    async def _check(tenant: TenantSessionContext = Depends(get_tenant)):
        if tenant.role not in allowed_roles and "*" not in tenant.scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Required role: {allowed_roles}, you have: {tenant.role}"
            )
        return tenant
    return _check


def require_scope(scope: str):
    """Dependency factory: require a specific scope."""
    async def _check(tenant: TenantSessionContext = Depends(get_tenant)):
        if not tenant.has_scope(scope):
            raise HTTPException(
                status_code=403,
                detail=f"Required scope: {scope}"
            )
        return tenant
    return _check


# ── Request Models ──────────────────────────────────────────────────────

class CreateOrgRequest(BaseModel):
    name: str
    tier: str = "free"
    billing_email: str = ""

class UpdateTierRequest(BaseModel):
    tier: str

class InviteSeatRequest(BaseModel):
    email: str
    role: str = "STANDARD_USER"
    team_id: str = ""

class AcceptInviteRequest(BaseModel):
    invite_id: str
    user_id: str

class UpdateSeatRoleRequest(BaseModel):
    seat_id: str
    role: str

class CreateTeamRequest(BaseModel):
    name: str
    description: str = ""

class RegisterNodeRequest(BaseModel):
    node_type: str = "worker"
    platform: str = ""
    ip_address: str = ""
    capabilities: list = []

class AssignNodeRequest(BaseModel):
    node_id: str
    seat_id: str

class PolicyEvaluationRequest(BaseModel):
    agent_domain: str = "CORE_AGENT"
    tool_name: str = ""
    tool_args: dict = {}
    mcp_server: str = ""
    data_classification: str = "internal"
    node_type: str = "worker"

class AddPolicyRuleRequest(BaseModel):
    rule_json: dict


# ── Organization Routes ────────────────────────────────────────────────

@router.get("/status")
async def org_status(tenant: TenantSessionContext = Depends(get_tenant)):
    """Current organization status and limits."""
    mgr = get_org_manager()
    org = mgr.get_organization(tenant.org_id)
    usage = mgr.get_usage_summary(tenant.org_id)
    return {
        "ok": True,
        "tenant": tenant.to_dict(),
        "organization": {
            "org_id": tenant.org_id,
            "tier": tenant.org_tier,
            "limits": tenant.tier_limits,
        },
        "usage": usage,
    }


@router.post("/create")
async def create_organization(
    req: CreateOrgRequest,
    tenant: TenantSessionContext = Depends(get_tenant),
):
    """Create a new organization."""
    mgr = get_org_manager()
    org, ctx = mgr.create_organization(
        name=req.name, tier=req.tier,
        billing_email=req.billing_email,
        creator_user_id=tenant.user_id,
    )
    return {
        "ok": True,
        "organization": mgr.export_org_config(org.org_id),
        "context": ctx.to_dict(),
    }


@router.post("/upgrade")
async def upgrade_tier(
    req: UpdateTierRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN)
    ),
):
    """Upgrade organization tier."""
    mgr = get_org_manager()
    ok = mgr.update_tier(tenant.org_id, req.tier)
    if not ok:
        raise HTTPException(status_code=404, detail="Organization not found")
    org = mgr.get_organization(tenant.org_id)
    limits = TIER_LIMITS.get(req.tier, TIER_LIMITS[OrgTier.FREE])
    return {
        "ok": True,
        "new_tier": req.tier,
        "limits": limits,
    }


@router.get("/config")
async def get_org_config(tenant: TenantSessionContext = Depends(get_tenant)):
    """Full organization configuration export."""
    mgr = get_org_manager()
    return mgr.export_org_config(tenant.org_id)


# ── Seat / Invitation Routes ───────────────────────────────────────────

@router.get("/seats")
async def list_seats(tenant: TenantSessionContext = Depends(get_tenant)):
    """List all seats in the organization."""
    mgr = get_org_manager()
    seats = mgr.get_org_seats(tenant.org_id)
    return {
        "ok": True,
        "seats": [
            {
                "seat_id": s.seat_id,
                "user_id": s.user_id,
                "display_name": s.display_name,
                "email": s.email,
                "role": s.role,
                "team_id": s.team_id,
                "is_active": s.is_active,
                "last_active_at": s.last_active_at,
            }
            for s in seats
        ],
        "count": len(seats),
        "limits": tenant.tier_limits,
    }


@router.post("/seats/invite")
async def invite_seat(
    req: InviteSeatRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN, Role.TEAM_LEAD)
    ),
):
    """Invite a new seat to the organization."""
    mgr = get_org_manager()
    try:
        invite = mgr.invite_seat(
            org_id=tenant.org_id, email=req.email,
            role=req.role, team_id=req.team_id,
            invited_by_seat_id=tenant.seat_id,
        )
        return {
            "ok": True,
            "invitation": {
                "invite_id": invite.invite_id,
                "email": invite.email,
                "role": invite.role,
                "expires_at": invite.expires_at,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/seats/accept")
async def accept_invitation(req: AcceptInviteRequest):
    """Accept an invitation and create a seat."""
    mgr = get_org_manager()
    seat = mgr.accept_invitation(req.invite_id, req.user_id)
    if not seat:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found or expired",
        )
    return {
        "ok": True,
        "seat": {
            "seat_id": seat.seat_id,
            "role": seat.role,
            "org_id": seat.org_id,
            "scopes": seat.scopes,
        },
    }


@router.post("/seats/role")
async def update_seat_role(
    req: UpdateSeatRoleRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN)
    ),
):
    """Update a seat's role."""
    mgr = get_org_manager()
    ok = mgr.update_seat_role(req.seat_id, req.role)
    if not ok:
        raise HTTPException(status_code=404, detail="Seat not found")
    return {"ok": True, "seat_id": req.seat_id, "new_role": req.role}


@router.delete("/seats/{seat_id}")
async def deactivate_seat(
    seat_id: str,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN)
    ),
):
    """Deactivate a seat."""
    mgr = get_org_manager()
    ok = mgr.deactivate_seat(seat_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Seat not found")
    return {"ok": True, "seat_id": seat_id, "is_active": False}


# ── Team Routes ─────────────────────────────────────────────────────────

@router.get("/teams")
async def list_teams(tenant: TenantSessionContext = Depends(get_tenant)):
    mgr = get_org_manager()
    teams = mgr.get_org_teams(tenant.org_id)
    return {
        "ok": True,
        "teams": [
            {"team_id": t.team_id, "name": t.name, "description": t.description}
            for t in teams
        ],
    }


@router.post("/teams/create")
async def create_team(
    req: CreateTeamRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN, Role.TEAM_LEAD)
    ),
):
    mgr = get_org_manager()
    team = mgr.create_team(tenant.org_id, req.name, req.description)
    return {
        "ok": True,
        "team": {"team_id": team.team_id, "name": team.name},
    }


# ── Node Routes ─────────────────────────────────────────────────────────

@router.get("/nodes")
async def list_nodes(tenant: TenantSessionContext = Depends(get_tenant)):
    mgr = get_org_manager()
    nodes = mgr.get_org_nodes(tenant.org_id)
    return {
        "ok": True,
        "nodes": [
            {
                "node_id": n.node_id, "node_type": n.node_type,
                "status": n.status, "assigned_seat_id": n.assigned_seat_id,
                "platform": n.platform, "ip_address": n.ip_address,
                "last_heartbeat": n.last_heartbeat,
                "capabilities": n.capabilities,
            }
            for n in nodes
        ],
    }


@router.post("/nodes/register")
async def register_node(
    req: RegisterNodeRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN, Role.SYSTEM_ENGINEER)
    ),
):
    mgr = get_org_manager()
    try:
        node = mgr.register_node(
            org_id=tenant.org_id, node_type=req.node_type,
            platform=req.platform, ip_address=req.ip_address,
            capabilities=req.capabilities,
        )
        return {
            "ok": True,
            "node": {"node_id": node.node_id, "status": "standby"},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/heartbeat")
async def node_heartbeat(
    node_id: str, status: str = "active",
    tenant: TenantSessionContext = Depends(get_tenant),
):
    mgr = get_org_manager()
    ok = mgr.update_node_heartbeat(node_id, status)
    return {"ok": ok, "node_id": node_id, "status": status}


@router.post("/nodes/assign")
async def assign_node(
    req: AssignNodeRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN)
    ),
):
    mgr = get_org_manager()
    ok = mgr.assign_node_to_seat(req.node_id, req.seat_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True, "node_id": req.node_id, "seat_id": req.seat_id}


# ── Billing / Usage Routes ─────────────────────────────────────────────

@router.get("/billing/usage")
async def usage_summary(tenant: TenantSessionContext = Depends(get_tenant)):
    mgr = get_org_manager()
    return {"ok": True, "usage": mgr.get_usage_summary(tenant.org_id)}


@router.get("/billing/tiers")
async def list_tiers():
    """List all available tiers and their limits."""
    return {
        "ok": True,
        "tiers": {
            tier: limits
            for tier, limits in TIER_LIMITS.items()
        },
        "pricing": {
            "free": {"monthly": 0, "per_seat": 0},
            "pro": {"monthly": 40, "per_seat": 40},
            "group": {"monthly": 500, "per_seat": 20},
            "enterprise": {"monthly": 50000, "per_seat": 100, "note": "Custom pricing"},
            "sovereign": {"monthly": 0, "per_seat": 0, "note": "Self-hosted"},
        },
    }


# ── Policy Routes ───────────────────────────────────────────────────────

@router.get("/policy/rules")
async def list_policy_rules(tenant: TenantSessionContext = Depends(get_tenant)):
    mgr = get_org_manager()
    engine = mgr.get_policy_engine()
    rules = engine.get_org_rules(tenant.org_id)
    return {
        "ok": True,
        "rules": rules_to_json(rules),
        "count": len(rules),
    }


@router.post("/policy/evaluate")
async def evaluate_policy(
    req: PolicyEvaluationRequest,
    tenant: TenantSessionContext = Depends(get_tenant),
):
    """Evaluate a policy action against current tenant context."""
    mgr = get_org_manager()
    engine = mgr.get_policy_engine()
    verdict, rule, reason = engine.evaluate(
        org_id=tenant.org_id,
        user_role=tenant.role,
        scopes=tenant.scopes,
        agent_domain=req.agent_domain,
        tool_name=req.tool_name,
        tool_args=req.tool_args,
        mcp_server=req.mcp_server,
        data_classification=req.data_classification,
        node_type=req.node_type,
        seat_id=tenant.seat_id,
    )
    return {
        "ok": True,
        "verdict": verdict.value,
        "rule_id": rule.rule_id if rule else None,
        "description": rule.description if rule else None,
        "reason": reason,
    }


@router.post("/policy/rules/add")
async def add_policy_rule(
    req: AddPolicyRuleRequest,
    tenant: TenantSessionContext = Depends(
        require_role(Role.GLOBAL_ADMIN, Role.ORG_ADMIN)
    ),
):
    """Add a custom policy rule to the organization."""
    from policy_engine import PolicyRule, PolicyCategory
    rule_data = req.rule_json
    rule = PolicyRule(
        rule_id=rule_data.get("rule_id", f"custom_{int(time.time())}"),
        category=PolicyCategory(rule_data.get("category", "tool_access")),
        description=rule_data.get("description", ""),
        effect=Verdict(rule_data.get("effect", "allow")),
        priority=rule_data.get("priority", 50),
        match_agent_domains=rule_data.get("match_agent_domains", []),
        match_mcp_servers=rule_data.get("match_mcp_servers", []),
        match_tool_patterns=rule_data.get("match_tool_patterns", []),
        match_user_roles=rule_data.get("match_user_roles", []),
        match_data_classes=rule_data.get("match_data_classes", []),
        max_per_minute=rule_data.get("max_per_minute", 0),
        max_per_hour=rule_data.get("max_per_hour", 0),
        max_per_day=rule_data.get("max_per_day", 0),
        approval_required_by=rule_data.get("approval_required_by", []),
        tags=rule_data.get("tags", []),
    )
    mgr = get_org_manager()
    engine = mgr.get_policy_engine()
    existing = engine.get_org_rules(tenant.org_id)
    existing.append(rule)
    engine.load_org_rules(tenant.org_id, existing)
    return {"ok": True, "rule_id": rule.rule_id}


@router.get("/policy/audit")
async def policy_audit_log(
    limit: int = 100,
    tenant: TenantSessionContext = Depends(get_tenant),
):
    mgr = get_org_manager()
    engine = mgr.get_policy_engine()
    log_entries = engine.get_audit_log(tenant.org_id, limit=limit)
    return {"ok": True, "audit_log": log_entries, "count": len(log_entries)}


# ── Context Resolution Endpoint ────────────────────────────────────────

@router.get("/context")
async def current_context(tenant: TenantSessionContext = Depends(get_tenant)):
    """Return the full tenant context for the current request."""
    return {"ok": True, "context": tenant.to_dict()}
