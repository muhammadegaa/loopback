// Typed client for the Loopback API. The browser only ever talks to this API —
// all GitLab and Gemini credentials live server-side.

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type RunStatus =
  | "running"
  | "awaiting_approval"
  | "creating"
  | "done"
  | "empty"
  | "error";

export type Step = { author: string; text: string; ts: number };

export type Signal = { id: string; text: string; channel: string; date: string };

export type Preview = { total: number; sample: Signal[] };

// triage totals from clustering: signals in, how many became themes, how many were noise.
// filtered_by_learning + filtered_signals fire when the "learns your no's" loop
// filters themes the user rejected on a prior run from the same source.
export type Triage = {
  total: number;
  themed: number;
  ignored: number;
  themes: number;
  filtered_by_learning?: number;
  filtered_signals?: number;
};

// PII redaction counts; visible in the trust strip and the agent step log
export type Redaction = { email: number; phone: number; url: number; signals_touched: number };

// run timing snapshots used for the "saved you ~Xh" framing and the decision log
export type Timings = {
  started_at: number | null;
  gate_at: number | null;
  decided_at: number | null;
  done_at: number | null;
};

export type Draft = {
  theme_id: string;
  title: string;
  body: string;
  repro_steps: string[];
  evidence_quotes: string[];
  suggested_labels: string[];
  priority: "critical" | "high" | "medium" | "low" | string;
  remediation: string;
  related_iids: (number | string)[];
  // ranking provenance (computed deterministically server-side), powers the "why this" line
  frequency: number;
  severity: number;
  score: number;
  rank: number;
  channels: string[];
  // confidence lane assigned by the Triage Router Agent:
  //   "high"            : top rank + score >= 60% of max, ready for one-click approve
  //   "needs_review"    : below the bar, flagged for PM judgment
  //   "extend_existing" : classifier found a strong open duplicate; agent will add a note
  //                       to that ticket instead of filing new
  lane?: "high" | "needs_review" | "extend_existing";
  // classifier-set: the existing-issue iid we'd extend, and a deterministic comment body
  // we'd post if approved. Both null unless the classifier found a strong duplicate.
  extend_target?: number | null;
  comment_body?: string | null;
  // classifier-set: a closed-issue iid this theme appears to be a regression of.
  // Orthogonal to lane — we still file a new ticket, but flag it as a regression.
  regression_of?: number | null;
  // classifier's one-line rationale for the extend_target / regression_of decision.
  classifier_reason?: string | null;
};

export type Created = {
  theme_id: string;
  iid: number;
  url: string;
  title: string;
  labels: string[];
  // true if the GitLab Writer Agent added a comment to an existing issue
  // instead of creating a new one.
  extended?: boolean;
};

export type RunState = {
  status: RunStatus;
  preview: Preview;
  triage: Triage;
  redaction: Redaction;
  steps: Step[];
  drafts: Draft[];
  created: Created[];
  approved: string[];
  rejected: string[];
  edited_ids: string[];
  timings: Timings;
  error: string | null;
};

export async function createRun(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/runs`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d.detail as string)
      .catch(() => "Upload failed.");
    throw new Error(detail);
  }
  const { run_id } = (await res.json()) as { run_id: string };
  return run_id;
}

export async function getRun(runId: string): Promise<RunState> {
  const res = await fetch(`${BASE}/api/runs/${runId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Lost contact with the run.");
  return (await res.json()) as RunState;
}

export type DraftEdit = {
  title?: string;
  body?: string;
  priority?: string;
  suggested_labels?: string[];
};

export async function postDecision(
  runId: string,
  approvedIds: string[],
  rejectedIds: string[],
  edits: Record<string, DraftEdit> = {},
  fileNewInsteadOfExtend: string[] = [],
): Promise<void> {
  const res = await fetch(`${BASE}/api/runs/${runId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approved_ids: approvedIds,
      rejected_ids: rejectedIds,
      edits,
      file_new_instead_of_extend: fileNewInsteadOfExtend,
    }),
  });
  if (!res.ok) throw new Error("Couldn't submit your decision.");
}
