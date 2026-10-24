"""Duplicate pull request detection based on issues, title similarity, and changed files."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

_ISSUE_RE = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:#|gh-)?([0-9]+)|(?:^|[\s(])(?:#|gh-)([0-9]+)\b",
    re.IGNORECASE,
)
_PREFIX_RE = re.compile(
    r"^(?:feat|fix|chore|refactor|docs|test|style|perf|ci|build)(?:\([^)]*\))?!?:?\s*",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "with", "from", "by", "this", "that", "it", "pr", "pull", "request",
}


@dataclass
class DuplicateMatch:
    number: int
    title: str
    author: str
    url: str
    score: float
    shared_issues: list[str] = field(default_factory=list)
    shared_files: list[str] = field(default_factory=list)

    @property
    def percent(self) -> int:
        return int(round(self.score * 100))


def find_issue_references(text: str | None) -> set[str]:
    """Extract referenced issue numbers from PR text or body."""
    if not text:
        return set()
    matches = _ISSUE_RE.findall(text)
    out: set[str] = set()
    for m in matches:
        num = m[0] or m[1]
        if num:
            out.add(num.lstrip("#"))
    return out


def normalize_tokens(title: str | None) -> set[str]:
    """Extract normalized word tokens from a PR title, stripping conventions and stopwords."""
    if not title:
        return set()
    cleaned = _PREFIX_RE.sub("", title.strip().lower())
    words = re.findall(r"[a-z0-9_.-]+", cleaned)
    return {w for w in words if w not in _STOP_WORDS and len(w) > 1}


def title_similarity(t1: str | None, t2: str | None) -> float:
    """Calculate similarity between two PR titles (0.0 to 1.0)."""
    s1 = (t1 or "").strip().lower()
    s2 = (t2 or "").strip().lower()
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    tokens1 = normalize_tokens(s1)
    tokens2 = normalize_tokens(s2)
    if not tokens1 or not tokens2:
        return 0.0

    inter = len(tokens1 & tokens2)
    if inter == 0:
        return 0.0

    # Dice coefficient
    dice = 2.0 * inter / (len(tokens1) + len(tokens2))

    # Boost if one stripped title contains the other
    c1 = _PREFIX_RE.sub("", s1).strip()
    c2 = _PREFIX_RE.sub("", s2).strip()
    if c1 and c2 and (c1 in c2 or c2 in c1):
        dice = max(dice, 0.85)

    return min(1.0, dice)


def files_similarity(files1: set[str], files2: set[str]) -> float:
    """Calculate Jaccard and containment similarity between two sets of changed files."""
    if not files1 or not files2:
        return 0.0
    shared = len(files1 & files2)
    if shared == 0:
        return 0.0
    jaccard = shared / len(files1 | files2)
    containment = shared / min(len(files1), len(files2))
    return max(jaccard, containment * 0.8)


def find_duplicates(
    current_pr: dict,
    current_files: list[str],
    open_prs: list[dict],
    fetch_files_fn: Callable[[int], list[str]] | None = None,
    threshold: float = 0.55,
) -> list[DuplicateMatch]:
    """Find potential duplicate pull requests among open PRs."""
    curr_num = current_pr.get("number")
    curr_title = current_pr.get("title", "")
    curr_body = current_pr.get("body") or ""
    curr_issues = find_issue_references(curr_title) | find_issue_references(curr_body)
    curr_files_set = set(current_files)

    matches: list[DuplicateMatch] = []

    for pr in open_prs:
        cand_num = pr.get("number")
        if not cand_num or cand_num == curr_num:
            continue

        cand_title = pr.get("title", "")
        cand_body = pr.get("body") or ""
        cand_issues = find_issue_references(cand_title) | find_issue_references(cand_body)
        shared_issues = sorted(curr_issues & cand_issues)

        t_sim = title_similarity(curr_title, cand_title)

        # Only investigate files if there is a shared issue or sufficient title similarity
        cand_files: list[str] = []
        f_sim = 0.0
        if shared_issues or t_sim >= 0.35:
            if fetch_files_fn:
                try:
                    cand_files = fetch_files_fn(cand_num)
                except Exception:
                    cand_files = []
                if cand_files and curr_files_set:
                    f_sim = files_similarity(curr_files_set, set(cand_files))

        shared_files = sorted(list(curr_files_set & set(cand_files))) if cand_files else []

        # Scoring logic
        if shared_issues:
            # Shared issue is a very strong duplicate indicator
            score = 0.50 + (0.30 * f_sim) + (0.20 * t_sim)
        elif cand_files:
            score = (0.50 * t_sim) + (0.50 * f_sim)
        else:
            score = t_sim

        score = min(1.0, score)

        if score >= threshold:
            user = pr.get("user") or {}
            author = user.get("login", "unknown")
            url = pr.get("html_url") or f"https://github.com/pull/{cand_num}"
            matches.append(DuplicateMatch(
                number=cand_num,
                title=cand_title,
                author=author,
                url=url,
                score=score,
                shared_issues=shared_issues,
                shared_files=shared_files,
            ))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:5]
