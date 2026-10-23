# Changelog

## 0.5.0 — 2026-10-23

### Added
- Dollar cost estimate per PR: PR Sentinel now calculates and displays the estimated USD cost of each review alongside token counts in the comment footer (e.g. `Tokens: 1,234 in / 567 out (~$0.004).`).
- Built-in pricing model table covering OpenAI models (`gpt-5.4`, `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`, etc.) with intelligent prefix matching.

## 0.4.0 — 2026-10-23

### Added
- Inline code review comments: PR Sentinel posts line-level review comments via the GitHub Pull Request Reviews API for findings tied to specific lines in the diff hunks.
- One-click GitHub code suggestions: When proposing a fix, the model supplies a code replacement block (` ```suggestion ````) that maintainers can accept directly in the GitHub PR UI.
- Duplicate prevention & fallback: Comments are deduplicated against existing PR Sentinel review comments on subsequent pushes, and reviews automatically fall back to individual comments if any single position is rejected by GitHub.
- Configurable with `inline_comments: true` (default) or `false`.

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
