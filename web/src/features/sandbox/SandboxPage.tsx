import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { duration, ease } from "../../app/theme/motion";
import { ApiError } from "../../shared/api/client";
import { useSandbox, useSandboxSend } from "../../shared/api/queries";
import { messageText, t } from "../../shared/text/de";
import { Button } from "../../shared/ui/Button";
import { Skeleton } from "../../shared/ui/Skeleton";
import { EmptyState, ErrorState } from "../../shared/ui/States";
import { Lang } from "../../shared/ui/Verdict";
import s from "./sandbox.module.css";

export const EXAMPLES: { lang: string; text: string }[] = [
  { lang: "de", text: "J-LKW-LEJ Hallo, bin LKW-Fahrer mit CE und Code 95, wohne in Leipzig, kann ab sofort" },
  { lang: "tr", text: "Merhaba, elektrikçiyim, Münih'te oturuyorum, 6 yıldır çalışıyorum" },
  { lang: "pl", text: "Dzień dobry, jestem magazynierem, mam uprawnienia na wózek widłowy, mieszkam w Dortmundzie" },
  { lang: "ro", text: "Bună ziua, sunt asistentă medicală din România, echivalarea e în curs" },
  { lang: "uk", text: "Привіт, я доглядальниця, живу в Берліні, можу почати з грудня" },
  { lang: "ar", text: "مرحبا، أنا سباك وأسكن في هامبورغ" },
];

const newPhone = () => `4900${Math.floor(1e7 + Math.random() * 9e7)}`;
const PHONE_KEY = "fkp.sandboxPhone";

function initialPhone(): string {
  try {
    const p = sessionStorage.getItem(PHONE_KEY);
    if (p) return p;
  } catch { /* storage unavailable: a fresh number per visit */ }
  return newPhone();
}

export function SandboxPage() {
  const [phone, setPhone] = useState(initialPhone);
  const [name, setName] = useState("Alex Beispiel");
  const [text, setText] = useState("");
  const log = useSandbox(phone);
  const send = useSandboxSend(phone);
  const end = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => { try { sessionStorage.setItem(PHONE_KEY, phone); } catch { /* not kept */ } }, [phone]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: reduce ? "auto" : "smooth" }); }, [log.data, send.isPending, reduce]);

  const submit = (v: { text?: string; button_id?: string }) => {
    if (send.isPending) return;
    send.mutate({ ...v, name }, { onSuccess: () => setText("") });
  };
  const lines = log.data ?? [];
  const lastOut = [...lines].reverse().find((l) => l.direction === "out");
  const sandboxOff = log.error instanceof ApiError && log.error.status === 404;

  return (
    <div className={s.page}>
      <section className={s.phone} aria-label={t.sandbox.title}>
        <div className={s.bar}>
          <span className={s.barTitle}>{t.product}</span>
          <button type="button" className={s.restart} onClick={() => { setPhone(newPhone()); setText(""); send.reset(); }}>{t.sandbox.restart}</button>
        </div>
        <div className={s.log} role="log" aria-live="polite">
          {log.isPending && <Skeleton lines={4} height="2.4rem" width={["70%", "50%", "80%"]} />}
          {log.isError && <ErrorState error={sandboxOff ? new Error("Der Test-Chat ist auf diesem Server ausgeschaltet (FKP_SANDBOX=1).") : log.error}
            onRetry={() => log.refetch()} />}
          {log.isSuccess && lines.length === 0 && !send.isPending && <EmptyState title={t.sandbox.emptyTitle} body={t.sandbox.emptyBody} />}
          <AnimatePresence initial={false}>
            {lines.map((l, i) => (
              <motion.p key={`${l.at}-${i}`} dir="auto" className={`${s.bubble} ${l.direction === "in" ? s.in : s.out}`}
                initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: duration.base, ease: ease.out }}>
                {messageText(l.body)}
              </motion.p>
            ))}
          </AnimatePresence>
          {lastOut && lastOut.buttons.length > 0 && lines[lines.length - 1] === lastOut && (
            <div className={s.buttons}>
              {lastOut.buttons.map((b) => (
                <button key={b.id} type="button" className={s.reply} onClick={() => submit({ button_id: b.id })} disabled={send.isPending}>{b.title}</button>
              ))}
            </div>
          )}
          {send.isPending && <p className={s.typing}>{t.sandbox.typing}</p>}
          <div ref={end} />
        </div>
        {send.isError && <p className={s.error} role="alert">{send.error.message}</p>}
        <form className={s.composer} onSubmit={(e) => { e.preventDefault(); if (text.trim()) submit({ text }); }}>
          <label className="visually-hidden" htmlFor="sbx-text">{t.sandbox.placeholder}</label>
          <input id="sbx-text" value={text} placeholder={t.sandbox.placeholder} onChange={(e) => setText(e.target.value)} autoComplete="off" />
          <Button type="submit" disabled={!text.trim() || send.isPending}>{t.sandbox.send}</Button>
        </form>
      </section>
      <div className={s.side}>
        <h1>{t.sandbox.title}</h1>
        <p className={s.lead}>{t.sandbox.lead}</p>
        <label className={s.nameField}><span>{t.sandbox.name}</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <section aria-labelledby="ex-h" style={{ display: "grid", gap: "var(--space-3)" }}>
          <h2 id="ex-h">{t.sandbox.examples}</h2>
          <ul className={s.examples}>
            {EXAMPLES.map((x) => (
              <li key={x.text}>
                <button type="button" className={s.example} onClick={() => setText(x.text)} lang={x.lang}>
                  <Lang code={x.lang} /><span>{x.text}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
