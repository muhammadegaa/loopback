"""Smoke tests for tools/gitlab_mcp.py (official GitLab MCP server).

Two layers:
  * OFFLINE unit tests (always run) - SSE/JSON parsing, Bearer header, and the
    argument shaping for create_issue (labels CSV) and relate (link_work_items).
    No network, no creds.
  * LIVE smoke cycle (`run_live_smoke`) - create (with labels) -> get_issue verify ->
    relate via link_work_items -> search, against a real GitLab project via the
    official MCP server. Requires an OAuth token (run scripts/oauth_spike.py first)
    and GITLAB_PROJECT_ID. Run:  python tests/test_gitlab_mcp.py

The official server has no close/delete-issue tool and rejects quick actions, so the
live cycle leaves its throwaway issues open - close them in the GitLab UI.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))  # so the wrapper's lazy `from tools.gitlab_oauth` resolves

_spec = importlib.util.spec_from_file_location(
    "gitlab_mcp", ROOT / "tools" / "gitlab_mcp.py"
)
gitlab_mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gitlab_mcp)
GitLabMCP = gitlab_mcp.GitLabMCP

NEEDED_TOOLS = ("create_issue", "get_issue", "search", "link_work_items", "create_workitem_note")


# --- offline unit tests (no network) ------------------------------------


def test_parse_plain_json():
    assert GitLabMCP._parse_body('{"result":{"x":1}}')["result"]["x"] == 1


def test_parse_sse_framed():
    body = 'event: message\ndata: {"result":{"tools":[]}}\n\n'
    assert GitLabMCP._parse_body(body)["result"]["tools"] == []


def test_parse_empty_is_none():
    assert GitLabMCP._parse_body("   ") is None


def test_bearer_header_uses_token_provider():
    gl = GitLabMCP(token_provider=lambda: "tok-abc")
    headers = gl._headers()
    assert headers["Authorization"] == "Bearer tok-abc"
    gl.close()


def test_create_issue_joins_labels_csv():
    gl = object.__new__(GitLabMCP)
    captured = {}
    gl.call_tool = lambda name, args: captured.update(name=name, args=args) or {}  # type: ignore
    GitLabMCP.create_issue(gl, "1", "Title", "Body", labels=["bug", "priority::high"])
    assert captured["name"] == "create_issue"
    assert captured["args"]["id"] == "1"
    assert captured["args"]["labels"] == "bug,priority::high"


def test_relate_uses_link_work_items_with_gids():
    gl = object.__new__(GitLabMCP)
    captured = {}
    gl.call_tool = lambda name, args: captured.update(name=name, args=args) or {}  # type: ignore
    GitLabMCP.relate(gl, "82508739", 16, [190967384, 190967386])
    assert captured["name"] == "link_work_items"
    assert captured["args"]["work_item_iid"] == 16
    assert captured["args"]["work_items_ids"] == [
        "gid://gitlab/WorkItem/190967384",
        "gid://gitlab/WorkItem/190967386",
    ]
    assert captured["args"]["link_type"] == "relates_to"


def run_offline() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("offline unit tests: all green")


# --- live smoke cycle (requires an OAuth token) -------------------------


def _token_available() -> bool:
    return bool(
        os.environ.get("GITLAB_OAUTH_BEARER")
        or os.environ.get("GITLAB_OAUTH_TOKEN_JSON")
        or (Path(__file__).parent.parent / ".oauth_token.json").exists()
    )


def run_live_smoke() -> int:
    project = os.environ.get("GITLAB_PROJECT_ID") or os.environ.get("GITLAB_PROJECT_PATH")
    if not (_token_available() and project):
        print(
            "\nLIVE SMOKE SKIPPED - run scripts/oauth_spike.py for an OAuth token and set "
            "GITLAB_PROJECT_ID to run create->verify->relate->search."
        )
        return 0

    marker = uuid.uuid4().hex[:8]
    title = f"[loopback-smoke {marker}] session-logout cluster"
    failures: list[str] = []
    issue_url = None

    with GitLabMCP() as gl:
        print("\n--- tool availability ---")
        tools = {t.get("name") for t in gl.list_tools()}
        for name in NEEDED_TOOLS:
            present = "yes" if name in tools else "MISSING"
            print(f"  {name:22s} {present}")
            if name not in tools:
                failures.append(f"tool {name} missing from server")
        if failures:
            print("\nFAIL - required tools missing:", failures)
            return 1

        # 1. create with labels (auto-created + applied at creation)
        issue = gl.create_issue(
            project, title, "Throwaway smoke-test issue.", labels=["bug", f"smoke-{marker}"]
        )
        iid, gid, labels = issue.get("iid"), issue.get("id"), issue.get("labels", [])
        issue_url = issue.get("web_url")
        print(f"\n[1] create_issue   -> iid={iid} labels={labels} url={issue_url}")
        if not iid:
            print("    FAIL: no iid returned:", issue)
            return 1
        if "bug" not in labels:
            failures.append("label 'bug' not applied at creation")

        # 2. read back
        back = gl.get_issue(project, iid)
        title_ok = back.get("title") == title
        print(f"[2] get_issue      -> title_match={title_ok} labels={back.get('labels')}")
        if not title_ok:
            failures.append(f"get_issue title mismatch: {back.get('title')!r}")

        # 3. relate via link_work_items (first-class)
        dup = gl.create_issue(
            project, f"[loopback-smoke {marker}] duplicate", "dup.", labels=["bug"]
        )
        res = gl.relate(project, dup.get("iid"), [gid])
        linked = "Successfully linked" in (res.get("message", "") if isinstance(res, dict) else "")
        print(f"[3] link_work_items #{dup.get('iid')} relates_to #{iid} -> linked={linked}")
        if not linked:
            failures.append(f"relate failed: {res}")

        # 4. search (retry for indexing lag; lag is tolerated, not a failure)
        found = []
        for _attempt in range(3):
            found = gl.find_issues(project, marker)
            if found:
                break
            time.sleep(5)
        print(f"[4] search {marker!r}    -> {len(found)} hit(s) (search has brief indexing lag)")

        print("\n[cleanup] throwaway issues left open - close them in the GitLab UI.")

    print(
        "\n"
        + (
            f"PASS - live smoke green. Issue: {issue_url}"
            if not failures
            else f"FAIL - {failures}. Issue: {issue_url}"
        )
    )
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
