"""Per-source rejection memory. When the human rejects a theme, we remember its
fingerprint (the theme label tokenized) and use it on the NEXT run with the same
source to filter matching themes BEFORE they reach the gate.

This is the real "learns your no's" loop: the agent stops proposing things you've
already told it not to. Persisted to disk so it survives across runs. Stored under
a per-source hash so different feedback streams don't pollute each other."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

_STORE_DIR = Path(os.environ.get("LOOPBACK_LEARNING_DIR", "/tmp/loopback-learning"))

# tokens we strip from theme labels before fingerprinting
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "is", "are", "be", "for",
    "with", "by", "at", "from", "as", "this", "that", "it", "its", "into", "over",
}


def _source_key(source_label: str) -> Path:
    h = hashlib.sha1((source_label or "global").encode("utf-8")).hexdigest()[:12]
    return _STORE_DIR / f"rejections-{h}.json"


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


def recall_rejections(source_label: str) -> list[dict]:
    """Return previously-rejected theme fingerprints for this source.

    inputs: source_label — the dataset/source identifier (e.g., uploaded filename).
    outputs: list of {label, tokens: [str], rejected_at: float}.
    side effects: none.
    """
    p = _source_key(source_label)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def remember_rejections(source_label: str, themes: list[dict]) -> int:
    """Persist rejected themes as fingerprints to be applied on the next run.

    inputs: source_label, list of theme dicts (with a `label` field).
    outputs: count of NEW rejections written (existing ones aren't duplicated).
    side effects: writes the per-source JSON file under the learning store.
    """
    if not themes:
        return 0
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    p = _source_key(source_label)
    existing = recall_rejections(source_label)
    seen = {e.get("label", "").lower() for e in existing}
    added = 0
    now = time.time()
    for t in themes:
        label = (t.get("label") or "").strip()
        if not label or label.lower() in seen:
            continue
        existing.append(
            {"label": label, "tokens": sorted(_tokens(label)), "rejected_at": now}
        )
        seen.add(label.lower())
        added += 1
    try:
        p.write_text(json.dumps(existing))
    except OSError:
        return 0
    return added


def matches_rejection(theme_label: str, rejections: list[dict]) -> bool:
    """True if a theme matches any past rejection by label-token overlap.

    Jaccard >= 0.5 on the tokenized label is enough to flag as "you've seen and
    rejected this before." Conservative: requires meaningful overlap, not a single
    shared word. Exact label match (case-insensitive) always counts.
    """
    label = (theme_label or "").strip()
    if not label:
        return False
    label_lower = label.lower()
    tokens = _tokens(label)
    if not tokens:
        return False
    for r in rejections:
        rlabel = (r.get("label") or "").lower().strip()
        if rlabel and rlabel == label_lower:
            return True
        rtokens = set(r.get("tokens") or [])
        if not rtokens:
            continue
        intersection = len(rtokens & tokens)
        union = len(rtokens | tokens)
        if union and intersection / union >= 0.5:
            return True
    return False
