"""Reset the GitLab demo project back to the seed state for the next rehearsal.

A full pipeline run writes new issues; a second rehearsal would start from a
polluted project (the classifier would route everything to extend_existing
because the agent's own past output looks like duplicate matches). This script
restores the seed:

  * Deletes every issue that does NOT carry a `demo-seed-open` or
    `demo-seed-closed` label (these are the issues the agent created during
    the previous rehearsal). Deletion is necessary — merely closing them
    leaves "closed candidates" the classifier may flag as false regressions
    on the next run. Idempotent — non-seed issues already gone are skipped.
  * Reopens any `demo-seed-open` issue that's currently closed.
  * Closes any `demo-seed-closed` issue that's currently open.
  * POSTs to /api/admin/clear-learning on the live API to wipe the per-source
    rejection memory.

Run: .venv/bin/python scripts/reset_demo.py [--api URL]

WARNING: this DELETES (not closes) every non-seed issue in the demo project.
The seed (#113-#118 currently) is protected by the demo-seed-* labels.
"""

from __future__ import annotations

import argparse
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
DEFAULT_API = "https://loopback-182683404521.us-central1.run.app"

LABEL_OPEN = "demo-seed-open"
LABEL_CLOSED = "demo-seed-closed"


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


def list_issues(state: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        res = _http(
            "GET",
            f"/projects/{PROJECT}/issues?state={state}&per_page=100&page={page}",
        )
        if not isinstance(res, list) or not res:
            break
        out.extend(res)
        page += 1
    return out


def set_state(iid: int, event: str) -> None:
    """event: 'close' or 'reopen'"""
    _http("PUT", f"/projects/{PROJECT}/issues/{iid}", {"state_event": event})


def delete_issue(iid: int) -> None:
    _http("DELETE", f"/projects/{PROJECT}/issues/{iid}")


def clear_learning(api_url: str) -> None:
    url = f"{api_url.rstrip('/')}/api/admin/clear-learning"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"  clear-learning: {r.status} {r.read().decode('utf-8', 'replace').strip()}")
    except urllib.error.HTTPError as e:
        print(f"  clear-learning FAILED: {e.code} {e.read().decode('utf-8', 'replace')}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("LOOPBACK_API_URL", DEFAULT_API))
    p.add_argument("--skip-clear-learning", action="store_true")
    args = p.parse_args()

    if not PAT:
        sys.exit("Missing GITLAB_TOKEN / GITLAB_PAT in .env")

    opened = list_issues("opened")
    closed = list_issues("closed")
    print(f"BEFORE  open={len(opened)}  closed={len(closed)}")

    seed_open_iids = {
        i["iid"] for i in (opened + closed) if LABEL_OPEN in i.get("labels", [])
    }
    seed_closed_iids = {
        i["iid"] for i in (opened + closed) if LABEL_CLOSED in i.get("labels", [])
    }
    print(f"seed-open present:   {sorted(seed_open_iids)}")
    print(f"seed-closed present: {sorted(seed_closed_iids)}")

    if len(seed_open_iids) != 3 or len(seed_closed_iids) != 3:
        print(
            "WARNING: seed manifest incomplete. "
            "Run scripts/seed_demo.py to recreate the seed first."
        )

    # 1. delete every non-seed issue (agent fallout from prior rehearsals,
    # whether currently open or closed). Closing alone leaves closed candidates
    # the classifier may flag as false regressions on the next run.
    deleted_count = 0
    for i in opened + closed:
        labels = i.get("labels", [])
        if LABEL_OPEN in labels or LABEL_CLOSED in labels:
            continue
        delete_issue(i["iid"])
        deleted_count += 1
        print(f"  DELETE non-seed #{i['iid']} ({i['state']}): {i.get('title','')[:70]}")
    print(f"deleted {deleted_count} non-seed issue(s)")

    # 2. reopen any seed-open that drifted to closed
    reopen_count = 0
    for i in closed:
        if LABEL_OPEN in i.get("labels", []):
            set_state(i["iid"], "reopen")
            reopen_count += 1
            print(f"  REOPEN seed   #{i['iid']}: {i.get('title','')[:70]}")
    if reopen_count:
        print(f"reopened {reopen_count} demo-seed-open issue(s)")

    # 3. close any seed-closed that drifted to open
    close_count = 0
    for i in opened:
        if LABEL_CLOSED in i.get("labels", []):
            set_state(i["iid"], "close")
            close_count += 1
            print(f"  CLOSE seed    #{i['iid']}: {i.get('title','')[:70]}")
    if close_count:
        print(f"closed {close_count} demo-seed-closed issue(s) back to closed")

    # 4. clear per-source rejection memory on the live API
    if not args.skip_clear_learning:
        print(f"clearing learning memory at {args.api} ...")
        clear_learning(args.api)

    # 5. verify
    opened = list_issues("opened")
    closed = list_issues("closed")
    final_open_seed = sum(
        1 for i in opened if LABEL_OPEN in i.get("labels", [])
    )
    final_closed_seed = sum(
        1 for i in closed if LABEL_CLOSED in i.get("labels", [])
    )
    non_seed_open = sum(
        1
        for i in opened
        if LABEL_OPEN not in i.get("labels", [])
        and LABEL_CLOSED not in i.get("labels", [])
    )
    print(
        f"AFTER   open={len(opened)}  closed={len(closed)}  "
        f"seed_open={final_open_seed}/3  seed_closed={final_closed_seed}/3  "
        f"non-seed-open={non_seed_open}"
    )
    ok = (
        final_open_seed == 3
        and final_closed_seed == 3
        and non_seed_open == 0
    )
    print("OK — seed restored" if ok else "WARNING: state not fully restored")


if __name__ == "__main__":
    main()
