import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from fkp.api import create_app
from fkp.engine import Engine
from fkp.whatsapp import SandboxClient

from .conftest import T0

pytestmark = pytest.mark.db
ADMIN, REC, READ = "a" * 20, "r" * 20, "v" * 20
H = {k: {"Authorization": f"Bearer {v}"} for k, v in (("admin", ADMIN), ("rec", REC), ("read", READ))}


@pytest.fixture
def env(store, monkeypatch):
    monkeypatch.setenv("FKP_API_KEYS", f"{ADMIN}:admin,{REC}:recruiter,{READ}:reader,short:admin")
    monkeypatch.setenv("FKP_WA_APP_SECRET", "app-secret")
    monkeypatch.setenv("FKP_WA_VERIFY_TOKEN", "verify-me")
    clock = {"now": T0}
    wa = SandboxClient()
    engine = Engine(store, {"whatsapp": wa, "sandbox": SandboxClient()})
    client = TestClient(create_app(store, engine, clock=lambda: clock["now"], sandbox=True))
    return client, engine, wa, clock


def signed(doc):
    raw = json.dumps(doc).encode()
    return raw, {"X-Hub-Signature-256": "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest(), "Content-Type": "application/json"}


def wa_doc(i, text="", button=""):
    m = {"from": "4917055501234", "id": f"wamid.api.{i}", "timestamp": str(int((T0 + timedelta(minutes=i)).timestamp()))}
    m.update({"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": button, "title": "x"}}} if button
             else {"type": "text", "text": {"body": text}})
    return {"entry": [{"changes": [{"value": {"contacts": [{"wa_id": "4917055501234", "profile": {"name": "Ion Popa"}}], "messages": [m]}}]}]}


def test_auth_and_webhook_verification(env):
    c, *_ = env
    assert c.get("/healthz").status_code == 200 and c.get("/readyz").json() == {"status": "ready"}
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/api/jobs", headers={"Authorization": "Bearer short"}).status_code == 401
    assert c.post("/api/jobs", json={"job": {}}, headers=H["read"]).status_code == 403
    ok = c.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.text == "42"
    assert c.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"}).status_code == 403


def test_webhook_signature_and_flow(env):
    c, engine, wa, _ = env
    raw, hdr = signed(wa_doc(1, "Bună, sunt sudor în Dortmund"))
    assert c.post("/webhooks/whatsapp", content=raw, headers={**hdr, "X-Hub-Signature-256": "sha256=00"}).status_code == 401
    assert c.post("/webhooks/whatsapp", content=raw, headers=hdr).json() == {"messages": 1, "statuses": 0}
    assert c.post("/webhooks/whatsapp", content=raw, headers=hdr).status_code == 200  # Meta's retry is a no-op
    raw, hdr = signed(wa_doc(2, button="consent_yes"))
    c.post("/webhooks/whatsapp", content=raw, headers=hdr)
    engine.deliver(T0 + timedelta(minutes=3))
    assert len(wa.sent) == 2 and wa.sent[0][1]["type"] == "interactive"
    [cand] = c.get("/api/candidates", headers=H["read"]).json()
    assert cand["lang"] == "ro" and cand["name"] == "Ion Popa" and cand["occupation"] == ["schweisser"]
    detail = c.get(f"/api/candidates/{cand['id']}", headers=H["read"]).json()
    assert detail["profile"]["occupation"]["evidence"] == "sudor" and detail["consent_at"]
    assert sorted(m["direction"] for m in detail["messages"]) == ["in", "in", "out", "out"]


def test_jobs_with_agg_block_and_override(env):
    c, *_ = env
    job = {"id": "J-NEW", "title": "Lagerhelfer", "occupation": "lagerlogistik", "plz": "44135", "start_by": "2026-12-31",
           "text": "Wir suchen junge, dynamische Leute. Deutsch als Muttersprache."}
    r = c.post("/api/jobs", json={"job": job}, headers=H["rec"])
    assert r.status_code == 422 and {i["rule"] for i in r.json()["detail"]["issues"]} == {"age", "origin-native-language"}
    lint = c.post("/api/jobs/lint", json=job, headers=H["read"]).json()
    assert "gender-title" in {i["rule"] for i in lint}
    fixed = {**job, "title": "Lagerhelfer (m/w/d)", "text": "Wareneingang im Team. Deutsch B1 für Sicherheitsunterweisungen."}
    saved = c.post("/api/jobs", json={"job": fixed}, headers=H["rec"]).json()
    assert saved["agg"] == [] and any(j["id"] == "J-NEW" for j in c.get("/api/jobs", headers=H["read"]).json())
    assert c.post("/api/jobs", json={"job": {**job, "occupation": "astronaut"}}, headers=H["rec"]).status_code == 422
    assert c.patch("/api/jobs/J-NEW", json={"open": False}, headers=H["rec"]).json() == {"id": "J-NEW", "open": False}


def test_recruiter_reply_respects_the_window_and_erasure_works(env):
    c, engine, wa, clock = env
    r = c.post("/api/sandbox/4915550001111/messages", json={"text": "Hallo, ich bin Maler in Hamburg", "name": "Lea Weiß"}, headers=H["read"])
    cid = r.json()["conversation_id"]
    assert r.json()["transcript"][-1]["buttons"][0]["id"] == "consent_yes"
    clock["now"] = T0 + timedelta(minutes=5)
    assert c.post(f"/api/candidates/{cid}/messages", json={"text": "Hallo Lea!"}, headers=H["rec"]).json() == {"queued": True}
    clock["now"] = T0 + timedelta(hours=30)
    assert c.post(f"/api/candidates/{cid}/messages", json={"text": "Noch da?"}, headers=H["rec"]).status_code == 409
    export = c.get(f"/api/candidates/{cid}/export", headers=H["rec"]).json()
    assert export["messages"] and export["exported_at"]
    assert c.delete(f"/api/candidates/{cid}", headers=H["read"]).status_code == 403
    assert c.delete(f"/api/candidates/{cid}", headers=H["rec"]).json() == {"deleted": True}
    assert c.get(f"/api/candidates/{cid}", headers=H["read"]).status_code == 404


def test_sandbox_conversation_and_metrics(env):
    c, *_ = env
    phone = "4915550002222"
    for step in ({"text": "Hello, J-ELE-MUC"}, {"button_id": "consent_yes"}, {"text": "I'm an electrician in 80331 Munich, available immediately"},
                 {"text": "early shift"}, {"text": "German B2"}, {"text": "6 years"}, {"button_id": "confirm_yes"}, {"text": "sam@mail.example"}):
        r = c.post(f"/api/sandbox/{phone}/messages", json={**step, "name": "Sam Lee"}, headers=H["read"]).json()
    assert r["stage"] == "handed_over"
    assert "You fit" in r["transcript"][-1]["body"]
    m = c.get("/api/metrics", headers=H["read"]).json()
    assert m["funnel"]["handed_over"] == 1 and m["funnel"]["confirmed"] == 1 and m["languages"] == {"en": 1}
    assert c.post("/api/sandbox/abc/messages", json={"text": "x"}, headers=H["read"]).status_code == 422
