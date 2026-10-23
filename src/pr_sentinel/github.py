"""Minimal GitHub REST client (stdlib only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")


class GitHub:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo

    def _req(self, method: str, path: str, body: Any = None, accept: str = "application/vnd.github+json", raw_text: bool = False) -> Any:
        url = path if path.startswith("http") else f"{API}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", accept)
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "pr-sentinel")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"GitHub API {method} {path} failed: {e.code} {detail}") from e
        if raw_text or accept.endswith("diff"):
            return raw
        return json.loads(raw) if raw else None

    def pull(self, number: int) -> dict:
        return self._req("GET", f"/repos/{self.repo}/pulls/{number}")

    def pull_diff(self, number: int) -> str:
        return self._req("GET", f"/repos/{self.repo}/pulls/{number}", accept="application/vnd.github.v3.diff")

    def file_text(self, path: str, ref: str | None = None) -> str | None:
        """Raw text of a file in the repo, or None if it doesn't exist."""
        q = f"?ref={urllib.request.quote(ref)}" if ref else ""
        try:
            return self._req("GET", f"/repos/{self.repo}/contents/{path}{q}", accept="application/vnd.github.raw", raw_text=True)
        except RuntimeError as e:
            if " 404 " in str(e):
                return None
            raise

    def comments(self, number: int) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            batch = self._req("GET", f"/repos/{self.repo}/issues/{number}/comments?per_page=100&page={page}")
            out.extend(batch)
            if len(batch) < 100:
                return out
            page += 1

    def upsert_comment(self, number: int, body: str, marker: str) -> str:
        """Edit our previous comment if present, otherwise create one. Returns 'created'|'updated'."""
        for c in self.comments(number):
            if marker in (c.get("body") or ""):
                self._req("PATCH", f"/repos/{self.repo}/issues/comments/{c['id']}", {"body": body})
                return "updated"
        self._req("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": body})
        return "created"

    def set_risk_label(self, number: int, label: str, prefix: str = "risk:") -> None:
        current = [lbl["name"] for lbl in self._req("GET", f"/repos/{self.repo}/issues/{number}/labels")]
        for name in current:
            if name.startswith(prefix) and name != label:
                try:
                    self._req("DELETE", f"/repos/{self.repo}/issues/{number}/labels/{urllib.request.quote(name)}")
                except RuntimeError:
                    pass
        if label not in current:
            self._req("POST", f"/repos/{self.repo}/issues/{number}/labels", {"labels": [label]})

    def pull_review_comments(self, number: int) -> list[dict]:
        """Fetch all pull request review comments (inline comments)."""
        out: list[dict] = []
        page = 1
        while True:
            batch = self._req("GET", f"/repos/{self.repo}/pulls/{number}/comments?per_page=100&page={page}")
            out.extend(batch)
            if len(batch) < 100:
                return out
            page += 1

    def create_review(
        self,
        number: int,
        commit_id: str,
        comments: list[dict],
        body: str = "",
        event: str = "COMMENT",
    ) -> dict | None:
        """Create a pull request review with inline comments."""
        if not comments:
            return None
        payload: dict[str, Any] = {
            "commit_id": commit_id,
            "event": event,
            "comments": comments,
        }
        if body:
            payload["body"] = body
        return self._req("POST", f"/repos/{self.repo}/pulls/{number}/reviews", payload)

    def create_review_comment(self, number: int, commit_id: str, path: str, line: int, body: str) -> dict:
        """Post a single review comment on a PR diff line."""
        payload = {
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": "RIGHT",
            "body": body,
        }
        return self._req("POST", f"/repos/{self.repo}/pulls/{number}/comments", payload)

    def post_inline_review(
        self,
        number: int,
        commit_id: str,
        comments: list[dict],
        summary: str = "",
    ) -> int:
        """Post inline comments via review, falling back to individual comments if needed."""
        if not comments:
            return 0
        try:
            self.create_review(number, commit_id, comments, body=summary)
            return len(comments)
        except Exception as e:
            posted = 0
            for c in comments:
                try:
                    self.create_review_comment(number, commit_id, c["path"], c["line"], c["body"])
                    posted += 1
                except Exception:
                    pass
            if posted > 0:
                return posted
            raise e
