"""
Git Operations — Native git automation for JARVIS.

Supports: clone, branch, commit, push, pull, diff, log, status, checkout.
Runs git commands via subprocess with structured output.
"""

import os
import re
import json
import subprocess
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict

log = logging.getLogger("jarvis-git")


@dataclass
class GitResult:
    success: bool
    output: str
    error: str = ""
    data: Dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class GitOps:
    """Native git command execution."""

    def __init__(self, working_dir: str = None):
        self._dir = working_dir or os.getcwd()

    def _run(self, args: List[str], cwd: str = None) -> GitResult:
        """Run a git command and return structured result."""
        dir_used = cwd or self._dir
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=dir_used,
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            success = result.returncode == 0
            return GitResult(success=success, output=output, error=error)
        except FileNotFoundError:
            return GitResult(success=False, output="", error="git not found in PATH")
        except subprocess.TimeoutExpired:
            return GitResult(success=False, output="", error="git command timed out")
        except Exception as e:
            return GitResult(success=False, output="", error=str(e))

    def is_repo(self, path: str = None) -> bool:
        r = self._run(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return r.success and r.output == "true"

    def init(self, path: str = None) -> GitResult:
        return self._run(["init"], cwd=path)

    def clone(self, url: str, dest: str = None) -> GitResult:
        args = ["clone", url]
        if dest:
            args.append(dest)
        r = self._run(args)
        if r.success and dest:
            self._dir = dest
        return r

    def status(self) -> GitResult:
        r = self._run(["status", "--porcelain"])
        if r.success:
            files = []
            for line in r.output.splitlines():
                if len(line) >= 3:
                    status_code = line[:2].strip()
                    filepath = line[3:]
                    files.append({"status": status_code, "file": filepath})
            r.data = {"files": files, "dirty": len(files) > 0}
        return r

    def branch(self, name: str = None, checkout: bool = True) -> GitResult:
        if name:
            if checkout:
                r = self._run(["checkout", "-b", name])
            else:
                r = self._run(["branch", name])
        else:
            r = self._run(["branch", "--list"])
            if r.success:
                branches = [b.strip().replace("* ", "") for b in r.output.splitlines()]
                current = next((b for b in branches if b.startswith("*")), "")
                r.data = {"branches": branches, "current": current}
        return r

    def checkout(self, branch: str) -> GitResult:
        return self._run(["checkout", branch])

    def add(self, files: List[str] = None) -> GitResult:
        if files:
            return self._run(["add"] + files)
        return self._run(["add", "."])

    def commit(self, message: str) -> GitResult:
        return self._run(["commit", "-m", message])

    def push(self, remote: str = "origin", branch: str = None) -> GitResult:
        args = ["push", remote]
        if branch:
            args.append(branch)
        return self._run(args)

    def pull(self, remote: str = "origin", branch: str = None) -> GitResult:
        args = ["pull", remote]
        if branch:
            args.append(branch)
        return self._run(args)

    def diff(self, ref1: str = None, ref2: str = None, file: str = None) -> GitResult:
        args = ["diff"]
        if ref1 and ref2:
            args.extend([ref1, ref2])
        elif ref1:
            args.append(ref1)
        if file:
            args.extend(["--", file])
        r = self._run(args)
        if r.success:
            r.data = self._parse_diff(r.output)
        return r

    def log(self, count: int = 10, oneline: bool = True) -> GitResult:
        args = ["log", f"--max-count={count}"]
        if oneline:
            args.append("--oneline")
        r = self._run(args)
        if r.success:
            commits = []
            for line in r.output.splitlines():
                if " " in line:
                    sha, msg = line.split(" ", 1)
                    commits.append({"sha": sha, "message": msg})
            r.data = {"commits": commits}
        return r

    def blame(self, file: str) -> GitResult:
        r = self._run(["blame", "--porcelain", file])
        if r.success:
            r.data = {"raw": r.output}
        return r

    def stash(self) -> GitResult:
        return self._run(["stash"])

    def stash_pop(self) -> GitResult:
        return self._run(["stash", "pop"])

    def merge(self, branch: str) -> GitResult:
        return self._run(["merge", branch])

    def remote_add(self, name: str, url: str) -> GitResult:
        return self._run(["remote", "add", name, url])

    def show(self, ref: str) -> GitResult:
        r = self._run(["show", ref, "--stat"])
        return r

    def _parse_diff(self, diff_text: str) -> Dict:
        """Parse unified diff into structured data."""
        files = []
        current_file = None
        additions = 0
        deletions = 0

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                m = re.search(r"b/(.+)$", line)
                if m:
                    current_file = {"file": m.group(1), "hunks": [], "additions": 0, "deletions": 0}
                    files.append(current_file)
            elif line.startswith("@@"):
                m = re.search(r"@@ -(\d+),?\d* \+(\d+),?\d* @@", line)
                if m and current_file:
                    hunk = {"old_start": int(m.group(1)), "new_start": int(m.group(2)), "lines": []}
                    current_file["hunks"].append(hunk)
            elif current_file and current_file["hunks"]:
                hunk = current_file["hunks"][-1]
                if line.startswith("+"):
                    hunk["lines"].append({"type": "add", "text": line[1:]})
                    current_file["additions"] += 1
                    additions += 1
                elif line.startswith("-"):
                    hunk["lines"].append({"type": "del", "text": line[1:]})
                    current_file["deletions"] += 1
                    deletions += 1
                else:
                    hunk["lines"].append({"type": "ctx", "text": line[1:] if line.startswith(" ") else line})

        return {"files": files, "total_additions": additions, "total_deletions": deletions}


_ops = {}

def get_git(working_dir: str = None) -> GitOps:
    key = working_dir or os.getcwd()
    if key not in _ops:
        _ops[key] = GitOps(key)
    return _ops[key]
