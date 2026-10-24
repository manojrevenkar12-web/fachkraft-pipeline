"""The engine against PostgreSQL: exactly-once processing, the outbox, reminders, erasure."""

import threading
from datetime import timedelta

import httpx
import pytest

from fkp.ats import WebhookAdapter
from fkp.dialogue import Inbound
from fkp.engine import Engine
from fkp.privacy import phone_hash
from fkp.store import Store
from fkp.whatsapp import WINDOW_CLOSED, SandboxClient, SendError

from .conftest import T0

pytestmark = pytest.mark.db
PHONE = "4917012345678"


class Flaky(SandboxClient):
    def __init__(self, fail=0, code=None):
        super().__init__()
        self.fail, self.code = fail, code

    def send(self, to, out):
        if self.fail:
            self.fail -= 1
            raise SendError("boom", retryable=self.code is None, code=self.code)
        return super().send(to, out)


def msg(i, text="", button="", at=None, kind=None):
    return Inbound(id=f"wamid.{i}", at=at or T0 + timedelta(minutes=i), kind=kind or ("button" if button else "text"), text=text,
                   button_id=button, profile_name="Ana Popescu")


def run(engine, texts, phone=PHONE, start=0):
    for i, t in enumerate(texts, start):
        engine.inbound("whatsapp", phone, msg(i, *(("", t[1:]) if t.startswith("@") else (t,))))
        engine.deliver(T0 + timedelta(minutes=i, seconds=30))


def outbox(store):
    with store.conn() as c:
        return c.execute("SELECT kind, status, payload, attempts FROM outbox ORDER BY id").fetchall()


def test_webhook_retries_are_processed_once(store):
    wa = SandboxClient()
    e = Engine(store, {"whatsapp": wa})
    assert e.inbound("whatsapp", PHONE, msg(1, "Bună, sunt sudor"))["status"] == "processed"
    assert e.inbound("whatsapp", PHONE, msg(1, "Bună, sunt sudor"))["status"] == "duplicate"
    e.deliver(T0 + timedelta(minutes=2))
    assert len(wa.sent) == 1 and wa.sent[0][1]["type"] == "interactive"


