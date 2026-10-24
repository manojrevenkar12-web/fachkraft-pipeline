import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { AggIssue, CandidateDetail, CandidateRow, Job, Metrics, SandboxLine } from "./types";

export const keys = {
  candidates: ["candidates"] as const,
  candidate: (id: string) => ["candidate", id] as const,
  jobs: ["jobs"] as const,
  metrics: ["metrics"] as const,
  sandbox: (phone: string) => ["sandbox", phone] as const,
};

export const useCandidates = () => useQuery({ queryKey: keys.candidates, queryFn: () => api<CandidateRow[]>("/api/candidates") });
export const useCandidate = (id: string | undefined) =>
  useQuery({ queryKey: keys.candidate(id ?? ""), queryFn: () => api<CandidateDetail>(`/api/candidates/${id}`), enabled: Boolean(id) });
export const useJobs = () => useQuery({ queryKey: keys.jobs, queryFn: () => api<Job[]>("/api/jobs") });
export const useMetrics = () => useQuery({ queryKey: keys.metrics, queryFn: () => api<Metrics>("/api/metrics") });
export const useSandbox = (phone: string) =>
  useQuery({ queryKey: keys.sandbox(phone), queryFn: () => api<SandboxLine[]>(`/api/sandbox/${phone}/messages`) });

export const lintJob = (job: Partial<Job>) => api<AggIssue[]>("/api/jobs/lint", { method: "POST", json: job });

export function useSaveJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { job: Partial<Job>; override_reason?: string }) => api<Job>("/api/jobs", { method: "POST", json: v }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.jobs }),
  });
}

export function useSandboxSend(phone: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { text?: string; button_id?: string; name?: string }) =>
      api<{ transcript: SandboxLine[] }>(`/api/sandbox/${phone}/messages`, { method: "POST", json: v }),
    onSuccess: (r) => qc.setQueryData(keys.sandbox(phone), r.transcript),
  });
}

export function useReply(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => api<{ queued: boolean }>(`/api/candidates/${id}/messages`, { method: "POST", json: { text } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.candidate(id) }),
  });
}
