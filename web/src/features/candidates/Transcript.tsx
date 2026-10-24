import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { Message } from "../../shared/api/types";
import { duration, ease } from "../../app/theme/motion";
import { messageText, t } from "../../shared/text/de";
import { splitAt, type Span } from "./evidence";
import s from "./candidates.module.css";

const time = (iso: string) => new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

/** The chat; the message a selected fact came from scrolls into view with its span highlighted. */
export function Transcript({ messages, span }: { messages: Message[]; span: Span | null }) {
  const target = useRef<HTMLElement | null>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    target.current?.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
  }, [span, reduce]);

  return (
    <div className={s.chat} role="log" aria-label={t.candidates.chat}>
      {messages.map((m, i) => {
        const own = span?.index === i ? span : null;
        const [before, hit, after] = splitAt(messageText(m.body), own);
        return (
          <p key={`${m.at}-${i}`} dir="auto" className={`${s.bubble} ${m.direction === "in" ? s.in : s.out}`}
            ref={own ? (el) => { target.current = el; } : undefined}>
            {before}
            {hit && (
              <mark className={s.mark}>
                <motion.span key={`${own?.start}-${own?.end}`} className={s.markInk} aria-hidden="true"
                  initial={reduce ? false : { scaleX: 0 }} animate={{ scaleX: 1 }}
                  transition={{ duration: duration.stroke, ease: ease.out }} />
                <span className={s.markText}>{hit}</span>
              </mark>
            )}
            {after}
            {m.redacted && <span className={s.redacted}> · {t.candidates.redacted}</span>}
            <span className={s.stamp}>{time(m.at)}</span>
          </p>
        );
      })}
    </div>
  );
}
