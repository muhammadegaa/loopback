"""Issue drafting. STUB (Day 4-6)."""
from __future__ import annotations


def draft_issues(themes: list, related: dict) -> dict:
    """Draft well-scoped GitLab issues for the top themes.

    Inputs:  themes — ranked themes; related — existing issues/MRs found by search.
    Outputs: {"drafts": [{"title","body","repro_steps","evidence_quotes":[],
              "labels":[],"priority","remediation","related":[]}, ...]}
    Side effects: model call only. Does NOT write to GitLab.
    """
    raise NotImplementedError("Day 4-6")
