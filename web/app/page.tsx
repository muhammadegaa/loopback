"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createRun,
  getRun,
  postDecision,
  type Created,
  type Draft,
  type DraftEdit,
  type Redaction,
  type RunState,
  type Step,
  type Timings,
  type Triage,
} from "@/lib/api";

const TERMINAL = new Set(["done", "empty", "error"]);

// per-field flags the IssueCard uses to mark co-authored input
type EditedFields = { title: boolean; body: boolean; priority: boolean; labels: boolean };
const NO_EDITS: EditedFields = { title: false, body: false, priority: false, labels: false };

export default function Home() {
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // rejected theme_ids chosen by the human at the gate (default: everything approved)
  const [rejected, setRejected] = useState<Set<string>>(new Set());
  // the human's edits to each draft, keyed by theme_id (title/body/priority/labels)
  const [edits, setEdits] = useState<Record<string, DraftEdit>>({});
  const [submitting, setSubmitting] = useState(false);
  // per-card "show details" override; undefined means "use the default for this index"
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  // theme_ids the human chose to file as a new issue even though the classifier
  // routed them to extend_existing. Empty for the common case.
  const [extendOverrides, setExtendOverrides] = useState<Set<string>>(new Set());

  const toggleExtendOverride = (themeId: string) =>
    setExtendOverrides((prev) => {
      const next = new Set(prev);
      if (next.has(themeId)) next.delete(themeId);
      else next.add(themeId);
      return next;
    });

  const onEdit = (themeId: string, patch: DraftEdit) =>
    setEdits((prev) => ({ ...prev, [themeId]: { ...prev[themeId], ...patch } }));

  const toggleExpanded = (themeId: string, defaultOpen: boolean) =>
    setExpanded((prev) => ({ ...prev, [themeId]: !(prev[themeId] ?? defaultOpen) }));

  const expandAll = (open: boolean) => {
    if (!run) return;
    setExpanded(Object.fromEntries(run.drafts.map((d) => [d.theme_id, open])));
  };

  // detect which fields the human touched so the card can flag them as co-authored
  const editedFields = useMemo<Record<string, EditedFields>>(() => {
    if (!run) return {};
    const out: Record<string, EditedFields> = {};
    for (const d of run.drafts) {
      const e = edits[d.theme_id] || {};
      out[d.theme_id] = {
        title: typeof e.title === "string" && e.title.trim() !== d.title.trim(),
        body: typeof e.body === "string" && e.body.trim() !== d.body.trim(),
        priority: typeof e.priority === "string" && e.priority !== d.priority,
        labels:
          Array.isArray(e.suggested_labels) &&
          JSON.stringify(e.suggested_labels) !== JSON.stringify(d.suggested_labels),
      };
    }
    return out;
  }, [run, edits]);

  // resumable across refresh — the runId lives in ?run=<id> so a panel refresh
  // during the pause picks the same in-memory run state back up on the server.
  useEffect(() => {
    if (runId) return;
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const persisted = url.searchParams.get("run");
    if (!persisted) return;
    (async () => {
      try {
        const state = await getRun(persisted);
        setRunId(persisted);
        setRun(state);
      } catch {
        // unknown run id (e.g. server restarted) — drop the param so the upload screen shows
        url.searchParams.delete("run");
        window.history.replaceState({}, "", url.toString());
      }
    })();
  }, [runId]);

  // poll the run while it is live
  useEffect(() => {
    if (!runId) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const state = await getRun(runId);
        if (!alive) return;
        setRun(state);
        if (TERMINAL.has(state.status) || state.status === "awaiting_approval") return;
      } catch {
        /* transient; keep polling */
      }
      if (alive) timer = setTimeout(tick, 1000);
    };
    timer = setTimeout(tick, 400);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [runId]);

  // resume polling after the human submits a decision (status flips to "creating")
  const resumePolling = useCallback(() => {
    if (!runId) return;
    let alive = true;
    const tick = async () => {
      const state = await getRun(runId);
      if (!alive) return;
      setRun(state);
      if (!TERMINAL.has(state.status)) setTimeout(tick, 1000);
    };
    setTimeout(tick, 400);
    return () => {
      alive = false;
    };
  }, [runId]);

  const onFile = async (file: File | null) => {
    if (!file) return;
    setUploadError(null);
    setBusy(true);
    try {
      const id = await createRun(file);
      setRunId(id);
      // persist runId in the URL so a mid-pause refresh resumes the same run
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        url.searchParams.set("run", id);
        window.history.replaceState({}, "", url.toString());
      }
      setRun({
        status: "running",
        preview: { total: 0, sample: [] },
        triage: { total: 0, themed: 0, ignored: 0, themes: 0 },
        redaction: { email: 0, phone: 0, url: 0, signals_touched: 0 },
        steps: [],
        drafts: [],
        created: [],
        approved: [],
        rejected: [],
        edited_ids: [],
        timings: { started_at: null, gate_at: null, decided_at: null, done_at: null },
        error: null,
      });
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const submitDecision = useCallback(async () => {
    if (!runId || !run) return;
    setSubmitting(true);
    const approved = run.drafts.map((d) => d.theme_id).filter((id) => !rejected.has(id));
    // only include overrides for drafts the classifier actually routed to extend
    const fileNew = run.drafts
      .filter((d) => d.lane === "extend_existing" && extendOverrides.has(d.theme_id))
      .map((d) => d.theme_id);
    try {
      await postDecision(runId, approved, [...rejected], edits, fileNew);
      setRun({ ...run, status: "creating" });
      resumePolling();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Couldn't submit.");
    } finally {
      setSubmitting(false);
    }
  }, [runId, run, rejected, edits, extendOverrides, resumePolling]);

  // ⌘↵ (or Ctrl+↵) at the gate submits — the keyboard shortcut a power user reaches for.
  useEffect(() => {
    if (run?.status !== "awaiting_approval") return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !submitting) {
        e.preventDefault();
        void submitDecision();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [run?.status, submitting, submitDecision]);

  const reset = () => {
    setRunId(null);
    setRun(null);
    setRejected(new Set());
    setEdits({});
    setExpanded({});
    setExtendOverrides(new Set());
    setUploadError(null);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("run");
      window.history.replaceState({}, "", url.toString());
    }
  };

  const status = run?.status;
  const showReview = status === "awaiting_approval" || status === "running" || status === "creating";

  return (
    <div className="flex min-h-full flex-col">
      <Header status={status} onReset={runId ? reset : undefined} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 pb-24 pt-8">
        {!runId && <Upload onFile={onFile} busy={busy} error={uploadError} />}

        {runId && showReview && <Stepper status={status} />}

        {runId && status === "error" && (
          <Banner kind="error" title="The run hit a problem" body={run?.error ?? "Unknown error."} onReset={reset} />
        )}
        {runId && status === "empty" && (
          <Banner
            kind="empty"
            title="No recurring themes found"
            body="The feedback didn't contain enough repeated, actionable pain to cluster into issues. Try a larger or noisier batch."
            onReset={reset}
          />
        )}

        {runId && showReview && run && (
          <Review
            run={run}
            rejected={rejected}
            setRejected={setRejected}
            edits={edits}
            onEdit={onEdit}
            editedFields={editedFields}
            expanded={expanded}
            toggleExpanded={toggleExpanded}
            expandAll={expandAll}
            extendOverrides={extendOverrides}
            toggleExtendOverride={toggleExtendOverride}
            submitting={submitting}
            onSubmit={submitDecision}
          />
        )}

        {runId && status === "done" && run && <Result run={run} onReset={reset} />}
      </main>
    </div>
  );
}

/* ===================================================================== shell */

