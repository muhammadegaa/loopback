"""Human approval gate. STUB (Day 7-9).

Implemented as an ADK LongRunningFunctionTool: returns a pending status that
pauses the agent run before any GitLab write. The UI feeds back the human's
decision as a FunctionResponse to resume. This gate is mandatory.
"""
from __future__ import annotations


def request_approval(drafts: list) -> dict:
    """Pause for human approval of the drafted issues.

    Inputs:  drafts — the issues proposed for creation.
    Outputs: {"status": "pending", "batch_id": "..."}  (run pauses here)
    Side effects: creates a pending approval batch; no GitLab write.
    """
    raise NotImplementedError("Day 7-9: wrap with LongRunningFunctionTool + request_confirmation")
