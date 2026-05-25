#!/usr/bin/env python3
"""OAuth spike for the OFFICIAL GitLab MCP server (`/api/v4/mcp`).

The Day-2 spike proved a PAT 404s here: this endpoint speaks OAuth 2.0, not PAT
(GitLab issue #586184 — PAT support is still open). But Loopback is human-in-the-loop
by design, so a ONE-TIME browser OAuth is fully compatible: a human authorizes once,
we capture the refresh token, and the agent runs headless thereafter.

This spike answers the two questions that decide whether we switch off the community
server onto GitLab's own MCP server:

  1. Can we authenticate to https://gitlab.com/api/v4/mcp via OAuth and list tools?
  2. Does the official server expose the WRITE tools Loopback needs
     (create issue, apply labels, relate issues, search, get issue)?

FLOW (standard MCP OAuth 2.1):
  probe MCP (401) -> protected-resource metadata -> auth-server metadata
  -> Dynamic Client Registration (RFC 7591) -> PKCE authorize (browser, one click)
  -> token exchange -> MCP initialize + tools/list (Bearer).

On success it writes the tokens to `.oauth_token.json` (gitignored) and prints how to
feed the access token to the agent's HTTP McpToolset.

USAGE
    .venv/bin/python scripts/oauth_spike.py
    # custom host / pre-registered client:
    GITLAB_BASE_URL=https://gitlab.example.com \
    GITLAB_OAUTH_CLIENT_ID=... .venv/bin/python scripts/oauth_spike.py

EXIT CODES
    0  authenticated and listed >=1 tool  (switch is viable)
    2  authenticated but missing write tools  (keep community server)
    3  auth / discovery / network failure
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

BASE_URL = os.environ.get("GITLAB_BASE_URL", "https://gitlab.com").rstrip("/")
MCP_URL = f"{BASE_URL}/api/v4/mcp"
PROTOCOL_VERSION = "2025-06-18"
CALLBACK_PORT = int(os.environ.get("OAUTH_CALLBACK_PORT", "7777"))
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
TOKEN_FILE = Path(__file__).parent.parent / ".oauth_token.json"
TIMEOUT = 30
# Tools Loopback's pipeline needs; names are guesses across known GitLab MCP surfaces.
NEEDED = {
    "create issue": ("create_issue", "create_work_item", "create_workitem"),
    "apply labels": ("update_issue", "create_issue_note", "create_work_item_note", "add_label"),
    "relate issues": ("create_issue_link", "create_issue_note", "relate_issue"),
    "search issues": ("list_issues", "search", "get_issues", "list_work_items"),
    "get issue": ("get_issue", "get_work_item"),
}


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False)


def _parse_jsonrpc(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith(("event:", "data:")) or "\ndata:" in text:
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


def discover(http_client: httpx.Client) -> dict:
    """Probe the MCP endpoint and resolve the OAuth authorization-server metadata."""
    print(f"[1/6] Probing {MCP_URL} (expect 401 with an OAuth challenge)...")
    r = http_client.post(
        MCP_URL,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    print(f"      status={r.status_code}  "
          f"www-authenticate={r.headers.get('WWW-Authenticate', '(none)')}")

    # Resolve protected-resource metadata (from the challenge, else the well-known URL).
    resource_meta_url = None
    challenge = r.headers.get("WWW-Authenticate", "")
    if "resource_metadata=" in challenge:
        resource_meta_url = challenge.split('resource_metadata="', 1)[1].split('"', 1)[0]
    if not resource_meta_url:
        resource_meta_url = f"{BASE_URL}/.well-known/oauth-protected-resource"

    auth_server = BASE_URL
    scopes = ["mcp"]
    try:
        rm = http_client.get(resource_meta_url, headers={"Accept": "application/json"})
        if rm.status_code < 400:
            meta = rm.json()
            servers = meta.get("authorization_servers") or []
            if servers:
                auth_server = servers[0].rstrip("/")
            if meta.get("scopes_supported"):
                scopes = meta["scopes_supported"]
            print(f"      protected-resource: auth_server={auth_server} scopes={scopes}")
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        print(f"      (protected-resource metadata unavailable: {e}; using defaults)")

    # Authorization-server metadata (RFC 8414).
    for wk in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
        try:
            am = http_client.get(f"{auth_server}{wk}", headers={"Accept": "application/json"})
            if am.status_code < 400:
                m = am.json()
                m["_scopes"] = scopes
                print(f"      auth-server metadata via {wk}")
                return m
        except (httpx.HTTPError, json.JSONDecodeError):
            continue

    # Fallback to GitLab's conventional OAuth endpoints.
    print("      (no discovery doc; falling back to /oauth/{authorize,token,register})")
    return {
        "authorization_endpoint": f"{auth_server}/oauth/authorize",
        "token_endpoint": f"{auth_server}/oauth/token",
        "registration_endpoint": f"{auth_server}/oauth/register",
        "_scopes": scopes,
    }


def register_client(http_client: httpx.Client, meta: dict) -> str:
    """Dynamic Client Registration (RFC 7591); fall back to a pre-registered client_id."""
    preset = os.environ.get("GITLAB_OAUTH_CLIENT_ID")
    if preset:
        print(f"[2/6] Using preset GITLAB_OAUTH_CLIENT_ID={preset[:8]}...")
        return preset
    reg = meta.get("registration_endpoint")
    if not reg:
        _fail_manual_app()
    print(f"[2/6] Dynamic client registration at {reg} ...")
    try:
        r = http_client.post(
            reg,
            headers={"Content-Type": "application/json"},
            json={
                "client_name": "Loopback (hackathon spike)",
                "redirect_uris": [REDIRECT_URI],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "scope": " ".join(meta.get("_scopes", ["mcp"])),
            },
        )
    except httpx.HTTPError as e:
        print(f"      DCR network error: {e}")
        _fail_manual_app()
    if r.status_code >= 400:
        print(f"      DCR rejected (HTTP {r.status_code}): {r.text[:200]}")
        _fail_manual_app()
    client_id = r.json().get("client_id")
    print(f"      registered client_id={client_id[:8]}...")
    return client_id


def _fail_manual_app() -> None:
    print(
        "\n  Dynamic registration unavailable. Create an OAuth app manually instead:\n"
        f"    GitLab -> Settings -> Applications -> Add new application\n"
        f"      Redirect URI: {REDIRECT_URI}\n"
        f"      Scopes: mcp (and api)\n"
        f"    Then re-run: GITLAB_OAUTH_CLIENT_ID=<id> .venv/bin/python scripts/oauth_spike.py\n"
    )
    sys.exit(3)


def authorize(meta: dict, client_id: str) -> tuple[str, str]:
    """Run the PKCE authorization-code flow; returns (code, code_verifier)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(meta.get("_scopes", ["mcp"])),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{meta['authorization_endpoint']}?{urllib.parse.urlencode(params)}"

    captured: dict[str, str] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            captured.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            ok = "code" in captured and captured.get("state") == state
            msg = "Authorized — return to the terminal." if ok else "Authorization failed."
            self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())
            done.set()

        def log_message(self, *_: object) -> None:
            pass

    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print(f"[3/6] Opening browser for one-time authorization on {BASE_URL} ...")
    print(f"      If it doesn't open, paste this URL:\n      {auth_url}\n")
    webbrowser.open(auth_url)
    print("      Waiting for you to click Authorize...")
    if not done.wait(timeout=300):
        print("      timed out waiting for authorization.")
        sys.exit(3)
    server.shutdown()

    if "code" not in captured:
        print(f"      no code returned: {captured}")
        sys.exit(3)
    if captured.get("state") != state:
        print("      state mismatch — aborting.")
        sys.exit(3)
    print("      got authorization code.")
    return captured["code"], verifier


