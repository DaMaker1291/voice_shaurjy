"""
JARVIS Security Isolation Vault & Execution Guardrails
======================================================
Deterministic local proxy that dry-runs / intercepts scripts
to ensure absolute execution safety on host environments.
"""

import re
from typing import Dict, Any, List

# Strict whitelist of allowed network destinations and process actions
ALLOWED_DOMAINS = ["localhost", "127.0.0.1", "huggingface.co", "github.com", "groq.com", "google.com"]
BLOCKED_KEYWORDS = [
    "rm -rf /", "shred ", "mkfs", "/dev/sd", "drop database", "eval(", 
    "exec(", "subprocess.call", "os.system('rm", "os.system(\"rm"
]

class SecurityVault:
    def __init__(self):
        self.whitelisted_domains = ALLOWED_DOMAINS
        self.blocked_keywords = BLOCKED_KEYWORDS

    def inspect_script(self, script_body: str, runtime: str) -> Dict[str, Any]:
        """
        Inspects python/powershell/bash scripts for malicious execution patterns.
        """
        if not script_body:
            return {"safe": True, "error": None}

        # Check for blocked keywords
        for keyword in self.blocked_keywords:
            if keyword in script_body:
                return {
                    "safe": False,
                    "error": f"Security violation: Blocked dangerous keyword '{keyword}' detected."
                }

        # Check for potential outbound IP connections in script
        ip_patterns = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", script_body)
        for ip in ip_patterns:
            if ip not in ["127.0.0.1", "0.0.0.0"]:
                return {
                    "safe": False,
                    "error": f"Security violation: Direct IP connection to '{ip}' is blocked."
                }

        # URL extraction check
        urls = re.findall(r'https?://([a-zA-Z0-9.-]+)', script_body)
        for domain in urls:
            is_allowed = any(allowed in domain for allowed in self.whitelisted_domains)
            if not is_allowed:
                return {
                    "safe": False,
                    "error": f"Security violation: Domain '{domain}' is not whitelisted."
                }

        return {"safe": True, "error": None}

    def inspect_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inspects generic multi-agent output payloads for system boundaries.
        """
        os_payload = payload.get("os_action_payload", {})
        if os_payload:
            action_type = os_payload.get("action_type")
            # Limit dangerous actions
            if action_type == "PROCESS_KILL" and os_payload.get("target_identifier") in ["lsass.exe", "kernel", "system"]:
                return {
                    "safe": False,
                    "error": "Security violation: Blocked attempt to kill critical system processes."
                }

            script_body = os_payload.get("payload_data", {}).get("script_body")
            runtime = os_payload.get("script_runtime", "python")
            return self.inspect_script(script_body, runtime)

        web_payload = payload.get("web_action_payload", {})
        if web_payload:
            for step in web_payload.get("steps", []):
                endpoint = step.get("api_endpoint")
                if endpoint:
                    # check url whitelists
                    domain_match = re.search(r'https?://([a-zA-Z0-9.-]+)', endpoint)
                    if domain_match:
                        domain = domain_match.group(1)
                        if not any(allowed in domain for allowed in self.whitelisted_domains):
                            return {
                                "safe": False,
                                "error": f"Security violation: Web API target '{domain}' is not whitelisted."
                            }

        return {"safe": True, "error": None}

# Global singleton
vault = SecurityVault()
