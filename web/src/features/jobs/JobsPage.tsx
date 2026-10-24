import { useNavigate, useParams, Link } from "react-router-dom";
import { useJobs } from "../../shared/api/queries";
import type { Job } from "../../shared/api/types";
import { occupationLabel, t } from "../../shared/text/de";
import { Button } from "../../shared/ui/Button";
import { Skeleton } from "../../shared/ui/Skeleton";
import { EmptyState, ErrorState } from "../../shared/ui/States";
import { JobEditor } from "./JobEditor";
import s from "./jobs.module.css";

export const NEW_ID = "neu";

export function JobsPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const jobs = useJobs();
  const job = id && id !== NEW_ID ? jobs.data?.find((j) => j.id === id) : undefined;

  return (
    <div className={`${s.page} ${id ? s.hasSelection : s.noSelection}`}>
      <aside className={s.listCol} aria-label={t.jobs.title}>
        <div className={s.listHead}>
          <h1>{t.jobs.title}</h1>
          <Button tone="quiet" onClick={() => nav(`/jobs/${NEW_ID}`)}>{t.jobs.new}</Button>
        </div>
        {jobs.isPending && <div aria-busy="true" style={{ padding: "var(--space-4)" }}><Skeleton lines={6} height="2.4rem" /></div>}
        {jobs.isError && <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} />}
        {jobs.data?.length === 0 && <EmptyState title={t.jobs.emptyTitle} body={t.jobs.emptyBody} />}
        <ul className={s.rows}>
          {jobs.data?.map((j) => <JobRow key={j.id} job={j} active={j.id === id} />)}
        </ul>
      </aside>
      <div className={s.editorWrap}>
        {!id && <EmptyState title="Wähle eine Stelle" body={t.jobs.emptyBody} />}
        {id === NEW_ID && <JobEditor key="new" onSaved={(j) => nav(`/jobs/${j.id}`)} />}
        {id && id !== NEW_ID && jobs.isPending && <div style={{ padding: "var(--space-5)" }}><Skeleton lines={8} height="2.4rem" /></div>}
        {job && <JobEditor key={job.id} job={job} onSaved={() => undefined} />}
        {id && id !== NEW_ID && jobs.isSuccess && !job && <EmptyState title="Diese Stelle gibt es nicht mehr" />}
      </div>
    </div>
  );
}

function JobRow({ job, active }: { job: Job; active: boolean }) {
  const blocks = (job.agg ?? []).filter((i) => i.severity === "block").length;
  return (
    <li>
      <Link to={`/jobs/${job.id}`} className={`${s.row} ${active ? s.rowActive : ""}`} aria-current={active ? "page" : undefined}>
        <span className={s.rowTitle}>{job.title}</span>
        <span className={s.rowSub}>
          <span>{occupationLabel[job.occupation] ?? job.occupation}</span>
          <span>{job.plz} {job.place}</span>
          <span className={job.open ? undefined : s.closed}>{job.open ? t.jobs.open : t.jobs.closed}</span>
          {blocks > 0 && <span className={s.flag}>{blocks} AGG</span>}
        </span>
      </Link>
    </li>
  );
}
