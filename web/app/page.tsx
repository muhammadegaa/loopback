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
      setRun({ status: "running", preview: { total: 0, sample: [] }, steps: [], drafts: [], created: [], approved: [], rejected: [], error: null });
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
          <Review run={run} rejected={rejected} setRejected={setRejected} submitting={submitting} onSubmit={submitDecision} />
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

function Upload({ onFile, busy, error }: { onFile: (f: File | null) => void; busy: boolean; error: string | null }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="mx-auto max-w-2xl pt-12 text-center risein">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1 text-[11px] font-medium text-muted shadow-card">
        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
        Voice of Customer → Engineering
      </span>
      <h1 className="mt-5 text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-5xl">
        Stop letting customer pain rot in the support inbox.
      </h1>
      <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-muted">
        Drop in a batch of customer feedback. Loopback clusters the recurring pain, ranks it, and
        drafts well-scoped GitLab issues, then{" "}
        <span className="font-medium text-ink">stops and waits for your approval</span> before
        creating a single thing.
      </p>

      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); onFile(e.dataTransfer.files?.[0] ?? null); }}
        className={`mt-9 flex cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 transition ${
          drag ? "border-primary bg-primary-bg" : "border-border-strong bg-surface hover:border-primary/50 hover:bg-primary-bg/40"
        }`}
      >
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
        <div className="grid h-12 w-12 place-items-center rounded-xl bg-primary-bg text-primary">
          {busy ? <Spinner /> : <UploadIcon />}
        </div>
        <div className="text-sm font-semibold text-ink">{busy ? "Starting the agent…" : "Drop a feedback CSV, or click to choose"}</div>
        <div className="rounded-md bg-subtle px-2 py-1 font-mono text-[11px] text-muted">columns: id, text, channel, date</div>
      </label>

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

