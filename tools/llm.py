"""Shared Gemini client + structured-output helper.

Works with Vertex (ADC) when GOOGLE_GENAI_USE_VERTEXAI=true, else an AI Studio
API key (GEMINI_API_KEY / GOOGLE_API_KEY). No GitLab — model calls only.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# GA fallback: if the primary model (e.g. a preview) is ever retired mid-judging and
# returns 404, fall back to this so the live demo never breaks.
_FALLBACK_MODEL = "gemini-2.5-flash"

# Vertex returns 429 RESOURCE_EXHAUSTED under per-minute quota, and 503/500 on transient
# blips. Retry those with backoff so a single rate-limit spike never fails a whole run.
_RETRY_CODES = {429, 503, 500}
_MAX_ATTEMPTS = 4
_BACKOFF_SECONDS = (5, 12, 24)  # waits between attempts; ~41s worst case per call
_log = logging.getLogger("loopback")

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return a cached genai.Client configured from env (Vertex/ADC or API key)."""
    global _client
    if _client is None:
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
            _client = genai.Client(
                vertexai=True,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
            )
        else:
            _client = genai.Client()  # uses GEMINI_API_KEY / GOOGLE_API_KEY
    return _client


def generate_structured(
    prompt: str, schema: type[T], *, model: str | None = None, temperature: float = 0.0
) -> T:
    """Call Gemini with JSON-schema-constrained output; return the parsed object.

    inputs: prompt text; a pydantic response schema; optional model + temperature
            (temperature defaults to 0 for stable, repeatable output).
    outputs: an instance of `schema`.
    side effects: one Gemini API call (network, billable). No GitLab.
    """
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=schema,
        # Disable extended "thinking": these are well-structured tasks, and turning it off
        # makes calls fast and snappy (clustering ~1.4s vs ~9.5s) and eases quota pressure.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    active = model or DEFAULT_MODEL
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = get_client().models.generate_content(
                model=active, contents=prompt, config=config
            )
            parsed = resp.parsed
            if parsed is None:
                raise RuntimeError(
                    f"Gemini returned no parseable structured output: {(resp.text or '')[:300]}"
                )
            return parsed  # type: ignore[return-value]
        except genai_errors.APIError as e:
            code = getattr(e, "code", None)
            # Primary model gone (e.g. a retired preview) -> drop to the GA model and retry.
            if (code == 404 or "NOT_FOUND" in str(e)) and active != _FALLBACK_MODEL:
                _log.warning("model %s unavailable (%s); using %s", active, code, _FALLBACK_MODEL)
                active = _FALLBACK_MODEL
                continue
            if code in _RETRY_CODES and attempt < _MAX_ATTEMPTS - 1:
                wait = _BACKOFF_SECONDS[attempt]
                _log.warning("Gemini %s; retry %d in %ds", code, attempt + 1, wait)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")  # loop returns or raises
