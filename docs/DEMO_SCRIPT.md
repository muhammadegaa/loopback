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
- Clean the GitLab demo project so the verification beat starts from zero issues.
- Confirm the live app's hero reads: *"The agent that pauses before every GitLab write."*
- Have `data/sample_feedback.csv` ready (loaded inline via the "try sample feedback" link).

**Legend:** 🎥 = shot / on-screen · 🎙️ = voiceover.

---

## 0:00 – 0:20 — Trigger

🎥 Loopback landing page. Amber `Human-approved by design` chip and hero
**"The agent that pauses before every GitLab write."** Click `try it with sample feedback →`.

🎙️ *"Loopback is a multi-agent system that triages customer feedback into GitLab issues —
on Google Cloud's Agent Development Kit, powered by Gemini 3 on Vertex AI, integrating
GitLab's official MCP server. The agent does the work. The human approves every external
write."*

---

## 0:20 – 1:00 — Reasoning visible · ingestion → clustering

🎥 The agent activity panel on the right starts filling. Named specialists scroll in:
**Signal Ingestion Agent** (PII redaction count visible),
**Theme Clustering Agent** (themes counted, noise filtered),
**Duplicate-Check Agent** (existing GitLab issues searched).
On the left: triage bar animates up — 142 signals analyzed → 18 ignored as noise → 6 themes.

🎙️ *"The Signal Ingestion Agent reads the batch and redacts PII before anything reaches the
model. The Theme Clustering Agent groups the actionable signal — 142 messages into 6 themes,
18 filtered as non-actionable noise. The Duplicate-Check Agent searches GitLab for existing
issues so we don't propose work that's already tracked."*

---

## 1:00 – 1:20 — Triage Router beat (the multi-agent branching)

🎥 New line lands in the agent activity panel:
**Triage Router Agent** — *"routed 6 drafts — 3 high-confidence ready for one-click approve;
3 flagged for your judgment."*
Drafts appear below. The top 3 cards render cleanly; the bottom 3 carry an amber left rule
and a `needs your judgment` chip near the priority pill.

🎙️ *"The Triage Router Agent is where the multi-agent system earns its name. It decides which
drafts are clear enough for one-click approve and which need the human to look closer —
based on rank and severity, not vibes. Three clear ones, three that need my judgment."*

---

## 1:20 – 1:40 — Drafts surfaced, why-line + MCP depth

🎥 Hover the `#1 by impact` chip on the top card (rank justification visible: frequency,
severity, channels). Hover a `bug` label chip — tooltip appears:
*"Applied at issue creation via the official GitLab MCP server — no quick-action workaround."*

🎙️ *"Every draft shows its reasoning. Why this one ranked first: 20 reports, across 5 channels,
severity 5 of 5 — computed deterministically, not estimated. The labels you'll see in a
moment go through the official MCP server's create-issue tool, not a workaround."*

---

## 1:40 – 2:10 — Human approval beat (the headline)

🎥 Edit the title of the #1 card. The amber left rule lands on the input, and the `edited by
you` chip lights up next to the priority pill. Press `⌘ + Enter`. The Approval Gate Agent
log line lands: *"approved 6 drafts."*

🎙️ *"Here's what wins the design point: the agent paused server-side. Nothing has touched
GitLab yet. I can edit any draft — that becomes my co-authored ticket, not the model's draft.
Cmd-Enter approves the batch."*

---

## 2:10 – 2:40 — GitLab Writer Agent fires live

🎥 The activity panel shows the **GitLab Writer Agent** firing tool calls in real time:
`create_issue #1247 (labels [bug, signup] applied): Signup loop sends users back to login`,
`link_work_items: related #1247 to 2 existing`, `get_issue #1247: labels [bug, signup]`.

🎙️ *"Now the GitLab Writer Agent fires. Issue created with the labels applied at creation.
Related to existing issues using link_work_items — the first-class work-item relation, not a
slash-relate quick action. Every call is verified by reading the issue back."*

---

## 2:40 – 3:00 — Verification in real GitLab

🎥 Switch tabs to https://gitlab.com/egg-labs-group/loopback-demo/-/issues. Refresh once.
Six new issues at the top of the list with their labels visible. Click into the #1: see the
title (the edited version), the labels, the relates panel.

🎙️ *"Six issues in the actual GitLab project. Edited title. Labels applied. Relates wired.
Loopback — the agent that pauses before every GitLab write."*

---

## If a beat overruns

Cut from longest beat first, in this order:
1. **1:20 – 1:40** (why-line + tooltips) — can be 8 seconds instead of 20.
2. **0:20 – 1:00** (ingestion + clustering narration) — 30 seconds instead of 40.
3. **2:40 – 3:00** (verification) — minimum 12 seconds; do not cut below.

The non-negotiable beats are: Trigger (0:00), Router Agent line (1:00 – 1:20),
Approval (1:40 – 2:10), MCP writes firing (2:10 – 2:40), GitLab verification
(2:40 – end). Lose any of those and the demo loses a rubric axis.

## Stack name-drops to land on screen or in voiceover

Each must be heard or seen at least once:
- **Gemini 3** (Vertex AI)
- **ADK** / **Agent Development Kit**
- **Cloud Run**
- **GitLab Official MCP server**
- **OAuth 2.0**
