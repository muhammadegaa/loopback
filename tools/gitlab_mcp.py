"""GitLab Duo MCP client wrapper. STUB (Day 3).

ALL GitLab actions go through here — never raw REST (see CLAUDE.md). Connects via
ADK McpToolset over HTTP (StreamableHTTPConnectionParams) to /api/v4/mcp.

Auth: PAT as `Authorization: Bearer` (leading candidate from the Day-2 spike).
Tools used: create_issue, get_issue, search, search_labels, create_workitem_note.

Labels & relations are applied with quick actions in a note, e.g.:
    create_workitem_note(issue_iid, body="/label ~bug ~priority::high\\n/relate #123")
"""
from __future__ import annotations


def mcp_toolset():
    """Build the ADK McpToolset bound to the GitLab Duo MCP server."""
    raise NotImplementedError("Day 3")


def create_in_gitlab(approved_drafts: list) -> dict:
    """Create approved issues, then label+relate via a note, then read back.

    Inputs:  approved_drafts — human-approved issue drafts.
    Outputs: {"created": [{"iid","url"}, ...]}
    Side effects: WRITES to GitLab (create_issue + create_workitem_note). Only
    call after the approval gate has been satisfied.
    """
    raise NotImplementedError("Day 3-9")
