"""JARVIS Permission Policies — Configurable AI permission system.

Users establish rules for what JARVIS can do without asking:
- Automatically allow: safe operations
- Ask first: moderate risk operations
- Always ask: high-risk operations
- Deny: forbidden operations
"""

import os
import json
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

log = logging.getLogger("policies")

POLICIES_FILE = Path.home() / ".jarvis" / "policies.json"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyAction(Enum):
    AUTO_ALLOW = "auto_allow"
    ASK_FIRST = "ask_first"
    ALWAYS_ASK = "always_ask"
    DENY = "deny"


@dataclass
class PolicyRule:
    id: str
    name: str
    description: str
    category: str  # file, network, system, external, financial
    action: str  # PolicyAction value
    risk_level: str  # RiskLevel value
    patterns: List[str] = field(default_factory=list)  # regex patterns to match
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "action": self.action,
            "risk_level": self.risk_level,
            "patterns": self.patterns,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PolicyRule":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PolicyDecision:
    """Result of evaluating an action against policies."""
    allowed: bool
    action: str  # auto_allow, ask_first, always_ask, deny
    reason: str
    matched_rule: Optional[str] = None
    risk_level: str = "low"
    requires_approval: bool = False


class PermissionManager:
    """Manages permission policies and evaluates actions."""

    def __init__(self):
        self._rules: Dict[str, PolicyRule] = {}
        self._load()

    def _load(self):
        """Load policies from disk."""
        if POLICIES_FILE.exists():
            try:
                data = json.loads(POLICIES_FILE.read_text())
                for item in data:
                    rule = PolicyRule.from_dict(item)
                    self._rules[rule.id] = rule
            except Exception as e:
                log.error(f"[POLICIES] Load failed: {e}")
                self._load_defaults()
        else:
            self._load_defaults()

    def _save(self):
        """Save policies to disk."""
        POLICIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self._rules.values()]
        POLICIES_FILE.write_text(json.dumps(data, indent=2))

    def _load_defaults(self):
        """Load default permission policies."""
        defaults = [
            # LOW RISK — Auto-allow
            PolicyRule(
                id="file_read", name="Read Files", description="Read file contents",
                category="file", action=PolicyAction.AUTO_ALLOW.value, risk_level=RiskLevel.LOW.value,
                patterns=[r"^read_file$", r"^open_file$", r"^view_file$"],
            ),
            PolicyRule(
                id="file_create", name="Create Files", description="Create new files",
                category="file", action=PolicyAction.AUTO_ALLOW.value, risk_level=RiskLevel.LOW.value,
                patterns=[r"^create_file$", r"^write_file$", r"^new_file$"],
            ),
            PolicyRule(
                id="file_edit", name="Edit Files", description="Modify existing files",
                category="file", action=PolicyAction.AUTO_ALLOW.value, risk_level=RiskLevel.LOW.value,
                patterns=[r"^edit_file$", r"^modify_file$", r"^update_file$"],
            ),
            PolicyRule(
                id="run_tests", name="Run Tests", description="Execute test suites",
                category="system", action=PolicyAction.AUTO_ALLOW.value, risk_level=RiskLevel.LOW.value,
                patterns=[r"^run_tests?$", r"^test$", r"^pytest$"],
            ),
            PolicyRule(
                id="browse_web", name="Browse Web", description="Navigate websites",
                category="network", action=PolicyAction.AUTO_ALLOW.value, risk_level=RiskLevel.LOW.value,
                patterns=[r"^navigate$", r"^browse$", r"^open_url$", r"^go_to$"],
            ),
            PolicyRule(
                id="web_search", name="Web Search", description="Search the web",
                category="network", action=PolicyAction.AUTO_ALLOW.value, risk_level=RiskLevel.LOW.value,
                patterns=[r"^search$", r"^web_search$", r"^google$"],
            ),

            # MEDIUM RISK — Ask first
            PolicyRule(
                id="file_delete", name="Delete Files", description="Delete files or directories",
                category="file", action=PolicyAction.ASK_FIRST.value, risk_level=RiskLevel.MEDIUM.value,
                patterns=[r"^delete_file$", r"^remove_file$", r"^rm$"],
            ),
            PolicyRule(
                id="install_software", name="Install Software", description="Install applications",
                category="system", action=PolicyAction.ASK_FIRST.value, risk_level=RiskLevel.MEDIUM.value,
                patterns=[r"^install$", r"^pip_install$", r"^npm_install$", r"^apt_install$"],
            ),
            PolicyRule(
                id="modify_settings", name="Modify Settings", description="Change system settings",
                category="system", action=PolicyAction.ASK_FIRST.value, risk_level=RiskLevel.MEDIUM.value,
                patterns=[r"^set_setting$", r"^change_config$", r"^modify_settings$"],
            ),
            PolicyRule(
                id="download_file", name="Download Files", description="Download from internet",
                category="network", action=PolicyAction.ASK_FIRST.value, risk_level=RiskLevel.MEDIUM.value,
                patterns=[r"^download$", r"^fetch$", r"^wget$", r"^curl$"],
            ),

            # HIGH RISK — Always ask
            PolicyRule(
                id="send_email", name="Send Email", description="Send emails to external recipients",
                category="external", action=PolicyAction.ALWAYS_ASK.value, risk_level=RiskLevel.HIGH.value,
                patterns=[r"^send_email$", r"^email$", r"^smtp$"],
            ),
            PolicyRule(
                id="publish_content", name="Publish Content", description="Publish to external platforms",
                category="external", action=PolicyAction.ALWAYS_ASK.value, risk_level=RiskLevel.HIGH.value,
                patterns=[r"^publish$", r"^post$", r"^deploy$", r"^push_to_live$"],
            ),
            PolicyRule(
                id="modify_system", name="Modify System", description="Modify system configuration",
                category="system", action=PolicyAction.ALWAYS_ASK.value, risk_level=RiskLevel.HIGH.value,
                patterns=[r"^system_config$", r"^registry$", r"^sysctl$", r"^systemd$"],
            ),

            # CRITICAL — Always ask with extra verification
            PolicyRule(
                id="financial_transaction", name="Financial Transaction", description="Execute financial transactions",
                category="financial", action=PolicyAction.ALWAYS_ASK.value, risk_level=RiskLevel.CRITICAL.value,
                patterns=[r"^payment$", r"^purchase$", r"^buy$", r"^transfer$", r"^transaction$"],
            ),
            PolicyRule(
                id="delete_critical", name="Delete Critical Data", description="Delete important data",
                category="system", action=PolicyAction.ALWAYS_ASK.value, risk_level=RiskLevel.CRITICAL.value,
                patterns=[r"^destroy$", r"^wipe$", r"^format$", r"^shred$"],
            ),
            PolicyRule(
                id="change_credentials", name="Change Credentials", description="Modify passwords or keys",
                category="system", action=PolicyAction.ALWAYS_ASK.value, risk_level=RiskLevel.CRITICAL.value,
                patterns=[r"^change_password$", r"^rotate_key$", r"^update_credentials$"],
            ),
        ]

        for rule in defaults:
            self._rules[rule.id] = rule
        self._save()
        log.info(f"[POLICIES] Loaded {len(defaults)} default rules")

    def evaluate(self, action: str, category: str = "system") -> PolicyDecision:
        """Evaluate an action against all policies."""
        import re

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            for pattern in rule.patterns:
                if re.match(pattern, action, re.IGNORECASE):
                    return PolicyDecision(
                        allowed=rule.action != PolicyAction.DENY.value,
                        action=rule.action,
                        reason=f"Matched rule: {rule.name}",
                        matched_rule=rule.id,
                        risk_level=rule.risk_level,
                        requires_approval=rule.action in (PolicyAction.ASK_FIRST.value, PolicyAction.ALWAYS_ASK.value),
                    )

        # Default: ask first for unknown actions
        return PolicyDecision(
            allowed=True,
            action=PolicyAction.ASK_FIRST.value,
            reason="No matching policy — default to ask",
            risk_level=RiskLevel.MEDIUM.value,
            requires_approval=True,
        )

    def update_rule(self, rule_id: str, **kwargs) -> Optional[PolicyRule]:
        """Update a policy rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            return None
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        self._save()
        return rule

    def add_rule(self, rule: PolicyRule) -> PolicyRule:
        """Add a custom policy rule."""
        self._rules[rule.id] = rule
        self._save()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a policy rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            self._save()
            return True
        return False

    def get_rules(self) -> List[dict]:
        """Get all policy rules."""
        return [r.to_dict() for r in self._rules.values()]

    def get_rules_by_category(self, category: str) -> List[dict]:
        """Get rules filtered by category."""
        return [r.to_dict() for r in self._rules.values() if r.category == category]

    def get_rules_by_risk(self, risk_level: str) -> List[dict]:
        """Get rules filtered by risk level."""
        return [r.to_dict() for r in self._rules.values() if r.risk_level == risk_level]


# Global instance
_manager = None


def get_permission_manager() -> PermissionManager:
    global _manager
    if _manager is None:
        _manager = PermissionManager()
    return _manager
