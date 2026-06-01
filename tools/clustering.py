"""Theme clustering + ranking (Day 4-6). LLM-based; no GitLab.

Frequency and the final score are computed deterministically from the model's theme
assignments (not estimated by the model), so ranking is stable across runs.

Themes whose labels match anything the human has rejected on this source before are
filtered out *before* drafting — the real "learns your no's" loop.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from tools.learning import matches_rejection
from tools.llm import generate_structured


class _Theme(BaseModel):
    label: str
    severity: int  # 1-5; clamped in code
    signal_ids: list[str]


class _Clusters(BaseModel):
    themes: list[_Theme]


_PREAMBLE = """You are triaging customer feedback for an engineering team.
Group the ACTIONABLE problem reports below into recurring themes (distinct product issues).
Ignore non-actionable noise — praise, thank-yous, off-topic or pricing questions, unrelated
feature requests, spam, or test messages. Do NOT create themes for noise.

For each theme provide:
- label: a short, specific title for the underlying problem (e.g. "Frequent session logouts").
- severity: integer 1-5. 5 = data loss, billing errors, or blocks core work; 3 = significant
  friction; 1 = minor or cosmetic.
- signal_ids: the ids of every feedback item that belongs to this theme.

Assign each actionable item to exactly one theme. Use only ids that appear below; never invent ids.

FEEDBACK (id<TAB>text):
"""


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "theme"


def cluster_and_rank(signals: list, past_rejections: list[dict] | None = None) -> dict:
    """Cluster feedback into recurring themes ranked by frequency x severity.

    inputs:
      - signals — list of {"id","text","channel",...} from load_signals.
      - past_rejections — optional list of rejection fingerprints from tools.learning.
        Any theme whose label matches a past rejection (token-overlap Jaccard >= 0.5
        or exact case-insensitive label match) is filtered out before ranking.
    outputs: {"themes": [{"id","label","quotes":[...],"signal_ids":[...],"channels":[...],
              "frequency","severity","score","rank"}, ...] sorted by score descending,
              "total","themed","ignored","filtered_by_learning"} where:
              - `ignored` is non-actionable noise the model dropped, and
              - `filtered_by_learning` is themes suppressed because the human rejected
                similar themes on this source before.
    side effects: one Gemini call (network, billable). No GitLab.
    """
    by_id = {str(s["id"]): s for s in signals}
    items = "\n".join(f"{s['id']}\t{s['text']}" for s in signals)
    result = generate_structured(_PREAMBLE + items + "\n", _Clusters)
    rejections = past_rejections or []

    themes: list[dict] = []
    suppressed: list[dict] = []
    used_slugs: set[str] = set()
    suppressed_signal_count = 0
    for t in result.themes:
        ids = [i for i in t.signal_ids if i in by_id]
        if not ids:
            continue
        if rejections and matches_rejection(t.label, rejections):
            suppressed.append({"label": t.label.strip(), "frequency": len(ids)})
            suppressed_signal_count += len(ids)
            continue
        slug = _slug(t.label)
        while slug in used_slugs:
            slug += "-x"
        used_slugs.add(slug)
        freq = len(ids)
        sev = max(1, min(5, t.severity))
        channels = sorted({by_id[i].get("channel", "") for i in ids if by_id[i].get("channel")})
        themes.append(
            {
                "id": slug,
                "label": t.label.strip(),
                "quotes": [by_id[i]["text"] for i in ids[:3]],
                "signal_ids": ids,
                "channels": channels,
                "frequency": freq,
                "severity": sev,
                "score": freq * sev,
            }
        )

    themes.sort(key=lambda x: (-x["score"], x["label"].lower()))
    for rank, t in enumerate(themes, start=1):
        t["rank"] = rank

    total = len(signals)
    themed = sum(t["frequency"] for t in themes)
    return {
        "themes": themes,
        "total": total,
        "themed": themed,
        "ignored": max(0, total - themed - suppressed_signal_count),
        "filtered_by_learning": len(suppressed),
        "filtered_signals": suppressed_signal_count,
        "suppressed": suppressed,
    }
