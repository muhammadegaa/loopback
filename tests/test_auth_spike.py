"""Smoke test: the auth spike imports and its parsers behave. (No network.)"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "auth_spike", Path(__file__).parent.parent / "scripts" / "auth_spike.py"
)
auth_spike = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(auth_spike)


def test_parse_plain_json():
    body = '{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"create_issue"}]}}'
    parsed = auth_spike._parse_jsonrpc(body)
    assert parsed["result"]["tools"][0]["name"] == "create_issue"


def test_parse_sse_framed():
    body = 'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"tools":[]}}\n\n'
    parsed = auth_spike._parse_jsonrpc(body)
    assert parsed["result"]["tools"] == []


def test_parse_empty():
    assert auth_spike._parse_jsonrpc("") is None


def test_mcp_url_built():
    assert auth_spike.MCP_URL.endswith("/api/v4/mcp")
