# Loopback - locked 3-minute demo script

**Status:** canonical script for the Rapid Agent Hackathon submission video.
Supersedes the prior single-batch lock - this version is keyed to the
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
the live run is weekly-batch only - it has the richest spread (four regression
flags, two extends, one high-confidence ready-to-file, eleven needs-review)
and the highest PII-redaction count (14 signals touched).

**Legend:** Each beat has two blocks:
- **SHOW** - what to do on screen (clicks, things to watch for). Numbered.
- **SAY** - exact words to read aloud. Pre-sized to fit the time budget at ~150 words/min natural narration pace.

Read SAY out loud; glance at SHOW for the clicks. Don't memorise - read.

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

6. **Have your gate questions ready** - for the recording, the question
   you ask should be specific to the regression-flagged card. The two
   that work well (verified live):
   - First: *"why isn't this a new ticket?"* (lets the agent quote the
     classifier reason)
   - Follow-up: *"what should I check first?"* (lets the agent
     suggest a concrete next step)
   Type them slowly enough that the viewer reads the question on screen.

---

## 0:00 – 0:15 - Setup (15s)

**SHOW**
1. Loopback landing page on screen. Amber "Human-approved by design" chip + hero **"The agent that pauses before every GitLab write."**
2. Cursor lingers on the three-batch picker (First week · Weekly batch · Post-incident) for 2 seconds.
3. Click **Weekly batch**.

**SAY** (~37 words)
> Loopback turns messy customer feedback into approved GitLab issues. Built on Google's Agent Development Kit, Gemini 3 on Cloud Run, integrating GitLab's official MCP server. Today: one chaotic week - 298 customer messages for Helix, a fictional AI coding assistant.

---

## 0:15 – 0:50 - Eight specialists run (35s)

**SHOW**
1. Upload starts. Dark agent activity panel on the right begins filling, line by line.
2. Triage bar on the left animates: **298 → 174 actionable → 14 themes**.
3. Specialist lines land in order: Signal Ingestion → Theme Clustering → Duplicate-Check.
4. **Speed-ramp this span 2-2.5× in edit.** Voiceover stays at normal pace. Add a small "sped up 2.5×" caption.

**SAY** (~83 words)
> Eight named specialists run in sequence. The Signal Ingestion Agent reads 298 messages from in-app, Discord, GitHub, Twitter, email, and Reddit, and redacts PII before anything touches the model - emails, phones, even pasted API keys and bearer tokens. The Theme Clustering Agent groups the actionable signal into themes. The Duplicate-Check Agent connects to GitLab's official MCP server over OAuth and reads the full description of every candidate issue it finds - so the next step reasons about content, not titles.

---

## 0:50 – 1:20 - The Classifier headline (30s)

**SHOW**
1. New log line lands in the dark terminal - **Classifier Agent**: *"classified candidates across themes in one batched Gemini call. 2 themes will extend existing tickets; 4 flagged as regressions. Decision: declined to extend #116 - closed, fix didn't hold - flagged as possible regression."*
2. **Zoom in on the phrase** *"declined to extend ... flagged as possible regression"*. Hold the zoom for 2 seconds.

**SAY** (~74 words)
> This is the move. The Classifier Agent reads every candidate's full description and decides what it IS - duplicate, regression, related, or unrelated - with a confidence score and a one-line reason. Watch the decision: it found a ticket that matched the model-regression theme, but that ticket was closed last sprint. So it declined to extend it. The fix didn't hold. That gets flagged as a possible regression. That's agency, not autocomplete.

---

## 1:20 – 1:45 - Triage Router: four lanes light up (25s)

**SHOW**
1. **Triage Router Agent** log line in the terminal: *"routed 14 drafts - 1 high-confidence; 11 flagged for your judgment; 2 will extend existing."*
2. Cards arrive below with four visually distinct lane treatments:
   - **4 RED bands** ("Flagged as possible regression of #N") with "Agent reasoning" quote inside the card
   - **1 GREEN band** ("Ready for one-click approve") - destructive agent actions
   - **2 INDIGO bands** ("Will extend existing issue #N") - SSO → #115, hallucination → #113
   - A faint divider **`Long tail · 11 for your judgment`** lands, then 11 amber-ruled review cards drop into a 2-col grid below.

**SAY** (~58 words)
> Fourteen themes. Four different agent decisions in one batch. One strong enough to file immediately. Two are duplicates of tickets already on the backlog - extend, not duplicate. Four are regressions of closed issues - fixes that didn't hold. Eleven want a PM's call. That's real triage.

---

## 1:45 – 2:05 - Drafts read like proper engineering tickets (20s)

**SHOW**
1. Click **`Show details`** on the HIGH card (the one with the green band).
2. Body expands with section headers in order: `Problem` · `Evidence` (3 blockquoted customer quotes) · `Repro` · `Expected` · `Suggested fix` · `Acceptance criteria`.
3. Labels at the bottom: `kind::bug`, `area::agent-behavior`, `priority::p0`, `customer-pain::high`.

