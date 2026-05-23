"""Loopback root agent — ADK step graph.

STUB (Day 7-9). Wires the tools into the explicit flow:
    ingest -> cluster_and_rank -> search_existing -> draft_issues
           -> [LongRunningFunctionTool approval gate] -> create_in_gitlab

Model: gemini-2.5-flash (location="global"). The approval gate pauses the run
before any GitLab write. See PLAN.md and CLAUDE.md.
"""
from __future__ import annotations

# root_agent = LlmAgent(model="gemini-2.5-flash", name="loopback", tools=[...])
raise NotImplementedError("Day 7-9: build the ADK step graph + approval gate.")
