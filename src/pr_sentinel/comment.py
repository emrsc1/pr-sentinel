"""Render the PR comment."""
from __future__ import annotations

from .diff import FileDiff
from .heuristics import Signals
from .review import Review

MARKER = "<!-- pr-sentinel -->"
INLINE_MARKER = "<!-- pr-sentinel-inline -->"
_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}
_SEV = {"critical": "🔴", "major": "🟠", "minor": "🟡", "nit": "⚪"}
_ORDER = {"critical": 0, "major": 1, "minor": 2, "nit": 3}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "risk": "risk",
        "files": "files",
        "summary": "Summary",
        "why": "Why this risk level:",
        "low_effort": "This PR may be low-effort or unreviewed generated output. A human should check it closely before spending review time.",
        "findings": "Findings",
        "tests": "Suggested tests",
        "reviewers": "Suggested reviewers (from CODEOWNERS):",
        "checks": "Automated checks",
        "not_sent": "Not sent to the model:",
        "more": "and {n} more",
        "footer": "AI-assisted review; it can be wrong. Maintainers make the final call.",
        "model": "Model:",
        "tokens": "Tokens: {i} in / {o} out.",
        "levels": "low|medium|high",
        "sev": "nit|minor|major|critical",
        "note_disabled": "Model review disabled; showing automated checks only.",
        "note_nokey": "No OpenAI API key available (common for PRs from forks); showing automated checks only.",
        "note_failed": "Model review failed; showing automated checks only.",
    },
    "tr": {
        "risk": "risk",
        "files": "dosya",
        "summary": "Özet",
        "why": "Risk seviyesinin nedeni:",
        "low_effort": "Bu PR özensiz ya da gözden geçirilmeden üretilmiş olabilir. İnceleme için zaman harcamadan önce bir insanın dikkatlice bakması iyi olur.",
        "findings": "Bulgular",
        "tests": "Önerilen testler",
        "reviewers": "Önerilen reviewer'lar (CODEOWNERS'a göre):",
        "checks": "Otomatik kontroller",
        "not_sent": "Modele gönderilmeyenler:",
        "more": "ve {n} tane daha",
        "footer": "Yapay zekâ destekli inceleme; hata yapabilir. Son karar maintainer'larındır.",
        "model": "Model:",
        "tokens": "Token: {i} girdi / {o} çıktı.",
        "levels": "düşük|orta|yüksek",
        "sev": "küçük not|minör|majör|kritik",
        "note_disabled": "Model incelemesi kapalı; sadece otomatik kontroller gösteriliyor.",
        "note_nokey": "OpenAI API anahtarı yok (fork'tan gelen PR'larda normal); sadece otomatik kontroller gösteriliyor.",
        "note_failed": "Model incelemesi başarısız oldu; sadece otomatik kontroller gösteriliyor.",
    },
}


def lang_code(language: str | None) -> str:
    """Map a free-form language input ('Turkish', 'Türkçe', 'tr') to a UI string table."""
    l = (language or "").strip().lower()
    if l.startswith(("tr", "turk", "türk")):
        return "tr"
    return "en"


def _level(t: dict[str, str], level: str) -> str:
    return dict(zip("low|medium|high".split("|"), t["levels"].split("|"))).get(level, level)


def _sev(t: dict[str, str], sev: str) -> str:
    return dict(zip("nit|minor|major|critical".split("|"), t["sev"].split("|"))).get(sev, sev)


def final_risk(signals: Signals, review: Review | None) -> str:
    """Take the higher of the heuristic and model risk; heuristics can only raise it."""
    rank = {"low": 0, "medium": 1, "high": 2}
    levels = [signals.level] + ([review.risk] if review and review.risk in rank else [])
    return max(levels, key=rank.__getitem__)


