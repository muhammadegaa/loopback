# Two stages: build the static UI with Node, then a slim Python runtime that serves the
# UI + runs the ADK agent/API. The agent talks directly to GitLab's OFFICIAL MCP server
# (gitlab.com/api/v4/mcp) over HTTPS via OAuth — no MCP sidecar, no Node at runtime.

# --- stage 1: build the static UI ---
FROM node:22-bookworm-slim AS ui
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Same-origin: the UI calls /api/... on the host that serves it.
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build   # next.config output:"export" -> /web/out

# --- stage 2: runtime (Python only) ---
FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

COPY agent/ ./agent/
COPY tools/ ./tools/
COPY server/ ./server/
COPY start.sh ./start.sh
COPY --from=ui /web/out ./web/out
RUN chmod +x start.sh

ENV PORT=8080
EXPOSE 8080
CMD ["./start.sh"]
