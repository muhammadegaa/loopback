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

// triage totals from clustering: signals in, how many became themes, how many were noise
export type Triage = { total: number; themed: number; ignored: number; themes: number };

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
};

export type Created = {
  theme_id: string;
  iid: number;
  url: string;
  title: string;
  labels: string[];
};

export type RunState = {
  status: RunStatus;
  preview: Preview;
  triage: Triage;
  steps: Step[];
  drafts: Draft[];
  created: Created[];
  approved: string[];
  rejected: string[];
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
): Promise<void> {
  const res = await fetch(`${BASE}/api/runs/${runId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_ids: approvedIds, rejected_ids: rejectedIds, edits }),
  });
  if (!res.ok) throw new Error("Couldn't submit your decision.");
}
