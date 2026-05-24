"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createRun,
  getRun,
  postDecision,
  type Created,
  type Draft,
  type RunState,
  type Step,
} from "@/lib/api";

const TERMINAL = new Set(["done", "empty", "error"]);

export default function Home() {
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // rejected theme_ids chosen by the human at the gate (default: everything approved)
  const [rejected, setRejected] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  // poll the run while it is live
  useEffect(() => {
    if (!runId) return;
    let alive = true;
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
    let timer = setTimeout(tick, 400);
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
      setRun({ status: "running", steps: [], drafts: [], created: [], approved: [], rejected: [], error: null });
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const submitDecision = async () => {
    if (!runId || !run) return;
    setSubmitting(true);
    const approved = run.drafts.map((d) => d.theme_id).filter((id) => !rejected.has(id));
    try {
      await postDecision(runId, approved, [...rejected]);
      setRun({ ...run, status: "creating" });
      resumePolling();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Couldn't submit.");
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setRunId(null);
    setRun(null);
    setRejected(new Set());
    setUploadError(null);
  };

  const status = run?.status;
  const showReview = status === "awaiting_approval" || status === "running" || status === "creating";

  return (
    <div className="flex min-h-full flex-col">
      <Header status={status} onReset={runId ? reset : undefined} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 pb-24 pt-8">
        {!runId && <Upload onFile={onFile} busy={busy} error={uploadError} />}

        {runId && status === "error" && <Banner kind="error" title="The run hit a problem" body={run?.error ?? "Unknown error."} onReset={reset} />}
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
            submitting={submitting}
            onSubmit={submitDecision}
          />
        )}

        {runId && status === "done" && run && <Result run={run} onReset={reset} />}
      </main>
    </div>
  );
}

/* ---------------------------------------------------------------- header */

function Header({ status, onReset }: { status?: string; onReset?: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <LoopMark />
          <div className="leading-none">
            <div className="text-[15px] font-semibold tracking-tight">Loopback</div>
            <div className="mt-0.5 text-[11px] text-muted">customer pain → GitLab, on the record</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {status && <StatusPill status={status} />}
          {onReset && (
            <button onClick={onReset} className="rounded-md border border-line px-3 py-1.5 text-xs text-muted transition hover:border-paper/30 hover:text-paper">
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
    <div className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-surface">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--color-amber)" strokeWidth="2.1" strokeLinecap="round">
        <path d="M4 9a5 5 0 0 1 5-5h6a5 5 0 0 1 0 10H7" />
        <path d="M9 16l-3 3 3 3" transform="translate(0 -6)" />
      </svg>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string; dot: string }> = {
    running: { label: "Analyzing", cls: "border-blue/40 text-blue", dot: "bg-blue blink" },
    awaiting_approval: { label: "Awaiting you", cls: "border-amber/50 text-amber", dot: "bg-amber blink" },
    creating: { label: "Creating issues", cls: "border-blue/40 text-blue", dot: "bg-blue blink" },
    done: { label: "Done", cls: "border-green/40 text-green", dot: "bg-green" },
    empty: { label: "No themes", cls: "border-line text-muted", dot: "bg-muted" },
    error: { label: "Error", cls: "border-red/40 text-red", dot: "bg-red" },
  };
  const s = map[status] ?? map.running;
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

/* ---------------------------------------------------------------- upload */

function Upload({ onFile, busy, error }: { onFile: (f: File | null) => void; busy: boolean; error: string | null }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="mx-auto max-w-2xl pt-10 text-center risein">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-amber">Voice of Customer → Engineering</p>
      <h1 className="mt-4 text-balance text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
        Stop letting customer pain rot in the support inbox.
      </h1>
      <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-muted">
        Drop in a batch of feedback. Loopback clusters the recurring pain, ranks it, and drafts
        well-scoped GitLab issues — then <span className="text-paper">stops and waits for your
        approval</span> before creating a single thing.
      </p>

      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); onFile(e.dataTransfer.files?.[0] ?? null); }}
        className={`mt-9 flex cursor-pointer flex-col items-center gap-3 rounded-2xl border border-dashed px-6 py-12 transition ${
          drag ? "border-amber bg-amber-d/40" : "border-line bg-surface hover:border-paper/25"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        <div className="grid h-12 w-12 place-items-center rounded-xl border border-line bg-surface2 text-amber">
          {busy ? <Spinner /> : <UploadIcon />}
        </div>
        <div className="text-sm font-medium">{busy ? "Starting the agent…" : "Drop a feedback CSV, or click to choose"}</div>
        <div className="font-mono text-[11px] text-muted">columns: id, text, channel, date</div>
      </label>

      {error && (
        <div className="mt-5 rounded-lg border border-red/40 bg-red-d/50 px-4 py-3 text-left text-sm text-red">{error}</div>
      )}

      <div className="mt-8 flex items-center justify-center gap-6 text-[11px] text-muted">
        <Stat n="1" label="Cluster & rank" />
        <Stat n="2" label="Draft issues" />
        <Stat n="3" label="You approve" />
        <Stat n="4" label="Create in GitLab" />
      </div>
    </div>
  );
}

function Stat({ n, label }: { n: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="grid h-5 w-5 place-items-center rounded-full border border-line font-mono text-[10px] text-amber">{n}</span>
      {label}
    </span>
  );
}

/* ---------------------------------------------------------------- review */

function Review({
  run,
  rejected,
  setRejected,
  submitting,
  onSubmit,
}: {
  run: RunState;
  rejected: Set<string>;
  setRejected: (s: Set<string>) => void;
  submitting: boolean;
  onSubmit: () => void;
}) {
  const atGate = run.status === "awaiting_approval";
  const creating = run.status === "creating";
  const drafts = run.drafts;
  const approvedCount = drafts.length - drafts.filter((d) => rejected.has(d.theme_id)).length;

  const toggle = (id: string) => {
    const next = new Set(rejected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setRejected(next);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="order-2 lg:order-1">
        {/* THE APPROVAL GATE — focal point */}
        {atGate ? (
          <div className="gate-pulse sticky top-[68px] z-20 mb-5 rounded-xl border border-amber bg-gradient-to-b from-amber-d/70 to-surface px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border border-amber/60 text-amber">⏸</span>
                <div>
                  <div className="text-sm font-semibold text-amber">The agent has paused for your approval</div>
                  <div className="mt-0.5 text-[13px] text-muted">
                    Nothing is created in GitLab until you decide. Reject any card below, then create the rest.
                  </div>
                </div>
              </div>
              <button
                onClick={onSubmit}
                disabled={submitting}
                className="rounded-lg bg-amber px-4 py-2.5 text-sm font-semibold text-ink transition hover:brightness-110 disabled:opacity-60"
              >
                {submitting ? "Creating…" : approvedCount > 0 ? `Approve & create ${approvedCount}` : "Reject all"}
              </button>
            </div>
          </div>
        ) : (
          <div className="mb-5 rounded-xl border border-line bg-surface px-5 py-4 text-sm text-muted">
            {creating ? (
              <span className="text-blue">Creating the approved issues in GitLab…</span>
            ) : (
              <span>The agent is analyzing the feedback — proposed issues will appear here.</span>
            )}
          </div>
        )}

        {drafts.length === 0 ? (
          <RunningSkeleton />
        ) : (
          <div className="space-y-4">
            {drafts.map((d, i) => (
              <IssueCard
                key={d.theme_id}
                draft={d}
                index={i}
                rejected={rejected.has(d.theme_id)}
                disabled={!atGate}
                onToggle={() => toggle(d.theme_id)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="order-1 lg:order-2">
        <StepLog steps={run.steps} live={!atGate} />
      </div>
    </div>
  );
}

function RunningSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="animate-pulse rounded-xl border border-line bg-surface p-5">
          <div className="h-4 w-2/3 rounded bg-surface2" />
          <div className="mt-3 h-3 w-full rounded bg-surface2" />
          <div className="mt-2 h-3 w-4/5 rounded bg-surface2" />
        </div>
      ))}
    </div>
  );
}

const PRIORITY: Record<string, string> = {
  critical: "border-red/50 text-red bg-red-d/40",
  high: "border-amber/50 text-amber bg-amber-d/40",
  medium: "border-blue/40 text-blue bg-blue/10",
  low: "border-line text-muted",
};

function IssueCard({
  draft,
  index,
  rejected,
  disabled,
  onToggle,
}: {
  draft: Draft;
  index: number;
  rejected: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <article
      className={`risein rounded-xl border bg-surface p-5 transition ${
        rejected ? "border-line opacity-55" : "border-line hover:border-paper/20"
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className={`mt-0.5 shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${PRIORITY[draft.priority] ?? PRIORITY.low}`}>
            {draft.priority}
          </span>
          <h3 className={`text-[15px] font-semibold leading-snug ${rejected ? "line-through decoration-muted/60" : ""}`}>
            {draft.title}
          </h3>
        </div>
        <ApproveToggle rejected={rejected} disabled={disabled} onToggle={onToggle} />
      </div>

      <p className="mt-3 text-[13.5px] leading-relaxed text-muted">{draft.body}</p>

      {draft.evidence_quotes.length > 0 && (
        <div className="mt-4 space-y-1.5 border-l-2 border-amber/40 pl-3">
          {draft.evidence_quotes.slice(0, 3).map((q, i) => (
            <p key={i} className="text-[12.5px] italic leading-snug text-paper/75">“{q}”</p>
          ))}
        </div>
      )}

      {draft.repro_steps.length > 0 && (
        <div className="mt-4">
          <Label>Repro</Label>
          <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-[13px] text-paper/85 marker:text-muted">
            {draft.repro_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      {draft.remediation && (
        <div className="mt-4">
          <Label>Suggested fix</Label>
          <p className="mt-1.5 text-[13px] leading-relaxed text-paper/85">{draft.remediation}</p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {draft.suggested_labels.map((l) => (
          <span key={l} className="rounded-full border border-line bg-surface2 px-2.5 py-0.5 font-mono text-[11px] text-paper/80">
            {l}
          </span>
        ))}
        {draft.related_iids.length > 0 && (
          <span className="ml-1 font-mono text-[11px] text-blue">↔ relates #{draft.related_iids.join(", #")}</span>
        )}
      </div>
    </article>
  );
}

function ApproveToggle({ rejected, disabled, onToggle }: { rejected: boolean; disabled: boolean; onToggle: () => void }) {
  if (disabled) return null;
  return (
    <button
      onClick={onToggle}
      className={`shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium transition ${
        rejected
          ? "border-line text-muted hover:text-paper"
          : "border-green/40 bg-green-d/40 text-green hover:brightness-110"
      }`}
    >
      {rejected ? "Rejected · undo" : "✓ Approved"}
    </button>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{children}</span>;
}

/* ---------------------------------------------------------------- step log */

function StepLog({ steps, live }: { steps: Step[]; live: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [steps.length]);

  return (
    <div className="sticky top-[68px] rounded-xl border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span className="flex gap-1.5">
          <Dot c="#ff5f57" /> <Dot c="#febc2e" /> <Dot c="#28c840" />
        </span>
        <span className="ml-1 font-mono text-[11px] text-muted">agent · step log</span>
        {live && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-blue blink" />}
      </div>
      <div className="scroll-slim max-h-[70vh] overflow-y-auto px-4 py-3 font-mono text-[11.5px] leading-relaxed">
        {steps.length === 0 && <div className="text-muted">waiting for the agent…</div>}
        {steps.map((s, i) => (
          <div key={i} className="mb-1.5 flex gap-2">
            <span className="shrink-0 text-amber/70">{s.author}</span>
            <span className="text-paper/80">{s.text}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}

function Dot({ c }: { c: string }) {
  return <span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />;
}

/* ---------------------------------------------------------------- result */

function Result({ run, onReset }: { run: RunState; onReset: () => void }) {
  const created: Created[] = run.created;
  const rejectedDrafts = run.drafts.filter((d) => run.rejected.includes(d.theme_id));

  return (
    <div className="mx-auto max-w-3xl risein">
      <div className="rounded-2xl border border-green/40 bg-green-d/30 px-6 py-7 text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-green/50 text-green">✓</div>
        <h2 className="mt-4 text-2xl font-semibold tracking-tight">
          {created.length} issue{created.length === 1 ? "" : "s"} created in GitLab
        </h2>
        <p className="mt-2 text-sm text-muted">
          The loop is closed — recurring customer pain is now tracked work, with labels and links.
        </p>
      </div>

      <div className="mt-6 space-y-2.5">
        {created.map((c) => (
          <a
            key={c.iid}
            href={c.url}
            target="_blank"
            rel="noreferrer"
            className="group flex items-center justify-between gap-4 rounded-xl border border-line bg-surface px-5 py-3.5 transition hover:border-green/40"
          >
            <div className="flex min-w-0 items-center gap-3">
              <span className="font-mono text-sm text-green">#{c.iid}</span>
              <div className="flex flex-wrap gap-1.5">
                {c.labels.map((l) => (
                  <span key={l} className="rounded-full border border-line bg-surface2 px-2 py-0.5 font-mono text-[10.5px] text-paper/75">
                    {l}
                  </span>
                ))}
              </div>
            </div>
            <span className="shrink-0 text-xs text-muted transition group-hover:text-green">open ↗</span>
          </a>
        ))}
      </div>

      {rejectedDrafts.length > 0 && (
        <div className="mt-6">
          <Label>Rejected — not created</Label>
          <div className="mt-2 space-y-1.5">
            {rejectedDrafts.map((d) => (
              <div key={d.theme_id} className="flex items-center gap-2 rounded-lg border border-line bg-surface/60 px-4 py-2.5 text-sm text-muted">
                <span className="text-red">✕</span>
                <span className="line-through decoration-muted/50">{d.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 text-center">
        <button onClick={onReset} className="rounded-lg border border-line px-5 py-2.5 text-sm transition hover:border-paper/30">
          Triage another batch
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- misc */

function Banner({ kind, title, body, onReset }: { kind: "error" | "empty"; title: string; body: string; onReset: () => void }) {
  const cls = kind === "error" ? "border-red/40 bg-red-d/40" : "border-line bg-surface";
  return (
    <div className={`mx-auto mt-10 max-w-xl rounded-2xl border ${cls} px-6 py-8 text-center risein`}>
      <div className="text-3xl">{kind === "error" ? "⚠️" : "🔍"}</div>
      <h2 className="mt-3 text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
      <button onClick={onReset} className="mt-6 rounded-lg border border-line px-5 py-2.5 text-sm transition hover:border-paper/30">
        Try another batch
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
