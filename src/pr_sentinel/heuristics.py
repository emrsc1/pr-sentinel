"""Deterministic, model-free risk signals.

These run before any API call, cost nothing, and give the model (and the
maintainer) a grounded starting point. They also keep working when no API key
is configured, e.g. on PRs from forks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch

from .diff import FileDiff

SENSITIVE_PATTERNS: dict[str, str] = {
    ".github/workflows/*": "CI workflow changed (can run code with repository secrets)",
    "**/auth*": "authentication code",
    "**/*security*": "security-related code",
    "**/migrations/**": "database migration",
    "Dockerfile": "container build",
    "**/Dockerfile": "container build",
    "setup.py": "package build script",
    "pyproject.toml": "packaging / dependency config",
    "package.json": "dependency manifest",
    "**/package.json": "dependency manifest",
    "requirements*.txt": "dependency manifest",
    "go.mod": "dependency manifest",
    "Cargo.toml": "dependency manifest",
}

LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock", "go.sum")

SECRET_RES: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("OpenAI-style API key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("hard-coded password", re.compile(r"(?i)\b(password|passwd|secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]")),
]

TEST_HINTS = ("test", "tests", "spec", "__tests__")
CODE_EXT = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".c", ".cc", ".cpp", ".cs", ".swift")


@dataclass
class Signals:
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    findings: list[str] = field(default_factory=list)
    score: int = 0

    @property
    def level(self) -> str:
        if self.score >= 6:
            return "high"
        if self.score >= 3:
            return "medium"
        return "low"


def _match(path: str, pat: str) -> bool:
    return fnmatch(path, pat) or fnmatch(path, pat.replace("**/", ""))


def _is_test(path: str) -> bool:
    parts = re.split(r"[/_.\-]", path.lower())
    return any(h in parts for h in TEST_HINTS)


def analyze(files: list[FileDiff]) -> Signals:
    s = Signals(files_changed=len(files))
    s.additions = sum(f.additions for f in files)
    s.deletions = sum(f.deletions for f in files)
    total = s.additions + s.deletions

    if total > 1000:
        s.score += 3
        s.findings.append(f"Very large change ({total} lines). Consider splitting it.")
    elif total > 400:
        s.score += 1
        s.findings.append(f"Large change ({total} lines).")

    for f in files:
        for pat, why in SENSITIVE_PATTERNS.items():
            if _match(f.path, pat):
                s.score += 2
                s.findings.append(f"`{f.path}`: {why}.")
                break
        if f.path.rsplit("/", 1)[-1] in LOCKFILES:
            manifest_changed = any(_match(o.path, "**/package.json") or o.path.endswith(("pyproject.toml", "Cargo.toml", "go.mod")) for o in files)
            if not manifest_changed:
                s.score += 1
                s.findings.append(f"`{f.path}`: lockfile changed without a matching manifest change.")
        for lineno, text in f.added_lines:
            for name, rx in SECRET_RES:
                if rx.search(text):
                    s.score += 5
                    s.findings.append(f"`{f.path}:{lineno}`: possible {name} added.")
                    break

    code_changed = [f for f in files if f.path.endswith(CODE_EXT) and not _is_test(f.path) and f.status != "deleted"]
    tests_changed = [f for f in files if _is_test(f.path)]
    if code_changed and not tests_changed and sum(f.additions for f in code_changed) > 30:
        s.score += 1
        s.findings.append("Source code changed but no tests were added or updated.")

    return s
