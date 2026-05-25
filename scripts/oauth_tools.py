#!/usr/bin/env python3
"""Dump full input schemas for the official GitLab MCP tools Loopback will use.

Reuses the access token saved by `oauth_spike.py` (`.oauth_token.json`, valid ~2h),
so it does not re-open the browser. Run `oauth_spike.py` first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BASE_URL = "https://gitlab.com"
MCP_URL = f"{BASE_URL}/api/v4/mcp"
PROTOCOL_VERSION = "2025-06-18"
TOKEN_FILE = Path(__file__).parent.parent / ".oauth_token.json"
WANT = (
    "create_issue",
    "create_workitem_note",
    "link_work_items",
    "search",
    "search_labels",
    "get_issue",
)


def _parse(text: str) -> dict | None:
    text = text.strip()
    if text.startswith(("event:", "data:")) or "\ndata:" in text:
        for line in text.splitlines():
            if line.strip().startswith("data:"):
                try:
                    return json.loads(line.strip()[5:].strip())
                except json.JSONDecodeError:
                    continue
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def main() -> int:
    if not TOKEN_FILE.exists():
        print("No .oauth_token.json — run scripts/oauth_spike.py first.")
        return 1
    token = json.loads(TOKEN_FILE.read_text())["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    with httpx.Client(timeout=30) as c:
        init = c.post(
            MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "loopback-schema-dump", "version": "0.1"},
                },
            },
        )
        sid = init.headers.get("mcp-session-id") or init.headers.get("Mcp-Session-Id")
        if sid:
            headers["Mcp-Session-Id"] = sid
        c.post(MCP_URL, headers=headers,
               json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        r = c.post(MCP_URL, headers=headers,
                   json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    parsed = _parse(r.text)
    if not parsed or "result" not in parsed:
        print(f"tools/list failed: {r.status_code} {r.text[:300]}")
        return 1
    by_name = {t["name"]: t for t in parsed["result"]["tools"]}
    for name in WANT:
        t = by_name.get(name)
        print(f"\n### {name}  {'(MISSING)' if not t else ''}")
        if not t:
            continue
        print(f"  desc: {(t.get('description') or '').strip()[:200]}")
        schema = t.get("inputSchema", {}) or {}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        for k, v in props.items():
            star = "*" if k in required else " "
            typ = v.get("type", v.get("anyOf", "?"))
            desc = (v.get("description") or "").strip()[:80]
            print(f"    {star}{k} ({typ}): {desc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