function Header({ status, onReset }: { status?: string; onReset?: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-3">
        <div className="flex items-center gap-2.5">
          <LoopMark />
          <div className="leading-none">
            <div className="text-[15px] font-semibold tracking-tight text-ink">Loopback</div>
            <div className="mt-1 text-[11px] text-muted">Voice-of-Customer → GitLab</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {status && <StatusPill status={status} />}
          {onReset && (
            <button
              onClick={onReset}
              className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted shadow-card transition hover:border-border-strong hover:text-ink"
            >
              New run
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

function LoopMark() {
  return (
    <div className="grid h-8 w-8 place-items-center rounded-lg bg-ink">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#f6b73c" strokeWidth="2.1" strokeLinecap="round">
        <path d="M4 9a5 5 0 0 1 5-5h6a5 5 0 0 1 0 10H7" />
        <path d="M9 16l-3 3 3 3" transform="translate(0 -6)" />
      </svg>
    </div>
  );
}

const STATUS_MAP: Record<string, { label: string; cls: string; dot: string; pulse?: boolean }> = {
  running: { label: "Analyzing", cls: "border-primary/30 bg-primary-bg text-primary", dot: "bg-primary", pulse: true },
  awaiting_approval: { label: "Awaiting you", cls: "border-amber-border bg-amber-bg text-amber", dot: "bg-amber", pulse: true },
  creating: { label: "Creating issues", cls: "border-primary/30 bg-primary-bg text-primary", dot: "bg-primary", pulse: true },
  done: { label: "Done", cls: "border-green-border bg-green-bg text-green", dot: "bg-green" },
  empty: { label: "No themes", cls: "border-border bg-subtle text-muted", dot: "bg-faint" },
  error: { label: "Error", cls: "border-red-border bg-red-bg text-red", dot: "bg-red" },
};

function StatusPill({ status }: { status: string }) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.running;
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${s.pulse ? "blink" : ""}`} />
      {s.label}
    </span>
  );
}

/* ================================================================== stepper */

const STAGES = ["Analyze feedback", "Your approval", "Create in GitLab"];

function Stepper({ status }: { status?: string }) {
  const active = status === "awaiting_approval" ? 1 : status === "creating" ? 2 : status === "done" ? 3 : 0;
  return (
    <ol className="risein mb-6 flex items-center gap-1.5 rounded-xl border border-border bg-surface px-4 py-3 shadow-card sm:gap-3">
      {STAGES.map((label, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <li key={label} className="flex flex-1 items-center gap-2.5">
            <span
              className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[11px] font-semibold transition ${
                done
                  ? "border-green bg-green text-white"
                  : current
                    ? "border-primary bg-primary text-white"
                    : "border-border-strong bg-surface text-faint"
              }`}
            >
              {done ? "✓" : i + 1}
            </span>
            <span className={`hidden text-[13px] font-medium sm:inline ${current ? "text-ink" : done ? "text-muted" : "text-faint"}`}>
              {label}
            </span>
            {i < STAGES.length - 1 && (
              <span className={`mx-1 h-px flex-1 ${done ? "bg-green/40" : "bg-border"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/* =================================================================== upload */

// Three sample batches, each scripted for a different demo beat. The agent's
// decision spread should look visibly different across them — same agent,
// different inputs (and, ideally, different GitLab project state).
const SAMPLES: { file: string; label: string; size: string; desc: string }[] = [
  { file: "first-week.csv",     label: "First week",     size: "75 signals",  desc: "Calm batch — mostly new tickets" },
  { file: "weekly-batch.csv",   label: "Weekly batch",   size: "298 signals", desc: "Mixed lanes — the messy week" },
  { file: "post-incident.csv",  label: "Post-incident",  size: "100 signals", desc: "Model regressed after a ship" },
];

function Upload({ onFile, busy, error }: { onFile: (f: File | null) => void; busy: boolean; error: string | null }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadSample = async (filename: string) => {
    try {
      const res = await fetch(`/${filename}`);
      if (!res.ok) return;
      onFile(new File([await res.blob()], filename, { type: "text/csv" }));
    } catch {
      /* ignore; manual upload still works */
    }
  };

  return (
    <div className="mx-auto max-w-2xl pt-12 text-center">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-border bg-amber-bg px-3 py-1 text-[11px] font-medium text-amber shadow-card">
        <span className="h-1.5 w-1.5 rounded-full bg-amber" />
        Human-approved by design
      </span>
      <h1 className="mt-5 text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-[52px]">
        The agent that pauses before every GitLab write.
      </h1>
      <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-muted">
        Loopback triages your customers&apos; feedback,{" "}
        <span className="font-medium text-ink">learns what you reject</span>, and waits for your
        call before creating a single GitLab issue. PII redacted server-side. Every decision
        logged.
      </p>

      <div>
        <label
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); onFile(e.dataTransfer.files?.[0] ?? null); }}
          className={`mt-9 flex cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 transition ${
            drag ? "border-primary bg-primary-bg" : "border-border-strong bg-surface hover:border-primary/50 hover:bg-primary-bg/40"
          }`}
        >
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-primary-bg text-primary">
            {busy ? <Spinner /> : <UploadIcon />}
          </div>
          <div className="text-sm font-semibold text-ink">{busy ? "Starting the agent…" : "Drop a feedback CSV, or click to choose"}</div>
          <div className="rounded-md bg-subtle px-2 py-1 font-mono text-[11px] text-muted">columns: id, text, channel, date</div>
        </label>

        <div className="mt-4 flex flex-col items-center gap-2">
          <div className="text-[10.5px] font-medium uppercase tracking-[0.1em] text-faint">
            or try a sample batch
          </div>
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            {SAMPLES.map((s) => (
              <button
                key={s.file}
                type="button"
                onClick={() => loadSample(s.file)}
                disabled={busy}
                title={s.desc}
                className="group rounded-md border border-border bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink shadow-sm transition hover:border-primary/60 hover:bg-primary-bg/30 hover:text-primary-strong disabled:opacity-50"
              >
                <span>{s.label}</span>
                <span className="ml-1.5 font-normal text-[10.5px] text-faint group-hover:text-primary/70">{s.size}</span>
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-red-border bg-red-bg px-4 py-3 text-left text-sm text-red">
            <span className="mt-0.5">⚠</span>
            <span>{error}</span>
          </div>
        )}

        <div className="mx-auto mt-10 grid max-w-lg grid-cols-3 gap-3 text-left">
          <Pillar n="1" title="Cluster & rank" body="Themes by frequency × severity" />
          <Pillar n="2" title="You approve" body="A real pause, nothing auto-filed" />
          <Pillar n="3" title="Create in GitLab" body="Labels + linked duplicates" />
        </div>
      </div>
    </div>
  );
}


// A 2-second "this in, this out" example that lands the value before the user clicks.
function MicroDemo() {
  return (
    <div className="mx-auto mt-10 grid max-w-xl grid-cols-[1fr_auto_1fr] items-center gap-3 rounded-2xl border border-border bg-surface px-5 py-4 text-left shadow-card">
      <div className="min-w-0">
        <div className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-faint">customer feedback</div>
        <p className="mt-1.5 text-[12.5px] italic leading-snug text-ink/70">
          &ldquo;Trial signup keeps looping me back to login. Tried three times, gave up.&rdquo;
        </p>
      </div>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-primary" aria-hidden>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
      <div className="min-w-0">
        <div className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-faint">drafted gitlab issue</div>
        <p className="mt-1.5 text-[12.5px] font-medium leading-snug text-ink">Signup loop sends users back to login after verification</p>
        <div className="mt-1.5 flex flex-wrap gap-1">
          <span className="rounded-full border border-border bg-subtle px-1.5 py-0.5 font-mono text-[9.5px] text-muted">bug</span>
          <span className="rounded-full border border-border bg-subtle px-1.5 py-0.5 font-mono text-[9.5px] text-muted">signup</span>
          <span className="rounded-full border border-amber-border bg-amber-bg px-1.5 py-0.5 font-mono text-[9.5px] text-amber">high</span>
        </div>
      </div>
    </div>
  );
}

function Pillar({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3.5 shadow-card">
      <span className="grid h-6 w-6 place-items-center rounded-full bg-primary-bg font-mono text-[11px] font-semibold text-primary">{n}</span>
      <div className="mt-2.5 text-[13px] font-semibold text-ink">{title}</div>
      <div className="mt-0.5 text-[11.5px] leading-snug text-muted">{body}</div>
    </div>
  );
}

/* ============================================================= now-thinking */

// A live status ribbon that sits above the workspace and the activity panel.
// Reads (a) the most recent step author + text, (b) the run's timings, and
// shows what the agent is doing RIGHT NOW with an elapsed counter. The ribbon
// freezes at the gate (the agent really has stopped) and again at done. This
// is the at-a-glance state visibility that single-row stoppers don't give you.
function NowThinking({ run }: { run: RunState }) {
  const startedAt = run.timings.started_at;
  const gateAt = run.timings.gate_at;
  const doneAt = run.timings.done_at;
  const status = run.status;

  // freeze the counter at the right moment for each status
  const frozenAt =
    status === "awaiting_approval"
      ? gateAt
      : status === "done" || status === "empty" || status === "error"
        ? doneAt
        : null;
  const isLive = startedAt != null && frozenAt == null;

  // tick to refresh elapsed while live; cheap (250ms re-render of one component)
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isLive) return;
    const t = setInterval(() => setTick((x) => x + 1), 250);
    return () => clearInterval(t);
  }, [isLive]);

  if (startedAt == null) return null;

  const endpoint = frozenAt ?? Date.now() / 1000;
  const elapsed = Math.max(0, endpoint - startedAt);

  const lastStep = run.steps.length > 0 ? run.steps[run.steps.length - 1] : null;
  const isAgentAuthor = lastStep && lastStep.author !== "user";
  const specialistName = isAgentAuthor ? humanizeAuthor(lastStep.author) : null;

  const tone =
    status === "awaiting_approval"
      ? "amber"
      : status === "done"
        ? "green"
        : status === "error"
          ? "red"
          : "primary";
  const palette = {
    primary: { dot: "bg-primary", ping: "bg-primary/40", label: "text-primary" },
    amber: { dot: "bg-amber", ping: "bg-amber/40", label: "text-amber" },
    green: { dot: "bg-green", ping: "bg-green/40", label: "text-green" },
    red: { dot: "bg-red", ping: "bg-red/40", label: "text-red" },
  }[tone];

  const stateLabel =
    status === "awaiting_approval"
      ? "Paused for your approval"
      : status === "creating"
        ? "Writing to GitLab"
        : status === "done"
          ? "Run complete"
          : status === "empty"
            ? "Nothing to file"
            : status === "error"
              ? "Stopped"
              : "Agent is working";

  return (
    <div className="mb-5 flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-2.5 shadow-card">
      <span className="relative flex h-2.5 w-2.5 shrink-0 items-center justify-center">
        {isLive && (
          <span className={`absolute inset-0 animate-ping rounded-full ${palette.ping}`} />
        )}
        <span className={`relative h-2 w-2 rounded-full ${palette.dot}`} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 font-mono text-[9.5px] font-bold uppercase tracking-[0.14em]">
          <span className={palette.label}>{stateLabel}</span>
          {specialistName && (
            <>
              <span className="text-faint">·</span>
              <span className="text-ink">{specialistName}</span>
            </>
          )}
        </div>
        <div className="mt-0.5 truncate text-[12.5px] leading-snug text-muted">
          {lastStep?.text ?? "Starting the pipeline…"}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-[13px] font-semibold tabular-nums text-ink">{formatElapsed(elapsed)}</div>
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-faint">elapsed</div>
      </div>
    </div>
  );
}

function formatElapsed(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/* =================================================================== review */

function Review({
  run,
  rejected,
  setRejected,
  edits,
  onEdit,
  editedFields,
  expanded,
  toggleExpanded,
  expandAll,
  extendOverrides,
  toggleExtendOverride,
  submitting,
  onSubmit,
}: {
  run: RunState;
  rejected: Set<string>;
  setRejected: (s: Set<string>) => void;
  edits: Record<string, DraftEdit>;
  onEdit: (themeId: string, patch: DraftEdit) => void;
  editedFields: Record<string, EditedFields>;
  expanded: Record<string, boolean>;
  toggleExpanded: (themeId: string, defaultOpen: boolean) => void;
  expandAll: (open: boolean) => void;
  extendOverrides: Set<string>;
  toggleExtendOverride: (themeId: string) => void;
  submitting: boolean;
  onSubmit: () => void;
}) {
  const atGate = run.status === "awaiting_approval";
  const drafts = run.drafts;
  const approvedCount = drafts.length - drafts.filter((d) => rejected.has(d.theme_id)).length;
  const hasTriage = run.triage.total > 0;
  const editedCount = Object.values(editedFields).filter(
    (e) => e.title || e.body || e.priority || e.labels,
  ).length;
  const allOpen = drafts.length > 0 && drafts.every((d, i) => expanded[d.theme_id] ?? i === 0);
  // routing counts from the Triage Router Agent
  const highCount = drafts.filter((d) => d.lane === "high").length;
  const reviewCount = drafts.filter((d) => d.lane === "needs_review").length;
  const extendCount = drafts.filter((d) => d.lane === "extend_existing").length;
  const hasLanes = highCount + reviewCount + extendCount > 0;

  // Prioritize-and-grid: loud lanes (high / extend / regression) stay full width;
  // the long tail of needs_review cards drops into a 2-col grid below so reviewing
  // 14 themes doesn't read as a wall of cards. Both render the same IssueCard.
  const priorityDrafts = drafts.filter(
    (d) => d.lane === "high" || d.lane === "extend_existing" || d.regression_of != null,
  );
  const tailDrafts = drafts.filter(
    (d) => d.lane !== "high" && d.lane !== "extend_existing" && d.regression_of == null,
  );

  const toggle = (id: string) => {
    const next = new Set(rejected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setRejected(next);
  };

  return (
    <>
      <NowThinking run={run} />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div>
        {atGate && (
          <GateBanner
            approvedCount={approvedCount}
            editedCount={editedCount}
            submitting={submitting}
            onSubmit={onSubmit}
          />
        )}

        {hasTriage && <TriageBar triage={run.triage} />}

        {!hasTriage && drafts.length === 0 && <SignalsPreview preview={run.preview} />}
        {hasTriage && drafts.length === 0 && <DraftingSkeleton />}

        {drafts.length > 0 && (
          <>
            <div className="mt-4 flex items-center justify-between px-1">
              <div className="text-[11.5px] text-muted">
                {drafts.length} proposed issue{drafts.length === 1 ? "" : "s"}
                {hasLanes && (
                  <>
                    {" · "}
                    <span className="text-ink">{highCount}</span> ready for one-click approve
                    {reviewCount > 0 && (
                      <>
                        {" · "}
                        <span className="text-amber">{reviewCount} need your judgment</span>
                      </>
                    )}
                    {extendCount > 0 && (
                      <>
                        {" · "}
                        <span className="text-primary">
                          {extendCount} will extend existing
                        </span>
                      </>
                    )}
                  </>
                )}
                {atGate && editedCount > 0 && (
                  <>
                    {" · "}
                    <span className="text-amber">{editedCount} edited by you</span>
                  </>
                )}
              </div>
              <button
                onClick={() => expandAll(!allOpen)}
                className="text-[11.5px] font-medium text-primary transition hover:text-primary-strong"
              >
                {allOpen ? "Collapse all details" : "Expand all details"}
              </button>
            </div>
            {/* PRIORITY DRAFTS — full width, loud. The agent's distinct decisions. */}
            <div className="mt-3 space-y-4">
              {priorityDrafts.map((d, i) => (
                <IssueCard
                  key={d.theme_id}
                  draft={{ ...d, ...(edits[d.theme_id] || {}) }}
                  index={i}
                  editable={atGate}
                  atGate={atGate}
                  rejected={rejected.has(d.theme_id)}
                  onToggle={() => toggle(d.theme_id)}
                  onEdit={(patch) => onEdit(d.theme_id, patch)}
                  edited={editedFields[d.theme_id] ?? NO_EDITS}
                  expanded={expanded[d.theme_id] ?? i === 0}
                  onToggleExpanded={() => toggleExpanded(d.theme_id, i === 0)}
                  extendOverridden={extendOverrides.has(d.theme_id)}
                  onToggleExtendOverride={() => toggleExtendOverride(d.theme_id)}
                />
              ))}
            </div>

            {/* LONG TAIL — compact 2-col grid. The needs_review cards the
                agent isn't confident enough to auto-route. Browsable, not a wall. */}
            {tailDrafts.length > 0 && (
              <div className="mt-7">
                <div className="mb-3 flex items-center gap-3">
                  <span className="h-px flex-1 bg-border" />
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
                    Long tail · {tailDrafts.length} for your judgment
                  </span>
                  <span className="h-px flex-1 bg-border" />
                </div>
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  {tailDrafts.map((d, i) => {
                    const flatIndex = priorityDrafts.length + i;
                    return (
                      <IssueCard
                        key={d.theme_id}
                        draft={{ ...d, ...(edits[d.theme_id] || {}) }}
                        index={flatIndex}
                        editable={atGate}
                        atGate={atGate}
                        rejected={rejected.has(d.theme_id)}
                        onToggle={() => toggle(d.theme_id)}
                        onEdit={(patch) => onEdit(d.theme_id, patch)}
                        edited={editedFields[d.theme_id] ?? NO_EDITS}
                        expanded={expanded[d.theme_id] ?? false}
                        onToggleExpanded={() => toggleExpanded(d.theme_id, false)}
                        extendOverridden={extendOverrides.has(d.theme_id)}
                        onToggleExtendOverride={() => toggleExtendOverride(d.theme_id)}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div>
        <StepLog steps={run.steps} live={!atGate} dim={atGate} />
      </div>
    </div>
    {atGate && (
      <>
        <div aria-hidden className="h-24" />
        <GateDock
          approvedCount={approvedCount}
          rejectedCount={rejected.size}
          editedCount={editedCount}
          overrideCount={extendOverrides.size}
          submitting={submitting}
          onSubmit={onSubmit}
        />
      </>
    )}
    </>
  );
}

// Sticky bottom-center dock surface — the primary call-to-action while the
// agent is paused. Banner up top names the moment; dock down here is the click.
function GateDock({
  approvedCount,
  rejectedCount,
  editedCount,
  overrideCount,
  submitting,
  onSubmit,
}: {
  approvedCount: number;
  rejectedCount: number;
  editedCount: number;
  overrideCount: number;
  submitting: boolean;
  onSubmit: () => void;
}) {
  return (
    <div className="dock-slide pointer-events-none fixed inset-x-0 bottom-5 z-30 flex justify-center">
      <div className="pointer-events-auto flex items-center gap-4 rounded-2xl border border-border-strong bg-surface px-3 py-3 shadow-pop">
        <div className="flex items-center gap-3 pl-3 pr-1 font-mono text-[11px] tabular-nums">
          <span className="text-ink">
            <span className="text-[14px] font-semibold">{approvedCount}</span>
            <span className="ml-1 text-faint">ready</span>
          </span>
          {rejectedCount > 0 && (
            <>
              <span className="h-3 w-px bg-border" />
              <span className="text-muted">
                <span className="font-semibold text-ink">{rejectedCount}</span>
                <span className="ml-1 text-faint">rejected</span>
              </span>
            </>
          )}
          {overrideCount > 0 && (
            <>
              <span className="h-3 w-px bg-border" />
              <span className="text-muted">
                <span className="font-semibold text-ink">{overrideCount}</span>
                <span className="ml-1 text-faint">override</span>
              </span>
            </>
          )}
          {editedCount > 0 && (
            <>
              <span className="h-3 w-px bg-border" />
              <span className="text-amber">
                <span className="font-semibold">{editedCount}</span>
                <span className="ml-1 text-amber/60">edited</span>
              </span>
            </>
          )}
        </div>
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitting || approvedCount === 0}
          className="inline-flex items-center gap-3 rounded-xl bg-amber px-5 py-2.5 text-[13.5px] font-semibold text-white shadow-card transition hover:bg-amber/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Creating in GitLab…" : approvedCount === 0 ? "Reject all" : `Approve ${approvedCount} · create in GitLab`}
          <span className="ml-1 inline-flex items-center gap-0.5 rounded-md bg-white/15 px-1.5 py-0.5 font-mono text-[10.5px] font-semibold tracking-tight">
            <span>⌘</span>
            <span>↵</span>
          </span>
        </button>
      </div>
    </div>
  );
}

function GateBanner({
  approvedCount,
  editedCount,
  submitting,
  onSubmit,
}: {
  approvedCount: number;
  editedCount: number;
  submitting: boolean;
  onSubmit: () => void;
}) {
  return (
    <div className="gate-pulse gate-slide sticky top-[64px] z-20 mb-5 rounded-xl border border-amber-border bg-amber-bg px-5 py-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full border border-amber-border bg-surface text-amber">⏸</span>
          <div>
            <div className="text-sm font-semibold text-amber">The agent has paused for your approval</div>
            <div className="mt-0.5 text-[13px] text-muted">
              Nothing is created until you decide. Edit any field, drop the ones you don&apos;t want, then create the rest.
              {editedCount > 0 && (
                <>
                  {" "}
                  <span className="font-medium text-amber">{editedCount} edit{editedCount === 1 ? "" : "s"} ready to apply.</span>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden items-center gap-1.5 text-[11px] text-muted sm:inline-flex">
            <span className="kbd">⌘</span>
            <span className="kbd">↵</span>
            to approve
          </span>
          <button
            onClick={onSubmit}
            disabled={submitting}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-pop transition hover:bg-primary-strong disabled:opacity-60"
          >
            {submitting ? "Creating…" : approvedCount > 0 ? `Approve & create ${approvedCount}` : "Reject all"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SignalsPreview({ preview }: { preview: RunState["preview"] }) {
  if (!preview || preview.total === 0) return <RunningSkeleton />;
  return (
    <div className="risein overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="text-sm font-semibold text-ink">
          Parsed <span className="text-primary">{preview.total}</span> customer signals
        </div>
        <div className="font-mono text-[11px] text-muted">first {preview.sample.length} shown</div>
      </div>
      <div className="scroll-slim max-h-[60vh] overflow-y-auto">
        <table className="w-full border-collapse text-left text-[12.5px]">
          <thead className="sticky top-0 bg-subtle text-[10px] uppercase tracking-[0.1em] text-muted">
            <tr className="border-b border-border">
              <th className="px-5 py-2 font-semibold">#</th>
              <th className="py-2 pr-3 font-semibold">channel</th>
              <th className="py-2 pr-5 font-semibold">feedback</th>
            </tr>
          </thead>
          <tbody>
            {preview.sample.map((s, i) => (
              <tr key={s.id || i} className="border-b border-border/70 align-top last:border-0">
                <td className="px-5 py-2.5 font-mono text-[11px] text-faint">{i + 1}</td>
                <td className="py-2.5 pr-3">
                  <span className="rounded-md bg-subtle px-1.5 py-0.5 font-mono text-[10.5px] text-muted">{s.channel}</span>
                </td>
                <td className="py-2.5 pr-5 leading-snug text-ink/90">{s.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border bg-subtle/50 px-5 py-2.5 text-[11px] text-muted">
        Clustering these into themes ranked by frequency and severity.
      </div>
    </div>
  );
}

function DraftingSkeleton() {
  return (
    <div className="mt-4 space-y-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-xl border border-border bg-surface p-5 shadow-card">
          <div className="flex items-center justify-between">
            <div className="h-5 w-16 animate-pulse rounded-md bg-subtle" />
            <div className="h-2 w-14 animate-pulse rounded-full bg-subtle/70" />
          </div>
          <div className="mt-4 h-4 w-3/4 animate-pulse rounded bg-subtle" />
          <div className="mt-2 h-3 w-1/2 animate-pulse rounded bg-subtle/80" />
          <div className="mt-4 h-3 w-full animate-pulse rounded bg-subtle/60" />
          <div className="mt-2 h-3 w-5/6 animate-pulse rounded bg-subtle/60" />
        </div>
      ))}
      <div className="text-center text-[11.5px] text-faint">Drafting issues from the top themes…</div>
    </div>
  );
}

function RunningSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="animate-pulse rounded-xl border border-border bg-surface p-5 shadow-card">
          <div className="h-4 w-2/3 rounded bg-subtle" />
          <div className="mt-3 h-3 w-full rounded bg-subtle" />
          <div className="mt-2 h-3 w-4/5 rounded bg-subtle" />
        </div>
      ))}
    </div>
  );
}

const PRIORITY: Record<string, { cls: string; label: string }> = {
  critical: { cls: "border-red-border bg-red-bg text-red", label: "Critical" },
  high: { cls: "border-amber-border bg-amber-bg text-amber", label: "High" },
  medium: { cls: "border-blue/30 bg-blue-bg text-blue", label: "Medium" },
  low: { cls: "border-border bg-subtle text-muted", label: "Low" },
};

const PRIORITY_OPTS = ["critical", "high", "medium", "low"] as const;

function IssueCard({
  draft,
  index,
  editable,
  atGate,
  rejected,
  onToggle,
  onEdit,
  edited,
  expanded,
  onToggleExpanded,
  extendOverridden,
  onToggleExtendOverride,
}: {
  draft: Draft;
  index: number;
  editable: boolean;
  atGate: boolean;
  rejected: boolean;
  onToggle: () => void;
  onEdit: (patch: DraftEdit) => void;
  edited: EditedFields;
  expanded: boolean;
  onToggleExpanded: () => void;
  extendOverridden: boolean;
  onToggleExtendOverride: () => void;
}) {
  const p = PRIORITY[draft.priority] ?? PRIORITY.low;
  const [labelInput, setLabelInput] = useState("");
  const anyEdited = edited.title || edited.body || edited.priority || edited.labels;
  const hasDetails =
    Boolean(draft.body) ||
    draft.evidence_quotes.length > 0 ||
    draft.repro_steps.length > 0 ||
    Boolean(draft.remediation);

  const addLabel = () => {
    const v = labelInput.trim();
    if (v && !draft.suggested_labels.includes(v)) onEdit({ suggested_labels: [...draft.suggested_labels, v] });
    setLabelInput("");
  };
  const removeLabel = (l: string) => onEdit({ suggested_labels: draft.suggested_labels.filter((x) => x !== l) });

  const needsReview = draft.lane === "needs_review";
  // extending = the classifier routed this to extend_existing AND the human hasn't overridden
  const extending = draft.lane === "extend_existing" && !extendOverridden;
  const regressionOf = draft.regression_of ?? null;
  return (
    <article
      className={`risein overflow-hidden rounded-xl border bg-surface shadow-card transition ${
        atGate ? "gate-lift" : ""
      } ${
        regressionOf
          ? "ring-1 ring-red/25"
          : extending
            ? "ring-1 ring-primary/20"
            : draft.lane === "high"
              ? "ring-1 ring-green/20"
              : needsReview
                ? "border-l-2 border-l-amber"
                : ""
      } ${
        rejected ? "border-border opacity-60" : "border-border hover:border-border-strong hover:shadow-pop"
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* LANE BAND — the agent's headline decision for this draft (the demo beat) */}
      {regressionOf && (
        <div className="flex items-center gap-2.5 border-b border-red-border bg-gradient-to-r from-red-bg via-red-bg/80 to-red-bg/30 px-5 py-2.5">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-red" aria-hidden>
            <path d="M12 9v4" />
            <path d="M12 17h.01" />
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          </svg>
          <div className="flex-1 text-[11.5px] font-bold uppercase tracking-[0.08em] text-red">
            Flagged as possible regression of #{regressionOf}
          </div>
          <span className="hidden font-mono text-[10px] text-red/70 sm:inline">classifier · regression</span>
        </div>
      )}
      {!regressionOf && extending && (
        <div className="flex items-center gap-2.5 border-b border-primary/40 bg-gradient-to-r from-primary-bg via-primary-bg/70 to-primary-bg/30 px-5 py-2.5">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-primary" aria-hidden>
            <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
            <path d="M21 3v5h-5" />
            <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
            <path d="M3 21v-5h5" />
          </svg>
          <div className="flex-1 text-[11.5px] font-bold uppercase tracking-[0.08em] text-primary">
            Will extend existing issue #{draft.extend_target}
          </div>
          <span className="hidden font-mono text-[10px] text-primary/70 sm:inline">classifier · duplicate</span>
        </div>
      )}
      {!regressionOf && !extending && draft.lane === "high" && (
        <div className="flex items-center gap-2.5 border-b border-green-border bg-gradient-to-r from-green-bg/70 via-green-bg/30 to-transparent px-5 py-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-green" aria-hidden>
            <path d="M5 13l4 4L19 7" />
          </svg>
          <div className="flex-1 text-[11.5px] font-bold uppercase tracking-[0.08em] text-green">
            Ready for one-click approve
          </div>
        </div>
      )}

      <div className="p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {editable ? (
              <select
                value={draft.priority}
                onChange={(e) => onEdit({ priority: e.target.value })}
                className={`cursor-pointer rounded-md border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide focus:outline-none focus:ring-2 focus:ring-primary/30 ${p.cls} ${edited.priority ? "ring-1 ring-amber/50" : ""}`}
              >
                {PRIORITY_OPTS.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            ) : (
              <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${p.cls}`}>{p.label}</span>
            )}
            {needsReview && !extending && !regressionOf && (
              <span
                className="inline-flex items-center gap-1 rounded-full border border-amber-border bg-amber-bg px-2 py-0.5 text-[10px] font-semibold text-amber"
                title="The Triage Router Agent flagged this for PM judgment. Top-rank, high-score drafts are pre-routed for one-click approve."
              >
                <span className="h-1.5 w-1.5 rounded-full bg-amber" />
                needs your judgment
              </span>
            )}
            {anyEdited && (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-border bg-amber-bg px-2 py-0.5 text-[10px] font-semibold text-amber" title="The human has edited this draft">
                <span className="h-1.5 w-1.5 rounded-full bg-amber" />
                edited by you
              </span>
            )}
          </div>
          <ApproveToggle rejected={rejected} disabled={!editable} onToggle={onToggle} />
        </div>

        {regressionOf && draft.classifier_reason && (
          <div className="mt-3 rounded-md border-l-2 border-red bg-red-bg/25 px-3.5 py-2">
            <div className="font-mono text-[9.5px] font-semibold uppercase tracking-[0.12em] text-red">
              Agent reasoning · why this isn&apos;t a new ticket
            </div>
            <p className="mt-1.5 text-[12.5px] italic leading-relaxed text-ink/85">
              &ldquo;{draft.classifier_reason}&rdquo;
            </p>
            <p className="mt-1.5 text-[11px] leading-snug text-muted">
              If approved, the new issue links to #{regressionOf} via link_work_items and appends a regression note for the team.
            </p>
          </div>
        )}

      {extending && draft.comment_body ? (
        <ExtendPanel
          draft={draft}
          editable={editable}
          onOverride={onToggleExtendOverride}
        />
      ) : (
        <>
          {editable ? (
            <input
              value={draft.title}
              onChange={(e) => onEdit({ title: e.target.value })}
              aria-label="Issue title"
              className={`mt-3 w-full rounded-md border border-transparent bg-subtle/60 px-2.5 py-1.5 text-[15px] font-semibold text-ink transition hover:bg-subtle focus:border-primary/40 focus:bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 ${edited.title ? "edited-rule bg-amber-bg/40" : ""} ${rejected ? "line-through decoration-faint" : ""}`}
            />
          ) : (
            <h3 className={`mt-3 text-[15px] font-semibold leading-snug text-ink ${rejected ? "line-through decoration-faint" : ""}`}>{draft.title}</h3>
          )}

          <WhyLine draft={draft} />

          {/* If the classifier wanted to extend but the human overrode, show the path back */}
          {extendOverridden && draft.extend_target && editable && (
            <button
              onClick={onToggleExtendOverride}
              className="mt-2 text-[11.5px] font-medium text-primary transition hover:text-primary-strong"
            >
              ← undo override (extend #{draft.extend_target} instead)
            </button>
          )}

          {hasDetails && (
            <button
              onClick={onToggleExpanded}
              className="mt-3 inline-flex items-center gap-1 text-[11.5px] font-medium text-primary transition hover:text-primary-strong"
              aria-expanded={expanded}
            >
              <Chevron open={expanded} />
              {expanded ? "Hide details" : "Show details"}
            </button>
          )}

          {expanded && hasDetails && (
            <div className="details-open">
              {editable ? (
                <textarea
                  value={draft.body}
                  onChange={(e) => onEdit({ body: e.target.value })}
                  rows={8}
                  aria-label="Issue description"
                  className={`mt-3 w-full resize-y rounded-md border border-transparent bg-subtle/60 px-2.5 py-2 font-mono text-[12px] leading-relaxed text-muted transition hover:bg-subtle focus:border-primary/40 focus:bg-surface focus:text-ink focus:outline-none focus:ring-2 focus:ring-primary/20 ${edited.body ? "edited-rule bg-amber-bg/40 text-ink" : ""}`}
                />
              ) : (
                <MarkdownBody text={draft.body} />
              )}

              {draft.repro_steps.length > 0 && (
                <div className="mt-4">
                  <SectionLabel>Repro</SectionLabel>
                  <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-[13px] text-ink/85 marker:text-faint">
                    {draft.repro_steps.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ol>
                </div>
              )}

              {draft.remediation && (
                <div className="mt-4">
                  <SectionLabel>Suggested fix</SectionLabel>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink/85">{draft.remediation}</p>
                </div>
              )}
            </div>
          )}
        </>
      )}

      <div className={`mt-4 flex flex-wrap items-center gap-1.5 border-t pt-3.5 ${edited.labels ? "border-amber/40" : "border-border"}`}>
        {draft.suggested_labels.map((l) =>
          editable ? (
            <span
              key={l}
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-mono text-[11px] ${edited.labels ? "border-amber-border bg-amber-bg/60 text-amber" : "border-border bg-subtle text-muted"}`}
              title="Applied at issue creation via the official GitLab MCP server — no quick-action workaround."
            >
              {l}
              <button onClick={() => removeLabel(l)} aria-label={`remove ${l}`} className="text-faint transition hover:text-red">×</button>
            </span>
          ) : (
            <span
              key={l}
              className="rounded-full border border-border bg-subtle px-2.5 py-0.5 font-mono text-[11px] text-muted"
              title="Applied at issue creation via the official GitLab MCP server — no quick-action workaround."
            >
              {l}
            </span>
          ),
        )}
        {editable && (
          <input
            value={labelInput}
            onChange={(e) => setLabelInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addLabel(); } }}
            onBlur={addLabel}
            placeholder="+ label"
            aria-label="Add label"
            className="w-24 rounded-full border border-dashed border-border-strong bg-surface px-2.5 py-0.5 font-mono text-[11px] text-ink placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        )}
        {draft.related_iids.length > 0 && (
          <span
            className="ml-1 inline-flex items-center gap-1 font-mono text-[11px] text-primary"
            title="Linked via link_work_items — first-class work-item relation, not a /relate quick-action note."
          >
            ↔ relates #{draft.related_iids.join(", #")}
          </span>
        )}
      </div>
      </div>
    </article>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform ${open ? "rotate-90" : ""}`}
      aria-hidden
    >
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function ApproveToggle({ rejected, disabled, onToggle }: { rejected: boolean; disabled: boolean; onToggle: () => void }) {
  if (disabled) return null;
  return (
    <button
      onClick={onToggle}
      className={`shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
        rejected
          ? "border-border bg-surface text-muted hover:border-border-strong hover:text-ink"
          : "border-green-border bg-green-bg text-green hover:bg-green-bg/70"
      }`}
    >
      {rejected ? "Rejected · undo" : "✓ Approved"}
    </button>
  );
}

// Read-only preview of the comment_body the agent will post to an existing issue.
// Includes the "Override → file new instead" toggle so the human stays in command.
function ExtendPanel({
  draft,
  editable,
  onOverride,
}: {
  draft: Draft;
  editable: boolean;
  onOverride: () => void;
}) {
  const target = draft.extend_target ?? null;
  return (
    <div className="mt-3 rounded-lg border border-primary/20 bg-primary-bg/40 p-4">
      <div className="flex items-start gap-2.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 text-primary" aria-hidden>
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
        <div className="min-w-0 flex-1">
          <div className="text-[13.5px] font-semibold text-ink">
            Will extend #{target} instead of creating a new issue
          </div>
          {draft.classifier_reason && (
            <div className="mt-1 text-[11.5px] leading-snug text-muted">
              <span className="font-medium text-ink/70">Why:</span> {draft.classifier_reason}
            </div>
          )}
          <div className="mt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
            Comment that will be posted
          </div>
          <div className="mt-1.5 rounded-md border border-border bg-surface px-3 py-2 font-mono text-[11.5px] leading-relaxed text-ink/80 whitespace-pre-wrap">
            {draft.comment_body}
          </div>
          {editable && (
            <button
              onClick={onOverride}
              className="mt-3 inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-[11px] font-medium text-muted shadow-card transition hover:border-border-strong hover:text-ink"
            >
              Override → file as new issue instead
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Minimal markdown for the issue body: just ## section headings + > blockquotes +
// numbered lists + paragraphs. No external dep. The agent emits a known format.
function MarkdownBody({ text }: { text: string }) {
  const lines = (text || "").split("\n");
  const out: React.ReactNode[] = [];
  let buf: string[] = [];
  const flushPara = (key: string) => {
    if (buf.length === 0) return;
    out.push(
      <p key={`p-${key}`} className="mt-2 text-[13px] leading-relaxed text-ink/85">
        {buf.join(" ")}
      </p>,
    );
    buf = [];
  };
  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    if (/^##\s/.test(line)) {
      flushPara(`b${i}`);
      out.push(
        <div key={`h-${i}`} className="mt-4 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
          {line.replace(/^##\s+/, "")}
        </div>,
      );
    } else if (/^>\s?/.test(line)) {
      flushPara(`b${i}`);
      out.push(
        <p key={`q-${i}`} className="mt-2 border-l-2 border-primary/40 bg-primary-bg/40 py-1 pl-3 pr-2 text-[12.5px] italic leading-snug text-ink/75">
          {line.replace(/^>\s?/, "")}
        </p>,
      );
    } else if (line.trim() === "") {
      flushPara(`b${i}`);
    } else {
      buf.push(line);
    }
  });
  flushPara("end");
  return <div className="mt-3">{out}</div>;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">{children}</span>;
}

/* ============================================================== triage stats */

// Count a number up from 0 with an easeOutCubic curve. Mount-once; respects reduced motion.
function useCountUp(target: number, duration = 750) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setN(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return n;
}

// Trust strip: a single restrained row that names the safety posture in concrete terms.
// Lives above the cards so the panel sees it before they read anything else.
function TrustStrip({ redaction }: { redaction: Redaction }) {
  const redactionTotal = redaction.email + redaction.phone + redaction.url;
  return (
    <div className="risein mb-4 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-border bg-surface/70 px-4 py-2.5 text-[11px] text-muted shadow-card">
      <span className="inline-flex items-center gap-1.5">
        <ShieldDot />
        <span title={redactionTotal > 0 ? `${redaction.email} emails, ${redaction.phone} phones, ${redaction.url} URLs across ${redaction.signals_touched} signals` : "Emails, phone numbers, and URLs are masked server-side before any model call."}>
          PII redacted
          {redactionTotal > 0 && (
            <span className="ml-1 text-faint">({redactionTotal})</span>
          )}
        </span>
      </span>
      <TrustDot />
      <span title="Every approval, rejection, and edit is captured in the decision log on the done state.">
        Every decision logged
      </span>
      <TrustDot />
      <span title="The run pauses server-side at request_confirmation. No GitLab tool runs until you submit a decision.">
        Zero GitLab writes without your approval
      </span>
      <TrustDot />
      <span title="Vertex AI on Google Cloud, via the Cloud Run service account — no API key.">
        Gemini 3 on Vertex AI
      </span>
      <TrustDot />
      <span title="https://gitlab.com/api/v4/mcp — OAuth 2.0 (DCR + PKCE).">
        GitLab Official MCP
      </span>
    </div>
  );
}

function ShieldDot() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-green" aria-hidden>
      <path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function TrustDot() {
  return <span className="text-faint" aria-hidden>·</span>;
}

function TriageBar({ triage }: { triage: Triage }) {
  const total = useCountUp(triage.total);
  const ignored = useCountUp(triage.ignored);
  const themes = useCountUp(triage.themes);
  if (!triage.total) return null;
  return (
    <div className="risein flex items-start gap-1 overflow-x-auto rounded-xl border border-border bg-surface px-5 py-4 shadow-card">
      <TriageStat value={total} label="signals analyzed" />
      <TriageArrow />
      <TriageStat value={ignored} label="ignored as noise" tone="muted" />
      <TriageArrow />
      <TriageStat value={themes} label="themes, ranked by impact" tone="primary" />
    </div>
  );
}

function TriageStat({ value, label, tone = "ink" }: { value: number; label: string; tone?: "ink" | "muted" | "primary" }) {
  const color = tone === "primary" ? "text-primary" : tone === "muted" ? "text-muted" : "text-ink";
  return (
    <div className="flex flex-col px-2">
      <span className={`text-[26px] font-semibold leading-none tabular-nums ${color}`}>{value}</span>
      <span className="mt-1.5 whitespace-nowrap text-[11px] font-medium text-muted">{label}</span>
    </div>
  );
}

function TriageArrow() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-1 shrink-0 text-faint" aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

/* ================================================================= why-line */

// The justification strip: WHY this theme made the cut and where it ranks. Every value is
// computed deterministically server-side (frequency × severity), not estimated by the model.
function WhyLine({ draft }: { draft: Draft }) {
  const freq = draft.frequency ?? 0;
  const chans = draft.channels ?? [];
  if (!freq && !draft.rank) return null;
  const chanLabel = chans.length === 0 ? null : chans.length <= 3 ? chans.join(", ") : `${chans.length} channels`;
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[11.5px] text-muted">
      <RankChip rank={draft.rank} />
      <span className="font-medium tabular-nums text-ink/80">
        {freq} report{freq === 1 ? "" : "s"}
      </span>
      {chanLabel && (
        <>
          <WhyDot />
          <span>across {chanLabel}</span>
        </>
      )}
      <WhyDot />
      <span className="inline-flex items-center gap-1.5">
        severity <SeverityMeter value={draft.severity} />
      </span>
    </div>
  );
}

function RankChip({ rank }: { rank: number }) {
  if (!rank) return null;
  const top = rank === 1;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold tracking-wide ring-1 ${
        top ? "bg-amber-bg text-amber ring-amber-border" : "bg-subtle text-muted ring-border"
      }`}
    >
      {top && <span className="text-[8px] leading-none">▲</span>}#{rank} by impact
    </span>
  );
}

