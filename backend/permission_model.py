"""JARVIS Permission Model - Configurable approval gates and risk policies.

Controls which actions require human approval based on:
- Risk level (low/medium/high/critical)
- Action category (financial, communication, destructive, etc.)
- User-configurable autonomy level
- Per-session and per-mission overrides

This is the TRUST layer that makes autonomous agents safe.
"""

import os
import json
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, field, asdict

log = logging.getLogger("permission_model")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), ".jarvis_permissions.json")


@dataclass
class PermissionPolicy:
    """Defines approval requirements for an action category."""
    auto_approve: bool = False
    require_approval: bool = True
    hold_to_approve: bool = False
    hold_duration_s: float = 1.5
    max_risk_level: str = "medium"
    description: str = ""


@dataclass
class PermissionConfig:
    """Global permission configuration."""
    autonomy_level: int = 75
    policies: Dict[str, PermissionPolicy] = field(default_factory=dict)
    blocked_actions: Set[str] = field(default_factory=set)
    always_require_approval: Set[str] = field(default_factory=set)
    never_require_approval: Set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "autonomy_level": self.autonomy_level,
            "policies": {k: asdict(v) for k, v in self.policies.items()},
            "blocked_actions": list(self.blocked_actions),
            "always_require_approval": list(self.always_require_approval),
            "never_require_approval": list(self.never_require_approval),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PermissionConfig":
        policies = {}
        for k, v in data.get("policies", {}).items():
            policies[k] = PermissionPolicy(**v)
        return cls(
            autonomy_level=data.get("autonomy_level", 75),
            policies=policies,
            blocked_actions=set(data.get("blocked_actions", [])),
            always_require_approval=set(data.get("always_require_approval", [])),
            never_require_approval=set(data.get("never_require_approval", [])),
        )


# Default policies aligned with vision doc Section 15
DEFAULT_POLICIES = {
    "financial": PermissionPolicy(
        auto_approve=False,
        require_approval=True,
        hold_to_approve=True,
        hold_duration_s=2.0,
        max_risk_level="high",
        description="Financial transactions, payments, purchases",
    ),
    "communication": PermissionPolicy(
        auto_approve=False,
        require_approval=True,
        hold_to_approve=True,
        hold_duration_s=1.5,
        max_risk_level="medium",
        description="External communication, emails, messages",
    ),
    "destructive": PermissionPolicy(
        auto_approve=False,
        require_approval=True,
        hold_to_approve=True,
        hold_duration_s=2.0,
        max_risk_level="critical",
        description="Data deletion, file removal, account changes",
    ),
    "publishing": PermissionPolicy(
        auto_approve=False,
        require_approval=True,
        hold_to_approve=False,
        max_risk_level="high",
        description="Public publishing, social media, deployment",
    ),
    "infrastructure": PermissionPolicy(
        auto_approve=False,
        require_approval=True,
        hold_to_approve=True,
        hold_duration_s=2.0,
        max_risk_level="critical",
        description="System changes, credential modifications, security",
    ),
    "code_execution": PermissionPolicy(
        auto_approve=True,
        require_approval=False,
        max_risk_level="medium",
        description="Running code, scripts, commands in sandbox",
    ),
    "browser": PermissionPolicy(
        auto_approve=True,
        require_approval=False,
        max_risk_level="low",
        description="Web browsing, searches, navigation",
    ),
    "file_read": PermissionPolicy(
        auto_approve=True,
        require_approval=False,
        max_risk_level="low",
        description="Reading files, viewing content",
    ),
    "file_write": PermissionPolicy(
        auto_approve=True,
        require_approval=True,
        max_risk_level="medium",
        description="Creating or modifying files",
    ),
    "research": PermissionPolicy(
        auto_approve=True,
        require_approval=False,
        max_risk_level="low",
        description="Web searches, data gathering, analysis",
    ),
}

# Action-to-category mapping
ACTION_CATEGORIES = {
    "launch_app": "browser",
    "click": "browser",
    "type_text": "browser",
    "press_key": "browser",
    "navigate_web": "browser",
    "web_search": "research",
    "web_scrape": "research",
    "read_file": "file_read",
    "write_file": "file_write",
    "create_directory": "file_write",
    "run_command": "code_execution",
    "run_python": "code_execution",
    "screenshot": "browser",
    "wait": "browser",
    "send_email": "communication",
    "send_message": "communication",
    "post_social": "publishing",
    "deploy": "publishing",
    "delete_file": "destructive",
    "delete_directory": "destructive",
    "financial_transfer": "financial",
    "purchase": "financial",
    "subscribe": "financial",
    "modify_credentials": "infrastructure",
    "system_config": "infrastructure",
}

