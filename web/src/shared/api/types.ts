/** Shapes returned by the fachkraft-pipeline API (src/fkp/api.py). */

export type Verdict = "fit" | "near" | "unknown" | "no";
export type Stage =
  | "new" | "awaiting_consent" | "declined" | "collecting" | "confirming" | "fixing" | "handover_details"
  | "pool_question" | "handed_over" | "pooled" | "human" | "deleted" | "closed";

export interface CandidateRow {
  id: string;
  channel: string;
  stage: Stage;
  lang: string;
  job_id: string | null;
  name: string;
  occupation: string[];
  place: string | null;
  updated_at: string;
  created_at: string;
  matches: { job_id: string; verdict: Verdict }[];
  fields: number;
}

export interface FieldValue {
  value: unknown;
  evidence: string;
  message_id: string;
  source: string;
  confidence: number;
  at: string;
}

export interface Check { name: string; status: "pass" | "fail" | "unknown" | "fixable"; detail: string }
export interface MatchResult { job_id: string; verdict: Verdict; score: number; distance_km: number | null; checks: Check[] }

export interface Message {
  direction: "in" | "out";
  kind: string;
  channel_id: string | null;
  body: string;
  purpose: string | null;
  status: string | null;
  category: string | null;
  cost: number;
  at: string;
  redacted: boolean;
}

export interface CandidateDetail extends Omit<CandidateRow, "matches"> {
  phone: string;
  consent_at: string | null;
  profile: Record<string, FieldValue>;
  matches: MatchResult[];
  skipped: string[];
  asked: string | null;
  messages: Message[];
  events: { type: string; data: Record<string, unknown>; at: string }[];
}

export interface AggIssue { rule: string; severity: "block" | "warn"; quote: string; advice: string }

export interface Job {
  id: string;
  title: string;
  occupation: string;
  plz: string;
  place: string;
  radius_km: number;
  shifts: string[];
  employment: string[];
  start_by: string;
  must: { licences?: string[]; recognition?: boolean };
  german_level: { min: string; justification?: string } | null;
  soft: Record<string, unknown>;
  pay: string;
  text: string;
  open: boolean;
  agg?: AggIssue[];
}

export interface Metrics {
  funnel: Record<"started" | "consented" | "confirmed" | "handed_over" | "pooled" | "human" | "declined" | "deleted", number>;
  stages: Record<string, number>;
  languages: Record<string, number>;
  minutes_to_confirmed_median: number | null;
  messages: { category: string; count: number; amount: number }[];
  currency: string;
  reminders: number;
  window_closed: number;
}

export interface SandboxLine {
  direction: "in" | "out";
  kind: string;
  body: string;
  purpose: string | null;
  at: string;
  buttons: { id: string; title: string }[];
}
