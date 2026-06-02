"""One-shot cleanup for the GitLab demo project.

After many recording rehearsals the demo project fills up with duplicates of the
same themes. That breaks the video's verification beat (you can't point at "the
new issues we just created" when there are 90 existing ones above them) and it
also forces the Classifier Agent to route every theme to extend_existing, which
makes the demo lopsided (no fresh creates to show).

This script closes and deletes issues whose titles match patterns the demo
keeps producing, leaving a small handful behind on purpose — so the next live
run finds SOME existing issues to extend, and SOME themes that route to a fresh
create. A mixed batch is the best demo state.

Uses the GitLab REST API with the PAT in .env (the OFFICIAL MCP server doesn't
expose close_issue or delete_issue — that's a maintenance task, not part of the
live agent loop).

Run: .venv/bin/python scripts/cleanup_demo_project.py [--dry-run]

WARNING: this DELETES issues. Always run with --dry-run first.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for raw in env.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_env()
PAT = os.environ.get("GITLAB_PAT") or os.environ.get("GITLAB_TOKEN")
PROJECT_ID = os.environ.get("GITLAB_PROJECT_ID", "82508739")
BASE = os.environ.get("GITLAB_API_BASE", "https://gitlab.com/api/v4")


# Title-keyword patterns the demo produces over and over. An issue is a deletion
# candidate if its title contains ANY of these substrings (case-insensitive).
# Tune by inspecting current GitLab state before running. Keep this list short
# and obvious so we don't accidentally delete unrelated work.
PATTERNS = (
    "sso",
    "saml",
    "redirect loop",
    "destructive",
    "rm -rf",
    "hallucinat",
    "non-existent api",
    "non-existent method",
    "duplicate stripe",
    "duplicate billing",
    "plan upgrade",
    "model regression",
    "composer planning",
    "schema validation",
    "tool schema",
    "convention drift",
    "context loss",
    "context window",
    "first-token latency",
    "cold start",
    "token budget",
    "token cap",
    "over-refusal",
    "guardrail",
    "ui inconsistenc",
    "ui state synchroniz",
    "pagination inconsisten",
    "whiteboard cursor",
)

# How many matching issues to KEEP per pattern (so the Duplicate-Check Agent
# has SOMETHING to find on the next run, but not 10 things). Setting to 1
# means: keep one matching issue per pattern, delete the rest.
KEEP_PER_PATTERN = 1

# Safety: never delete an issue whose iid is above this watermark (set to the
# highest-known iid in the project so a misconfigured run doesn't nuke the
# very-latest work). Initially set to a large number.
SAFETY_MAX_IID = 10_000


def _headers() -> dict[str, str]:
    if not PAT:
        sys.exit(
            "no GITLAB_PAT (or GITLAB_TOKEN) in env or .env. Add one and re-run."
        )
    return {"PRIVATE-TOKEN": PAT}


def list_issues() -> list[dict]:
    """Page through ALL open + closed issues on the project."""
    issues: list[dict] = []
    for state in ("opened", "closed"):
        page = 1
        while True:
            r = httpx.get(
                f"{BASE}/projects/{PROJECT_ID}/issues",
                params={
                    "state": state,
                    "per_page": 100,
                    "page": page,
                    "order_by": "created_at",
                    "sort": "desc",
                },
                headers=_headers(),
                timeout=30.0,
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            issues.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return issues


def close_issue(iid: int) -> bool:
    """Mark an issue closed. Returns True on success."""
    r = httpx.put(
        f"{BASE}/projects/{PROJECT_ID}/issues/{iid}",
        json={"state_event": "close"},
        headers=_headers(),
        timeout=30.0,
    )
    return r.status_code == 200


def delete_issue(iid: int) -> bool:
    """Permanently delete an issue. Requires Owner-level access."""
    r = httpx.delete(
        f"{BASE}/projects/{PROJECT_ID}/issues/{iid}",
        headers=_headers(),
        timeout=30.0,
    )
    return r.status_code in (200, 202, 204)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="show what WOULD be deleted, without touching GitLab",
    )
    ap.add_argument(
        "--close-only",
        action="store_true",
        help="close matching issues instead of deleting them (safer)",
    )
    args = ap.parse_args()

    print(f"Project: {PROJECT_ID}")
    print(f"Dry run: {args.dry_run}")
    print(f"Mode: {'close-only' if args.close_only else 'DELETE'}")
    print()

    issues = list_issues()
    print(f"Fetched {len(issues)} total issues from the project.")

    # Bucket by pattern. Newest first (already sorted that way by the API).
    buckets: dict[str, list[dict]] = {p: [] for p in PATTERNS}
    matched: set[int] = set()
    for issue in issues:
        title = (issue.get("title") or "").lower()
        for p in PATTERNS:
            if p in title:
                buckets[p].append(issue)
                matched.add(issue["iid"])
                break  # one pattern per issue

    print(f"Matched {len(matched)} issues across {len(PATTERNS)} patterns.")
    print()
    print(f"{'PATTERN':<28} {'MATCHED':>7} {'TO DELETE':>10}")
    print("-" * 50)
    to_delete: list[dict] = []
    for p in PATTERNS:
        b = buckets[p]
        # Keep the K newest; delete the rest.
        keep = b[:KEEP_PER_PATTERN]
        kill = b[KEEP_PER_PATTERN:]
        # Safety: drop any deletion candidates above the safety watermark.
        kill = [i for i in kill if i["iid"] <= SAFETY_MAX_IID]
        to_delete.extend(kill)
        print(f"{p:<28} {len(b):>7} {len(kill):>10}  (keeping #{keep[0]['iid'] if keep else '-'})")
    print("-" * 50)
    print(f"TOTAL to delete/close: {len(to_delete)}")

    if args.dry_run:
        print()
        print("DRY RUN — nothing was changed. Re-run without --dry-run to apply.")
        return

    if not to_delete:
        print("Nothing to do.")
        return

    prompt_verb = "close" if args.close_only else "DELETE"
    ans = input(f"\nProceed to {prompt_verb} {len(to_delete)} issues? (yes/no) ").strip().lower()
    if ans != "yes":
        print("Aborted.")
        return

    ok = 0
    fail = 0
    for issue in to_delete:
        iid = issue["iid"]
        title = (issue.get("title") or "")[:60]
        action = close_issue if args.close_only else delete_issue
        verb = "closed" if args.close_only else "deleted"
        try:
            if action(iid):
                print(f"  {verb} #{iid}: {title}")
                ok += 1
            else:
                print(f"  ! {verb} failed for #{iid}: {title}")
                fail += 1
        except Exception as e:  # noqa: BLE001 - log and continue
            print(f"  ! exception on #{iid}: {e}")
            fail += 1
        # gentle: avoid burst rate-limits
        time.sleep(0.15)
    print()
    print(f"Done. {ok} {verb}, {fail} failed.")


if __name__ == "__main__":
    main()
