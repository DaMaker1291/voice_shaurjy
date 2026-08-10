"""
Security Scanner — CVE/vulnerability detection for dependencies and code.

Scans Python requirements, package.json, Docker images, and source code
for known vulnerabilities using public databases.
"""

import os
import re
import json
import logging
import subprocess
from typing import Dict, List, Optional
from pathlib import Path

log = logging.getLogger("jarvis-security")


class SecurityScanner:
    """Scan for vulnerabilities in dependencies and code."""

    def scan_python_deps(self, requirements_path: str = None) -> Dict:
        """Scan Python dependencies for known CVEs using pip-audit or safety."""
        if requirements_path is None:
            requirements_path = self._find_requirements()

        if not requirements_path or not os.path.exists(requirements_path):
            return {"error": "No requirements.txt found"}

        # Try pip-audit first
        try:
            r = subprocess.run(
                ["pip-audit", "-r", requirements_path, "--format", "json"],
                capture_output=True, text=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if r.returncode >= 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                vulns = []
                for v in data.get("dependencies", []):
                    for vuln in v.get("vulns", []):
                        vulns.append({
                            "package": v.get("name", ""),
                            "version": v.get("version", ""),
                            "vulnerability": vuln.get("id", ""),
                            "description": vuln.get("description", ""),
                            "fix_versions": vuln.get("fix_versions", []),
                        })
                return {"vulnerabilities": vulns, "total": len(vulns), "tool": "pip-audit"}
        except FileNotFoundError:
            pass

        # Try safety check
        try:
            r = subprocess.run(
                ["safety", "check", "-r", requirements_path, "--output", "json"],
                capture_output=True, text=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if r.stdout.strip():
                data = json.loads(r.stdout)
                vulns = []
                for v in data:
                    vulns.append({
                        "package": v.get("package", ""),
                        "version": v.get("installed_version", ""),
                        "vulnerability": v.get("vulnerability_id", ""),
                        "description": v.get("description", ""),
                        "fix_versions": [v.get("fixed_version", "")],
                    })
                return {"vulnerabilities": vulns, "total": len(vulns), "tool": "safety"}
        except FileNotFoundError:
            pass

        # Fallback: check for outdated packages with known issues
        return self._check_outdated(requirements_path)

    def scan_code_patterns(self, directory: str) -> Dict:
        """Scan source code for security anti-patterns."""
        patterns = [
            (r'eval\s*\(', "CRITICAL", "eval() usage — potential code injection"),
            (r'exec\s*\(', "HIGH", "exec() usage — potential code injection"),
            (r'__import__\s*\(', "MEDIUM", "Dynamic import — potential code injection"),
            (r'os\.system\s*\(', "HIGH", "os.system() — use subprocess instead"),
            (r'subprocess\.call.*shell\s*=\s*True', "HIGH", "Shell=True — potential command injection"),
            (r'pickle\.loads?\s*\(', "MEDIUM", "Pickle deserialization — potential RCE"),
            (r'yaml\.load\s*\((?!.*Loader)', "MEDIUM", "yaml.load without Loader — potential RCE"),
            (r'SQL.*\+.*\+', "HIGH", "String concatenation in SQL — potential SQL injection"),
            (r'f["\'].*SELECT.*\{', "HIGH", "f-string SQL query — potential SQL injection"),
            (r'password\s*=\s*["\'][^"\']+["\']', "CRITICAL", "Hardcoded password"),
            (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "CRITICAL", "Hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "CRITICAL", "Hardcoded secret"),
            (r'token\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "HIGH", "Hardcoded token"),
            (r'BEGIN\s+(RSA|DSA|EC)?\s*PRIVATE\s+KEY', "CRITICAL", "Private key in source code"),
        ]

        findings = []
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            # Skip common non-source dirs
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
            for f in files:
                if not f.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".yaml", ".yml", ".env", ".cfg", ".ini", ".conf")):
                    continue
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                    files_scanned += 1
                    for pattern, severity, desc in patterns:
                        for m in re.finditer(pattern, content):
                            line_num = content[:m.start()].count("\n") + 1
                            findings.append({
                                "file": filepath,
                                "line": line_num,
                                "severity": severity,
                                "issue": desc,
                                "match": m.group(0)[:100],
                            })
                except Exception:
                    pass

        # Deduplicate
        seen = set()
        unique = []
        for f in findings:
            key = (f["file"], f["line"], f["issue"])
            if key not in seen:
                seen.add(key)
                unique.append(f)

        return {
            "findings": unique,
            "total": len(unique),
            "files_scanned": files_scanned,
            "critical": sum(1 for f in unique if f["severity"] == "CRITICAL"),
            "high": sum(1 for f in unique if f["severity"] == "HIGH"),
            "medium": sum(1 for f in unique if f["severity"] == "MEDIUM"),
        }

    def scan_docker(self, image: str) -> Dict:
        """Scan a Docker image for vulnerabilities using trivy."""
        try:
            r = subprocess.run(
                ["trivy", "image", "--format", "json", image],
                capture_output=True, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if r.stdout.strip():
                data = json.loads(r.stdout)
                vulns = []
                for result in data.get("Results", []):
                    for v in result.get("Vulnerabilities", []):
                        vulns.append({
                            "id": v.get("VulnerabilityID", ""),
                            "severity": v.get("Severity", ""),
                            "package": v.get("PkgName", ""),
                            "installed": v.get("InstalledVersion", ""),
                            "fixed": v.get("FixedVersion", ""),
                            "title": v.get("Title", ""),
                        })
                return {"vulnerabilities": vulns, "total": len(vulns), "image": image}
        except FileNotFoundError:
            return {"error": "trivy not installed"}
        except Exception as e:
            return {"error": str(e)}
        return {"vulnerabilities": [], "total": 0}

    def _find_requirements(self) -> Optional[str]:
        candidates = ["requirements.txt", "requirements-lock.txt", "requirements-dev.txt"]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _check_outdated(self, requirements_path: str) -> Dict:
        """Fallback: check for outdated packages."""
        try:
            r = subprocess.run(
                ["pip", "list", "--outdated", "--format", "json"],
                capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if r.stdout.strip():
                outdated = json.loads(r.stdout)
                return {
                    "outdated_packages": [{"name": p["name"], "current": p["version"],
                                           "latest": p["latest_version"]} for p in outdated],
                    "total": len(outdated),
                    "note": "Install pip-audit or safety for CVE scanning",
                }
        except Exception:
            pass
        return {"vulnerabilities": [], "total": 0, "note": "No scanning tool available"}


_scanner = None

def get_scanner() -> SecurityScanner:
    global _scanner
    if _scanner is None:
        _scanner = SecurityScanner()
    return _scanner