def exchange(
    http_client: httpx.Client, meta: dict, client_id: str, code: str, verifier: str
) -> dict:
    print("[4/6] Exchanging code for tokens...")
    r = http_client.post(
        meta["token_endpoint"],
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    if r.status_code >= 400:
        print(f"      token exchange failed (HTTP {r.status_code}): {r.text[:300]}")
        sys.exit(3)
    tok = r.json()
    if "access_token" not in tok:
        print(f"      no access_token in response: {tok}")
        sys.exit(3)
    print(f"      got access_token (expires_in={tok.get('expires_in')}, "
          f"refresh_token={'yes' if tok.get('refresh_token') else 'no'})")
    return tok


def list_tools(http_client: httpx.Client, access_token: str) -> list[dict]:
    print(f"[5/6] MCP handshake + tools/list against {MCP_URL} ...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    init = http_client.post(
        MCP_URL,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "loopback-oauth-spike", "version": "0.1"},
            },
        },
    )
    if init.status_code >= 400:
        print(f"      initialize failed (HTTP {init.status_code}): {init.text[:300]}")
        sys.exit(3)
    sid = init.headers.get("mcp-session-id") or init.headers.get("Mcp-Session-Id")
    if sid:
        headers["Mcp-Session-Id"] = sid
    http_client.post(
        MCP_URL, headers=headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    )
    r = http_client.post(
        MCP_URL, headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    parsed = _parse_jsonrpc(r.text)
    if not parsed or "result" not in parsed:
        print(f"      tools/list returned no result: {r.text[:300]}")
        sys.exit(3)
    return parsed["result"].get("tools", [])


def main() -> int:
    print(f"=== Loopback OFFICIAL GitLab MCP OAuth spike ===\n    target: {MCP_URL}\n")
    with _client() as http_client:
        try:
            meta = discover(http_client)
            client_id = register_client(http_client, meta)
            code, verifier = authorize(meta, client_id)
            tok = exchange(http_client, meta, client_id, code, verifier)
            tools = list_tools(http_client, tok["access_token"])
        except httpx.HTTPError as e:
            print(f"\n[error] network failure: {e}")
            return 3

    names = sorted(t.get("name", "?") for t in tools)
    print(f"\n[6/6] Official server exposes {len(names)} tools:\n      {', '.join(names)}\n")

    print("=== Can Loopback's pipeline run on the official server? ===")
    have = set(names)
    all_ok = True
    for need, candidates in NEEDED.items():
        hit = next((c for c in candidates if c in have), None)
        status = f"-> {hit}" if hit else f"MISSING (tried: {', '.join(candidates)})"
        print(f"    {need:14s} {status}")
        if not hit:
            all_ok = False

    # Persist what the token manager needs to refresh headlessly later.
    tok["client_id"] = client_id
    tok["token_endpoint"] = meta["token_endpoint"]
    TOKEN_FILE.write_text(json.dumps(tok, indent=2))
    print(f"\n    tokens saved to {TOKEN_FILE} (gitignored).")
    print("    Wire the agent's HTTP McpToolset with:")
    print(f'      url="{MCP_URL}", headers={{"Authorization": "Bearer <access_token>"}}')

    if all_ok:
        print("\n=== VERDICT: SWITCH IS VIABLE. Official server has every tool Loopback needs. ===")
        return 0
    print("\n=== VERDICT: official server is missing write tools above. ===")
    print("    Keep the community server, but document this spike as the honest reason.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
