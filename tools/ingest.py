"""Signal ingestion. STUB (Day 4-6)."""
from __future__ import annotations


def load_signals(source: str) -> dict:
    """Load a batch of customer feedback from a source (CSV path or URL).

    Inputs:  source — path/URL to a feedback batch.
    Outputs: {"signals": [{"id", "text", "channel", "date"}, ...]}
    Side effects: reads the file; no external writes.
    """
    raise NotImplementedError("Day 4-6")
