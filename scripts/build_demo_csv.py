# ruff: noqa: E501
"""Generate the demo CSV: one chaotic week of customer feedback for Helix, a
fictional B2B AI coding assistant.

This dataset is calibrated to read as "the inbox of a real AI startup at ~1-10k
WAU" - the categories of complaint, the channel mix, and the noise sub-types are
derived from targeted research into actual public feedback for Cursor, Lovable,
v0, Replit Agent, and the Anthropic / OpenAI API ecosystem.

What makes it realistic (vs. a generic SaaS dataset):

- AI-product-specific themes: hallucination loops, irreversible destructive
  agent actions, silent model regressions, token cost surprises, over-refusal,
  schema breakage after model updates, context-window loss, latency spikes.
- Two conventional themes (SSO outage, Stripe double-charge) to prove the
  agent handles enterprise pain too - not just AI complaints.
- A channel mix that matches AI-startup reality (Discord and GitHub presence,
  not just email + support).
- Noise sub-categories that match what real triagers actually see:
  auto-replies, OOO bounces, multi-issue tickets, upstream-outage
  misattribution, PII pasted by accident (including API keys), wrong-channel
  routing, non-English, screenshot-only "halp", competitor-comparison churn
  signals.

Run: python scripts/build_demo_csv.py
Writes three CSVs under data/ and (mirrored) web/public/ - one per demo scenario:
  first-week.csv      ~75 signals  · calm batch, mostly new tickets
  weekly-batch.csv    ~298 signals · the full chaotic week, mixed lanes
  post-incident.csv   ~100 signals · concentrated regression cluster
The static export serves them under /<name>.csv on the hosted UI.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

ROOT = Path(__file__).parent.parent
SEED = 42

# Dates span 2026-05-26 through 2026-06-01 - one chaotic week.

# ============================================================================
# AI-PRODUCT-SPECIFIC THEMES (8) - the differentiation
# ============================================================================

# --- T1: Agent hallucinates nonexistent APIs / tool calls (sev 5, 22) -------
T1 = [
    ("Helix keeps calling supabase.auth.signInWithMagicLink2() which doesn't exist. Third time this morning.", "discord", "2026-05-31"),
    ("The agent invented a `useFireMutation` hook and committed it across 4 files before I caught it.", "discord", "2026-05-30"),
    ("Asked Helix to add Stripe checkout. It wrote `stripe.checkout.sessions.create_v3` - that endpoint isn't real.", "github", "2026-05-31"),
    ("Composer hallucinated a Postgres function called auth.uid_or_default() that doesn't exist in our schema or in Supabase.", "discord", "2026-06-01"),
    ("@helixai keeps fabricating tailwind classes. `text-display-3xl` isn't in our config and isn't a default.", "twitter", "2026-05-30"),
    ("It made up an entire Next.js API: `headers().setRequestId(...)`. Pure hallucination.", "github", "2026-05-29"),
    ("The agent invented a Prisma method `.upsertManyOrCreate()`. We've been trying to find docs for it for an hour.", "in-app", "2026-05-31"),
    ("Helix keeps generating `import { useServerAction } from 'next/navigation'` - that's not real, never has been.", "github", "2026-06-01"),
    ("Agent invented a configuration key `tailwind.darkVariants.modal` and added it to our config. App broke.", "discord", "2026-05-31"),
    ("Asked for a migration; got SQL referencing a `pg_audit_log` view that doesn't exist in our DB.", "in-app", "2026-05-30"),
    ("It's fabricating Shadcn components again. `<Combobox.Async>` doesn't exist.", "discord", "2026-05-31"),
    ("Helix wrote a 200-line refactor calling `redis.acquireDistributedLock` which is NOT in ioredis. Where did it get this?", "github", "2026-06-01"),
    ("Composer just imported `@vercel/kv-edge` - that's not a package.", "discord", "2026-05-31"),
    ("It cited a Stripe webhook event `invoice.recovery.failed` that does not exist in their API.", "in-app", "2026-05-30"),
    ("Helix asserted that React Server Components support `useState`. They don't. Lost an afternoon debugging.", "reddit", "2026-06-01"),
    ("Agent is confidently citing functions from a library version we don't even have installed.", "discord", "2026-05-30"),
    ("Made up the entire prisma client method signature. Confidently. Three retries, three different hallucinated APIs.", "in-app", "2026-05-31"),
    ("Helix generated code that imports from `next/edge-functions` (doesn't exist) and `@auth/server-only` (doesn't exist).", "github", "2026-06-01"),
    ("It wrote `await ctx.runMutation(api.notes.create, ...)` but our Convex schema has no `notes` module. It invented one.", "discord", "2026-05-31"),
    ("Spent 90 minutes debugging a 'fix' from Helix that called `fetch.withRetries()` - there's no such method.", "in-app", "2026-05-30"),
    ("@helixai stop hallucinating Drizzle methods. `db.select().joinLateral()` is not in any release.", "twitter", "2026-05-31"),
    ("The agent literally typed `import type { ServerActionContext } from 'react'` - confident, wrong, broke my build.", "github", "2026-06-01"),
]

# --- T2: Irreversible destructive agent action without confirmation (sev 5, 14)
T2 = [
    ("Helix ran rm -rf node_modules AND my src/components folder during a 'cleanup'. No confirm prompt. Lost work.", "discord", "2026-05-29"),
    ("Agent dropped my prisma migration directory because it 'looked obsolete'. We had unmerged migrations in there.", "github", "2026-05-29"),
    ("Composer just did `git push --force` to main without asking. Erased two teammate commits. Please add a guardrail.", "in-app", "2026-05-30"),
    ("Helix ran a destructive DB migration in dev WITHOUT prompting. Lost an afternoon of test data.", "discord", "2026-05-30"),
    ("Agent went rogue and ran `npm uninstall` on 14 packages it 'didn't need' - but we DO need them in production.", "discord", "2026-05-29"),
    ("It DELETED my .env.local file. I literally watched it happen. There was no confirmation.", "in-app", "2026-05-30"),
    ("Helix ran `git reset --hard HEAD~5` without asking. Lost a half-day of work that wasn't pushed.", "discord", "2026-05-31"),
    ("Agent dropped a table in our staging Supabase project. 'This table appears unused.' It was not unused.", "github", "2026-05-30"),
    ("@helixai DELETED MY LOCK FILE. The agent should not be able to touch package-lock.json without permission.", "twitter", "2026-05-30"),
    ("Composer ran `docker system prune -a -f` on its own. Took down our local dev environment. Need confirmation gates.", "in-app", "2026-05-31"),
    ("The agent decided to 'reorganize' my repo and moved 40 files into new directories. PRs are now uninspectable.", "discord", "2026-05-30"),
    ("Helix overwrote my custom webpack config with a generic one. No diff prompt. Have to dig through git reflog now.", "in-app", "2026-05-31"),
    ("Agent ran a tear-down script in our staging environment without asking. AWS bill went weird, took an hour to recover.", "github", "2026-05-30"),
    ("Composer pushed a branch named main-2 to origin and then deleted my actual main branch. How is this allowed?", "discord", "2026-05-31"),
]

# --- T3: Silent model regression - "was fine yesterday" (sev 5, 14) ---------
T3 = [
    ("Helix was great on Friday, now it's lobotomized. What changed? Roll back please.", "discord", "2026-05-31"),
    ("Composer quality has crashed since this weekend. Same prompts that worked are getting wrong, confidently-wrong answers.", "in-app", "2026-06-01"),
    ("Did you ship a model change overnight? My usual workflow is suddenly bad.", "discord", "2026-05-31"),
    ("Yesterday's Helix wrote clean refactors. Today's makes the same change worse three times in a row. Regression.", "in-app", "2026-06-01"),
    ("@helixai your model regressed. The diff quality is dramatically worse this week. Status page is green though.", "twitter", "2026-05-31"),
    ("Helix used to follow my CLAUDE.md conventions. Now it ignores them. Was something rolled back?", "discord", "2026-05-31"),
    ("Same prompt, same codebase, same project. Friday: one-shot fix. Today: 4 turns of trash. What model are we on?", "reddit", "2026-06-01"),
    ("Output quality has tanked over the last 48 hours. Are you A/B testing model versions on prod accounts?", "in-app", "2026-05-31"),
    ("Composer started ignoring my existing types and inventing new ones today. Wasn't doing that last week.", "discord", "2026-06-01"),
    ("Whatever changed Friday night needs to be reverted. The agent is noticeably worse at our react codebase.", "in-app", "2026-05-31"),
    ("Helix is worse at TypeScript inference than it was last Monday. Same files, same edits, more red squigglies.", "discord", "2026-05-31"),
    ("Did you swap us to a smaller model on the Pro tier? Quality drop is too sudden to be anything else.", "reddit", "2026-06-01"),
    ("Composer's planning step has regressed badly. It used to outline 5 steps and execute. Now it skips ahead and breaks things.", "discord", "2026-06-01"),
    ("The agent stopped using our existing utility functions and started reimplementing them inline. This is new this week.", "in-app", "2026-05-31"),
]

# --- T4: Token cost surprise / billed for hallucination loops (sev 4, 12) ---
T4 = [
    ("Hit my $200 monthly cap in four hours debugging a single file. Helix went into a hallucination loop.", "in-app", "2026-05-30"),
    ("Charged for 47k tokens of output that was just the agent trying the same wrong fix five times. Refund please.", "in-app", "2026-05-29"),
    ("My API bill tripled this month and I wrote less code. The agent burns tokens on retries that should be free to me.", "discord", "2026-05-30"),
    ("Why am I billed full price when the agent retries its own bad output? That's your bug, not my usage.", "discord", "2026-05-31"),
    ("Token bill went from $80/mo to $340 this week with no workflow change. Looking at the logs it's all loops.", "in-app", "2026-05-31"),
    ("Helix burned through 80k output tokens on a 60-line file. Most of it was the agent arguing with itself.", "discord", "2026-05-30"),
    ("Cost dashboard shows $42 in one prompt because the agent went in circles. Are you going to make this right?", "in-app", "2026-05-31"),
    ("@helixai a hallucination loop cost me $18 in one sitting. Need a cap I can set per task.", "twitter", "2026-05-31"),
    ("Pro plan was supposed to include 'unlimited reasonable use' but I'm getting throttled at $400/mo on solo work.", "in-app", "2026-05-30"),
    ("Auto-mode on Composer is dangerously expensive. Spent $35 in 20 minutes today. Add a per-task budget please.", "discord", "2026-05-31"),
    ("My team is over our Helix budget by 4x and we shipped less than usual. The math doesn't math.", "in-app", "2026-05-31"),
    ("Asking the agent to fix a typo cost me 12,000 input tokens (it re-read the whole repo). This needs a cap.", "discord", "2026-05-30"),
]

# --- T5: Over-refusal of valid request (sev 3, 12) --------------------------
T5 = [
    ("Asked it to write `DELETE FROM users WHERE test_account = true` against my own test DB and got 'I can't help with that.'", "discord", "2026-05-28"),
    ("Helix refused to help me write a webscraper for my own website. I OWN the site.", "discord", "2026-05-29"),
    ("Trying to write a password reset flow. Agent keeps refusing 'for security reasons'. It's literally part of my own auth.", "in-app", "2026-05-28"),
    ("Over-refusal is getting worse. Won't help with anything touching auth, payments, or data deletion - even in MY repo.", "discord", "2026-05-29"),
    ("'I can't generate code that handles sensitive data.' It's a TODO app. The 'sensitive data' is a string.", "reddit", "2026-05-30"),
    ("Helix won't help me delete a row from my own dev database. Three turns of pushback. Cursor wouldn't do this.", "discord", "2026-05-29"),
    ("Asked for a script to bulk-archive my own customer records (per GDPR). Got refused 4 times before I gave up.", "in-app", "2026-05-28"),
    ("Helix refuses to write the bcrypt comparison in my login route 'for safety'. Bcrypt comparisons are the safe path.", "github", "2026-05-29"),
    ("Won't help me write a CSV export of my own user table for compliance. This is absurd.", "in-app", "2026-05-30"),
    ("Agent refused to write a SQL UPDATE for a column I admittedly own and operate. Lecture about 'best practices' instead.", "discord", "2026-05-29"),
    ("Over-refusal is killing my workflow. Yesterday it refused to help me write rate-limit middleware.", "reddit", "2026-05-30"),
    ("@helixai I am the admin. I can DELETE FROM test_users. Stop refusing.", "twitter", "2026-05-29"),
]

# --- T6: Tool-use schema broke after underlying model update (sev 4, 10) ----
T6 = [
    ("Since last week's update my custom tool registrations 500 with 'unrecognized parameter `description_short`'. Was working.", "github", "2026-05-31"),
    ("Tool-use JSON schemas with `additionalProperties: false` started failing yesterday. Did you change the validator?", "github", "2026-05-30"),
    ("My agent's tools all stopped firing after the Helix update. The function signatures didn't change.", "discord", "2026-05-31"),
    ("Tool schema validation broke when you upgraded the underlying model. Anyone else seeing 400s on tool calls?", "discord", "2026-05-31"),
    ("Helix used to accept `oneOf` in tool params. Now it rejects with 'unsupported schema feature'. When did this change?", "github", "2026-05-31"),
    ("Our entire production agent fleet is failing tool calls today. Have not changed anything on our side in two weeks.", "in-app", "2026-06-01"),
    ("`enum` in a tool parameter now triggers a validation error. Was fine until yesterday. This is a breaking change.", "github", "2026-05-31"),
    ("Composer tool calls are returning empty payloads on tools that used to work. Reproduces 100% of the time.", "discord", "2026-06-01"),
    ("Did you switch us from Sonnet 4.6 to 4.7 silently? Schema strictness changed and our integration broke.", "in-app", "2026-05-31"),
    ("Two of our six custom tools stopped getting invoked. Same prompt, same schema. Started Saturday.", "github", "2026-05-31"),
]

# --- T7: Context window / agent forgot schema mid-turn (sev 3, 10) ----------
T7 = [
    ("Pasted my schema, six turns later the agent invented brand-new column names and rewrote my queries against them.", "discord", "2026-05-30"),
    ("Helix forgot the type definitions I gave it 4 messages ago. Now generating code against a schema I didn't define.", "in-app", "2026-05-31"),
    ("Composer keeps losing the context of the project conventions doc I pinned. Wrote it in the wrong style for the 4th time.", "discord", "2026-05-30"),
    ("Long sessions are unusable. Agent forgets early-session decisions and contradicts itself in late-session edits.", "in-app", "2026-05-31"),
    ("Agent ignored my CLAUDE.md after about turn 8. Generated code that uses libraries we banned in there.", "discord", "2026-05-31"),
    ("Helix re-invented column names I gave it at the start of the session. Pretty critical loss of context.", "in-app", "2026-05-30"),
    ("After 15 turns the agent forgot we use Tailwind v4 and started writing Tailwind v3 syntax.", "discord", "2026-05-31"),
    ("Session length matters: anything past 10-12 turns loses earlier context. The conventions get dropped first.", "reddit", "2026-05-30"),
    ("Loses the project rules halfway through. Now I have to re-paste them every 6 messages, which negates the point.", "discord", "2026-05-31"),
    ("Helix forgot the test framework I told it about and wrote Jest while we use Vitest. Three turns earlier I had told it.", "in-app", "2026-05-31"),
]

# --- T8: First-token latency spike (sev 4, 8) -------------------------------
T8 = [
    ("First token took 14s today. Was 2s last week. Status page is green. What's happening?", "discord", "2026-05-31"),
    ("Helix went from snappy to 8s-to-first-token over the past two days. Did you change something?", "in-app", "2026-06-01"),
    ("Latency on Composer is brutal this week. 10-14s before the agent starts streaming. Was sub-3s before.", "discord", "2026-05-31"),
    ("@helixai TTFT is brutal today. Around 12s for me on us-east. Is anyone else seeing this?", "twitter", "2026-06-01"),
    ("First-token latency tripled on the Pro plan. Cancelled the Team upgrade I was about to do until this is fixed.", "in-app", "2026-05-31"),
    ("Helix takes 9-15s to start responding. Yesterday it was instant. Network is fine on my end (eu-west).", "discord", "2026-05-31"),
    ("Cold starts seem to happen every 30s of inactivity now. The agent feels broken even when it's working.", "in-app", "2026-06-01"),
    ("Composer first-token latency went from sub-3s to ~10s overnight. The fluency improvement isn't worth it.", "discord", "2026-06-01"),
]

# ============================================================================
# CONVENTIONAL-SAAS BRIDGE THEMES (2) - prove Loopback isn't AI-only
# ============================================================================

# --- T9: SSO/SAML redirect loop (sev 5, 16) ---------------------------------
T9 = [
    ("Our Okta SSO logs in then bounces back to the login page. Whole team locked out of Helix this morning.", "email", "2026-05-31"),
    ("SAML auth via Azure AD just stopped working. Two PMs locked out, exec demo at 2pm. Help.", "email", "2026-05-31"),
    ("@helixai SSO redirect loop for everyone on our team. Burning hours on this today.", "twitter", "2026-05-31"),
    ("Cannot log in via Google Workspace SSO. Worked fine last week. Cleared cookies, no change.", "in-app", "2026-05-30"),
    ("alice.cohen@octane.io cannot log in via SSO and has an exec demo at 2pm. Please look ASAP.", "email", "2026-05-31"),
    ("SSO redirect loop has been going on for six hours. Any ETA? Paying customer here.", "in-app", "2026-05-31"),
    ("Whole team locked out of Helix today. SAML login keeps looping back. Tickets piling up.", "email", "2026-05-31"),
    ("Okta admin here. SAML cert hasn't changed. Helix side keeps rejecting the assertion. Help.", "email", "2026-05-31"),
    ("Cannot get into Helix via Okta. Tried password reset, also stuck. Reach me at (415) 555-0199.", "email", "2026-05-30"),
    ("Two-thirds of our 80-person eng org cannot log in today. SSO is in a redirect loop.", "in-app", "2026-05-31"),
    ("SAML response valid in browser devtools but Helix invalidates the session immediately.", "in-app", "2026-05-30"),
    ("Workspace SSO is broken. Email updates to pm-ops@acmecorp.com please.", "email", "2026-05-31"),
    ("Login then SSO provider then Helix dashboard for 0.3s then bounced back to login. Forever.", "in-app", "2026-05-31"),
    ("SSO is down. We're a paying customer. Please status page this - your green dashboard is wrong.", "twitter", "2026-05-31"),
    ("Anybody else stuck in the Helix SSO loop today? My whole team can't get in.", "twitter", "2026-05-31"),
    ("Update: still locked out via SSO. Our IT lead messaged your team yesterday with no response.", "email", "2026-05-31"),
]

# --- T10: Stripe billing double-charge on plan upgrade (sev 5, 10) ----------
T10 = [
    ("Upgraded from Team to Business yesterday and got charged twice. Stripe shows two charges.", "email", "2026-05-30"),
    ("Billing double-charged for the seat add-on. Stripe receipts show identical line items.", "in-app", "2026-05-31"),
    ("@helixai upgraded plan, billed twice within 2 minutes. Stripe receipts came back to back.", "twitter", "2026-05-30"),
    ("I clicked upgrade ONCE. Got two charges. Stripe shows them 4 seconds apart. Idempotency key missing?", "email", "2026-05-30"),
    ("Charged twice for the upgrade. Invoice URL: https://invoice.stripe.com/i/acct_xyz123. Please reverse the dup.", "email", "2026-05-31"),
    ("Got billed double on plan change. Card statement attached. Refund the duplicate please.", "email", "2026-05-30"),
    ("CFO is asking why our Helix bill doubled this month. Looks like the upgrade flow billed us twice.", "email", "2026-05-31"),
    ("Reach me at +44 20 7946 0958 to refund the double charge. I have screenshots.", "email", "2026-05-31"),
    ("Got the same Stripe charge twice when I added 5 seats. Webhook fired twice on your end?", "in-app", "2026-05-30"),
    ("Plan upgrade billed me for both the old AND the new plan. Shouldn't it prorate?", "in-app", "2026-05-31"),
]

# ============================================================================
# NOISE - realistic sub-categories from the research
# ============================================================================

NOISE_PRAISE = [
    ("Helix has saved my team so much time, thank you for building it.", "twitter", "2026-05-30"),
    ("Just shipped a feature in 2 hours that would have taken a day. Love this product.", "twitter", "2026-05-31"),
    ("Best AI dev tool I've used. Sticking with you.", "reddit", "2026-05-29"),
    ("5 stars. Onboarding was smooth, dashboard makes sense, the agent is genuinely useful.", "in-app", "2026-05-30"),
    ("Helix > Cursor for our stack. Thank you for the Convex support.", "discord", "2026-05-31"),
    ("Just want to say the latest Composer update is great.", "twitter", "2026-05-30"),
    ("Cannot live without this in my workflow now.", "reddit", "2026-05-31"),
    ("Switched my whole team from a competitor. So far so good.", "in-app", "2026-05-30"),
    ("Support team responded super fast yesterday. Appreciated.", "email", "2026-05-31"),
    ("The new diff view is so much better than before.", "discord", "2026-05-31"),
    ("Love Helix's approach to multi-file edits. Keep going.", "twitter", "2026-05-31"),
    ("Onboarded my whole startup this week. Smooth experience.", "twitter", "2026-05-30"),
    ("Big fan, please keep iterating. The pace of improvement is impressive.", "reddit", "2026-05-31"),
    ("This app paid for itself the first week we used it.", "in-app", "2026-05-30"),
    ("Recommending Helix to every dev I know. Great work team.", "twitter", "2026-05-31"),
]

NOISE_FEATURE_REQUESTS = [
    ("Will Helix ever support multi-repo workspaces? Our monorepo is rejected.", "discord", "2026-05-31"),
    ("Native Linux desktop app? Web works but a wrapper would help.", "reddit", "2026-05-30"),
    ("Could you add Mandarin to the prompt-language list?", "in-app", "2026-05-29"),
    ("A Pomodoro / focus mode inside the editor would be amazing.", "discord", "2026-05-30"),
    ("Please add Convex / Drizzle as first-class integrations.", "github", "2026-05-31"),
    ("Voice mode for Composer would be incredible. Cursor is doing this.", "discord", "2026-05-31"),
    ("Could we get a public API to programmatically run Composer in CI?", "github", "2026-05-30"),
    ("Notion-style backlinks inside the chat history would help with long sessions.", "discord", "2026-05-31"),
    ("A 'plan only, don't execute' mode by default would be useful for risky changes.", "discord", "2026-05-30"),
    ("Gantt-style view for tracking Composer's long-running tasks?", "in-app", "2026-05-31"),
    ("Native iPad app please. We've got designers who would use Composer for spec docs.", "reddit", "2026-05-31"),
    ("Could you add support for our self-hosted Gitea?", "github", "2026-05-31"),
    ("More verbose explanations option for educational use - we're using Helix in a bootcamp.", "in-app", "2026-05-30"),
    ("Native Jira sync would be huge. Currently doing it through Zapier.", "in-app", "2026-05-31"),
    ("Add a 'budget per task' setting so the agent stops when it hits the cap.", "discord", "2026-05-30"),
    ("Multi-cursor mode in the editor inside Helix?", "discord", "2026-05-31"),
    ("Support for org-wide style guides that override personal preferences?", "in-app", "2026-05-31"),
    ("A model marketplace where I can pick from a list per task?", "reddit", "2026-05-31"),
    ("Could the agent suggest tests proactively after a non-trivial diff?", "discord", "2026-05-30"),
    ("Plugin SDK for our internal infra would let us actually scale this.", "github", "2026-05-31"),
    ("Inline-comment AI mode where I @mention Helix on a PR.", "github", "2026-05-31"),
    ("Native Slack thread integration for support escalation? We use Plain.", "discord", "2026-05-31"),
]

NOISE_PRICING = [
    ("Student discount available? CS grad student, I'd love to use Helix on my thesis project.", "email", "2026-05-30"),
    ("Annual billing discount? We'd commit to 18 months.", "email", "2026-05-31"),
    ("What's the cheapest plan with SSO?", "email", "2026-05-31"),
    ("Nonprofit pricing? We're a 501c3 with 12 developers.", "email", "2026-05-30"),
    ("Could you confirm the per-seat enterprise rate? Sales hasn't responded.", "email", "2026-05-31"),
    ("Pay-as-you-go option without a monthly minimum?", "in-app", "2026-05-30"),
    ("How many tokens does the Pro plan actually include?", "in-app", "2026-05-31"),
    ("Is there a free tier for open-source maintainers?", "discord", "2026-05-30"),
    ("Asked sales about volume pricing twice - any timeline?", "email", "2026-05-31"),
    ("Can I add seats mid-cycle and get prorated?", "in-app", "2026-05-30"),
    ("Education tier for a university? Who do I talk to?", "email", "2026-05-31"),
    ("Will the price stay the same if I downgrade and re-upgrade?", "in-app", "2026-05-30"),
]

NOISE_AUTOREPLIES = [
    ("Automatic reply: I am out of office until Tuesday June 8. For urgent matters please contact ops@example.com.", "email", "2026-05-31"),
    ("Mailer-Daemon: delivery to support+notifications@helix.dev failed permanently.", "email", "2026-05-31"),
    ("Thank you for contacting us. Your ticket #29481 has been created. We will respond within 24 hours.", "email", "2026-05-30"),
    ("Unsubscribe me from your marketing emails. I never opted in to this list.", "email", "2026-05-29"),
    ("Out of office, returning Wednesday. Please email teammate@acme.com in the meantime.", "email", "2026-05-31"),
    ("Auto-reply: I'm at offsite all week with limited email access.", "email", "2026-05-31"),
    ("Notification of delivery failure: 550 5.1.1 The email account that you tried to reach does not exist.", "email", "2026-05-30"),
    ("This is an automated response. Your inquiry has been routed to billing.", "email", "2026-05-31"),
    ("Auto-response: I no longer work at this company. Please contact ops@former-employer.io.", "email", "2026-05-30"),
    ("Vacation responder: away until Monday, will reply on return.", "email", "2026-05-31"),
]

NOISE_JUNK = [
    ("test test", "in-app", "2026-05-31"),
    ("asdf", "in-app", "2026-05-31"),
    ("hi", "in-app", "2026-05-30"),
    ("is this thing on", "in-app", "2026-05-31"),
    ("please ignore - qa test", "in-app", "2026-05-31"),
    (".", "in-app", "2026-05-30"),
]

NOISE_VENTING = [
    ("Today is just one of those days. The app is fine, I'm tired.", "in-app", "2026-05-31"),
    ("Frustrated this morning. Not at you, just generally.", "discord", "2026-05-30"),
    ("Ugh.", "in-app", "2026-05-31"),
    ("Why does software exist.", "twitter", "2026-05-31"),
    ("Mondays.", "twitter", "2026-05-30"),
    ("Posting just to vent. Carry on.", "discord", "2026-05-30"),
    ("I miss MS-DOS sometimes.", "twitter", "2026-05-31"),
    ("My coffee betrayed me before I logged in. Don't blame the agent today.", "in-app", "2026-05-31"),
]

NOISE_HOWTO = [
    ("Where do I find my API key?", "in-app", "2026-05-31"),
    ("How do I rotate my refresh token?", "discord", "2026-05-30"),
    ("Where do I change notification settings?", "in-app", "2026-05-31"),
    ("How do I invite an external collaborator?", "in-app", "2026-05-30"),
    ("What's the keyboard shortcut to start a new Composer session?", "discord", "2026-05-31"),
    ("Where can I see token usage by repo?", "in-app", "2026-05-31"),
    ("How do I revoke a personal access token?", "in-app", "2026-05-30"),
    ("Where do I configure org-wide rules?", "in-app", "2026-05-31"),
    ("How do I export my Composer history?", "in-app", "2026-05-30"),
    ("How do I make a workspace template?", "in-app", "2026-05-31"),
    ("How do I share a chat with a non-member?", "in-app", "2026-05-30"),
    ("Where do I find my billing history?", "in-app", "2026-05-30"),
    ("Where do I report a bug?", "in-app", "2026-05-31"),
    ("How do I check which model I'm currently on?", "in-app", "2026-05-31"),
    ("Is there a way to pin a system prompt across sessions?", "discord", "2026-05-30"),
]

NOISE_OFFTOPIC = [
    ("Saw your team at AI Engineer Summit last week, great talk!", "twitter", "2026-05-30"),
    ("Hi, I'm a designer interested in joining Helix. Where do I apply?", "email", "2026-05-31"),
    ("Are you hiring engineers? Senior backend, 10 years experience.", "email", "2026-05-30"),
    ("Can I get a refund for the trial?", "email", "2026-05-31"),
    ("Marketing request: can someone change our org name in the workspace?", "email", "2026-05-30"),
    ("Do you ship swag with paid plans?", "email", "2026-05-31"),
    ("Hello, please reach out to discuss a partnership opportunity.", "email", "2026-05-31"),
    ("Thanks for the quick response yesterday.", "email", "2026-05-30"),
    ("Following up on my last email - any update on the demo?", "email", "2026-05-31"),
    ("Wanted to send a thank-you for the gift card. Lovely surprise.", "email", "2026-05-30"),
]

NOISE_ONE_OFFS = [
    ("The export to PDF shows blank pages on Firefox 122.", "in-app", "2026-05-30"),
    ("Markdown in the activity feed would be nice.", "in-app", "2026-05-29"),
    ("Profile picture doesn't upload, but only on Safari iOS 18.", "in-app", "2026-05-31"),
    ("Search doesn't find archived chats.", "in-app", "2026-05-31"),
    ("Webhook payloads are missing the user_id field after the v3 update.", "github", "2026-05-30"),
    ("Cannot see comments from deleted users in the activity log.", "in-app", "2026-05-31"),
    ("Pagination on the API returns inconsistent counts between pages.", "github", "2026-05-30"),
    ("Tooltips overflow the screen on the right edge in 1080p.", "in-app", "2026-05-31"),
    ("Date picker in Safari doesn't show correct week numbers.", "in-app", "2026-05-29"),
    ("Color picker UX in custom fields is fiddly on touch screens.", "in-app", "2026-05-30"),
    ("Notifications panel sometimes shows the same item twice.", "in-app", "2026-05-31"),
    ("Member directory pagination skips the last page sometimes.", "in-app", "2026-05-30"),
    ("In Firefox, drag-and-drop reorders cards but the order resets on refresh.", "in-app", "2026-05-31"),
    ("Email digest comes at 3am for me. Where do I configure that?", "in-app", "2026-05-30"),
    ("Workspace member badges show 'inactive' for users who logged in yesterday.", "in-app", "2026-05-31"),
    ("Mobile gestures (swipe to archive) trigger on accidental touches.", "in-app", "2026-05-29"),
    ("Whiteboard tool shows my cursor jitter when collaborating.", "in-app", "2026-05-31"),
    ("Activity timeline missed an event when I created a card via API.", "github", "2026-05-30"),
    ("Card title truncation cuts off useful info. Show a tooltip on hover?", "in-app", "2026-05-31"),
    ("API rate-limit headers are inconsistent between endpoints.", "github", "2026-05-29"),
    ("Pasted images get re-encoded poorly and lose detail.", "in-app", "2026-05-30"),
    ("In dark mode the green text color is too low contrast against the background.", "in-app", "2026-05-31"),
    ("Some emojis (regional indicators) don't render in chat history.", "discord", "2026-05-31"),
    ("Right-click context menu doesn't show on touchpad two-finger taps.", "in-app", "2026-05-30"),
    ("Audit log doesn't capture role changes for service accounts.", "in-app", "2026-05-31"),
]

NOISE_MULTI_ISSUE = [
    ("Helix hallucinated an import AND my Stripe invoice doubled this morning. Compound bad day.", "email", "2026-05-31"),
    ("Two issues: SSO is broken AND I got charged for a hallucination loop. Help me?", "in-app", "2026-05-31"),
    ("Honestly bad week: comments disappearing, model is worse, my bill is up. Are y'all OK?", "in-app", "2026-06-01"),
    ("Got billed twice last week AND the agent deleted a folder. Need both fixed please.", "email", "2026-05-30"),
    ("iOS app crashes on the Files tab AND the agent invented a Prisma method. Mobile + AI both rough today.", "twitter", "2026-05-31"),
    ("SSO locked us out AND when I worked around it via PAT, Composer was clearly worse than yesterday. Bad timing.", "discord", "2026-05-31"),
    ("Multiple things broken today: dark mode flicker on the diff view, comments missing, agent refused a valid task.", "in-app", "2026-05-30"),
    ("Comments disappeared. Then I refreshed and got the SSO redirect loop. Then I gave up.", "in-app", "2026-05-31"),
]

NOISE_UPSTREAM_OUTAGE = [
    ("Helix is down - wait, it's actually AWS us-east-1, never mind.", "twitter", "2026-05-31"),
    ("Why is Helix broken - oh, looks like Vercel is having an outage. Please ignore.", "twitter", "2026-05-30"),
    ("My deploys are failing. Is it Helix? Oh - Stripe webhook is down, blocking our checkout. Sorry.", "discord", "2026-05-31"),
    ("Cannot connect. Status page says 'all systems operational' but I'm getting 503. Update - it's Cloudflare.", "in-app", "2026-05-31"),
    ("Composer is timing out for me. Oh, looks like Anthropic's API is having a moment. Carry on.", "discord", "2026-05-30"),
    ("My GitHub Actions runs are failing on Helix steps. Update: GitHub is down, never mind.", "github", "2026-05-31"),
    ("Helix is broken - actually it's Supabase having auth issues for the third time this month.", "discord", "2026-05-31"),
    ("Tool calls failing. Update - DNS issue on my end. False alarm.", "discord", "2026-05-30"),
]

NOISE_PII_PASTES = [
    ("My env says OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345 and the agent refuses to read from it - is this leaking?", "in-app", "2026-05-31"),
    ("Helix logged my Anthropic key ANTHROPIC_API_KEY=sk-ant-api03-AbCdEfGhIjKlMnOpQrSt-XYZ in the chat. Should I rotate?", "in-app", "2026-05-30"),
    ("Pasted my Stripe key sk_live_51HXXXAbCdEfGhIjKlMnOp into a debug message. Did this end up in your logs?", "discord", "2026-05-31"),
    ("My .env contains POSTGRES_API_KEY='abcdef123456' - agent refuses to use it. Should I be worried it saw it?", "in-app", "2026-05-31"),
    ("Token attached for debugging: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature - can you trace?", "in-app", "2026-05-30"),
]

NOISE_WRONG_CHANNEL = [
    ("Submitted via sales contact form: my account got billed twice last week. Help?", "email", "2026-05-31"),
    ("Posting here because no one is replying in support: pricing question - do you do annual prepay?", "discord", "2026-05-30"),
    ("[Wrong channel, sorry] partnership pitch - we sell hosting and want to discuss bundling.", "in-app", "2026-05-31"),
    ("Posted this in #incidents because nothing else worked: how do I upgrade my plan?", "discord", "2026-05-30"),
    ("Reaching out via support because Discord moderation is slow: feature request for a Linux build.", "in-app", "2026-05-31"),
    ("Filing as a bug because I can't find sales contact: need an enterprise quote.", "github", "2026-05-30"),
]

NOISE_NON_ENGLISH = [
    ("El agente no respeta nuestras convenciones internas, sigue cambiando los nombres de las columnas.", "discord", "2026-05-31"),
    ("Helix está alucinando funciones que no existen en nuestra base de código. Por favor revisar.", "in-app", "2026-05-30"),
    ("Helix が今日 SSO ループでログインできません。Okta 連携が壊れています。", "in-app", "2026-05-31"),
    ("Composer beendet sich mit einem Fehler wenn ich grosse Dateien hochlade. Reproduzierbar.", "discord", "2026-05-30"),
    ("O agente acabou de deletar minha pasta de migrations sem perguntar. Preciso de ajuda urgente.", "in-app", "2026-05-31"),
    ("Notre intégration SSO via Azure AD est cassée depuis ce matin. Plus de cinquante développeurs bloqués.", "email", "2026-05-31"),
]

NOISE_SCREENSHOT_ONLY = [
    ("can someone help? [image attached]", "in-app", "2026-05-31"),
    ("see attached [screenshot.png]", "in-app", "2026-05-30"),
    ("this is broken [image]", "discord", "2026-05-31"),
    ("look at this [photo]", "twitter", "2026-05-31"),
    ("what does this mean? [image attached]", "in-app", "2026-05-30"),
    ("anyone seen this before? [screenshot]", "discord", "2026-05-31"),
]

NOISE_CHURN = [
    ("Lovable shipped a working version of this in one shot. Cancelling sorry.", "in-app", "2026-05-31"),
    ("Trying Cursor instead - Helix has been worse for our stack lately.", "discord", "2026-05-31"),
    ("Replit Agent is doing what I wanted Helix to do, for half the price. Pausing my sub.", "reddit", "2026-05-30"),
    ("Cancelling, going to v0 for prototyping. Helix doesn't read our stack well.", "in-app", "2026-05-31"),
    ("Bolt's diff quality is better than yours this week. Cancelling team plan.", "in-app", "2026-05-30"),
    ("Devin shipped a real PR for us yesterday. You're behind. Cancelling.", "twitter", "2026-05-31"),
    ("Trying Claude Code direct, skipping Helix. The middleman is hurting more than helping.", "discord", "2026-05-31"),
    ("If Helix doesn't fix the regression by Friday, our team is going back to Copilot.", "in-app", "2026-05-31"),
]


# ============================================================================
# VARIANTS - three demo CSVs, each scripted for a different story
# ============================================================================
# Per (pool, n): take the first `n` items deterministically, or all if None.
# We deliberately do not randomly sample within a theme: the leading messages
# in each pool are the most evocative, and we want the same n every run.
#
# Stories:
#   first-week.csv      Fresh project state. Smaller, calmer inbox dominated by
#                       a single big outage (SSO) plus a couple of pain themes.
#                       Demo beat: clean triage, mostly NEW tickets filed.
#
#   weekly-batch.csv    Mature project state. The full chaotic week with every
#                       theme and every noise category present. Demo beat:
#                       MIXED lanes - high-confidence + needs-review + extend.
#
#   post-incident.csv   Recent ship broke something. Concentrated cluster of
#                       quality complaints (silent regression + tool-schema
#                       break + latency spike) plus spillover and incident
#                       noise. Demo beat: REGRESSION detection + extends.

VARIANTS = {
    "first-week.csv": {
        "themes": [
            (T9, None),  # 16 - SSO outage, the biggest signal of the week
            (T10, 6),    # Stripe double-charge
            (T2, 6),     # destructive agent action
            (T1, 6),     # hallucination
            (T4, 4),     # token cost surprise
        ],
        "noise": [
            (NOISE_AUTOREPLIES, 4),
            (NOISE_PRAISE, 4),
            (NOISE_PRICING, 4),
            (NOISE_HOWTO, 4),
            (NOISE_FEATURE_REQUESTS, 4),
            (NOISE_ONE_OFFS, 8),
            (NOISE_NON_ENGLISH, 2),
            (NOISE_VENTING, 2),
            (NOISE_OFFTOPIC, 5),
        ],
    },
    "weekly-batch.csv": {
        "themes": [(t, None) for t in (T1, T2, T3, T4, T5, T6, T7, T8, T9, T10)],
        "noise": [
            (NOISE_PRAISE, None),
            (NOISE_FEATURE_REQUESTS, None),
            (NOISE_PRICING, None),
            (NOISE_AUTOREPLIES, None),
            (NOISE_JUNK, None),
            (NOISE_VENTING, None),
            (NOISE_HOWTO, None),
            (NOISE_OFFTOPIC, None),
            (NOISE_ONE_OFFS, None),
            (NOISE_MULTI_ISSUE, None),
            (NOISE_UPSTREAM_OUTAGE, None),
            (NOISE_PII_PASTES, None),
            (NOISE_WRONG_CHANNEL, None),
            (NOISE_NON_ENGLISH, None),
            (NOISE_SCREENSHOT_ONLY, None),
            (NOISE_CHURN, None),
        ],
    },
    "post-incident.csv": {
        "themes": [
            (T3, None),  # 14 - silent regression, the dominant signal
            (T6, None),  # 10 - tool-use schema broke after model update
            (T8, None),  # 8 - first-token latency spike
            (T1, 8),     # hallucination uptick after the regression
            (T7, 6),     # context window / forgot schema mid-turn
            (T2, 4),     # spillover destructive-action reports
            (T4, 4),     # spillover token-cost complaints
        ],
        "noise": [
            (NOISE_UPSTREAM_OUTAGE, None),  # 8 - people misattributing
            (NOISE_CHURN, None),            # 8 - threats to leave for competitors
            (NOISE_MULTI_ISSUE, None),      # 8 - compound bad-day reports
            (NOISE_VENTING, 4),
            (NOISE_PRAISE, 4),
            (NOISE_AUTOREPLIES, 4),
            (NOISE_ONE_OFFS, 6),
            (NOISE_SCREENSHOT_ONLY, 4),
        ],
    },
}


def _take(pool: list[tuple[str, str, str]], n: int | None) -> list[tuple[str, str, str]]:
    return pool if n is None else pool[:n]


def _emit(name: str, spec: dict, seed: int) -> tuple[int, int]:
    rows: list[tuple[str, str, str]] = []
    actionable = 0
    for pool, n in spec["themes"]:
        taken = _take(pool, n)
        rows.extend(taken)
        actionable += len(taken)
    noise = 0
    for pool, n in spec["noise"]:
        taken = _take(pool, n)
        rows.extend(taken)
        noise += len(taken)

    rng = random.Random(seed)
    rng.shuffle(rows)

    targets = [
        ROOT / "data" / name,
        ROOT / "web" / "public" / name,
    ]
    for path in targets:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "text", "channel", "date"])
            for i, (text, channel, date) in enumerate(rows, start=1):
                w.writerow([i, text, channel, date])
    print(
        f"{name:24s} actionable={actionable:3d}  noise={noise:3d}  total={len(rows):3d}"
    )
    return actionable, noise


def main() -> None:
    """Build all three demo CSVs deterministically. Each variant gets its own
    seed so the shuffled order is stable run-to-run but different per variant."""
    for offset, (name, spec) in enumerate(VARIANTS.items()):
        _emit(name, spec, seed=SEED + offset)


if __name__ == "__main__":
    main()
