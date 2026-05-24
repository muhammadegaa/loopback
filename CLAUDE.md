# Loopback — Voice-of-Customer → GitLab Agent

## What this is
An agent built with the **Google Agent Development Kit (ADK)** and deployed to
**Vertex AI Agent Engine** (the Gemini Enterprise Agent Platform runtime), powered by
**Gemini**, that converts batches of customer feedback into approved, well-scoped GitLab
issues via a **GitLab MCP server** (community `@zereight/mcp-gitlab` — the official Duo
server's PAT auth was unavailable; see below). Submission for the Rapid Agent Hackathon
(GitLab track). Judged on: Technical Implementation, Design, Potential Impact, Quality of
Idea. See `PLAN.md` for the approved plan and timeline.

## Architecture (do not deviate without updating this file)
- `agent/` — ADK agent definition (`root_agent`) + step graph + prompts (Python).
- `tools/` — tool implementations: `ingest`, `clustering`, `drafting`, `approval`,
  `gitlab_mcp` (the MCP client wrapper).
- `server/` — FastAPI service (Cloud Run) exposing the agent + approval API; `deploy.py`
  pushes the agent to Agent Engine.
- `web/` — minimal Next.js UI: upload signals, review proposed issues, approve/reject,
  view the step log.
- `data/` — sample customer-feedback dataset for the demo.
- `scripts/` — `auth_spike.py` (MCP auth probe), `demo_run.py` (end-to-end).
- Agent flow is multi-step and explicit:
  `ingest → cluster → rank → search_existing → draft → HUMAN APPROVAL GATE → create-in-GitLab`.
  The approval gate is mandatory and must never be bypassed. It is implemented with
  `tool_context.request_confirmation()` inside an `LlmAgent` tool (`request_approval`),
  with the pipeline wrapped in `App(resumability_config=ResumabilityConfig(is_resumable=True))`
  so the run pauses before any GitLab write and resumes only on the human's decision.
  The four data steps are deterministic custom `BaseAgent`s (signals/themes/drafts flow
  through session state, never through the LLM as bulk args); `create_in_gitlab` strictly
  honors `approved_ids`. Note: `SequentialAgent` is deprecation-warned in ADK 2.1 (the
  successor is "Workflow") but is fully functional — keep it for now.

## Stack defaults
- ADK (Python 3.11+), model `gemini-2.5-flash` (use `location="global"`; 2.5+ models are
  global-endpoint-only). `gemini-2.5-pro` only for the heaviest clustering/draft step.
- MCP via ADK `McpToolset` over **HTTP** (`StreamableHTTPConnectionParams`) — never stdio
  inside Agent Engine.
- Cloud Run for the UI + custom backend; Secret Manager for all secrets.
- MongoDB Atlas is **optional/stretch** — do not let it block the core loop.

## GitLab MCP server (community — verified Day 3)
- The official GitLab Duo MCP server (`/api/v4/mcp`) was **abandoned per the hard-boxed
  auth rule**: it 404s for PAT auth (the endpoint requires an OAuth `mcp` scope a PAT
  cannot hold). No further attempts on it.
- We use the community **`@zereight/mcp-gitlab`** server, run in streamable-HTTP
  remote-auth mode (the client sends the PAT as a `PRIVATE-TOKEN` header per request):
  ```
  STREAMABLE_HTTP=true REMOTE_AUTHORIZATION=true GITLAB_API_URL=https://gitlab.com/api/v4 \
  HOST=127.0.0.1 PORT=3002 npx -y @zereight/mcp-gitlab
  ```
  Endpoint `http://127.0.0.1:3002/mcp` (override with `MCP_SERVER_URL`). A static
  server-side PAT is rejected in HTTP mode — auth must be per-request.
- Tools (verified live): `create_issue` (project_id, title, description, labels[]),
  `create_issue_note` (project_id, issue_iid, body), `get_issue`, `list_issues`
  (search, scope), `list_labels` / `create_label` / `delete_label`. `update_issue`,
  `create_merge_request`, `create_issue_link` also exist.
- **Apply labels and relate issues via quick actions in a note** (approved, MCP-only):
  after `create_issue`, call `create_issue_note` with `/label ~bug ~priority::high` and
  `/relate #123`. Verified working. Do NOT reach for raw REST to label or relate.
- **Deploy:** run the community server as its own Cloud Run service / sidecar container;
  the agent's `McpToolset` connects to it over HTTP with the `PRIVATE-TOKEN` header.

## Conventions
- Type hints everywhere, `ruff` clean.
- Secrets only via Google Secret Manager — never hardcode keys, never commit `.env`.
- All GitLab actions go through the GitLab MCP client wrapper (`tools/gitlab_mcp.py`),
  never raw API calls, so the MCP integration is the demonstrable partner surface.
  (The one documented exception, if quick-actions-in-notes fail verification, is a single
  REST call for labeling — flag it loudly in code if you ever need it.)
- Every tool function has a docstring stating: inputs, outputs, side effects. ADK turns the
  docstring + type hints into the tool schema, so write them for the model, not just humans.
- Web UI: TypeScript, no secrets client-side, calls the Cloud Run API only.

## Do / Don't
- DO keep the human approval gate visible and central — it is a judged design point.
- DO log every agent step so the demo and judges can see reasoning + tool calls.
- DO write a smoke test for each tool and run it before declaring a task done.
- DON'T let the agent create GitLab issues without explicit approval.
- DON'T add features outside the ingest→approve→create loop before that loop works end to
  end and is demoable.
- DON'T use raw GitLab REST calls — MCP only (see the one documented exception above).
- DON'T pin a regional endpoint for Gemini 2.5+ — use `location="global"`.

## Running locally (web demo)
1. Community GitLab MCP server: `STREAMABLE_HTTP=true REMOTE_AUTHORIZATION=true
   GITLAB_API_URL=https://gitlab.com/api/v4 HOST=127.0.0.1 PORT=3002 npx -y @zereight/mcp-gitlab`
2. API: `.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000` (reads `.env`).
3. UI: `npm --prefix web run dev` → http://localhost:3000.
The UI (`web/`, Next.js 16 — see `web/AGENTS.md`, it differs from older Next) calls the
API only; the API holds all secrets and runs the agent in a worker thread so the step log
streams while blocking Gemini/MCP calls run. The approval pause is real and held server-side.

## Verification
- After any tool change: run `pytest tests/` and report pass/fail before moving on.
- After any agent-flow change: run `scripts/demo_run.py` against the sample dataset and
  confirm issues appear in the GitLab trial project.
- MCP auth: `python scripts/auth_spike.py` must list real tools from the server before the
  GitLab client wrapper is considered working.

## Definition of done (submission)
- Hosted public URL works for a stranger.
- Public GitHub repo with MIT LICENSE file detectable in the About section.
- 3-minute demo video recorded.
- Devpost form complete, GitLab challenge selected.
