# Loopback — locked 3-minute demo script

**Status:** canonical script for the Rapid Agent Hackathon submission video.
Supersedes the prior single-batch lock — this version is keyed to the
three-batch sample picker and the live rehearsal numbers (see "Visible counts"
below; nine pipeline runs were measured before locking, decisions identical
across successful runs).

**Format:** screen recording of the live app + voiceover. Target 2:55, hard
cap 3:00.

**Recording URL:** `https://loopback-182683404521.us-central1.run.app` on
Chrome (incognito). 1920x1080, bookmark bar hidden, two tabs open:
1. Loopback (the app).
2. GitLab demo project: `https://gitlab.com/egg-labs-group/loopback-demo/-/issues`.

**Recorded batch:** `weekly-batch.csv` (298 signals). The first-week and
post-incident batches are visible in the picker on the landing screen so the
viewer understands the same agent produces different decisions per batch, but
the live run is weekly-batch only — it has the richest spread (four regression
flags, two extends, one high-confidence ready-to-file, eleven needs-review)
and the highest PII-redaction count (14 signals touched).

**Legend:** `[shot]` = on-screen action. `[VO]` = voiceover.

---

## Pre-recording checklist

1. Run the reset so GitLab is at the seed state and learning memory is fresh:
   ```bash
   .venv/bin/python scripts/reset_demo.py
   ```
   Expected output ends: `OK -- seed restored`. The project should now hold
   3 open seed issues (#113-#115) + 3 closed seed issues (#116-#118), no
   non-seed issues, no rejection-memory files. If any non-seed issues remain,
   re-run.

2. Do **one warm-up run** in incognito (upload weekly-batch, click through to
   done, do not record). This pre-warms the Cloud Run instance + Vertex AI
   quota lane. Two of nine rehearsal runs hit a transient classifier error;
   the warm-up makes the recorded take far more reliable. After the warm-up
   re-run `reset_demo.py` once more.

3. Confirm the live app's hero reads: **"The agent that pauses before every
   GitLab write."** Confirm the sample picker shows three chips: First week ·
   Weekly batch · Post-incident.

4. Hide cursor when not interacting. Disable Chrome notifications.

5. **Warm up the `/ask` route** before the real take. Run a sample,
   reach the **gate** (the amber "paused for your approval" ribbon),
   click "Ask the agent" on any card, ask one trivial question
   (e.g. "why this priority?"), see the answer come back. This
   pre-warms the Gemini connection on the Cloud Run instance so the
   on-camera ask answers in under 2 seconds. Then approve through
   to done, run `scripts/reset_demo.py`, and start the real take.

6. **Have your gate questions ready** — for the recording, the question
   you ask should be specific to the regression-flagged card. The two
   that work well (verified live):
   - First: *"why isn't this a new ticket?"* (lets the agent quote the
     classifier reason)
   - Follow-up: *"what should I check first?"* (lets the agent
     suggest a concrete next step)
   Type them slowly enough that the viewer reads the question on screen.

---

## 0:00 - 0:15 — Setup

[shot] Loopback landing page. Amber "Human-approved by design" chip; hero
**"The agent that pauses before every GitLab write."** Camera lingers a beat
on the three-batch picker — First week (75 signals) · Weekly batch (298
signals) · Post-incident (100 signals). Cursor hovers Weekly batch, clicks.

[VO] *"Loopback is a multi-agent system that turns customer feedback into
approved GitLab issues. It's built with Google's Agent Development Kit on
Cloud Run, runs on Gemini 3, and integrates with GitLab's official MCP
server. Three sample batches give it three different shapes of work. Today
we'll run one chaotic week — 298 messages of customer feedback for Helix, a
fictional AI coding assistant."*

---

## 0:15 - 0:50 — Eight named specialists run

[shot] Upload starts. The activity panel on the right fills in order, each
line a real log event from the agent. Triage bar on the left animates up
to 298 -> 174 actionable -> 14 themes.

- **Signal Ingestion Agent** — *"loaded 298 signals from weekly-batch.csv.
  PII redacted: 6 emails, 2 phones, 6 URLs across 14 signals."*
- **Theme Clustering Agent** — *"14 themes from 174 actionable signals;
  ignored 124 as non-actionable noise."*
- **Duplicate-Check Agent** — *"connected to gitlab.com/api/v4/mcp (OAuth)
  — 19 tools discovered. Searched and fetched full content for several
  candidates via get_issue."*

Speed-ramp this span 2-2.5x during edit; voiceover stays at normal pace. Add
a small "sped up 2.5x" caption.

[VO] *"Eight named specialists run in sequence. The Signal Ingestion Agent
reads 298 messages from in-app, Discord, GitHub, Twitter, email, and Reddit,
and redacts PII before anything touches the model — including pasted API
keys and bearer tokens. The Theme Clustering Agent groups the actionable
signal. The Duplicate-Check Agent connects to GitLab's official MCP server
over OAuth and reads the full description of every existing issue it finds
— so the next step can reason about content, not match on titles."*

---

## 0:50 - 1:20 — The Classifier Agent beat (the headline)

[shot] New log line lands in the activity panel:

> **Classifier Agent** — *"classified candidates across themes in one batched
> Gemini call. 2 themes will extend existing tickets; 4 flagged as
> regressions. Decision: declined to extend #116 (candidate is closed —
> matching issue describes the same diff-quality regression after deploy) ->
> flagged as possible regression."*

