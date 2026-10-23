"""CODEOWNERS parsing and matching.

Supports the common subset of GitHub's CODEOWNERS syntax:
- `#` comments and blank lines
- a leading `/` anchors the pattern to the repository root
- a trailing `/` matches everything inside that directory
- `*` matches within one path segment, `**` across segments
- a pattern without `/` (other than a trailing one) matches at any depth
- the last matching rule wins, as on GitHub
"""
from __future__ import annotations

import re

CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


def _to_regex(pattern: str) -> re.Pattern[str]:
    p = pattern.lstrip("/")
    directory = p.endswith("/")
    p = p.rstrip("/")
    # Anchored to the root if it starts with "/" or contains a "/" in the middle.
    anchored = pattern.startswith("/") or "/" in p

    out = ""
    i = 0
    while i < len(p):
        if p.startswith("**/", i):
            out += r"(?:.*/)?"
            i += 3
        elif p.startswith("**", i):
            out += r".*"
            i += 2
        elif p[i] == "*":
            out += r"[^/]*"
            i += 1
        elif p[i] == "?":
            out += r"[^/]"
            i += 1
        else:
            out += re.escape(p[i])
            i += 1

    prefix = "^" if anchored else r"^(?:.*/)?"
    # A pattern matches the path itself or anything beneath it (a file or a directory name).
    suffix = r"/.*$" if directory else r"(?:/.*)?$"
    return re.compile(prefix + out + suffix)


def parse(text: str) -> list[tuple[re.Pattern[str], list[str]]]:
    rules: list[tuple[re.Pattern[str], list[str]]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        rules.append((_to_regex(parts[0]), parts[1:]))
    return rules


def owners_for(path: str, rules: list[tuple[re.Pattern[str], list[str]]]) -> list[str]:
    owners: list[str] = []
    for rx, who in rules:
        if rx.match(path):
            owners = who  # last match wins; an empty owner list clears ownership
    return owners


def suggest_reviewers(paths: list[str], rules: list[tuple[re.Pattern[str], list[str]]], author: str | None = None, limit: int = 5) -> list[str]:
    """Owners of the changed files, most-files-owned first, excluding the PR author."""
    counts: dict[str, int] = {}
    for p in paths:
        for o in owners_for(p, rules):
            counts[o] = counts.get(o, 0) + 1
    if author:
        counts.pop(f"@{author}", None)
    ranked = sorted(counts, key=lambda o: (-counts[o], o.lower()))
    return ranked[:limit]
