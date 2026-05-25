"""End-to-end demo + verification of the full Loopback loop (Day 7-9).

Drives the agent against the GitLab trial project, lets it PAUSE at the human
approval gate, supplies a decision (approve most, reject the lowest-ranked draft),
resumes, and confirms: the agent genuinely paused, approved drafts became real
GitLab issues with labels, and rejected drafts created nothing. Prints the full
step log throughout.

    .venv/bin/python scripts/demo_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


_load_dotenv()

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions.in_memory_session_service import InMemorySessionService  # noqa: E402
from google.adk.tools.tool_confirmation import ToolConfirmation  # noqa: E402
from google.genai import types  # noqa: E402

APP_NAME, USER_ID, SESSION_ID = "loopback", "demo-user", "demo-session"
SAMPLE = str(ROOT / "data" / "sample_feedback.csv")


def _print_event(event) -> object | None:
    """Print an event's text + tool activity; return a paused confirmation call if present."""
    confirmation_fc = None
    for part in event.content.parts if event.content else []:
        if part.text and part.text.strip():
            print(f"  [{event.author}] {part.text.strip()}")
        if part.function_call:
            fc = part.function_call
            if (
                fc.id in (event.long_running_tool_ids or [])
                and fc.name == "adk_request_confirmation"
            ):
                confirmation_fc = fc
            elif fc.name != "adk_request_confirmation":
                print(f"  [{event.author}] → tool_call {fc.name}({dict(fc.args or {})})")
        if part.function_response and part.function_response.name != "adk_request_confirmation":
            print(f"  [{event.author}] ← {part.function_response.name} returned")
    return confirmation_fc


def _check(cond: bool, msg: str, failures: list[str]) -> None:
    print(f"  [{'ok ' if cond else 'FAIL'}] {msg}")
    if not cond:
        failures.append(msg)


async def main() -> int:
    import agent.agent as A

    project = os.environ.get("GITLAB_PROJECT_ID") or os.environ.get("GITLAB_PROJECT_PATH")
    token_available = (
        os.environ.get("GITLAB_OAUTH_BEARER")
        or os.environ.get("GITLAB_OAUTH_TOKEN_JSON")
        or (ROOT / ".oauth_token.json").exists()
    )
    if not (token_available and project):
        print(
            "SKIPPED — run scripts/oauth_spike.py for an OAuth token and set "
            "GITLAB_PROJECT_ID in .env to run the live demo."
        )
        return 2

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state={"source": SAMPLE, "project_id": str(project)},
    )
    runner = Runner(app=A.build_app(), session_service=session_service)

    print("\n===== RUN 1: ingest -> cluster -> search -> draft -> PAUSE =====")
    confirmation_fc = None
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="Run the Loopback pipeline on the customer feedback.")],
        ),
    ):
        fc = _print_event(event)
        if fc:
            confirmation_fc = fc

    failures: list[str] = []
    _check(confirmation_fc is not None, "agent PAUSED at the approval gate", failures)
    if confirmation_fc is None:
        print("\nFAIL — agent never paused; aborting.")
        return 1

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    drafts = session.state.get("drafts", [])
    ids = [d["theme_id"] for d in drafts]
    rejected = ids[-1:]  # reject the lowest-ranked draft
    approved = [i for i in ids if i not in rejected]

    print(f"\n⏸  PAUSED. {len(drafts)} drafts awaiting review; nothing created in GitLab yet.")
    _check(not session.state.get("created"), "no GitLab issues created before approval", failures)
    print(f"   drafts: {ids}")
    print(f"   DECISION → approve {approved} | reject {rejected}")

    decision = ToolConfirmation(
        confirmed=True, payload={"approved_ids": approved, "rejected_ids": rejected}
    )
    resume = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=confirmation_fc.id,
                    name="adk_request_confirmation",
                    response=decision.model_dump(by_alias=True, exclude_none=True),
                )
            )
        ],
    )

    print("\n===== RUN 2: RESUME -> create approved issues in GitLab =====")
    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=resume):
        _print_event(event)

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    created = session.state.get("created", [])
    created_themes = {c["theme_id"] for c in created}

    print("\n===== VERIFICATION =====")
    _check(
        len(created) == len(approved),
        f"created count == approved ({len(created)}/{len(approved)})",
        failures,
    )
    _check(
        all(r not in created_themes for r in rejected),
        f"rejected {rejected} created nothing",
        failures,
    )
    _check(
        bool(created) and all(c["labels"] for c in created),
        "every created issue has labels applied",
        failures,
    )

    print("\nCreated GitLab issues:")
    for c in created:
        print(f"  #{c['iid']}  labels={c['labels']}  {c['url']}")

    print("\n" + ("PASS — full loop green." if not failures else f"FAIL — {failures}"))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
