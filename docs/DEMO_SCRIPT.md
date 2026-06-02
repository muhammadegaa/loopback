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
- GitLab demo project is shaped for a realistic **mixed batch** — verified
  in the live practice run. The classifier produces:
  - **1 high-confidence file-new** (the hallucination theme — no match)
  - **4 extends** (SSO, destructive actions, Stripe, token budgets)
  - **1 regression flag** (Composer planning, against a closed issue)
  - **5 needs-review** (uncertain themes for PM judgment)
- This reflects what real-life Monday-morning triage looks like — the agent
  doesn't make one type of decision; it makes five.
- Hit `POST /api/admin/clear-learning` once before recording so the
  "learns your no's" loop is fresh.
- Confirm the live app's hero reads: *"The agent that pauses before every GitLab write."*

**Gate latency to expect:** ~100-110s end to end. The classifier reads ~18
candidate descriptions and runs a Gemini verdict call per theme. The activity
panel scrolling past the eight specialists IS the demo — don't compress it
away. Slow your voiceover, name the work, let the agent be visibly thinking.

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

## 0:50 – 1:15 — The Classifier Agent beat *(the headline)*

🎥 New line lands in the activity panel:
**Classifier Agent** — *"classified 6 duplicate, 1 regression, 1 related, 4
unrelated candidates across 7 themes. 4 theme(s) will extend existing tickets;
1 flagged as regressions."*

🎙️ *"This is the move. The Classifier Agent reads each candidate's title and
full description, and decides what it IS — duplicate, regression, related, or
unrelated — with a confidence score and a one-line reason. The agent isn't
matching titles; it's reasoning about content. Look at the spread of decisions:
six duplicates, one regression of a previously-closed issue, one loosely
related, four genuine false positives the agent declined to link."*

---

## 1:15 – 1:40 — Triage Router: five different decisions in one batch

🎥 **Triage Router Agent** log line: *"routed 10 drafts — 1 high-confidence
ready for one-click approve; 5 flagged for your judgment; 4 will extend
existing tickets instead of creating new."*

Cards arrive below in **four visual treatments**:
- One **HIGH** card (no left rule) — Hallucination of non-existent APIs
- Four **EXTEND** cards (indigo left rule + `extends #N` chip) — SSO,
  destructive actions, Stripe, token budgets
- One **REGRESSION** card (red chip `regression of #91`) — Composer planning
- Five **REVIEW** cards (amber left rule + `needs your judgment` chip)

🎙️ *"This is the irresistible part. Eleven themes. Five different agent
decisions in one batch — exactly what a senior PM does on a Monday morning.
One theme strong enough to file immediately. Four already tracked, so extend
not duplicate. One that matches a CLOSED issue — possible regression, the
fix didn't hold. Five that need my judgment because the agent isn't confident
enough to auto-route. That's real triage."*

---

## 1:40 – 2:00 — Drafts read like proper tickets

🎥 Click the **HIGH** card (Hallucination) to expand its details. The body
renders with clean section headers: `Problem`, `Evidence` (three blockquoted
customer quotes), `Repro`, `Expected`, `Suggested fix`, `Acceptance criteria`.
Labels: `kind::bug`, `area::agent-behavior`, `priority::p1`, `customer-pain::high`.

🎙️ *"Every draft reads like a senior engineer wrote it. Action-first title.
Sectioned body. Evidence quotes spliced in deterministically, verbatim from
the customer reports — never rewritten by the model. Labels follow convention.
Priority derived from severity. These are the tickets I'd file myself."*

---

## 2:00 – 2:25 — Approval: edit one, override one extend, ⌘↵

🎥 (a) Edit the title of the **HIGH** card — the amber left rule lands;
`edited by you` chip lights up. (b) On one EXTEND card, click
`Override → file as new issue instead` — the card flips to a standard card.
(c) Optionally reject one of the REVIEW cards as noise. (d) Press `⌘ + Enter`.
The Approval Gate Agent log line lands.

🎙️ *"I'm in command of every decision. I can edit any draft — that becomes my
co-authored ticket. I can override the agent's extend recommendation if I want
a fresh issue instead. I can reject a draft outright — and the agent will
remember the no for the next run. The gate isn't a rubber stamp. Cmd-Enter
approves the batch."*

---

## 2:25 – 2:50 — GitLab Writer Agent fires: a mixed batch lands

