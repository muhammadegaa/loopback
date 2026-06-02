"""Issue drafting. Structured-output Gemini call per theme; no GitLab.

Two responsibilities now:
1. Draft a proper engineering ticket — action-first title, sectioned markdown body
   (Problem / Evidence / Repro / Expected / Suggested fix / Acceptance criteria),
   labels in `area::name` / `kind::name` convention, priority derived from severity.
   Evidence quotes are spliced in deterministically post-generation so they are
   verbatim customer reports (never rewritten by the model).
2. For themes the classifier flagged as duplicates of an existing open issue,
   also produce a `comment_body` — a deterministic markdown summary the
   GitLab Writer Agent will post via create_workitem_note instead of filing a
   new ticket.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel

from tools.llm import generate_structured

_log = logging.getLogger("loopback")


# These are the AI tells we strip — em dash, "not just X but Y", "delve", etc.
_BANNED_PHRASES = ("not just ", "delve into", "leverage ", "seamless", "robust ")


def _humanize(text: str) -> str:
    """Strip em dashes and a few of the most common AI tells the model may emit."""
    text = (
        text.replace(" — ", ", ")
        .replace(" —", ",")
        .replace("— ", ", ")
        .replace("—", "-")
        .strip()
    )
    return text


class _Draft(BaseModel):
    title: str
    body: str
    repro_steps: list[str]
    suggested_labels: list[str]
    priority: Literal["critical", "high", "medium", "low"]
    remediation: str


_PROMPT_HEADER = (
    "Draft a well-scoped GitLab issue for the engineering team based on this "
    "recurring customer-pain theme. Write like a senior engineer filing the ticket: "
    "plain, direct, specific. Ground every claim in the reports and invent no facts.\n\n"
    "VOICE rules — strict:\n"
    "- No em dashes. Use periods or commas.\n"
    "- No marketing or filler words: seamless, robust, leverage, delve, elevate, "
    "streamline, unlock, game-changing.\n"
    "- No \"not just X, but Y\" constructions.\n"
    "- Short, concrete sentences.\n"
    "- Reference specific code surfaces when possible (a hook, route, query, queue,\n"
    "  schema field) instead of vague language like \"the system\" or \"this feature.\"\n"
)


_PROMPT_SPEC = """
PRODUCE these fields:

TITLE (action-first, specific, under 80 characters)
- Start with a verb: Fix / Implement / Investigate / Prevent / Restore.
- Name the concrete subject, not a category.
- BAD:  "UI inconsistencies and platform issues."
- GOOD: "Fix whiteboard cursor jitter during real-time collaboration."

BODY (markdown, with these exact section headings, in order):

## Problem
2-3 sentences from the user's perspective. Concrete and specific.

## Evidence
Leave this section empty. The pipeline will insert verbatim customer quotes
deterministically post-generation. Do not write quotes here; do not duplicate them.

## Repro
Numbered steps to reproduce, inferred from the reports.
If unclear: "Repro unclear from reports; confirm with the reporter."

## Expected
One sentence describing the correct behavior.

## Suggested fix
2-3 sentences on a remediation direction. Reference specific code surfaces.

## Acceptance criteria
2-3 testable conditions for closing the ticket.

REPRO_STEPS (list form of the Repro section, for downstream consumers).

SUGGESTED_LABELS (2-4 labels, `area::name` / `kind::name` convention).
Examples: bug, area::auth, kind::regression, priority::p1,
agent-behavior::hallucination, customer-pain::high.

PRIORITY (one of critical/high/medium/low, derived from theme severity:
5 -> critical, 4 -> high, 3 -> medium, 1-2 -> low).

REMEDIATION (1-2 sentences; the suggested-fix direction, repeated as a
standalone field for downstream consumers).

STRICT RULES:
- ONE TICKET = ONE ISSUE. If the theme bundles unrelated problems, name the
  single dominant root cause in the title. Mention others ONLY under a
  trailing "## Related signals not addressed" section.
- If the theme spans >2 distinct root causes, title it as an INVESTIGATION
  ("Investigate ..."), not a Fix.
- Every claim must come from the EVIDENCE QUOTES or the deterministic theme
  metadata (frequency, severity, channels). Invent no facts.
