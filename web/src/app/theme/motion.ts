/** Motion constants: one place for durations and easings, used by every animated component. */
export const duration = { quick: 0.16, base: 0.24, slow: 0.42, stroke: 0.55 } as const;
export const ease = { out: [0.22, 1, 0.36, 1], inOut: [0.65, 0, 0.35, 1] } as const;
export const stagger = 0.035;

export const reveal = {
  hidden: { opacity: 0, y: 8 },
  shown: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: duration.base, ease: ease.out, delay: i * stagger } }),
};

/** Rows animate in with a stagger only up to this index; later rows appear with the last ones. */
export const maxStagger = 12;
/** Pause after typing before the job text is checked again (ms). */
export const lintDelayMs = 350;
