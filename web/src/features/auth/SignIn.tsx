import { useState } from "react";
import { api, apiKey, ApiError } from "../../shared/api/client";
import { t } from "../../shared/text/de";
import { Button } from "../../shared/ui/Button";
import s from "../../app/app.module.css";

/** Checks the key against the API before keeping it, so a typo shows here and not on every screen. */
export function SignIn({ onDone }: { onDone: () => void }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <main className={s.signIn}>
      <form className={s.card} onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        apiKey.set(key.trim());
        try {
          await api("/api/jobs");
          onDone();
        } catch (err) {
          apiKey.clear();
          setError(err instanceof ApiError ? err.message : String(err));
        } finally {
          setBusy(false);
        }
      }}>
        <h1>{t.product}</h1>
        <p>{t.signIn.lead}</p>
        <label><span>{t.signIn.label}</span><input type="password" autoComplete="current-password" required value={key} onChange={(e) => setKey(e.target.value)} /></label>
        {error && <p className={s.err} role="alert">{error}</p>}
        <Button type="submit" disabled={busy || !key.trim()}>{t.signIn.submit}</Button>
      </form>
    </main>
  );
}
