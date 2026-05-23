# Loopback

**Voice-of-Customer → GitLab agent.** Loopback ingests a batch of customer feedback,
clusters it into recurring themes ranked by frequency × severity, drafts well-scoped GitLab
issues for the top themes, **pauses for explicit human approval**, and — only on approval —
creates the issues in GitLab (with labels and related-issue links) via the **GitLab Duo MCP
server**.

Built for the **Rapid Agent Hackathon** (GitLab track) with the Google **Agent Development
Kit (ADK)** + **Gemini**, deployed to **Vertex AI Agent Engine**, fronted by a **Cloud Run**
web UI.

> The human-in-the-loop approval gate is central: the agent never writes to GitLab without
> a person approving the drafted issues first.

## How it works
```
ingest → cluster → rank → search existing → draft → ⏸ HUMAN APPROVAL → create in GitLab
```
The approval gate is an ADK `LongRunningFunctionTool`: the agent run pauses before any
GitLab write and resumes only when the human approves from the UI.

## Repo layout
| Path | What |
|---|---|
| `agent/` | ADK agent definition + step graph + prompts |
| `tools/` | ingest, clustering, drafting, approval, GitLab MCP client |
| `server/` | FastAPI service (Cloud Run) + Agent Engine deploy script |
| `web/` | Next.js review UI |
| `data/` | sample feedback dataset |
| `scripts/` | `auth_spike.py`, `demo_run.py` |
| `tests/` | per-tool smoke tests |

See **`PLAN.md`** for the full plan and **`CLAUDE.md`** for working conventions.

## Quick start (dev)
```bash
python scripts/auth_spike.py     # verify GitLab MCP auth (set GITLAB_TOKEN first)
pytest tests/                    # smoke tests
```

## License
MIT — see `LICENSE`.
