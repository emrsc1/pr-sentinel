import json
from pathlib import Path

from pr_sentinel import review as review_mod
from pr_sentinel.comment import MARKER, final_risk, render
from pr_sentinel.diff import build_prompt_diff, parse_unified_diff
from pr_sentinel.heuristics import analyze
from pr_sentinel.review import Review, _extract_text

SAMPLE = (Path(__file__).parent.parent / "examples" / "sample.diff").read_text()


def test_parse():
    files = parse_unified_diff(SAMPLE)
    assert [f.path for f in files] == ["src/auth/login.py", ".github/workflows/release.yml", "logo.png"]
    login = files[0]
    assert login.additions == 6 and login.deletions == 1
    assert (3, 'API_KEY = "sk-test_abcdefghijklmnopqrstuvwx"') in login.added_lines
    assert files[1].status == "added"
    assert files[2].binary


def test_heuristics_flag_secret_workflow_and_auth():
    s = analyze(parse_unified_diff(SAMPLE))
    text = " ".join(s.findings)
    assert "possible OpenAI-style API key" in text and "login.py:3" in text
    assert "CI workflow changed" in text
    assert "authentication code" in text
    assert s.level == "high"


def test_small_clean_change_is_low():
    d = "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-hi\n+hello\n"
    assert analyze(parse_unified_diff(d)).level == "low"


def test_prompt_diff_skips_binary_ignored_and_oversize():
    files = parse_unified_diff(SAMPLE)
    text, skipped = build_prompt_diff(files, max_chars=10_000, ignore=[".github/*"])
    assert "logo.png" in skipped and ".github/workflows/release.yml" not in text
    text, skipped = build_prompt_diff(files, max_chars=50, ignore=[])
    assert "src/auth/login.py" in skipped


def test_model_cannot_lower_heuristic_risk():
    s = analyze(parse_unified_diff(SAMPLE))
    assert final_risk(s, Review(summary="x", risk="low", risk_reason="")) == "high"


def test_render_contains_marker_and_findings():
    s = analyze(parse_unified_diff(SAMPLE))
    r = Review(summary="Adds admin bypass.", risk="high", risk_reason="auth bypass",
               issues=[{"file": "src/auth/login.py", "line": 6, "severity": "critical", "message": "Admin bypasses password check."}],
               missing_tests=["Test admin login requires a password"], likely_low_effort=True)
    body = render(s, r, ["logo.png"], "gpt-5.4")
    assert body.startswith(MARKER)
    assert "risk: **high**" in body and "L6" in body and "WARNING" in body and "`logo.png`" in body


def test_extract_text_from_responses_output():
    resp = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": '{"a":1}'}]}]}
    assert json.loads(_extract_text(resp)) == {"a": 1}


def test_run_review_parses_structured_output(monkeypatch):
    payload = {"summary": "s", "risk": "medium", "risk_reason": "r", "issues": [], "missing_tests": [], "likely_low_effort": False}
    captured = {}

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}]}).encode()

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data)
        return FakeResp()

    monkeypatch.setattr(review_mod.urllib.request, "urlopen", fake_urlopen)
    r = review_mod.run_review("k", "gpt-5.4", "prompt", "Turkish")
    assert r.risk == "medium"
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert "Turkish" in captured["body"]["instructions"]


def test_token_usage_captured_and_shown(monkeypatch):
    payload = {"summary": "s", "risk": "low", "risk_reason": "r", "issues": [], "missing_tests": [], "likely_low_effort": False}

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}],
                "usage": {"input_tokens": 12345, "output_tokens": 678},
            }).encode()

    monkeypatch.setattr(review_mod.urllib.request, "urlopen", lambda req, timeout: FakeResp())
    r = review_mod.run_review("k", "gpt-5.4", "prompt")
    assert (r.input_tokens, r.output_tokens) == (12345, 678)
    s = analyze(parse_unified_diff(SAMPLE))
    assert "12,345 in / 678 out" in render(s, r, [], "gpt-5.4")


def test_turkish_layout():
    from pr_sentinel.comment import lang_code
    assert lang_code("Turkish") == "tr" and lang_code("Türkçe") == "tr" and lang_code("tr") == "tr"
    assert lang_code("English") == "en" and lang_code(None) == "en"
    s = analyze(parse_unified_diff(SAMPLE))
    r = Review(summary="Özet metni.", risk="high", risk_reason="neden",
               issues=[{"file": "a.py", "line": 1, "severity": "critical", "message": "m"}])
    body = render(s, r, [], None, "note_nokey", language="Turkish")
    assert "risk: **yüksek**" in body and "### Özet" in body and "**kritik**" in body
    assert "OpenAI API anahtarı yok" in body and "Otomatik kontroller" in body
    assert "note_nokey" not in body


