import s from "./ui.module.css";

/** A placeholder block; `lines` stacks several with the given width pattern. */
export function Skeleton({ width = "100%", height = "1em", lines = 1, gap = "var(--space-2)" }:
  { width?: string | string[]; height?: string; lines?: number; gap?: string }) {
  const widths = Array.isArray(width) ? width : [width];
  return (
    <span aria-hidden="true" style={{ display: "grid", gap }} data-testid="skeleton">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={s.skeleton} style={{ width: widths[i % widths.length], height }} />
      ))}
    </span>
  );
}
