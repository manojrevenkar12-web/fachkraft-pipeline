"""Wiring the conversation to the database and the outside world.

* `inbound`: one webhook message, processed exactly once (deduplicated by message id, serialised
  per phone number by an advisory lock), in one transaction with everything it causes: the
  stored message (health sentences removed), the conversation state, events, and outbox rows for
  replies and hand-overs.
* `deliver`: the outbox worker. Rows are claimed with FOR UPDATE SKIP LOCKED and a lease, sent
  outside the transaction, and retried with backoff; a crashed worker's rows come back when the
  lease runs out. WhatsApp's 24-hour rule is checked again at send time, because a reply queued
  at minute 1439 may leave at minute 1441.
* `tick`: reminders for candidates who went quiet, inside quiet hours and the template rules.
* `purge`: retention. Pre-consent chats after 72 hours, everything else after the configured months.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Protocol

from . import config
from .ats import Adapter, AtsError, handover_payload
from .dialogue import Agent, Conversation, Inbound, Outgoing
from .jobs import Job
from .privacy import phone_hash, redact
from .store import Conn, Store
from .whatsapp import WINDOW_CLOSED, SendError, Status

LEASE = timedelta(seconds=60)
MAX_ATTEMPTS = 8
NOTIFY = {"handover", "human_requested", "deleted", "pooled"}


class Channel(Protocol):
    def send(self, to: str, out: Outgoing) -> str: ...


class Engine:
    def __init__(
        self, store: Store, channels: dict[str, Channel], ats: Adapter | None = None, notifier: Adapter | None = None, extractor: Any = None
    ) -> None:
        self.store = store
        self.channels = channels
        self.ats = ats
        self.notifier = notifier
        self.extractor = extractor
        self.st = config.settings()

    def agent(self, jobs: list[Job] | None = None) -> Agent:
        a = Agent(jobs if jobs is not None else self.store.jobs(only_open=True), self.extractor)
        if self.ats is not None and self.ats.name == "personio":
            a.st = {**a.st, "conversation": {**a.st["conversation"], "fields_for_handover": ["full_name", "email"]}}
        return a

    # -- inbound -------------------------------------------------------------------------------

    def inbound(self, channel: str, phone: str, msg: Inbound) -> dict[str, Any]:
        agent = self.agent()
        with self.store.conn() as c, c.transaction():
            Store.lock(c, channel, phone)
            if Store.seen(c, msg.id):
                return {"status": "duplicate"}
            conv = Store.get_conversation(c, channel, phone) or Conversation(id=str(uuid.uuid4()), phone=phone, last_inbound_at=msg.at.isoformat())
            was = conv.stage
            Store.save_conversation(c, channel, conv)
            # a tapped reply button is stored as "[button_id]", so the chat history shows the choice
            body, red = redact(msg.text or (f"[{msg.button_id}]" if msg.button_id else ""), conv.lang)
            Store.add_message(c, conv.id, "in", msg.kind, body, msg.at, channel_id=msg.id, redacted=red)
            res = agent.handle(conv, msg)
            if was == "deleted" and conv.stage != "deleted":
                Store.unsuppress(c, phone_hash(phone))  # they wrote again and started over
            for e in res.events:
                if e["type"] == "deleted":
                    self._erase(c, conv, e.get("reason", "opt_out"), msg.at)
                    Store.suppress(c, phone_hash(phone), e.get("reason", "opt_out"), msg.at)
            Store.save_conversation(c, channel, conv)
            for e in res.events:
                Store.add_event(c, conv.id if e["type"] != "deleted" else None, e["type"], {k: v for k, v in e.items() if k != "type"}, msg.at)
                if e["type"] == "handover":
                    for j in e["jobs"]:
                        p = handover_payload(conv, j["job_id"], j["verdict"], agent.summary(conv))
                        Store.enqueue(c, conv.id, "ats", p, f"handover:{conv.id}:{j['job_id']}:{conv.handed_over_at}", msg.at)
                if e["type"] in NOTIFY and self.notifier is not None:
                    Store.enqueue(
                        c,
                        None if e["type"] == "deleted" else conv.id,
                        "webhook",
                        {
                            "event": e["type"],
                            "conversation_id": conv.id if e["type"] != "deleted" else None,
                            "at": msg.at.isoformat(),
                            "job_id": conv.job_id,
                        },
                        f"event:{msg.id}:{e['type']}",
                        msg.at,
                    )
            for i, out in enumerate(res.outgoing):
                Store.enqueue(c, conv.id, "message", {"channel": channel, "to": phone, "out": asdict(out)}, f"reply:{msg.id}:{i}", msg.at)
        return {"status": "processed", "conversation_id": conv.id, "stage": conv.stage, "replies": len(res.outgoing)}

    def _erase(self, c: Conn, conv: Conversation, reason: str, at: datetime) -> None:
        c.execute("DELETE FROM outbox WHERE conversation_id = %s AND status = 'pending'", (conv.id,))
        Store.erase(c, conv.id, reason, at)

    def status(self, s: Status) -> None:
        """A delivery receipt: record status and the category Meta billed."""
        prices = self.st["whatsapp"]["prices_usd"]
        with self.store.conn() as c:
            cost = prices.get(s.category or "", 0.0) if s.billable else 0.0
            c.execute(
                """UPDATE messages SET status = %s, category = COALESCE(%s, category), cost_usd = CASE WHEN %s THEN %s ELSE cost_usd END
                         WHERE direction = 'out' AND channel_id = %s""",
                (s.status, s.category, s.billable is not None, cost, s.message_id),
            )
            if s.status == "failed":
                row = c.execute("SELECT conversation_id FROM messages WHERE direction = 'out' AND channel_id = %s", (s.message_id,)).fetchone()
                if row:
                    Store.add_event(c, row["conversation_id"], "delivery_failed", {"code": s.error_code}, s.at)

    # -- outbox --------------------------------------------------------------------------------

    def deliver(self, now: datetime, limit: int = 50) -> dict[str, int]:
        stats = {"sent": 0, "retry": 0, "failed": 0, "expired": 0}
        with self.store.conn() as c, c.transaction():
            rows = c.execute(
                """UPDATE outbox SET attempts = attempts + 1, next_attempt_at = %s
                   WHERE id IN (SELECT id FROM outbox WHERE status = 'pending' AND next_attempt_at <= %s ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED)
                   RETURNING *""",
                (now + LEASE, now, limit),
            ).fetchall()
        for row in sorted(rows, key=lambda r: r["id"]):
            try:
                outcome, ext = self._send(row, now)
            except (SendError, AtsError) as e:
                retry = e.retryable and row["attempts"] < MAX_ATTEMPTS
                with self.store.conn() as c:
                    if retry:
                        wait = min(timedelta(hours=1), timedelta(seconds=30 * 2 ** (row["attempts"] - 1)))
                        c.execute("UPDATE outbox SET next_attempt_at = %s, last_error = %s WHERE id = %s", (now + wait, str(e)[:500], row["id"]))
                        stats["retry"] += 1
                    else:
                        status = "expired" if isinstance(e, SendError) and e.code == WINDOW_CLOSED else "failed"
                        c.execute("UPDATE outbox SET status = %s, last_error = %s WHERE id = %s", (status, str(e)[:500], row["id"]))
                        if row["conversation_id"]:
                            Store.add_event(c, row["conversation_id"], f"{row['kind']}_{status}", {"error": str(e)[:200]}, now)
                        stats["failed" if status == "failed" else "expired"] += 1
                continue
            with self.store.conn() as c:
                c.execute(
                    "UPDATE outbox SET status = %s, sent_at = %s, external_id = %s WHERE id = %s",
                    ("sent" if outcome == "sent" else "expired", now, ext, row["id"]),
                )
            stats["sent" if outcome == "sent" else "expired"] += 1
        return stats

    def _send(self, row: dict[str, Any], now: datetime) -> tuple[str, str | None]:
        p = row["payload"]
        if row["kind"] == "ats":
            if self.ats is None:
                raise AtsError("no ATS configured", retryable=False)
            ext = self.ats.send(p)
            with self.store.conn() as c:
                Store.add_event(c, row["conversation_id"], "handover_sent", {"ats": self.ats.name, "external_id": ext, "job_id": p["job_id"]}, now)
            return "sent", ext
        if row["kind"] == "webhook":
            if self.notifier is None:
                return "expired", None
            return "sent", self.notifier.send(p)
        out = Outgoing(**{**p["out"], "buttons": [tuple(b) for b in p["out"].get("buttons", [])]})
        with self.store.conn() as c:
            conv = self.store.conversation_by_id(c, row["conversation_id"])
        if conv is None:
            return "expired", None
        window_end = conv["last_inbound_at"] + timedelta(hours=self.st["whatsapp"]["window_hours"]) if conv["last_inbound_at"] else now
        if out.kind != "template" and now > window_end:
            with self.store.conn() as c:
                Store.add_event(c, row["conversation_id"], "window_closed", {"purpose": out.purpose}, now)
            return "expired", None
        if out.kind == "template":
            with self.store.conn() as c:
                if Store.suppressed(c, phone_hash(p["to"])):
                    return "expired", None
        ext = self.channels[p["channel"]].send(p["to"], out)
        category = (out.template or {}).get("category", "service")
        cost = self.st["whatsapp"]["prices_usd"].get(category, 0.0) if out.kind == "template" else 0.0
        with self.store.conn() as c:
            mid = Store.add_message(c, row["conversation_id"], "out", out.kind, out.body, now, channel_id=ext, purpose=out.purpose, status="sent")
            if mid:
                c.execute("UPDATE messages SET category = %s, cost_usd = %s WHERE id = %s", (category, cost, mid))
        return "sent", ext

    # -- reminders and retention ---------------------------------------------------------------

    def tick(self, now: datetime) -> int:
        """Queue due reminders. Safe to run from several places at once."""
        agent = self.agent()
        queued = 0
        with self.store.conn() as c:
            rows = c.execute(
                """SELECT channel, phone FROM conversations
                                WHERE stage IN ('collecting', 'confirming', 'fixing', 'handover_details') AND updated_at < %s""",
                (now - timedelta(hours=min(self.st["followups"]["schedule_hours"]) - 1),),
            ).fetchall()
        for r in rows:
            with self.store.conn() as c, c.transaction():
                Store.lock(c, r["channel"], r["phone"])
                conv = Store.get_conversation(c, r["channel"], r["phone"])
                if conv is None or Store.suppressed(c, phone_hash(conv.phone)):
                    continue
                out = agent.reminder(conv, now)
                if out is None:
                    continue
                key = f"reminder:{conv.id}:{conv.last_inbound_at}:{conv.reminders_sent}"
                if Store.enqueue(c, conv.id, "message", {"channel": r["channel"], "to": conv.phone, "out": asdict(out)}, key, now):
                    conv.last_outbound_at = now.isoformat()
                    Store.save_conversation(c, r["channel"], conv)
                    Store.add_event(c, conv.id, "reminder_queued", {"n": conv.reminders_sent, "kind": out.kind}, now)
                    queued += 1
        return queued

    def purge(self, now: datetime) -> int:
        ret = self.st["retention"]
        with self.store.conn() as c, c.transaction():
            rows = c.execute(
                """DELETE FROM conversations WHERE
                     (stage IN ('new', 'awaiting_consent', 'declined') AND updated_at < %(pre)s)
                  OR (stage = 'pooled' AND pool_until < %(now)s)
                  OR (stage NOT IN ('pooled') AND updated_at < %(old)s)
                   RETURNING id""",
                {"pre": now - timedelta(hours=ret["pre_consent_hours"]), "now": now, "old": now - timedelta(days=30 * ret["rejected_months"])},
            ).fetchall()
            for _ in rows:
                c.execute("INSERT INTO erasures (reason, at) VALUES ('retention', %s)", (now,))
        return len(rows)
