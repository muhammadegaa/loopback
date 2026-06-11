# Loopback - 2-minute demo script

**Status:** locked. Target 2:05. Hard cap 3:00. Punchier rewrite that cuts the proper-tickets walkthrough beat and tightens every voiceover. Seven beats total.

**Recording URL:** `https://loopback-182683404521.us-central1.run.app` in Chrome incognito at 1920x1080. Bookmark bar hidden. Two tabs ready:
1. Loopback (the app).
2. `https://gitlab.com/egg-labs-group/loopback-demo/-/issues`.

**Legend per beat:**
- **SHOW** - clicks and on-screen events. Numbered.
- **SAY** - exact words, sized to fit the beat at ~150 wpm.

Read SAY at natural pace, don't rush.

---

## Pre-recording (do these in order)

1. `.venv/bin/python scripts/reset_demo.py`. Expect `OK - seed restored`.
2. One **warm-up run** in incognito. Upload weekly-batch, click through to gate, click `Ask the agent` on any card and ask one trivial question to pre-warm Gemini, approve, see done. Do not record this.
3. `.venv/bin/python scripts/reset_demo.py` again.
4. Fresh incognito window. Landing page should read **"The agent that pauses before every GitLab write."**
5. Hide cursor when not interacting. Disable notifications.

Optional: have these two questions ready to type at the gate so you don't blank on camera:
- **Primary:** `why isn't this a new ticket?`
- **Cut if running long.** Don't memorise; the input has autofocus.

---

## 0:00 - 0:10 - Setup (10s)

**SHOW**
1. Landing page. Hero reads "The agent that pauses before every GitLab write."
2. Three-batch picker visible. Click **Weekly batch**.

**SAY** (~25 words)
> Loopback turns customer feedback into approved GitLab issues. Google's ADK, Gemini 3 on Vertex, GitLab's official MCP server. 298 messages. Watch this.

---

## 0:10 - 0:35 - Eight specialists (25s)

**SHOW**
1. Dark agent activity panel fills line by line.
2. Triage bar animates: **298 -> 174 actionable -> 14 themes**.
3. Lines land: Signal Ingestion -> Theme Clustering -> Duplicate-Check.
4. **Speed-ramp 2-2.5x in edit.** Voiceover stays at normal pace. Caption "sped up 2.5x".

**SAY** (~62 words)
> Eight named specialists run in sequence. Signal Ingestion reads 298 messages from in-app, Discord, GitHub, Twitter, email, Reddit, and redacts PII before any model call - emails, phones, even pasted API keys. Theme Clustering groups the signal. Duplicate-Check connects to GitLab's official MCP server over OAuth and reads every candidate issue's full description.

---

## 0:35 - 0:55 - The Classifier headline (20s)

**SHOW**
1. New log line lands in the dark terminal: *"Classifier Agent: declined to extend #116 - candidate is closed - flagged as possible regression."*
2. **Zoom on the phrase** "declined to extend ... flagged as possible regression". Hold 2 seconds.

**SAY** (~48 words)
> Here's the move. The Classifier Agent reads every candidate's full description and decides what it is. It found a matching ticket - but that ticket was closed last sprint. So it declined to extend. The fix didn't hold. Flagged as a regression. That's agency, not autocomplete.

---

## 0:55 - 1:15 - Four lanes light up (20s)

**SHOW**
1. Triage Router log line lands.
2. Cards arrive with four lane treatments at once:
   - **4 red bands** ("Flagged as possible regression of #N")
   - **1 green band** ("Ready for one-click approve")
   - **2 indigo bands** ("Will extend existing issue #N")
   - **`Long tail - 11 for your judgment`** divider, then 11 review cards in 2-col grid.

**SAY** (~46 words)
> Fourteen themes. Four different decisions. One strong enough to file. Two are duplicates of open tickets - the agent will extend, not duplicate. Four are regressions of closed issues. Eleven want a PM's call. That's real triage.

---

## 1:15 - 1:40 - Pause, ask, decide (25s) **- the agentic centerpiece**

**SHOW**
1. On the regression-flagged card (red band), click **`Ask the agent`** at the top-right.
2. Inline chat opens. **Type slowly:** `why isn't this a new ticket?`
3. Hit Enter. Wait ~2 seconds for the agent's reply. **HOLD - let the viewer read.**
4. Press **⌘ + ↵** (or Ctrl+Enter). Dark terminal log line lands: *"All drafted issues were approved for creation."*

**SAY** (~58 words)
> Before any GitLab write, I can interrogate any draft. Same data the agent used to decide - classifier reason, customer quotes, the matched closed ticket. *(let the answer land)* I can edit, override, reject - the agent remembers. The pause is real. The agent and I make the call together. Command-Enter.

