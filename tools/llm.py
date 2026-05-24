"""Shared Gemini client + structured-output helper.

Works with Vertex (ADC) when GOOGLE_GENAI_USE_VERTEXAI=true, else an AI Studio
API key (GEMINI_API_KEY / GOOGLE_API_KEY). No GitLab — model calls only.
"""

from __future__ import annotations

import os
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

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
    resp = get_client().models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    parsed = resp.parsed
    if parsed is None:
        raise RuntimeError(
            f"Gemini returned no parseable structured output: {(resp.text or '')[:300]}"
        )
    return parsed  # type: ignore[return-value]
