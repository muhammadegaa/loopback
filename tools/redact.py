"""PII redaction - runs before any signal reaches clustering, drafting, the model,
or the UI. We mask only what we can mask reliably (emails, phone numbers, URLs, and
common API-key shapes). Names are not in scope: regex-based name detection is too
lossy to claim. Honest scope beats a leaky promise."""

from __future__ import annotations

import re

# RFC 5322-ish; intentionally generous on what we accept, conservative on what we mask.
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# International or domestic phone numbers, 7+ digits, with optional separators and
# country code. Conservative: requires at least one non-digit separator OR a leading +
# so plain order numbers (e.g. ticket #4823910) don't match.
PHONE_RE = re.compile(
    r"(?:(?<!\w))"
    r"(?:\+?\d{1,3}[\s.\-]?)?"
    r"(?:\(?\d{2,4}\)?[\s.\-]\d{2,4}[\s.\-]\d{2,4}(?:[\s.\-]\d{2,4})?"
    r"|\+\d{8,15})"
    r"(?!\w)"
)

# http(s) and www. URLs; trims trailing punctuation that's usually sentence terminator.
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)

# API-key shapes common in B2B AI products. Customers pasting these into support
# messages is a real category - every AI-product team has seen it. Patterns:
#   - sk-proj-… / sk-ant-… / sk-… (OpenAI / Anthropic / generic)
#   - ANTHROPIC_API_KEY=… / OPENAI_API_KEY=… / any *_API_KEY=…
#   - Stripe live/test keys (sk_live_, pk_live_, sk_test_, pk_test_)
# Counts roll into the existing `url` slot to avoid plumbing changes - they are
# all "secrets the customer pasted in" from a trust perspective.
API_KEY_RE = re.compile(
    r"(?:sk|pk)[-_](?:live|test|proj|ant|[a-z]{2,8})[-_][A-Za-z0-9_-]{16,}"
    r"|[A-Z][A-Z0-9_]{4,}_API_KEY\s*[:=]\s*['\"]?[\w-]{8,}['\"]?"
    r"|Bearer\s+[A-Za-z0-9_\-.]{20,}",
    re.IGNORECASE,
)


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Mask emails, phones, and URLs in `text`. Returns (redacted_text, counts).

    inputs: text - the raw signal text.
    outputs: redacted text where matches are replaced with `[email]`, `[phone]`,
             `[url]`, and a counts dict {kind: int} for telemetry.
    side effects: none.
    """
    counts = {"email": 0, "phone": 0, "url": 0}

    def _sub_email(_: re.Match[str]) -> str:
        counts["email"] += 1
        return "[email]"

    def _sub_phone(_: re.Match[str]) -> str:
        counts["phone"] += 1
        return "[phone]"

    def _sub_url(_: re.Match[str]) -> str:
        counts["url"] += 1
        return "[url]"

    # Emails first so we don't lose them to the api-key matcher.
    # API keys before URLs because Bearer-token patterns can look URL-ish to a loose matcher.
    text = EMAIL_RE.sub(_sub_email, text)
    text = API_KEY_RE.sub(_sub_url, text)  # API keys ride the url slot - same trust semantics
    text = URL_RE.sub(_sub_url, text)
    text = PHONE_RE.sub(_sub_phone, text)
    return text, counts


def redact_signals(signals: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Apply `redact_pii` to every signal's `text` field. Returns (signals, totals).

    inputs: list of signal dicts with a `text` key.
    outputs: a new list with redacted text + a totals dict
             {"email": N, "phone": N, "url": N, "signals_touched": N}.
    side effects: none (does not mutate the input).
    """
    out: list[dict] = []
    totals = {"email": 0, "phone": 0, "url": 0, "signals_touched": 0}
    for s in signals:
        redacted, counts = redact_pii(s.get("text", ""))
        touched = sum(counts.values()) > 0
        if touched:
            totals["signals_touched"] += 1
        for k in ("email", "phone", "url"):
            totals[k] += counts[k]
        new = dict(s)
        new["text"] = redacted
        out.append(new)
    return out, totals