def render(
    signals: Signals,
    review: Review | None,
    skipped: list[str],
    model: str | None,
    note: str | None = None,
    language: str | None = None,
    reviewers: list[str] | None = None,
) -> str:
    t = STRINGS[lang_code(language)]
    risk = final_risk(signals, review)
    out = [MARKER, f"## {_ICON[risk]} PR Sentinel — {t['risk']}: **{_level(t, risk)}**", ""]
    out.append(f"`{signals.files_changed}` {t['files']} · `+{signals.additions}` / `-{signals.deletions}`")
    out.append("")

    if review:
        out += [f"### {t['summary']}", review.summary.strip(), ""]
        if review.risk_reason:
            out += [f"_{t['why']}_ {review.risk_reason.strip()}", ""]
        if review.likely_low_effort:
            out += ["> [!WARNING]", f"> {t['low_effort']}", ""]
        if review.issues:
            out.append(f"### {t['findings']}")
            for i in sorted(review.issues, key=lambda x: _ORDER.get(x.get("severity", "nit"), 9)):
                loc = f"`{i.get('file')}`" + (f" L{i['line']}" if i.get("line") else "")
                sev = i.get("severity", "nit")
                out.append(f"- {_SEV.get(sev, '⚪')} **{_sev(t, sev)}** {loc}: {i.get('message', '').strip()}")
            out.append("")
        if review.missing_tests:
            out.append(f"### {t['tests']}")
            out += [f"- {x}" for x in review.missing_tests]
            out.append("")

    if reviewers:
        # Backticks so owners are shown without being @-mentioned (no notification spam).
        out += [f"{t['reviewers']} " + " ".join(f"`{r}`" for r in reviewers), ""]

    if signals.findings:
        out.append(f"<details><summary>{t['checks']}</summary>\n")
        out += [f"- {f}" for f in signals.findings]
        out.append("\n</details>\n")

    if skipped:
        shown = ", ".join(f"`{p}`" for p in skipped[:20])
        more = " " + t["more"].format(n=len(skipped) - 20) if len(skipped) > 20 else ""
        out += [f"<sub>{t['not_sent']} {shown}{more}</sub>", ""]

    if note:
        out += [f"<sub>{t.get(note, note)}</sub>", ""]
    footer = t["footer"]
    if model:
        footer += f" {t['model']} `{model}`."
    if review and (review.input_tokens or review.output_tokens):
        footer += " " + t["tokens"].format(i=f"{review.input_tokens:,}", o=f"{review.output_tokens:,}")
    out.append(f"<sub>{footer} · [pr-sentinel](https://github.com/emrsc1/pr-sentinel)</sub>")
    return "\n".join(out)


def clean_suggestion(snippet: str | None) -> str | None:
    """Normalize code suggestion by stripping markdown code fences."""
    if not snippet:
        return None
    s = snippet.strip()
    if s.startswith("```suggestion"):
        s = s[len("```suggestion"):].strip()
    elif s.startswith("```"):
        s = s.strip("`").strip()
    if s.endswith("```"):
        s = s[:-3].strip()
    return s if s else None


def format_inline_comment(issue: dict, language: str | None = None) -> str:
    """Format an issue as a GitHub inline review comment body with optional suggestion."""
    t = STRINGS[lang_code(language)]
    sev = issue.get("severity", "nit")
    sev_str = _sev(t, sev).capitalize()
    icon = _SEV.get(sev, "⚪")
    msg = (issue.get("message") or "").strip()

    body = f"{INLINE_MARKER}\n{icon} **{sev_str}** (PR Sentinel): {msg}"
    sug = clean_suggestion(issue.get("suggestion"))
    if sug:
        body += f"\n\n```suggestion\n{sug}\n```"
    return body


def prepare_inline_comments(
    issues: list[dict],
    files: list[FileDiff],
    existing_comments: list[dict] | None = None,
    language: str | None = None,
) -> list[dict]:
    """Filter issues to those tied to diff lines, deduplicate, and format for GitHub review comments."""
    files_map = {f.path: f for f in files}
    existing_keys: set[tuple[str, int]] = set()
    for c in existing_comments or []:
        body = c.get("body") or ""
        if INLINE_MARKER in body:
            path = c.get("path")
            line = c.get("line") or c.get("original_line")
            if path and line:
                try:
                    existing_keys.add((path, int(line)))
                except (ValueError, TypeError):
                    pass

    inline_items: list[dict] = []
    seen_in_batch: set[tuple[str, int]] = set()

    for issue in issues:
        path = issue.get("file")
        line = issue.get("line")
        if not path or not isinstance(line, int) or line <= 0:
            continue
        file_diff = files_map.get(path)
        if not file_diff or line not in file_diff.diff_lines:
            continue
        key = (path, line)
        if key in existing_keys or key in seen_in_batch:
            continue
        seen_in_batch.add(key)

        inline_items.append({
            "path": path,
            "line": line,
            "side": "RIGHT",
            "body": format_inline_comment(issue, language),
        })
    return inline_items

