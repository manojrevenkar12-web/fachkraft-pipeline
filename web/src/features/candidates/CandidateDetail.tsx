import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../shared/api/client";
import { useCandidate, useJobs, useReply } from "../../shared/api/queries";
import type { CandidateDetail as Detail, Check } from "../../shared/api/types";
import { checkDetail, checkLabel, fieldLabel, formatValue, languageLabel, occupationLabel, stageLabel, t } from "../../shared/text/de";
import { Button } from "../../shared/ui/Button";
import { Skeleton } from "../../shared/ui/Skeleton";
import { EmptyState, ErrorState } from "../../shared/ui/States";
import { Lang, Verdict } from "../../shared/ui/Verdict";
import { locate } from "./evidence";
import { Transcript } from "./Transcript";
import s from "./candidates.module.css";

const ORDER = ["occupation", "location", "qualification", "recognition", "licences", "start_date", "shifts", "german_level",
  "experience_years", "employment", "commute_km", "full_name", "email"];
const ICON: Record<Check["status"], string> = { pass: "✓", fail: "✕", fixable: "~", unknown: "?" };

export function CandidateDetail({ id }: { id: string }) {
  const q = useCandidate(id);
  if (q.isPending) return <DetailSkeleton />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return <Loaded c={q.data} />;
}

function Loaded({ c }: { c: Detail }) {
  const [field, setField] = useState<string | null>(null);
  const jobs = useJobs();
  const titles = useMemo(() => Object.fromEntries((jobs.data ?? []).map((j) => [j.id, j.title])), [jobs.data]);
  const fields = ORDER.filter((f) => f in c.profile);
  const selected = field ? c.profile[field] : undefined;
  const span = selected ? locate(c.messages, selected) : null;
  const handed = c.matches.filter((m) => m.verdict !== "no").slice(0, 3);

  return (
    <article className={s.detail} aria-labelledby="cand-name">
      <header className={s.head}>
        <Link to="/candidates" className={s.back}>{t.candidates.back}</Link>
        <h1 id="cand-name">{c.name || "Ohne Namen"}</h1>
        <div className={s.meta}>
          <span>{c.occupation.map((o) => occupationLabel[o] ?? o).join(", ") || "Beruf noch offen"}</span>
          {c.place && <span>{c.place}</span>}
          <span><Lang code={c.lang} /> {languageLabel[c.lang] ?? c.lang}</span>
          <span>{stageLabel[c.stage] ?? c.stage}</span>
          <span>{c.consent_at ? `${t.candidates.consent} ${new Date(c.consent_at).toLocaleDateString("de-DE")}` : t.candidates.noConsent}</span>
        </div>
      </header>
      <div className={s.body}>
        <div className={s.factsCol}>
          <section className={s.section} aria-labelledby="facts-h">
            <h2 id="facts-h">{t.candidates.facts}</h2>
            {fields.length === 0 ? <p className={s.hint}>{t.candidates.noFacts}</p> : <p className={s.hint}>{t.candidates.factsHint}</p>}
            <ul className={s.facts}>
              {fields.map((f) => {
                const v = c.profile[f]!;
                return (
                  <li key={f}>
                    <button type="button" className={`${s.fact} ${field === f ? s.factOn : ""}`} aria-pressed={field === f}
                      onClick={() => setField(field === f ? null : f)}>
                      <span className={s.factLabel}>{fieldLabel[f] ?? f}</span>
                      <span className={s.factValue}>
                        {formatValue(f, v.value)}
                        <span className={s.src} dir="auto">„{v.evidence}“ · {t.candidates.source[v.source as "rules"] ?? v.source}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
              {c.skipped.map((f) => (
                <li key={f} className={`${s.fact} ${s.factMissing}`}>
                  <span className={s.factLabel}>{fieldLabel[f] ?? f}</span><span className={s.factValue}>{t.candidates.skipped}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className={s.section} aria-labelledby="matches-h">
            <h2 id="matches-h">{t.candidates.matches}</h2>
            {handed.length === 0 && <p className={s.hint}>{t.candidates.noMatches}</p>}
            {handed.map((m) => (
              <div key={m.job_id} className={s.match}>
                <div className={s.matchHead}>
                  <span className={s.jobTitle}>{titles[m.job_id] ?? m.job_id}</span>
                  <Verdict verdict={m.verdict} />
                </div>
                <ul className={s.checks}>
                  {m.checks.map((ch) => (
                    <li key={ch.name} className={s.check}>
                      <span className={`${s.checkIcon} ${ch.status === "unknown" ? s.unknownCheck : s[ch.status]}`} aria-label={ch.status}>{ICON[ch.status]}</span>
                      <span>{checkLabel[ch.name] ?? ch.name}</span>
                      <span>{checkDetail(ch.detail)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        </div>
        <section className={s.chatCol} aria-labelledby="chat-h">
          <div className={s.chatHead}><h2 id="chat-h">{t.candidates.chat}</h2></div>
          {c.messages.length ? <Transcript messages={c.messages} span={span} /> : <EmptyState title="Keine Nachrichten" />}
          <ReplyBox id={c.id} />
        </section>
      </div>
    </article>
  );
}

function ReplyBox({ id }: { id: string }) {
  const [text, setText] = useState("");
  const reply = useReply(id);
  const closed = reply.error instanceof ApiError && reply.error.status === 409;
  return (
    <form className={s.reply} onSubmit={(e) => { e.preventDefault(); if (text.trim()) reply.mutate(text, { onSuccess: () => setText("") }); }}>
      <label className="visually-hidden" htmlFor={`reply-${id}`}>{t.candidates.reply}</label>
      <textarea id={`reply-${id}`} rows={2} value={text} placeholder={t.candidates.reply} onChange={(e) => setText(e.target.value)} />
      <Button type="submit" disabled={!text.trim() || reply.isPending}>{t.candidates.send}</Button>
      {reply.isSuccess && <p className={s.replyNote} role="status">{t.candidates.sent}</p>}
      {closed && <p className={s.replyError} role="alert">{t.candidates.windowClosed}</p>}
      {reply.isError && !closed && <p className={s.replyError} role="alert">{reply.error.message}</p>}
    </form>
  );
}

function DetailSkeleton() {
  return (
    <div className={s.detail} aria-busy="true" aria-label="Lädt">
      <div className={s.head}><Skeleton height="2.2rem" width="40%" /><Skeleton width="70%" /></div>
      <div className={s.body}>
        <div className={s.factsCol}><Skeleton lines={8} height="1.6rem" width={["90%", "75%", "85%"]} /></div>
        <div className={s.chat}><Skeleton lines={6} height="2.6rem" width={["60%", "45%", "70%"]} /></div>
      </div>
    </div>
  );
}
