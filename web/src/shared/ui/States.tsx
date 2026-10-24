import type { ReactNode } from "react";
import { t } from "../text/de";
import { Button } from "./Button";
import s from "./ui.module.css";

export function ErrorState({ error, onRetry, title = t.states.loadFailed }: { error: unknown; onRetry?: () => void; title?: string }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className={s.state} role="alert">
      <span className={s.errorMark} />
      <p className={s.stateTitle}>{title}</p>
      <p className={s.stateBody}>{message}</p>
      {onRetry && <Button tone="quiet" onClick={onRetry}>{t.states.retry}</Button>}
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className={s.state}>
      <span className={s.emptyMark} />
      <p className={s.stateTitle}>{title}</p>
      {body && <p className={s.stateBody}>{body}</p>}
      {action}
    </div>
  );
}