/* =================================================================== review */

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
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="order-2 lg:order-1">
        {atGate ? (
          <GateBanner approvedCount={approvedCount} submitting={submitting} onSubmit={onSubmit} />
        ) : (
          <div className="mb-5 flex items-center gap-2.5 rounded-xl border border-border bg-surface px-5 py-3.5 text-sm shadow-card">
            <span className={`h-1.5 w-1.5 rounded-full ${creating ? "bg-primary" : "bg-primary"} blink`} />
            <span className="text-muted">
              {creating
                ? "Creating the approved issues in GitLab…"
                : "The agents are reading and clustering the signals into themes. Proposed issues will appear here for your approval."}
            </span>
          </div>
        )}

        {drafts.length === 0 ? (
          <SignalsPreview preview={run.preview} />
        ) : (
          <div className="space-y-4">
            {drafts.map((d, i) => (
              <IssueCard key={d.theme_id} draft={d} index={i} rejected={rejected.has(d.theme_id)} disabled={!atGate} onToggle={() => toggle(d.theme_id)} />
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

function GateBanner({ approvedCount, submitting, onSubmit }: { approvedCount: number; submitting: boolean; onSubmit: () => void }) {
  return (
    <div className="gate-pulse sticky top-[64px] z-20 mb-5 rounded-xl border border-amber-border bg-amber-bg px-5 py-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full border border-amber-border bg-surface text-amber">⏸</span>
          <div>
            <div className="text-sm font-semibold text-amber">The agent has paused for your approval</div>
            <div className="mt-0.5 text-[13px] text-muted">Nothing is created in GitLab until you decide. Reject any card, then create the rest.</div>
          </div>
        </div>
        <button
          onClick={onSubmit}
          disabled={submitting}
          className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-pop transition hover:bg-primary-strong disabled:opacity-60"
        >
          {submitting ? "Creating…" : approvedCount > 0 ? `Approve & create ${approvedCount}` : "Reject all"}
        </button>
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
  const p = PRIORITY[draft.priority] ?? PRIORITY.low;
  return (
    <article
      className={`risein rounded-xl border bg-surface p-5 shadow-card transition ${
        rejected ? "border-border opacity-60" : "border-border hover:border-border-strong hover:shadow-pop"
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className={`mt-0.5 shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${p.cls}`}>{p.label}</span>
          <h3 className={`text-[15px] font-semibold leading-snug text-ink ${rejected ? "line-through decoration-faint" : ""}`}>{draft.title}</h3>
        </div>
        <ApproveToggle rejected={rejected} disabled={disabled} onToggle={onToggle} />
      </div>

      <p className="mt-3 text-[13.5px] leading-relaxed text-muted">{draft.body}</p>

      {draft.evidence_quotes.length > 0 && (
        <div className="mt-4 space-y-1.5 rounded-lg border-l-2 border-primary/40 bg-primary-bg/40 py-2 pl-3 pr-2">
          {draft.evidence_quotes.slice(0, 3).map((q, i) => (
            <p key={i} className="text-[12.5px] italic leading-snug text-ink/75">“{q}”</p>
          ))}
        </div>
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

      <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-border pt-3.5">
        {draft.suggested_labels.map((l) => (
          <span key={l} className="rounded-full border border-border bg-subtle px-2.5 py-0.5 font-mono text-[11px] text-muted">{l}</span>
        ))}
        {draft.related_iids.length > 0 && (
          <span className="ml-1 inline-flex items-center gap-1 font-mono text-[11px] text-primary">↔ relates #{draft.related_iids.join(", #")}</span>
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

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">{children}</span>;
}

/* ================================================================= step log */

function StepLog({ steps, live }: { steps: Step[]; live: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [steps.length]);

  return (
    <div className="sticky top-[64px] overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <div className="flex items-center gap-2 border-b border-border bg-subtle/60 px-4 py-2.5">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted">
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M7 9l3 3-3 3M13 15h4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-[11.5px] font-semibold text-ink">Agent activity</span>
        {live && <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-primary"><span className="h-1.5 w-1.5 rounded-full bg-primary blink" />live</span>}
      </div>
      <div className="scroll-slim max-h-[70vh] overflow-y-auto px-4 py-3">
        {steps.length === 0 && <div className="py-2 text-[12px] text-faint">Waiting for the agent…</div>}
        <ol className="relative space-y-2.5 border-l border-border pl-4">
          {steps.map((s, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full border-2 border-surface bg-primary" />
              <div className="font-mono text-[10px] uppercase tracking-wide text-faint">{s.author}</div>
              <div className="mt-0.5 text-[12px] leading-snug text-ink/85">{s.text}</div>
            </li>
          ))}
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

  return (
    <div className="mx-auto max-w-3xl risein">
      <div className="overflow-hidden rounded-2xl border border-green-border bg-surface shadow-card">
        <div className="border-b border-green-border bg-green-bg px-6 py-7 text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-green text-lg text-white">✓</div>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-ink">
            {created.length} issue{created.length === 1 ? "" : "s"} created in GitLab
          </h2>
          <p className="mt-2 text-sm text-muted">The loop is closed. Recurring customer pain is now tracked work, with labels and links.</p>
        </div>

        <div className="divide-y divide-border">
          {created.map((c) => (
            <a
              key={c.iid}
              href={c.url}
              target="_blank"
              rel="noreferrer"
              className="group flex items-center justify-between gap-4 px-5 py-3.5 transition hover:bg-subtle"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="font-mono text-sm font-semibold text-green">#{c.iid}</span>
                <div className="flex flex-wrap gap-1.5">
                  {c.labels.map((l) => (
                    <span key={l} className="rounded-full border border-border bg-subtle px-2 py-0.5 font-mono text-[10.5px] text-muted">{l}</span>
                  ))}
                </div>
              </div>
              <span className="shrink-0 text-xs font-medium text-muted transition group-hover:text-primary">open ↗</span>
            </a>
          ))}
        </div>
      </div>

      {rejectedDrafts.length > 0 && (
        <div className="mt-6">
          <SectionLabel>Rejected (not created)</SectionLabel>
          <div className="mt-2 space-y-1.5">
            {rejectedDrafts.map((d) => (
              <div key={d.theme_id} className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-muted shadow-card">
                <span className="text-red">✕</span>
                <span className="line-through decoration-faint">{d.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 text-center">
        <button onClick={onReset} className="rounded-lg border border-border bg-surface px-5 py-2.5 text-sm font-medium text-ink shadow-card transition hover:border-border-strong">
          Triage another batch
        </button>
      </div>
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
