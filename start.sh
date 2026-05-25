#!/usr/bin/env bash
# Container entrypoint: start the API (which also serves the static UI).
# The agent talks DIRECTLY to GitLab's OFFICIAL MCP server (gitlab.com/api/v4/mcp)
# over HTTPS using an OAuth token (GITLAB_OAUTH_TOKEN_JSON from Secret Manager,
# refreshed in-process). No MCP sidecar, no Node at runtime.
set -euo pipefail

# Cloud Run provides $PORT. The API mounts the static UI at / and the API at /api/*.
exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8080}"
