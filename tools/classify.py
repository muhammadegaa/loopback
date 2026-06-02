# ruff: noqa: E501
"""Candidate classification — the agent actually reads the GitLab issues that
matched its search and decides what each one IS in relation to the theme.

For each (theme, candidate) pair, Gemini returns a verdict:
  - duplicate   : same root cause, open issue → extend with new evidence, do not duplicate.
  - regression  : closed issue describing the same root cause → fix didn't hold; flag.
  - related     : same area, different root cause → worth linking, do not dedup.
  - unrelated   : keyword match only → do not link.

Plus a confidence (0-1) and a one-line reason. The agent then decides theme-level
routing — which candidate (if any) to extend, or to flag a regression — using
conservative thresholds (0.8 to extend, 0.7 to flag regression).

This is the bidirectional MCP use that turns the system from "LLM-with-tools"
into "agent that reads the system of record and decides what to do."
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tools.llm import generate_structured

# confidence floors. Conservative: a wrong "extend" is worse than a missed extend.
EXTEND_CONFIDENCE_MIN = 0.8
REGRESSION_CONFIDENCE_MIN = 0.7


class CandidateVerdict(BaseModel):
    iid: int
    relation: Literal["duplicate", "regression", "related", "unrelated"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=4, max_length=240)


class ThemeVerdicts(BaseModel):
    verdicts: list[CandidateVerdict]


_PREAMBLE = """You are classifying existing GitLab issues against a recurring customer-pain
theme. Decide, for each candidate, whether it is the SAME problem as the theme.

Verdict definitions:
- duplicate: same root cause as the theme, an OPEN issue. The right move is to
  add new evidence to it, not file a new ticket.
- regression: a CLOSED issue describing the same root cause. The fix did not hold;
  flag this so the team can re-open or investigate.
- related: same product surface, but a different root cause. Worth linking but
  do not dedupe.
- unrelated: matched on keywords only; do not link.

Rules:
- Be conservative. If the candidate's description does not clearly support
  duplicate or regression, downgrade to related or unrelated.
- A candidate without a description (we only have the title) defaults to at most
  "related" unless the title is unambiguous.
- Confidence reflects how strongly the candidate's content supports the verdict.
  Use 0.0-0.4 for guessing, 0.5-0.7 for likely, 0.8-1.0 for certain.
- The reason must cite something specific from the candidate (a phrase from the
  title or description) — not a generic statement.
"""


def _format_theme(theme: dict) -> str:
    quotes = (theme.get("quotes") or [])[:3]
    quote_block = "\n".join(f'  - "{q}"' for q in quotes) or "  (no quotes)"
    return (
        f"THEME LABEL: {theme.get('label','').strip()}\n"
        f"SEVERITY: {theme.get('severity', '?')}\n"
        f"REPORTS: {theme.get('frequency', '?')}\n"
        f"REPRESENTATIVE QUOTES:\n{quote_block}\n"
    )


def _format_candidates(candidates: list[dict]) -> str:
    rows: list[str] = []
    for i, c in enumerate(candidates, start=1):
        state = c.get("state") or "unknown"
        updated = c.get("updated_at") or "unknown"
        labels = ", ".join(c.get("labels") or []) or "(none)"
        desc = (c.get("description") or "").strip()
        if not desc:
            desc = "(no description available — classify on title alone)"
        rows.append(
            f"#{i} iid={c['iid']} state={state} updated={updated}\n"
            f"   title: {c.get('title', '').strip()}\n"
            f"   labels: {labels}\n"
            f"   description:\n   {desc[:800]}"
        )
    return "\n\n".join(rows)


def classify_candidates(theme: dict, candidates: list[dict]) -> list[dict]:
    """Classify a list of candidate GitLab issues against a theme.

    inputs: theme — dict with label, quotes, severity, frequency.
            candidates — list of dicts (each with iid, title, state, description, labels,
                         updated_at). Empty list returns empty list.
    outputs: candidates with three new fields appended in place AND returned:
             relation, confidence, reason. Candidates whose iid the model
             omitted from its verdict list fall back to relation="related",
             confidence=0.0, reason="not classified".
    side effects: one Gemini call (network, billable). No GitLab.
    """
    if not candidates:
        return candidates
    prompt = (
        _PREAMBLE
        + "\n"
        + _format_theme(theme)
        + "\nCANDIDATES:\n"
        + _format_candidates(candidates)
        + "\n\nReturn one verdict per candidate, keyed by iid. Use only the iids listed."
    )
    try:
        result = generate_structured(prompt, ThemeVerdicts)
        by_iid = {v.iid: v for v in result.verdicts}
    except Exception:  # noqa: BLE001 - classification is best-effort, never block
        by_iid = {}
    for c in candidates:
        v = by_iid.get(c["iid"])
        if v is not None:
            c["relation"] = v.relation
            c["confidence"] = float(v.confidence)
            c["reason"] = v.reason
        else:
            c["relation"] = "related"
            c["confidence"] = 0.0
            c["reason"] = "not classified"
    return candidates


def derive_theme_flags(candidates: list[dict]) -> dict:
    """Decide theme-level routing from a classified candidate list.

    outputs: {extend_target, regression_of, classifier_reason}
      - extend_target  : iid of the strongest open duplicate (confidence >= EXTEND_CONFIDENCE_MIN)
      - regression_of  : iid of the strongest closed regression (confidence >= REGRESSION_CONFIDENCE_MIN)
      - classifier_reason : the reason from whichever candidate drove the routing
    All None if no candidate clears the bar.
    """
    extend_target: int | None = None
    regression_of: int | None = None
    classifier_reason: str | None = None

    # pick the strongest open duplicate above the floor
    duplicates = [
        c
        for c in candidates
        if c.get("relation") == "duplicate"
        and (c.get("state") or "opened") in {"opened", "open"}
        and float(c.get("confidence", 0.0)) >= EXTEND_CONFIDENCE_MIN
    ]
    if duplicates:
        best = max(duplicates, key=lambda c: float(c.get("confidence", 0.0)))
        extend_target = best["iid"]
        classifier_reason = best.get("reason")

    # pick the strongest closed regression above the (lower) regression floor
    regressions = [
        c
        for c in candidates
        if c.get("relation") == "regression"
        and (c.get("state") or "closed") in {"closed"}
        and float(c.get("confidence", 0.0)) >= REGRESSION_CONFIDENCE_MIN
    ]
    if regressions:
        best = max(regressions, key=lambda c: float(c.get("confidence", 0.0)))
        regression_of = best["iid"]
        if classifier_reason is None:
            classifier_reason = best.get("reason")

    return {
        "extend_target": extend_target,
        "regression_of": regression_of,
        "classifier_reason": classifier_reason,
    }
