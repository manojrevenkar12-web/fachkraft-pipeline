import { useNavigate, useParams } from "react-router-dom";
import { useCandidates } from "../../shared/api/queries";
import { t } from "../../shared/text/de";
import { EmptyState } from "../../shared/ui/States";
import { CandidateDetail } from "./CandidateDetail";
import { CandidateList } from "./CandidateList";
import s from "./candidates.module.css";

export function CandidatesPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const list = useCandidates();
  return (
    <div className={`${s.page} ${id ? s.hasSelection : s.noSelection}`}>
      <CandidateList rows={list.data} loading={list.isPending} error={list.error} onRetry={() => list.refetch()} selected={id}
        onSandbox={() => nav("/sandbox")} />
      {id ? <CandidateDetail key={id} id={id} /> : (
        <div className={s.detail}><EmptyState title={t.candidates.pickTitle} body={t.candidates.pickBody} /></div>
      )}
    </div>
  );
}
