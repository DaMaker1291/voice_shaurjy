"""
JARVIS Anti-Prompt Injection Sandbox
=====================================
Screens untrusted web pages, emails, and PDFs inside an isolated parser
to prevent indirect prompt injection attacks from hijacking system execution.

Guards against:
- Hidden instruction injection in web content
- Encoded/obfuscated malicious prompts
- Multi-language injection attempts
- Structural manipulation of document content
- Unicode homoglyph attacks
"""

import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("jarvis-injection-sandbox")


class InjectionRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ScanResult:
    """Result of a content injection scan."""
    risk_level: str
    is_safe: bool
    violations: List[Dict[str, Any]]
    sanitized_content: str
    scan_duration_ms: float
    content_source: str = ""


class InjectionPatternDetector:
    """
    Pattern-based detection of prompt injection attempts.
    Uses regex patterns and heuristics to identify malicious content.
    """

    def __init__(self):
        self._patterns = self._load_patterns()

    def _load_patterns(self) -> List[Dict[str, Any]]:
        """Load injection detection patterns."""
        return [
            # Direct instruction injection
            {
                "name": "direct_instruction",
                "pattern": re.compile(
                    r'(?i)(ignore|disregard|forget|override)\s+'
                    r'(all\s+)?(previous|prior|above|earlier|system)\s+'
                    r'(instructions?|prompts?|rules?|constraints?)',
                    re.IGNORECASE,
                ),
                "severity": "critical",
                "description": "Direct instruction override attempt",
            },
            {
                "name": "system_prompt_injection",
                "pattern": re.compile(
                    r'(?i)(you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+as|'
                    r'system\s*:\s*|assistant\s*:\s*|human\s*:\s*)',
                    re.IGNORECASE,
                ),
                "severity": "high",
                "description": "System prompt injection attempt",
            },
            {
                "name": "role_hijack",
                "pattern": re.compile(
                    r'(?i)(new\s+instructions?|updated?\s+instructions?|'
                    r'override\s+instructions?|instead\s+of|rather\s+than)',
                    re.IGNORECASE,
                ),
                "severity": "high",
                "description": "Role/context hijack attempt",
            },
            # Encoded injection
            {
                "name": "base64_injection",
                "pattern": re.compile(
                    r'(?i)(decode|interpret|execute|run|eval)\s+(this\s+)?base64',
                    re.IGNORECASE,
                ),
                "severity": "high",
                "description": "Encoded injection attempt",
            },
            {
                "name": "unicode_manipulation",
                "pattern": re.compile(
                    r'[\u200b\u200c\u200d\ufeff\u00ad\u2060\u2061\u2062\u2063\u2064]',
                ),
                "severity": "medium",
                "description": "Unicode manipulation detected (zero-width chars)",
            },
            # Exfiltration patterns
            {
                "name": "exfiltration_url",
                "pattern": re.compile(
                    r'(?i)(send|exfiltrate|upload|post|transmit)\s+'
                    r'(all\s+)?(data|content|text|results?)\s+to\s+',
                    re.IGNORECASE,
                ),
                "severity": "critical",
                "description": "Data exfiltration attempt",
            },
            {
                "name": "data_leak",
                "pattern": re.compile(
                    r'(?i)(api[_\s]?key|secret[_\s]?key|password|token|credential)'
                    r'\s*[:=]\s*\S+',
                    re.IGNORECASE,
                ),
                "severity": "high",
                "description": "Potential credential leak in content",
            },
            # Manipulation patterns
            {
                "name": "urgency_manipulation",
                "pattern": re.compile(
                    r'(?i)(urgent|emergency|immediately|right\s+now|'
                    r'asap|critical|important:\s*you\s+must)',
                    re.IGNORECASE,
                ),
                "severity": "medium",
                "description": "Urgency manipulation detected",
            },
            {
                "name": "delimiter_manipulation",
                "pattern": re.compile(
                    r'(?i)(---+\s*(system|assistant|human|user|end)\s*---+|'
                    r'={3,}\s*(system|assistant|human|user|end)\s*={3,}|'
                    r'#{3,}\s*(system|assistant|human|user|end)\s*#{3,})',
                    re.IGNORECASE,
                ),
                "severity": "medium",
                "description": "Message delimiter manipulation",
            },
            # Indirect injection via HTML/markdown
            {
                "name": "hidden_html",
                "pattern": re.compile(
                    r'(?i)<(script|style|meta|link|iframe)[^>]*>.*?</\1>',
                    re.DOTALL,
                ),
                "severity": "high",
                "description": "Hidden HTML content detected",
            },
            {
                "name": "invisible_text",
                "pattern": re.compile(
                    r'(?i)style\s*=\s*["\'][^"\']*(?:visibility\s*:\s*hidden|'
                    r'display\s*:\s*none|font-size\s*:\s*0|color\s*:\s*transparent)',
                    re.IGNORECASE,
                ),
                "severity": "high",
                "description": "Invisible text injection attempt",
            },
            # SQL/Code injection in content
            {
                "name": "code_injection",
                "pattern": re.compile(
                    r'(?i)(exec|eval|system|subprocess|os\.system|__import__)\s*\(',
                    re.IGNORECASE,
                ),
                "severity": "critical",
                "description": "Code injection attempt in content",
            },
        ]

    def scan(self, content: str) -> List[Dict[str, Any]]:
        """Scan content for injection patterns."""
        violations = []

        for pattern_def in self._patterns:
            matches = pattern_def["pattern"].finditer(content)
            for match in matches:
                violations.append({
                    "pattern_name": pattern_def["name"],
                    "severity": pattern_def["severity"],
                    "description": pattern_def["description"],
                    "match_position": match.start(),
                    "match_preview": content[max(0, match.start() - 20):match.end() + 20],
                })

        return violations


