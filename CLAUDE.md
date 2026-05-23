# Loopback — Voice-of-Customer → GitLab Agent

## What this is
An agent built with the **Google Agent Development Kit (ADK)** and deployed to
**Vertex AI Agent Engine** (the Gemini Enterprise Agent Platform runtime), powered by
**Gemini**, that converts batches of customer feedback into approved, well-scoped GitLab
issues via the **GitLab Duo MCP server**. Submission for the Rapid Agent Hackathon
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
  The approval gate is mandatory and must never be bypassed. It is implemented as an ADK
  `LongRunningFunctionTool` + `tool_context.request_confirmation()` — the runner pauses
  before any GitLab write and resumes only on the human's decision.

## Stack defaults
- ADK (Python 3.11+), model `gemini-2.5-flash` (use `location="global"`; 2.5+ models are
  global-endpoint-only). `gemini-2.5-pro` only for the heaviest clustering/draft step.
- MCP via ADK `McpToolset` over **HTTP** (`StreamableHTTPConnectionParams`) — never stdio
  inside Agent Engine.
- Cloud Run for the UI + custom backend; Secret Manager for all secrets.
- MongoDB Atlas is **optional/stretch** — do not let it block the core loop.

## GitLab MCP reality (important)
- The official Duo MCP server is **create-and-read only**: `create_issue`, `get_issue`,
  `search`, `search_labels`, `create_workitem_note`, plus MR/pipeline reads. There is **no**
  `update_issue`, no apply-labels tool, no link-MR tool.
- **Apply labels and relate issues via quick actions in a note**: after `create_issue`,
  call `create_workitem_note` with a body like `/label ~bug ~priority::high` and `/relate #123`.
  This is the approved, MCP-only path. Do NOT reach for raw REST to label or relate.
- **Auth:** attempt **PAT via `Authorization: Bearer`** against `https://gitlab.com/api/v4/mcp`
  first (empirically the likely headless path). The auth spike is **hard-boxed to one day**;
  if headless auth isn't working by end of Day 2, fall to the **community PAT-based GitLab
  MCP server** and proceed — no further attempts on the official server.

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