"""


def _prompt(
    label: str, severity: int, frequency: int, quotes: list[str], related: list[dict]
) -> str:
    quote_block = "\n".join(f"- {q}" for q in quotes)
    related_block = ""
    if related:
        # Surface candidate context to the drafter so it can reference iids and avoid
        # restating things the existing ticket already says.
        rows = []
        for r in related:
            rel = r.get("relation") or "related"
            conf = r.get("confidence")
            conf_str = f" conf={conf:.2f}" if isinstance(conf, float) else ""
            rows.append(
                f"- #{r.get('iid')} [{r.get('state','?')}/{rel}{conf_str}]: "
                f"{r.get('title','')}"
            )
        related_block = (
            "\nRELATED EXISTING ISSUES (reference iids if relevant):\n"
            + "\n".join(rows)
            + "\n"
        )
    return (
        _PROMPT_HEADER
        + "\n"
        + f"THEME: {label}\n"
        + f"SEVERITY (1-5): {severity}\n"
        + f"NUMBER OF REPORTS: {frequency}\n"
        + f"REPRESENTATIVE CUSTOMER QUOTES:\n{quote_block}\n"
        + related_block
        + _PROMPT_SPEC
    )


# Match a markdown ## Evidence section (heading + its body up to the next ## or end).
_EVIDENCE_SECTION_RE = re.compile(
    r"(?im)^##\s*Evidence\b.*?(?=^##\s|\Z)", re.DOTALL | re.MULTILINE
)


def _splice_evidence(body: str, quotes: list[str]) -> str:
    """Replace any model-generated ## Evidence section with the verbatim quotes.

    Quotes are blockquoted, one per line. If the model omitted the section entirely,
    insert it after ## Problem; if neither heading is found, append it at the end.
    Always ensures a blank line before the next heading so markdown renders cleanly.
    """
    quote_lines = "\n\n".join(f'> "{q}"' for q in quotes[:3]) if quotes else "> (no quotes)"
    # Trailing blank line so the next ## heading is separated from the last quote.
    block = f"## Evidence\n\n{quote_lines}\n\n"

    if _EVIDENCE_SECTION_RE.search(body):
        return _EVIDENCE_SECTION_RE.sub(block, body, count=1).rstrip() + "\n"
    # No Evidence section; insert after ## Problem if present.
    problem = re.search(r"(?im)^##\s*Problem\b.*?(?=^##\s|\Z)", body, re.DOTALL | re.MULTILINE)
    if problem:
        _start, end = problem.span()
        return (body[:end].rstrip() + "\n\n" + block + body[end:]).rstrip() + "\n"
    # Fall back: append Evidence at the end.
    return body.rstrip() + "\n\n" + block.rstrip() + "\n"


def _enforce_priority(model_priority: str, severity: int) -> str:
    """Severity-derived priority overrides whatever the model returned, so the
    rubric stays deterministic. Severity 5 -> critical, 4 -> high, 3 -> medium,
    1-2 -> low. Falls back to the model's value only when severity is missing."""
    mapping = {5: "critical", 4: "high", 3: "medium", 2: "low", 1: "low"}
    if severity in mapping:
        return mapping[severity]
    return model_priority


def _comment_body(theme: dict, conf_summary: str | None = None) -> str:
    """Generate the deterministic markdown comment we'd post when extending an
    existing issue instead of filing a new one. No LLM call — pure data."""
    quotes = (theme.get("quotes") or [])[:3]
    quote_block = "\n\n".join(f'> "{q}"' for q in quotes) or "> (no quotes captured)"
    channels = ", ".join(theme.get("channels") or []) or "various channels"
    freq = theme.get("frequency", 0)
    sev = theme.get("severity", 0)
    conf_line = f"Classifier confidence: {conf_summary}." if conf_summary else ""
    return (
        f"**{freq} new customer reports of this theme this week** "
        f"(across {channels}).\n\n"
        f"{quote_block}\n\n"
        f"Severity {sev}/5 · frequency {freq} this batch. {conf_line}".strip()
    )


def draft_issues(themes: list, related: dict | None = None) -> dict:
    """Draft a structured GitLab issue per theme. Honors classifier-set theme flags.

    inputs: themes — ranked themes (each may carry classifier-set extend_target,
                     regression_of, classifier_reason).
            related — {theme_id: [enriched candidates]} from search + classify.
    outputs: {"drafts": [{theme_id, title, body, repro_steps, evidence_quotes,
              suggested_labels, priority, remediation, related_iids,
              frequency, severity, score, rank, channels,
              extend_target, regression_of, comment_body, classifier_reason}, ...]}
    side effects: one Gemini call per theme. No GitLab.
    """
    related = related or {}
    drafts: list[dict] = []
    for theme in themes:
        quotes = theme.get("quotes", [])
        rel = related.get(theme["id"], [])
        try:
            d = generate_structured(
                _prompt(
                    theme["label"],
                    theme.get("severity", 3),
                    theme.get("frequency", 0),
                    quotes,
                    rel,
                ),
                _Draft,
            )
        except Exception:  # noqa: BLE001 - one theme failing must not abort the whole batch
            _log.exception("drafting failed for theme %s; skipping it", theme.get("id"))
            continue

        body = _humanize(d.body)
        body = _splice_evidence(body, quotes)

        extend_target = theme.get("extend_target")
        regression_of = theme.get("regression_of")
        classifier_reason = theme.get("classifier_reason")

        comment_body = None
        if extend_target:
            # Build a short confidence summary for the comment footer
            best = max(
                (
                    c
                    for c in rel
                    if c.get("relation") == "duplicate"
                    and c.get("iid") == extend_target
                ),
                key=lambda c: float(c.get("confidence", 0.0)),
                default=None,
            )
            conf_summary = None
            if best is not None:
                conf_summary = f"{float(best.get('confidence', 0.0)):.2f}"
            comment_body = _comment_body(theme, conf_summary)

        drafts.append(
            {
                "theme_id": theme.get("id"),
                "title": _humanize(d.title),
                "body": body,
                "repro_steps": [_humanize(s) for s in d.repro_steps],
                "evidence_quotes": quotes,
                "suggested_labels": d.suggested_labels,
                "priority": _enforce_priority(d.priority, theme.get("severity", 0)),
                "remediation": _humanize(d.remediation),
                "related_iids": [r["iid"] for r in rel if r.get("iid")],
                # ranking provenance (deterministic)
                "frequency": theme.get("frequency", 0),
                "severity": theme.get("severity", 0),
                "score": theme.get("score", 0),
                "rank": theme.get("rank", 0),
                "channels": theme.get("channels", []),
                # classifier-set fields (None for themes without strong duplicates/regressions)
                "extend_target": extend_target,
                "regression_of": regression_of,
                "comment_body": comment_body,
                "classifier_reason": classifier_reason,
            }
        )
    return {"drafts": drafts}
