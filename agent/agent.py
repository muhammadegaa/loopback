"""Loopback agent (Day 7-9) — the full loop on Google ADK + Gemini.

    ingest → cluster_and_rank → search_existing → draft_issues
           → ⏸ HUMAN APPROVAL GATE → create_in_gitlab

Step order is guaranteed by a SequentialAgent. The four data steps are custom
deterministic BaseAgents that pass data through session state (so the 142 signals,
themes, and drafts never round-trip through the LLM as tool args). The approval gate
is an LlmAgent whose tool calls `tool_context.request_confirmation()` — the agent
PAUSES there and creates nothing in GitLab until a human approves/rejects. Creation
is a deterministic step that strictly honors the approved ids.

Every step yields a visible log Event so the agent's reasoning and tool calls show up
in the demo and the UI step log.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from tools.clustering import cluster_and_rank
from tools.drafting import draft_issues
from tools.gitlab_mcp import GitLabMCP
from tools.ingest import load_signals

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _log(agent: BaseAgent, ctx: InvocationContext, text: str, **state_delta) -> Event:
    """Build a visible step-log Event, optionally carrying a session state delta."""
    return Event(
        author=agent.name,
        invocation_id=ctx.invocation_id,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        actions=EventActions(state_delta=dict(state_delta)) if state_delta else EventActions(),
    )


# --- data steps (deterministic; no LLM, data via session state) ----------


class _Ingest(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        source = ctx.session.state.get("source")
        label = ctx.session.state.get("source_label") or source
        out = load_signals(source)
        sigs = out["signals"]
        yield _log(
            self,
            ctx,
            f"ingest: loaded {len(sigs)} signals from {label} (dropped {out['dropped']} empty).",
            signals=sigs,
        )


class _Cluster(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        themes = cluster_and_rank(ctx.session.state.get("signals", []))["themes"]
        summary = " | ".join(f"{t['label']} (score {t['score']})" for t in themes)
        yield _log(
            self,
            ctx,
            f"cluster_and_rank: {len(themes)} themes ranked by frequency x severity — {summary}",
            themes=themes,
        )


class _SearchExisting(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        themes = ctx.session.state.get("themes", [])
        project = ctx.session.state.get("project_id")
        related: dict[str, list] = {}
        with GitLabMCP() as gl:
            for t in themes:
                try:
                    hits = gl.find_issues(project, t["label"])
                    lst = hits if isinstance(hits, list) else []
                except Exception as e:  # noqa: BLE001 - search is best-effort, never block the loop
                    lst, _ = [], e
                rel = [
                    {"iid": h.get("iid"), "id": h.get("id"), "title": h.get("title")}
                    for h in lst[:3]
                    if isinstance(h, dict) and h.get("iid")
                ]
                related[t["id"]] = rel
                yield _log(
                    self,
                    ctx,
                    f"search_existing: '{t['label']}' -> {len(rel)} related issue(s).",
                )
        yield _log(self, ctx, "search_existing: complete.", related=related)


class _Draft(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        themes = ctx.session.state.get("themes", [])
        related = ctx.session.state.get("related", {})
        drafts = draft_issues(themes, related)["drafts"]
        titles = "; ".join(d["title"] for d in drafts)
        yield _log(
            self, ctx, f"draft_issues: drafted {len(drafts)} issue(s) — {titles}", drafts=drafts
        )


# =========================================================================
#   THE HUMAN APPROVAL GATE — the single most important design point.
#   The agent PAUSES here via tool_context.request_confirmation() and creates
#   NOTHING in GitLab until a human returns an explicit approve/reject decision.
# =========================================================================
def request_approval(tool_context: ToolContext) -> dict:
    """Pause the run for human review of the drafted issues. Creates NOTHING in GitLab.

    inputs: none — reads the drafted issues from session state.
    outputs:
      - first invocation: calls request_confirmation() (which PAUSES the agent) and
        returns a PENDING status; the drafts are surfaced in the confirmation payload
        so the human / UI can review them.
      - on resume: reads the human's ToolConfirmation, records approved_ids and
        rejected_ids in session state, and returns the decision summary.
    side effects: pauses the invocation; writes approved_ids / rejected_ids to state.
    """
    drafts = tool_context.state.get("drafts", [])
    confirmation = tool_context.tool_confirmation

    if confirmation is None:
        # FIRST PASS → ask the human. The run pauses once this returns.
        tool_context.request_confirmation(
            hint=(
                "Review the drafted GitLab issues. Approve or reject each by replying with a "
                "ToolConfirmation whose payload is {'approved_ids': [...], 'rejected_ids': [...]} "
                "of draft theme_ids. Set confirmed=false to reject everything."
            ),
            payload={
                "drafts": [
                    {
                        "theme_id": d["theme_id"],
                        "title": d["title"],
                        "priority": d["priority"],
                        "suggested_labels": d["suggested_labels"],
                    }
                    for d in drafts
                ]
            },
        )
        return {"status": "PENDING_HUMAN_APPROVAL", "awaiting_review": len(drafts)}

    # RESUME → apply the human's decision.
    payload = confirmation.payload or {}
    all_ids = [d["theme_id"] for d in drafts]
    if not confirmation.confirmed:
        approved, rejected = [], list(all_ids)
    else:
        approved = list(payload.get("approved_ids", all_ids))
        rejected = list(payload.get("rejected_ids", [i for i in all_ids if i not in approved]))
    approved = [i for i in approved if i not in rejected]  # rejection wins ties

    # Apply the human's edits so creation files THEIR version, not the model's draft.
    # The human co-authors the ticket: title, body, priority, labels are theirs to change.
    edits = payload.get("edits") or {}
    if edits:
        merged = []
        for d in drafts:
            e = edits.get(d["theme_id"])
            if isinstance(e, dict):
                d = dict(d)
                for key in ("title", "body", "priority"):
                    val = e.get(key)
                    if isinstance(val, str) and val.strip():
                        d[key] = val.strip()
                labels = e.get("suggested_labels")
                if isinstance(labels, list):
                    d["suggested_labels"] = [str(x) for x in labels if str(x).strip()]
            merged.append(d)
        tool_context.state["drafts"] = merged

    tool_context.state["approved_ids"] = approved
    tool_context.state["rejected_ids"] = rejected
    return {"status": "decided", "approved": approved, "rejected": rejected}


approval_gate_agent = LlmAgent(
    name="approval_gate",
    model=GEMINI_MODEL,
    instruction=(
        "You are the human approval gate for GitLab issue creation. Call the "
        "`request_approval` tool exactly once — it pauses for a human decision. When the "
        "decision returns, state in one sentence which drafts were approved and which were "
        "rejected. You must NOT create anything in GitLab; that is a later step."
    ),
    tools=[request_approval],
)


# --- creation step (deterministic; strictly honors approved_ids) ---------


class _CreateInGitLab(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        drafts = ctx.session.state.get("drafts", [])
        approved = set(ctx.session.state.get("approved_ids", []))
        rejected = ctx.session.state.get("rejected_ids", [])
        project = ctx.session.state.get("project_id")
        related = ctx.session.state.get("related", {})
        to_create = [d for d in drafts if d["theme_id"] in approved]

        yield _log(
            self,
            ctx,
            f"create_in_gitlab: {len(to_create)} approved; skipping {len(rejected)} rejected.",
        )
        created: list[dict] = []
        with GitLabMCP() as gl:
            for d in to_create:
                labels = d.get("suggested_labels", [])
                try:
                    # Official server: labels are applied AND auto-created at creation.
                    issue = gl.create_issue(project, d["title"], d.get("body", ""), labels=labels)
                    iid, url = issue.get("iid"), issue.get("web_url")
                    yield _log(
                        self,
                        ctx,
                        f"   create_issue #{iid} (labels {labels} applied): {d['title']} -> {url}",
                    )
                    rel_ids = [r["id"] for r in related.get(d["theme_id"], []) if r.get("id")]
                    if rel_ids:
                        gl.relate(project, iid, rel_ids)
                        yield _log(
                            self,
                            ctx,
                            f"   link_work_items: related #{iid} to {len(rel_ids)} existing",
                        )
                    verified = gl.get_issue(project, iid)
                    created.append(
                        {
                            "theme_id": d["theme_id"],
                            "iid": iid,
                            "url": url,
                            "labels": verified.get("labels", []),
                        }
                    )
                    yield _log(self, ctx, f"   get_issue #{iid}: labels {verified.get('labels')}")
                except Exception:  # noqa: BLE001 - one draft failing must not abort the batch
                    yield _log(self, ctx, f"   ! create failed for {d['theme_id']!r}; skipped.")
                    continue
        yield _log(
            self, ctx, f"create_in_gitlab: created {len(created)} issue(s).", created=created
        )


root_agent = SequentialAgent(
    name="loopback",
    sub_agents=[
        _Ingest(name="ingest"),
        _Cluster(name="cluster"),
        _SearchExisting(name="search_existing"),
        _Draft(name="draft"),
        approval_gate_agent,
        _CreateInGitLab(name="create_in_gitlab"),
    ],
)


def build_app() -> App:
    """Wrap the pipeline in a resumable App — required for the HITL pause/resume."""
    return App(
        name="loopback",
        root_agent=root_agent,
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
