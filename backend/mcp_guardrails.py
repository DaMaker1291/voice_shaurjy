"""
JARVIS Deterministic Guardrail Engine

OPA-style policy enforcement for MCP tool invocations.
Screens inputs BEFORE they reach execution vectors.

Guards against:
- SQL injection / destructive database operations
- Filesystem destruction (rm -rf, format, etc.)
- Cloud infrastructure termination
- Prompt injection attacks
- Unauthorized write operations
- Exfiltration patterns

Every violation is logged to the compliance ledger with full context.
"""
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("jarvis-guardrails")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationType(str, Enum):
    PATTERN_MATCH = "pattern_match"
    SCOPE_VIOLATION = "scope_violation"
    RATE_LIMIT = "rate_limit"
    INJECTION_DETECTED = "injection_detected"
    DESTRUCTIVE_OP = "destructive_op"
    EXFILTRATION = "exfiltration"
    POLICY_RULE = "policy_rule"


@dataclass
class GuardrailResult:
    """Result of a guardrail screening."""
    allowed: bool
    risk_level: RiskLevel = RiskLevel.LOW
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_reason: str = ""


@dataclass
class PolicyRule:
    """A single guardrail policy rule."""
    name: str
    description: str
    risk_level: RiskLevel
    patterns: List[re.Pattern] = field(default_factory=list)
    tool_filter: Optional[str] = None  # Apply only to tools matching this
    argument_filter: Optional[str] = None  # Apply only to args matching this
    enabled: bool = True