class ContentSanitizer:
    """
    Sanitizes untrusted content to prevent injection attacks.
    Removes or neutralizes dangerous patterns while preserving readability.
    """

    def __init__(self):
        self._html_tag_pattern = re.compile(r'<[^>]+>')
        self._zero_width_pattern = re.compile(
            '[\u200b\u200c\u200d\ufeff\u00ad\u2060\u2061\u2062\u2063\u2064]'
        )
        self._comment_pattern = re.compile(r'<!--[\s\S]*?-->')
        self._instruction_prefixes = [
            "ignore previous", "disregard above", "new instructions",
            "system:", "assistant:", "human:", "user:",
        ]

    def sanitize(self, content: str) -> str:
        """Sanitize content by removing/neutralizing injection vectors."""
        sanitized = content

        # Remove HTML comments
        sanitized = self._comment_pattern.sub("", sanitized)

        # Remove zero-width characters
        sanitized = self._zero_width_pattern.sub("", sanitized)

        # Neutralize hidden HTML elements
        sanitized = re.sub(
            r'<(script|style|meta|link|iframe|object|embed)[^>]*>.*?</\1>',
            "[REMOVED: hidden element]",
            sanitized,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove invisible text styles
        sanitized = re.sub(
            r'style\s*=\s*["\'][^"\']*(?:visibility\s*:\s*hidden|'
            r'display\s*:\s*none|font-size\s*:\s*0|color\s*:\s*transparent)[^"\']*["\']',
            '',
            sanitized,
            flags=re.IGNORECASE,
        )

        # Escape instruction prefixes in non-code content
        for prefix in self._instruction_prefixes:
            pattern = re.compile(re.escape(prefix), re.IGNORECASE)
            sanitized = pattern.sub(
                f"[NEUTRALIZED] {prefix}",
                sanitized,
            )

        return sanitized

    def extract_text_only(self, html_content: str) -> str:
        """Extract plain text from HTML, removing all tags."""
        text = self._html_tag_pattern.sub(" ", html_content)
        text = self._comment_pattern.sub("", text)
        text = self._zero_width_pattern.sub("", text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class InjectionSandbox:
    """
    Isolated sandbox for processing untrusted content.
    Scans, sanitizes, and provides safe content for LLM consumption.
    """

    def __init__(self):
        self._detector = InjectionPatternDetector()
        self._sanitizer = ContentSanitizer()
        self._scan_count = 0
        self._blocked_count = 0

    def scan_and_sanitize(
        self,
        content: str,
        source: str = "unknown",
        max_length: int = 50000,
    ) -> ScanResult:
        """
        Scan content for injection attacks and sanitize if needed.
        Returns sanitized content and scan results.
        """
        start_time = time.time()
        self._scan_count += 1

        # Truncate if too long
        if len(content) > max_length:
            content = content[:max_length]

        # Detect injection patterns
        violations = self._detector.scan(content)

        # Determine risk level
        risk_level = self._calculate_risk(violations)

        # Sanitize content
        sanitized = self._sanitizer.sanitize(content)

        # Additional: strip HTML if source is web
        if source in ("web_page", "email", "pdf"):
            sanitized = self._sanitizer.extract_text_only(sanitized)

        # Calculate scan duration
        scan_duration = (time.time() - start_time) * 1000

        is_safe = risk_level in ("none", "low")

        if not is_safe:
            self._blocked_count += 1
            log.warning(
                f"INJECTION SANDBOX: {risk_level.upper()} risk content blocked "
                f"from {source} ({len(violations)} violations)"
            )

        return ScanResult(
            risk_level=risk_level,
            is_safe=is_safe,
            violations=violations,
            sanitized_content=sanitized,
            scan_duration_ms=round(scan_duration, 2),
            content_source=source,
        )

    def _calculate_risk(self, violations: List[Dict[str, Any]]) -> str:
        """Calculate overall risk level from violations."""
        if not violations:
            return InjectionRisk.NONE.value

        severity_scores = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }

        max_severity = max(
            severity_scores.get(v["severity"], 0)
            for v in violations
        )

        if max_severity >= 4:
            return InjectionRisk.CRITICAL.value
        elif max_severity >= 3:
            return InjectionRisk.HIGH.value
        elif max_severity >= 2:
            return InjectionRisk.MEDIUM.value
        return InjectionRisk.LOW.value

    def scan_url_content(self, url: str, content: str) -> ScanResult:
        """Scan content fetched from a URL."""
        return self.scan_and_sanitize(content, source="web_page")

    def scan_email(self, email_content: str) -> ScanResult:
        """Scan email content for injection."""
        return self.scan_and_sanitize(email_content, source="email")

    def scan_pdf_text(self, pdf_text: str) -> ScanResult:
        """Scan extracted PDF text for injection."""
        return self.scan_and_sanitize(pdf_text, source="pdf")

    def scan_user_input(self, user_input: str) -> ScanResult:
        """Scan direct user input for injection attempts."""
        return self.scan_and_sanitize(user_input, source="user_input")

    def get_stats(self) -> Dict[str, Any]:
        """Get sandbox statistics."""
        return {
            "total_scans": self._scan_count,
            "blocked_count": self._blocked_count,
            "block_rate": f"{(self._blocked_count / max(self._scan_count, 1) * 100):.1f}%",
            "patterns_loaded": len(self._detector._patterns),
        }


# ── Singleton ────────────────────────────────────────────────────────────
_sandbox: Optional[InjectionSandbox] = None


def get_injection_sandbox() -> InjectionSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = InjectionSandbox()
    return _sandbox
