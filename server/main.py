"""Loopback API (Cloud Run) — a thin HTTP layer over the ADK agent.

All GitLab and Gemini credentials live here, server-side; the web UI calls this API
only. The human approval pause is REAL: a run executes the actual ADK agent, which
pauses at `request_confirmation`; the run is held server-side until the UI posts a
decision, then resumed. The agent runs in a worker thread so its blocking Gemini/MCP
calls never freeze the event loop — the UI can poll a live step log throughout.

Endpoints:
    POST /api/runs                 multipart CSV upload -> {run_id}
    GET  /api/runs/{run_id}        run snapshot: status, steps, drafts, created, ...
    POST /api/runs/{run_id}/decision   {approved_ids, rejected_ids} -> resumes the run
    GET  /api/health
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import threading
import time
import uuid
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

from fastapi import FastAPI, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions.in_memory_session_service import InMemorySessionService  # noqa: E402
from google.adk.tools.tool_confirmation import ToolConfirmation  # noqa: E402
from google.genai import types  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import agent.agent as agent_mod  # noqa: E402
from tools.ingest import IngestError, load_signals  # noqa: E402

PROJECT = os.environ.get("GITLAB_PROJECT_ID") or os.environ.get("GITLAB_PROJECT_PATH")
log = logging.getLogger("loopback")

app = FastAPI(title="Loopback API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev: the API holds no secrets the browser can read
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, dict] = {}
PUBLIC_KEYS = (
    "status", "preview", "triage", "redaction", "steps", "drafts", "created",
    "approved", "rejected", "edited_ids", "timings", "error",
)


def _new_state() -> dict:
    return {
        "status": "running",  # running | awaiting_approval | creating | done | empty | error
        "preview": {"total": 0, "sample": []},  # parsed signals shown for transparency
        # triage totals from clustering: how many signals became themes vs were ignored as noise
        "triage": {
            "total": 0, "themed": 0, "ignored": 0, "themes": 0,
            "filtered_by_learning": 0, "filtered_signals": 0,
        },
        # PII redaction counts surfaced for the trust strip
        "redaction": {"email": 0, "phone": 0, "url": 0, "signals_touched": 0},
        "steps": [],
        "drafts": [],
        "created": [],
        "approved": [],
        "rejected": [],
        # theme_ids the human edited at the gate — feeds the decision log
        "edited_ids": [],
        # timestamps powering the "saved you Xh of triage" framing on the done state
        "timings": {"started_at": None, "gate_at": None, "decided_at": None, "done_at": None},
        "error": None,
        "_decision": None,
        "_decision_ready": threading.Event(),
    }


def _step(state: dict, author: str, text: str) -> None:
    state["steps"].append({"author": author, "text": text, "ts": time.time()})


def _ingest_events(event, state: dict):
    """Record an event's text + tool activity into the step log; return a paused
    confirmation function call if this event is the approval pause. Also surfaces
    deterministic state deltas (triage totals) so the UI animates them live — without
    waiting for the gate."""
    confirmation_fc = None
    for part in event.content.parts if event.content else []:
        if part.text and part.text.strip():
            _step(state, event.author, part.text.strip())
        if part.function_call:
            fc = part.function_call
            paused = fc.id in (event.long_running_tool_ids or [])
            if paused and fc.name == "adk_request_confirmation":
                confirmation_fc = fc
            elif fc.name != "adk_request_confirmation":
                _step(state, event.author, f"calling tool: {fc.name}")
    delta = getattr(event.actions, "state_delta", None) if event.actions else None
    if isinstance(delta, dict) and "triage" in delta:
        state["triage"] = delta["triage"]
    return confirmation_fc


PRE_GATE_TIMEOUT = 300  # ingest + cluster + search + draft
CREATE_TIMEOUT = 300  # create approved issues in GitLab


async def _pipeline(run_id: str, source: str, source_label: str) -> None:
    state = RUNS[run_id]
    sessions = InMemorySessionService()
    try:
        await sessions.create_session(
            app_name="loopback",
            user_id="web",
            session_id=run_id,
            state={"source": source, "source_label": source_label, "project_id": str(PROJECT)},
        )
        runner = Runner(app=agent_mod.build_app(), session_service=sessions)

        async def _until_pause():
            fc = None
            async for event in runner.run_async(
                user_id="web",
                session_id=run_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text="Run the Loopback pipeline on the feedback.")],
                ),
            ):
                got = _ingest_events(event, state)
                if got:
                    fc = got
            return fc

        confirmation_fc = await asyncio.wait_for(_until_pause(), timeout=PRE_GATE_TIMEOUT)

        session = await sessions.get_session(app_name="loopback", user_id="web", session_id=run_id)
        state["drafts"] = session.state.get("drafts", [])
        state["triage"] = session.state.get("triage", state["triage"])
        if not state["drafts"] or confirmation_fc is None:
            state["status"] = "empty"
            state["timings"]["done_at"] = time.time()
            return

        # --- REAL PAUSE: hold here until the human posts a decision (no timeout) ---
        state["status"] = "awaiting_approval"
        state["timings"]["gate_at"] = time.time()
        while not state["_decision_ready"].is_set():
            await asyncio.sleep(0.2)
        approved, rejected, edits, file_new = state["_decision"]
        state["approved"], state["rejected"] = approved, rejected
        state["edited_ids"] = sorted(edits.keys()) if isinstance(edits, dict) else []
        state["status"] = "creating"

        decision = ToolConfirmation(
            confirmed=bool(approved),
            payload={
                "approved_ids": approved,
                "rejected_ids": rejected,
                "edits": edits,
                "file_new_instead_of_extend": file_new,
            },
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

        async def _create():
            async for event in runner.run_async(
                user_id="web", session_id=run_id, new_message=resume
            ):
                _ingest_events(event, state)

        await asyncio.wait_for(_create(), timeout=CREATE_TIMEOUT)

        session = await sessions.get_session(app_name="loopback", user_id="web", session_id=run_id)
        state["created"] = session.state.get("created", [])
        state["status"] = "done"
        state["timings"]["done_at"] = time.time()
    except IngestError:
        log.exception("run %s: ingest failed", run_id)
        state["status"], state["error"] = (
            "error",
            "That file couldn't be read as customer feedback. Make sure it's a CSV with "
            "id, text, channel, and date columns.",
        )
    except TimeoutError:
        log.exception("run %s: timed out", run_id)
        state["status"], state["error"] = (
            "error",
            "The run took too long and was stopped. Try a smaller batch of feedback.",
        )
    except Exception:
        # Full detail goes to server logs; the user sees a clean, non-leaky message.
        log.exception("run %s: agent failure", run_id)
        state["status"], state["error"] = (
            "error",
            "The agent hit a problem processing this batch. Please try again.",
        )


def _run_thread(run_id: str, source: str, source_label: str) -> None:
    asyncio.run(_pipeline(run_id, source, source_label))


class Decision(BaseModel):
    approved_ids: list[str]
    rejected_ids: list[str]
    # human edits keyed by theme_id: {title, body, priority, suggested_labels}
    edits: dict = {}
    # theme_ids the human wants to file as a new issue even though the classifier
    # routed them to extend_existing. Empty for the common case.
    file_new_instead_of_extend: list[str] = []


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "project": PROJECT}


@app.post("/api/runs")
async def create_run(file: UploadFile) -> dict:
    content = (await file.read()).decode("utf-8", "replace")
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    tmp.write(content)
    tmp.close()
    label = file.filename or "uploaded.csv"
    try:
        out = load_signals(tmp.name)  # validate upfront so bad CSVs fail fast and friendly
    except IngestError as e:
        msg = str(e).replace(tmp.name, "the uploaded file")
        raise HTTPException(status_code=400, detail=msg) from e

    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = _new_state()
    sigs = out["signals"]
    RUNS[run_id]["preview"] = {
        "total": len(sigs),
        "sample": [
            {
                "id": str(s.get("id", "")),
                "text": s.get("text", ""),
                "channel": s.get("channel", ""),
                "date": s.get("date", ""),
            }
            for s in sigs[:12]
        ],
    }
    RUNS[run_id]["redaction"] = out.get("redaction") or RUNS[run_id]["redaction"]
    RUNS[run_id]["timings"]["started_at"] = time.time()
    threading.Thread(target=_run_thread, args=(run_id, tmp.name, label), daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    state = RUNS.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="run not found")
    return {k: state[k] for k in PUBLIC_KEYS}


@app.post("/api/runs/{run_id}/decision")
def decide(run_id: str, body: Decision) -> dict:
    state = RUNS.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="run not found")
    if state["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="run is not awaiting approval")
    state["_decision"] = (
        body.approved_ids,
        body.rejected_ids,
        body.edits,
        body.file_new_instead_of_extend,
    )
    state["timings"]["decided_at"] = time.time()
    state["_decision_ready"].set()
    return {"ok": True}


@app.post("/api/admin/clear-learning")
def clear_learning() -> dict:
    """Delete the per-source rejection memory so the next run sees a fresh slate.
    Used between rehearsal sessions — a no-op if there's nothing to clear."""
    import shutil

    store = Path(os.environ.get("LOOPBACK_LEARNING_DIR", "/tmp/loopback-learning"))
    removed = 0
    if store.exists():
        for f in store.glob("rejections-*.json"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        shutil.rmtree(store, ignore_errors=True)
    return {"ok": True, "removed_files": removed}


# Serve the built UI (web/out) same-origin so there is ONE public URL. Mounted last
# so the /api/* routes above take precedence. Absent in local dev (UI on its own port).
_WEB_DIR = ROOT / "web" / "out"
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="ui")