def test_skip_rules():
    from pr_sentinel.__main__ import skip_reason
    assert skip_reason({"draft": True}) == "draft PR"
    assert skip_reason({"draft": True}, skip_drafts="false") is None
    assert "bot" in skip_reason({"user": {"login": "dependabot[bot]", "type": "Bot"}})
    assert skip_reason({"user": {"login": "dependabot[bot]", "type": "Bot"}}, review_bots="true") is None
    assert "sentinel:skip" in skip_reason({"user": {"login": "x"}, "labels": [{"name": "sentinel:skip"}]})
    assert skip_reason({"user": {"login": "x", "type": "User"}, "labels": [{"name": "bug"}]}) is None


CODEOWNERS = """
# default owner
*                   @alice
/docs/              @docs-team
*.js                @frontend
/src/auth/          @org/security @bob
src/**/migrations/  @dba
README.md
"""


def test_codeowners_matching():
    from pr_sentinel.codeowners import owners_for, parse
    rules = parse(CODEOWNERS)
    assert owners_for("setup.py", rules) == ["@alice"]
    assert owners_for("docs/guide/intro.md", rules) == ["@docs-team"]
    assert owners_for("web/app/main.js", rules) == ["@frontend"]  # unanchored, any depth
    assert owners_for("src/auth/login.py", rules) == ["@org/security", "@bob"]
    assert owners_for("lib/src/auth/x.py", rules) == ["@alice"]  # /src/auth/ is anchored
    assert owners_for("src/app/db/migrations/0001.py", rules) == ["@dba"]
    assert owners_for("README.md", rules) == []  # empty owner list clears ownership


def test_suggest_reviewers_ranked_and_excludes_author():
    from pr_sentinel.codeowners import parse, suggest_reviewers
    rules = parse(CODEOWNERS)
    paths = ["src/auth/login.py", "src/auth/token.py", "setup.py"]
    assert suggest_reviewers(paths, rules) == ["@bob", "@org/security", "@alice"]
    assert suggest_reviewers(paths, rules, author="bob") == ["@org/security", "@alice"]


def test_reviewers_rendered_without_mentions():
    s = analyze(parse_unified_diff(SAMPLE))
    body = render(s, None, [], None, reviewers=["@bob", "@org/security"])
    assert "Suggested reviewers (from CODEOWNERS): `@bob` `@org/security`" in body


def test_diff_lines_tracked():
    files = parse_unified_diff(SAMPLE)
    login = files[0]
    assert 6 in login.diff_lines
    assert 3 in login.diff_lines
    assert 100 not in login.diff_lines


def test_clean_suggestion():
    from pr_sentinel.comment import clean_suggestion
    assert clean_suggestion(None) is None
    assert clean_suggestion("  return False  ") == "return False"
    assert clean_suggestion("```suggestion\nreturn False\n```") == "return False"
    assert clean_suggestion("```\nreturn False\n```") == "return False"


def test_format_inline_comment():
    from pr_sentinel.comment import INLINE_MARKER, format_inline_comment

    # English with suggestion
    c1 = format_inline_comment({
        "severity": "critical",
        "message": "Admin bypasses check.",
        "suggestion": "return False",
    }, "English")
    assert INLINE_MARKER in c1
    assert "🔴 **Critical** (PR Sentinel): Admin bypasses check." in c1
    assert "```suggestion\nreturn False\n```" in c1

    # Turkish without suggestion
    c2 = format_inline_comment({
        "severity": "minor",
        "message": "Değişken ismi daha açıklayıcı olabilir.",
        "suggestion": None,
    }, "Turkish")
    assert INLINE_MARKER in c2
    assert "🟡 **Minör** (PR Sentinel): Değişken ismi daha açıklayıcı olabilir." in c2
    assert "```suggestion" not in c2


