# Loopback - 3-minute demo video script (DRAFT)

**Format:** screen recording of the live app + voiceover. Target 2:55, hard cap 3:00.
**Demo runs against:** `egg-labs-group/loopback-demo` (clean project) via the **live Cloud Run
URL** `https://loopback-182683404521.us-central1.run.app` (or the local container at :8080).
**Two takes to pre-record:** Run A (creates issues), then Run B on the same project a
moment later (so `search_existing` finds Run A's issues - the "remembers" beat). Record
both before editing so Run B genuinely has duplicates to find.

**Legend:** 🎥 = shot / on-screen · 🎙️ = voiceover.

---

## 0:00–0:25 - The problem (concrete)

🎥 Open on a messy support inbox / a wall of reviews and chat logs (screen-record a few
real-looking feedback lines scrolling). Then a GitLab issues board that's nearly empty.

🎙️ "Every product team is sitting on the same gold mine and the same graveyard. Customers
tell you exactly what's broken - in support tickets, app reviews, chat logs. But that pain
lives over *here* [inbox], and engineering's work lives over *there* [empty GitLab board].
The bridge between them is a human reading hundreds of messages, spotting the pattern, and
writing it up. So it happens late, or never. The same complaint rots for weeks before it
becomes a ticket."

🎥 Cut to the Loopback landing screen ("Stop letting customer pain rot in the support inbox.").

🎙️ "Loopback closes that loop."

---

## 0:25–2:15 - Live walkthrough

### 0:25–0:40 - Upload
🎥 Drag `sample_feedback.csv` onto the dropzone. Show the file name + the 4-step rail
(Cluster · Draft · You approve · Create).

🎙️ "I drop in a batch of raw customer feedback - 142 support messages, reviews, and chat logs.
Triaging this by hand is half a day of someone senior. Loopback runs it through a **pipeline of
specialized agents** on Google's ADK, powered by Gemini 3."

### 0:40–1:05 - Agent reasoning (the ~50s work, sped up)
🎥 **PACING:** clustering + drafting takes ~50s. Show the **terminal step log streaming**
for ~4-5s at real speed (so viewers see live reasoning), then a **2-3x speed-ramp** over the
rest with a small "⏩ sped up" caption. **Caption the agent graph** as the steps fire:
`ingest → cluster → search_existing → draft`. Lines to land on screen: `ingest: loaded 142
signals` … `cluster_and_rank: 6 themes ranked by frequency × severity` … `search_existing: …`
… `draft_issues: drafted 6 issues`.

🎙️ "Watch the agents work - a pipeline of specialized agents, each on the record. One ingests
the 142 signals. One clusters them into recurring themes and ranks by frequency times severity
- computed in code, so it's stable and explainable, not guessed. One searches GitLab for issues
that already exist. One drafts a real issue per theme. 142 messages become six ranked themes."

### 1:05–1:35 - The approval gate (THE focal moment)
🎥 Speed returns to real-time. The amber **"The agent has paused for your approval"** banner
pulses into view. Hold on it for a beat. Pan the proposed issue cards: title, priority,
evidence quotes, repro steps, suggested labels. Show that the fields are editable (a cursor in
the title, the priority as a dropdown) so the next beat reads as real control.

🎙️ "And here's the heart of it. The agents did the tedious ninety percent - read everything,
found the pattern, drafted the tickets - and then **stop**. A real pause, held server-side, that
hands the judgment call to me. Six well-scoped issues: title, reproduction steps, the actual
customer quotes as evidence, labels, priority. Nothing touches GitLab until I say so. Knowing
when to stop is the feature."

### 1:35–2:00 - Co-author the tickets, then approve (THE proof beat)
🎥 This is the moment that proves the gate is real, so show real editing. On one card, click
into the **title** and tighten the wording. On another, change the **priority** dropdown from
medium to **critical**. (Keep it brisk: one title tweak, one priority change, maybe add a
label. Do not type a paragraph on camera.) Then click the toggle on the "Search performance"
card so it dims and strikes through; the gate button updates to **"Approve & create 5."** Click it.

🎙️ "And I am not just rubber-stamping. I shape each one. I sharpen this title. I bump this from
medium to critical, because I know it is hurting users. And this one is not worth a ticket yet,
so I drop it. These get filed as my issues, not the model's draft. Approve and create."

### 2:00–2:15 - Real issues appear
🎥 Cut to the Result screen: "5 issues created in GitLab," rows #N with label chips and
**clickable links**. Click one link → the real GitLab issue opens (labels applied, evidence
in the body). Show the rejected card under "Rejected - not created."

🎙️ "Five real GitLab issues, created through GitLab's official MCP server - with labels applied
and customer evidence in the body. The one I rejected? Created nowhere. The loop is closed."

### (edit point) 2:15 - Second run: "it remembers what it's seen"
🎥 Quick cut: "New run," re-upload the same feedback. Jump (speed-ramp) to the step log line
`search_existing: 'Frequent Session Logouts' → 1 related issue(s)`, then on a created issue
show the linked / related-issue cross-link in GitLab.

🎙️ "Run it again and it remembers - `search_existing` finds the issues it already filed and
links the duplicates with GitLab's native `link_work_items`, so you never get the same ticket
twice."

---

## 2:15–2:50 - Why it matters + the integration (honest)

🎥 Split or B-roll: the closed loop animation (feedback → themes → approved issues → GitLab),
then a clean architecture card: **Gemini + Google ADK (multi-agent) · human approval gate ·
GitLab official MCP (OAuth)**.

🎙️ "Every product team does this by hand, and it doesn't scale. Loopback turned 142 messages
into five approved, well-scoped issues - labels, evidence, duplicate links - in about a minute,
versus half a day by hand. Under the hood: a **multi-step system of specialized agents** built
with Google's Agent Development Kit - the Agent Builder framework - powered by Gemini 3, deployed
on Cloud Run. The data steps are deterministic; the model's judgment goes where it earns its
keep - clustering and drafting - and the human is the planner. For something that writes to your
backlog, that's the responsible design. And it's a genuine, multi-call integration with GitLab's
official MCP server over OAuth: search existing, create with labels, link duplicates natively,
read back to verify. A real partner surface."

*(Honesty note for the VO: this is GitLab's **official** MCP server at
`gitlab.com/api/v4/mcp`, authenticated via OAuth 2.0 - accurate to say so. It's part of the
GitLab Duo Agent Platform; only reference "Duo" if you want to name the platform precisely.)*

---

## 2:50–3:00 - Close

🎥 Back to the closed-loop hero shot + the Loopback wordmark and URL.

🎙️ "Loopback. Customer pain, triaged into GitLab. On the record, and only with your
approval."

🎥 End card: **Loopback · Gemini + Google ADK + GitLab official MCP ·
https://loopback-182683404521.us-central1.run.app**

---

### Edit checklist
- [ ] Keep total under 3:00 (aim 2:55). **The VO grew - time a read-through; if over, trim the
      problem intro (0:00–0:25), NOT the architecture beat's "deterministic / human is the
      planner" line or the numbers - those are the winner-pattern points.**
- [ ] The ~50s analysis is speed-ramped, not cut to black - the streaming log is the proof.
- [ ] **Caption the agent graph** (`ingest → cluster → search_existing → draft`) so it reads as
      a multi-agent system, not one black-box call. This is the framing that matches winners.
- [ ] **The numbers land on screen/VO:** 142 messages → 6 ranked themes → 5 issues created,
      duplicate links, "~1 minute vs half a day." Quantified impact = a winner pattern.
- [ ] The amber approval gate gets a held beat, the judged design moment ("knows when to stop").
- [ ] **The editing beat is shown** (refine a title, change a priority, drop one), brisk. This is
      the proof the human co-authors the tickets and the gate is not a rubber stamp.
- [ ] At least one real GitLab issue link is clicked and opens.
- [ ] Run B genuinely shows a related-issue link (pre-record both runs).
- [ ] Captions for the spoken tool names (`search_existing`, `link_work_items`) so they land.
- [ ] Upload to YouTube unlisted; put the link in Devpost.
