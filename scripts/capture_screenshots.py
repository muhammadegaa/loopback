# ruff: noqa: E501
"""Capture the Devpost image-gallery screenshots from the live URL.

Drives a real run through the live pipeline and stops at five moments:
  1. landing-batch-picker.png    — three-batch picker visible
  2. pipeline-running.png        — agent activity panel mid-run
  3. gate-cards.png              — gate with multiple lane treatments visible
  4. ask-the-agent.png           — chat surface open with a real Q&A
  5. done-hero.png               — done state hero + side-by-side lists

Viewport 1800x1200 (3:2 ratio, Devpost-friendly at 5MB max).
Run: .venv/bin/python scripts/capture_screenshots.py
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

URL = "https://loopback-182683404521.us-central1.run.app"
OUT = Path(__file__).parent.parent / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)


def poll_until(run_id: str, want: str, timeout: float = 180.0) -> dict:
    """Poll /api/runs/{id} until status matches, return last state."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = httpx.get(f"{URL}/api/runs/{run_id}", timeout=10.0)
        r.raise_for_status()
        last = r.json()
        if last["status"] == want:
            return last
        if last["status"] in ("error", "empty"):
            print(f"  pipeline ended: {last['status']} — {last.get('error')}")
            return last
        time.sleep(2.0)
    raise TimeoutError(f"timed out waiting for status={want}; last={last and last.get('status')}")


def snap(page: Page, name: str, label: str) -> None:
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    print(f"  saved {name}  ({label})")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1800, "height": 1200})
        page = ctx.new_page()

        # -------- 1. Landing with three-batch picker --------
        print("=> landing")
        page.goto(URL, wait_until="networkidle")
        # let cinematic chrome settle
        page.wait_for_selector("text=The agent that pauses before every GitLab write.", timeout=15000)
        page.wait_for_timeout(800)
        snap(page, "01-landing-batch-picker.png", "landing + three-batch picker")

        # -------- 2. Click Weekly batch, wait for pipeline mid-flight --------
        print("=> clicking Weekly batch")
        page.click("text=Weekly batch")
        # Read run_id from the URL once it lands
        page.wait_for_function("window.location.search.includes('run=')", timeout=15000)
        run_id = page.evaluate("new URLSearchParams(window.location.search).get('run')")
        print(f"  run_id={run_id}")

        # mid-pipeline screenshot at ~25s — agent activity panel is filling
        page.wait_for_timeout(25_000)
        # ensure NowThinking ribbon is visible
        page.evaluate("window.scrollTo(0, 0)")
        snap(page, "02-pipeline-running.png", "agent activity panel mid-run")

        # -------- 3. Wait for the gate, capture cards --------
        print("=> waiting for gate")
        poll_until(run_id, "awaiting_approval", timeout=180.0)
        # let the UI settle (cards animate in)
        page.wait_for_selector("text=Paused for your approval", timeout=20000)
        page.wait_for_timeout(2500)
        page.evaluate("window.scrollTo(0, 0)")
        snap(page, "03-gate-cards.png", "gate with cards + dock")

        # -------- 4. Click Ask the agent on the regression card --------
        print("=> opening Ask the agent on regression card")
        # find a regression-flagged card by its red band text
        try:
            # the band reads exactly: "Flagged as possible regression of #{N}"
            band = page.locator("text=/Flagged as possible regression/i").first
            band.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            # find the Ask button INSIDE the same article
            article = band.locator("xpath=ancestor::article[1]")
            ask_btn = article.locator("button:has-text('Ask the agent')").first
            ask_btn.click()
        except Exception as e:
            print(f"  fallback: no regression card found ({e}); clicking first available Ask button")
            page.locator("button:has-text('Ask the agent')").first.click()

        page.wait_for_timeout(600)
        # type the question
        ask_input = page.locator("input[placeholder*='Ask the agent']").first
        ask_input.fill("why isn't this a new ticket?")
        # press Enter to send
        ask_input.press("Enter")
        # wait for the agent's reply to land (look for 'Loopback agent' label or absence of Thinking)
        try:
            page.wait_for_selector("text=/Loopback agent/i", timeout=30000)
            # give it a beat for the bubble to fully render
            page.wait_for_timeout(2500)
        except Exception:
            print("  warning: agent reply may not have landed in time")
            page.wait_for_timeout(5000)

        # scroll so chat is centered
        ask_input.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        snap(page, "04-ask-the-agent.png", "chat open with grounded Q&A")

        # -------- 5. Approve, wait for done, capture hero --------
        print("=> approving")
        approve_btn = page.locator("button:has-text('create in GitLab')").first
        approve_btn.scroll_into_view_if_needed()
        approve_btn.click()

        poll_until(run_id, "done", timeout=200.0)
        page.wait_for_selector("text=Run complete", timeout=20000)
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 0)")
        snap(page, "05-done-hero.png", "done state hero + lists")

        browser.close()

    print(f"\nDone. Screenshots in {OUT}")
    for f in sorted(OUT.glob("*.png")):
        size = f.stat().st_size
        print(f"  {f.name}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