def test_prepare_inline_comments():
    from pr_sentinel.comment import INLINE_MARKER, prepare_inline_comments
    files = parse_unified_diff(SAMPLE)

    issues = [
        {"file": "src/auth/login.py", "line": 6, "severity": "critical", "message": "Admin bypass.", "suggestion": "return False"},
        {"file": "src/auth/login.py", "line": 999, "severity": "minor", "message": "Not in diff"},
        {"file": "non_existent.py", "line": 1, "severity": "nit", "message": "Missing file"},
        {"file": "src/auth/login.py", "line": None, "severity": "nit", "message": "No line"},
    ]

    # First run: only line 6 is eligible
    prepared = prepare_inline_comments(issues, files)
    assert len(prepared) == 1
    assert prepared[0]["path"] == "src/auth/login.py"
    assert prepared[0]["line"] == 6
    assert "```suggestion\nreturn False\n```" in prepared[0]["body"]

    # Deduplication against existing comments
    existing = [{"path": "src/auth/login.py", "line": 6, "body": f"{INLINE_MARKER} Previous comment"}]
    prepared_again = prepare_inline_comments(issues, files, existing_comments=existing)
    assert len(prepared_again) == 0


def test_github_review_and_inline_posting(monkeypatch):
    from pr_sentinel.github import GitHub

    calls = []

    def fake_req(self, method, path, body=None, accept="application/vnd.github+json", raw_text=False):
        calls.append({"method": method, "path": path, "body": body})
        if path.endswith("/comments?per_page=100&page=1"):
            return []
        if path.endswith("/reviews"):
            return {"id": 101, "state": "COMMENTED"}
        if path.endswith("/comments"):
            return {"id": 202}
        return {}

    monkeypatch.setattr(GitHub, "_req", fake_req)
    gh = GitHub("token", "owner/repo")

    comments = gh.pull_review_comments(12)
    assert comments == []

    items = [{"path": "a.py", "line": 5, "side": "RIGHT", "body": "comment"}]
    count = gh.post_inline_review(12, "sha123", items, summary="Summary")
    assert count == 1
    assert calls[-1]["method"] == "POST"
    assert calls[-1]["path"] == "/repos/owner/repo/pulls/12/reviews"
    assert calls[-1]["body"]["commit_id"] == "sha123"
    assert calls[-1]["body"]["comments"] == items


def test_github_review_fallback_to_individual_comments(monkeypatch):
    from pr_sentinel.github import GitHub

    review_called = []
    individual_called = []

    def fake_req(self, method, path, body=None, accept="application/vnd.github+json", raw_text=False):
        if "/reviews" in path:
            review_called.append(True)
            raise RuntimeError("GitHub API 422 line not in diff")
        if "/comments" in path:
            individual_called.append(body)
            return {"id": 1}
        return {}

    monkeypatch.setattr(GitHub, "_req", fake_req)
    gh = GitHub("token", "owner/repo")

    items = [
        {"path": "a.py", "line": 5, "side": "RIGHT", "body": "comment 1"},
        {"path": "b.py", "line": 10, "side": "RIGHT", "body": "comment 2"},
    ]
    posted = gh.post_inline_review(12, "sha123", items)
    assert review_called == [True]
    assert posted == 2
    assert len(individual_called) == 2


def test_cost_calculation():
    from pr_sentinel.cost import estimate_cost, find_pricing, format_cost

    assert find_pricing("gpt-5.4") == (2.50, 10.00)
    assert find_pricing("gpt-4o-mini-2024-07-18") == (0.15, 0.60)
    assert find_pricing("o3-mini") == (1.10, 4.40)
    assert find_pricing("unknown-model") == (2.50, 10.00)

    # gpt-4o-mini: 10,000 in, 1,000 out => 10,000*0.15/1M + 1,000*0.60/1M = 0.0015 + 0.0006 = 0.0021
    cost = estimate_cost("gpt-4o-mini", 10_000, 1_000)
    assert abs(cost - 0.0021) < 1e-6
    assert format_cost(cost) == "$0.0021"

    # Edge cases
    assert format_cost(None) is None
    assert format_cost(0.0) == "$0.00"
    assert format_cost(0.0376) == "$0.038"
    assert format_cost(1.234) == "$1.23"


def test_render_includes_cost_estimate():
    s = analyze(parse_unified_diff(SAMPLE))
    r = Review(
        summary="Özet",
        risk="low",
        risk_reason="",
        input_tokens=12345,
        output_tokens=678,
    )
    # English
    body_en = render(s, r, [], "gpt-5.4")
    assert "Tokens: 12,345 in / 678 out (~$0.038)." in body_en

    # Turkish
    body_tr = render(s, r, [], "gpt-5.4", language="Turkish")
    assert "Token: 12,345 girdi / 678 çıktı (~$0.038)." in body_tr


