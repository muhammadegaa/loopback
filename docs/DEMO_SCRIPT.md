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
- GitLab demo project is in a "mixed" state — the cleanup script (see below)
  closed and deleted the top duplicates so the next run produces a mix of
  **new issues created** and **existing issues extended**.
- Confirm the live app's hero reads: *"The agent that pauses before every GitLab write."*
- The sample CSV is wired to the "try sample feedback" button (Helix dataset, 298 signals).

**Gate latency to expect:** ~60-65s end to end (the classifier added ~25s for
the read-and-classify step). Plan the recording to compress that span — see
"production tip" notes inline.

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
actually read."*

**Production tip:** speed-ramp this span 2-3× during edit. The voiceover stays at
normal cadence; the screen is sped up. Add a small "⏩ sped up 2.5×" caption.

---

## 0:50 – 1:15 — The Classifier Agent beat *(the new headline)*

🎥 New line lands in the activity panel:
**Classifier Agent** — *"classified 23 duplicate, 0 regression, 2 related, 3
unrelated candidates across 11 themes. 11 theme(s) will extend existing tickets;
0 flagged as regressions."*

🎙️ *"This is the move. The Classifier Agent reads each candidate's title and full
description and decides what it IS — duplicate, regression, related, or
unrelated — with a confidence score and a one-line reason that cites something
specific. The agent isn't matching titles; it's reasoning about content. And
when it finds a strong open duplicate, it decides not to file a new ticket."*

---

## 1:15 – 1:35 — Triage Router routes to three lanes

🎥 **Triage Router Agent** log line: *"routed 11 drafts — X high-confidence ready
for one-click approve; Y need your judgment; Z will extend existing tickets
instead of creating new."* (X/Y/Z depend on the project state.)

Drafts arrive below in three visual lanes:
- **High-confidence** cards: clean, no left rule
- **Needs-your-judgment** cards: amber left rule + amber chip
- **Extend-existing** cards: indigo left rule + indigo chip `extends #N`, with a
  read-only preview of the comment that will be posted instead

🎙️ *"The Triage Router Agent splits the work into three lanes: ready, needs my
judgment, and extend an existing ticket. That third lane is where the multi-agent
system earns its name — the agent decided some of this work already has a home in
GitLab, and recommended a comment instead of a duplicate."*

---

## 1:35 – 1:55 — Drafts read like proper tickets

🎥 Click a **High-confidence** card to expand its details. The body renders with
clean section headers: `Problem`, `Evidence` (three blockquoted customer quotes),
`Repro`, `Expected`, `Suggested fix`, `Acceptance criteria`. Labels are in
convention: `kind::bug`, `area::auth`, `priority::p1`, `customer-pain::high`.

🎙️ *"Every ticket reads like a senior engineer wrote it. Action-first title.
Sectioned body: Problem, Evidence, Repro, Expected, Suggested fix, Acceptance
criteria. Evidence quotes are spliced in deterministically — verbatim from the
customer reports, never rewritten by the model. Labels follow the team's
convention. Priority is derived from severity, not estimated."*

---

## 1:55 – 2:20 — Approval beat: edit one, override one, ⌘↵

🎥 (a) Edit the title of one card — the amber left rule lands; `edited by you`
chip lights up. (b) On one extend-lane card, click `Override → file as new issue
instead` — the card flips to a standard card. (c) Press `⌘ + Enter`. The
Approval Gate Agent log line lands.

🎙️ *"I'm in command. I can edit any draft — that becomes my co-authored ticket. I
can override the agent's extend recommendation if I want a fresh issue instead. The
gate isn't a rubber stamp. Cmd-Enter approves the batch."*

---

## 2:20 – 2:45 — GitLab Writer Agent fires (mixed create + extend)

🎥 Activity panel shows tool calls in real time:
- `create_issue (labels [kind::bug, area::auth, priority::p1] applied)` → new
  iid + URL
- `link_work_items: related #N to M existing`
- `create_workitem_note on #87: extended with new evidence` (the extend-lane
  call — uses a different MCP tool than the new ones)
- `get_issue #N: labels verified`

🎙️ *"The GitLab Writer Agent dispatches by lane. New ones use create_issue with
labels applied at creation. Extends use create_workitem_note — posting a comment
to the existing ticket, not a duplicate. Related issues are linked with
link_work_items, the first-class work-item relation, not a slash-relate quick
action. Every call verified by reading the issue back."*

---

## 2:45 – 3:00 — Verification in real GitLab

🎥 Switch tabs to https://gitlab.com/egg-labs-group/loopback-demo/-/issues. New
issues at the top of the list. Click one of the extended tickets and scroll to
the latest comment — the agent's evidence summary is visible. Switch back to
Loopback's done state: split list shows "New issues created" and "Existing
issues extended" with the impact chip:
*"From 298 signals → N created · M extended · ~170 filtered · K linked."*

🎙️ *"From 298 messy customer signals to N properly-scoped engineering tickets, M
existing tickets extended with new evidence, all in about a minute — with the
human in command of every external write. Loopback."*

---

## If a beat overruns

Cut from longest beat first, in this order:
1. **1:35 – 1:55** (proper-ticket walkthrough) — can be 10 seconds instead of 20.
2. **0:15 – 0:50** (eight-specialist narration) — 25 seconds instead of 35.
3. **2:45 – 3:00** (verification) — minimum 12 seconds; do not cut below.

**Non-negotiable beats:**
- Trigger (0:00)
- Classifier Agent line (0:50–1:15) — **the new headline**
- Three-lane routing visible (1:15–1:35)
- Approval (1:55–2:20)
- MCP writes firing (2:20–2:45) — must show BOTH create_issue and
  create_workitem_note
- GitLab verification (2:45–end)

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

The exact numbers depend on what's in the GitLab demo project when you record,
because the Classifier Agent decides extend-vs-new based on what already exists.

After running the cleanup script (`scripts/cleanup_demo_project.py`), expect:
- 11 themes total
- ~5-6 new issues created
- ~5-6 existing issues extended
- 23+ duplicate verdicts logged by the classifier
- 0 regressions (no closed issues in the project unless seeded)

If the project hasn't been cleaned recently, expect more extends and fewer new
creates. The story still lands — "the agent decided not to file because every
theme already has a home" is a strong narrative — but the verification beat
(2:45) is weaker without a fresh-create to point at.
