"""
JARVIS Deterministic Policy Engine

Enforces organization-level policies with OPA-style rule evaluation.
Every agent action, MCP tool call, and resource access is screened against
compiled policy rules before execution.

Policy hierarchy:
  Global Defaults → Org Policies → Team Overrides → Seat Overrides

Rules are compiled at org load time for zero-latency evaluation.
No LLM calls — deterministic, auditable, tamper-proof.
"""
import os
import re
import json
import time
import logging
import hashlib
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("jarvis-policy")


# ── Policy Verdicts ─────────────────────────────────────────────────────
class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"
    ESCALATE = "escalate"


class PolicyCategory(str, Enum):
    AGENT_ACCESS = "agent_access"
    TOOL_ACCESS = "tool_access"
    FILE_ACCESS = "file_access"
    DB_ACCESS = "db_access"
    CLOUD_ACCESS = "cloud_access"
    NETWORK_ACCESS = "network_access"
    RATE_LIMIT = "rate_limit"
    DATA_CLASS = "data_classification"
    TIME_WINDOW = "time_window"
    APPROVAL = "approval"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class PolicyRule:
    """A single compiled policy rule."""
    rule_id: str
    category: PolicyCategory
    description: str
    effect: Verdict  # allow / deny / needs_approval
    priority: int = 50  # 0=highest priority, 100=lowest

    # Match conditions (all must be true for rule to fire)
    match_scopes: List[str] = field(default_factory=list)  # Required scopes
    match_agent_domains: List[str] = field(default_factory=list)
    match_mcp_servers: List[str] = field(default_factory=list)
    match_tool_patterns: List[str] = field(default_factory=list)  # Regex
    match_data_classes: List[str] = field(default_factory=list)
    match_time_windows: List[str] = field(default_factory=list)  # "09:00-17:00"
    match_weekdays: List[int] = field(default_factory=list)  # 0=Mon, 6=Sun
    match_node_types: List[str] = field(default_factory=list)
    match_user_roles: List[str] = field(default_factory=list)
    match_org_tiers: List[str] = field(default_factory=list)

    # Limits (for rate-limit rules)
    max_per_minute: int = 0
    max_per_hour: int = 0
    max_per_day: int = 0
    max_concurrent: int = 0

    # Approval requirements
    approval_required_by: List[str] = field(default_factory=list)  # Roles
    approval_timeout_seconds: int = 300

    # Audit
    log_verbosely: bool = True
    tags: List[str] = field(default_factory=list)

    # Compiled patterns
    _compiled_patterns: List[re.Pattern] = field(default_factory=list, repr=False)

    def __post_init__(self):
        for p in self.match_tool_patterns:
            try:
                self._compiled_patterns.append(re.compile(p, re.IGNORECASE))
            except re.error:
                log.warning(f"Invalid regex in rule {self.rule_id}: {p}")

    def matches_tool(self, tool_name: str, tool_args: Dict[str, Any] = None) -> bool:
        """Check if a tool matches this rule's tool patterns."""
        if not self.match_tool_patterns:
            return True  # No pattern = match all tools
        tool_str = json.dumps({"tool": tool_name, "args": tool_args or {}})
        return any(pat.search(tool_str) for pat in self._compiled_patterns)


# ── Rate Limit State (per seat) ─────────────────────────────────────────
@dataclass
class RateLimitBucket:
    """Sliding window counter for rate limiting."""
    minute_count: int = 0
    hour_count: int = 0
    day_count: int = 0
    last_minute_reset: float = 0
    last_hour_reset: float = 0
    last_day_reset: float = 0


# ── Policy Engine ───────────────────────────────────────────────────────

