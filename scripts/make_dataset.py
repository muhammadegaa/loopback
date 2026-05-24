"""Generate data/sample_feedback.csv — ~150 realistic customer support messages.

Six recurring problem themes plus non-actionable noise (praise, off-topic, spam,
unrelated feature requests). Deterministic (fixed seed) so the demo dataset is stable.
Run: python scripts/make_dataset.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 7
random.seed(SEED)

# Each theme: a pool of distinct, realistic phrasings. Noise is intentionally
# non-actionable so clustering must separate signal from chatter.
THEMES: dict[str, list[str]] = {
    "session_logout": [
        "The app logs me out every few minutes and I lose whatever I was typing.",
        "Why do I keep getting signed out? I've had to log back in five times this hour.",
        "Session keeps expiring mid-task. Just lost 20 minutes of unsaved work.",
        "Got kicked out again while filling in a form. Incredibly frustrating.",
        "I stay logged in for maybe 10 minutes then it dumps me back to the login screen.",
        "Constant random logouts on the web app. Is this a known issue?",
        "Every time I switch tabs and come back I have to sign in again.",
        "My session drops the moment I stop typing for a bit. Lost a whole draft.",
        "Please fix the auto-logout, it's making the product unusable for long edits.",
        "Logged out three times during a single support call with my own customer.",
        "The 'remember me' checkbox does nothing, I'm signed out within minutes anyway.",
        "Session timeout is way too aggressive. I lose work constantly.",
        "Keeps logging me out on mobile and desktop both. Auth feels broken.",
        "I refreshed the page and suddenly I'm logged out and my form is gone.",
        "Had to re-authenticate four times just to finish one report. Painful.",
        "The session expiry warning never shows, it just silently logs me out.",
        "Why does it forget my login so fast? Competitors keep me signed in for days.",
        "Lost an hour of notes because it logged me out without saving anything.",
        "Auth token seems to expire instantly, I'm re-logging every few minutes.",
        "I can't stay signed in long enough to actually get anything done.",
        "Repeated forced logouts since this week. Used to be fine.",
        "It signed me out in the middle of checkout and I had to start over.",
    ],
    "pdf_export_blank": [
        "Export to PDF is broken, the file downloads but it's completely empty.",
        "Tried exporting my report as PDF three times, all blank pages.",
        "PDF export just gives me a 0-byte file every single time.",
        "When I export to PDF on Safari I get an empty document.",
        "The exported PDF has the header but the body is totally blank.",
        "Downloading a PDF produces a corrupted file that won't open.",
        "My charts don't render in the PDF export, just white space where they should be.",
        "PDF download finishes but Acrobat says the file is damaged.",
        "Exporting to PDF strips out all the content and leaves an empty page.",
        "Can't get a usable PDF, the export is blank no matter what I try.",
        "PDF comes out empty unless I wait and retry several times, very flaky.",
        "The 'Export PDF' button downloads nothing useful, file is 0 bytes.",
        "All my exported PDFs this week have been blank. Was working last month.",
        "PDF export drops images and tables, exports an empty shell.",
        "I need to send a PDF to a client but every export is blank. Urgent.",
        "Export works as CSV but PDF is always empty. Something's wrong with PDF.",
        "Blank PDF again. This is the third report I couldn't deliver on time.",
        "The PDF generator times out and returns an empty file.",
        "Exported PDF opens to a single blank page, none of my data is there.",
        "PDF export is unusable, just produces empty documents.",
        "Tried Chrome and Firefox, PDF export is blank in both.",
    ],
    "mobile_layout_broken": [
        "The mobile layout is unusable, buttons overlap on my phone.",
        "On my iPhone the navigation menu covers half the screen and I can't tap anything.",
        "Text is cut off on the right edge on mobile, can't read full sentences.",
        "Buttons are stacked on top of each other on a small screen.",
        "The mobile site doesn't scroll properly, content is stuck behind the header.",
        "On Android the form fields are squished together and overlap the labels.",
        "Can't use the app on my phone, the layout is completely broken.",
        "The bottom toolbar hides the submit button on mobile so I can't save.",
        "Everything is misaligned on mobile, looks like the CSS didn't load.",
        "Tapping a button on mobile triggers the one next to it because they overlap.",
        "The sidebar won't close on mobile and blocks the whole page.",
        "On a small screen the modal is bigger than the viewport and I can't close it.",
        "Mobile view zooms in weirdly and I have to pinch constantly to use it.",
        "Images break out of their container on mobile and push text off-screen.",
        "The responsive layout falls apart below tablet width.",
        "Menu items wrap into each other on my phone, totally unreadable.",
        "Can't complete signup on mobile because the button is off the bottom of the screen.",
        "Landscape mode on mobile is a mess, controls overlap the content.",
        "The mobile header overlaps the first row of my data table.",
        "Phone layout is broken after the latest update, was fine before.",
        "Dropdowns render off-screen on mobile so I can't pick an option.",
    ],
    "search_slow": [
        "Search is really slow, takes over 10 seconds to return anything on large projects.",
        "Searching my workspace times out constantly when I have a lot of items.",
        "The search bar lags so badly it's faster to scroll manually.",
        "Every search takes forever, sometimes it never returns at all.",
        "Search performance is terrible once a project gets big.",
        "Typing in search freezes the whole page for several seconds.",
        "Results take 15+ seconds to load, by then I've forgotten what I searched.",
        "Search is unusably slow in the afternoon, must be a load issue.",
        "Filtering a large list is painfully slow, the spinner just keeps going.",
        "Search query spins forever and then shows a timeout error.",
        "Global search is so laggy I've started using ctrl+F on the page instead.",
        "It takes 20 seconds to search across my projects. Way too slow.",
        "The autocomplete in search is delayed by several seconds per keystroke.",
        "Search got much slower after we crossed a few thousand records.",
        "Performance of search has degraded a lot this month.",
        "Searching returns results eventually but the wait kills my workflow.",
        "Big projects make search crawl, small ones are fine.",
        "The search index seems to choke on large datasets, super slow.",
        "I get frequent 504 timeouts when searching large workspaces.",
        "Search latency is unacceptable, 10-20 seconds every time.",
    ],
    "billing_double_charge": [
        "I was charged twice this month for the same subscription.",
        "My card got billed two times for one invoice, please refund the duplicate.",
        "There are two identical charges on my statement from you this week.",
        "Got double-charged after my payment failed and I retried.",
        "I see a duplicate charge for my annual plan, need that reversed.",
        "Billing charged me twice and support hasn't responded in days.",
        "Why is there a second charge on my account for the same amount?",
        "Upgraded my plan and got billed for both the old and new price.",
        "I cancelled but was still charged, and twice at that.",
        "Two payments came out of my account for a single renewal.",
        "Please refund the extra charge, I only have one subscription.",
        "My invoice shows one seat but I was billed for two.",
        "Double billing again this month, this is the second time it's happened.",
        "Got charged the monthly fee twice on the same day.",
        "There's an unexpected duplicate transaction from you on my credit card.",
        "Payment retried after a glitch and now I've paid twice.",
        "I need an urgent refund for a duplicate charge before my card maxes out.",
        "The renewal charged my card and my backup card both.",
        "Billed twice for the team plan, finance is asking me why.",
        "Duplicate charge on my account, the receipt emails both arrived a minute apart.",
    ],
    "signup_email_missing": [
        "The verification email never arrives so I can't finish signing up.",
        "I've requested the confirmation email five times and nothing comes through.",
        "Stuck on the 'verify your email' step, no email ever lands in my inbox.",
        "Sign-up is blocked because the activation email isn't being sent.",
        "The confirmation link email goes nowhere, checked spam too.",
        "Can't create an account, the verify-email step never emails me.",
        "No welcome or verification email after registering, account stuck unverified.",
        "Resent the verification email repeatedly, still nothing after an hour.",
        "The email with the confirmation code just doesn't show up.",
        "I signed up two days ago and still haven't gotten the verification email.",
        "Verification email finally arrived but the link says it already expired.",
        "Onboarding is dead in the water, no activation email at all.",
        "The confirm-your-email message isn't delivered to my work address.",
        "Tried three different email providers, none receive the verification mail.",
        "Account creation fails silently because the verify email never sends.",
        "Please manually verify me, the signup email system seems down.",
        "The 'resend email' button says sent but I never receive anything.",
        "Confirmation email landed 6 hours late, by then the token was invalid.",
        "Can't onboard my team, none of them get the invite verification emails.",
        "Signed up but no email, so I'm locked out of my own new account.",
    ],
    "_noise": [
        "Honestly love this product, it's made my week so much easier!",
        "Just wanted to say the new dashboard looks fantastic, great work team.",
        "Could you add a dark mode? Would be a nice touch.",
        "Is there a student discount available for the annual plan?",
        "Thanks for the quick reply yesterday, you all are awesome.",
        "When is the next webinar? I missed the last one.",
        "Can I integrate this with my calendar app somehow?",
        "Do you have an office in Europe? Just curious.",
        "asdkfj test test please ignore this message",
        "Unsubscribe me from the newsletter please.",
        "Great app, five stars, keep it up!",
        "What's the difference between the Pro and Team tiers?",
        "Loving the product so far, no complaints at all.",
        "Random question: who designed your logo? It's lovely.",
        "Can you ship me some stickers? Big fan here.",
        "Is the API rate limit documented anywhere public?",
        "Happy customer, just renewed for another year.",
        "Hello, testing whether support chat works. Hi!",
    ],
}

CHANNELS = ["support", "review", "chat", "email", "twitter"]
START = date(2026, 5, 1)


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for theme, pool in THEMES.items():
        for text in pool:
            rows.append({"text": text, "_theme": theme})
    random.shuffle(rows)
    out = []
    for i, r in enumerate(rows, start=1):
        out.append(
            {
                "id": str(i),
                "text": r["text"],
                "channel": random.choice(CHANNELS),
                "date": (START + timedelta(days=random.randint(0, 20))).isoformat(),
            }
        )
    return out


def main() -> None:
    rows = build_rows()
    path = Path(__file__).parent.parent / "data" / "sample_feedback.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "text", "channel", "date"])
        writer.writeheader()
        writer.writerows(rows)
    actionable = sum(len(v) for k, v in THEMES.items() if not k.startswith("_"))
    print(
        f"wrote {len(rows)} rows to {path} ({actionable} actionable across 6 themes, "
        f"{len(THEMES['_noise'])} noise)"
    )


if __name__ == "__main__":
    main()
