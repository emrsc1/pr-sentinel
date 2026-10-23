"""Render the PR comment."""
from __future__ import annotations

from .heuristics import Signals
from .review import Review

MARKER = "<!-- pr-sentinel -->"
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
