"""Render the PR comment."""
from __future__ import annotations

from .heuristics import Signals
from .review import Review

MARKER = "<!-- pr-sentinel -->"
_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}
_SEV = {"critical": "🔴", "major": "🟠", "minor": "🟡", "nit": "⚪"}
_ORDER = {"critical": 0, "major": 1, "minor": 2, "nit": 3}


def final_risk(signals: Signals, review: Review | None) -> str:
    """Take the higher of the heuristic and model risk; heuristics can only raise it."""
    rank = {"low": 0, "medium": 1, "high": 2}
    levels = [signals.level] + ([review.risk] if review and review.risk in rank else [])
    return max(levels, key=rank.__getitem__)


def render(signals: Signals, review: Review | None, skipped: list[str], model: str | None, note: str | None = None) -> str:
    risk = final_risk(signals, review)
    out = [MARKER, f"## {_ICON[risk]} PR Sentinel — risk: **{risk}**", ""]
    out.append(f"`{signals.files_changed}` files · `+{signals.additions}` / `-{signals.deletions}`")
    out.append("")

    if review:
        out += ["### Summary", review.summary.strip(), ""]
        if review.risk_reason:
            out += [f"_Why this risk level:_ {review.risk_reason.strip()}", ""]
        if review.likely_low_effort:
            out += ["> [!WARNING]", "> This PR may be low-effort or unreviewed generated output. A human should check it closely before spending review time.", ""]
        if review.issues:
            out.append("### Findings")
            for i in sorted(review.issues, key=lambda x: _ORDER.get(x.get("severity", "nit"), 9)):
                loc = f"`{i.get('file')}`" + (f" L{i['line']}" if i.get("line") else "")
                out.append(f"- {_SEV.get(i.get('severity'), '⚪')} **{i.get('severity')}** {loc}: {i.get('message', '').strip()}")
            out.append("")
        if review.missing_tests:
            out.append("### Suggested tests")
            out += [f"- {t}" for t in review.missing_tests]
            out.append("")

    if signals.findings:
        out.append("<details><summary>Automated checks</summary>\n")
        out += [f"- {f}" for f in signals.findings]
        out.append("\n</details>\n")

    if skipped:
        shown = ", ".join(f"`{p}`" for p in skipped[:20])
        more = f" and {len(skipped) - 20} more" if len(skipped) > 20 else ""
        out += [f"<sub>Not sent to the model: {shown}{more}</sub>", ""]

    if note:
        out += [f"<sub>{note}</sub>", ""]
    footer = "AI-assisted review; it can be wrong. Maintainers make the final call."
    if model:
        footer += f" Model: `{model}`."
    out.append(f"<sub>{footer} · [pr-sentinel](https://github.com/emrsc1/pr-sentinel)</sub>")
    return "\n".join(out)
