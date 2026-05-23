# Loopback — Phase-0 Plan (APPROVED)

> Voice-of-Customer → GitLab agent. Rapid Agent Hackathon, GitLab track.
> Deadline: 11 June 2026, 2:00pm PDT. Solo build. Approved 2026-05-23.

## Day-3 OUTCOME (resolved)
The official Duo MCP server **failed** the hard-boxed auth gate: `/api/v4/mcp` returns
`404` for PAT auth (token valid everywhere else; the endpoint requires an OAuth `mcp`
scope a PAT can't hold). Enabling group beta features did not change it. Per decision 1
we pivoted to the community **`@zereight/mcp-gitlab`** server (HTTP remote-auth,
`PRIVATE-TOKEN` per request) and the Day-3 smoke test is **green against the real trial
project** (create → label-via-note → search → read-back → close, all via MCP).
**Submission framing:** describe this honestly as a "GitLab MCP server integration"
(community server) — not "GitLab Duo MCP." Still a genuine, multi-call MCP partner surface.

## Approved decisions (locked)
1. **Official GitLab Duo MCP server first.** The Day-2 auth spike is **hard-boxed to one
   day**. If headless auth is not working by end of Day 2, fall to the
   **community PAT-based GitLab MCP server** (e.g. `zereight/gitlab-mcp`) and proceed —
   **no further attempts** on the official server. → *Outcome: pivoted to community (above).*
2. **Labels & relations via GitLab quick actions in a note** (`create_workitem_note` with
   `/label ~x`, `/relate #n`). Keeps the integration 100% MCP-only.
3. Runtime: **Agent Engine** (ADK + Gemini) as the agent runtime; **Cloud Run** hosts the
   Next.js UI. Model: **`gemini-2.5-flash`**, `location="global"`.
4. **LLM-based thematic clustering** is primary; embeddings are the scale fallback.
5. **MongoDB Atlas is optional/stretch** (signal store + embedding dedup). Submit to the
   GitLab track only.

## Two findings that reshaped the original concept
- **The official Duo MCP server is create-and-read only** — no `update_issue`, no
  apply-labels tool, no link-MR tool. Resolved by quick-actions-in-notes (decision 2) and
  by having the agent run `search` itself for duplicate/related detection. This keeps
  CLAUDE.md's "MCP only, never raw REST" rule intact and makes the agent's reasoning more
  impressive, not less.
- **Auth is the #1 risk.** Docs describe browser-interactive OAuth (DCR) for IDE clients.
  But empirically (2026-05-23) `https://gitlab.com/api/v4/mcp` returns a plain GitLab
  `401` with **no `WWW-Authenticate` OAuth challenge** — it rejects like the rest of
  `/api/v4/`, which strongly suggests a **PAT via `Authorization: Bearer`** authenticates
  headlessly. The Day-2 spike confirms this against the trial token.

## GitLab MCP — tools we use (community `@zereight/mcp-gitlab`, verified live)
| Need | Tool | Notes |
|---|---|---|
| Create issue | `create_issue` | args: project_id, title, description, labels[] |
| Apply labels | `create_issue_note` → `/label ~x` | MCP-native quick action (verified applies) |
| Relate issues | `create_issue_note` → `/relate #n` | MCP-native quick action |
| Find duplicates/related | `list_issues` (search, scope=all) | agent runs pre-draft |
| List/create labels | `list_labels` / `create_label` | suggested labels are real |
| Read back / close | `get_issue` / `create_issue_note` → `/close` | demo verification + cleanup |

- Endpoint: `http://127.0.0.1:3002/mcp` locally (override `MCP_SERVER_URL`); run the
  server in streamable-HTTP **remote-auth** mode; client sends PAT as `PRIVATE-TOKEN`.
- Deploy: community server as its own Cloud Run service/sidecar; agent's `McpToolset`
  connects over HTTP. PAT scope `api` (writes) is sufficient; no GitLab beta config needed.

## Architecture
```
[Next.js UI on Cloud Run]  — upload signals · review drafts · approve/reject · step log
        │ HTTPS
        ▼
[Loopback agent on Vertex AI Agent Engine]  — ADK + gemini-2.5-flash
   ingest → cluster → rank → search_existing → draft → ⏸ APPROVAL GATE → create
        │ McpToolset over HTTP
        ▼
[GitLab Duo MCP  /api/v4/mcp]   ← auth decided by Day-2 spike
```
- Approval gate = ADK `LongRunningFunctionTool` + `tool_context.request_confirmation()`:
  the runner pauses before `create_issue`, resumes on the human's decision from the UI.

## Agent step graph + tool signatures
```
ingest → cluster_and_rank → search_existing → draft_issues → ⏸approval⏸ → create_in_gitlab
```
```python
def load_signals(source: str) -> dict          # → {"signals":[{id,text,channel,date}]}
def cluster_and_rank(signals: list) -> dict     # → {"themes":[{id,label,quotes[],freq,severity,score}]}
def search_existing(theme_label: str) -> dict   # MCP search → {"related_issues":[], "related_mrs":[]}
def draft_issues(themes: list, related: dict) -> dict
    # → {"drafts":[{title,body,repro_steps,evidence_quotes[],labels[],priority,remediation,related[]}]}
def request_approval(drafts: list) -> dict       # LongRunningFunctionTool → {"status":"pending","batch_id"}
def create_in_gitlab(approved_drafts: list) -> dict
    # per draft: create_issue → create_workitem_note(/label,/relate) → get_issue → {"created":[{iid,url}]}
```

## Day-by-day (19 days; e2e demoable by Day 9)
| Days | Goal |
|---|---|
| 0–1 | Console setup. **Submit GCP credits form TODAY** (1–5 day wait). GitLab Ultimate trial + Duo + beta features + default namespace. Devpost + Discord. |
| 2 | Repo scaffold + CLAUDE.md. **`scripts/auth_spike.py` — prove headless MCP auth + introspect `tools/list`.** Hard-boxed: go/no-go on official server by EOD. |
| 3 | `gitlab_mcp.py`: create_issue + note(/label,/relate) + search; smoke tests green against trial project. |
| 4–6 | `load_signals` + `cluster_and_rank` + `draft_issues`. Build `sample_feedback.csv`. |
| 7–9 | ADK step graph + approval gate. **Full ingest→draft→approve→create loop e2e. Demoable checkpoint.** |
| 10–12 | Next.js UI: upload, review drafts, approve/reject, visible step log. |
| 13–14 | Deploy agent → Agent Engine; UI → Cloud Run. Secret Manager. Error handling. |
| 15–16 | Record + edit 3-min video. Devpost write-up. |
| 17 | **Pivot gate: check gallery. If GitLab overcrowded + MongoDB thin, re-point clustering at Atlas Vector Search. Decide today.** |
| 18 | Buffer / fix. Verify submission checklist (esp. MIT LICENSE in About). |
| 19 | Submit with margin. Not at 2pm. |

## Top 3 risks + fallbacks
1. **Headless MCP auth.** Spike order: (a) PAT as `Authorization: Bearer` (now the leading
   candidate — see findings); else (b) `mcp-remote` proxy on Cloud Run holding a once-obtained
   OAuth token in Secret Manager; else (c) **community PAT server fallback** (decision 1). One day max.
2. **Create-only tool surface.** Mitigated by quick-actions-in-notes (decision 2); verify
   `/label` & `/relate` fire via `create_workitem_note` on Day 2. Fallback: one documented
   REST call for labeling.
3. **Model/runtime drift.** Pin `gemini-2.5-flash` (GA, global) + MCP over HTTP (no stdio in
   Agent Engine). Fallback: `adk deploy cloud_run` (own container) if Agent Engine fights us.

## Console setup you must do yourself
1. **Google Cloud:** create account → submit $100 credits form NOW (1–5 business days) →
   enable Agent Platform (Vertex AI) API + Cloud Storage → staging GCS bucket →
   grant *Agent Platform User* + *Storage Admin* → `gcloud auth login` + `gcloud auth application-default login`.
2. **GitLab:** 30-day **Ultimate** trial → enable **GitLab Duo** → **"Beta and experimental
   features" ON** → set **default Duo namespace** → create the demo project.
3. **MongoDB Atlas (optional):** free cluster, only if we pursue the stretch.
4. **Devpost:** register, select **GitLab** challenge. **Discord:** join; attend "Secure AI
   Agent Deployment with GitLab and Gemini" (26 May).

## Submission checklist (disqualification-grade)
- [ ] Hosted public URL works for a logged-out stranger
- [ ] Public GitHub repo
- [ ] MIT LICENSE detectable in the repo About section
- [ ] ~3-min demo video (public/unlisted)
- [ ] GitLab challenge selected on the form
- [ ] Devpost form complete
- [ ] Demonstrably runs on Gemini + Agent Builder, uses the GitLab MCP server
- [ ] Submitted with margin before 11 June 2:00pm PDT
