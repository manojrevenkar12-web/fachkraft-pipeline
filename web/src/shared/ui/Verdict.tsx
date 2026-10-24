import type { Verdict as V } from "../api/types";
import { verdictLabel } from "../text/de";
import s from "./ui.module.css";

/** Colour plus pattern (solid, hatched, outline), so the verdict reads without colour too. */
export function Verdict({ verdict, label }: { verdict: V; label?: string }) {
  return (
    <span className={s.verdict}>
      <span className={`${s.swatch} ${s[verdict]}`} aria-hidden="true" />
      {label ?? verdictLabel[verdict]}
    </span>
  );
}

export function Lang({ code }: { code: string }) {
  return <span className={s.lang} lang={code}>{code}</span>;
}
