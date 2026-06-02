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
# Batched classifier reasons across themes and gets more confident than per-theme,
# so the extend bar is tighter than it would be for an isolated verdict.
EXTEND_CONFIDENCE_MIN = 0.9
REGRESSION_CONFIDENCE_MIN = 0.75


class PairVerdict(BaseModel):
    """A single (theme_id, candidate_iid) verdict in the batched response."""

    theme_id: str
    iid: int
    relation: Literal["duplicate", "regression", "related", "unrelated"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=4, max_length=240)


class BatchVerdicts(BaseModel):
    """All verdicts for every (theme, candidate) pair, in one structured response."""

    verdicts: list[PairVerdict]


_PREAMBLE = """You are classifying existing GitLab issues against recurring customer-pain
themes. For EVERY (theme, candidate) pair listed below, decide whether the candidate
is the SAME problem as the theme.

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
- Use ONLY the theme_ids and iids that appear below. Do not invent identifiers.
- You may reason across themes: if the same candidate appears under two themes,
  it may legitimately be duplicate of one and unrelated to the other.
"""


def _format_theme_block(theme: dict, candidates: list[dict]) -> str:
    quotes = (theme.get("quotes") or [])[:3]
    quote_block = "\n".join(f'  - "{q}"' for q in quotes) or "  (no quotes)"
    cand_rows: list[str] = []
    for i, c in enumerate(candidates, start=1):
        state = c.get("state") or "unknown"
        updated = c.get("updated_at") or "unknown"
        labels = ", ".join(c.get("labels") or []) or "(none)"
        desc = (c.get("description") or "").strip()
        if not desc:
            desc = "(no description available — classify on title alone)"
        cand_rows.append(
            f"  #{i} iid={c['iid']} state={state} updated={updated}\n"
            f"     title: {c.get('title', '').strip()}\n"
            f"     labels: {labels}\n"
            f"     description: {desc[:600]}"
        )
    cand_block = "\n\n".join(cand_rows) if cand_rows else "  (no candidates)"
    return (
        f"=== THEME theme_id={theme.get('id','').strip()} ===\n"
        f"LABEL: {theme.get('label','').strip()}\n"
        f"SEVERITY: {theme.get('severity', '?')}\n"
        f"REPORTS: {theme.get('frequency', '?')}\n"
        f"REPRESENTATIVE QUOTES:\n{quote_block}\n"
        f"CANDIDATES:\n{cand_block}"
    )


def classify_all(
    themes: list[dict], related: dict[str, list[dict]]
) -> dict[str, list[dict]]:
    """Classify ALL (theme, candidate) pairs in a SINGLE Gemini call.

    Replaces the per-theme classifier that ran N parallel calls and hit Vertex
    quota under business-hours pressure. One structured-output call handles 30+
    verdicts cleanly, and the model can also reason across themes — flagging
    when the same candidate looks like a duplicate of one theme and unrelated
    to another.

    inputs: themes — the full theme list (with id, label, quotes, severity,
                     frequency).
            related — {theme_id: [candidates...]} from the read step.
    outputs: a new {theme_id: [candidates with relation/confidence/reason
             appended]}. Candidates whose verdict the model omitted fall back
             to relation="related", confidence=0.0, reason="not classified".
    side effects: one Gemini call (network, billable). No GitLab.
    """
    # Only include themes that actually have candidates to classify.
    themes_with_cands = [t for t in themes if related.get(t["id"])]
    if not themes_with_cands:
        return {tid: list(cs) for tid, cs in related.items()}

    blocks = [_format_theme_block(t, related[t["id"]]) for t in themes_with_cands]
    prompt = (
        _PREAMBLE
        + "\n"
        + "\n\n".join(blocks)
        + "\n\nReturn one PairVerdict per (theme_id, iid) listed above. "
        "Use the theme_id values verbatim."
    )

    try:
        result = generate_structured(prompt, BatchVerdicts)
        # Index by (theme_id, iid) for O(1) lookup.
        by_pair: dict[tuple[str, int], PairVerdict] = {
            (v.theme_id, v.iid): v for v in result.verdicts
        }
    except Exception:  # noqa: BLE001 - classification is best-effort, never block
        by_pair = {}

    out: dict[str, list[dict]] = {}
    for tid, cands in related.items():
        enriched: list[dict] = []
        for c in cands:
            new = dict(c)
            v = by_pair.get((tid, c["iid"]))
            if v is not None:
                new["relation"] = v.relation
                new["confidence"] = float(v.confidence)
                new["reason"] = v.reason
            else:
                new["relation"] = "related"
                new["confidence"] = 0.0
                new["reason"] = "not classified"
            enriched.append(new)
        out[tid] = enriched
    return out


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
