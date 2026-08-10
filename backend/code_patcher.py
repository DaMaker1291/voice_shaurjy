"""
Code Patcher — LLM-powered code fix generation and patch application.

Analyzes errors, generates fixes using the LLM, creates patches,
and applies them to source files.
"""

import os
import re
import json
import time
import logging
import difflib
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict

log = logging.getLogger("jarvis-patcher")


@dataclass
class PatchHunk:
    file: str
    old_lines: List[str]
    new_lines: List[str]
    start_line: int = 0
    context: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Patch:
    description: str
    hunks: List[PatchHunk] = field(default_factory=list)
    test_code: str = ""
    commit_message: str = ""
    risk_level: str = "low"  # low | medium | high
    affected_files: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "description": self.description,
            "hunks": [h.to_dict() for h in self.hunks],
            "test_code": self.test_code,
            "commit_message": self.commit_message,
            "risk_level": self.risk_level,
            "affected_files": self.affected_files,
        }


class CodePatcher:
    """Generate and apply code fixes using LLM analysis."""

    def analyze_error(self, error_text: str, source_code: str = "",
                      file_path: str = "") -> Dict:
        """Analyze an error and return root cause analysis."""
        prompt = f"""Analyze this error and provide a root cause analysis.

Error:
{error_text[:3000]}

{"Source file: " + file_path if file_path else ""}
{"Source code:" + chr(10) + source_code[:5000] if source_code else ""}

Respond in JSON format:
{{
  "root_cause": "brief explanation",
  "error_type": "type of error",
  "affected_component": "which part of the code",
  "severity": "low/medium/high/critical",
  "fix_strategy": "how to fix it"
}}"""

        try:
            from groq_agent import call_groq
            response = call_groq(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
            )
            if response:
                # Extract JSON
                response = response.strip()
                if "```" in response:
                    response = re.sub(r'```\w*\n?', '', response)
                    response = re.sub(r'\n?```$', '', response)
                return json.loads(response)
        except Exception as e:
            log.debug(f"LLM analysis failed: {e}")

        # Fallback: basic pattern analysis
        return self._basic_analysis(error_text)

    def generate_fix(self, error_text: str, source_code: str,
                     file_path: str = "", context: str = "") -> Optional[Patch]:
        """Generate a code fix using LLM."""
        prompt = f"""You are a senior software engineer. Fix this bug.

Error:
{error_text[:3000]}

File: {file_path}

Source code:
```python
{source_code[:8000]}
```

{("Additional context: " + context) if context else ""}

Respond with a JSON object:
{{
  "description": "what the fix does",
  "commit_message": "git commit message",
  "risk_level": "low/medium/high",
  "hunks": [{{
    "file": "path/to/file.py",
    "old_lines": ["original line 1", "original line 2"],
    "new_lines": ["fixed line 1", "fixed line 2"],
    "start_line": 42,
    "context": "what this change does"
  }}],
  "test_code": "test function to verify the fix (optional)"
}}

IMPORTANT: old_lines must be EXACT substrings from the source code. Include enough context lines to make the match unique."""

        try:
            from groq_agent import call_groq
            response = call_groq(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000,
            )
            if response:
                response = response.strip()
                if "```" in response:
                    response = re.sub(r'```\w*\n?', '', response)
                    response = re.sub(r'\n?```$', '', response)
                data = json.loads(response)
                return self._build_patch(data)
        except Exception as e:
            log.debug(f"LLM fix generation failed: {e}")

        return None

    def apply_patch(self, patch: Patch, dry_run: bool = False) -> Dict:
        """Apply a patch to source files. Returns success status and details."""
        results = []
        all_success = True

        for hunk in patch.hunks:
            filepath = hunk.file
            if not os.path.exists(filepath):
                results.append({"file": filepath, "success": False, "error": "File not found"})
                all_success = False
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    current_content = f.read()

                old_text = "\n".join(hunk.old_lines)
                new_text = "\n".join(hunk.new_lines)

                if old_text not in current_content:
                    # Try fuzzy match
                    fuzzy = self._fuzzy_find(old_text, current_content)
                    if fuzzy:
                        old_text = fuzzy
                    else:
                        results.append({"file": filepath, "success": False,
                                        "error": "Old text not found in file"})
                        all_success = False
                        continue

                if not dry_run:
                    new_content = current_content.replace(old_text, new_text, 1)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)

                results.append({"file": filepath, "success": True, "dry_run": dry_run})
            except Exception as e:
                results.append({"file": filepath, "success": False, "error": str(e)})
                all_success = False

        return {"success": all_success, "results": results}

    def generate_diff(self, patch: Patch) -> str:
        """Generate a unified diff for the patch."""
        diffs = []
        for hunk in patch.hunks:
            old = hunk.old_lines
            new = hunk.new_lines
            diff = list(difflib.unified_diff(
                old, new,
                fromfile=f"a/{hunk.file}",
                tofile=f"b/{hunk.file}",
                lineterm="",
            ))
            diffs.extend(diff)
        return "\n".join(diffs)

    def _build_patch(self, data: Dict) -> Patch:
        hunks = []
        for h in data.get("hunks", []):
            hunks.append(PatchHunk(
                file=h.get("file", ""),
                old_lines=h.get("old_lines", []),
                new_lines=h.get("new_lines", []),
                start_line=h.get("start_line", 0),
                context=h.get("context", ""),
            ))
        return Patch(
            description=data.get("description", ""),
            hunks=hunks,
            test_code=data.get("test_code", ""),
            commit_message=data.get("commit_message", ""),
            risk_level=data.get("risk_level", "low"),
            affected_files=[h.file for h in hunks],
        )

    def _basic_analysis(self, error_text: str) -> Dict:
        if "ModuleNotFoundError" in error_text:
            m = re.search(r"No module named '(.+?)'", error_text)
            module = m.group(1) if m else "unknown"
            return {"root_cause": f"Missing module: {module}", "error_type": "import",
                    "fix_strategy": f"pip install {module}", "severity": "low"}
        if "SyntaxError" in error_text:
            return {"root_cause": "Syntax error in code", "error_type": "syntax",
                    "fix_strategy": "Fix the syntax error", "severity": "high"}
        if "TypeError" in error_text:
            return {"root_cause": "Type mismatch", "error_type": "type",
                    "fix_strategy": "Check argument types", "severity": "medium"}
        if "KeyError" in error_text:
            m = re.search(r"KeyError:\s*(.+?)(?:\n|$)", error_text)
            key = m.group(1) if m else "unknown"
            return {"root_cause": f"Missing key: {key}", "error_type": "key",
                    "fix_strategy": f"Add key '{key}' or use .get()", "severity": "medium"}
        if "IndexError" in error_text:
            return {"root_cause": "Index out of range", "error_type": "index",
                    "fix_strategy": "Check bounds before accessing", "severity": "medium"}
        if "ConnectionRefused" in error_text or "ConnectionError" in error_text:
            return {"root_cause": "Connection refused", "error_type": "connection",
                    "fix_strategy": "Check if service is running", "severity": "high"}
        return {"root_cause": "Unknown error", "error_type": "unknown",
                "fix_strategy": "Review the error details", "severity": "medium"}

    def _fuzzy_find(self, target: str, content: str) -> Optional[str]:
        """Fuzzy find target text in content."""
        target_lines = target.strip().splitlines()
        content_lines = content.splitlines()
        best_ratio = 0
        best_match = None
        for i in range(len(content_lines) - len(target_lines) + 1):
            candidate = "\n".join(content_lines[i:i + len(target_lines)])
            ratio = difflib.SequenceMatcher(None, target, candidate).ratio()
            if ratio > best_ratio and ratio > 0.7:
                best_ratio = ratio
                best_match = candidate
        return best_match


_patcher = None

def get_patcher() -> CodePatcher:
    global _patcher
    if _patcher is None:
        _patcher = CodePatcher()
    return _patcher
