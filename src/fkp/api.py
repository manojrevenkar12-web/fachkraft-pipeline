"""HTTP API: the WhatsApp webhook, the recruiter API behind the web app, and a sandbox channel.

Auth: `Authorization: Bearer <key>` with keys from FKP_API_KEYS (`key:role`, roles reader <
recruiter < admin, keys at least 16 characters). The webhook is authenticated by Meta's signature
instead (FKP_WA_APP_SECRET), its subscription by FKP_WA_VERIFY_TOKEN.
"""

from __future__ import annotations

import hmac
import json
import os
import statistics
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from . import jobs as jobs_mod
from .dialogue import Conversation, Inbound, Outgoing
from .engine import Engine
from .privacy import phone_hash
from .store import Store
from .whatsapp import SignatureError, parse_webhook, verify_signature

ROLES = {"reader": 0, "recruiter": 1, "admin": 2}


def _keys() -> dict[str, str]:
    out = {}
    for pair in os.environ.get("FKP_API_KEYS", "").split(","):
        if ":" in pair:
            k, role = pair.rsplit(":", 1)
            if role in ROLES and len(k) >= 16:
                out[k] = role
    return out


def require(role: str) -> Any:
    def dep(authorization: str = Header(default="")) -> str:
        token = authorization.removeprefix("Bearer ").strip()
        for key, r in _keys().items():
            if hmac.compare_digest(key, token):
                if ROLES[r] < ROLES[role]:
                    raise HTTPException(403, f"needs the {role} role")
                return r
        raise HTTPException(401, "missing or unknown API key")

    return dep


class JobBody(BaseModel):
    job: dict[str, Any]
    override_reason: str | None = Field(default=None, max_length=500)


class ReplyBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SandboxBody(BaseModel):
    text: str = Field(default="", max_length=4000)
    button_id: str = Field(default="", max_length=64)
    name: str = Field(default="", max_length=80)


def _public_conv(row: dict[str, Any]) -> dict[str, Any]:
    st = row["state"]
    prof = st.get("profile") or {}
    occ = (prof.get("occupation") or {}).get("value") or []
    loc = (prof.get("location") or {}).get("value") or {}
    verdicts = [f.split(":") for f in st.get("flags", []) if f.startswith("job:")]
    return {
        "id": row["id"],
        "channel": row["channel"],
        "stage": row["stage"],
        "lang": row["lang"],
        "job_id": row["job_id"],
        "name": (prof.get("full_name") or {}).get("value") or st.get("wa_name") or "",
        "occupation": occ,
        "place": loc.get("place"),
        "updated_at": row["updated_at"].isoformat(),
        "created_at": row["created_at"].isoformat(),
        "matches": [{"job_id": j, "verdict": v} for _, j, v in verdicts],
        "fields": len(prof),
    }


