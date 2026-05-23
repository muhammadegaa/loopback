"""FastAPI service for Cloud Run: serves the agent + approval API. STUB (Day 13-14).

Uses ADK's get_fast_api_app to expose the agent; adds approval endpoints the web
UI calls to approve/reject a pending batch and resume the paused run.
"""
from __future__ import annotations

# from google.adk.cli.fast_api import get_fast_api_app
# app = get_fast_api_app(agents_dir=..., web=True)
