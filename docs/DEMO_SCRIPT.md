# Loopback — locked 3-minute demo script

**Status:** canonical lock for the Rapid Agent Hackathon submission video. Supersedes
`docs/VIDEO_SCRIPT.md` (kept as historical reference).

**Format:** screen recording of the live app + voiceover. Target 2:55, hard cap 3:00.
**Demo runs against:** the live Cloud Run URL
`https://loopback-182683404521.us-central1.run.app` recording on Chrome (incognito).
**Resolution:** 1920×1080. Hide the bookmark bar. Two tabs open and ready:
1. Loopback (the app).
2. The GitLab demo project at https://gitlab.com/egg-labs-group/loopback-demo/-/issues.

**Pre-recording checklist:**
- GitLab demo project has open issues that match every theme — verified.
  The classifier will route ALL 11 themes to `extend_existing`. The demo
  story is the agent's restraint: it decided not to file anything new.
- If you accidentally over-cleaned the project (no candidates to extend),
  the demo will file fresh issues instead and lose the headline beat.
  Re-seed by running a previous demo run end to end before re-recording.
- Hit `POST /api/admin/clear-learning` once before recording so the
  "learns your no's" loop is fresh and won't filter themes from prior runs.
- Confirm the live app's hero reads: *"The agent that pauses before every GitLab write."*
- The sample CSV is wired to the "try sample feedback" button (Helix dataset, 298 signals).

**Gate latency to expect:** ~100-110s end to end. The classifier reads ~18
candidate descriptions and runs a Gemini verdict call per theme. This is the
real cost of the bidirectional MCP work and it's worth showing.

The recording strategy is to use that span — don't compress it away. The
activity panel scrolling past the eight specialists IS the demo. Slow your
voiceover, name the work, let the agent be visibly thinking.

**Legend:** 🎥 = shot / on-screen · 🎙️ = voiceover.

---

## 0:00 – 0:15 — Trigger

🎥 Loopback landing page. Amber `Human-approved by design` chip and hero
**"The agent that pauses before every GitLab write."** Click `try it with sample
feedback →`.

🎙️ *"This is one chaotic week of customer feedback for Helix — a fictional AI coding
assistant. The kind of feedback every AI startup is drowning in: hallucination loops,
an agent that ran rm-rf without asking, a model regression, plus the usual SSO and
billing pain. Loopback is the multi-agent system that triages it — on Google Cloud's
Agent Development Kit, Gemini 3 on Vertex AI, GitLab's official MCP server."*

---

## 0:15 – 0:50 — Eight named specialists, real reasoning

🎥 The agent activity panel on the right fills with named specialists, in order:
- **Signal Ingestion Agent** — "redacted 14 signals carrying emails, phones, API keys"
- **Theme Clustering Agent** — "11 themes from ~120 actionable signals; ignored ~170
  as non-actionable noise"
- **Duplicate-Check Agent** — "connected to gitlab.com/api/v4/mcp — 18 tools
  discovered. Searched and fetched full content for 28 candidates via get_issue"
- **Classifier Agent** *(NEW)* — "classified 23 duplicate, 0 regression, 2 related,
  3 unrelated"

On the left: triage bar animates up — 298 signals analyzed → ~170 ignored as noise
→ 11 themes.

🎙️ *"Eight named specialists run in sequence. The Signal Ingestion Agent reads 298
messages from in-app, Discord, GitHub, Twitter, email, and Reddit, and redacts PII
before anything touches the model — including pasted API keys. The Theme Clustering
Agent groups the actionable signal. The Duplicate-Check Agent connects to GitLab's
official MCP server over OAuth and — critically — reads the full content of every
candidate it finds. Eighteen GitLab tools discovered. Twenty-eight candidate issues
actually read. Every Gemini call is wrapped in exponential-backoff retry, so a
single 429 from Vertex AI doesn't kill the run."*

**Production tip:** speed-ramp this span 2-3× during edit. The voiceover stays at
normal cadence; the screen is sped up. Add a small "⏩ sped up 2.5×" caption.

---

## 0:50 – 1:20 — The Classifier Agent beat *(the headline)*

🎥 New line lands in the activity panel:
**Classifier Agent** — *"classified 13 duplicate, 0 regression, 1 related, 4
unrelated candidates across 11 themes. 11 theme(s) will extend existing tickets;
0 flagged as regressions."*

🎙️ *"This is the move. The Classifier Agent reads each candidate's title and full
description and decides what it IS — duplicate, regression, related, or
unrelated — with a confidence score and a one-line reason that cites something
specific. The agent isn't matching titles; it's reasoning about content. And
look at what it decided: every single theme already has a home in GitLab.
Eleven duplicates found. Zero new issues warranted."*

---

## 1:20 – 1:40 — Triage Router: eleven extends, zero creates

🎥 **Triage Router Agent** log line: *"routed 11 drafts — 0 high-confidence
ready for one-click approve; 0 need your judgment; 11 will extend existing
tickets instead of creating new."*

Eleven cards arrive below, all with the indigo left rule and the `extends #N`
chip. Each card shows the read-only preview of the comment the agent will post.

🎙️ *"The Triage Router has three lanes: ready, needs my judgment, extend an
existing ticket. Today every theme landed in the third lane. That is the
strongest possible agentic behavior — the agent's most impressive move was
restraint."*

---

## 1:40 – 2:00 — Drafts read like proper tickets

🎥 Click any extend card to expand its details. The body renders with clean
section headers: `Problem`, `Evidence` (three blockquoted customer quotes),
`Repro`, `Expected`, `Suggested fix`, `Acceptance criteria`. Labels: `kind::bug`,
`area::auth`, `priority::p1`, `customer-pain::high`.

