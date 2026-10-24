import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import { CandidatesPage } from "../features/candidates/CandidatesPage";
import { JobsPage } from "../features/jobs/JobsPage";
import { NumbersPage } from "../features/numbers/NumbersPage";
import { SandboxPage } from "../features/sandbox/SandboxPage";
import { SignIn } from "../features/auth/SignIn";
import { ApiError, apiKey } from "../shared/api/client";
import { t } from "../shared/text/de";
import { Button } from "../shared/ui/Button";
import { duration, ease } from "./theme/motion";
import s from "./app.module.css";

const NAV = [
  { to: "/candidates", label: t.nav.candidates },
  { to: "/jobs", label: t.nav.jobs },
  { to: "/numbers", label: t.nav.numbers },
  { to: "/sandbox", label: t.nav.sandbox },
];

export function App() {
  const [signedIn, setSignedIn] = useState(() => Boolean(apiKey.get()));
  const client = useMemo(() => new QueryClient({
    queryCache: new QueryCache({ onError: (e) => { if (e instanceof ApiError && e.status === 401) { apiKey.clear(); setSignedIn(false); } } }),
    defaultOptions: { queries: { retry: (n, e) => !(e instanceof ApiError && e.status < 500) && n < 2, refetchOnWindowFocus: true, staleTime: 15_000 } },
  }), []);

  if (!signedIn) return <SignIn onDone={() => setSignedIn(true)} />;
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <a href="#main" className={s.skip}>Zum Inhalt</a>
        <header className={s.bar}>
          <NavLink to="/candidates" className={s.brand}><span className={s.brandMark} aria-hidden="true" /><span className={s.brandText}>{t.product}</span></NavLink>
          <nav className={s.nav} aria-label="Hauptnavigation">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => `${s.link} ${isActive ? s.active : ""}`}>
                {({ isActive }) => (
                  <>
                    {n.label}
                    {isActive && <motion.span layoutId="nav-underline" className={s.underline} transition={{ duration: duration.base, ease: ease.out }} />}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <span className={s.spacer} />
          <Button tone="quiet" className={s.signOut} onClick={() => { apiKey.clear(); client.clear(); setSignedIn(false); }}>{t.signIn.signOut}</Button>
        </header>
        <main id="main" className={s.main}>
          <Routes>
            <Route path="/" element={<Navigate to="/candidates" replace />} />
            <Route path="/candidates/:id?" element={<CandidatesPage />} />
            <Route path="/jobs/:id?" element={<JobsPage />} />
            <Route path="/numbers" element={<NumbersPage />} />
            <Route path="/sandbox" element={<SandboxPage />} />
            <Route path="*" element={<Navigate to="/candidates" replace />} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