🎥 Activity panel shows tool calls in real time, mixing both code paths:
- `create_issue (labels [...] applied)` × 2 (the high-confidence and the override)
- `create_issue ... ## Possible regression of #91` × 1 (the regression flag)
- `link_work_items: related #N to M existing`
- `create_workitem_note on #87: extended with new evidence` × 3 (the remaining extends)
- `get_issue: labels verified` after each

🎙️ *"The GitLab Writer Agent dispatches by lane. Some draft go through
create_issue — labels applied at creation, regression flag embedded in the body
when the classifier said so. Others go through create_workitem_note — extending
existing tickets with new customer evidence instead of duplicating. Every call
verified by reading the issue back."*

---

## 2:50 – 3:00 — Verification in real GitLab

🎥 Switch tabs to https://gitlab.com/egg-labs-group/loopback-demo/-/issues.
Show: (a) new issues at the top including the regression flag with its
`## Possible regression of #91` block visible, (b) click into the extended SSO
issue and scroll to Loopback's posted comment, (c) switch back to Loopback's
done state — split list shows "New issues created" and "Existing issues
extended." Three big impact numbers visible: time saved, duplicates prevented,
noise filtered.

🎙️ *"This is what irresistible looks like for an AI startup's Monday morning.
298 messy customer signals to a real triage decision in under two minutes —
new tickets where new work is warranted, extensions where it's already
tracked, regression flags where fixes didn't hold, and PM judgment where the
agent is honestly uncertain. The agent did the homework. The human stayed in
command. Loopback."*

---

## If a beat overruns

Cut from longest beat first, in this order:
1. **1:40 – 2:00** (proper-ticket walkthrough) — can be 10 seconds instead of 20.
2. **0:15 – 0:50** (eight-specialist narration) — 25 seconds instead of 35.
3. **2:50 – 3:00** (verification) — minimum 10 seconds; do not cut below.

**Non-negotiable beats:**
- Trigger (0:00)
- Classifier Agent line showing the **spread of verdicts** (0:50–1:15)
- Triage Router showing **four lanes lighting up** (1:15–1:40) — this is the
  irresistible visual: a single batch producing five different agent decisions
- One proper-ticket body expansion to demonstrate quality (1:40–2:00)
- Approval beat including edit + override + ⌘↵ (2:00–2:25)
- MCP writes firing (2:25–2:50) — must show BOTH `create_issue` AND
  `create_workitem_note` AND a `## Possible regression of #N` block
- GitLab verification — show both a new issue AND an extended issue's comment
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

Verified live in the practice run that locked this script:

- 298 signals → 14 PII-redacted (6 emails, 2 phones, 6 URLs)
- 11 themes from 174 actionable signals; 124 ignored as non-actionable noise
- 18 candidate issues fetched via `get_issue`
- Classifier: 6 duplicate, 1 regression, 1 related, 4 unrelated
- Triage Router: **1 high · 5 needs_review · 4 extend_existing · 1 regression-flag**
- After approval (one edit, one override):
  6 `create_issue` calls + 3 `create_workitem_note` calls
- Done state: 6 created (1 of which is the regression flag) · 3 extended

If the GitLab project state drifts and you see all-extend or all-create on the
next run, the project shape has drifted from realistic. The shaped state to
preserve is documented in the cleanup recipe below.

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

# 2. Verify GitLab project state. The shaped state for the realistic mix is:
#    KEEP OPEN: #87 (sso), #88 (destructive), #90 + dupes (stripe), #96 (token),
#               and the 5 unrelated "search latency" issues #67/#61/#55/#49/#43
#               that the classifier should mark "unrelated" (visible reasoning).
#    CLOSED:    #91 (model-regression) — this is the regression candidate.
#    DELETED:   #89, #93, #92, #94, #95, #97, #84 — those themes file new.
# Run this Python check to confirm:
.venv/bin/python -c "
import os, httpx
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k,_,v = line.partition('='); os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))
PAT = os.environ.get('GITLAB_PAT') or os.environ.get('GITLAB_TOKEN')
KEEP_OPEN = {87, 88, 90, 96}
CLOSED = {91}
for iid in sorted(KEEP_OPEN | CLOSED):
    r = httpx.get(f'https://gitlab.com/api/v4/projects/82508739/issues/{iid}', headers={'PRIVATE-TOKEN': PAT})
    if r.status_code == 200:
        d = r.json(); want = 'closed' if iid in CLOSED else 'opened'
        marker = 'OK' if d['state']==want else 'WRONG'
        print(f'  [#{iid}] state={d[\"state\"]} (expected {want}) — {marker}')
    else:
        print(f'  [#{iid}] HTTP {r.status_code} — missing?')
"
```
