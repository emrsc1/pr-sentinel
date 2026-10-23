"""Entry point.

GitHub Action mode (default):   python -m pr_sentinel
Local dry run on a diff file:   python -m pr_sentinel --diff changes.diff [--no-model]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .comment import MARKER, final_risk, render
from .diff import build_prompt_diff, parse_unified_diff
from .heuristics import analyze
from .review import build_input, run_review


def env(name: str, default: str = "") -> str:
    return os.environ.get(f"INPUT_{name.upper()}", os.environ.get(name.upper(), default)).strip()


def _review_or_note(title, body, signals, files, use_model):
    model = env("model", "gpt-5.4")
    api_key = env("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    max_chars = int(env("max_diff_chars", "120000"))
    ignore = [p.strip() for p in env("ignore", "*.lock,*-lock.json,*.min.js,dist/**,vendor/**").split(",") if p.strip()]
    diff_text, skipped = build_prompt_diff(files, max_chars, ignore)

    if not use_model:
        return None, skipped, None, "Model review disabled; showing automated checks only."
    if not api_key:
        return None, skipped, None, "No OpenAI API key available (common for PRs from forks); showing automated checks only."
    try:
        prompt = build_input(title, body, signals, diff_text, skipped)
        return run_review(api_key, model, prompt, env("language", "English")), skipped, model, None
    except Exception as e:  # never fail the PR because the reviewer failed
        print(f"::warning::PR Sentinel model review failed: {e}", file=sys.stderr)
        return None, skipped, None, "Model review failed; showing automated checks only."


def local(path: str, use_model: bool) -> int:
    with open(path, encoding="utf-8") as fh:
        files = parse_unified_diff(fh.read())
    signals = analyze(files)
    review, skipped, model, note = _review_or_note("(local run)", "", signals, files, use_model)
    print(render(signals, review, skipped, model, note))
    return 0


def action() -> int:
    from .github import GitHub

    token = env("github_token") or os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
        event = json.load(fh)
    pr = event.get("pull_request") or {}
    number = pr.get("number") or event.get("number")
    if not number:
        print("::notice::Not a pull_request event; nothing to do.")
        return 0
    if pr.get("draft") and env("skip_drafts", "true").lower() == "true":
        print("::notice::Draft PR skipped.")
        return 0

    gh = GitHub(token, repo)
    files = parse_unified_diff(gh.pull_diff(number))
    signals = analyze(files)
    review, skipped, model, note = _review_or_note(pr.get("title", ""), pr.get("body") or "", signals, files, env("use_model", "true").lower() == "true")
    body = render(signals, review, skipped, model, note)

    result = gh.upsert_comment(number, body, MARKER)
    risk = final_risk(signals, review)
    if env("add_labels", "true").lower() == "true":
        try:
            gh.set_risk_label(number, f"risk:{risk}")
        except RuntimeError as e:
            print(f"::warning::Could not set label: {e}", file=sys.stderr)

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"risk={risk}\n")
    print(f"PR Sentinel: comment {result}, risk={risk}")

    if env("fail_on", "none") in ("high", "medium") and {"low": 0, "medium": 1, "high": 2}[risk] >= {"medium": 1, "high": 2}[env("fail_on")]:
        print(f"::error::Risk level {risk} meets fail_on threshold.")
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="pr-sentinel")
    p.add_argument("--diff", help="Run locally on a unified diff file and print the comment.")
    p.add_argument("--no-model", action="store_true", help="Skip the model call (heuristics only).")
    a = p.parse_args()
    if a.diff:
        return local(a.diff, not a.no_model)
    return action()


if __name__ == "__main__":
    sys.exit(main())
