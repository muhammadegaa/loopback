"""Pipeline verification (Day 4-6): load_signals -> cluster_and_rank -> draft_issues.

Offline layer (always runs): ingest happy-path + malformed/empty/missing-file errors.
Live layer (needs Gemini): asserts ~6 coherent themes, stable ranking across runs, and
fully-populated drafts. Run:  .venv/bin/python tests/test_pipeline.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools import ingest  # noqa: E402

SAMPLE = str(ROOT / "data" / "weekly-batch.csv")

# Canonical topics planted in the Helix dataset (weekly-batch.csv) - used for
# coverage + stability checks so the assertions are robust to exact label wording.
# Rewritten 2026-06 when the demo dataset changed from the original 6-topic
# generic-SaaS corpus to the 10-topic Helix B2B-AI-startup corpus.
TOPICS: dict[str, list[str]] = {
    # T9 SSO outage - Okta/Azure SAML/Google Workspace login loops
    "sso": ["sso", "saml", "okta", "azure ad", "azure", "redirect loop", "auth"],
    # T10 Stripe double-charge / billing
    "billing": ["billing", "stripe", "charge", "double", "duplicate", "invoice", "upgrade"],
    # T1 agent hallucinates non-existent APIs / methods
    "hallucination": ["hallucinat", "fabricat", "invent", "non-existent", "made up"],
    # T2 destructive agent action without confirmation
    "destructive": ["destructive", "delete", "rm -rf", "force", "drop", "unauthorized"],
    # T3 silent model regression
    "regression": ["regression", "model quality", "was fine", "diff quality", "rolled back"],
    # T4 token cost surprise
    "token_cost": ["token", "cost", "budget", "billed", "billable", "spend"],
    # T6 tool-use schema validation breaks after model update
    "tool_schema": ["tool", "schema", "validation", "parameter", "registration"],
    # T8 first-token latency spike
    "latency": ["latency", "ttft", "first-token", "first token", "slow"],
}


def topic_of(label: str) -> str:
    low = label.lower()
    for topic, kws in TOPICS.items():
        if any(kw in low for kw in kws):
            return topic
    return "other"


# --- offline ingest tests -----------------------------------------------


def test_load_signals_basic():
    out = ingest.load_signals(SAMPLE)
    sigs = out["signals"]
    assert len(sigs) >= 120, f"expected ~140 signals, got {len(sigs)}"
    assert all({"id", "text", "channel", "date"} <= set(s) for s in sigs)
    assert len({s["id"] for s in sigs}) == len(sigs), "ids must be unique"


def test_load_signals_missing_file():
    raised = False
    try:
        ingest.load_signals(str(ROOT / "data" / "does_not_exist.csv"))
    except ingest.IngestError:
        raised = True
    assert raised, "missing file should raise IngestError"


def test_load_signals_malformed_columns():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("foo,bar\n1,hello\n")
        bad = f.name
    try:
        raised = False
        try:
            ingest.load_signals(bad)
        except ingest.IngestError as e:
            raised = "missing required columns" in str(e)
        assert raised, "malformed CSV should raise a clear IngestError, not crash"
    finally:
        os.unlink(bad)


def test_load_signals_empty_file():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        bad = f.name  # empty
    try:
        raised = False
        try:
            ingest.load_signals(bad)
        except ingest.IngestError:
            raised = True
        assert raised, "empty file should raise IngestError"
    finally:
        os.unlink(bad)


def run_offline() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("offline ingest tests: all green\n")


# --- live pipeline checks -----------------------------------------------


def _check(cond: bool, msg: str, failures: list[str]) -> None:
    print(f"  [{'ok ' if cond else 'FAIL'}] {msg}")
    if not cond:
        failures.append(msg)


def run_live() -> int:
    if not (
        os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    ):
        print("LIVE PIPELINE SKIPPED - no Gemini credentials configured.")
        return 0

    from tools import clustering, drafting

    failures: list[str] = []
    signals = ingest.load_signals(SAMPLE)["signals"]
    print(f"loaded {len(signals)} signals\n")

    print("clustering (run 1)...")
    themes = clustering.cluster_and_rank(signals)["themes"]
    for t in themes:
        print(
            f"  score={t['score']:>3} freq={t['frequency']:>2} sev={t['severity']} {t['label']}"
        )
    print()

    _check(5 <= len(themes) <= 8, f"~6 themes emerge (got {len(themes)})", failures)
    _check(
        all(themes[i]["score"] >= themes[i + 1]["score"] for i in range(len(themes) - 1)),
        "themes sorted by score descending",
        failures,
    )
    well_formed = all(
        t["id"]
        and t["label"]
        and t["quotes"]
        and t["frequency"] >= 2
        and 1 <= t["severity"] <= 5
        and t["score"] == t["frequency"] * t["severity"]
        for t in themes
    )
    _check(
        well_formed, "every theme has id/label/quotes/freq>=2/severity/consistent score", failures
    )

    covered = {topic_of(t["label"]) for t in themes} - {"other"}
    _check(
        len(covered & set(TOPICS)) >= 5,
        f"covers >=5 of {len(TOPICS)} planted Helix topics (got {sorted(covered)})",
        failures,
    )

    print("\nclustering (run 2, stability)...")
    themes2 = clustering.cluster_and_rank(signals)["themes"]
    # Stable invariants: the set of themes and the #1-ranked theme. Exact mid-rank order
    # can vary run-to-run (LLM severity judgment on near-tied scores), so we don't assert
    # it - that would be testing noise.
    topics_a = {topic_of(t["label"]) for t in themes}
    topics_b = {topic_of(t["label"]) for t in themes2}
    top1a, top1b = topic_of(themes[0]["label"]), topic_of(themes2[0]["label"])
    _check(
        abs(len(themes) - len(themes2)) <= 1,
        f"theme count stable ({len(themes)} vs {len(themes2)})",
        failures,
    )
    _check(
        topics_a == topics_b,
        f"same theme set across runs ({sorted(topics_a)} == {sorted(topics_b)})",
        failures,
    )
    _check(top1a == top1b, f"#1 theme stable across runs ({top1a} == {top1b})", failures)

    print("\ndrafting top themes...")
    top = themes[:6]
    drafts = drafting.draft_issues(top)["drafts"]
    _check(len(drafts) == len(top), f"one draft per theme ({len(drafts)}/{len(top)})", failures)
    for d in drafts:
        ok = bool(
            d["title"]
            and d["body"]
            and d["repro_steps"]
            and d["evidence_quotes"]
            and d["suggested_labels"]
            and d["priority"] in {"critical", "high", "medium", "low"}
            and d["remediation"]
        )
        _check(ok, f"draft fully populated: {d['title'][:60]!r} [{d.get('priority')}]", failures)

    print("\n=== THEME LABELS PRODUCED (ranked) ===")
    for t in themes:
        print(f"  - {t['label']}  (freq {t['frequency']} x sev {t['severity']} = {t['score']})")

    print(
        "\n"
        + (
            "PASS - pipeline green."
            if not failures
            else f"FAIL - {len(failures)} issue(s): {failures}"
        )
    )
    return 0 if not failures else 1


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


if __name__ == "__main__":
    _load_dotenv()
    run_offline()
    sys.exit(run_live())
