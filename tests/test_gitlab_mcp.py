"""Smoke tests for tools/gitlab_mcp.py.

Two layers:
  * OFFLINE unit tests (always run) — quick-action body construction + SSE/JSON
    parsing. No network, no creds.
  * LIVE smoke cycle (`run_live_smoke`) — create -> label-via-note -> search ->
    read back -> close, against a real GitLab trial project. Requires:
        GITLAB_TOKEN           (PAT, mcp/api scope)
        GITLAB_PROJECT_ID      (numeric, preferred) or GITLAB_PROJECT_PATH
    Run:  python tests/test_gitlab_mcp.py

The live cycle PRINTS the introspected tool schemas first so any helper arg-name
mismatch is obvious on the first run.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "gitlab_mcp", Path(__file__).parent.parent / "tools" / "gitlab_mcp.py"
)
gitlab_mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gitlab_mcp)
GitLabMCP = gitlab_mcp.GitLabMCP

NEEDED_TOOLS = ("create_issue", "create_issue_note", "get_issue", "list_issues")


# --- offline unit tests (no network) ------------------------------------

def test_parse_plain_json():
    assert GitLabMCP._parse_body('{"result":{"x":1}}')["result"]["x"] == 1


def test_parse_sse_framed():
    body = 'event: message\ndata: {"result":{"tools":[]}}\n\n'
    assert GitLabMCP._parse_body(body)["result"]["tools"] == []


def test_parse_empty_is_none():
    assert GitLabMCP._parse_body("   ") is None


def test_missing_token_raises():
    env = {k: os.environ.pop(k) for k in ("GITLAB_TOKEN", "GITLAB_OAUTH_TOKEN") if k in os.environ}
    try:
        raised = False
        try:
            GitLabMCP(token=None)
        except gitlab_mcp.GitLabMCPError:
            raised = True
        assert raised, "expected GitLabMCPError when no token present"
    finally:
        os.environ.update(env)


def test_quick_action_bodies():
    # Build helper bodies without touching the network by stubbing add_note.
    gl = object.__new__(GitLabMCP)
    captured = {}
    gl.add_note = lambda project, iid, body: captured.update(body=body) or {}  # type: ignore
    GitLabMCP.apply_labels(gl, "1", 10, ["bug", "priority::high"])
    assert captured["body"] == '/label ~"bug" ~"priority::high"'
    GitLabMCP.relate(gl, "1", 10, [3, 7])
    assert captured["body"] == "/relate #3 #7"
    GitLabMCP.close_issue(gl, "1", 10)
    assert captured["body"] == "/close"


def run_offline() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("offline unit tests: all green")


# --- live smoke cycle (requires creds) ----------------------------------

def run_live_smoke() -> int:
    project = os.environ.get("GITLAB_PROJECT_ID") or os.environ.get("GITLAB_PROJECT_PATH")
    if not (os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_OAUTH_TOKEN")) or not project:
        print(
            "\nLIVE SMOKE SKIPPED — set GITLAB_TOKEN and GITLAB_PROJECT_ID (or "
            "GITLAB_PROJECT_PATH) to run the create->label->search->read cycle."
        )
        return 0

    marker = uuid.uuid4().hex[:8]
    title = f"[loopback-smoke {marker}] session-logout cluster"
    failures = []
    issue_url = None

    with GitLabMCP() as gl:
        print("\n--- introspected tool schemas ---")
        tools = {t.get("name"): t for t in gl.list_tools()}
        for name in NEEDED_TOOLS:
            present = "yes" if name in tools else "MISSING"
            print(f"  {name:22s} {present}")
            if name not in tools:
                failures.append(f"tool {name} missing from server")
        import json as _json
        print("  create_issue inputSchema:",
              _json.dumps(tools.get("create_issue", {}).get("inputSchema", {}))[:500])

        if failures:
            print("\nFAIL — required tools missing:", failures)
            return 1

        # 1. create
        issue = gl.create_issue(project, title, description="Throwaway smoke-test issue.")
        iid = issue.get("iid")
        issue_url = issue.get("web_url")
        print(f"\n[1] create_issue   -> iid={iid}  url={issue_url}")
        if not iid:
            print("    FAIL: no iid returned. Full payload:", issue)
            return 1

        # 2. label via note — ensure a label exists, apply via /label, assert it lands
        labels = gl.list_labels(project)
        label_names = [l.get("name") for l in labels if isinstance(l, dict)] if isinstance(labels, list) else []
        created_label = None
        if not label_names:
            created_label = f"loopback-smoke-{marker}"
            gl.create_label(project, created_label, color="#6699cc")
            label_names = [created_label]
        target_label = label_names[0]
        gl.apply_labels(project, iid, [target_label])
        after = gl.get_issue(project, iid)
        applied = target_label in (after.get("labels") or [])
        print(f"[2] label {target_label!r} via /label note -> applied={applied}")
        if not applied:
            failures.append("label not applied after /label note")

        # 3. search (list_issues with a search filter)
        found = gl.find_issues(project, marker)
        hits = found if isinstance(found, list) else (found.get("results") if isinstance(found, dict) else [])
        found_ok = bool(hits)
        print(f"[3] list_issues search for {marker!r} -> found={found_ok}")
        if not found_ok:
            failures.append("created issue not found via search")

        # 4. read back
        back = gl.get_issue(project, iid)
        title_ok = back.get("title") == title
        print(f"[4] get_issue -> title_match={title_ok}")
        if not title_ok:
            failures.append(f"get_issue title mismatch: {back.get('title')!r}")

        # 5. cleanup
        gl.close_issue(project, iid)
        print("[5] closed throwaway issue via /close")
        if created_label:
            gl.delete_label(project, created_label)
            print(f"[5] deleted throwaway label {created_label!r}")

    print("\n" + ("PASS — live smoke green. Issue: " + str(issue_url)
                   if not failures else f"FAIL — {failures}. Issue: {issue_url}"))
    return 0 if not failures else 1


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a gitignored .env at the repo root (no dependency)."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))


if __name__ == "__main__":
    _load_dotenv()
    run_offline()
    sys.exit(run_live_smoke())
