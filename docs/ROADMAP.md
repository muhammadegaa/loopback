# Loopback — what comes next

This doc exists because a panelist will reasonably ask: "OK, the demo is clean
— but what happens when two PMs sign in at once? Where's the dashboard? How do
you not break a live gate when you ship a new version of the agent?"

These are real questions and they have real answers. The hackathon submission
is intentionally single-tenant. This roadmap lays out the path to a real
multi-user product, what it costs, and what we're deliberately not doing in
the submission window.

## Table of contents

1. [What Loopback is today (scope-honest)](#what-loopback-is-today-scope-honest)
2. [Where it breaks the moment a second user signs in](#where-it-breaks-the-moment-a-second-user-signs-in)
3. [Phase 1 — Auth + workspaces + durable state](#phase-1--auth--workspaces--durable-state)
4. [Phase 2 — The PM dashboard](#phase-2--the-pm-dashboard)
5. [Phase 3 — Continuous ingest (beyond CSV upload)](#phase-3--continuous-ingest-beyond-csv-upload)
6. [Phase 4 — Learning that compounds](#phase-4--learning-that-compounds)
7. [Maintenance principles (how we don't break user flows)](#maintenance-principles-how-we-dont-break-user-flows)
8. [The decision boundary (the only contract that matters)](#the-decision-boundary-the-only-contract-that-matters)
9. [What we explicitly are NOT doing in the hackathon window](#what-we-explicitly-are-not-doing-in-the-hackathon-window)
10. [Sequencing + rough effort estimates](#sequencing--rough-effort-estimates)
11. [Things we haven't figured out yet (honest)](#things-we-havent-figured-out-yet-honest)

---

## What Loopback is today (scope-honest)

A single-instance, single-tenant agent that triages a CSV of customer feedback
into approved GitLab issues, with a real server-held HITL pause.

| Surface | Today's state |
|---|---|
| **Auth** | None. Anyone with the URL can start a run. |
| **Tenancy** | One workspace, hardcoded. One GitLab project ID (`82508739`). One OAuth token in Secret Manager. |
| **Run state** | In-memory `RUNS: dict[str, dict]` on a single Cloud Run instance. |
| **Cloud Run scaling** | `--min-instances=1 --max-instances=1` because the state can't move between instances. |
| **Learning memory** | `/tmp/loopback-learning` — per-source file, global to the instance. |
| **Resume across pause** | Yes within an instance (via `?run=<id>` URL param). No across instance restarts. |
| **Concurrency** | One worker thread per run. Shared dict without locking. Two simultaneous runs touch different keys so they coexist, but the design isn't safe at scale. |
| **Decision payload contract** | Single version. No `/api/v2` namespace. Breaking a field breaks all live UIs. |

That's the right scope for a judging artifact. It is not yet a product two
people can share.

## Where it breaks the moment a second user signs in

This is the honest catalog of every assumption that fails under multi-tenant
load:

1. **Visibility leak.** No auth, no workspace boundary. User B sees user A's
   in-flight runs by guessing run IDs.
2. **Cross-tenant writes.** One OAuth token, one project. User B's run files
   issues into user A's GitLab project.
3. **Cross-tenant learning pollution.** Per-source memory by filename. Two
   customers uploading `feedback.csv` poison each other's "learns your no's"
   loop.
4. **Gate interruption.** A UI change ships to all browsers at once. A user
   sitting at a paused gate refreshes and the React component renders against
   a `Draft` shape that's different from what their run produced.
5. **Single point of failure.** One Cloud Run instance. Restart kills every
   paused run in-flight. No way to recover.
6. **Cost socialization.** Every run uses the platform's Gemini quota. A
   single customer running 50 batches/day saturates and blocks every other
   customer's runs.
7. **No audit trail across runs.** Decision log exists for the current run
   only. Compliance ("show me every issue Loopback filed in Q3") has no answer.
8. **No way to revoke access.** A customer cancels. Their OAuth token is still
   in our Secret Manager. No off-boarding path.

Every one of these is fixable. The order to fix them in is what this roadmap
is about.

## Phase 1 — Auth + workspaces + durable state

**Goal:** two customers can sign in, run pipelines in parallel, and never see
each other's data.

This is the foundation. Without it, nothing in Phase 2+ makes sense.

### What it requires

1. **Auth.** Google Workspace SSO or WorkOS. Optionally Clerk for fast
   shipment. We don't need fancy identity; we need a stable `user_id` and
   `workspace_id`.

2. **Workspace model.** A workspace owns:
   - One GitLab connection: OAuth token (encrypted at rest, rotated on
     refresh), project ID, project URL.
   - One source-of-truth feedback channel config (Phase 3 hooks).
   - One set of members (roles: admin/maintainer).
   - One rejection memory namespace.

3. **Durable run state.** Move `RUNS` from in-memory dict to Postgres (Supabase
   would be the fastest path). Schema sketch:

   ```sql
   CREATE TABLE workspaces (
     id uuid primary key,
     name text not null,
     gitlab_project_id text not null,
     gitlab_oauth_secret_resource text not null,  -- pointer, not the token
     created_at timestamptz default now()
   );

   CREATE TABLE workspace_members (
     workspace_id uuid references workspaces(id),
     user_id uuid not null,
     role text not null check (role in ('admin','maintainer')),
     primary key (workspace_id, user_id)
   );

   CREATE TABLE runs (
     id text primary key,                        -- existing 12-hex run_id
     workspace_id uuid references workspaces(id),
     started_by uuid not null,                   -- user_id
     status text not null,
     state_jsonb jsonb not null,                 -- the public-keys payload
     decision_jsonb jsonb,                       -- the decision payload after gate
     created_at timestamptz default now(),
     updated_at timestamptz default now()
   );

   CREATE TABLE rejection_memory (
     workspace_id uuid references workspaces(id),
     source_label text not null,
     fingerprint jsonb not null,
     created_at timestamptz default now(),
     primary key (workspace_id, source_label, fingerprint)
   );
   ```

4. **HITL pause that survives restart.** Today the pause is held by a
   `threading.Event` in memory. After Phase 1, the pause is held by the row's
   `status = 'awaiting_approval'` in Postgres. The pipeline worker polls for
   the decision row. We can scale to multiple instances because any of them
   can pick up any paused run.

5. **Per-workspace OAuth.** During workspace onboarding, the admin authorizes
   GitLab via `scripts/oauth_spike.py`-style DCR+PKCE. The token blob is
   encrypted and stored under that workspace's `gitlab_oauth_secret_resource`.
   `tools/gitlab_oauth.py` is parameterized to refresh per-workspace.

6. **Per-workspace Gemini quota.** Initially: track tokens spent per workspace
   against a soft cap. Long term: pass-through billing where the workspace's
   own Vertex AI project is used (BYO-credentials model).

### What it does NOT require

- A new agent. The agent graph stays. We just isolate state per workspace.
- A redesigned UI. The current Upload → Review → Result UI works fine for one
  user at a time, just under a `/w/<workspace_slug>` URL prefix.
- A new MCP integration. Per-workspace OAuth means the GitLab tools call the
  customer's project, not ours.

### Effort estimate

~2 weeks for one engineer who already knows the codebase.

### Risks

- **OAuth refresh under multi-tenant load.** Our current OAuth refresh writes
  back to a single Secret Manager resource. Under N workspaces, we need
  per-workspace rotation. Concurrent runs in one workspace must serialize on
  refresh. Postgres advisory lock on `(workspace_id, 'oauth_refresh')` solves
  this.
- **Run state size.** A run's `state_jsonb` can hit ~50KB with full step log.
  Postgres handles this fine but we should not put it in `pg_dump` snapshots
  on every backup. Move step log to a separate table with a foreign key.

## Phase 2 — The PM dashboard

**Goal:** A workspace member opens Loopback and lands on a dashboard that
shows what the agent has done for them, how confidence has tracked over time,
and what's trending up in customer signal.

This is the move that turns Loopback from "a tool you open when you have a CSV"
into "a Monday-morning ritual."

### What it shows

1. **Recent runs feed.** Most recent run on top. Each row:
   - When it ran, who triggered it
   - Signal volume in, themes out
   - Decisions: N created, M extended, K regression flags, R rejected
   - Time-to-gate and time saved (the impact triptych, but per run)

2. **Theme tracker (the genuinely useful view).** A list of themes that have
   surfaced more than once across runs, ranked by trend slope. For each:
   - First seen, last seen, total reports across all runs
   - Linked GitLab issue (the canonical one — whichever was the latest extend
     target or original create)
   - Slope arrow: heating up / cooling down / steady
   - Click to see the runs that surfaced this theme + the customer quotes
     across all of them

3. **Decision quality metrics.** The agent's track record:
   - Approval rate (what % of drafted issues were approved unchanged)
   - Edit rate (what % were edited before approval)
   - Reject rate (what % were rejected as noise)
   - Override rate (what % of extends were overridden to file-new)
   - Per-classifier-verdict accuracy as the user disagrees with the agent
   - These metrics let a workspace OWN the agent's calibration over time.

4. **Audit log (compliance answer).** Every external GitLab write, who
   approved it, what the draft said before/after edits, classifier reasons.
   Filterable by date, user, theme. Exportable as CSV.

5. **Closed-loop dashboard (the customer-facing answer).** For each closed
   GitLab issue: how many customer reports were rolled into it, when was the
   last customer report, do those customers have a notification queued?

### What it does NOT need to be

- A real-time analytics dashboard. The data updates per run, not per second.
- Configurable. The first version ships with the views above. Customization is
  a Phase 6 problem.

### Why this is high-leverage

The dashboard is the answer to the question "why come back tomorrow." Without
it, Loopback is a one-shot tool. With it, the workspace becomes a system of
record for "what does my customer feedback say this week."

### Effort estimate

~1-2 weeks. Schema is mostly already present in `runs.state_jsonb`. Theme
tracker requires a denormalized `themes` table and a small job that updates
it after each run.

## Phase 3 — Continuous ingest (beyond CSV upload)

**Goal:** The PM stops uploading CSVs. Loopback pulls feedback continuously
from their actual channels.

The current "drop a CSV on the dropzone" workflow is the right thing for a
demo. It's the wrong thing for a product. Real teams have feedback streaming
into Intercom, Zendesk, Slack, app stores, Twitter, GitHub issues —
continuously.

### What we build

1. **Connectors.** Webhook-receiver or polling integration for each source:
   - Intercom (highest leverage — paid Intercom is enterprise SaaS's most
     common support tool)
   - Zendesk
   - Slack Connect channels (for the customer-Slack-with-our-team pattern)
   - GitHub issues on the SDK repo (for AI-product SDKs specifically)
   - App Store / Play Store review pulling
   - X/Twitter mention monitoring (limited but useful)

2. **Scheduled triage runs.** A workspace configures: "run a triage on the
   last 7 days of signal every Monday at 9am Pacific." Loopback runs it. The
   user gets a notification (Slack DM or email): "your weekly triage is ready
   for review — N themes, K need your judgment."

3. **Signal normalization.** Each connector emits a normalized
   `{id, text, channel, date, source_url, customer_id}` shape. The existing
   `_Ingest` agent reads from a queue, not a CSV.

4. **PII redaction at ingest time.** `tools/redact.py` already does this for
   text. The connector layer is responsible for stripping per-source identity
   metadata (Intercom user IDs, GitHub usernames) into anonymized IDs before
   storage.

### Why this is the unlock

Continuous ingest is what makes Loopback indispensable. The dashboard
(Phase 2) becomes a Monday-morning ritual when there's always new signal to
look at. Without it, the dashboard is mostly empty.

### Effort estimate

~3 weeks for the first connector (Intercom) + the scheduled-run plumbing.
Each subsequent connector is ~1 week.

## Phase 4 — Learning that compounds

**Goal:** The agent gets meaningfully better at each customer's taste over
weeks, in ways the customer can audit and trust.

Today we have one thin learning loop: per-source rejection memory. That's a
proof-of-concept, not a moat. A real learning surface has multiple dimensions:

1. **Severity calibration.** When the PM consistently downgrades the agent's
   sev=5 to sev=3 for a theme type ("dark mode flicker is not critical here"),
   future runs draft those at sev=3 from the start.

2. **Labeling style.** Track the labels the workspace's GitLab project
   actually uses. Drafts use those labels, not the agent's generic
   `area::auth` invention.

3. **Drafting style.** Closed issues in the project = ground-truth examples of
   what the team's tickets look like. After N closed issues are observable,
   the drafting prompt few-shots from them — the team's house style without
   asking anyone to write a style guide.

4. **Approval-pattern calibration.** Themes whose drafts get heavily edited
   before approval get flagged for more careful drafting next time. Themes
   the PM consistently approves unchanged get the "high" lane more
   permissively.

5. **Routing-decision calibration.** When the classifier says "duplicate of
   #420" and the PM overrides to file new 3 times in a row, the classifier's
   confidence threshold for that theme-type goes up.

These all already have a hook point in the codebase — the rejection memory in
`tools/learning.py` is the pattern. The harder question is: how does the
customer audit and trust the learning? The dashboard (Phase 2) needs a
"learning state" view that shows what the agent has learned about THEM.

### Effort estimate

Real learning loops are an ongoing investment. The infrastructure (per-
workspace memory tables, hooks into the drafting and classifier prompts) is
~2 weeks. Tuning the loops is forever.

## Phase 5 — Loopback replaces the scrum ceremony layer

This is the ambitious version. It's not the next thing to build, but it's the
defensible long-term position, and it's worth committing to a direction here so
the earlier phases don't drift sideways.

The bet: for AI-native product teams of 5-50 people, **scrum ceremony is
overhead**. Sprint planning, standups, backlog grooming, retros — these
exist to answer questions that a continuous, customer-grounded system could
answer better. Loopback is that system.

### What replaces what

| Ceremony | What it tries to answer | How Loopback answers it instead |
|---|---|---|
| **Sprint planning** | "What should we commit to this week?" | The backlog is continuously re-ranked by `frequency × severity × time-since-last-customer-report`. You pick the top N you have capacity for; the rest stays in queue and re-ranks itself as new signal arrives. No meeting required. |
| **Standup** | "Who's doing what, who's blocked?" | The dashboard shows every in-flight issue's current customer-reports count, last activity, classifier confidence, PM-set priority, owner. You read it; you don't gather. |
| **Backlog grooming** | "Is this still relevant?" | Every new customer report routes through the classifier. Stale themes get bumped to the top when new reports arrive; truly dead themes get rejection-memory'd. The backlog doesn't decay because the agent maintains it. |
| **Retro** | "What worked, what didn't?" | The agent's decision log is the retro. Approval rate, override rate, edit rate, classifier accuracy as humans disagreed. Per-theme: time-to-close, reporters-notified rate, regression rate. The retro IS the data. |
| **PRD** | "What are we building next quarter?" | The top N persistent themes ARE the roadmap. Not aspirational — observed across continuous customer signal. The PRD is a generated artifact from the dashboard. |
| **Customer feedback closing the loop** | "Did we tell the customer who reported it?" | When GitLab marks an issue closed, Loopback notifies every original reporter in their original channel: "you reported this, we shipped a fix yesterday." Closed-loop without ceremony. |

### The continuous re-ranking move

This is the single most important capability of Phase 5. Today the Triage
Router ranks themes once per run. In Phase 5, every new piece of customer
signal — a new ticket in Intercom, a new GitHub issue, a new app store review
— triggers an incremental classifier pass against the live backlog. If five
new reports of an existing GitLab issue arrive between Monday and Tuesday,
that issue jumps to the top of the visible backlog automatically. The
engineer opens Loopback Tuesday morning, sees the bump, and doesn't need to
ask anyone.

This requires:
- Webhooks from each connector (Phase 3) firing into a re-rank job.
- A backlog view in the dashboard that has a "since you last looked" diff.
- Notification rules per workspace member (Slack DM when an issue you own
  bumps significantly).

### Why this fits AI startups specifically (and not enterprise)

AI startups are typically small, fast-iterating teams where the PM is also a
half-engineer, where the engineer is also a half-PM, where customer success
is the founder's calendar. Scrum was designed for a different team shape —
sized teams, separated roles, predictable cadence. AI startups have none of
those. Their natural cadence is "what does the customer signal say today,"
not "what did we commit to two weeks ago."

For enterprise teams of 100+ engineers with regulatory sprints, compliance
requirements, and quarterly board reviews — scrum is here to stay. Loopback
is not for them. That's a separate product category.

### Why we don't build this for the hackathon

The hackathon submission optimizes for one judging panel watching 3 minutes
and reading a public repo. Phase 5 requires Phases 1, 2, 3 underneath it.
Building Phase 5 first would result in a pitch deck, not a working artifact.

But naming it in the roadmap is important — it answers the question "where
is this going" with something defensible. AI startup PMs reading this
roadmap should recognize their own daily reality in the Phase 5 description.
That's the recognition that turns a hackathon submission into a product
roadmap people want to join.

### Effort estimate

Phase 5 only becomes buildable once Phases 1-3 ship. Once they have, Phase 5
is ~4-6 calendar weeks for the continuous re-ranking + backlog diff view +
member notifications. The "replaces scrum" framing is mostly marketing — the
underlying capability is "continuously re-rank a backlog from real-time
customer signal." That's an engineering project, not a movement.

## Maintenance principles (how we don't break user flows)

A real product has this discipline, not just a Phase 1 todo. These are the
principles we'd put on the wall.

### 1. API contracts are frozen

Once a workspace's UI is running against an API shape, that shape doesn't
change. Concretely:

- `Decision` Pydantic model in `server/main.py`: never remove a field. Add
  optional fields freely.
- `Draft`/`Created`/`RunState` TypeScript types in `web/lib/api.ts`: same rule.
- If a breaking change is genuinely needed, version the route: `/api/v2/runs`.
  Keep `/api/v1` running for the migration window (minimum 90 days).

### 2. Agent graph changes ship behind workspace flags

Want to add a 9th specialist or change how the classifier scores? Roll it out
to 10% of workspaces, measure approval rate and edit rate against the
existing baseline for the same workspaces in the prior month, only then
roll to everyone.

The infrastructure: per-workspace `feature_flags` jsonb column, read at the
start of each run, threaded into the agent context.

### 3. The HITL pause is sacred

The implicit contract Loopback offers the customer is: "no external write
without your explicit decision at the gate." This contract is what makes the
product trustworthy. It is the product.

Every code change that touches `server/main.py:_pipeline` or any
`_CreateInGitLab`-equivalent agent needs:
- A test asserting that no MCP write tool is called before
  `state["_decision_ready"].is_set()` returns true.
- A test asserting that a draft the human rejected does not result in a
  `create_issue` or `create_workitem_note` call.

These tests would live in `tests/test_pipeline.py` and `tests/test_gate.py`.
They're the regression suite that prevents the worst possible product bug:
the agent silently filing a ticket the human didn't approve.

### 4. Observability is a Day-1 product feature, not a "later" thing

Per-workspace metrics shipped to Cloud Monitoring (or equivalent):
- Run latency per agent (Signal Ingestion is 800ms, Classifier is 8s, etc.)
- MCP tool call latency + error rate per tool
- Gemini call latency + token cost
- Pause duration distribution (do users abandon gates? if so, after how long?)
- Approval/edit/reject rates per theme type

The dashboard (Phase 2) consumes a subset of these. Internal product/eng
consumes the rest.

### 5. Decision-log immutability

Once a run completes, its state row in the `runs` table is read-only. We
never update past decisions. If the agent disagreed with the human, the log
records that disagreement and what the human chose. The record is the
artifact.

This is what makes "did Loopback ever file something I didn't approve" a
question with a defensible answer.

## The decision boundary (the only contract that matters)

There's one design principle that has to outlast every phase, every model
update, every agent graph change.

**The agent's authority ends at the gate. The human's authority is absolute
for every external write.**

Concretely this means:

- The agent can search GitLab, read GitLab, classify, draft, route, and
  recommend without asking.
- The agent CANNOT call `create_issue`, `create_workitem_note`,
  `link_work_items`, `add_note`, or any other MCP write tool until the human
  posts a decision through the gate.
- The human can override every routing decision the agent made (extend ->
  file new, file new -> reject, etc.).
- The human's decisions are remembered as preference signal, not as
  permission. Future runs may produce a different draft for the same theme;
  the human still has to gate it.

This is the boundary. Everything else is implementation detail. If we ever
weaken this — even slightly, even "just for the high-confidence high lane,
just auto-approve" — we lose the product's reason to exist.

## What we explicitly are NOT doing in the hackathon window

Honesty about scope, for the panel and for us:

- **No auth.** Anyone with the URL can run. Single judging URL.
- **No durable run state.** Cloud Run restart kills paused runs. The judging
  window doesn't restart often enough to matter.
- **No multi-tenancy.** Hardcoded GitLab project, hardcoded OAuth token.
- **No dashboard.** Past runs are not retrievable after the instance is
  recycled.
- **No connectors.** CSV upload only.
- **No SSO offboarding flow.** If we needed to revoke access today, we'd
  rotate the Secret Manager secret manually.
- **No per-tenant Gemini billing.** Every run uses our project's quota.
- **No API versioning.** `Decision` schema is mutable.

The hackathon submission optimizes for one judging panel watching a 3-minute
video and reading a public repo. Not for two simultaneous customers.

## Sequencing + rough effort estimates

| Phase | Outcome | Eng-weeks |
|---|---|---|
| Phase 1 | Auth + workspaces + Postgres-backed runs | 2 |
| Phase 2 | PM dashboard + theme tracker + audit log | 1.5 |
| Phase 3 | First connector (Intercom) + scheduled runs | 3 |
| Phase 4a | Per-workspace learning infrastructure | 2 |
| Phase 4b | Severity + label + style calibration loops | ongoing |
| Phase 5 | Continuous re-rank + backlog diff + member notifications (Loopback replaces scrum ceremony) | 4-6 |
| Maint | Observability + test suite + feature flags | 1, then ongoing |

Total for "a credible v1 product two paying customers can use": ~6 calendar
weeks of focused work, post-hackathon.

Total for "a product I'd put on the wall at AI Engineer Summit": Phase 1-3,
which is ~7-8 weeks if Phase 3 includes two connectors.

## Things we haven't figured out yet (honest)

There are things this roadmap papers over. Listing them so they're not
hidden:

1. **Pricing.** Per-seat? Per-workspace? Per-signal-volume? Pass-through
   Gemini billing or include? Unclear. Likely figured out by talking to the
   first 5 design partners, not by guessing.

2. **Where the dashboard lives.** Same Cloud Run instance as the agent
   pipeline? Separate Next.js app? The current setup has the UI baked into
   the FastAPI container via static export — that's fine for single-tenant,
   weird for multi-tenant. Probably needs to split into a separate frontend
   deployment with its own auth, calling the API backend.

3. **What happens when GitLab MCP server has an outage.** Today: the run
   fails. In a real product: queue the writes, retry on backoff, surface the
   queue state in the dashboard. Materially more complex than what we have.

4. **What happens when Gemini behaves differently next quarter.** Model
   regressions are the AI startup problem (it's literally one of the demo's
   themes). We need our own regression suite that runs the same Helix sample
   batch and verifies the verdicts haven't drifted dramatically. That's a
   ~1-week investment that pays back the first time a model update would have
   silently shipped to customers.

5. **Privacy posture for enterprise customers.** EU data residency. SOC 2.
   HIPAA if anyone in healthcare ever needs this (unlikely for a PM triage
   tool, but possible). None of this is in scope today; all of it is
   eventually required.

6. **Open source posture.** The hackathon repo is MIT. Long-term, do we keep
   the core open and sell hosting? Open-core where the agent is open and the
   dashboard is paid? Pure commercial? Affects how we structure the codebase
   going forward. This is a real strategic question and we don't have a
   strong answer yet.

7. **The "agent maintainer" role.** Someone in the workspace has to be the
   person who tunes the classifier confidence thresholds, reviews the
   learning state, decides when to roll out a new agent version. In a small
   team this is the PM. In a large team it's a different person — possibly
   the developer-experience lead. The product needs UI for that role. Not
   urgent, but not zero.

---

## What this roadmap is not

It's not a pitch deck. It's not a fundraising plan. It's not a "10x in 12
months" story. It's an honest engineering view of what Loopback would need to
become a product two PMs at two different companies could use without
breaking each other.

The hackathon submission is a credible first artifact pointing at this
product. The roadmap is the bridge. The bridge is buildable.
