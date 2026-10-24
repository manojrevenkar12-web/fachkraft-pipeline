"""`fkp demo`: fill a database with simulated candidates for the web app and the screenshots.

The candidates go through the real engine (sandbox channel, outbox, events), at simulated times
over the past days, so the recruiter screens show what production would show. Every name, email
and number is invented; phone numbers are in a range no network uses.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from ..dialogue import Inbound, Outgoing
from ..engine import Engine
from ..store import Store
from . import personas
from .run import Assumptions, _answer, _reply_delay

TERMINAL = {"matched", "near_miss", "deleted", "human", "pool_saved", "consent_declined"}


def seed(store: Store, engine: Engine, n: int, now: datetime, seed: int = 21, days: float = 5.0) -> dict[str, int]:
    rng = random.Random(seed)
    a = Assumptions()
    stages: dict[str, int] = {}
    for p in personas.make(n, seed, now.date()):
        phone = f"4900000{int(p.id[1:]):05d}"
        t = now - timedelta(days=rng.uniform(0.2, days))
        text, button = personas.first_message(p, t.date()), ""
        for i in range(30):
            if t > now:
                break
            msg = Inbound(id=f"demo.{seed}.{p.id}.{i}", at=t, kind="button" if button else "text", text=text, button_id=button,
                          profile_name=p.full_name)
            res = engine.inbound("sandbox", phone, msg)
            engine.deliver(t)
            with store.conn() as c:
                conv = Store.get_conversation(c, "sandbox", phone)
                last = c.execute("SELECT body, purpose FROM messages WHERE conversation_id = %s AND direction = 'out' ORDER BY at DESC, id DESC LIMIT 1",
                                 (res.get("conversation_id"),)).fetchone()
            if conv is None or last is None or res.get("replies", 0) == 0 or last["purpose"] in TERMINAL:
                break
            if p.rng.random() > p.patience:
                break  # went quiet; reminders would follow from `fkp worker`
            t = t + _reply_delay(p)
            text, button = _answer(p, Outgoing("text", last["body"], last["purpose"] or ""), conv, t.date(), a)
        with store.conn() as c:
            conv = Store.get_conversation(c, "sandbox", phone)
        stage = conv.stage if conv else "deleted"
        stages[stage] = stages.get(stage, 0) + 1
    return stages
