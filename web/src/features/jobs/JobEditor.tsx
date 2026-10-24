import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { duration, ease, lintDelayMs } from "../../app/theme/motion";
import { ApiError } from "../../shared/api/client";
import { lintJob, useSaveJob } from "../../shared/api/queries";
import type { AggIssue, Job } from "../../shared/api/types";
import { useDebouncedValue } from "../../shared/hooks/useDebouncedValue";
import { aggRuleLabel, occupationLabel, t } from "../../shared/text/de";
import { Button } from "../../shared/ui/Button";
import { markIssues } from "./marks";
import s from "./jobs.module.css";

const LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2"];
const BLANK: Partial<Job> = { id: "", title: "", occupation: "koch", plz: "", radius_km: 30, shifts: [], employment: ["full_time"],
  start_by: "", must: {}, german_level: null, soft: {}, pay: "", text: "", open: true };

export function JobEditor({ job, onSaved }: { job?: Job; onSaved: (j: Job) => void }) {
  const [draft, setDraft] = useState<Partial<Job>>(() => ({ ...BLANK, ...(job ?? {}) }));
  const [override, setOverride] = useState("");
  const save = useSaveJob();
  const checked = useMemo(() => ({ title: draft.title, text: draft.text, german_level: draft.german_level }),
    [draft.title, draft.text, draft.german_level]);
  const forCheck = useDebouncedValue(checked, lintDelayMs);
  const [issues, setIssues] = useState<AggIssue[] | null>(job?.agg ?? null);
  const [checkError, setCheckError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    lintJob(forCheck).then((r) => { if (live) { setIssues(r); setCheckError(null); } })
      .catch((e: unknown) => { if (live) setCheckError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; };
  }, [forCheck]);

  const set = <K extends keyof Job>(k: K, v: Job[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const blocked = (issues ?? []).some((i) => i.severity === "block");
  const serverBlocked = save.error instanceof ApiError && save.error.status === 422 && blocked;

  return (
    <div className={s.editor}>
      <form className={s.form} onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ job: draft, override_reason: override || undefined }, { onSuccess: (j) => onSaved(j) });
      }}>
        <h1>{job ? job.title : t.jobs.new}</h1>
        <div className={s.grid2}>
          <Field label={t.jobs.fields.id}><input required value={draft.id} disabled={Boolean(job)} onChange={(e) => set("id", e.target.value)} /></Field>
          <Field label={t.jobs.fields.occupation}>
            <select value={draft.occupation} onChange={(e) => set("occupation", e.target.value)}>
              {Object.entries(occupationLabel).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
        </div>
        <Field label={t.jobs.fields.title}><input required value={draft.title} onChange={(e) => set("title", e.target.value)} /></Field>
        <div className={s.grid2}>
          <Field label={t.jobs.fields.plz}><input required inputMode="numeric" pattern="\d{5}" value={draft.plz} onChange={(e) => set("plz", e.target.value)} /></Field>
          <Field label={t.jobs.fields.radius}><input type="number" min={1} value={draft.radius_km} onChange={(e) => set("radius_km", Number(e.target.value))} /></Field>
          <Field label={t.jobs.fields.startBy}><input required type="date" value={draft.start_by} onChange={(e) => set("start_by", e.target.value)} /></Field>
          <Field label={t.jobs.fields.pay}><input value={draft.pay} onChange={(e) => set("pay", e.target.value)} /></Field>
        </div>
        <div className={s.grid2}>
          <Field label={t.jobs.fields.german}>
            <select value={draft.german_level?.min ?? ""} onChange={(e) => set("german_level", e.target.value ? { min: e.target.value, justification: draft.german_level?.justification ?? "" } : null)}>
              {LEVELS.map((l) => <option key={l} value={l}>{l || t.jobs.none}</option>)}
            </select>
          </Field>
          {draft.german_level && (
            <Field label={t.jobs.fields.justification}>
              <input value={draft.german_level.justification ?? ""} onChange={(e) => set("german_level", { min: draft.german_level!.min, justification: e.target.value })} />
            </Field>
          )}
        </div>
        <Field label={t.jobs.fields.text}><textarea value={draft.text} onChange={(e) => set("text", e.target.value)} /></Field>
        {serverBlocked && (
          <>
            <p className={s.blockNote} role="alert">{t.jobs.blocked}</p>
            <Field label={t.jobs.override}><input value={override} onChange={(e) => setOverride(e.target.value)} /></Field>
          </>
        )}
        {save.isError && !serverBlocked && <p className={s.blockNote} role="alert">{save.error.message}</p>}
        <div className={s.actions}>
          <Button type="submit" disabled={save.isPending}>{t.jobs.save}</Button>
          {save.isSuccess && <span className={s.saved} role="status">{t.jobs.saved}</span>}
        </div>
      </form>
      <AggPanel title={draft.title ?? ""} text={draft.text ?? ""} issues={issues} error={checkError} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className={s.field}><span>{label}</span>{children}</label>;
}

function AggPanel({ title, text, issues, error }: { title: string; text: string; issues: AggIssue[] | null; error: string | null }) {
  const reduce = useReducedMotion();
  const pieces = useMemo(() => markIssues(text, issues ?? []), [text, issues]);
  return (
    <aside className={s.check} aria-labelledby="agg-h" aria-live="polite">
      <h2 id="agg-h">{t.jobs.check}</h2>
      {error && <p className={s.blockNote}>{error}</p>}
      {!error && issues === null && <p className={s.status}>{t.jobs.checking}</p>}
      {!error && issues?.length === 0 && <p className={s.status}>{t.jobs.clean}</p>}
      <ul className={s.issues}>
        <AnimatePresence initial={false}>
          {(issues ?? []).map((i) => (
            <motion.li key={i.rule} className={`${s.issue} ${i.severity === "block" ? s.issueBlock : ""}`}
              initial={reduce ? false : { opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: duration.quick, ease: ease.out }} layout={!reduce}>
              <span className={s.issueRule}>{aggRuleLabel[i.rule] ?? i.rule}{i.severity === "block" ? " · blockiert" : ""}</span>
              <span className={s.issueQuote}>„{i.quote}“</span>
              <span className={s.issueAdvice}>{i.advice}</span>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
      {text && (
        <div className={s.preview} aria-label="Vorschau mit Markierungen">
          <p className={s.previewTitle}>{title}</p>
          {pieces.map((p, k) => p.issue
            ? <mark key={k} className={p.issue.severity === "block" ? s.bad : s.warn} title={aggRuleLabel[p.issue.rule]}>{p.text}</mark>
            : <span key={k}>{p.text}</span>)}
        </div>
      )}
    </aside>
  );
}
