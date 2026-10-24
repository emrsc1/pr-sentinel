# 🛡️ PR Sentinel

**AI-assisted pull request triage for open source maintainers.**

Maintainers are drowning in pull requests, and a growing share of them are large, unreviewed or machine-generated. PR Sentinel is a GitHub Action that reads every new PR and posts one concise comment that answers the questions a maintainer asks first:

- **What does this PR actually do?** A short, plain summary.
- **How risky is it?** A `risk:low | medium | high` label you can filter and sort by.
- **Where should I look?** Specific findings tied to files and lines, with inline review comments and one-click suggestions.
- **Is someone else already working on this?** Automatic detection of duplicate or overlapping open PRs.
- **Is it worth my time?** A flag for PRs that look low-effort or unreviewed.
- **Who should review it?** Owners of the changed files from your `CODEOWNERS`, without pinging anyone.

It updates the same comment on every push instead of spamming the thread, posts line-level review comments with suggestions directly in the diff, flags duplicate PRs, shows token counts and estimated dollar cost for each review, and can write the whole comment in Turkish.

[![CI](https://github.com/emrsc1/pr-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/emrsc1/pr-sentinel/actions/workflows/ci.yml)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

## Quick start

Add `OPENAI_API_KEY` to your repository secrets, then create `.github/workflows/pr-sentinel.yml`:

```yaml
name: PR Sentinel
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: emrsc1/pr-sentinel@v0
        with:
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
```

That's it. No checkout step and no dependencies: the action uses only the Python standard library.

## How it works

```
PR opened / updated
   │
   ├─ 1. Fetch the diff (GitHub API)
   ├─ 2. Automated checks: free, deterministic, no API call
   │      secrets in added lines · CI workflow edits · auth / migrations /
   │      dependency manifests · lockfile drift · size · code without tests
   ├─ 3. Model review (OpenAI Responses API, structured JSON output)
   │      the model receives the diff plus the automated signals
   ├─ 4. Final risk = max(heuristic risk, model risk)
   └─ 5. Upsert one comment + set risk label (+ optional failing check)
```

Design choices that matter to maintainers:

- **Heuristics can only raise risk.** The model can't talk a leaked key or a workflow change down to "low".
- **Never blocks contributors by accident.** If the API call fails or no key is available, you still get the automated checks, and the job stays green (unless you opt into `fail_on`).
- **Fork-safe.** It runs on `pull_request`, not `pull_request_target`, so untrusted code never sees your secrets. On fork PRs without secrets it falls back to heuristics-only.
- **Bounded cost.** Lockfiles, minified files, vendored code and binaries are never sent; the diff is capped by `max_diff_chars`, preferring to include more small files.
- **Honest output.** Structured output with a strict schema; the prompt forbids inventing files or lines, and every comment says it's AI-assisted.

## Configuration

| Input | Default | Description |
|---|---|---|
| `openai_api_key` | — | OpenAI key. Empty → automated checks only. |
| `model` | `gpt-5.4` | Model used for review. |
| `language` | `English` | Language of the comment. `Turkish` also translates the comment layout. |
| `max_diff_chars` | `120000` | Max diff size sent to the model. |
| `ignore` | `*.lock,*-lock.json,*.min.js,dist/**,vendor/**` | Globs never sent to the model. |
| `add_labels` | `true` | Add `risk:*` labels. |
| `skip_drafts` | `true` | Ignore draft PRs. |
| `review_bots` | `false` | Also review PRs from bots (Dependabot, Renovate…). |
| `skip_label` | `sentinel:skip` | PRs with this label are skipped. |
| `suggest_reviewers` | `true` | List CODEOWNERS of the changed files (no @-mentions). |
| `inline_comments` | `true` | Post inline review comments on the PR diff with suggestions. |
| `detect_duplicates` | `true` | Detect potential duplicate or overlapping open pull requests. |
| `use_model` | `true` | `false` = free heuristics-only mode. |
| `fail_on` | `none` | `medium` or `high` to fail the check at that risk. |

Output: `risk` (`low` / `medium` / `high`) for use in later steps.

## Try it locally

```bash
git diff main > my.diff
PYTHONPATH=src python -m pr_sentinel --diff my.diff --no-model   # free checks only
OPENAI_API_KEY=sk-... PYTHONPATH=src python -m pr_sentinel --diff my.diff
```

## Roadmap

- [x] Inline review comments on specific lines (with one-click suggestions)
- [ ] `.pr-sentinel.yml` per-repo rules (custom sensitive paths, house style)
- [ ] Contributor-facing mode: suggestions the author can fix before a maintainer looks
- [x] Duplicate PR / issue detection
- [ ] Release notes and changelog drafting from merged PRs
- [x] Token usage per review
- [x] Turkish comment layout
- [x] Skip bot PRs and PRs labeled `sentinel:skip`
- [x] Suggested reviewers from CODEOWNERS
- [x] Dollar cost estimate per PR

## Contributing

Issues and PRs are welcome, and PR Sentinel reviews its own pull requests. Run the tests with:

```bash
pip install pytest && PYTHONPATH=src pytest -q
```

## License

MIT © emrsc1
