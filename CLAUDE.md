# Loopback — Voice-of-Customer → GitLab Agent

## What this is
An agent built with the **Google Agent Development Kit (ADK / the Agent Builder framework)**,
deployed on **Cloud Run**, powered by **Gemini 3**, that converts batches of customer feedback
into approved, well-scoped GitLab issues via **GitLab's official MCP server**
(`gitlab.com/api/v4/mcp`, authenticated with OAuth 2.0; see below). Submission for the Rapid
Agent Hackathon (GitLab track). Judged on: Technical Implementation, Design, Potential Impact,
Quality of Idea. See `PLAN.md` for the approved plan and timeline.

## Architecture (do not deviate without updating this file)
- `agent/` — ADK agent definition (`root_agent`) + step graph + prompts (Python).
- `tools/` — tool implementations: `ingest`, `clustering`, `drafting`,
  `gitlab_mcp` (the official-server MCP client wrapper), `gitlab_oauth` (OAuth token manager).
- `server/` — FastAPI service (Cloud Run) exposing the agent + approval API + the static UI.
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
- ADK (Python 3.11+), model `gemini-3-flash-preview` (set via `GEMINI_MODEL`), with an
  automatic GA fallback to `gemini-2.5-flash` if the preview is ever unavailable (see
  `tools/llm.py`). Use `location="global"` (2.5+/3 models are global-endpoint-only).
- MCP via ADK `McpToolset` over **HTTP** (`StreamableHTTPConnectionParams`) — never stdio
  inside the container.
- Cloud Run for the UI + custom backend; Secret Manager for all secrets.
- MongoDB Atlas is **optional/stretch** — do not let it block the core loop.

## GitLab MCP server (OFFICIAL — switched on OAuth, verified live May 25)
- We use **GitLab's official MCP server** at `https://gitlab.com/api/v4/mcp` (override with
  `MCP_SERVER_URL`). Auth is **OAuth 2.0** — a PAT 404s here (PAT support is open issue
  #586184). Loopback is human-in-the-loop, so a one-time browser authorization is fine:
  `scripts/oauth_spike.py` does OAuth 2.0 Dynamic Client Registration + PKCE once and writes
  `.oauth_token.json` (access + refresh + client_id + token_endpoint). `tools/gitlab_oauth.py`
  refreshes the access token headlessly; the client sends `Authorization: Bearer <token>`.
  In the container the token lives in Secret Manager and rotated tokens are written back
  (`GITLAB_OAUTH_SECRET_RESOURCE`) so it survives the judging window.
- Tools (verified live): `create_issue` (id, title, description, `labels`=CSV — **labels are
  auto-created + applied at creation**), `get_issue` (id, issue_iid), `search`
  (scope="issues", search, project_id) → `{"items":[...]}` (items carry both `iid` and the
  global `id`), `link_work_items` (work_item_iid, work_items_ids=`gid://gitlab/WorkItem/<id>`,
  link_type), `create_workitem_note`. Also: merge-request + pipeline tools.
- **The official server REJECTS quick actions in notes** ("commands starting with /"). So:
  apply labels at **creation** (`create_issue` `labels`), and relate via the first-class
  **`link_work_items`** (needs the target's global `id`, which `search`/`get_issue` return).
  There is **no** `create_label`/`list_labels`/`update_issue`/close tool — don't reach for them.
- **Deploy:** no MCP sidecar — the agent connects straight to `gitlab.com/api/v4/mcp` over
  HTTPS with the OAuth Bearer header. (Historical: the Day-2 PAT 404 finding lives in
  `scripts/auth_spike.py`; the community `@zereight/mcp-gitlab` server was an interim path,
  now retired in favor of the official server.)

## Conventions
- Type hints everywhere, `ruff` clean.
- Secrets only via Google Secret Manager — never hardcode keys, never commit `.env`.
- All GitLab actions go through the GitLab MCP client wrapper (`tools/gitlab_mcp.py`),
  never raw API calls, so the MCP integration is the demonstrable partner surface. Labels are
  set at issue creation and relations use `link_work_items` — both first-class official-server
  tools, so no REST fallback is needed.
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
1. One-time OAuth: `.venv/bin/python scripts/oauth_spike.py` (browser → `.oauth_token.json`).
2. API: `.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000` (reads `.env` +
   `.oauth_token.json`; the agent calls the official MCP server directly — no local server).
3. UI: `npm --prefix web run dev` → http://localhost:3000.
The UI (`web/`, Next.js 16 — see `web/AGENTS.md`, it differs from older Next) calls the
API only; the API holds all secrets and runs the agent in a worker thread so the step log
streams while blocking Gemini/MCP calls run. The approval pause is real and held server-side.

## Deploy (Cloud Run)
One Python container (`Dockerfile`) runs the API + built static UI → one public URL; the
agent talks directly to GitLab's official MCP server over HTTPS (no MCP sidecar, no Node at
runtime). `next.config.ts` uses `output: "export"`; the API serves `web/out` at `/` and the
API at `/api/*` (same origin). Only secret is the GitLab OAuth token (Secret Manager — read
and rotated-write via `GITLAB_OAUTH_SECRET_RESOURCE`); Gemini runs on the deploy project via
the Cloud Run service account (Vertex/ADC), no key. Pin `google-genai<2` (google-adk 2.1's
range). Run model needs a single always-on instance (`--no-cpu-throttling --min-instances=1
--max-instances=1`) since run state is in-memory and the agent runs in a background thread.
Full steps: `DEPLOY.md`.

## Verification
- After any tool change: run `.venv/bin/python tests/test_gitlab_mcp.py` (offline units +
  live smoke) and report pass/fail before moving on. (pytest isn't installed; tests self-run.)
- After any agent-flow change: run `scripts/demo_run.py` against the sample dataset and
  confirm issues appear in the GitLab demo project.
- MCP auth: `scripts/oauth_spike.py` must authenticate and list the official server's tools;
  `scripts/verify_wrapper.py` exercises create→relate→search→verify end to end.

## Definition of done (submission)
- Hosted public URL works for a stranger.
- Public GitHub repo with MIT LICENSE file detectable in the About section.
- 3-minute demo video recorded.
- Devpost form complete, GitLab challenge selected.