function SeverityMeter({ value }: { value: number }) {
  const v = Math.max(0, Math.min(5, value || 0));
  const tone = v >= 5 ? "bg-red" : v >= 4 ? "bg-amber" : v >= 3 ? "bg-amber" : "bg-blue";
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label={`severity ${v} of 5`}>
      <span className="inline-flex items-center gap-[3px]">
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={`h-2.5 w-[3px] rounded-full ${i <= v ? tone : "bg-border"}`} />
        ))}
      </span>
      <span className="tabular-nums text-ink/70">{v}/5</span>
    </span>
  );
}

function WhyDot() {
  return <span className="text-faint" aria-hidden>·</span>;
}

/* ================================================================= step log */

// Render snake_case agent names as "Signal Ingestion Agent" in the step log.
function humanizeAuthor(name: string): string {
  if (!name) return "agent";
  return name
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => (w.toLowerCase() === "gitlab" ? "GitLab" : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

function StepLog({ steps, live, dim }: { steps: Step[]; live: boolean; dim?: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [steps.length]);

  // Dark agent panel — the visual signal that this column is agent territory.
  // Terminal-style coloring: cyan for the specialist that just spoke, amber
  // for tool calls, neutral slate for everything else.
  return (
    <div className={`sticky top-[64px] overflow-hidden rounded-xl border border-[#1c2230] bg-[#0b0e14] shadow-pop ${dim ? "gate-dim" : ""}`}>
      <div className="flex items-center gap-2 border-b border-[#1c2230] bg-[#0f131c] px-4 py-2.5">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#67e8f9]">
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M7 9l3 3-3 3M13 15h4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-[#cbd5e1]">Agent activity</span>
        {live ? (
          <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[#67e8f9]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#67e8f9] blink" />
            live
          </span>
        ) : (
          <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[#fbbf24]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#fbbf24]" />
            paused
          </span>
        )}
      </div>
      <div className="scroll-slim max-h-[70vh] overflow-y-auto px-4 py-3">
        {steps.length === 0 && (
          <div className="py-2 font-mono text-[11.5px] text-[#64748b]">▸ Waiting for the agent…</div>
        )}
        <ol className="relative space-y-2.5 border-l border-[#1f2937] pl-4">
          {steps.map((s, i) => {
            const text = s.text ?? "";
            const isToolCall = text.startsWith("calling tool:");
            return (
              <li key={i} className="relative">
                <span
                  className={`absolute -left-[21px] top-1 h-2 w-2 rounded-full border-2 border-[#0b0e14] ${
                    isToolCall ? "bg-[#fbbf24]" : "bg-[#67e8f9]"
                  }`}
                />
                <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#67e8f9]">
                  {humanizeAuthor(s.author)}
                </div>
                <div
                  className={`mt-0.5 text-[12px] leading-snug ${
                    isToolCall ? "font-mono text-[#fbbf24]" : "text-[#cbd5e1]"
                  }`}
                >
                  {text}
                </div>
              </li>
            );
          })}
        </ol>
        <div ref={endRef} />
      </div>
    </div>
  );
}

/* =================================================================== result */

function Result({ run, onReset }: { run: RunState; onReset: () => void }) {
  const created: Created[] = run.created;
  const rejectedDrafts = run.drafts.filter((d) => run.rejected.includes(d.theme_id));
  const totalSignals = run.triage.total;
  const noise = run.triage.ignored;
  const analysisSeconds = run.timings.gate_at && run.timings.started_at
    ? Math.max(1, Math.round(run.timings.gate_at - run.timings.started_at))
    : null;
  // savings model is honest and conservative: 30s of human skim per signal, 8 min per
  // properly-scoped draft. Honest framing, not marketing.
  const savedMinutes = Math.round(totalSignals * 0.5 + created.length * 8);

  const createdNew = created.filter((c) => !c.extended);
  const extendedExisting = created.filter((c) => c.extended);

  return (
    <div className="mx-auto max-w-5xl risein">
      {/* ============ HERO BAND ============
          The 2:55 verification frame. Numbers, lists, and impact — all in one
          screen so a video viewer reads "agent did X work in Y time" without
          scrolling. */}
      <div className="overflow-hidden rounded-2xl border border-green-border bg-surface shadow-pop">
        <div className="grid grid-cols-1 gap-4 border-b border-border bg-gradient-to-br from-green-bg via-surface to-surface px-7 py-7 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-green">
              <span className="grid h-5 w-5 place-items-center rounded-full bg-green text-[10px] text-white">✓</span>
              Run complete
              {analysisSeconds && (
                <>
                  <span className="text-faint">·</span>
                  <span className="text-muted">in {humanDuration(Math.max(1, Math.round(analysisSeconds / 60)))}</span>
                  <span className="font-normal text-faint">({analysisSeconds}s)</span>
                </>
              )}
            </div>
            <h2 className="mt-2 text-[26px] font-semibold leading-tight tracking-tight text-ink sm:text-[30px]">
              <span className="tabular-nums">{totalSignals}</span>
              <span className="mx-2 text-faint">→</span>
              <span className="tabular-nums">{run.triage.themes}</span> themes
              <span className="mx-2 text-faint">→</span>
              <span className="tabular-nums text-green">{createdNew.length}</span> created
              {extendedExisting.length > 0 && (
                <>
                  <span className="mx-1 text-faint"> · </span>
                  <span className="tabular-nums text-primary">{extendedExisting.length}</span> extended
                </>
              )}
            </h2>
            <p className="mt-1.5 text-[12.5px] text-muted">
              <span className="font-medium text-ink/80">{run.triage.themed}</span> actionable signals across
              {" "}<span className="font-medium text-ink/80">{run.triage.themes}</span> themes;
              {" "}<span className="font-medium text-ink/80">{noise}</span> noise filtered before any model call.
            </p>
          </div>
          <div className="flex flex-wrap items-stretch gap-3 sm:flex-nowrap">
            <ImpactStat
              value={savedMinutes > 0 ? humanDuration(savedMinutes) : "0m"}
              label="saved"
              sub="of triage time"
              tone="ink"
            />
            <ImpactStat
              value={String(extendedExisting.length)}
              label="dedupes"
              sub="extends, not new"
              tone="primary"
            />
            <ImpactStat
              value={String(noise)}
              label="noise"
              sub={`of ${totalSignals} in`}
              tone="muted"
            />
          </div>
        </div>

        {(run.triage.filtered_by_learning ?? 0) > 0 && (
          <div className="border-b border-border bg-amber-bg/30 px-7 py-2.5 text-center">
            <span className="inline-flex items-center gap-2 text-[12px] text-ink/85">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber" aria-hidden>
                <path d="M9 11V7a3 3 0 0 1 6 0v4" />
                <rect x="3" y="11" width="18" height="11" rx="2" />
              </svg>
              <span>
                Filtered{" "}
                <span className="font-semibold tabular-nums text-ink">{run.triage.filtered_by_learning}</span>{" "}
                theme{(run.triage.filtered_by_learning ?? 0) === 1 ? "" : "s"} matching your past rejections.
                <span className="ml-1 text-muted">The agent gets sharper with every batch.</span>
              </span>
            </span>
          </div>
        )}

        {/* TWO-COLUMN ISSUE LISTS (created | extended) — side by side on lg,
            stacked on mobile. The verification beat sees both at once. */}
        <div className={`grid ${createdNew.length > 0 && extendedExisting.length > 0 ? "lg:grid-cols-2 lg:divide-x lg:divide-y-0 divide-y" : "grid-cols-1"} divide-border`}>
          {createdNew.length > 0 && (
            <div>
              <div className="flex items-center justify-between border-b border-border bg-subtle/40 px-5 py-2">
                <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-green">
                  New in GitLab · {createdNew.length}
                </span>
                <span className="font-mono text-[10px] tracking-tight text-faint">create_issue</span>
              </div>
              <div className="scroll-slim max-h-[42vh] divide-y divide-border overflow-y-auto">
                {createdNew.map((c) => (
                  <a
                    key={`new-${c.iid}`}
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex items-center justify-between gap-3 px-5 py-2.5 transition hover:bg-subtle"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="font-mono text-[12.5px] font-semibold text-green">#{c.iid}</span>
                      <span className="truncate text-[13px] font-medium text-ink">{c.title}</span>
                    </div>
                    <span className="shrink-0 text-[11px] font-medium text-muted transition group-hover:text-primary">open ↗</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {extendedExisting.length > 0 && (
            <div>
              <div className="flex items-center justify-between border-b border-border bg-subtle/40 px-5 py-2">
                <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">
                  Extended (declined to file new) · {extendedExisting.length}
                </span>
                <span className="font-mono text-[10px] tracking-tight text-faint">create_workitem_note</span>
              </div>
              <div className="scroll-slim max-h-[42vh] divide-y divide-border overflow-y-auto">
                {extendedExisting.map((c) => (
                  <a
                    key={`ext-${c.iid}`}
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex items-center justify-between gap-3 px-5 py-2.5 transition hover:bg-subtle"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="font-mono text-[12.5px] font-semibold text-primary">#{c.iid}</span>
                      <span className="truncate text-[13px] font-medium text-ink">{c.title}</span>
                    </div>
                    <span className="shrink-0 text-[11px] font-medium text-muted transition group-hover:text-primary">open ↗</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {rejectedDrafts.length > 0 && (
        <div className="mt-6">
          <SectionLabel>Rejected · {rejectedDrafts.length}</SectionLabel>
          <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {rejectedDrafts.map((d) => (
              <div key={d.theme_id} className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 text-[12.5px] text-muted shadow-card">
                <span className="text-red">✕</span>
                <span className="line-through decoration-faint">{d.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <DecisionLog run={run} />

      {run.steps.length > 0 && <AuditTrail steps={run.steps} />}

      <div className="mt-8 text-center">
        <button onClick={onReset} className="rounded-lg border border-border bg-surface px-5 py-2.5 text-sm font-medium text-ink shadow-card transition hover:border-border-strong">
          Triage another batch
        </button>
      </div>
    </div>
  );
}

// One of three big stacked numbers on the done state. The value is the
// magnitude; the label/sub are the question it answers.
function ImpactStat({
  value,
  label,
  sub,
  tone = "ink",
}: {
  value: string;
  label: string;
  sub: string;
  tone?: "ink" | "primary" | "muted";
}) {
  const color = tone === "primary" ? "text-primary" : tone === "muted" ? "text-muted" : "text-ink";
  return (
    <div className="min-w-[88px] flex-1 rounded-xl border border-border bg-surface px-3 py-2.5 text-center shadow-card sm:flex-none">
      <div className={`text-[22px] font-semibold leading-none tracking-tight tabular-nums ${color}`}>
        {value}
      </div>
      <div className="mt-1.5 font-mono text-[9.5px] font-semibold uppercase tracking-[0.12em] text-ink/80">
        {label}
      </div>
      <div className="mt-0.5 text-[10.5px] leading-snug text-muted">{sub}</div>
    </div>
  );
}

// Inline-prose duration formatter — "47 minutes", "2 hours", "2.4 hours".
function humanDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"}`;
  const hrs = minutes / 60;
  if (Math.abs(hrs - Math.round(hrs)) < 0.05) {
    const n = Math.round(hrs);
    return `${n} hour${n === 1 ? "" : "s"}`;
  }
  return `${hrs.toFixed(1)} hours`;
}

// Preview tile that names the next product step (closing the customer-facing loop).
// Marked "preview" so panelists read it as a real product trajectory, not vapor.
function ClosedLoopPreview({ reporterCount }: { reporterCount: number }) {
  return (
    <div className="risein mt-6 flex items-start gap-3 rounded-xl border border-dashed border-primary/40 bg-primary-bg/40 px-5 py-4 shadow-card">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface text-primary">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M4 4h16v12H5l-1 4z" />
          <path d="M8 9h8M8 12h5" />
        </svg>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">
            <span className="tabular-nums">{reporterCount}</span> reporter{reporterCount === 1 ? "" : "s"} waiting to hear when these ship
          </span>
          <span className="rounded-full border border-amber-border bg-amber-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide text-amber">
            preview
          </span>
        </div>
        <p className="mt-1 text-[12.5px] leading-snug text-muted">
          When GitLab marks an issue closed, Loopback will notify the customers who originally reported it,
          in their original channel. Closing the loop end to end.
        </p>
      </div>
    </div>
  );
}

// A full timestamped trail of what happened: who approved, who rejected, who was edited,
// what got created. The audit story panelists need to see for any agent that writes to
// systems of record.
function DecisionLog({ run }: { run: RunState }) {
  const [open, setOpen] = useState(false);
  const editedSet = new Set(run.edited_ids);
  const approvedSet = new Set(run.approved);
  const rejectedSet = new Set(run.rejected);
  const createdById = new Map(run.created.map((c) => [c.theme_id, c]));
  const total = run.drafts.length;
  if (!total) return null;
  const decidedAt = run.timings.decided_at;
  const formatTs = (ts: number | null) => (ts ? new Date(ts * 1000).toLocaleTimeString() : "—");

  return (
    <div className="mt-6 overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left transition hover:bg-subtle/60"
      >
        <div className="flex items-center gap-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted" aria-hidden>
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M7 8h10M7 12h10M7 16h6" />
          </svg>
          <SectionLabel>Decision log</SectionLabel>
          <span className="text-[11.5px] text-muted">
            {run.approved.length} approved · {run.rejected.length} rejected · {run.edited_ids.length} edited
          </span>
        </div>
        <Chevron open={open} />
      </button>
      {open && (
        <div className="details-open border-t border-border bg-subtle/30 px-5 py-3">
          <ol className="space-y-2">
            {run.drafts.map((d) => {
              const isApproved = approvedSet.has(d.theme_id);
              const isRejected = rejectedSet.has(d.theme_id);
              const wasEdited = editedSet.has(d.theme_id);
              const c = createdById.get(d.theme_id);
              return (
                <li key={d.theme_id} className="flex items-start gap-3 rounded-md bg-surface px-3 py-2 text-[12.5px] shadow-card">
                  <span
                    className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
                      c ? "bg-green text-white" : isRejected ? "bg-red/15 text-red" : "bg-subtle text-muted"
                    }`}
                    aria-hidden
                  >
                    {c ? "✓" : isRejected ? "✕" : "·"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-ink">{d.title}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
                      <span>
                        {c ? `Created #${c.iid}` : isRejected ? "Rejected" : isApproved ? "Approved" : "Pending"}
                      </span>
                      {wasEdited && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-amber-border bg-amber-bg px-1.5 py-0.5 text-[10px] font-semibold text-amber">
                          edited by you
                        </span>
                      )}
                      {c?.labels?.length ? (
                        <span className="text-faint">
                          labels: {c.labels.join(", ")}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <span className="shrink-0 font-mono text-[10.5px] text-faint">
                    {formatTs(decidedAt)}
                  </span>
                </li>
              );
            })}
          </ol>
          <div className="mt-3 text-[10.5px] leading-snug text-faint">
            All timestamps are local to your browser. Server logs hold the full trail.
          </div>
        </div>
      )}
    </div>
  );
}

/* ============================================================== audit trail */

// Collapsed-by-default accordion at the bottom of the done state. Surfaces the
// full agent activity log AFTER the run, so anyone who wants to audit the
// agent's reasoning, tool calls, and decisions can expand it inline without
// taking workspace real estate during the active run.
function AuditTrail({ steps }: { steps: Step[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-6 overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left transition hover:bg-subtle"
      >
        <div className="flex items-center gap-3">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted" aria-hidden>
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M7 9l3 3-3 3M13 15h4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <div className="text-[12.5px] font-semibold text-ink">Agent activity log</div>
            <div className="text-[11px] text-muted">
              {steps.length} event{steps.length === 1 ? "" : "s"} · the agent&apos;s reasoning, named tool calls, and decisions
            </div>
          </div>
        </div>
        <Chevron open={open} />
      </button>
      {open && (
        <div className="border-t border-border bg-[#0b0e14]">
          <div className="scroll-slim max-h-[55vh] overflow-y-auto px-4 py-3">
            <ol className="relative space-y-2.5 border-l border-[#1f2937] pl-4">
              {steps.map((s, i) => {
                const text = s.text ?? "";
                const isToolCall = text.startsWith("calling tool:");
                return (
                  <li key={i} className="relative">
                    <span
                      className={`absolute -left-[21px] top-1 h-2 w-2 rounded-full border-2 border-[#0b0e14] ${
                        isToolCall ? "bg-[#fbbf24]" : "bg-[#67e8f9]"
                      }`}
                    />
                    <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#67e8f9]">
                      {humanizeAuthor(s.author)}
                    </div>
                    <div
                      className={`mt-0.5 text-[12px] leading-snug ${
                        isToolCall ? "font-mono text-[#fbbf24]" : "text-[#cbd5e1]"
                      }`}
                    >
                      {text}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===================================================================== misc */

function Banner({ kind, title, body, onReset }: { kind: "error" | "empty"; title: string; body: string; onReset: () => void }) {
  const cls = kind === "error" ? "border-red-border bg-red-bg" : "border-border bg-surface";
  return (
    <div className={`mx-auto mt-6 max-w-xl rounded-2xl border ${cls} px-6 py-8 text-center shadow-card risein`}>
      <div className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-surface text-2xl shadow-card">{kind === "error" ? "⚠️" : "🔍"}</div>
      <h2 className="mt-3 text-xl font-semibold text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-muted">{body}</p>
      <button onClick={onReset} className="mt-6 rounded-lg border border-border bg-surface px-5 py-2.5 text-sm font-medium text-ink shadow-card transition hover:border-border-strong">
        Triage another batch
      </button>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M5 16v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3" />
    </svg>
  );
}
