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

🎙️ *"This is one chaotic week of customer feedback for Helix, a fictional B2B AI coding
assistant — the kind of feedback every AI startup is drowning in. Hallucination loops, an
agent that ran rm-rf without asking, a silent model regression, plus the usual SSO and
billing pain. Loopback is the multi-agent system that triages this — built on Google Cloud's
Agent Development Kit, powered by Gemini 3 on Vertex AI, integrating GitLab's official MCP
server."*

---

## 0:20 – 1:00 — Reasoning visible · ingestion → clustering

🎥 The agent activity panel on the right starts filling. Named specialists scroll in:
**Signal Ingestion Agent** (PII redaction count visible — "redacted 14 signals carrying
emails, phones, and API keys"),
**Theme Clustering Agent** (themes counted, noise filtered),
**Duplicate-Check Agent** (existing GitLab issues searched).
On the left: triage bar animates up — 298 signals analyzed → ~170 ignored as noise → 10
themes.

🎙️ *"The Signal Ingestion Agent reads 298 messages from in-app support, Discord, GitHub,
Twitter, email, Reddit — and redacts PII before any model call, including pasted API keys.
The Theme Clustering Agent groups the actionable signal into 10 themes, filtering 170 as
noise — praise, OOO replies, customer-blames-AWS-for-our-outage, churn threats. The
Duplicate-Check Agent searches GitLab so we don't propose work that's already tracked."*

---

## 1:00 – 1:20 — Triage Router beat (the multi-agent branching)

🎥 New line lands in the agent activity panel:
**Triage Router Agent** — *"routed 10 drafts — 4 high-confidence ready for one-click approve;
6 flagged for your judgment."*
Drafts appear below. The top 4 cards render cleanly (hallucination loops, SSO redirect,
destructive action, model regression). The bottom 6 carry an amber left rule and a `needs
your judgment` chip — Stripe double-charge, token cost surprise, schema break, over-refusal,
latency spike, context loss.

🎙️ *"The Triage Router Agent is where the multi-agent system earns its name. It decides
which drafts are clear enough for one-click approve and which need the human to look closer
— based on rank and severity, not vibes. Four clear ones — hallucinations, SSO, destructive
action, model regression. Six need my judgment."*

---

## 1:20 – 1:40 — Drafts surfaced, why-line + MCP depth

🎥 Hover the `#1 by impact` chip on the hallucination card (rank justification visible: 22
reports, across Discord, in-app, GitHub, Twitter, severity 5 of 5). Hover a `hallucination`
label chip — tooltip appears: *"Applied at issue creation via the official GitLab MCP server
— no quick-action workaround."*

🎙️ *"Every draft shows its reasoning. Why this ranked first: 22 reports across four channels,
severity 5 of 5 — computed deterministically. The labels go through the official MCP
server's create-issue tool, not a workaround."*

---

## 1:40 – 2:10 — Human approval beat (the headline)

🎥 Edit the title of the hallucination card. The amber left rule lands on the input, and the
`edited by you` chip lights up. Press `⌘ + Enter`. The Approval Gate Agent log line lands.

🎙️ *"Here's what wins the design point: the agent paused server-side. Nothing has touched
GitLab yet. I can edit any draft — that becomes my co-authored ticket, not the model's draft.
Cmd-Enter approves all ten."*

---

## 2:10 – 2:40 — GitLab Writer Agent fires live

🎥 The activity panel shows the **GitLab Writer Agent** firing tool calls in real time:
`create_issue (labels [hallucination, agent-behavior] applied): Agent hallucinates
nonexistent APIs in tool calls`, `link_work_items: related to 2 existing`, `get_issue:
labels verified`.

🎙️ *"Now the GitLab Writer Agent fires. Each issue created with labels applied at creation.
Related to existing issues using link_work_items — the first-class work-item relation, not a
slash-relate quick action. Every call verified by reading the issue back."*

---

## 2:40 – 3:00 — Verification in real GitLab

🎥 Switch tabs to https://gitlab.com/egg-labs-group/loopback-demo/-/issues. Refresh once.
Ten new issues at the top of the list with their labels visible. Click into the
hallucination issue: see the title (the edited version), the labels, the relates panel.

🎙️ *"Ten issues in the actual GitLab project. Edited title. Labels applied. Relates wired.
From 298 messy customer signals to ten properly-scoped engineering tickets in 30 seconds —
with the human in command of every external write. Loopback."*

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