Camera zooms on the "declined to extend ... flagged as possible regression"
phrase. Hold the zoom 2 seconds.

[VO] *"This is the move. The Classifier Agent reads each candidate's full
description and decides what it IS — duplicate, regression, related, or
unrelated — with a confidence score and a one-line reason. Watch the
decision: it found an open ticket that matched the model-regression theme,
but the matching ticket was closed last sprint. So it declined to extend
it. The fix didn't hold. That gets flagged as a possible regression, not
filed as a new ticket and not silently merged into a stale one. That's
agency, not autocomplete."*

---

## 1:20 - 1:45 — Triage Router: four lanes in one batch

[shot] **Triage Router Agent** log line: *"routed 14 drafts — 1
high-confidence ready for one-click approve; 11 flagged for your judgment;
2 will extend existing tickets instead of creating new."*

Cards arrive below in **four visual treatments**:
- One **HIGH** card (no left rule) — destructive agent actions.
- Two **EXTEND** cards (indigo left rule + `extends #N` chip) — SSO -> #115,
  hallucination -> #113.
- Four cards with a red **regression-of** chip (orthogonal to lane) — model
  regression, tool schema, latency, CLAUDE.md drift, all pointing at the
  closed seed issues.
- Eleven **REVIEW** cards (amber left rule + `needs your judgment` chip) —
  the long tail.

[VO] *"Fourteen themes. Four different agent decisions in one batch. One
strong enough to file immediately. Two are duplicates of tickets already
on the backlog, so the agent will extend them instead of creating noise.
Four are flagged as regressions of closed issues. Eleven want a PM's call
because the agent isn't confident enough to auto-route. That's real
triage."*

---

## 1:45 - 2:05 — Drafts read like proper engineering tickets

[shot] Click the **HIGH** card (destructive actions) to expand. The body
renders with clean section headers, in order: `Problem` · `Evidence` (three
blockquoted customer quotes) · `Repro` · `Expected` · `Suggested fix` ·
`Acceptance criteria`. Labels visible: `kind::bug`,
`area::agent-behavior`, `priority::p0`, `customer-pain::high`.

[VO] *"Every draft reads like a senior engineer wrote it. Action-first
title. Sectioned body. Evidence quotes spliced in deterministically,
verbatim from the customer reports — never rewritten by the model. Labels
follow convention. Priority derived from severity. These are the tickets
I'd file myself."*

---

## 2:05 - 2:35 — Pause, ask the agent, decide (the agentic beat)

The most agentic moment of the demo: at the gate, **the PM and the agent
talk before any GitLab write happens**. The agent's reasoning is grounded
in this run's data — classifier_reason, customer quotes, severity,
channels, the matched seed iid.

