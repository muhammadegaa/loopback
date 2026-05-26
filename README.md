# Loopback

**Customer pain, triaged into GitLab — on the record, and only with your approval.**

Loopback is a Voice-of-Customer → GitLab agent. It ingests a batch of customer feedback,
clusters it into recurring themes ranked by **frequency × severity**, drafts well-scoped
GitLab issues for the top themes, **pauses for explicit human approval**, and — only on
approval — creates the issues in GitLab (labels applied, duplicates linked) through
**GitLab's official MCP server**.

Built for the **Rapid Agent Hackathon** (GitLab track) with Google's **Agent Development Kit
(the Agent Builder framework)** + **Gemini 3**, deployed on **Cloud Run**, integrating GitLab's
official MCP server over **OAuth 2.0**.

> **The human-in-the-loop approval gate is the point.** The agent does the tedious 90% —
> read everything, find the pattern, draft the ticket — then *stops* and hands control to a
> person. Nothing is written to GitLab until a human approves. Knowing when to stop is the
> feature.

## How it works
```
ingest → cluster → rank → search existing → draft → ⏸ HUMAN APPROVAL → create in GitLab
```
The four data steps are deterministic (the bulk feedback flows through session state, never
through the model as arguments); clustering and drafting use Gemini with schema-constrained
output. The approval gate is a **real, server-held pause** — ADK's
`tool_context.request_confirmation()` in a resumable app — that suspends the run before any
GitLab write and resumes only when a human posts an approve/reject decision.

## The GitLab integration (official MCP server, OAuth)
A genuine, multi-call partner surface against `gitlab.com/api/v4/mcp`:
`search` (find duplicates) → `create_issue` (labels auto-created at creation) →
`link_work_items` (relate duplicates, first-class) → `get_issue` (read back & verify).
Auth is OAuth 2.0: a one-time browser authorization (fitting for a human-in-the-loop tool),
then the access token refreshes headlessly. See `scripts/oauth_spike.py`.

## Repo layout
| Path | What |
|---|---|
| `agent/` | ADK agent definition + step graph + the approval gate |
| `tools/` | ingest, clustering, drafting, GitLab MCP client, OAuth token manager |
| `server/` | FastAPI service (Cloud Run) — agent + approval API + static UI |
| `web/` | Next.js review UI (upload → review/approve → result) |
| `data/` | sample feedback dataset (142 messages) |
| `scripts/` | `oauth_spike.py` (one-time OAuth), `verify_wrapper.py`, `demo_run.py` (end-to-end) |
| `tests/` | per-tool smoke tests (offline units + live cycle) |

See **`PLAN.md`** for the plan, **`CLAUDE.md`** for working conventions, **`DEPLOY.md`** to
deploy, and **`docs/RUN_LOCAL.md`** to run it locally.

## Quick start (dev)
```bash
.venv/bin/python scripts/oauth_spike.py     # one-time GitLab OAuth → .oauth_token.json
.venv/bin/python tests/test_gitlab_mcp.py   # offline units + live MCP smoke
.venv/bin/python scripts/demo_run.py        # full ingest→approve→create against GitLab
```

## License
MIT — see `LICENSE`.