---

## 1:40 - 1:55 - Writer fires (15s)

**SHOW**
Activity panel streams real MCP tool calls:
1. `create_issue (labels applied)` for new tickets.
2. `## Possible regression of #116` block visible in a created body.
3. `link_work_items: related #N to existing #116`.
4. `create_workitem_note on #115: extended with new evidence`.
5. `get_issue: labels verified`.

**SAY** (~32 words)
> The Writer dispatches by lane. `create_issue` with labels at creation, `link_work_items` for regression flags, `create_workitem_note` for extends. Every call verified by reading back.

---

## 1:55 - 2:05 - Verification (10s)

**SHOW**
1. Tab switch to `https://gitlab.com/egg-labs-group/loopback-demo/-/issues`.
2. Pan once: (a) new issues at top including one with `## Possible regression of #116` visible, (b) seed #115 with Loopback's fresh comment.

**SAY** (~22 words)
> 298 messy signals, triaged in two minutes. The agent did the homework, the human kept command. Loopback.

---

## If you go over

Cut in this order:
1. Trim the **eight specialists** narration (0:10 - 0:35) - the speed-ramp carries it; you can drop the channel list ("in-app, Discord, GitHub...").
2. Skip the follow-up question at the ask beat (already not in the script - good).
3. **Do not cut** the classifier zoom (0:35 - 0:55) or the ask beat (1:15 - 1:40). Those are the rubric.

**Non-negotiable beats** (lose any and you lose a rubric axis):
- Three-batch picker visible in the open shot (0:00).
- The classifier "declined to extend ... flagged as possible regression" sentence zoomed (0:35 - 0:55).
- Four lane treatments landing on screen at once (0:55 - 1:15).
- Ask the agent open + a real grounded answer (1:15 - 1:40).
- Writer beat must include BOTH `create_issue` AND `create_workitem_note` AND a `## Possible regression of` block visible (1:40 - 1:55).
- GitLab verification (1:55 - end).

---

## Stack name-drops (each must be heard or seen once)

- **Gemini 3** on **Vertex AI**
- **Agent Development Kit** (ADK) / **Google Cloud Agent Builder**
- **Cloud Run**
- **GitLab's official MCP server** (`gitlab.com/api/v4/mcp`)
- **OAuth 2.0**
- The four MCP tool names called out in the writer beat: `create_issue`, `create_workitem_note`, `link_work_items`, `get_issue`.

---

## Visible counts (verified live, weekly-batch.csv)

| Metric | Value |
|---|---|
| Signals in | 298 |
| PII redacted | 14 signals touched (6 emails, 2 phones, 6 URLs) |
| Actionable | 174 |
| Noise ignored | 124 |
| Themes | 14 |
| Lane: high | 1 |
| Lane: needs_review | 11 |
| Lane: extend_existing | 2 (-> #115 SSO, -> #113 hallucination) |
| Regression flags | 4 (-> #116 model regression x3, -> #117 tool schema x1) |
| Writer: create_issue | 12 |
| Writer: create_workitem_note | 2 |
| Pre-gate wall-clock | 80-100s |

If the on-screen counts drift, reset and re-run before shooting.

---

## Reset between takes

```bash
.venv/bin/python scripts/reset_demo.py
```

Deletes everything not labelled `demo-seed`, restores the seed (#113-#115 open, #116-#118 closed), wipes the rejection memory. Run between every take.

---

## Total word count

About 293 words across all SAY blocks. At 150 wpm that's ~117 seconds of speech. Lands at ~2:00 with natural pauses for the visual beats. Well inside the 3:00 cap.

---

## Submission text bullets (for Devpost)

- **Built with:** Google Cloud ADK (Python), Gemini 3 (`gemini-3-flash-preview`) on Vertex AI, FastAPI on Cloud Run, GitLab's official MCP server over OAuth 2.0 (Dynamic Client Registration + PKCE), Secret Manager for token rotation. UI: Next.js 16 + Tailwind v4, static export served same-origin.
- **What it does:** triages a batch of customer feedback into approved GitLab issues. Eight named specialists. The agent pauses server-side via `tool_context.request_confirmation` inside a resumable App, before any GitLab write. The Classifier Agent reads each candidate's full description and decides extend / regression / related / unrelated with confidence and reason. The Triage Router emits one of three lanes per draft. The GitLab Writer Agent dispatches by lane.
- **What I learned:** the moves that turn an LLM with tools into a real agent: bidirectional MCP, a server-held human pause, deterministic data flow through session state, classifying candidates against full content rather than matching titles, and a conversational follow-up at the gate so the PM can interrogate the agent's decisions before any write.