def create_app(store: Store, engine: Engine, clock: Callable[[], datetime] | None = None, sandbox: bool | None = None) -> FastAPI:
    now = clock or (lambda: datetime.now(UTC))
    sandbox_on = sandbox if sandbox is not None else os.environ.get("FKP_SANDBOX") == "1"
    app = FastAPI(title="fachkraft-pipeline", version="0.1.0")
    app.state.store, app.state.engine = store, engine
    origins = [o for o in os.environ.get("FKP_CORS_ORIGINS", "").split(",") if o]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        try:
            with store.conn() as c:
                c.execute("SELECT 1")
        except Exception as e:
            raise HTTPException(503, "database unavailable") from e
        return {"status": "ready"}

    # -- WhatsApp ------------------------------------------------------------------------------

    @app.get("/webhooks/whatsapp", response_class=PlainTextResponse)
    def wa_verify(
        mode: str = Query("", alias="hub.mode"), token: str = Query("", alias="hub.verify_token"), challenge: str = Query("", alias="hub.challenge")
    ) -> str:
        expected = os.environ.get("FKP_WA_VERIFY_TOKEN", "")
        if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
            return challenge
        raise HTTPException(403, "verification failed")

    @app.post("/webhooks/whatsapp")
    async def wa_webhook(request: Request, x_hub_signature_256: str = Header(default="")) -> dict[str, Any]:
        raw = await request.body()
        try:
            verify_signature(os.environ.get("FKP_WA_APP_SECRET", ""), raw, x_hub_signature_256)
        except SignatureError as e:
            raise HTTPException(401, str(e)) from e
        try:
            batch = parse_webhook(json.loads(raw or b"{}"))
        except (ValueError, KeyError) as e:
            raise HTTPException(400, f"unreadable webhook: {e}") from e
        results = [engine.inbound("whatsapp", phone, msg) for phone, msg in batch.messages]
        for s in batch.statuses:
            engine.status(s)
        return {"messages": len(results), "statuses": len(batch.statuses)}

    # -- jobs ----------------------------------------------------------------------------------

    @app.get("/api/jobs", dependencies=[Depends(require("reader"))])
    def list_jobs() -> list[dict[str, Any]]:
        out = []
        for j in store.jobs():
            d = j.to_dict()
            d["agg"] = [i.__dict__ for i in jobs_mod.check_agg(j)]
            out.append(d)
        return out

    @app.post("/api/jobs/lint", dependencies=[Depends(require("reader"))])
    def lint(body: dict[str, Any]) -> list[dict[str, Any]]:
        return [i.__dict__ for i in jobs_mod.check_agg(body)]

    @app.post("/api/jobs", dependencies=[Depends(require("recruiter"))])
    def save_job(body: JobBody) -> dict[str, Any]:
        try:
            job = jobs_mod.parse(body.job)
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(422, str(e)) from e
        issues = jobs_mod.check_agg(job)
        blocking = [i for i in issues if i.severity == "block"]
        if blocking and not (body.override_reason and len(body.override_reason.strip()) >= 10):
            raise HTTPException(422, {"message": "the job text has wording that discriminates (AGG)", "issues": [i.__dict__ for i in blocking]})
        store.upsert_job(job)
        with store.conn() as c:
            Store.add_event(
                c, None, "job_saved", {"job_id": job.id, "override_reason": body.override_reason, "issues": [i.rule for i in issues]}, now()
            )
        return {**job.to_dict(), "agg": [i.__dict__ for i in issues]}

    @app.patch("/api/jobs/{job_id}", dependencies=[Depends(require("recruiter"))])
    def set_open(job_id: str, body: dict[str, bool]) -> dict[str, Any]:
        with store.conn() as c:
            r = c.execute(
                "UPDATE jobs SET open = %s, data = jsonb_set(data, '{open}', to_jsonb(%s::boolean)), updated_at = now() WHERE id = %s RETURNING id",
                (bool(body.get("open")), bool(body.get("open")), job_id),
            ).fetchone()
        if not r:
            raise HTTPException(404, "no such job")
        return {"id": job_id, "open": bool(body.get("open"))}

    # -- candidates ----------------------------------------------------------------------------

    @app.get("/api/candidates", dependencies=[Depends(require("reader"))])
    def candidates(stage: str | None = None, job_id: str | None = None, q: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        where, args = ["stage <> 'deleted'"], []
        if stage:
            where.append("stage = %s")
            args.append(stage)
        if job_id:
            where.append("(job_id = %s OR state->'flags' ? %s)")
            args += [job_id, f"job:{job_id}:fit"]
        with store.conn() as c:
            rows = c.execute(
                f"SELECT * FROM conversations WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT %s",  # noqa: S608
                [*args, min(limit, 500)],
            ).fetchall()
        out = [_public_conv(r) for r in rows]
        if q:
            ql = q.lower()
            out = [o for o in out if ql in o["name"].lower() or ql in (o["place"] or "").lower() or any(ql in x for x in o["occupation"])]
        return out

    @app.get("/api/candidates/{cid}", dependencies=[Depends(require("reader"))])
    def candidate(cid: str) -> dict[str, Any]:
        with store.conn() as c:
            row = Store.conversation_by_id(c, cid)
            if not row or row["stage"] == "deleted":
                raise HTTPException(404, "no such candidate")
            msgs = c.execute(
                "SELECT direction, kind, channel_id, body, purpose, status, category, cost_usd, at, redacted FROM messages WHERE conversation_id = %s ORDER BY at, id",
                (cid,),
            ).fetchall()
            evs = c.execute("SELECT type, data, at FROM events WHERE conversation_id = %s ORDER BY at, id", (cid,)).fetchall()
        st = row["state"]
        return {
            **_public_conv(row),
            "phone": row["phone"],
            "consent_at": st.get("consent_at"),
            "profile": st.get("profile") or {},
            "matches": st.get("matches") or [],
            "skipped": st.get("skipped") or [],
            "asked": st.get("asked"),
            "messages": [{**m, "at": m["at"].isoformat(), "cost_usd": float(m["cost_usd"])} for m in msgs],
            "events": [{**e, "at": e["at"].isoformat()} for e in evs],
        }

    @app.post("/api/candidates/{cid}/messages", dependencies=[Depends(require("recruiter"))])
    def reply(cid: str, body: ReplyBody) -> dict[str, Any]:
        t = now()
        with store.conn() as c, c.transaction():
            row = Store.conversation_by_id(c, cid)
            if not row or row["stage"] == "deleted":
                raise HTTPException(404, "no such candidate")
            last = row["last_inbound_at"]
            if not last or (t - last).total_seconds() > 24 * 3600:
                raise HTTPException(409, "the 24-hour window is closed; only an approved template can reach this candidate now")
            out = Outgoing("text", body.text, "recruiter")
            Store.enqueue(c, cid, "message", {"channel": row["channel"], "to": row["phone"], "out": out.__dict__}, f"recruiter:{cid}:{t.isoformat()}")
            Store.add_event(c, cid, "recruiter_reply", {}, t)
        return {"queued": True}

    @app.delete("/api/candidates/{cid}", dependencies=[Depends(require("recruiter"))])
    def erase(cid: str) -> dict[str, Any]:
        t = now()
        with store.conn() as c, c.transaction():
            row = Store.conversation_by_id(c, cid)
            if not row:
                raise HTTPException(404, "no such candidate")
            c.execute("DELETE FROM conversations WHERE id = %s", (cid,))
            c.execute("INSERT INTO erasures (reason, at) VALUES ('request', %s)", (t,))
            Store.suppress(c, phone_hash(row["phone"]), "erasure_request", t)
        return {"deleted": True}

    @app.get("/api/candidates/{cid}/export", dependencies=[Depends(require("recruiter"))])
    def export(cid: str) -> dict[str, Any]:
        """Everything stored about a person (GDPR Art. 15)."""
        return {**candidate(cid), "exported_at": now().isoformat()}

    # -- metrics -------------------------------------------------------------------------------

    @app.get("/api/metrics", dependencies=[Depends(require("reader"))])
    def metrics() -> dict[str, Any]:
        with store.conn() as c:
            stages = {r["stage"]: r["n"] for r in c.execute("SELECT stage, count(*) AS n FROM conversations GROUP BY stage")}
            langs = {r["lang"]: r["n"] for r in c.execute("SELECT lang, count(*) AS n FROM conversations WHERE stage <> 'deleted' GROUP BY lang")}
            ev = {r["type"]: r["n"] for r in c.execute("SELECT type, count(*) AS n FROM events GROUP BY type")}
            cost = c.execute(
                "SELECT category, count(*) AS n, coalesce(sum(cost_usd), 0) AS usd FROM messages WHERE direction = 'out' GROUP BY category"
            ).fetchall()
            durations = [
                r["m"]
                for r in c.execute(
                    """SELECT extract(epoch FROM (min(e.at) - c.created_at)) / 60 AS m FROM conversations c
                   JOIN events e ON e.conversation_id = c.id AND e.type = 'profile_confirmed' GROUP BY c.id, c.created_at"""
                )
            ]
            erasures = (c.execute("SELECT count(*) AS n FROM erasures").fetchone() or {"n": 0})["n"]
        started = sum(stages.values())
        consented = ev.get("consent_given", 0)
        return {
            "funnel": {
                "started": started,
                "consented": consented,
                "confirmed": ev.get("profile_confirmed", 0),
                "handed_over": ev.get("handover", 0),
                "pooled": ev.get("pooled", 0),
                "human": ev.get("human_requested", 0),
                "declined": ev.get("consent_declined", 0),
                "deleted": erasures,
            },
            "stages": stages,
            "languages": langs,
            "minutes_to_confirmed_median": round(statistics.median(durations), 1) if durations else None,
            "messages": [{"category": r["category"] or "service", "count": r["n"], "usd": float(r["usd"])} for r in cost],
            "reminders": ev.get("reminder_queued", 0),
            "window_closed": ev.get("window_closed", 0),
        }

    # -- sandbox -------------------------------------------------------------------------------

    @app.post("/api/sandbox/{phone}/messages", dependencies=[Depends(require("reader"))])
    def sandbox_send(phone: str, body: SandboxBody) -> dict[str, Any]:
        if not sandbox_on:
            raise HTTPException(404, "sandbox is off")
        if not phone.isdigit() or not 6 <= len(phone) <= 15:
            raise HTTPException(422, "phone must be 6-15 digits")
        t = now()
        msg = Inbound(
            id=f"sbx.{uuid.uuid4().hex}",
            at=t,
            kind="button" if body.button_id else "text",
            text=body.text,
            button_id=body.button_id,
            profile_name=body.name,
        )
        result = engine.inbound("sandbox", phone, msg)
        engine.deliver(t)
        return {**result, "transcript": sandbox_transcript(phone)}

    @app.get("/api/sandbox/{phone}/messages", dependencies=[Depends(require("reader"))])
    def sandbox_transcript(phone: str) -> list[dict[str, Any]]:
        if not sandbox_on:
            raise HTTPException(404, "sandbox is off")
        with store.conn() as c:
            row = c.execute("SELECT id FROM conversations WHERE channel = 'sandbox' AND phone = %s", (phone,)).fetchone()
            if not row:
                return []
            rows = c.execute(
                """SELECT m.direction, m.kind, m.body, m.purpose, m.at, o.payload->'out'->'buttons' AS buttons
                   FROM messages m LEFT JOIN outbox o ON o.external_id = m.channel_id AND m.direction = 'out'
                   WHERE m.conversation_id = %s ORDER BY m.at, m.id""",
                (row["id"],),
            ).fetchall()
        return [
            {
                "direction": r["direction"],
                "kind": r["kind"],
                "body": r["body"],
                "purpose": r["purpose"],
                "at": r["at"].isoformat(),
                "buttons": [{"id": b[0], "title": b[1]} for b in (r["buttons"] or [])],
            }
            for r in rows
        ]

    return app


def app_from_env() -> FastAPI:  # pragma: no cover - wiring
    from .ats import PersonioAdapter, WebhookAdapter
    from .whatsapp import CloudApiClient, SandboxClient

    store = Store(os.environ["FKP_DATABASE_URL"])
    channels: dict[str, Any] = {"sandbox": SandboxClient()}
    if os.environ.get("FKP_WA_TOKEN"):
        channels["whatsapp"] = CloudApiClient(os.environ["FKP_WA_PHONE_NUMBER_ID"], os.environ["FKP_WA_TOKEN"])
    ats: Any = None
    if os.environ.get("FKP_PERSONIO_TOKEN"):
        ats = PersonioAdapter(
            os.environ["FKP_PERSONIO_TOKEN"], os.environ["FKP_PERSONIO_COMPANY_ID"], json.loads(os.environ.get("FKP_PERSONIO_POSITIONS", "{}"))
        )
    elif os.environ.get("FKP_ATS_WEBHOOK_URL"):
        ats = WebhookAdapter(os.environ["FKP_ATS_WEBHOOK_URL"], os.environ.get("FKP_ATS_WEBHOOK_SECRET", ""))
    notifier = (
        WebhookAdapter(os.environ["FKP_EVENTS_WEBHOOK_URL"], os.environ.get("FKP_EVENTS_WEBHOOK_SECRET", ""))
        if os.environ.get("FKP_EVENTS_WEBHOOK_URL")
        else None
    )
    return create_app(store, Engine(store, channels, ats, notifier))


__all__ = ["Conversation", "create_app"]
