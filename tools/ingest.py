"""Signal ingestion (Day 4-6). Pure CSV load + validation — no model, no GitLab."""

from __future__ import annotations

import csv
from pathlib import Path

REQUIRED_COLUMNS = ("id", "text", "channel", "date")


class IngestError(ValueError):
    """Raised for an unreadable, empty, or malformed feedback file."""


def load_signals(source: str) -> dict:
    """Load customer feedback from a CSV with columns: id, text, channel, date.

    inputs: source — path to a CSV file.
    outputs: {"signals": [{"id","text","channel","date"}, ...], "dropped": int}
             where `dropped` counts rows skipped for having empty text.
    side effects: reads the file. No network, no GitLab.
    raises: IngestError on a missing file, an empty file, missing required columns,
            or a file with no usable rows — a clear error, never a crash.
    """
    path = Path(source)
    if not path.exists():
        raise IngestError(f"Feedback file not found: {source}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise IngestError(f"Could not read {source}: {e}") from e

    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise IngestError(f"{source} is empty (no header row).")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise IngestError(
            f"{source} is missing required columns: {', '.join(missing)} "
            f"(found: {', '.join(reader.fieldnames)})"
        )

    signals: list[dict] = []
    dropped = 0
    seen_ids: set[str] = set()
    for line_no, row in enumerate(reader, start=2):  # line 2 = first data row
        text_val = (row.get("text") or "").strip()
        if not text_val:
            dropped += 1
            continue
        sid = (row.get("id") or "").strip() or str(line_no - 1)
        if sid in seen_ids:
            sid = f"{sid}-{line_no}"
        seen_ids.add(sid)
        signals.append(
            {
                "id": sid,
                "text": text_val,
                "channel": (row.get("channel") or "").strip() or "unknown",
                "date": (row.get("date") or "").strip(),
            }
        )

    if not signals:
        raise IngestError(f"{source} has a valid header but no usable rows.")
    return {"signals": signals, "dropped": dropped}
