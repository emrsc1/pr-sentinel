# Changelog

## 0.3.0 — 2026-10-23

### Added
- Suggested reviewers: PR Sentinel reads `CODEOWNERS` (`.github/`, root or `docs/`) from the base branch and lists the owners of the changed files, ranked by how many files they own. Owners are shown in backticks, so nobody gets an extra notification. The PR author is excluded. Turn off with `suggest_reviewers: false`.

## 0.2.0 — 2026-10-23

### Added
- Token usage (input / output) shown in the comment footer for every model review.
- Turkish comment layout: `language: Turkish` now translates headings, risk levels, severities and notes, not just the model's text.
- Skip rules: PRs opened by bots (Dependabot, Renovate…) are skipped by default (`review_bots: true` to review them), and PRs labeled `sentinel:skip` are never reviewed (`skip_label` input).

## 0.1.0 — 2026-10-23

- First release: PR summary, risk label, file/line findings, suggested tests, low-effort PR flag, heuristic checks and fork-safe fallback.
