#!/usr/bin/env bash
# Container entrypoint: start the GitLab MCP server, then the API (which also serves
# the static UI). The MCP server runs in remote-auth mode — the API sends the GitLab
# PAT (from Secret Manager, via the GITLAB_TOKEN env) as a PRIVATE-TOKEN per request.
set -euo pipefail

STREAMABLE_HTTP=true REMOTE_AUTHORIZATION=true \
  GITLAB_API_URL="${GITLAB_API_URL:-https://gitlab.com/api/v4}" \
  HOST=127.0.0.1 PORT=3002 \
  mcp-gitlab &

# Wait for the MCP server to accept connections (best-effort; the API also tolerates it being late).
for _ in $(seq 1 30); do
  if curl -sS -o /dev/null "http://127.0.0.1:3002/mcp" 2>/dev/null; then
    echo "mcp-gitlab is up on :3002"
    break
  fi
  sleep 1
done

# Cloud Run provides $PORT. The API mounts the static UI at / and the API at /api/*.
exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8080}"
