"""GitLab MCP client wrapper (Day 3).

ALL GitLab actions go through here — never raw REST (see CLAUDE.md). Two surfaces:

1. `GitLabMCP` — a thin, synchronous MCP-over-HTTP (JSON-RPC 2.0, streamable HTTP)
   client used by smoke tests and `demo_run.py`. Independent of the agent runtime so
   it is testable without deploying anything.
2. `mcp_toolset()` — an ADK `McpToolset` bound to the same server, for the agent
   (Day 7-9). Imports google-adk lazily so this module loads without ADK installed.

SERVER: we use the community `@zereight/mcp-gitlab` server (the official GitLab Duo
MCP server 404s for PAT auth — it requires an OAuth `mcp` scope a PAT can't hold; see
PLAN.md). Run it in streamable-HTTP remote-auth mode:

    STREAMABLE_HTTP=true REMOTE_AUTHORIZATION=true GITLAB_API_URL=https://gitlab.com/api/v4 \\
    HOST=127.0.0.1 PORT=3002 npx -y @zereight/mcp-gitlab

The client sends the PAT as a `PRIVATE-TOKEN` header per request (bypasses the server's
OAuth path and uses the PAT directly). Default endpoint: http://127.0.0.1:3002/mcp
(override with MCP_SERVER_URL).

Labels & relations use GitLab quick actions posted in a note (the approved MCP-only
path), e.g. `add_note(body="/label ~bug ~priority::high\\n/relate #123")` — these run
server-side via `create_issue_note`.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_URL = "http://127.0.0.1:3002/mcp"


class GitLabMCPError(RuntimeError):
    """An MCP call returned an error or an unparseable response."""


class GitLabMCP:
    """Minimal synchronous client for the community GitLab MCP server (HTTP)."""

    def __init__(
        self, token: str | None = None, url: str | None = None, timeout: float = 30.0
    ) -> None:
        token = token or os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_OAUTH_TOKEN")
        if not token:
            raise GitLabMCPError("No GITLAB_TOKEN (or GITLAB_OAUTH_TOKEN) in env/args.")
        self.url = url or os.environ.get("MCP_SERVER_URL", DEFAULT_URL)
        self._token = token
        self._session_id: str | None = None
        self._next_id = 0
        self._client = httpx.Client(timeout=timeout)
        self._initialized = False

    # -- low level --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "PRIVATE-TOKEN": self._token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    @staticmethod
    def _parse_body(text: str) -> dict | None:
        """Parse a JSON or SSE-framed (`data:` line) JSON-RPC body."""
        text = text.strip()
        if not text:
            return None
        if text.startswith("event:") or text.startswith("data:") or "\ndata:" in text:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        return json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _rpc(self, method: str, params: dict | None = None, *, notify: bool = False) -> dict | None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self._next_id += 1
            payload["id"] = self._next_id
        if params is not None:
            payload["params"] = params
        resp = self._client.post(self.url, headers=self._headers(), json=payload)
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        if notify:
            return None
        if resp.status_code >= 400:
            raise GitLabMCPError(f"{method} -> HTTP {resp.status_code}: {resp.text[:300]}")
        parsed = self._parse_body(resp.text)
        if parsed is None:
            raise GitLabMCPError(f"{method} -> unparseable body: {resp.text[:300]}")
        if "error" in parsed:
            raise GitLabMCPError(f"{method} -> {parsed['error']}")
        return parsed.get("result", {})

    def initialize(self) -> GitLabMCP:
        if self._initialized:
            return self
        self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "loopback", "version": "0.1"},
            },
        )
        self._rpc("notifications/initialized", {}, notify=True)
        self._initialized = True
        return self

    def list_tools(self) -> list[dict]:
        """Return the server's tool definitions (name + inputSchema)."""
        self.initialize()
        return (self._rpc("tools/list", {}) or {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> Any:
        """Call an MCP tool; return structuredContent if present, else parsed text."""
        self.initialize()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments}) or {}
        if result.get("isError"):
            raise GitLabMCPError(f"tool {name} error: {result.get('content')}")
        if "structuredContent" in result:
            return result["structuredContent"]
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except (json.JSONDecodeError, KeyError):
                    return block.get("text")
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitLabMCP:
        return self.initialize()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- helpers (community @zereight/mcp-gitlab tool surface) ------------

    def create_issue(
        self,
        project_id: str | int,
        title: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> dict:
        """Create an issue. Side effect: WRITES to GitLab. Returns the issue dict."""
        args: dict[str, Any] = {
            "project_id": str(project_id),
            "title": title,
            "description": description,
        }
        if labels:
            args["labels"] = labels
        return self.create_issue_payload(args)

    def create_issue_payload(self, args: dict) -> dict:
        return self.call_tool("create_issue", args)

    def add_note(self, project_id: str | int, issue_iid: int, body: str) -> dict:
        """Add a note to an issue. Quick actions in `body` execute server-side.

        Side effect: WRITES to GitLab (and runs any quick actions in the body).
        """
        return self.call_tool(
            "create_issue_note",
            {"project_id": str(project_id), "issue_iid": issue_iid, "body": body},
        )

    def apply_labels(self, project_id: str | int, issue_iid: int, labels: list[str]) -> dict:
        """Apply labels via the /label quick action in a note (approved MCP-only path)."""
        quick = " ".join(f'~"{label}"' for label in labels)
        return self.add_note(project_id, issue_iid, f"/label {quick}")

    def relate(self, project_id: str | int, issue_iid: int, other_iids: list[int]) -> dict:
        """Relate this issue to others via the /relate quick action in a note."""
        refs = " ".join(f"#{iid}" for iid in other_iids)
        return self.add_note(project_id, issue_iid, f"/relate {refs}")

    def close_issue(self, project_id: str | int, issue_iid: int) -> dict:
        """Close an issue via the /close quick action (used to clean up smoke-test issues)."""
        return self.add_note(project_id, issue_iid, "/close")

    def get_issue(self, project_id: str | int, issue_iid: int) -> dict:
        """Retrieve a single issue by iid."""
        return self.call_tool("get_issue", {"project_id": str(project_id), "issue_iid": issue_iid})

    def find_issues(self, project_id: str | int, search: str) -> Any:
        """Find existing issues (used for duplicate/related detection) via list_issues."""
        return self.call_tool(
            "list_issues", {"project_id": str(project_id), "search": search, "scope": "all"}
        )

    def list_labels(self, project_id: str | int) -> Any:
        """List labels available in a project (so suggested labels are real)."""
        return self.call_tool("list_labels", {"project_id": str(project_id)})

    def create_label(
        self, project_id: str | int, name: str, color: str = "#6699cc", description: str = ""
    ) -> dict:
        """Create a project label. Side effect: WRITES to GitLab."""
        return self.call_tool(
            "create_label",
            {
                "project_id": str(project_id),
                "name": name,
                "color": color,
                "description": description,
            },
        )

    def delete_label(self, project_id: str | int, label_id: str | int) -> Any:
        """Delete a project label by name or id (cleanup)."""
        return self.call_tool(
            "delete_label", {"project_id": str(project_id), "label_id": str(label_id)}
        )


def mcp_toolset():  # noqa: ANN201 - return type is google.adk's McpToolset
    """Build an ADK McpToolset bound to the GitLab MCP server (Day 7-9 agent wiring)."""
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_OAUTH_TOKEN")
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.environ.get("MCP_SERVER_URL", DEFAULT_URL),
            headers={"PRIVATE-TOKEN": token},
        )
    )


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a gitignored .env at the repo root (no dependency)."""
    from pathlib import Path

    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


if __name__ == "__main__":
    # Dump live tool schemas — confirm helper tool/arg names against the running server.
    _load_dotenv()
    with GitLabMCP() as gl:
        tools = {t.get("name"): t for t in gl.list_tools()}
        print(f"{len(tools)} tools available")
        for name in (
            "create_issue",
            "create_issue_note",
            "get_issue",
            "list_issues",
            "list_labels",
        ):
            t = tools.get(name)
            print(f"\n### {name}  {'(MISSING)' if not t else ''}")
            if t:
                props = (t.get("inputSchema", {}) or {}).get("properties", {})
                required = (t.get("inputSchema", {}) or {}).get("required", [])
                print("  args:", ", ".join(f"{k}{'*' if k in required else ''}" for k in props))