**SAY** (~45 words)
> Every draft reads like a senior engineer wrote it. Action-first title. Sectioned body. Evidence quotes spliced in deterministically - verbatim from the customer reports, never rewritten by the model. Labels follow convention. Priority derived from severity. These are the tickets I'd file myself.

---

## 2:05 – 2:35 - Pause, ask, decide (30s) **- the agentic centerpiece**

**SHOW**
1. On the **regression-flagged card** (red band reads "Flagged as possible regression of #116"), click **`Ask the agent`** at the top-right of the card (next to the green `✓ Approved` toggle).
2. Inline chat slides open below the card. **Type slowly**: `why isn't this a new ticket?`
3. Hit Enter. Wait ~2 seconds for the agent's reply to arrive. **HOLD HERE - let the viewer read.**
4. Quick follow-up, no need to close the chat: `what should I check first?` Hit Enter. Hold another beat for the answer.
5. Click **Close**.
6. (Optional) Edit one HIGH card's title - amber `edited by you` chip lights up.
7. Press **⌘ + ↵** (or Ctrl+Enter).
8. Dark terminal log line lands: *"All drafted issues were approved for creation."*

**SAY** (~74 words)
> This is the agentic move. Before a single GitLab write, I can interrogate any draft. The agent answers from the same data it used to decide - classifier reasoning, customer quotes, the matched closed issue. I can edit any field; it becomes my co-authored ticket. I can override, I can reject - and the agent remembers. The pause is real. The agent and I make the call together. Command-Enter.

**Production tip**: hold ~2 seconds on the agent's first answer before typing the follow-up. The pause sells the read.

---

## 2:35 – 2:55 - GitLab Writer Agent fires (20s)

**SHOW**
Activity panel streams real MCP tool calls in this order:
1. `create_issue (labels [...] applied)` × multiple times - labels appear on screen at creation
2. `## Possible regression of #116` block visible in a created body
3. `link_work_items: related #N to existing #116`
4. `create_workitem_note on #115: extended with new evidence` × 2 (the extends)
5. `get_issue: labels verified` after each create

**SAY** (~48 words)
> The GitLab Writer Agent dispatches by lane. Some drafts go through `create_issue` - labels at creation, regression flags embedded in the body, work items linked via `link_work_items`. Others go through `create_workitem_note` - extending existing tickets instead of duplicating. Every call verified by reading back through `get_issue`.

---

## 2:55 – 3:00 - Verification in GitLab (5s)

**SHOW**
1. Quick tab switch to `https://gitlab.com/egg-labs-group/loopback-demo/-/issues`.
2. Pan once across: (a) new issues at the top, one with a visible `## Possible regression of #116` block, (b) seed #115 (the extended SSO issue) with Loopback's fresh posted comment.

**SAY** (~22 words - the closing line; the words ride the tab switch, voiceover ends as the screen lands on the issue list)
> 298 messy signals to a triaged decision in two minutes. Agent did the homework. Human kept command. Loopback.

---

## If a beat overruns

Cut from longest beat first, in this order:

1. **0:15 - 0:50** (eight specialists) - can be 25 seconds. The speed-ramp
   carries the narration.
2. **1:45 - 2:05** (proper-ticket walkthrough) - can be 10 seconds; show
   only the section headings sliding in.
3. **2:55 - 3:00** (verification) - minimum 5 seconds; do not cut below.
4. **2:05 - 2:35** (ask + decide) - the second question can be cut;
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
  2:35). This is the agentic centerpiece - agent and PM deciding
  together, not the agent making decisions alone.
- MCP writes firing must include BOTH `create_issue` AND
  `create_workitem_note` AND a `## Possible regression of` block visible
  on screen (2:35 - 2:55).
- GitLab verification showing both a new issue AND an extended issue's
  posted comment (2:55 - end).

---

## Stack name-drops to land on screen or in voiceover

Each must be heard or seen at least once:

- **Gemini 3** (`gemini-3-flash-preview` on Vertex AI - `location=global`)
- **Agent Development Kit** (ADK) / **Google Cloud Agent Builder**
- **Cloud Run** (single-instance Python container, no MCP sidecar)
- **GitLab Official MCP server** (`gitlab.com/api/v4/mcp`)
- **OAuth 2.0** (Dynamic Client Registration + PKCE; token rotation via
  Secret Manager)
- **`create_issue`** · **`create_workitem_note`** · **`link_work_items`** ·
  **`get_issue`** - call them by name in the writer-fires beat (2:35 -
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
shooting again - the seed has drifted.

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
`scripts/seed_demo.py` (it's idempotent - only fills in what's missing).

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

Reuse these verbatim - they match what's on screen and back the rubric
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
  draft. The GitLab Writer Agent dispatches by lane - create_issue,
  create_workitem_note, or link_work_items for regression flags.
- **What I learned:** the moves that turn an LLM with tools into a real
  agent are (a) bidirectional MCP - reading the system of record before
  writing, (b) a real, server-held human pause that the agent and the UI
  both treat as load-bearing, (c) deterministic data flow through session
  state rather than the LLM as a bulk-arg bus, and (d) classifying
  candidates against full content rather than matching titles. Each one
  shows up on screen in the video.
