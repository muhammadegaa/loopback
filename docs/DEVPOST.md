# Loopback — Devpost project description (DRAFT)

> **Track:** GitLab. **Built with:** Google Agent Development Kit (ADK) + Gemini, a GitLab
> MCP integration, Cloud Run. **Tagline:** Customer pain, triaged into GitLab — on the
> record, and only with your approval.

---

## Inspiration

Every product team sits on the same paradox: customers tell you exactly what's broken — in
support tickets, app store reviews, chat logs — but that signal lives in one world, and
engineering's work lives in another. The bridge between them is a human who reads hundreds
of messages, spots the recurring pattern, and writes it up. So it happens slowly,
inconsistently, and late. The same complaint can rot for weeks before it ever becomes a
ticket, if it does at all.

I wanted to close that loop — without handing a bot the keys. The point isn't to let AI file
issues unsupervised; it's to do the tedious 90% (read everything, find the pattern, draft the
ticket) and then **stop and ask a human** before anything is written to the system of record.

## What it does

Loopback turns a batch of customer feedback into approved, well-scoped GitLab issues:

1. **Ingest** a batch of customer signals (a CSV of support messages, reviews, chat logs).
2. **Cluster** them into recurring themes and **rank** by frequency × severity.
3. **Search** the GitLab project for issues that already exist, so it can spot duplicates.
4. **Draft** a well-scoped issue for each top theme — title, reproduction steps, the actual
   customer quotes as evidence, suggested labels, priority, and a remediation sketch.
5. **Pause at a human approval gate.** This is the heart of the product. The agent creates
   *nothing* until a person reviews the drafts and approves or rejects each one.
6. On approval, **create** the issues in GitLab, apply labels, and link related/duplicate
   issues — all through the GitLab MCP integration. Rejected drafts are created nowhere.

Run it again on the same project and it recognizes the issues it already filed and links
them as duplicates — it remembers what it has seen.

## How I built it

- **Agent:** Google's **Agent Development Kit (ADK)**, the code-first framework of Vertex AI
  Agent Builder, **powered by Gemini** (`gemini-2.5-flash` on Vertex). The pipeline is an ADK
  `SequentialAgent`: `ingest → cluster → search_existing → draft → approval gate → create`.
  The data steps are deterministic custom agents (the bulk feedback flows through session
  state, never through the model as arguments); clustering and drafting use Gemini with
  schema-constrained structured output.
- **The human-in-the-loop gate** is the design centerpiece, and it's a *real* pause, not a UI
  trick. It uses ADK's `tool_context.request_confirmation()` with a resumable app: the agent
  run genuinely suspends server-side before any GitLab write and only resumes when a human
  posts an approve/reject decision.
- **GitLab integration** is a genuine **GitLab MCP integration** — through a community MCP
  server — and it's a multi-call partner surface, not a token gesture: the agent calls
  `search`/`list_issues` to find duplicates before drafting, `create_issue` to file, posts
  `/label` and `/relate` quick-action notes to label and link, and `get_issue` to verify.
- **Frontend:** a Next.js app — one flow, three states (Upload → Review → Result). The Review
  screen shows the proposed issues as cards beside a live, streaming step log, with the
  approval gate as the visual focal point. No secrets ever reach the client; it talks to the
  API only.
- **Deploy:** one container on Cloud Run runs the MCP server, the ADK agent/API, and the
  built UI together (one public URL, no external moving parts). The only secret — a GitLab
  token — lives in Secret Manager; Gemini runs via the Cloud Run service account.

## Challenges I ran into

The honest, most interesting one was **authentication**, and it changed the architecture.

The plan was to use GitLab's official **Duo MCP server**. But its endpoint authenticates with
a browser-interactive OAuth flow designed for IDE clients — and a headless agent can't click
"Approve." I de-risked this on day two with a tiny spike: a valid Personal Access Token
authenticated everywhere on GitLab's API *except* the MCP endpoint, which returned `404`
(it requires an OAuth scope a PAT simply can't hold). I'd pre-committed to a hard time-box:
if headless auth wasn't working by end of day two, fall back — no rabbit-holing. So I pivoted
to a **community GitLab MCP server**, which authenticates per-request with the token and
exposes a richer tool set. The lesson baked into the whole build: **verify the real API
surface before building on it.** I introspected every MCP tool's live schema before writing a
single helper, which is also how I caught a dependency conflict (ADK pins `google-genai<2`)
before it could break the deploy.

The other interesting one: getting a real HITL pause to survive across an HTTP round-trip.
ADK's confirmation flow needs a resumable app and a precise resume payload; I read the
installed ADK source and the official samples to get the exact mechanism rather than guess.

## What I learned

- Context engineering beats prompt cleverness: feeding the agent real, introspected schemas
  (GitLab MCP tools, ADK's confirmation API) made the difference between a build that works
  and one that fails on stage.
- The most valuable thing an AI agent can do for trust is **know when to stop.** The approval
  gate isn't a limitation; it's the feature.
- Deterministic where it should be deterministic: I compute frequency and ranking in code from
  the model's theme assignments, so the output is stable and explainable, not vibes.

## What's next

- Continuous ingestion from live sources (Zendesk, Intercom, app-store reviews) instead of a
  CSV upload, with scheduled triage.
- Richer dedup using embeddings/vector search so "same issue, different words" is caught.
- Shared run state (Firestore) to scale beyond a single instance.
- Two-way sync: when an issue ships, tell the customers who reported it.

## How it maps to the judging criteria

- **Technical Implementation:** a multi-step ADK + Gemini agent with a *real* server-held
  human-in-the-loop pause (`request_confirmation` + resumable app), and a genuine multi-call
  GitLab MCP integration (search → create → label → relate → verify) — verified end to end
  against a live GitLab project.
- **Design:** one focused flow; the approval gate is the unmistakable visual and conceptual
  center; the agent's reasoning is visible as a live step log; every failure path (bad file,
  empty themes, errors, timeouts) shows a friendly message, never a crash.
- **Potential Impact:** the customer-feedback → engineering loop is universal — every product
  and dev team does this by hand today. Loopback makes it minutes instead of weeks, while
  keeping a human in control.
- **Quality of Idea:** most "AI + repo" tools are "chat with your code." Closing the
  voice-of-customer → engineering loop, with a mandatory approval gate, is a distinct and
  genuinely useful wedge.

---

### Submission checklist (yours to complete)
- [ ] Hosted public URL (Cloud Run) — pending credits/deploy.
- [ ] Public GitHub repo with MIT LICENSE visible in About.
- [ ] ~3-min demo video (YouTube unlisted) — see `docs/VIDEO_SCRIPT.md`.
- [ ] GitLab challenge selected on the Devpost form.
- [ ] This description pasted + edited.
