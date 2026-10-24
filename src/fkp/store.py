"""PostgreSQL: conversations, messages, the outbox, events, jobs and the opt-out list."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import jobs as jobs_mod
from .config import ROOT
from .dialogue import Conversation

MIGRATIONS = ROOT / "migrations"
Conn = psycopg.Connection[dict[str, Any]]


class Store:
    def __init__(self, dsn: str, pool_size: int = 8) -> None:
        self.dsn = dsn
        self.pool: ConnectionPool[Conn] = ConnectionPool(dsn, min_size=1, max_size=pool_size, kwargs={"row_factory": dict_row}, open=True)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def conn(self) -> Iterator[Conn]:
        with self.pool.connection() as c:
            yield c

    def migrate(self, directory: Path = MIGRATIONS) -> list[str]:
        applied = []
        with self.conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, at timestamptz NOT NULL DEFAULT now())")
            done = {r["name"] for r in c.execute("SELECT name FROM schema_migrations")}
            for f in sorted(directory.glob("*.sql")):
                if f.name in done:
                    continue
                with c.transaction():
                    c.execute(f.read_text())  # type: ignore[call-overload]
                    c.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
                applied.append(f.name)
        return applied

    # -- conversations -------------------------------------------------------------------------

    @staticmethod
    def lock(c: Conn, channel: str, phone: str) -> None:
        """Serialise all work on one phone number (two webhooks for one person arrive together)."""
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"{channel}:{phone}",))

    @staticmethod
    def get_conversation(c: Conn, channel: str, phone: str) -> Conversation | None:
        r = c.execute("SELECT state FROM conversations WHERE channel = %s AND phone = %s", (channel, phone)).fetchone()
        return Conversation.from_dict(r["state"]) if r else None

    @staticmethod
    def save_conversation(c: Conn, channel: str, conv: Conversation) -> None:
        c.execute(
            """INSERT INTO conversations (id, channel, phone, lang, stage, job_id, state, last_inbound_at, consent_at, handed_over_at, pool_until,
                                         created_at, updated_at)
               VALUES (%(id)s, %(channel)s, %(phone)s, %(lang)s, %(stage)s, %(job_id)s, %(state)s, %(li)s, %(ca)s, %(ho)s, %(pu)s,
                       COALESCE(%(ua)s, now()), COALESCE(%(ua)s, now()))
               ON CONFLICT (channel, phone) DO UPDATE SET lang = EXCLUDED.lang, stage = EXCLUDED.stage, job_id = EXCLUDED.job_id,
                 state = EXCLUDED.state, updated_at = EXCLUDED.updated_at, last_inbound_at = EXCLUDED.last_inbound_at, consent_at = EXCLUDED.consent_at,
                 handed_over_at = EXCLUDED.handed_over_at, pool_until = EXCLUDED.pool_until""",
            {"id": conv.id, "channel": channel, "phone": conv.phone, "lang": conv.lang, "stage": conv.stage, "job_id": conv.job_id,
             "state": Jsonb(conv.to_dict()), "li": conv.last_inbound_at, "ca": conv.consent_at, "ho": conv.handed_over_at, "pu": conv.pool_until,
             # activity time comes from the messages, not the database clock, so retention and
             # reminders follow the conversation (and tests can run in simulated time)
             "ua": max(filter(None, [conv.last_inbound_at, conv.last_outbound_at]), default=None)},
        )

    @staticmethod
    def conversation_by_id(c: Conn, cid: str) -> dict[str, Any] | None:
        return c.execute("SELECT * FROM conversations WHERE id = %s", (cid,)).fetchone()

    @staticmethod
    def add_message(c: Conn, cid: str, direction: str, kind: str, body: str, at: datetime, channel_id: str | None = None,
                    purpose: str | None = None, status: str | None = None, redacted: bool = False) -> int | None:
        r = c.execute(
            """INSERT INTO messages (conversation_id, direction, channel_id, kind, body, purpose, status, at, redacted)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id""",
            (cid, direction, channel_id, kind, body, purpose, status, at, redacted),
        ).fetchone()
        return r["id"] if r else None

    @staticmethod
    def seen(c: Conn, channel_id: str) -> bool:
        return c.execute("SELECT 1 FROM messages WHERE direction = 'in' AND channel_id = %s", (channel_id,)).fetchone() is not None

    @staticmethod
    def add_event(c: Conn, cid: str | None, typ: str, data: dict[str, Any], at: datetime) -> None:
        c.execute("INSERT INTO events (conversation_id, type, data, at) VALUES (%s, %s, %s, %s)", (cid, typ, Jsonb(data), at))

    @staticmethod
    def enqueue(c: Conn, cid: str | None, kind: str, payload: dict[str, Any], key: str, at: datetime | None = None) -> bool:
        r = c.execute(
            """INSERT INTO outbox (conversation_id, kind, payload, idempotency_key, next_attempt_at)
               VALUES (%s, %s, %s, %s, COALESCE(%s, now())) ON CONFLICT (idempotency_key) DO NOTHING RETURNING id""",
            (cid, kind, Jsonb(payload), key, at),
        ).fetchone()
        return r is not None

    @staticmethod
    def erase(c: Conn, cid: str, reason: str, at: datetime) -> None:
        """Delete messages, events and pending outbox rows of a conversation; the conversation row
        keeps only its reset state."""
        c.execute("DELETE FROM messages WHERE conversation_id = %s", (cid,))
        c.execute("DELETE FROM events WHERE conversation_id = %s", (cid,))
        c.execute("DELETE FROM outbox WHERE conversation_id = %s AND status = 'pending' AND kind <> 'message'", (cid,))
        c.execute("INSERT INTO erasures (reason, at) VALUES (%s, %s)", (reason, at))

    @staticmethod
    def suppress(c: Conn, phone_hash: str, reason: str, at: datetime) -> None:
        c.execute("INSERT INTO suppression (phone_hash, reason, at) VALUES (%s, %s, %s) ON CONFLICT (phone_hash) DO UPDATE SET at = EXCLUDED.at",
                  (phone_hash, reason, at))

    @staticmethod
    def unsuppress(c: Conn, phone_hash: str) -> None:
        c.execute("DELETE FROM suppression WHERE phone_hash = %s", (phone_hash,))

    @staticmethod
    def suppressed(c: Conn, phone_hash: str) -> bool:
        return c.execute("SELECT 1 FROM suppression WHERE phone_hash = %s", (phone_hash,)).fetchone() is not None

    # -- jobs ----------------------------------------------------------------------------------

    def jobs(self, only_open: bool = False) -> list[jobs_mod.Job]:
        with self.conn() as c:
            rows = c.execute("SELECT data FROM jobs" + (" WHERE open" if only_open else "") + " ORDER BY id").fetchall()
        return [jobs_mod.parse(r["data"]) for r in rows]

    def upsert_job(self, job: jobs_mod.Job) -> None:
        with self.conn() as c:
            c.execute("""INSERT INTO jobs (id, data, open) VALUES (%s, %s, %s)
                         ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, open = EXCLUDED.open, updated_at = now()""",
                      (job.id, Jsonb(json.loads(json.dumps(job.to_dict(), default=str))), job.open))
