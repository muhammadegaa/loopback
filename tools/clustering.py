"""Theme clustering + ranking. STUB (Day 4-6).

Primary method: LLM-based thematic clustering (feed the batch to Gemini, get
themes with evidence quotes). Embeddings are the scale fallback.
"""
from __future__ import annotations


def cluster_and_rank(signals: list) -> dict:
    """Cluster signals into recurring themes and rank by frequency x severity.

    Inputs:  signals — list of {"id","text","channel","date"}.
    Outputs: {"themes": [{"id","label","quotes":[],"freq","severity","score"}, ...]}
    Side effects: model call only.
    """
    raise NotImplementedError("Day 4-6")
