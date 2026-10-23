"""Unified diff parsing and size-aware truncation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class FileDiff:
    path: str
    old_path: str | None = None
    status: str = "modified"  # added | deleted | renamed | modified
    binary: bool = False
    additions: int = 0
    deletions: int = 0
    lines: list[str] = field(default_factory=list)
    added_lines: list[tuple[int, str]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def parse_unified_diff(diff: str) -> list[FileDiff]:
    """Parse `git diff` / GitHub `.diff` output into per-file records."""
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    new_line = 0

    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            parts = raw.split(" ")
            a = parts[2][2:] if len(parts) > 2 else ""
            b = parts[3][2:] if len(parts) > 3 else a
            cur = FileDiff(path=b, old_path=a if a != b else None)
            if a != b:
                cur.status = "renamed"
            files.append(cur)
            cur.lines.append(raw)
            continue
        if cur is None:
            continue
        cur.lines.append(raw)
        if raw.startswith("new file mode"):
            cur.status = "added"
        elif raw.startswith("deleted file mode"):
            cur.status = "deleted"
        elif raw.startswith("Binary files") or raw.startswith("GIT binary patch"):
            cur.binary = True
        elif raw.startswith("+++ ") or raw.startswith("--- "):
            continue
        elif raw.startswith("@@"):
            m = _HUNK_RE.match(raw)
            new_line = int(m.group(1)) if m else 0
        elif raw.startswith("+"):
            cur.additions += 1
            cur.added_lines.append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith("-"):
            cur.deletions += 1
        elif raw.startswith(" "):
            new_line += 1
    return files


def build_prompt_diff(files: list[FileDiff], max_chars: int, ignore: list[str] | None = None) -> tuple[str, list[str]]:
    """Concatenate file diffs up to `max_chars`. Returns (diff_text, skipped_paths).

    Smaller files are included first so the model sees as many files as possible.
    """
    from fnmatch import fnmatch

    ignore = ignore or []
    skipped: list[str] = []
    candidates: list[FileDiff] = []
    for f in files:
        if f.binary or any(fnmatch(f.path, pat) for pat in ignore):
            skipped.append(f.path)
        else:
            candidates.append(f)

    out: list[str] = []
    used = 0
    for f in sorted(candidates, key=lambda x: len(x.text)):
        t = f.text
        if used + len(t) + 1 > max_chars:
            skipped.append(f.path)
            continue
        out.append(t)
        used += len(t) + 1
    return "\n".join(out), skipped