[shot] On the **regression-flagged** card (red band, "Flagged as possible
regression of #116"), click the small `Ask the agent` button next to the
`✓ Approved` toggle. The inline chat surface slides open below the card.
Type:

> *"why isn't this a new ticket?"*

The agent's answer streams back in 1-3 sentences, grounded in run data.
Expected response shape (verified live):

> *"Three of the 13 customer reports in this theme specifically describe
> diff quality on multi-file edits dropping after a deploy — the same
> symptom seed #116 closed on. Confidence the fix didn't hold is 0.82.
> If you approve, I'll link the new ticket to #116 and post a regression
> note. If you reject, I'll learn that signal isn't worth filing."*

[shot] Quick follow-up question without closing the chat:

> *"what should I check first?"*

The agent remembers context, answers specifically.

[shot] Close the chat. Edit the title of one HIGH card (`edited by you`
chip lights up). Press **Cmd + Enter**. The Approval Gate Agent log line
lands in the dark terminal: *"All drafted issues were approved for
creation."*

[VO] *"This is the agentic move. Before a single GitLab write, I can
interrogate every draft. The agent answers from the same data it used
to make the call — classifier reasoning, customer quotes, the matched
closed issue. I can edit any field — it becomes my co-authored ticket.
I can override the agent's extend recommendation. I can reject and the
agent remembers. The pause is real. The agent and I make the call
together. Command-Enter."*

**Production tip**: keep each question short. One question, one answer,
one short follow-up. The pause to read the agent's response is the
punchline; don't rush it.

---

## 2:35 - 2:55 — GitLab Writer Agent fires: a mixed batch lands

[shot] Activity panel shows tool calls in real time, mixing both code
paths:

- `create_issue (labels [...] applied)` for each new ticket
- `## Possible regression of #116` block embedded in regression-flagged
  bodies
- `link_work_items: related #N to existing #116` (first-class GitLab
  relation, not a quick action)
- `create_workitem_note on #115: extended with new evidence` for each
  extend
- `get_issue: labels verified` after each create

[VO] *"The GitLab Writer Agent dispatches by lane. Some drafts go through
create_issue — labels applied at creation, regression flags embedded in
the body when the classifier said so, related work items linked via
link_work_items, the first-class GitLab relation. Others go through
create_workitem_note — extending existing tickets with new customer
evidence instead of duplicating. Every call verified by reading the issue
back through get_issue."*

---

## 2:55 - 3:00 — Verification in GitLab

[shot] Quick tab switch to
`https://gitlab.com/egg-labs-group/loopback-demo/-/issues`. Pan once:
(a) new issues at the top including one with a visible
`## Possible regression of #116` block, (b) seed #115 (the extended
SSO issue) with Loopback's posted comment carrying fresh quotes.

[VO] *"298 messy customer signals to a real triage decision in under
two minutes. New tickets where new work is warranted. Extensions where
it's already tracked. Regression flags where fixes didn't hold. PM
judgment where the agent was honestly uncertain. Asked, answered,
approved, written. Loopback."*

---

## If a beat overruns

Cut from longest beat first, in this order:

1. **0:15 - 0:50** (eight specialists) — can be 25 seconds. The speed-ramp
   carries the narration.
2. **1:45 - 2:05** (proper-ticket walkthrough) — can be 10 seconds; show
   only the section headings sliding in.
3. **2:55 - 3:00** (verification) — minimum 5 seconds; do not cut below.
4. **2:05 - 2:35** (ask + decide) — the second question can be cut;
   the first question + answer + Cmd-Enter is the floor at ~22 seconds.

**Non-negotiable beats** (lose any of these and you lose a rubric axis):

- Three-batch picker visible in the setup shot (0:00 - 0:15).
- The "declined to extend ... flagged as possible regression" sentence
  zoomed (0:50 - 1:20). This is the agentic beat.
- Four-lane breakdown landing on screen (1:20 - 1:45).
- One proper-ticket body expansion showing the section structure
  (1:45 - 2:05).
- **Ask the agent AT THE GATE before the writer fires**: the PM clicks
  Ask the agent on the regression-flagged draft, asks a question grounded
  in run data, the agent answers from classifier_reason + customer
  quotes + the matched seed iid. THEN Cmd-Enter to approve (2:05 -
  2:35). This is the agentic centerpiece — agent and PM deciding
  together, not the agent making decisions alone.
- MCP writes firing must include BOTH `create_issue` AND
  `create_workitem_note` AND a `## Possible regression of` block visible
  on screen (2:35 - 2:55).
