"""
JARVIS Security Isolation Vault & Execution Guardrails
=====================================================
Production-grade script inspection with pattern-based detection,
AST analysis, and defense-in-depth validation.
"""

import re
import ast
import os
from typing import Dict, Any, List, Set
from dataclasses import dataclass, field


@dataclass
class SecurityViolation:
    """A detected security violation."""
    severity: str  # critical, high, medium, low
    category: str
    description: str
    line: int = 0
    pattern: str = ""


class SecurityVault:
    def __init__(self):
        self.whitelisted_domains = self._load_domains()
        self.blocked_keywords = self._load_blocked_keywords()
        self.blocked_processes = {
            "lsass.exe", "csrss.exe", "smss.exe", "wininit.exe",
            "services.exe", "svchost.exe", "winlogon.exe", "system",
            "kernel", "init", "launchd", "systemd", "kthreadd",
        }
        self.blocked_paths = {
            "/etc/shadow", "/etc/passwd", "/boot", "/sys", "/proc",
            "C:\\Windows\\System32\\config\\SAM",
            "C:\\Windows\\System32\\config\\SYSTEM",
        }

    def _load_domains(self) -> Set[str]:
        """Load domain whitelist from env or use defaults."""
        custom = os.getenv("JARVIS_ALLOWED_DOMAINS", "")
        defaults = {
            "localhost", "127.0.0.1", "huggingface.co", "github.com",
            "groq.com", "google.com", "duckduckgo.com", "python.org",
            "pypi.org", "npmjs.com", "cdn.jsdelivr.net",
        }
        if custom:
            defaults.update(d.strip() for d in custom.split(",") if d.strip())
        return defaults

    def _load_blocked_keywords(self) -> List[str]:
        """Load blocked patterns from env or use defaults."""
        return [
            # Destructive filesystem operations
            r"rm\s+-rf\s+/", r"rmdir\s+/\w", r"shred\s+",
            r"mkfs\.", r"format\s+[cC]:", r"fdisk",
            # Database destruction
            r"DROP\s+DATABASE", r"DELETE\s+FROM.*WHERE\s+1\s*=\s*1",
            r"TRUNCATE\s+TABLE", r"DROP\s+TABLE",
            # Code injection / arbitrary execution
            r"eval\s*\(", r"exec\s*\(", r"subprocess\.call\s*\(",
            r"os\.system\s*\(", r"__import__\s*\(",
            r"compile\s*\(", r"execfile\s*\(",
            # Privilege escalation
            r"chmod\s+[0-7]*777", r"chown\s+root",
            r"sudo\s+", r"su\s+-", r"runas\s+",
            # Network exfiltration
            r"curl\s+.*\|\s*sh", r"wget\s+.*\|\s*sh",
            r"nc\s+-", r"ncat\s+",
            # Encryption / ransomware patterns
            r"\.onion", r"tor\s+",
            # Process manipulation
            r"kill\s+-9\s+1", r"taskkill\s+/f\s+/pid\s+0",
            # System info disclosure
            r"cat\s+/etc/shadow", r"type\s+C:\\Windows\\System32\\config\\SAM",
        ]

    def _check_ast(self, script_body: str, runtime: str) -> List[SecurityViolation]:
        """AST-based analysis for Python scripts."""
        violations = []
        if runtime != "python":
            return violations

        try:
            tree = ast.parse(script_body)
        except SyntaxError:
            return violations

        dangerous_calls = {
            "eval", "exec", "compile", "__import__",
            "getattr", "setattr", "delattr",
            "globals", "locals", "vars",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in dangerous_calls:
                    violations.append(SecurityViolation(
                        severity="high",
                        category="code_injection",
                        description=f"Dangerous function call: {func_name}()",
                        line=getattr(node, "lineno", 0),
                        pattern=func_name,
                    ))

                # Check for subprocess with shell=True
                if func_name in ("subprocess.call", "subprocess.run", "subprocess.Popen"):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            violations.append(SecurityViolation(
                                severity="critical",
                                category="shell_injection",
                                description="subprocess with shell=True",
                                line=getattr(node, "lineno", 0),
                            ))

            # Check for import of dangerous modules
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = ""
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                elif isinstance(node, ast.ImportFrom):
                    module = (node.module or "").split(".")[0]

                dangerous_modules = {
                    "subprocess", "os", "shutil", "sys",
                    "socket", "ctypes", "signal",
                }
                if module in dangerous_modules:
                    violations.append(SecurityViolation(
                        severity="medium",
                        category="dangerous_import",
                        description=f"Import of restricted module: {module}",
                        line=getattr(node, "lineno", 0),
                        pattern=module,
                    ))

        return violations

    def inspect_script(self, script_body: str, runtime: str) -> Dict[str, Any]:
        """
        Inspects python/powershell/bash scripts for malicious execution patterns.
        Returns detailed violation report.
        """
        if not script_body:
            return {"safe": True, "error": None, "violations": []}

        violations: List[SecurityViolation] = []

        # 1. Regex pattern matching
        for pattern in self.blocked_keywords:
            matches = re.finditer(pattern, script_body, re.IGNORECASE)
            for match in matches:
                line_num = script_body[:match.start()].count("\n") + 1
                violations.append(SecurityViolation(
                    severity="high",
                    category="blocked_pattern",
                    description=f"Blocked pattern detected: {match.group()[:50]}",
                    line=line_num,
                    pattern=pattern,
                ))

        # 2. IP address check
        ip_patterns = re.findall(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", script_body)
        for ip in ip_patterns:
            if ip not in ("127.0.0.1", "0.0.0.0", "255.255.255.255"):
                violations.append(SecurityViolation(
                    severity="medium",
                    category="network_access",
                    description=f"Direct IP connection to '{ip}'",
                    pattern=ip,
                ))

        # 3. URL domain check
        urls = re.findall(r'https?://([a-zA-Z0-9.-]+)', script_body)
        for domain in urls:
            is_allowed = any(allowed in domain for allowed in self.whitelisted_domains)
            if not is_allowed:
                violations.append(SecurityViolation(
                    severity="high",
                    category="unauthorized_domain",
                    description=f"Domain '{domain}' is not whitelisted",
                    pattern=domain,
                ))

        # 4. Path traversal check
        for blocked_path in self.blocked_paths:
            if blocked_path.lower() in script_body.lower():
                violations.append(SecurityViolation(
                    severity="critical",
                    category="system_access",
                    description=f"Access to critical system path: {blocked_path}",
                    pattern=blocked_path,
                ))

        # 5. AST analysis (Python only)
        if runtime == "python":
            violations.extend(self._check_ast(script_body, runtime))

        # Determine overall safety
        critical = [v for v in violations if v.severity == "critical"]
        high = [v for v in violations if v.severity == "high"]

        if critical:
            return {
                "safe": False,
                "error": f"CRITICAL: {len(critical)} critical security violations detected",
                "violations": [vars(v) for v in violations],
                "risk_level": "critical",
            }
        elif high:
            return {
                "safe": False,
                "error": f"HIGH: {len(high)} high-severity violations detected",
                "violations": [vars(v) for v in violations],
                "risk_level": "high",
            }

        return {
            "safe": True,
            "error": None,
            "violations": [vars(v) for v in violations] if violations else [],
            "risk_level": "low" if not violations else "medium",
        }

    def inspect_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Inspects multi-agent output payloads for system boundaries."""
        os_payload = payload.get("os_action_payload", {})
        if os_payload:
            action_type = os_payload.get("action_type")
            if action_type == "PROCESS_KILL":
                target = os_payload.get("target_identifier", "").lower()
                if target in self.blocked_processes:
                    return {
                        "safe": False,
                        "error": f"Blocked attempt to kill critical system process: {target}",
                        "risk_level": "critical",
                    }

            script_body = os_payload.get("payload_data", {}).get("script_body")
            runtime = os_payload.get("script_runtime", "python")
            if script_body:
                return self.inspect_script(script_body, runtime)

        web_payload = payload.get("web_action_payload", {})
        if web_payload:
            for step in web_payload.get("steps", []):
                endpoint = step.get("api_endpoint", "")
                if endpoint:
                    domain_match = re.search(r'https?://([a-zA-Z0-9.-]+)', endpoint)
                    if domain_match:
                        domain = domain_match.group(1)
                        if not any(allowed in domain for allowed in self.whitelisted_domains):
                            return {
                                "safe": False,
                                "error": f"Web API target '{domain}' is not whitelisted",
                                "risk_level": "high",
                            }

        return {"safe": True, "error": None, "violations": [], "risk_level": "low"}

    def get_stats(self) -> Dict[str, Any]:
        """Get vault configuration stats."""
        return {
            "whitelisted_domains": len(self.whitelisted_domains),
            "blocked_patterns": len(self.blocked_keywords),
            "blocked_processes": len(self.blocked_processes),
            "blocked_paths": len(self.blocked_paths),
        }


# Global singleton
vault = SecurityVault()


def get_vault() -> SecurityVault:
    return vault