🎙️ *"The drafts read like a senior engineer wrote them. Action-first title.
Sectioned body: Problem, Evidence, Repro, Expected, Suggested fix, Acceptance
criteria. Evidence quotes are spliced in deterministically, verbatim from the
customer reports, never rewritten by the model. Labels follow convention.
Priority derived from severity, not estimated. These drafts wouldn't actually
be filed today, but the work product is on record."*

---

## 2:00 – 2:25 — Approval: edit one, override one to file fresh, ⌘↵

🎥 (a) Edit the title of one card — the amber left rule lands; `edited by you`
chip lights up. (b) On a different extend card, click
`Override → file as new issue instead` — the card flips to a standard `needs
your judgment` card. (c) Press `⌘ + Enter`. The Approval Gate Agent log line
lands.

🎙️ *"I'm in command. I can edit any draft — that becomes my co-authored ticket.
I can override the agent's extend recommendation if I want a fresh issue
instead, like for this one. The gate isn't a rubber stamp. Cmd-Enter approves
the batch."*

---

## 2:25 – 2:50 — GitLab Writer Agent fires: ten extends + one create

🎥 Activity panel shows tool calls in real time:
- `create_workitem_note on #87: extended with new evidence (not filed as new
  issue)` × 10 (with the iids varying)
- `create_issue (labels [kind::bug, ...] applied)` × 1 (the override)
- `link_work_items: related #N to M existing` for the new create
- `get_issue: labels verified` after each call

🎙️ *"The GitLab Writer Agent dispatches by lane. Ten extends use
create_workitem_note — posting a comment to the existing ticket, not a
duplicate. The one I overrode uses create_issue with labels applied at
creation. link_work_items is the first-class work-item relation, not a
slash-relate quick action. Every call verified by reading the issue back."*

---

## 2:50 – 3:00 — Verification in real GitLab

🎥 Switch tabs to https://gitlab.com/egg-labs-group/loopback-demo/-/issues.
Click into the SSO issue (the one the agent extended). Scroll to the latest
comment — Loopback's posted evidence summary is visible (the bolded count,
three blockquoted customer quotes, severity/frequency/confidence footer).
Switch back to Loopback's done state: split list reads
"1 issue created · 10 existing issues extended." Impact chip:
*"From 298 signals → 1 created · 10 extended instead of duplicated · 124 filtered · M linked."*

🎙️ *"Ten existing tickets extended with new customer evidence. One fresh issue
filed because I overrode the agent. The agent's most impressive move was
deciding not to duplicate. Loopback."*

---

## If a beat overruns

Cut from longest beat first, in this order:
1. **1:40 – 2:00** (proper-ticket walkthrough) — can be 10 seconds instead of 20.
2. **0:15 – 0:50** (eight-specialist narration) — 25 seconds instead of 35.
3. **2:50 – 3:00** (verification) — minimum 10 seconds; do not cut below.

**Non-negotiable beats:**
- Trigger (0:00)
- Classifier Agent line (0:50–1:20) — **the headline**
- Triage Router showing "11 will extend existing" (1:20–1:40)
- Approval beat including the one override (2:00–2:25)
- MCP writes firing (2:25–2:50) — must show BOTH create_workitem_note (multiple
  times) AND create_issue (once, the override)
- GitLab verification — clicking into an extended issue and showing the comment
  (2:50–end)

Lose any of those and the demo loses a rubric axis.

## Stack name-drops to land on screen or in voiceover

Each must be heard or seen at least once:
- **Gemini 3** (Vertex AI)
- **ADK** / **Agent Development Kit**
- **Cloud Run**
- **GitLab Official MCP server**
- **OAuth 2.0**
- **create_issue**, **create_workitem_note**, **link_work_items**, **get_issue** —
  call them by name in the writer-fires beat.

## What the visible counts will be

Verified live as of last practice run (revision loopback-00020-* on the date
the script was locked):

- 298 signals → 14 PII-redacted (6 emails, 2 phones, 6 URLs)
- 11 themes from 174 actionable signals; 124 ignored as non-actionable noise
- 18 candidate issues fetched via `get_issue`
- Classifier: 13 duplicate, 0 regression, 1 related, 4 unrelated
- Triage Router: 0 high · 0 needs_review · **11 extend_existing**
- After approval (one human override to file-new):
  10 `create_workitem_note` calls + 1 `create_issue` call
- Done state: 1 created · 10 extended

If the GitLab project state drifts (more issues deleted, more rehearsal runs
seeding new ones), the breakdown will shift. The non-negotiable count is the
Classifier's "11 themes will extend existing tickets" line — that's the
story. If you don't see at least 8 extends, the project has been
over-cleaned. Re-seed by running a previous demo end to end before
recording.

## How to reset the project between rehearsals

Two things can drift between rehearsal runs and break the demo:

1. **The GitLab project fills with new duplicates.** Each end-to-end rehearsal
   adds 1 fresh issue (the override) + 10 extension comments. Over several
   rehearsals the project bloats with create-issue-from-override iids. Not
   harmful to the demo per se, but the verification tab gets visually noisy.
   Fix: run `scripts/cleanup_demo_project.py --dry-run` to see what would be
   removed, then re-run without `--dry-run`.

2. **The "learns your no's" rejection memory accumulates.** If you reject
   themes during a rehearsal (instead of approving the batch), those themes
   get filtered on the next run with the same source filename. Hit
   `POST /api/admin/clear-learning` to reset.

Pre-recording recipe:
```bash
# 1. Clear the rejection memory
curl -sS -X POST https://loopback-182683404521.us-central1.run.app/api/admin/clear-learning

# 2. Verify GitLab project still has 10+ matching issues (dry-run, no changes)
.venv/bin/python scripts/cleanup_demo_project.py --dry-run
```