- GitLab verification showing both a new issue AND an extended issue's
  posted comment (2:55 - end).

---

## Stack name-drops to land on screen or in voiceover

Each must be heard or seen at least once:

- **Gemini 3** (`gemini-3-flash-preview` on Vertex AI — `location=global`)
- **Agent Development Kit** (ADK) / **Google Cloud Agent Builder**
- **Cloud Run** (single-instance Python container, no MCP sidecar)
- **GitLab Official MCP server** (`gitlab.com/api/v4/mcp`)
- **OAuth 2.0** (Dynamic Client Registration + PKCE; token rotation via
  Secret Manager)
- **`create_issue`** · **`create_workitem_note`** · **`link_work_items`** ·
  **`get_issue`** — call them by name in the writer-fires beat (2:35 -
  2:55).

---

## Visible counts (locked from the live rehearsal)

These are the actual numbers the live pipeline produces on `weekly-batch.csv`
against the current GitLab seed. Verified across three rehearsal runs;
decisions identical run-to-run.

| Metric | Value |
|---|---|
| Signals in | 298 |
| PII redacted | 14 signals touched (6 emails, 2 phones, 6 URLs) |
| Actionable | 174 |
| Noise ignored | 124 |
| Themes | 14 |
| Lane: high | 1 |
| Lane: needs_review | 11 |
| Lane: extend_existing | 2 (-> seed #115 SSO, -> seed #113 hallucination) |
| Regression flags | 4 (-> seed #116 model regression × 3, -> seed #117 tool schema × 1) |
| Writer: create_issue | 12 |
| Writer: create_workitem_note | 2 |
| Pre-gate wall-clock | ~80-100s |
| Done wall-clock | ~95-115s |

If the on-screen counts drift from these on a take, reset and re-run before
shooting again — the seed has drifted.

---

## Reset between takes

```bash
.venv/bin/python scripts/reset_demo.py
```

This single command deletes every non-seed issue (the rehearsal/take
fallout), restores the seed to its intended state (#113-#115 open,
#116-#118 closed), and POSTs to `/api/admin/clear-learning` to wipe the
per-source rejection memory. Takes about 5 seconds end to end. Run it
between every take.

If the reset reports `WARNING: seed manifest incomplete`, run
`scripts/seed_demo.py` (it's idempotent — only fills in what's missing).

---

## What to do with the other two batches

Don't run them live in this video. The same agent on `first-week.csv`
produces 11 creates + 1 extend (the calm-Monday beat); on
`post-incident.csv` it produces 6 high-confidence + 4 regression flags
(the post-deploy beat). Worth mentioning in the voiceover at 0:00, worth
showing in a separate 30-second cut for the project page, but not worth
the time in this 3-minute video. The weekly-batch run already shows
extend + regression + high + needs_review all firing on the same agent.

---

## Submission text bullets (for the Devpost description)

Reuse these verbatim — they match what's on screen and back the rubric
claims:

- **Built with:** Google Cloud Agent Development Kit (Python), Gemini 3
  (`gemini-3-flash-preview`) on Vertex AI, FastAPI on Cloud Run, GitLab's
  Official MCP server over OAuth 2.0 (Dynamic Client Registration + PKCE),
  Secret Manager for token rotation. UI: Next.js 16 + Tailwind v4, static
  export served same-origin by the Python container.
- **What it does:** triages a batch of customer feedback into approved
  GitLab issues. Eight named specialists. The agent pauses server-side
  via `tool_context.request_confirmation` inside a resumable App, before
  any GitLab write. The Classifier Agent reads each candidate's full
  description and decides extend / regression / related / unrelated with
  confidence and reason. The Triage Router emits one of three lanes per
  draft. The GitLab Writer Agent dispatches by lane — create_issue,
  create_workitem_note, or link_work_items for regression flags.
- **What I learned:** the moves that turn an LLM with tools into a real
  agent are (a) bidirectional MCP — reading the system of record before
  writing, (b) a real, server-held human pause that the agent and the UI
  both treat as load-bearing, (c) deterministic data flow through session
  state rather than the LLM as a bulk-arg bus, and (d) classifying
  candidates against full content rather than matching titles. Each one
  shows up on screen in the video.
