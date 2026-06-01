"""Generate a richer demo CSV — 150 signals across 7 clusterable themes plus
realistic noise (praise, off-topic feature requests, pricing questions, test
junk, generic venting, support how-to, single one-off complaints).

The themes are calibrated so the Triage Router Agent splits 3 high-confidence
and 4 needs-review, and the PII redactor finds a visible number of emails,
phone numbers, and URLs scattered through realistic prose.

Run: python scripts/build_demo_csv.py
Writes: data/sample_feedback.csv and web/public/sample_feedback.csv (the path
the static export serves to the hosted UI's "try sample" link).
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).parent.parent

# --- THEME 1: SSO/SAML login redirect loop (severity 5, 22 reports) ---------
T1 = [
    ("Our Okta SSO logs in then bounces straight back to the login screen. Cannot get into Nimbus today.", "chat", "2026-05-26"),
    ("SSO is broken. Click login, get redirected to /auth, redirected back to login. Infinite loop.", "support", "2026-05-26"),
    ("Hi team, SAML auth from our Azure AD just stopped working today. Two of our PMs locked out.", "email", "2026-05-25"),
    ("@nimbusapp SSO loop happening for everyone on our team in Berlin. Burning hours on this.", "twitter", "2026-05-26"),
    ("Tried Okta, tried email magic link, both kick me back to login screen. Lost half my morning.", "review", "2026-05-25"),
    ("Cannot log in with Google Workspace SSO anymore. Worked fine last week.", "support", "2026-05-22"),
    ("alice.cohen@octane.io can't log in via SSO and we have an exec demo at 2pm. Please look.", "email", "2026-05-26"),
    ("Logging in via Microsoft Entra used to work, now I just get stuck on the login page.", "chat", "2026-05-24"),
    ("SSO redirect loop has been going on for six hours. Any ETA?", "support", "2026-05-26"),
    ("Nimbus plus Okta equals redirect hell. Try login, instant bounce back. Have a screenshot at https://i.imgur.com/4hjs9p2.png", "twitter", "2026-05-25"),
    ("Whole team locked out of Nimbus this morning. SSO login keeps looping back. Tickets piling up.", "email", "2026-05-26"),
    ("Login then SSO provider then land on dashboard for 0.3 seconds then bounced to login. Repeat forever.", "chat", "2026-05-26"),
    ("Customer support said clear cookies. Cleared cookies. Still redirect loop. Bumping to engineering.", "support", "2026-05-26"),
    ("We're paying for ten seats and our team has been locked out for four hours. SSO is in a redirect loop.", "email", "2026-05-26"),
    ("SAML response looks valid in browser devtools but the app immediately invalidates the session.", "support", "2026-05-25"),
    ("Cannot get into Nimbus via Okta. Tried password reset, also stuck. Reach me at (415) 555-0199.", "email", "2026-05-25"),
    ("Have all engineering managers locked out due to SSO. This is impacting standups.", "chat", "2026-05-26"),
    ("Okta admin here. SAML cert hasn't changed. Nimbus side keeps rejecting the assertion. Help.", "support", "2026-05-25"),
    ("App keeps redirecting me back to login after I sign in via Google. Cleared cache, no change.", "chat", "2026-05-23"),
    ("Login then redirected to login then loop. Anyone else seeing this?", "twitter", "2026-05-25"),
    ("Just attempted SSO. Got redirected to /login?error=session_expired three times in a row.", "support", "2026-05-24"),
    ("Workspace SSO is broken. Email me with status updates at pm-ops@acmecorp.com", "email", "2026-05-26"),
]

# --- THEME 2: Document sync loses edits / data loss (severity 5, 18 reports) --
T2 = [
    ("Just wrote a two-page brief, switched tabs, came back and 30 minutes of work was gone.", "support", "2026-05-21"),
    ("Document sync is unreliable. Yesterday lost a whole spec doc when teammate edited at same time.", "chat", "2026-05-20"),
    ("I edit a document, refresh, my changes are gone but the timestamp says it saved. Data loss.", "support", "2026-05-19"),
    ("Lost notes from yesterday's planning meeting. They were there last night, gone this morning.", "email", "2026-05-22"),
    ("Conflict resolution on simultaneous edits is terrible. Whoever saves last wins, the rest just disappears.", "chat", "2026-05-18"),
    ("I just lost an hour of work. Real-time collab claimed to save but actually didn't.", "support", "2026-05-23"),
    ("Why does Nimbus silently drop my edits when there's a network blip? At least warn me.", "review", "2026-05-17"),
    ("Two of us editing the same doc. My edits vanished when she hit save. No conflict prompt.", "email", "2026-05-19"),
    ("'Document was saved successfully' the toast said. Then I refreshed and half my content was gone.", "support", "2026-05-21"),
    ("Real-time editing is broken when two people are typing. Lost 20 minutes of meeting notes.", "chat", "2026-05-20"),
    ("How is data loss happening in 2026 on a paid product? Lost a doc this morning.", "twitter", "2026-05-22"),
    ("Document edits revert randomly. Saved version is always older than what's on screen.", "support", "2026-05-18"),
    ("PM here. Just lost an entire PRD because Nimbus 'synced' over my version with an older one.", "email", "2026-05-19"),
    ("Switched tabs for 30 seconds, came back, doc reverted to 5 minutes ago. Where did my edits go?", "chat", "2026-05-22"),
    ("Real-time collab silently drops keystrokes when connection wobbles. Have logs at https://gist.github.com/abc123def", "support", "2026-05-20"),
    ("Lost work three times this week. We're evaluating moving off Nimbus because of this.", "email", "2026-05-22"),
    ("Sync indicator says synced. Refresh. Content from ten minutes ago. Lost ten minutes of writing.", "chat", "2026-05-21"),
    ("Nimbus document just ate forty minutes of my work. No warning, no conflict prompt, just gone.", "support", "2026-05-22"),
]

# --- THEME 3: Stripe billing double-charge on plan upgrade (sev 5, 14) ------
T3 = [
    ("Upgraded from Team to Business plan yesterday and got charged twice. Stripe shows two charges.", "support", "2026-05-15"),
    ("I see two charges on my card for the plan upgrade. Need a refund for the duplicate.", "email", "2026-05-14"),
    ("Billing double-charged us for the seat add-on. Stripe receipts show identical line items.", "support", "2026-05-16"),
    ("Upgrade flow charged me twice. Card statement attached. Please refund.", "email", "2026-05-13"),
    ("Why am I being charged for both my old plan AND the new plan after upgrade? Shouldn't it prorate?", "support", "2026-05-12"),
    ("@nimbusapp upgraded plan, got billed twice within 2 minutes. Stripe confirmation emails came back to back.", "twitter", "2026-05-14"),
    ("After upgrading, I see two transactions in Stripe customer portal. Both successful. Both for the same amount.", "support", "2026-05-15"),
    ("Got billed double on plan change. Invoice URL: https://invoice.stripe.com/i/acct_xyz123. Please reverse the dupe.", "email", "2026-05-16"),
    ("Charged twice for the upgrade. First invoice paid in cents, second one in dollars. Bug in your pricing logic?", "support", "2026-05-11"),
    ("I upgraded a week ago and now I see TWO recurring charges every month. Cancel the old one please.", "email", "2026-05-17"),
    ("Just upgraded plan, immediately got two Stripe receipts in inbox for the same amount.", "twitter", "2026-05-15"),
    ("Old plan was supposed to be cancelled on upgrade. Got billed for both this morning.", "support", "2026-05-16"),
    ("I clicked upgrade once. Got two charges. Stripe shows them 4 seconds apart.", "email", "2026-05-14"),
    ("Reach me at +44 20 7946 0958 to refund the double charge. I have screenshots.", "support", "2026-05-15"),
]

# --- THEME 4: iOS app crashes opening Files tab on iOS 18 (sev 4, 12) -------
T4 = [
    ("iOS app crashes the moment I tap the Files tab. iPhone 15, iOS 18.2.1.", "review", "2026-05-10"),
    ("Files tab equals instant crash on iOS 18. Other tabs are fine.", "appstore", "2026-05-11"),
    ("Latest iOS update broke the app. Files tab crashes within a second of opening.", "review", "2026-05-12"),
    ("Updated to iOS 18, now Nimbus crashes opening Files. iPhone 14 Pro.", "appstore", "2026-05-09"),
    ("Files tab is unusable on iOS 18.2. Crashes the entire app every time.", "review", "2026-05-13"),
    ("Tap Files then app vanishes then reopens then repeat. Have to force quit the app to escape.", "support", "2026-05-12"),
    ("Crashes consistently on Files since I updated to iOS 18 last week. Two stars until fixed.", "appstore", "2026-05-13"),
    ("@nimbusapp iOS app crashes opening Files on iOS 18, please push a fix", "twitter", "2026-05-12"),
    ("Cannot use the iOS app at all because Files tab crashes and I need to see my docs.", "review", "2026-05-14"),
    ("Files tab on iOS equals crash. Worked fine on iOS 17. iPhone 15 Plus.", "appstore", "2026-05-13"),
    ("iOS 18 user reporting: opening Files immediately crashes Nimbus. Crash log: https://gist.github.com/x9f4a", "support", "2026-05-12"),
    ("Files tab crashes the iOS app. Other tabs work. iOS 18.1.1, iPhone 14.", "review", "2026-05-11"),
]

# --- THEME 5: Slack notifications duplicated / spammy (sev 3, 10) -----------
T5 = [
    ("Getting four Slack notifications for every single comment in Nimbus. We disabled the integration.", "slack", "2026-05-08"),
    ("Slack integration is way too noisy, every micro-edit pings the channel. Cannot keep this on.", "support", "2026-05-07"),
    ("Why am I getting three identical Slack pings every time someone updates a card?", "email", "2026-05-09"),
    ("Slack notifications are duplicated. Every event fires twice in our #product channel.", "slack", "2026-05-08"),
    ("Disabled the Slack integration because it spammed our channel with duplicate pings constantly.", "support", "2026-05-06"),
    ("Each Nimbus event creates 2 to 4 Slack messages. Made our channel unusable.", "email", "2026-05-10"),
    ("Slack integration is broken, same notification arrives three times in a row.", "slack", "2026-05-09"),
    ("Slack integration pings me 4x for one comment. Disabled, can't use it.", "support", "2026-05-07"),
    ("Duplicate Slack notifications every time I update a card. Reach me at maya.lee@bigco.com to test.", "email", "2026-05-08"),
    ("Slack notifications are duplicating since last week's update. Have to mute the channel.", "slack", "2026-05-09"),
]

# --- THEME 6: Slow loading on large boards (>500 items) (sev 3, 10) ---------
T6 = [
    ("Boards with more than 500 cards take 30+ seconds to load. We have boards with 2000 cards.", "chat", "2026-05-05"),
    ("Our roadmap board has 800 items and it freezes the tab for ages when I open it.", "support", "2026-05-04"),
    ("Board load times are getting worse as we add more items. 1500-card board now takes a minute.", "review", "2026-05-06"),
    ("Why does the app block the entire UI while loading a large board? Cannot do anything else.", "chat", "2026-05-05"),
    ("Performance on large boards is unacceptable. We're a 50-person team with 2000+ items.", "email", "2026-05-07"),
    ("Board with 1200 cards takes 45 seconds to render. Was 15 seconds two months ago.", "support", "2026-05-06"),
    ("Large board equals browser freeze for 30 seconds. Tab unresponsive until it loads everything.", "chat", "2026-05-04"),
    ("Big boards (1k+ items) are getting slower every release. Now barely usable.", "review", "2026-05-08"),
    ("Could you paginate large boards? 1000+ cards locks my Chrome tab.", "support", "2026-05-05"),
    ("Boards over 500 items are super slow. We're considering moving to a competitor for this alone.", "email", "2026-05-07"),
]

# --- THEME 7: Dark mode flicker on modals/transitions (sev 2, 8) ------------
T7 = [
    ("Dark mode flickers to light mode whenever a modal opens. Annoying but minor.", "review", "2026-05-02"),
    ("Modal dialogs always flash white in dark mode. Hurts my eyes at night.", "chat", "2026-05-03"),
    ("Dark mode is incomplete. Settings panel and modals still render in light theme.", "review", "2026-05-04"),
    ("Open settings in dark mode equals flash of white. Please fix.", "twitter", "2026-05-03"),
    ("Dark mode flicker between routes. Whole screen flashes light for half a second.", "review", "2026-05-04"),
    ("Modals don't inherit dark mode. White flash every time I open one.", "chat", "2026-05-02"),
    ("Page transitions in dark mode briefly show the light theme. It's jarring.", "review", "2026-05-03"),
    ("Dark mode is still broken on modals after the latest update. Reported this last month too.", "twitter", "2026-05-04"),
]

# --- NOISE: praise, off-topic, pricing, junk, venting, how-to, one-offs ----
NOISE = [
    # praise (10)
    ("Love the new dashboard layout, much cleaner than before!", "twitter", "2026-05-15"),
    ("Best PM tool I've used. Sticking with Nimbus.", "review", "2026-05-18"),
    ("Just shipped our quarterly roadmap with Nimbus. Honestly amazing tool.", "twitter", "2026-05-20"),
    ("Cannot live without this app, thank you for building it!", "review", "2026-05-22"),
    ("The team loves Nimbus. Keep up the great work.", "email", "2026-05-21"),
    ("Nimbus is the best productivity tool out there.", "appstore", "2026-05-19"),
    ("Five stars. Use it every day. Don't change anything :)", "appstore", "2026-05-20"),
    ("Switched my whole team from Asana to Nimbus and we're never going back.", "review", "2026-05-17"),
    ("Your customer success team is excellent.", "email", "2026-05-22"),
    ("Just want to say thanks for the recent UX improvements.", "twitter", "2026-05-23"),
    # off-topic feature requests / one-offs (10)
    ("Will you ever add Mandarin language support? Some of our team would love it.", "email", "2026-05-10"),
    ("Calendar integration with Outlook would be amazing. Please consider.", "support", "2026-05-12"),
    ("I wish I could draw on whiteboards inside Nimbus.", "review", "2026-05-14"),
    ("AI summary feature would be great for long docs.", "chat", "2026-05-16"),
    ("Can you add a Pomodoro timer? Would help our team focus.", "email", "2026-05-13"),
    ("Why no native Linux desktop app? Web is fine but a wrapper would be nice.", "review", "2026-05-11"),
    ("Please add custom emoji reactions in comments.", "chat", "2026-05-15"),
    ("Voice notes in comments would be a killer feature for remote teams.", "review", "2026-05-12"),
    ("What about a public API for time tracking?", "support", "2026-05-13"),
    ("Considering Notion. What would you say to convince me to stay?", "email", "2026-05-14"),
    # pricing questions (5)
    ("Is there a student discount? I'm an MSc student using Nimbus for thesis work.", "email", "2026-05-09"),
    ("Do you offer an annual billing discount? Currently on monthly.", "support", "2026-05-10"),
    ("What's the cheapest plan that supports SSO?", "email", "2026-05-11"),
    ("Nonprofit pricing available? We're a 501c3.", "email", "2026-05-12"),
    ("Will the price stay the same if I upgrade now? Worried about hidden fees.", "support", "2026-05-13"),
    # test/junk (5)
    ("test test", "chat", "2026-05-25"),
    ("asdf", "chat", "2026-05-26"),
    ("hi", "chat", "2026-05-26"),
    ("is this thing on", "chat", "2026-05-25"),
    ("delete this", "support", "2026-05-24"),
    # generic venting (5)
    ("Today is just one of those days. The app is fine, I'm just tired.", "chat", "2026-05-19"),
    ("Frustrated this morning. Not at you, just generally.", "chat", "2026-05-20"),
    ("Ugh.", "chat", "2026-05-21"),
    ("Why does software exist.", "twitter", "2026-05-22"),
    ("Mondays.", "twitter", "2026-05-18"),
    # support how-to (5)
    ("How do I export my workspace as PDF?", "support", "2026-05-08"),
    ("Where do I change my notification settings?", "support", "2026-05-07"),
    ("How do I invite an external collaborator?", "support", "2026-05-09"),
    ("What's the keyboard shortcut for new task?", "chat", "2026-05-10"),
    ("Where can I see my recent activity?", "support", "2026-05-11"),
    # misc unrelated (8)
    ("Saw your team at the conference last week, great talk!", "email", "2026-05-16"),
    ("Hi, I'm a designer interested in joining your team. Where do I apply?", "email", "2026-05-15"),
    ("Are you guys hiring engineers? Send me details.", "email", "2026-05-17"),
    ("Can I get a refund for the trial?", "support", "2026-05-18"),
    ("Marketing team request: change the logo color on our workspace?", "support", "2026-05-19"),
    ("Do you ship swag with paid plans? Asking for the office.", "email", "2026-05-20"),
    ("Hello, please reach out to discuss potential partnership opportunities.", "email", "2026-05-21"),
    ("Thanks for the quick response yesterday.", "email", "2026-05-22"),
    # one-off complaints that don't cluster with anything (8)
    ("The print preview for documents shows blank pages on Firefox.", "support", "2026-05-13"),
    ("Can you support Markdown in the activity feed?", "support", "2026-05-14"),
    ("Sometimes my profile picture doesn't upload, but only on Safari.", "chat", "2026-05-15"),
    ("Search doesn't find archived items. Took me an hour to find a doc.", "support", "2026-05-16"),
    ("Webhook payloads are missing the user_id field after the v3 update.", "email", "2026-05-17"),
    ("I can't see comments from deleted users in the activity log.", "support", "2026-05-18"),
    ("Pagination on the API returns inconsistent counts between pages.", "support", "2026-05-19"),
    ("Tooltips overflow the screen on the right edge in 1080p.", "chat", "2026-05-20"),
]


def main() -> None:
    rows: list[tuple[int, str, str, str]] = []
    sid = 1
    for theme in (T1, T2, T3, T4, T5, T6, T7, NOISE):
        for text, channel, date in theme:
            rows.append((sid, text, channel, date))
            sid += 1
    # interleave so the agent does real clustering work (not pre-sorted by theme)
    rows = _interleave(rows)
    targets = [
        ROOT / "data" / "sample_feedback.csv",
        ROOT / "web" / "public" / "sample_feedback.csv",
    ]
    for path in targets:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "text", "channel", "date"])
            for sid_, text, channel, date in rows:
                w.writerow([sid_, text, channel, date])
        print(f"wrote {len(rows)} rows -> {path}")
    print(
        f"actionable: {len(T1)+len(T2)+len(T3)+len(T4)+len(T5)+len(T6)+len(T7)}, "
        f"noise: {len(NOISE)}, total: {len(rows)}"
    )


def _interleave(rows: list[tuple[int, str, str, str]]) -> list[tuple[int, str, str, str]]:
    """Shuffle deterministically so a human scrolling the CSV doesn't see the themes
    sorted into groups. Uses a fixed-seed Random so the same input always produces
    the same output — reproducible across runs."""
    import random as _random

    rng = _random.Random(42)
    shuffled = list(rows)
    rng.shuffle(shuffled)
    return [(i + 1, r[1], r[2], r[3]) for i, r in enumerate(shuffled)]


if __name__ == "__main__":
    main()