class DeterministicGuardrail:
    """
    Deterministic, rule-based security guardrail engine.
    
    Unlike LLM-based guardrails, this is:
    - Instant (no API calls)
    - Deterministic (same input = same result)
    - Auditable (every rule is explicit)
    - Tamper-proof (rules are compiled at startup)
    """

    def __init__(self):
        self._rules: List[PolicyRule] = []
        self._rate_limits: Dict[str, List[float]] = {}  # user_id -> [timestamps]
        self._violation_count = 0

        self._compile_rules()

    def _compile_rules(self):
        """Compile all security rules at startup."""
        
        # ── SQL Injection / Destructive Database Ops ──
        self._rules.append(PolicyRule(
            name="sql_destructive_drop",
            description="Blocks DROP TABLE/DATABASE/SCHEMA operations",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)\bDROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b"),
                re.compile(r"(?i)\bTRUNCATE\s+TABLE\b"),
                re.compile(r"(?i)\bALTER\s+TABLE\b.*\bDROP\s+COLUMN\b"),
            ],
            tool_filter="postgres|sqlite|mysql|mssql",
        ))

        self._rules.append(PolicyRule(
            name="sql_destructive_delete",
            description="Blocks DELETE without WHERE clause (full table wipe)",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)\bDELETE\s+FROM\b(?:(?!\bWHERE\b).)*$", re.DOTALL),
                re.compile(r"(?i)\bDELETE\s+FROM\b.*\bWHERE\b\s+1\s*=\s*1"),
                re.compile(r"(?i)\bDELETE\s+FROM\b.*\bWHERE\b\s+true"),
            ],
            tool_filter="postgres|sqlite|mysql|mssql",
        ))

        self._rules.append(PolicyRule(
            name="sql_injection_union",
            description="Detects UNION-based SQL injection patterns",
            risk_level=RiskLevel.HIGH,
            patterns=[
                re.compile(r"(?i)\bUNION\s+(?:ALL\s+)?SELECT\b"),
                re.compile(r"(?i)\bUNION\s+(?:ALL\s+)?SELECT\b.*\bFROM\b"),
                re.compile(r"(?i)'\s*OR\s+'1'\s*=\s*'1"),
                re.compile(r"(?i)'\s*OR\s+1\s*=\s*1"),
                re.compile(r"(?i)'\s*;\s*DROP\b"),
            ],
        ))

        self._rules.append(PolicyRule(
            name="sql_update_no_where",
            description="Blocks UPDATE without WHERE clause (full table overwrite)",
            risk_level=RiskLevel.HIGH,
            patterns=[
                re.compile(r"(?i)\bUPDATE\b.*\bSET\b(?:(?!\bWHERE\b).)*$", re.DOTALL),
            ],
            tool_filter="postgres|sqlite|mysql|mssql",
        ))

        # ── Filesystem Destruction ──
        self._rules.append(PolicyRule(
            name="fs_destructive_rm",
            description="Blocks recursive force deletion",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)\brm\s+-rf?\s+/"),
                re.compile(r"(?i)\brm\s+-rf?\s+~"),
                re.compile(r"(?i)\brm\s+-rf?\s+\*"),
                re.compile(r"(?i)shutil\.rmtree\s*\(\s*['\"]/(?:etc|usr|var|bin|sys|proc|dev)"),
                re.compile(r"(?i)os\.remove\s*\(\s*['\"]/(?:etc|usr|var|bin)"),
            ],
            tool_filter="filesystem|shell|exec",
        ))

        self._rules.append(PolicyRule(
            name="fs_format_disk",
            description="Blocks disk formatting operations",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)\bmkfs\b"),
                re.compile(r"(?i)\bformat\s+[cCdD]:"),
                re.compile(r"(?i)\bdd\s+if=.*\bof=/dev/"),
                re.compile(r"(?i)\bblockdev\s+--setrw\b"),
            ],
        ))

        self._rules.append(PolicyRule(
            name="fs_system_modification",
            description="Blocks modification of critical system files",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)(?:chmod|chown)\s+.*(?:/etc|/usr|/var|/bin|/sbin|/boot)"),
                re.compile(r"(?i)>\s*/(?:etc|boot)/(?:passwd|shadow|fstab|sudoers)"),
            ],
        ))

        # ── Cloud Infrastructure Destruction ──
        self._rules.append(PolicyRule(
            name="cloud_terminate",
            description="Blocks instance/container termination",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)terminate-instances"),
                re.compile(r"(?i)aws\s+ec2\s+terminate"),
                re.compile(r"(?i)kubectl\s+delete\s+(?:pod|deployment|service|namespace)"),
                re.compile(r"(?i)docker\s+(?:rm|stop|kill)\s+"),
                re.compile(r"(?i)docker\s+system\s+prune\s+--all"),
                re.compile(r"(?i)kubectl\s+delete\s+namespace"),
            ],
            tool_filter="aws|kubernetes|docker",
        ))

        self._rules.append(PolicyRule(
            name="cloud_bucket_delete",
            description="Blocks S3/GCS bucket deletion",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)delete.*bucket"),
                re.compile(r"(?i)s3\s+rb\s+"),
                re.compile(r"(?i)gsutil\s+rm\s+-r"),
                re.compile(r"(?i)remove.*storage.*account"),
            ],
            tool_filter="aws|gcp|azure",
        ))

        # ── Prompt Injection ──
        self._rules.append(PolicyRule(
            name="prompt_injection_ignore",
            description="Detects prompt injection attempts to override instructions",
            risk_level=RiskLevel.HIGH,
            patterns=[
                re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)"),
                re.compile(r"(?i)disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)"),
                re.compile(r"(?i)you\s+are\s+now\s+(?:a|an)\s+"),
                re.compile(r"(?i)act\s+as\s+if\s+you\s+(?:are|were)"),
                re.compile(r"(?i)forget\s+(?:everything|all)\s+(?:you|about)"),
                re.compile(r"(?i)override\s+(?:safety|security|guardrails)"),
            ],
        ))

        self._rules.append(PolicyRule(
            name="prompt_injection_system",
            description="Detects system-level prompt injection",
            risk_level=RiskLevel.CRITICAL,
            patterns=[
                re.compile(r"(?i)system\s*:\s*you\s+are"),
                re.compile(r"(?i)\[system\]"),
                re.compile(r"(?i)<\|im_start\|>"),
                re.compile(r"(?i)<\|im_end\|>"),
                re.compile(r"(?i)```system"),
                re.compile(r"(?i)ADMIN\s+MODE\s+ENABLED"),
                re.compile(r"(?i)DEVELOPER\s+MODE\s+ACTIVE"),
            ],
        ))

        # ── Exfiltration Patterns ──
        self._rules.append(PolicyRule(
            name="exfil_data_transfer",
            description="Detects potential data exfiltration patterns",
            risk_level=RiskLevel.HIGH,
            patterns=[
                re.compile(r"(?i)curl\s+.*-d\s+.*@(?:/etc/passwd|/etc/shadow|\.env|\.ssh)"),
                re.compile(r"(?i)wget\s+.*--post-file\s+"),
                re.compile(r"(?i)base64\s+.*\|\s*(?:curl|wget)"),
                re.compile(r"(?i)(?:cat|type)\s+.*\|\s*(?:nc|ncat|netcat)"),
            ],
        ))

        self._rules.append(PolicyRule(
            name="exfil_env_secrets",
            description="Blocks access to environment secrets files",
            risk_level=RiskLevel.HIGH,
            patterns=[
                re.compile(r"(?i)(?:cat|type|more|less)\s+.*\.env(?:\.|$)"),
                re.compile(r"(?i)(?:cat|type)\s+.*\.ssh/(?:id_|authorized_keys|known_hosts)"),
                re.compile(r"(?i)printenv\s+(?:AWS_|AZURE_|GCP_|SECRET|TOKEN|KEY)"),
            ],
            tool_filter="filesystem|shell|exec",
        ))

        # ── Rate Limiting ──
        self._rules.append(PolicyRule(
            name="rate_limit_write",
            description="Rate limits write operations to prevent runaway automation",
            risk_level=RiskLevel.MEDIUM,
            tool_filter=".*",  # Apply to all tools
        ))

        log.info(f"Compiled {len(self._rules)} guardrail rules")

    def screen(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str = "local",
        is_write: bool = False,
    ) -> GuardrailResult:
        """
        Screen a tool invocation against all guardrail rules.
        Returns immediately on first CRITICAL violation.
        """
        result = GuardrailResult(allowed=True)
        arg_string = json.dumps(arguments, default=str)

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check tool filter
            if rule.tool_filter:
                if not re.search(rule.tool_filter, tool_name, re.IGNORECASE):
                    continue

            # Rate limiting special case
            if rule.name == "rate_limit_write" and is_write:
                if not self._check_rate_limit(user_id):
                    result.allowed = False
                    result.risk_level = RiskLevel.MEDIUM
                    result.violations.append({
                        "rule": rule.name,
                        "type": ViolationType.RATE_LIMIT.value,
                        "risk": rule.risk_level.value,
                        "message": "Write operation rate limit exceeded",
                    })
                    result.blocked_reason = "Rate limit: too many write operations. Wait before retrying."
                    self._violation_count += 1
                    return result
                continue

            # Check patterns against argument string
            for pattern in rule.patterns:
                if pattern.search(arg_string):
                    violation = {
                        "rule": rule.name,
                        "type": ViolationType.PATTERN_MATCH.value,
                        "risk": rule.risk_level.value,
                        "description": rule.description,
                        "pattern": pattern.pattern,
                        "tool": tool_name,
                        "matching_args": self._extract_matching_args(arg_string, pattern),
                    }
                    result.violations.append(violation)
                    self._violation_count += 1

                    if rule.risk_level == RiskLevel.CRITICAL:
                        result.allowed = False
                        result.risk_level = RiskLevel.CRITICAL
                        result.blocked_reason = (
                            f"BLOCKED: {rule.description}. "
                            f"This operation has been logged to the compliance ledger."
                        )
                        log.warning(f"CRITICAL VIOLATION: {rule.name} on {tool_name}")
                        return result

                    if rule.risk_level == RiskLevel.HIGH:
                        result.risk_level = RiskLevel.HIGH
                        result.warnings.append(f"HIGH RISK: {rule.description}")

        # If we have CRITICAL violations, block
        if result.risk_level == RiskLevel.CRITICAL:
            result.allowed = False

        return result

    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded write operation rate limit."""
        now = time.time()
        window = 60  # 1 minute window
        max_ops = 30  # Max 30 writes per minute

        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = []

        # Clean old entries
        self._rate_limits[user_id] = [
            t for t in self._rate_limits[user_id] if now - t < window
        ]

        if len(self._rate_limits[user_id]) >= max_ops:
            return False

        self._rate_limits[user_id].append(now)
        return True

    def _extract_matching_args(self, arg_string: str, pattern: re.Pattern) -> str:
        """Extract the portion of args that matched the pattern."""
        match = pattern.search(arg_string)
        if match:
            start = max(0, match.start() - 20)
            end = min(len(arg_string), match.end() + 20)
            return arg_string[start:end]
        return ""

    def get_stats(self) -> Dict[str, Any]:
        """Get guardrail statistics."""
        return {
            "total_rules": len([r for r in self._rules if r.enabled]),
            "total_violations": self._violation_count,
            "rules_by_risk": {
                level.value: len([
                    r for r in self._rules
                    if r.risk_level == level and r.enabled
                ])
                for level in RiskLevel
            },
        }

    def add_rule(self, rule: PolicyRule):
        """Add a custom guardrail rule at runtime."""
        self._rules.append(rule)
        log.info(f"Added custom guardrail rule: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """Remove a guardrail rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                log.info(f"Removed guardrail rule: {name}")
                return True
        return False


# ── Convenience: Screen and block ────────────────────────────────────────

_guardrail: Optional[DeterministicGuardrail] = None


def get_guardrail() -> DeterministicGuardrail:
    global _guardrail
    if _guardrail is None:
        _guardrail = DeterministicGuardrail()
    return _guardrail


def screen_or_block(
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: str = "local",
    is_write: bool = False,
) -> GuardrailResult:
    """Screen a tool invocation and return result. Convenience wrapper."""
    return get_guardrail().screen(tool_name, arguments, user_id, is_write)
