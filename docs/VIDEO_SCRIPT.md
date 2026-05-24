# Loopback — 3-minute demo video script (DRAFT)

**Format:** screen recording of the live app + voiceover. Target 2:55, hard cap 3:00.
**Demo runs against:** `egg-labs-group/loopback-demo` (clean project) via the local
container at `http://localhost:8080` (or the public Cloud Run URL once deployed).
**Two takes to pre-record:** Run A (creates issues), then Run B on the same project a
moment later (so `search_existing` finds Run A's issues — the "remembers" beat). Record
both before editing so Run B genuinely has duplicates to find.

**Legend:** 🎥 = shot / on-screen · 🎙️ = voiceover.

---

## 0:00–0:25 — The problem (concrete)

🎥 Open on a messy support inbox / a wall of reviews and chat logs (screen-record a few
real-looking feedback lines scrolling). Then a GitLab issues board that's nearly empty.

🎙️ "Every product team is sitting on the same gold mine and the same graveyard. Customers
tell you exactly what's broken — in support tickets, app reviews, chat logs. But that pain
lives over *here* [inbox], and engineering's work lives over *there* [empty GitLab board].
The bridge between them is a human reading hundreds of messages, spotting the pattern, and
writing it up. So it happens late, or never. The same complaint rots for weeks before it
becomes a ticket."

🎥 Cut to the Loopback landing screen ("Stop letting customer pain rot in the support inbox.").

🎙️ "Loopback closes that loop."

---

## 0:25–2:15 — Live walkthrough

### 0:25–0:40 — Upload
🎥 Drag `sample_feedback.csv` onto the dropzone. Show the file name + the 4-step rail
(Cluster · Draft · You approve · Create).

🎙️ "I drop in a batch of raw customer feedback — 142 real-world support messages. Loopback
reads them with Gemini, running as a Google ADK agent."

### 0:40–1:05 — Agent reasoning (the ~50s work, sped up)
🎥 **PACING:** clustering + drafting takes ~50s. Show the **terminal step log streaming**
for ~4-5s at real speed (so viewers see live reasoning), then a **2-3x speed-ramp** over the
rest with a small "⏩ sped up" caption. Lines to land on screen: `ingest: loaded 142 signals`
… `cluster_and_rank: 6 themes ranked by frequency × severity` … `search_existing: …` …
`draft_issues: drafted 6 issues`.

🎙️ "Watch the agent think. It ingests the signals, clusters them into recurring themes,
ranks them by frequency times severity, checks GitLab for issues that already exist, and
drafts a real issue for each theme. Every step and every tool call is on the record."

### 1:05–1:35 — The approval gate (THE focal moment)
🎥 Speed returns to real-time. The amber **"The agent has paused for your approval"** banner
pulses into view. Hold on it for a beat. Pan the proposed issue cards: title, priority badge,
evidence quotes, repro steps, suggested labels.

🎙️ "And here's the heart of it. The agent does **not** touch GitLab. It stops — a real pause,
held server-side — and hands control to me. Six well-scoped issues: title, reproduction steps,
the actual customer quotes as evidence, labels, priority. Nothing gets created until I say so."

### 1:35–1:55 — Reject one, approve the rest
🎥 Click the toggle on the "Search performance" card → it dims + strikes through; the gate
button updates to **"Approve & create 5."** Click it.

🎙️ "I'm in control. This one's not worth a ticket yet — reject. The rest look right —
approve and create."

### 1:55–2:15 — Real issues appear
🎥 Cut to the Result screen: "5 issues created in GitLab," rows #N with label chips and
**clickable links**. Click one link → the real GitLab issue opens (labels applied, evidence
in the body). Show the rejected card under "Rejected — not created."

🎙️ "Five real GitLab issues, created through the GitLab MCP integration — with labels applied
and customer evidence in the body. The one I rejected? Created nowhere. The loop is closed."

### (edit point) 2:15 — Second run: "it remembers what it's seen"
🎥 Quick cut: "New run," re-upload the same feedback. Jump (speed-ramp) to the step log line
`search_existing: 'Frequent Session Logouts' → 1 related issue(s)`, then on a created issue
show the `/relate #N` cross-link in GitLab.

🎙️ "Run it again and it remembers — `search_existing` finds the issues it already filed and
links the duplicates with `/relate`, so you never get the same ticket twice."

---

## 2:15–2:50 — Why it matters + the integration (honest)

🎥 Split or B-roll: the closed loop animation (feedback → themes → approved issues → GitLab),
then a clean architecture card: **Gemini + Google ADK · human approval gate · GitLab MCP**.

🎙️ "Every product team does this by hand, and it doesn't scale. Loopback turns a batch of
customer pain into approved, well-scoped engineering work in minutes — with a human in the
loop, always. Under the hood: a multi-step agent built on Google's Agent Development Kit,
powered by Gemini. The GitLab side is a genuine **GitLab MCP integration** — through a
community MCP server — and it's not a single call: the agent searches existing issues,
creates issues, applies labels and relates duplicates via quick-action notes, and reads
them back to verify. A real, multi-call partner surface."

*(Honesty note for the VO: say "a GitLab MCP integration via a community MCP server." Do
NOT say "GitLab Duo.")*

---

## 2:50–3:00 — Close

🎥 Back to the closed-loop hero shot + the Loopback wordmark and URL.

🎙️ "Loopback. Customer pain, triaged into GitLab — on the record, and only with your
approval."

🎥 End card: **Loopback · Gemini + Google ADK + GitLab MCP · [public URL]**

---

### Edit checklist
- [ ] Keep total under 3:00 (aim 2:55).
- [ ] The ~50s analysis is speed-ramped, not cut to black — the streaming log is the proof.
- [ ] The amber approval gate gets a held beat — it's the judged design moment.
- [ ] At least one real GitLab issue link is clicked and opens.
- [ ] Run B genuinely shows a `/relate` cross-link (pre-record both runs).
- [ ] Captions for the spoken tool names (`search_existing`, `/relate`) so they land.
- [ ] Upload to YouTube unlisted; put the link in Devpost.
