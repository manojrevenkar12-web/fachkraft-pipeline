import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { CandidateRow } from "../../shared/api/types";
import { maxStagger, reveal } from "../../app/theme/motion";
import { groupLabel, occupationLabel, t } from "../../shared/text/de";
import { Skeleton } from "../../shared/ui/Skeleton";
import { EmptyState, ErrorState } from "../../shared/ui/States";
import { Lang, Verdict } from "../../shared/ui/Verdict";
import { Button } from "../../shared/ui/Button";
import { groupCandidates } from "./groups";
import s from "./candidates.module.css";

export function relativeTime(iso: string, now = Date.now()): string {
  const min = Math.round((now - new Date(iso).getTime()) / 60000);
  if (min < 1) return "gerade eben";
  if (min < 60) return `vor ${min} Min.`;
  const h = Math.round(min / 60);
  if (h < 24) return `vor ${h} Std.`;
  const d = Math.round(h / 24);
  return d === 1 ? "gestern" : `vor ${d} Tagen`;
}

interface Props {
  rows: CandidateRow[] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  selected?: string;
  onSandbox: () => void;
}

export function CandidateList({ rows, loading, error, onRetry, selected, onSandbox }: Props) {
  const [query, setQuery] = useState("");
  const groups = useMemo(() => groupCandidates(rows ?? [], query), [rows, query]);
  const reduce = useReducedMotion();
  let order = 0;

  return (
    <aside className={s.listCol} aria-label={t.candidates.title}>
      <label className={s.search}>
        <span className="visually-hidden">{t.candidates.search}</span>
        <input type="search" placeholder={t.candidates.search} value={query} onChange={(e) => setQuery(e.target.value)} disabled={!rows?.length} />
      </label>
      {loading && (
        <div aria-busy="true" aria-label="Lädt">
          {Array.from({ length: 7 }, (_, i) => (
            <div key={i} className={s.skeletonRow}><Skeleton lines={2} width={["60%", "85%"]} /></div>
          ))}
        </div>
      )}
      {!loading && error != null && <ErrorState error={error} onRetry={onRetry} />}
      {!loading && !error && rows?.length === 0 && (
        <EmptyState title={t.candidates.emptyTitle} body={t.candidates.emptyBody}
          action={<Button tone="quiet" onClick={onSandbox}>{t.candidates.emptyAction}</Button>} />
      )}
      {!loading && !error && !!rows?.length && groups.length === 0 && <EmptyState title={t.candidates.noResults} />}
      <div className={s.groups}>
        {groups.map((g) => (
          <section key={g.id} className={`${s.group} ${g.id === "ready" ? s.groupReady : ""}`} aria-label={groupLabel[g.id]}>
            <h2>{groupLabel[g.id]} <span className={s.count}>{g.rows.length}</span></h2>
            <ul className={s.rows}>
              {g.rows.map((r) => (
                <motion.li key={r.id} variants={reduce ? undefined : reveal} initial="hidden" animate="shown" custom={Math.min(order++, maxStagger)}>
                  <Link to={`/candidates/${r.id}`} className={`${s.row} ${r.id === selected ? s.rowActive : ""}`}
                    aria-current={r.id === selected ? "page" : undefined}>
                    <span className={s.name}>{r.name || "Ohne Namen"}</span>
                    <span className={s.when}>{relativeTime(r.updated_at)}</span>
                    <span className={s.sub}>
                      <span>{r.occupation.map((o) => occupationLabel[o] ?? o).join(", ") || "Beruf noch offen"}</span>
                      {r.place && <span>{r.place}</span>}
                      <Lang code={r.lang} />
                      {r.matches.map((m) => <Verdict key={m.job_id} verdict={m.verdict} label={m.job_id} />)}
                    </span>
                  </Link>
                </motion.li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </aside>
  );
}
