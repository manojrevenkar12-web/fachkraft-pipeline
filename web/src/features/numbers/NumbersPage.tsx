import { motion, useReducedMotion } from "framer-motion";
import { duration, ease, stagger } from "../../app/theme/motion";
import { useMetrics } from "../../shared/api/queries";
import type { Metrics } from "../../shared/api/types";
import { languageLabel, t } from "../../shared/text/de";
import { Skeleton } from "../../shared/ui/Skeleton";
import { EmptyState, ErrorState } from "../../shared/ui/States";
import s from "./numbers.module.css";

const STEPS = ["started", "consented", "confirmed", "handed_over"] as const;
const usd = new Intl.NumberFormat("de-DE", { style: "currency", currency: "USD" });

export function NumbersPage() {
  const m = useMetrics();
  return (
    <div className={s.page}>
      <h1>{t.numbers.title}</h1>
      {m.isPending && <div aria-busy="true"><Skeleton lines={4} height="1.6rem" width={["90%", "70%", "50%", "30%"]} /></div>}
      {m.isError && <ErrorState error={m.error} onRetry={() => m.refetch()} />}
      {m.data && (m.data.funnel.started === 0
        ? <EmptyState title={t.numbers.emptyTitle} body={t.numbers.emptyBody} />
        : <Loaded m={m.data} />)}
    </div>
  );
}

function Loaded({ m }: { m: Metrics }) {
  const reduce = useReducedMotion();
  const top = Math.max(1, m.funnel.started);
  const cost = m.messages.reduce((a, b) => a + b.usd, 0);
  const langs = Object.entries(m.languages).sort((a, b) => b[1] - a[1]);
  return (
    <>
      <section className={s.section} aria-labelledby="funnel-h">
        <h2 id="funnel-h">{t.numbers.funnel}</h2>
        <div className={s.funnel}>
          {STEPS.map((k, i) => (
            <div key={k} className={s.step}>
              <span className={s.stepLabel}>{t.numbers.funnelSteps[k]}</span>
              <span className={s.track} role="img" aria-label={`${t.numbers.funnelSteps[k]}: ${m.funnel[k]}`}>
                <motion.span className={`${s.bar} ${i === STEPS.length - 1 ? s.barLast : ""}`} style={{ display: "block", width: `${(100 * m.funnel[k]) / top}%` }}
                  initial={reduce ? false : { scaleX: 0 }} animate={{ scaleX: 1 }}
                  transition={{ duration: duration.slow, ease: ease.out, delay: i * stagger * 3 }} />
              </span>
              <span className={s.num}>{m.funnel[k]}</span>
            </div>
          ))}
        </div>
      </section>
      <div className={s.figures}>
        <Figure value={m.minutes_to_confirmed_median === null ? "–" : `${Math.round(m.minutes_to_confirmed_median)}`} label={`${t.numbers.median} (${t.numbers.minutes})`} />
        <Figure value={usd.format(cost)} label={t.numbers.cost} />
        <Figure value={String(m.reminders)} label={t.numbers.reminders} />
        <Figure value={String(m.window_closed)} label={t.numbers.windowClosed} />
      </div>
      <div className={s.two}>
        <section className={s.section} aria-labelledby="lang-h">
          <h2 id="lang-h">{t.numbers.languages}</h2>
          <table className={s.table}>
            <tbody>{langs.map(([k, v]) => <tr key={k}><td>{languageLabel[k] ?? k}</td><td>{v}</td></tr>)}</tbody>
          </table>
        </section>
        <section className={s.section} aria-labelledby="side-h">
          <h2 id="side-h">{t.numbers.side}</h2>
          <table className={s.table}>
            <tbody>
              <tr><td>{t.numbers.pooled}</td><td>{m.funnel.pooled}</td></tr>
              <tr><td>{t.numbers.human}</td><td>{m.funnel.human}</td></tr>
              <tr><td>{t.numbers.declined}</td><td>{m.funnel.declined}</td></tr>
              <tr><td>{t.numbers.deleted}</td><td>{m.funnel.deleted}</td></tr>
            </tbody>
          </table>
        </section>
      </div>
    </>
  );
}

function Figure({ value, label }: { value: string; label: string }) {
  return <div className={s.figure}><span className={s.figureValue}>{value}</span><span className={s.figureLabel}>{label}</span></div>;
}
