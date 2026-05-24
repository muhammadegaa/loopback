# One container: Node (community GitLab MCP server) + Python (ADK agent + API) +
# the built static UI. The deployed app holds no dependency on any laptop.

# --- stage 1: build the static UI ---
FROM node:22-bookworm-slim AS ui
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Same-origin: the UI calls /api/... on the host that serves it.
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build   # next.config output:"export" -> /web/out

# --- stage 2: runtime ---
FROM node:22-bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# the community GitLab MCP server (pinned), exposes the `mcp-gitlab` bin
RUN npm install -g @zereight/mcp-gitlab@2.1.14

WORKDIR /app
COPY requirements.txt ./
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

COPY agent/ ./agent/
COPY tools/ ./tools/
COPY server/ ./server/
COPY start.sh ./start.sh
COPY --from=ui /web/out ./web/out
RUN chmod +x start.sh

ENV GITLAB_API_URL="https://gitlab.com/api/v4" \
    MCP_SERVER_URL="http://127.0.0.1:3002/mcp" \
    PORT=8080
EXPOSE 8080
CMD ["./start.sh"]