def test_concurrent_messages_from_one_person_are_serialised(store):
    e = Engine(store, {"whatsapp": SandboxClient()})
    e.inbound("whatsapp", PHONE, msg(0, "Hallo"))
    e.inbound("whatsapp", PHONE, msg(1, button="consent_yes"))
    texts = ["Elektriker", "wohne in 80331 München", "ab sofort", "früh", "B1", "3 Jahre"]
    threads = [threading.Thread(target=e.inbound, args=("whatsapp", PHONE, msg(10 + i, t))) for i, t in enumerate(texts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with store.conn() as c:
        n = c.execute("SELECT count(*) AS n FROM messages WHERE direction = 'in'").fetchone()["n"]
        conv = Store.get_conversation(c, "whatsapp", PHONE)
    assert n == 8
    assert conv.profile["occupation"].value == ["elektroniker"]  # no lost update


def test_full_flow_hands_over_through_the_ats_webhook(store):
    got = []

    def handler(req):
        got.append(req)
        return httpx.Response(200)

    ats = WebhookAdapter("https://ats.example/hook", "s3cret", transport=httpx.MockTransport(handler))
    e = Engine(store, {"whatsapp": SandboxClient()}, ats)
    run(e, ["J-LKW-LEJ: LKW-Fahrer mit CE und Code 95, wohne in 04315 Leipzig", "@consent_yes", "ab 1.12.",
            "früh und spät, keine Nacht", "8 Jahre", "@confirm_yes", "ana@mail.example"])
    e.deliver(T0 + timedelta(hours=1))
    assert len(got) == 1
    import json
    body = json.loads(got[0].content)["data"]
    assert body["job_id"] == "J-LKW-LEJ" and body["verdict"] == "fit" and body["email"] == "ana@mail.example"
    assert body["profile"]["licences"]["evidence"] and "Code 95" in body["summary"]
    assert got[0].headers["X-FKP-Signature"].startswith("sha256=")


def test_retries_with_backoff_then_gives_up(store):
    wa = Flaky(fail=2)
    e = Engine(store, {"whatsapp": wa})
    e.inbound("whatsapp", PHONE, msg(0, "Hallo"))
    assert e.deliver(T0)["retry"] == 1
    assert e.deliver(T0 + timedelta(seconds=10)) == {"sent": 0, "retry": 0, "failed": 0, "expired": 0}  # backoff
    assert e.deliver(T0 + timedelta(seconds=31))["retry"] == 1
    assert e.deliver(T0 + timedelta(minutes=5))["sent"] == 1
    assert outbox(store)[0]["attempts"] == 3


def test_a_crashed_worker_lease_runs_out(store):
    e = Engine(store, {"whatsapp": SandboxClient()})
    e.inbound("whatsapp", PHONE, msg(0, "Hallo"))
    with store.conn() as c:  # a worker claimed the row and died before sending
        c.execute("UPDATE outbox SET attempts = 1, next_attempt_at = %s", (T0 + timedelta(seconds=60),))
    assert e.deliver(T0 + timedelta(seconds=30))["sent"] == 0
    assert e.deliver(T0 + timedelta(seconds=61))["sent"] == 1


def test_free_form_never_leaves_after_the_24_hour_window(store):
    wa = SandboxClient()
    e = Engine(store, {"whatsapp": wa})
    e.inbound("whatsapp", PHONE, msg(0, "Hallo"))
    assert e.deliver(T0 + timedelta(hours=25))["expired"] == 1 and wa.sent == []
    with store.conn() as c:
        assert c.execute("SELECT count(*) AS n FROM events WHERE type = 'window_closed'").fetchone()["n"] == 1


def test_window_closed_error_from_meta_expires_instead_of_retrying(store):
    e = Engine(store, {"whatsapp": Flaky(fail=1, code=WINDOW_CLOSED)})
    e.inbound("whatsapp", PHONE, msg(0, "Hallo"))
    assert e.deliver(T0)["expired"] == 1


def test_reminders_use_the_utility_template_and_skip_opted_out_numbers(store):
    wa = SandboxClient()
    e = Engine(store, {"whatsapp": wa})
    run(e, ["Hallo", "@consent_yes", "Ich bin Maler"])
    assert e.tick(T0 + timedelta(hours=5)) == 0
    assert e.tick(T0 + timedelta(hours=23)) == 1  # inside the window: a normal message
    assert e.tick(T0 + timedelta(hours=23, minutes=5)) == 0  # not twice
    e.deliver(T0 + timedelta(hours=23, minutes=1))
    assert wa.sent[-1][1]["type"] == "text"
    assert e.tick(T0 + timedelta(days=4)) == 1
    e.deliver(T0 + timedelta(days=4, minutes=1))
    t = wa.sent[-1][1]
    assert t["type"] == "template" and t["template"]["name"] == "application_missing_info"
    with store.conn() as c:
        Store.suppress(c, phone_hash(PHONE), "test", T0)
    assert e.tick(T0 + timedelta(days=12)) == 0


def test_stop_erases_messages_and_suppresses_the_number(store):
    e = Engine(store, {"whatsapp": SandboxClient()})
    run(e, ["Hallo, ich bin Koch in Hamburg", "@consent_yes", "Seit der OP habe ich Rückenprobleme", "STOP"])
    with store.conn() as c:
        conv = Store.get_conversation(c, "whatsapp", PHONE)
        inbound = c.execute("SELECT count(*) AS n FROM messages WHERE direction = 'in'").fetchone()["n"]
        assert conv.stage == "deleted" and conv.profile == {} and inbound == 0
        assert Store.suppressed(c, phone_hash(PHONE))
        assert c.execute("SELECT count(*) AS n FROM erasures").fetchone()["n"] == 1
        assert c.execute("SELECT count(*) AS n FROM events WHERE conversation_id IS NOT NULL").fetchone()["n"] == 0
    # writing again starts over and lifts the suppression
    run(e, ["Hallo"], start=20)
    with store.conn() as c:
        assert not Store.suppressed(c, phone_hash(PHONE))


def test_health_text_is_never_stored(store):
    e = Engine(store, {"whatsapp": SandboxClient()})
    run(e, ["Hallo", "@consent_yes", "Ich bin Pflegehelferin. Ich bin schwanger. Ab sofort, in 10247 Berlin."])
    with store.conn() as c:
        bodies = " ".join(r["body"] for r in c.execute("SELECT body FROM messages"))
        state = str(c.execute("SELECT state FROM conversations").fetchone()["state"])
    assert "schwanger" not in bodies and "schwanger" not in state and "[health information removed]" in bodies


def test_retention(store):
    e = Engine(store, {"whatsapp": SandboxClient()})
    run(e, ["Hallo"])  # never consented
    run(e, ["Hallo", "@consent_yes"], phone="4917099999999", start=50)
    assert e.purge(T0 + timedelta(hours=10)) == 0
    assert e.purge(T0 + timedelta(hours=73)) == 1
    assert e.purge(T0 + timedelta(days=200)) == 1