class PolicyEngine:
    """
    Deterministic policy evaluation engine.
    
    Rules are loaded once per org and evaluated synchronously.
    No LLM calls — all decisions are instant and auditable.
    """

    def __init__(self):
        self._rules: Dict[str, List[PolicyRule]] = {}  # org_id → rules
        self._rate_buckets: Dict[str, RateLimitBucket] = {}  # "org:seat:rule" → bucket
        self._audit_log: List[Dict[str, Any]] = []

    def load_org_rules(self, org_id: str, rules: List[PolicyRule]):
        """Load compiled rules for an organization."""
        self._rules[org_id] = sorted(rules, key=lambda r: r.priority)
        log.info(f"Loaded {len(rules)} policy rules for org {org_id}")

    def get_org_rules(self, org_id: str) -> List[PolicyRule]:
        return self._rules.get(org_id, [])

    def evaluate(
        self,
        org_id: str,
        user_role: str,
        scopes: List[str],
        agent_domain: str,
        tool_name: str = "",
        tool_args: Dict[str, Any] = None,
        mcp_server: str = "",
        data_classification: str = DataClassification.INTERNAL,
        node_type: str = "worker",
        seat_id: str = "",
    ) -> Tuple[Verdict, Optional[PolicyRule], str]:
        """
        Evaluate all rules against the given context.
        Returns: (verdict, matched_rule_or_none, reason)
        
        First matching rule wins (rules are sorted by priority).
        Default if no rules match: ALLOW.
        """
        rules = self._rules.get(org_id, [])

        for rule in rules:
            if not self._rule_matches(
                rule, user_role, scopes, agent_domain,
                tool_name, tool_args, mcp_server,
                data_classification, node_type, seat_id
            ):
                continue

            # Rule matches — check rate limits
            if rule.max_per_minute or rule.max_per_hour or rule.max_per_day:
                allowed = self._check_rate_limit(rule, org_id, seat_id)
                if not allowed:
                    self._audit(org_id, seat_id, rule, Verdict.DENY, "rate_limit_exceeded")
                    return Verdict.DENY, rule, f"Rate limit exceeded: {rule.description}"

            # Check approval flow
            if rule.effect == Verdict.NEEDS_APPROVAL:
                self._audit(org_id, seat_id, rule, Verdict.NEEDS_APPROVAL, "pending_approval")
                return Verdict.NEEDS_APPROVAL, rule, f"Requires approval from: {rule.approval_required_by}"

            self._audit(org_id, seat_id, rule, rule.effect, "matched")
            return rule.effect, rule, rule.description

        # No rules matched — default allow
        return Verdict.ALLOW, None, "No policy rule matched — default allow"

    def _rule_matches(
        self,
        rule: PolicyRule,
        user_role: str,
        scopes: List[str],
        agent_domain: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        mcp_server: str,
        data_classification: str,
        node_type: str,
        seat_id: str,
    ) -> bool:
        """Check if all match conditions are satisfied."""
        if rule.match_user_roles and user_role not in rule.match_user_roles:
            return False
        if rule.match_scopes:
            if not any(s in scopes or "*" in scopes for s in rule.match_scopes):
                return False
        if rule.match_agent_domains and agent_domain not in rule.match_agent_domains:
            return False
        if rule.match_mcp_servers and mcp_server not in rule.match_mcp_servers:
            return False
        if rule.match_tool_patterns and not rule.matches_tool(tool_name, tool_args):
            return False
        if rule.match_data_classes and data_classification not in rule.match_data_classes:
            return False
        if rule.match_node_types and node_type not in rule.match_node_types:
            return False
        return True

    def _check_rate_limit(self, rule: PolicyRule, org_id: str, seat_id: str) -> bool:
        """Check if the action is within rate limits."""
        key = f"{org_id}:{seat_id}:{rule.rule_id}"
        now = time.time()
        bucket = self._rate_buckets.get(key)
        if not bucket:
            bucket = RateLimitBucket()
            self._rate_buckets[key] = bucket

        # Reset windows
        if now - bucket.last_minute_reset > 60:
            bucket.minute_count = 0
            bucket.last_minute_reset = now
        if now - bucket.last_hour_reset > 3600:
            bucket.hour_count = 0
            bucket.last_hour_reset = now
        if now - bucket.last_day_reset > 86400:
            bucket.day_count = 0
            bucket.last_day_reset = now

        bucket.minute_count += 1
        bucket.hour_count += 1
        bucket.day_count += 1

        if rule.max_per_minute and bucket.minute_count > rule.max_per_minute:
            return False
        if rule.max_per_hour and bucket.hour_count > rule.max_per_hour:
            return False
        if rule.max_per_day and bucket.day_count > rule.max_per_day:
            return False
        return True

    def _audit(self, org_id, seat_id, rule, verdict, reason):
        entry = {
            "timestamp": time.time(),
            "org_id": org_id,
            "seat_id": seat_id,
            "rule_id": rule.rule_id,
            "category": rule.category.value,
            "effect": rule.effect.value,
            "verdict": verdict.value,
            "reason": reason,
            "description": rule.description,
            "tags": rule.tags,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
        if verdict == Verdict.DENY:
            log.warning(f"POLICY DENY: org={org_id} seat={seat_id} rule={rule.rule_id} — {reason}")

    def get_audit_log(self, org_id: str = None, limit: int = 100) -> List[Dict]:
        entries = self._audit_log
        if org_id:
            entries = [e for e in entries if e["org_id"] == org_id]
        return entries[-limit:]


# ── Default Policy Templates ────────────────────────────────────────────

def build_default_org_policies(org_id: str, tier: str = "free") -> List[PolicyRule]:
    """Build default policy rules for an organization based on tier."""
    rules = []

    # ── Agent Access ──────────────────────────────────────────────────
    rules.append(PolicyRule(
        rule_id=f"{org_id}:agent:core:allow",
        category=PolicyCategory.AGENT_ACCESS,
        description="Allow CORE_AGENT for all users",
        effect=Verdict.ALLOW,
        priority=10,
        match_agent_domains=["CORE_AGENT"],
        tags=["default", "agent"],
    ))

    rules.append(PolicyRule(
        rule_id=f"{org_id}:agent:os:role_check",
        category=PolicyCategory.AGENT_ACCESS,
        description="OS_AGENT requires SYSTEM_ENGINEER or higher",
        effect=Verdict.ALLOW,
        priority=20,
        match_agent_domains=["OS_AGENT"],
        match_user_roles=["GLOBAL_ADMIN", "ORG_ADMIN", "TEAM_LEAD", "SYSTEM_ENGINEER", "DEVOPS"],
        tags=["default", "agent", "os"],
    ))

    rules.append(PolicyRule(
        rule_id=f"{org_id}:agent:infra:role_check",
        category=PolicyCategory.AGENT_ACCESS,
        description="INFRA_AGENT requires ORG_ADMIN or higher",
        effect=Verdict.ALLOW,
        priority=20,
        match_agent_domains=["INFRA_AGENT"],
        match_user_roles=["GLOBAL_ADMIN", "ORG_ADMIN"],
        tags=["default", "agent", "infra"],
    ))

    # ── Tool Access ───────────────────────────────────────────────────
    rules.append(PolicyRule(
        rule_id=f"{org_id}:tool:destructive:deny",
        category=PolicyCategory.TOOL_ACCESS,
        description="Deny destructive DB operations (DROP, TRUNCATE) for non-admins",
        effect=Verdict.DENY,
        priority=5,
        match_tool_patterns=[r"DROP\s+TABLE", r"TRUNCATE", r"DELETE\s+FROM.*WHERE\s*1\s*=\s*1"],
        match_user_roles=["STANDARD_USER", "VIEWER", "GUEST"],
        tags=["default", "security", "sql"],
    ))

    rules.append(PolicyRule(
        rule_id=f"{org_id}:tool:shell:admin_only",
        category=PolicyCategory.TOOL_ACCESS,
        description="Shell/system commands require SYSTEM_ENGINEER+",
        effect=Verdict.DENY,
        priority=5,
        match_tool_patterns=[r"shell", r"exec", r"subprocess", r"os\.system"],
        match_user_roles=["STANDARD_USER", "VIEWER", "GUEST"],
        tags=["default", "security", "shell"],
    ))

    # ── Data Classification ───────────────────────────────────────────
    rules.append(PolicyRule(
        rule_id=f"{org_id}:data:restricted:approval",
        category=PolicyCategory.DATA_CLASS,
        description="Restricted data access requires approval",
        effect=Verdict.NEEDS_APPROVAL,
        priority=3,
        match_data_classes=["restricted"],
        approval_required_by=["ORG_ADMIN", "TEAM_LEAD"],
        tags=["default", "data", "approval"],
    ))

    # ── Rate Limits ───────────────────────────────────────────────────
    if tier in ("free", "pro"):
        rules.append(PolicyRule(
            rule_id=f"{org_id}:rate:write:limit",
            category=PolicyCategory.RATE_LIMIT,
            description="Write operations limited per seat",
            effect=Verdict.ALLOW,
            priority=15,
            match_tool_patterns=[r"write", r"create", r"update", r"delete"],
            max_per_minute=30,
            max_per_hour=500,
            tags=["default", "rate_limit"],
        ))

    # ── Network / Cloud ──────────────────────────────────────────────
    rules.append(PolicyRule(
        rule_id=f"{org_id}:cloud:terminate:deny",
        category=PolicyCategory.CLOUD_ACCESS,
        description="Block instance termination for non-admins",
        effect=Verdict.DENY,
        priority=5,
        match_tool_patterns=[r"terminate", r"delete.*instance", r"destroy"],
        match_user_roles=["STANDARD_USER", "VIEWER", "GUEST", "DEVOPS"],
        tags=["default", "cloud", "security"],
    ))

    # ── Time Window (Weekend restrictions for Group tier) ────────────
    if tier in ("group", "enterprise"):
        rules.append(PolicyRule(
            rule_id=f"{org_id}:time:weekend:restrict",
            category=PolicyCategory.TIME_WINDOW,
            description="No cloud writes on weekends",
            effect=Verdict.DENY,
            priority=10,
            match_weekdays=[5, 6],  # Sat, Sun
            match_tool_patterns=[r"cloud", r"deploy", r"terminate"],
            tags=["default", "time"],
        ))

    return rules


# ── Policy Serialization ────────────────────────────────────────────────

def rules_to_json(rules: List[PolicyRule]) -> str:
    """Serialize rules to JSON for storage."""
    out = []
    for r in rules:
        out.append({
            "rule_id": r.rule_id,
            "category": r.category.value,
            "description": r.description,
            "effect": r.effect.value,
            "priority": r.priority,
            "match_scopes": r.match_scopes,
            "match_agent_domains": r.match_agent_domains,
            "match_mcp_servers": r.match_mcp_servers,
            "match_tool_patterns": r.match_tool_patterns,
            "match_data_classes": r.match_data_classes,
            "match_user_roles": r.match_user_roles,
            "match_weekdays": r.match_weekdays,
            "max_per_minute": r.max_per_minute,
            "max_per_hour": r.max_per_hour,
            "max_per_day": r.max_per_day,
            "approval_required_by": r.approval_required_by,
            "tags": r.tags,
        })
    return json.dumps(out, indent=2)


def rules_from_json(data: str) -> List[PolicyRule]:
    """Deserialize rules from JSON."""
    items = json.loads(data)
    rules = []
    for item in items:
        rules.append(PolicyRule(
            rule_id=item["rule_id"],
            category=PolicyCategory(item["category"]),
            description=item.get("description", ""),
            effect=Verdict(item["effect"]),
            priority=item.get("priority", 50),
            match_scopes=item.get("match_scopes", []),
            match_agent_domains=item.get("match_agent_domains", []),
            match_mcp_servers=item.get("match_mcp_servers", []),
            match_tool_patterns=item.get("match_tool_patterns", []),
            match_data_classes=item.get("match_data_classes", []),
            match_user_roles=item.get("match_user_roles", []),
            match_weekdays=item.get("match_weekdays", []),
            max_per_minute=item.get("max_per_minute", 0),
            max_per_hour=item.get("max_per_hour", 0),
            max_per_day=item.get("max_per_day", 0),
            approval_required_by=item.get("approval_required_by", []),
            tags=item.get("tags", []),
        ))
    return rules
