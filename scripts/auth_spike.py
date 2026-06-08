#!/usr/bin/env python3
"""Day-2 auth spike for the GitLab Duo MCP server.

Goal: empirically answer ONE question before we build anything on top of it -
can a *headless* client (our Gemini agent on Agent Engine) authenticate to the
GitLab Duo MCP server and list its tools, without a browser-interactive OAuth dance?

This is a self-contained, dependency-free MCP (streamable-HTTP, JSON-RPC 2.0)
client. It runs the `initialize` -> `notifications/initialized` -> `tools/list`
handshake and reports whether real tools come back.

Auth paths tried, in the order the plan prioritizes:
  1. PAT as `Authorization: Bearer <token>`   (leading candidate - see below)
  2. PAT as `PRIVATE-TOKEN: <token>`           (classic GitLab API header)
  3. OAuth access token as Bearer              (if you obtained one out-of-band)

Why bearer-PAT is the lead candidate: an unauthenticated request to
`https://gitlab.com/api/v4/mcp` returns a plain GitLab `401 {"message":"401
Unauthorized"}` with NO `WWW-Authenticate` OAuth challenge - i.e. it rejects
exactly like the rest of `/api/v4/`, which standard PATs authenticate against.

USAGE
    # No token: runs the unauthenticated probe only (still a real datapoint).
    python scripts/auth_spike.py

    # With a token (create a PAT on the trial with `mcp` and/or `api` scope):
    GITLAB_TOKEN=glpat-xxxx python scripts/auth_spike.py

    # Self-managed / custom host:
    GITLAB_BASE_URL=https://gitlab.example.com GITLAB_TOKEN=... python scripts/auth_spike.py

EXIT CODES
    0  authenticated and listed >=1 tool (official server is GO)
    2  endpoint reachable but no token / auth failed (decision pending)
    3  endpoint unreachable / network error
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("GITLAB_BASE_URL", "https://gitlab.com").rstrip("/")
MCP_URL = f"{BASE_URL}/api/v4/mcp"
PAT = os.environ.get("GITLAB_TOKEN")
OAUTH_TOKEN = os.environ.get("GITLAB_OAUTH_TOKEN")
PROTOCOL_VERSION = "2025-06-18"
TIMEOUT = 20


def _post(headers: dict, payload: dict) -> tuple[int, dict, str]:
    """POST one JSON-RPC message. Returns (status, response_headers, body_text).

    Handles both `application/json` and `text/event-stream` (SSE) responses,
    which streamable-HTTP MCP servers may use interchangeably.
    """
    body = json.dumps(payload).encode()
    base = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    base.update(headers)
    req = urllib.request.Request(MCP_URL, data=body, headers=base, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def _parse_jsonrpc(body: str) -> dict | None:
    """Extract the first JSON-RPC object from a JSON or SSE-framed body."""
    body = body.strip()
    if not body:
        return None
    # SSE: pull the payload from the first `data:` line.
    if body.startswith("event:") or "\ndata:" in body or body.startswith("data:"):
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _handshake_and_list_tools(auth_headers: dict) -> tuple[bool, list[str], str]:
    """Run initialize -> initialized -> tools/list. Returns (ok, tool_names, detail)."""
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "loopback-auth-spike", "version": "0.1"},
        },
    }
    status, resp_headers, body = _post(auth_headers, init)
    if status == 401:
        return False, [], "401 Unauthorized (auth rejected)"
    if status >= 400:
        return False, [], f"HTTP {status}: {body[:200]}"

    # Carry the MCP session id through the rest of the handshake if provided.
    session_id = resp_headers.get("Mcp-Session-Id") or resp_headers.get("mcp-session-id")
    session_headers = dict(auth_headers)
    if session_id:
        session_headers["Mcp-Session-Id"] = session_id

    _post(session_headers, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    status, _, body = _post(
        session_headers, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    )
    if status >= 400:
        return False, [], f"tools/list HTTP {status}: {body[:200]}"
    parsed = _parse_jsonrpc(body)
    if not parsed or "result" not in parsed:
        return False, [], f"unexpected tools/list response: {body[:200]}"
    tools = [t.get("name", "?") for t in parsed["result"].get("tools", [])]
    return (len(tools) > 0), tools, f"{len(tools)} tools"


def _unauth_probe() -> int:
    """No token available: confirm the endpoint and its auth challenge."""
    print(f"[probe] No token in env. Probing {MCP_URL} unauthenticated...")
    status, headers, body = _post(
        {}, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    print(f"        status            = {status}")
    print(f"        www-authenticate  = {headers.get('WWW-Authenticate', '(none)')}")
    print(f"        body              = {body[:120].strip()}")
    if status == 401:
        challenge = headers.get("WWW-Authenticate")
        if challenge:
            print(
                "\n  Endpoint demands OAuth (WWW-Authenticate present). Headless PAT may NOT work -"
            )
            print("  plan for the mcp-remote proxy or community-server fallback.")
        else:
            print("\n  Endpoint rejects like a standard /api/v4/ route (no OAuth challenge).")
            print("  => Strong signal a PAT via `Authorization: Bearer` will authenticate.")
        print(
            "\n  NEXT: create a PAT on your GitLab Ultimate trial (scope `mcp` and/or `api`), then:"
        )
        print("        GITLAB_TOKEN=glpat-... python scripts/auth_spike.py")
        return 2
    if 200 <= status < 300:
        print("\n  Endpoint answered WITHOUT auth (unexpected) - inspect the body above.")
        return 2
    return 2


def main() -> int:
    print(f"=== Loopback GitLab Duo MCP auth spike ===\n    target: {MCP_URL}\n")

    candidates: list[tuple[str, dict]] = []
    if PAT:
        candidates.append(("PAT as Authorization: Bearer", {"Authorization": f"Bearer {PAT}"}))
        candidates.append(("PAT as PRIVATE-TOKEN", {"PRIVATE-TOKEN": PAT}))
    if OAUTH_TOKEN:
        candidates.append(
            ("OAuth token as Authorization: Bearer", {"Authorization": f"Bearer {OAUTH_TOKEN}"})
        )

    if not candidates:
        try:
            return _unauth_probe()
        except urllib.error.URLError as e:
            print(f"[error] cannot reach {MCP_URL}: {e}")
            return 3

    for label, headers in candidates:
        print(f"[try ] {label}")
        try:
            ok, tools, detail = _handshake_and_list_tools(headers)
        except urllib.error.URLError as e:
            print(f"       network error: {e}\n")
            return 3
        if ok:
            print(f"       OK - {detail}")
            print(f"       tools: {', '.join(sorted(tools))}\n")
            print("=== VERDICT: HEADLESS AUTH WORKS. Official Duo MCP server is GO. ===")
            for needed in ("create_issue", "create_workitem_note", "search", "get_issue"):
                mark = "yes" if needed in tools else "MISSING"
                print(f"    - {needed:22s} {mark}")
            return 0
        print(f"       no - {detail}\n")

    print("=== VERDICT: headless auth FAILED on all token paths. ===")
    print("    Per the plan, the spike is hard-boxed to one day. If it is end of Day 2,")
    print("    fall to the community PAT-based GitLab MCP server and proceed - no further")
    print("    attempts on the official server.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
