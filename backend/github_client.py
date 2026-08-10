"""
GitHub Client — Native GitHub API integration.

Supports: repos, commits, PRs, issues, code search, branches.
Uses GitHub REST API v3 via requests.
"""

import os
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

log = logging.getLogger("jarvis-github")

_API = "https://api.github.com"


class GitHubClient:
    """Native GitHub REST API client."""

    def __init__(self, token: str = None):
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "JARVIS-Bot/1.0",
        }
        if self._token:
            self._headers["Authorization"] = f"token {self._token}"

    def _request(self, method: str, path: str, data: Dict = None) -> Dict:
        url = f"{_API}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=self._headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            log.error(f"GitHub API {method} {path}: {e.code} {body[:200]}")
            return {"error": e.code, "message": body[:500]}
        except Exception as e:
            return {"error": str(e)}

    def is_authenticated(self) -> bool:
        if not self._token:
            return False
        r = self._request("GET", "/user")
        return "login" in r

    def get_user(self, username: str = "") -> Dict:
        path = f"/users/{username}" if username else "/user"
        return self._request("GET", path)

    def list_repos(self, user: str = "", per_page: int = 30) -> List[Dict]:
        path = f"/users/{user}/repos" if user else "/user/repos"
        return self._request("GET", f"{path}?per_page={per_page}&sort=updated")

    def get_repo(self, owner: str, repo: str) -> Dict:
        return self._request("GET", f"/repos/{owner}/{repo}")

    def list_branches(self, owner: str, repo: str) -> List[Dict]:
        return self._request("GET", f"/repos/{owner}/{repo}/branches")

    def get_branch(self, owner: str, repo: str, branch: str) -> Dict:
        return self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")

    def create_branch(self, owner: str, repo: str, from_branch: str, new_branch: str) -> Dict:
        # Get SHA of from_branch
        ref = self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}")
        if "sha" not in ref:
            return ref
        return self._request("POST", f"/repos/{owner}/{repo}/git/refs", {
            "ref": f"refs/heads/{new_branch}",
            "sha": ref["sha"],
        })

    def list_commits(self, owner: str, repo: str, branch: str = None, per_page: int = 20) -> List[Dict]:
        params = f"?per_page={per_page}"
        if branch:
            params += f"&sha={branch}"
        return self._request("GET", f"/repos/{owner}/{repo}/commits{params}")

    def get_commit(self, owner: str, repo: str, sha: str) -> Dict:
        return self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}")

    def get_file(self, owner: str, repo: str, path: str, ref: str = None) -> Dict:
        params = f"?ref={ref}" if ref else ""
        return self._request("GET", f"/repos/{owner}/{repo}/contents/{path}{params}")

    def list_files(self, owner: str, repo: str, path: str = "", ref: str = None) -> List[Dict]:
        params = f"?ref={ref}" if ref else ""
        result = self._request("GET", f"/repos/{owner}/{repo}/contents/{path}{params}")
        if isinstance(result, list):
            return result
        return []

    def search_code(self, query: str, owner: str = None, repo: str = None) -> Dict:
        q = query
        if owner and repo:
            q += f" repo:{owner}/{repo}"
        return self._request("GET", f"/search/code?q={urllib.parse.quote(q)}&per_page=10")

    def create_issue(self, owner: str, repo: str, title: str, body: str = "",
                     labels: List[str] = None) -> Dict:
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        return self._request("POST", f"/repos/{owner}/{repo}/issues", data)

    def create_pull_request(self, owner: str, repo: str, title: str, head: str,
                           base: str, body: str = "") -> Dict:
        return self._request("POST", f"/repos/{owner}/{repo}/pulls", {
            "title": title, "head": head, "base": base, "body": body,
        })

    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> List[Dict]:
        return self._request("GET", f"/repos/{owner}/{repo}/pulls?state={state}")

    def merge_pull_request(self, owner: str, repo: str, pr_number: int,
                          commit_title: str = "") -> Dict:
        data = {}
        if commit_title:
            data["commit_title"] = commit_title
        return self._request("PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", data)

    def create_comment(self, owner: str, repo: str, issue_number: int, body: str) -> Dict:
        return self._request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {
            "body": body,
        })

    def list_workflow_runs(self, owner: str, repo: str, per_page: int = 10) -> Dict:
        return self._request("GET", f"/repos/{owner}/{repo}/actions/runs?per_page={per_page}")

    def get_vulnerability_alerts(self, owner: str, repo: str) -> Dict:
        return self._request("GET", f"/repos/{owner}/{repo}/vulnerability-alerts")


_client = None

def get_github(token: str = None) -> GitHubClient:
    global _client
    if _client is None:
        _client = GitHubClient(token)
    return _client
