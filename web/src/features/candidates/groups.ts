import type { CandidateRow, Stage } from "../../shared/api/types";

export type GroupId = "ready" | "person" | "talking" | "pool" | "closed";
export const GROUP_ORDER: GroupId[] = ["ready", "person", "talking", "pool", "closed"];

const STAGE_GROUP: Record<Stage, GroupId> = {
  handed_over: "ready", human: "person", pooled: "pool", declined: "closed", closed: "closed", deleted: "closed",
  new: "talking", awaiting_consent: "talking", collecting: "talking", confirming: "talking", fixing: "talking",
  handover_details: "talking", pool_question: "talking",
};

export function groupOf(stage: Stage): GroupId {
  return STAGE_GROUP[stage] ?? "talking";
}

/** Groups in working order; within a group the most recent activity first. */
export function groupCandidates(rows: CandidateRow[], query = ""): { id: GroupId; rows: CandidateRow[] }[] {
  const q = query.trim().toLowerCase();
  const hit = (r: CandidateRow) =>
    !q || r.name.toLowerCase().includes(q) || (r.place ?? "").toLowerCase().includes(q) || r.occupation.some((o) => o.includes(q));
  return GROUP_ORDER.map((id) => ({
    id,
    rows: rows.filter((r) => groupOf(r.stage) === id && hit(r)).sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
  })).filter((g) => g.rows.length > 0);
}
