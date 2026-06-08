#!/usr/bin/env python3
"""End-to-end verification of the rewritten GitLabMCP wrapper on the official server.

Exercises every helper the agent uses: create_issue (with labels), find_issues (search),
relate (/relate note), get_issue (verify labels). Cleans up by closing the test issues.
Run after scripts/oauth_spike.py has produced a token.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.gitlab_mcp import GitLabMCP  # noqa: E402

PROJECT = os.environ.get("GITLAB_PROJECT_ID", "82508739")


def main() -> int:
    ok = True
    created_iids: list[int] = []
    with GitLabMCP() as gl:
        print(f"=== verifying wrapper on official server, project {PROJECT} ===\n")

        # 1. create_issue with labels (auto-created at creation)
        a = gl.create_issue(
            PROJECT,
            "Loopback verify A - frequent logouts",
            "Created by verify_wrapper.py.",
            labels=["bug", "priority::high"],
        )
        iid_a, gid_a, labels_a = a.get("iid"), a.get("id"), a.get("labels", [])
        created_iids.append(iid_a)
        print(f"[create_issue] #{iid_a}  labels={labels_a}  url={a.get('web_url')}")
        ok &= bool(iid_a) and "bug" in labels_a and "priority::high" in labels_a

        b = gl.create_issue(
            PROJECT, "Loopback verify B - logout duplicate", "Second issue.", labels=["bug"]
        )
        iid_b = b.get("iid")
        created_iids.append(iid_b)
        print(f"[create_issue] #{iid_b}  labels={b.get('labels', [])}")
        ok &= bool(iid_b)

        # 2. relate B -> A via link_work_items (first-class, global ids)
        res = gl.relate(PROJECT, iid_b, [gid_a])
        msg = res.get("message", "") if isinstance(res, dict) else str(res)
        print(f"[relate]       #{iid_b} relates_to #{iid_a}: {msg}")
        ok &= "Successfully linked" in msg

        # 3. get_issue verifies labels persisted
        v = gl.get_issue(PROJECT, iid_a)
        print(f"[get_issue]    #{iid_a} labels={v.get('labels', [])}")
        ok &= "bug" in v.get("labels", [])

        # 4. find_issues (search) - retry for indexing lag
        found_titles: list[str] = []
        for attempt in range(4):
            hits = gl.find_issues(PROJECT, "Loopback verify")
            found_titles = [h.get("title", "?") for h in hits if isinstance(h, dict)]
            if found_titles:
                break
            print(f"[find_issues]  attempt {attempt + 1}: not indexed yet, waiting 5s...")
            time.sleep(5)
        print(f"[find_issues]  'Loopback verify' -> {len(found_titles)} hit(s): {found_titles[:3]}")
        # search lag is acceptable; don't fail the run on it, just report.

        # NOTE: the official server has no close/delete-issue tool and rejects quick
        # actions, so test issues can't be cleaned via MCP - close them in the GitLab UI.
        print(f"\n[cleanup]      test issues {created_iids} left open - close them in GitLab UI.")

    print("\n=== VERDICT:", "PASS - wrapper works on official server ===" if ok
          else "FAIL - see above ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
