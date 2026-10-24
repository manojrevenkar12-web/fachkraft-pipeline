import type { AggIssue } from "../../shared/api/types";

export interface Piece { text: string; issue?: AggIssue }

/** Cut a text into plain pieces and the quoted AGG problems, first occurrence of each quote. */
export function markIssues(text: string, issues: AggIssue[]): Piece[] {
  const low = text.toLowerCase();
  const spans: { start: number; end: number; issue: AggIssue }[] = [];
  for (const issue of issues) {
    if (!issue.quote) continue;
    const at = low.indexOf(issue.quote.toLowerCase());
    if (at < 0) continue;
    const end = at + issue.quote.length;
    if (spans.some((sp) => at < sp.end && sp.start < end)) continue;
    spans.push({ start: at, end, issue });
  }
  spans.sort((a, b) => a.start - b.start);
  const out: Piece[] = [];
  let pos = 0;
  for (const sp of spans) {
    if (sp.start > pos) out.push({ text: text.slice(pos, sp.start) });
    out.push({ text: text.slice(sp.start, sp.end), issue: sp.issue });
    pos = sp.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos) });
  return out;
}
