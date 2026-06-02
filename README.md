# Loopback

**The agent that pauses before every GitLab write.**

Loopback is a multi-agent system on Google's Agent Development Kit. It triages a batch
of customer feedback into approved, well-scoped GitLab issues, with a real server-held
human-in-the-loop pause before any external write. PII is masked before any model call
(emails, phone numbers, URLs, API keys). Every approval, rejection, and edit is logged.

**Live demo:** https://loopback-182683404521.us-central1.run.app
The demo dataset is one chaotic week of customer feedback for **Helix**, a fictional
B2B AI coding assistant — 298 messages across in-app, Discord, GitHub, Twitter, email,
Reddit. Hallucination loops, model regressions, irreversible agent actions, token cost
surprises, plus the usual SSO and billing pain.

**Submission track:** Rapid Agent Hackathon — GitLab
**License:** MIT (see `LICENSE`)

## Stack

- **Agent runtime:** Google ADK (Python 3.11+), `SequentialAgent` with seven named
  specialists, one of them a real routing decision.
- **Model:** Gemini 3 (`gemini-3-flash-preview`) on Vertex AI, with a Gemini 2.5 GA
  fallback.
- **GitLab integration:** GitLab's **official MCP server** at
  `https://gitlab.com/api/v4/mcp`, authenticated via OAuth 2.0 (Dynamic Client Registration
  + PKCE). No raw REST. The agent uses `create_issue` (labels applied at creation),
  `search`, `link_work_items` (first-class work-item relation, not a slash-relate quick
  action), and `get_issue`.
- **Server:** FastAPI on Cloud Run. Single always-on instance keeps the run state and the
  resumable App alive across the human pause.
- **UI:** Next.js 16 (App Router) + Tailwind v4, static-exported and served same-origin.

## The agent graph

Seven named specialists in sequence; the Triage Router Agent is the visible branching
decision that turns this into a real multi-agent system.

```
Signal Ingestion Agent       (PII redaction + parse CSV)
    │
Theme Clustering Agent       (Gemini cluster, deterministic rank by frequency × severity)
    │
Duplicate-Check Agent        (search existing GitLab issues via MCP)
    │
Issue Drafting Agent         (Gemini draft per theme, with evidence quotes + repro)
    │
Triage Router Agent          (lane assignment: high-confidence vs needs-review)
    │
Approval Gate Agent          (LlmAgent + request_confirmation; server-held pause)
    │
GitLab Writer Agent          (create_issue, link_work_items, get_issue via MCP)
```

The four deterministic data steps pass signals/themes/drafts through session state — never
through the LLM as bulk args, so ranking is stable across runs. The Approval Gate Agent
pauses the run via `tool_context.request_confirmation()` inside a resumable `App`, so
GitLab writes only happen on an explicit human decision.

## Trust posture, by construction

- **PII redacted server-side** in `tools/redact.py` (emails, phone numbers, URLs) before
  any signal reaches clustering, drafting, the model, or the UI.
- **Zero GitLab writes without your approval.** The pause is real — the run blocks
  server-side at `request_confirmation`, in a resumable App.
- **Every decision logged.** The done state exposes a full decision log: every approval,
  rejection, edit, and creation with timestamps.
- **Learns your no's.** Per-source rejection memory (`tools/learning.py`) persists rejected
  theme fingerprints; the next run on the same source filters matching themes before
  drafting.
- **Refresh-survives-pause.** The run ID lives in `?run=<id>`, so a panel refresh during
  the pause resumes the same in-memory run.

## Demo

The locked 3-minute video script is in **`docs/DEMO_SCRIPT.md`** with second-by-second
timing for the submission.

## Run locally

One-time GitLab OAuth:
```bash
.venv/bin/python scripts/oauth_spike.py     # opens browser, writes .oauth_token.json
```

Smoke tests:
```bash
.venv/bin/python tests/test_gitlab_mcp.py   # offline units + live MCP smoke
.venv/bin/python scripts/demo_run.py        # full ingest → approve → create flow
```

Web app (two terminals):
```bash
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000
npm --prefix web run dev                    # http://localhost:3000
```

See **`docs/RUN_LOCAL.md`** for the full local setup and **`DEPLOY.md`** for the Cloud Run
deploy steps.

## Repo layout

| Path | What |
|---|---|
| `agent/agent.py` | ADK agent definition — the seven specialists and the resumable App |
| `tools/redact.py` | PII redaction (emails, phones, URLs) |
| `tools/ingest.py` | CSV load + validation, calls redact |
| `tools/clustering.py` | Gemini theme clustering, deterministic ranking, learning filter |
| `tools/drafting.py` | Gemini issue drafting per theme |
| `tools/learning.py` | Per-source rejection memory (learns your no's) |
| `tools/gitlab_mcp.py` | Official MCP client wrapper — `create_issue`, `search`, `link_work_items`, `get_issue` |
| `tools/gitlab_oauth.py` | OAuth token manager (refresh + Secret Manager rotation) |
| `server/main.py` | FastAPI service: agent runner, approval API, static UI mount |
| `web/app/page.tsx` | Review UI: upload → triage → review/approve → result |
| `data/sample_feedback.csv` | 142-message demo dataset |
| `scripts/` | `oauth_spike.py` (one-time OAuth), `verify_wrapper.py`, `demo_run.py` |
| `tests/` | per-tool smoke tests (offline + live cycle) |
| `docs/DEMO_SCRIPT.md` | Locked 3-minute video script |
| `docs/RUN_LOCAL.md` | Local setup |
| `docs/DEVPOST.md` | Devpost submission notes |
| `DEPLOY.md` | Cloud Run deploy steps |

## License

MIT — see `LICENSE`.
