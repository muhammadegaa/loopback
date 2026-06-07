# ruff: noqa: E501
"""Run the live Loopback pipeline against the three demo CSVs N times each and
capture the agent's decisions for each run. Used to measure run-to-run variance
of the load-bearing demo moments (regression hits, extend lanes) so the demo
script can lean on the reliable ones.

For each batch x run pair:
  1. scripts/reset_demo.py     (close non-seed issues, clear learning memory)
  2. POST /api/runs with the CSV
  3. poll /api/runs/{id} until status == awaiting_approval
  4. capture themes/drafts: lane, extend_target, regression_of, score, rank, etc.
  5. approve EVERY draft (no edits, no overrides), so the writer fires
  6. poll until status == done
  7. capture created (which lane became create_issue vs add_note)
  8. write a JSON observation file to /tmp/rehearse-{batch}-run{N}.json

Run: .venv/bin/python scripts/rehearse.py [--api URL] [--batches first-week,...]
                                          [--runs 3] [--reset-cmd "..."]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
DEFAULT_API = "https://loopback-182683404521.us-central1.run.app"

BATCHES = ["first-week.csv", "weekly-batch.csv", "post-incident.csv"]
POLL_INTERVAL = 2.0
PRE_GATE_TIMEOUT = 240.0  # wall-clock for ingest+cluster+search+classify+draft
POST_DECISION_TIMEOUT = 240.0  # wall-clock for create


def reset(reset_cmd: str) -> None:
    print(f"  [reset] {reset_cmd}")
    res = subprocess.run(reset_cmd, shell=True, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit("reset failed")


def upload_csv(api: str, csv_path: Path) -> str:
    with csv_path.open("rb") as f:
        files = {"file": (csv_path.name, f, "text/csv")}
        r = httpx.post(f"{api}/api/runs", files=files, timeout=30.0)
    r.raise_for_status()
    return r.json()["run_id"]


def poll(api: str, run_id: str, until_status: str, timeout: float) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = httpx.get(f"{api}/api/runs/{run_id}", timeout=10.0)
        r.raise_for_status()
        state = r.json()
        last = state
        if state["status"] == until_status:
            return state
        if state["status"] in ("error", "empty"):
            return state
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"timed out waiting for status={until_status}; last={last and last.get('status')}")


def approve_all(api: str, run_id: str, draft_ids: list[str]) -> None:
    r = httpx.post(
        f"{api}/api/runs/{run_id}/decision",
        json={
            "approved_ids": draft_ids,
            "rejected_ids": [],
            "edits": {},
            "file_new_instead_of_extend": [],
        },
        timeout=30.0,
    )
    r.raise_for_status()


def summarize_drafts(drafts: list[dict]) -> list[dict]:
    out = []
    for d in drafts:
        out.append(
            {
                "theme_id": d.get("theme_id"),
                "title": d.get("title"),
                "lane": d.get("lane"),
                "rank": d.get("rank"),
                "score": d.get("score"),
                "frequency": d.get("frequency"),
                "severity": d.get("severity"),
                "priority": d.get("priority"),
                "extend_target": d.get("extend_target"),
                "regression_of": d.get("regression_of"),
                "classifier_reason": d.get("classifier_reason"),
                "channels": d.get("channels"),
                "suggested_labels": d.get("suggested_labels"),
            }
        )
    return out


def lane_counts(drafts: list[dict]) -> dict:
    counts = {"high": 0, "needs_review": 0, "extend_existing": 0}
    regressions = 0
    for d in drafts:
        counts[d.get("lane", "needs_review")] = counts.get(d.get("lane", "needs_review"), 0) + 1
        if d.get("regression_of"):
            regressions += 1
    return {"lanes": counts, "regression_flags": regressions}


def run_once(api: str, csv_path: Path, batch: str, run_idx: int, reset_cmd: str) -> dict:
    print(f"\n=== {batch} run {run_idx} ===")
    reset(reset_cmd)

    started = time.time()
    run_id = upload_csv(api, csv_path)
    print(f"  run_id={run_id}")

    pre = poll(api, run_id, "awaiting_approval", PRE_GATE_TIMEOUT)
    pre_at = time.time() - started

    if pre.get("status") != "awaiting_approval":
        print(f"  pipeline ended without awaiting_approval: status={pre.get('status')}")
        return {
            "batch": batch,
            "run": run_idx,
            "run_id": run_id,
            "status_at_gate": pre.get("status"),
            "pre_gate_seconds": pre_at,
            "drafts": summarize_drafts(pre.get("drafts", [])),
            "lane_summary": lane_counts(pre.get("drafts", [])),
            "triage": pre.get("triage", {}),
            "redaction": pre.get("redaction", {}),
            "error": pre.get("error"),
        }

    draft_summary = summarize_drafts(pre.get("drafts", []))
    lane_summary = lane_counts(pre.get("drafts", []))
    triage = pre.get("triage", {})
    redaction = pre.get("redaction", {})
    print(f"  pre-gate {pre_at:.1f}s  themes={triage.get('themes')}  ignored={triage.get('ignored')}")
    print(f"  lanes={lane_summary['lanes']}  regression_flags={lane_summary['regression_flags']}")

    draft_ids = [d.get("theme_id") for d in pre.get("drafts", []) if d.get("theme_id")]
    approve_all(api, run_id, draft_ids)
    decided_at = time.time() - started

    done = poll(api, run_id, "done", POST_DECISION_TIMEOUT)
    done_at = time.time() - started
    created = done.get("created", [])
    creates = sum(1 for c in created if not c.get("extended"))
    extends = sum(1 for c in created if c.get("extended"))
    print(f"  done {done_at:.1f}s  created={creates}  extended={extends}")

    return {
        "batch": batch,
        "run": run_idx,
        "run_id": run_id,
        "status_at_gate": "awaiting_approval",
        "pre_gate_seconds": pre_at,
        "decided_at_seconds": decided_at,
        "done_seconds": done_at,
        "drafts": draft_summary,
        "lane_summary": lane_summary,
        "triage": triage,
        "redaction": redaction,
        "created": [
            {
                "theme_id": c.get("theme_id"),
                "iid": c.get("iid"),
                "title": c.get("title"),
                "extended": bool(c.get("extended")),
                "url": c.get("url"),
            }
            for c in created
        ],
        "created_summary": {"created": creates, "extended": extends},
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("LOOPBACK_API_URL", DEFAULT_API))
    p.add_argument(
        "--batches",
        default=",".join(BATCHES),
        help="comma-separated CSV file names (in data/) to run",
    )
    p.add_argument("--runs", type=int, default=3)
    p.add_argument(
        "--reset-cmd",
        default=f".venv/bin/python {ROOT}/scripts/reset_demo.py",
        help="command to run between runs (must reset GitLab + clear learning)",
    )
    p.add_argument(
        "--out-dir",
        default="/tmp",
        help="directory for observation JSON files",
    )
    args = p.parse_args()

    batches = [b.strip() for b in args.batches.split(",") if b.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"API={args.api}  batches={batches}  runs/batch={args.runs}")
    summary = []
    for batch in batches:
        csv_path = ROOT / "data" / batch
        if not csv_path.exists():
            print(f"  MISSING {csv_path}")
            sys.exit(1)
        for n in range(1, args.runs + 1):
            try:
                obs = run_once(args.api, csv_path, batch, n, args.reset_cmd)
            except Exception as e:
                obs = {"batch": batch, "run": n, "error": str(e), "fatal": True}
                print(f"  FATAL: {e}")
            out_file = out_dir / f"rehearse-{Path(batch).stem}-run{n}.json"
            out_file.write_text(json.dumps(obs, indent=2))
            summary.append({"file": str(out_file), **{k: v for k, v in obs.items() if k in ("batch", "run", "lane_summary", "triage", "created_summary", "error")}})
            print(f"  saved {out_file}")

    sum_path = out_dir / "rehearse-summary.json"
    sum_path.write_text(json.dumps(summary, indent=2))
    print(f"\n--- written {sum_path} ---")
    for s in summary:
        print(
            f"  {s['batch']}#{s['run']}  "
            f"lanes={s.get('lane_summary', {}).get('lanes')}  "
            f"reg={s.get('lane_summary', {}).get('regression_flags')}  "
            f"created={s.get('created_summary')}"
        )


if __name__ == "__main__":
    main()
