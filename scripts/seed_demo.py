"""Seed the GitLab demo project so the three batches produce visibly different
decision spreads at the live agent run.

What this creates (idempotent - safe to re-run; existing demo-seed issues by
title are skipped):
  3 OPEN issues  (label: demo-seed-open)  → enable extend_existing on the
                                            hallucination / over-refusal / SSO themes.
  3 CLOSED issues (label: demo-seed-closed) → enable regression_of on the
                                              silent-regression / tool-schema /
                                              latency themes (the post-incident
                                              cluster).

Uses the REST API with a PAT - the official MCP server has no close_issue tool,
so seeding/closing/reopening is a maintenance task that lives in scripts/, not
the agent loop. The live agent run during the demo video DOES exercise MCP
end-to-end (create_issue, search, get_issue, link_work_items,
create_workitem_note).

Run: .venv/bin/python scripts/seed_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_env()

PROJECT = os.environ.get("GITLAB_PROJECT_ID", "82508739")
PAT = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_PAT")
BASE = os.environ.get("GITLAB_API_BASE", "https://gitlab.com/api/v4")

LABEL_OPEN = "demo-seed-open"
LABEL_CLOSED = "demo-seed-closed"


SEED_OPEN: list[dict] = [
    {
        "title": "Agent fabricates non-existent APIs and library methods",
        "description": (
            "Customers report the agent inventing APIs, hooks, and library "
            "methods that do not exist - confidently. Examples include "
            "Supabase auth functions, Prisma methods, Next.js APIs, and "
            "Tailwind classes that aren't in any release. The hallucinated "
            "code compiles or appears valid until runtime, then breaks. "
            "Need stricter grounding against the project's actual imports "
            "and a refusal path when the agent isn't certain a symbol exists."
        ),
        "labels": LABEL_OPEN + ",area::agent-behavior,kind::bug,priority::p1",
    },
    {
        "title": "Over-refusal of valid requests for safety reasons",
        "description": (
            "The agent refuses safe, legitimate operations on the user's own "
            "data - DELETE FROM test_users on a dev DB, password-reset code "
            "in the user's own auth, GDPR-driven CSV exports, login bcrypt "
            "comparisons. Refusals come with a generic 'safety' lecture "
            "instead of help. We need calibrated refusal that respects "
            "user-as-admin context."
        ),
        "labels": LABEL_OPEN + ",area::agent-behavior,kind::bug,priority::p2",
    },
    {
        "title": "SSO redirect loop with Okta/Azure SAML providers",
        "description": (
            "Customers using Okta and Azure AD SAML get stuck in a redirect "
            "loop: provider authenticates, our app shows the dashboard for a "
            "moment, then bounces back to the login screen. Affects whole "
            "teams at a time. SAML assertion looks valid in browser devtools "
            "but our session is invalidated immediately. Reproduces on "
            "Google Workspace SSO too."
        ),
        "labels": LABEL_OPEN + ",area::auth,kind::bug,priority::p1",
    },
]


SEED_CLOSED: list[dict] = [
    {
        "title": "Silent model quality regression - diff quality drop after deploy",
        "description": (
            "After a model swap on the Pro tier the diff quality on multi-file "
            "edits dropped noticeably without an announcement. Same prompts "
            "and same codebases produced worse, confidently-wrong refactors "
            "for ~48 hours. Symptom: the agent stops following CLAUDE.md "
            "conventions, reimplements existing helpers inline, and ignores "
            "pinned project rules. Was rolled back in the previous release; "
            "closing as fixed."
        ),
        "labels": LABEL_CLOSED + ",area::model-quality,kind::regression,priority::p0",
    },
    {
        "title": "Tool-use schema validation breaks after model update",
        "description": (
            "Customers' custom tool registrations started 500-ing with "
            "'unrecognized parameter' errors and stricter schema rejections "
            "(oneOf, enum, additionalProperties:false) after a silent model "
            "update. Production agent fleets had tool calls returning empty "
            "payloads. Reproduced 100% of the time on affected accounts. "
            "Closed after we pinned the prior validator behaviour."
        ),
        "labels": LABEL_CLOSED + ",area::agent-tooling,kind::regression,priority::p0",
    },
    {
        "title": "First-token latency spike on Pro plan",
        "description": (
            "Time-to-first-token rose from sub-3s to 8-15s on the Pro plan "
            "for ~48 hours. Status page stayed green. Reports across "
            "us-east and eu-west; cold starts also looked worse. The "
            "fluency improvement that triggered the change wasn't worth "
            "the latency cost; reverted and closed."
        ),
        "labels": LABEL_CLOSED + ",area::performance,kind::regression,priority::p1",
    },
]


def _http(method: str, path: str, body: dict | None = None) -> dict | list:
    url = f"{BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "PRIVATE-TOKEN": PAT or "",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = r.read()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"{method} {path} -> {e.code}: {e.read().decode('utf-8', 'replace')}"
        ) from e


def list_demo_seed_issues() -> dict[str, list[dict]]:
    """Return {open: [...], closed: [...]} of issues already carrying a demo-seed
    label. Used for idempotency and for the final verification."""
    out: dict[str, list[dict]] = {"open": [], "closed": []}
    for state in ("opened", "closed"):
        label = LABEL_OPEN if state == "opened" else LABEL_CLOSED
        page = 1
        while True:
            res = _http(
                "GET",
                f"/projects/{PROJECT}/issues?state={state}&per_page=100&page={page}&labels={label}",
            )
            if not isinstance(res, list) or not res:
                break
            out["open" if state == "opened" else "closed"].extend(res)
            page += 1
    return out


def create_issue(spec: dict) -> dict:
    body = {
        "title": spec["title"],
        "description": spec["description"],
        "labels": spec["labels"],
    }
    return _http("POST", f"/projects/{PROJECT}/issues", body)  # type: ignore[return-value]


def close_issue(iid: int) -> None:
    _http("PUT", f"/projects/{PROJECT}/issues/{iid}", {"state_event": "close"})


def main() -> None:
    if not PAT:
        sys.exit("Missing GITLAB_TOKEN / GITLAB_PAT in .env")
    print(f"PROJECT={PROJECT}  BASE={BASE}")

    existing = list_demo_seed_issues()
    by_title: dict[str, dict] = {}
    for arr in existing.values():
        for i in arr:
            by_title[i.get("title", "").strip().lower()] = i
    if by_title:
        print(f"existing demo-seed issues: {len(by_title)} (will be skipped by title)")

    created_open: list[dict] = []
    for spec in SEED_OPEN:
        key = spec["title"].strip().lower()
        if key in by_title:
            i = by_title[key]
            print(f"  SKIP open #{i['iid']}: {spec['title']}")
            created_open.append(i)
            continue
        res = create_issue(spec)
        print(f"  CREATED open  #{res['iid']}  {spec['title']}")
        created_open.append(res)

    created_closed: list[dict] = []
    for spec in SEED_CLOSED:
        key = spec["title"].strip().lower()
        if key in by_title:
            i = by_title[key]
            print(f"  SKIP closed #{i['iid']}: {spec['title']}")
            created_closed.append(i)
            continue
        res = create_issue(spec)
        print(f"  CREATED open  #{res['iid']}  {spec['title']}  (will close)")
        close_issue(res["iid"])
        print(f"  CLOSED        #{res['iid']}")
        created_closed.append(res)

    print("\n--- final state ---")
    seeded = list_demo_seed_issues()
    print(f"open seed:   {len(seeded['open'])}  expected 3")
    for i in seeded["open"]:
        print(f"  #{i['iid']:4d}  {i['title']}")
    print(f"closed seed: {len(seeded['closed'])}  expected 3")
    for i in seeded["closed"]:
        print(f"  #{i['iid']:4d}  {i['title']}")

    ok = len(seeded["open"]) == 3 and len(seeded["closed"]) == 3
    print("\nOK" if ok else "\nWARNING: seed counts mismatch")


if __name__ == "__main__":
    main()
