"""Model-backed review using the OpenAI Responses API (stdlib only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .heuristics import Signals

OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/responses"

SYSTEM = """You are PR Sentinel, a careful reviewer helping open source maintainers triage pull requests.
Be concise, specific and honest. Only report problems you can point to in the diff.
Never invent files, functions or line numbers. If the diff looks fine, say so.
Write in {language}."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "risk", "risk_reason", "issues", "missing_tests", "likely_low_effort"],
    "properties": {
        "summary": {"type": "string", "description": "2-4 sentence plain summary of what the PR does."},
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "risk_reason": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["file", "line", "severity", "message"],
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": ["integer", "null"]},
                    "severity": {"type": "string", "enum": ["nit", "minor", "major", "critical"]},
                    "message": {"type": "string"},
                },
            },
        },
        "missing_tests": {"type": "array", "items": {"type": "string"}},
        "likely_low_effort": {
            "type": "boolean",
            "description": "True if the PR looks like unreviewed, low-value or mass-generated output.",
        },
    },
}


@dataclass
class Review:
    summary: str
    risk: str
    risk_reason: str
    issues: list[dict] = field(default_factory=list)
    missing_tests: list[str] = field(default_factory=list)
    likely_low_effort: bool = False


def build_input(title: str, body: str, signals: Signals, diff: str, skipped: list[str]) -> str:
    sig = "\n".join(f"- {f}" for f in signals.findings) or "- none"
    skip = ", ".join(skipped[:30]) or "none"
    return (
        f"PR title: {title}\n\nPR description:\n{(body or '(empty)')[:4000]}\n\n"
        f"Stats: {signals.files_changed} files, +{signals.additions}/-{signals.deletions}\n"
        f"Automated signals (heuristic, may be wrong):\n{sig}\n"
        f"Files omitted from diff (size/binary/ignored): {skip}\n\n"
        f"Diff:\n```diff\n{diff}\n```"
    )


def _extract_text(resp: dict) -> str:
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"]
    chunks = []
    for item in resp.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    chunks.append(c.get("text", ""))
                elif c.get("type") == "refusal":
                    raise RuntimeError(f"Model refused: {c.get('refusal')}")
    return "".join(chunks)


def run_review(api_key: str, model: str, prompt: str, language: str = "English", timeout: int = 180) -> Review:
    payload = {
        "model": model,
        "instructions": SYSTEM.format(language=language),
        "input": prompt,
        "text": {"format": {"type": "json_schema", "name": "pr_review", "schema": SCHEMA, "strict": True}},
    }
    req = urllib.request.Request(OPENAI_URL, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI API error {e.code}: {e.read().decode(errors='replace')[:500]}") from e
    data = json.loads(_extract_text(resp))
    return Review(**{k: data.get(k) for k in Review.__dataclass_fields__ if k in data})