# Risk level ordering
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class PermissionManager:
    """Manages approval gates and permission policies."""

    def __init__(self):
        self._config = self._load_config()

    def _load_config(self) -> PermissionConfig:
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                return PermissionConfig.from_dict(data)
        except Exception as e:
            log.warning(f"[PERM] Failed to load config: {e}")

        config = PermissionConfig(policies=DEFAULT_POLICIES.copy())
        self._save_config(config)
        return config

    def _save_config(self, config: PermissionConfig = None):
        if config is None:
            config = self._config
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump(config.to_dict(), f, indent=2)
        except Exception as e:
            log.error(f"[PERM] Failed to save config: {e}")

    def get_config(self) -> PermissionConfig:
        return self._config

    def set_autonomy_level(self, level: int):
        self._config.autonomy_level = max(0, min(100, level))
        self._save_config()
        log.info(f"[PERM] Autonomy level set to {self._config.autonomy_level}%")

    def requires_approval(self, action: str, params: dict = None, risk_level: str = "low") -> dict:
        """Check if an action requires human approval.

        Returns dict with:
            - required: bool
            - reason: str
            - hold_to_approve: bool
            - hold_duration_s: float
            - category: str
        """
        config = self._config

        # Check if action is blocked entirely
        if action in config.blocked_actions:
            return {
                "required": True,
                "reason": f"Action '{action}' is blocked by policy",
                "hold_to_approve": False,
                "hold_duration_s": 0,
                "category": "blocked",
            }

        # Check if action never requires approval
        if action in config.never_require_approval:
            return {
                "required": False,
                "reason": "Exempt by policy",
                "hold_to_approve": False,
                "hold_duration_s": 0,
                "category": "exempt",
            }

        # Check if action always requires approval
        if action in config.always_require_approval:
            return {
                "required": True,
                "reason": "Always requires approval",
                "hold_to_approve": True,
                "hold_duration_s": 2.0,
                "category": "always",
            }

        # Get category and policy
        category = ACTION_CATEGORIES.get(action, "code_execution")
        policy = config.policies.get(category, PermissionPolicy())

        # Check risk level against policy
        action_risk = RISK_ORDER.get(risk_level, 0)
        max_risk = RISK_ORDER.get(policy.max_risk_level, 1)

        # Autonomy level affects approval requirements
        # High autonomy = fewer approvals needed
        # Low autonomy = more approvals needed
        autonomy = config.autonomy_level

        if policy.auto_approve and autonomy >= 75 and action_risk <= max_risk:
            return {
                "required": False,
                "reason": f"Auto-approved (autonomy={autonomy}%, risk={risk_level})",
                "hold_to_approve": False,
                "hold_duration_s": 0,
                "category": category,
            }

        if policy.require_approval and (action_risk > max_risk or autonomy < 50):
            return {
                "required": True,
                "reason": f"Requires approval (risk={risk_level}, autonomy={autonomy}%)",
                "hold_to_approve": policy.hold_to_approve,
                "hold_duration_s": policy.hold_duration_s,
                "category": category,
            }

        # Default: no approval needed
        return {
            "required": False,
            "reason": "Standard action",
            "hold_to_approve": False,
            "hold_duration_s": 0,
            "category": category,
        }

    def update_policy(self, category: str, policy: PermissionPolicy):
        self._config.policies[category] = policy
        self._save_config()
        log.info(f"[PERM] Updated policy for '{category}'")

    def block_action(self, action: str):
        self._config.blocked_actions.add(action)
        self._save_config()

    def unblock_action(self, action: str):
        self._config.blocked_actions.discard(action)
        self._save_config()

    def require_approval_for(self, action: str):
        self._config.always_require_approval.add(action)
        self._config.never_require_approval.discard(action)
        self._save_config()

    def exempt_from_approval(self, action: str):
        self._config.never_require_approval.add(action)
        self._config.always_require_approval.discard(action)
        self._save_config()


_manager = None

def get_permission_manager() -> PermissionManager:
    global _manager
    if _manager is None:
        _manager = PermissionManager()
    return _manager
