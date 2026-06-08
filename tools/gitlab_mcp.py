"""GitLab MCP client wrapper — targets GitLab's OFFICIAL MCP server.

ALL GitLab actions go through here — never raw REST. Two surfaces:

1. `GitLabMCP` — a thin, synchronous MCP-over-HTTP (JSON-RPC 2.0, streamable HTTP)
   client used by the agent's data steps, smoke tests, and `demo_run.py`.
2. `mcp_toolset()` — an ADK `McpToolset` bound to the same server (for any LlmAgent
   that needs live GitLab tools). Imports google-adk lazily.

SERVER: GitLab's own MCP server at https://gitlab.com/api/v4/mcp (override with
MCP_SERVER_URL). It authenticates via OAuth 2.0 — a human authorizes once in a browser
(`scripts/oauth_spike.py`) and `tools.gitlab_oauth` refreshes the access token headlessly
thereafter. The token is sent as `Authorization: Bearer <access_token>` per request.
(The Day-2 spike proved a PAT 404s here — issue #586184; OAuth is the supported path.)

Tool mapping (verified live against the official server, May 2026):
  create issue   -> `create_issue(id, title, description, labels)`  labels = CSV string;
                    GitLab auto-creates any missing project labels at creation time.
  search/dedup   -> `search(scope="issues", search, project_id)`    returns {"items": [...]}.
  relate issues  -> `/relate #<iid>` quick action via `create_workitem_note`.
  apply labels   -> at creation (preferred) or `/label ~"x"` via `create_workitem_note`.
  get/verify     -> `get_issue(id, issue_iid)`.
There is no `create_label`/`list_labels` tool — labels auto-create at issue creation.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import httpx

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_URL = "https://gitlab.com/api/v4/mcp"


class GitLabMCPError(RuntimeError):
    """An MCP call returned an error or an unparseable response."""


def _default_token_provider() -> str:
    """Bearer token for the official server: explicit override, else the OAuth manager."""
    direct = os.environ.get("GITLAB_OAUTH_BEARER")
    if direct:
        return direct
    from tools.gitlab_oauth import get_access_token

    return get_access_token()


class GitLabMCP:
    """Minimal synchronous client for the official GitLab MCP server (HTTP, Bearer/OAuth)."""

    def __init__(
        self,
        token_provider: Callable[[], str] | None = None,
        url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._token_provider = token_provider or _default_token_provider
        self.url = url or os.environ.get("MCP_SERVER_URL", DEFAULT_URL)
        self._session_id: str | None = None
        self._next_id = 0
        self._client = httpx.Client(timeout=timeout)
        self._initialized = False

    # -- low level --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self._token_provider()}",
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
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
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

    # -- helpers (official GitLab MCP tool surface) ----------------------

    def create_issue(
        self,
        project_id: str | int,
        title: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> dict:
        """Create an issue (labels applied + auto-created at creation). WRITES to GitLab.

        inputs: project id/path, title, description, optional label names.
        outputs: the created issue dict (has `iid`, `web_url`, `labels`).
        side effects: creates a GitLab issue and any missing project labels.
        """
        args: dict[str, Any] = {
            "id": str(project_id),
            "title": title,
            "description": description,
        }
        if labels:
            args["labels"] = ",".join(labels)
        return self.call_tool("create_issue", args)

    def get_issue(self, project_id: str | int, issue_iid: int) -> dict:
        """Retrieve a single issue by iid (used to verify labels after creation)."""
        return self.call_tool("get_issue", {"id": str(project_id), "issue_iid": issue_iid})

    def find_issues(self, project_id: str | int, search: str) -> list[dict]:
        """Find existing issues for duplicate/related detection via `search`.

        outputs: a list of issue dicts (each with `iid`, `title`). Empty if none /
        not yet indexed. Best-effort: the agent never blocks on this.
        """
        res = self.call_tool(
            "search", {"scope": "issues", "search": search, "project_id": str(project_id)}
        )
        if isinstance(res, dict):
            items = res.get("items", [])
            return items if isinstance(items, list) else []
        return res if isinstance(res, list) else []

    def relate(self, project_id: str | int, issue_iid: int, target_global_ids: list[int]) -> dict:
        """Relate this issue to existing issues via `link_work_items` (first-class).

        inputs: source issue iid; target issues' GLOBAL ids (the `id` field from
        create_issue/get_issue/search — NOT the iid). link type is `relates_to`.
        side effects: creates work-item relationships in GitLab.

        (The official server rejects `/relate` quick-action notes, so this uses the
        native work-item linking tool — a stronger, first-class relation.)
        """
        gids = [f"gid://gitlab/WorkItem/{gid}" for gid in target_global_ids]
        return self.call_tool(
            "link_work_items",
            {
                "project_id": str(project_id),
                "work_item_iid": int(issue_iid),
                "work_items_ids": gids,
                "link_type": "relates_to",
            },
        )

    def add_note(self, project_id: str | int, issue_iid: int, body: str) -> dict:
        """Add a plain comment to an issue. WRITES to GitLab.

        NOTE: the official server rejects quick actions (a body starting with `/`).
        Labels are set at creation (`create_issue`); relations use `relate()`.
        """
        return self.call_tool(
            "create_workitem_note",
            {"project_id": str(project_id), "work_item_iid": int(issue_iid), "body": body},
        )


def mcp_toolset():  # noqa: ANN201 - return type is google.adk's McpToolset
    """Build an ADK McpToolset bound to the official GitLab MCP server (Bearer/OAuth)."""
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.environ.get("MCP_SERVER_URL", DEFAULT_URL),
            headers={"Authorization": f"Bearer {_default_token_provider()}"},
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
    # Dump live tool schemas — confirm helper tool/arg names against the official server.
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    _load_dotenv()
    with GitLabMCP() as gl:
        tools = {t.get("name"): t for t in gl.list_tools()}
        print(f"{len(tools)} tools available")
        for name in ("create_issue", "get_issue", "search", "create_workitem_note"):
            t = tools.get(name)
            print(f"\n### {name}  {'(MISSING)' if not t else ''}")
            if t:
                props = (t.get("inputSchema", {}) or {}).get("properties", {})
                required = (t.get("inputSchema", {}) or {}).get("required", [])
                print("  args:", ", ".join(f"{k}{'*' if k in required else ''}" for k in props))
