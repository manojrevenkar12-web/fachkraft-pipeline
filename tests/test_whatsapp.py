import hashlib
import hmac
import json

import httpx
import pytest

from fkp import config, whatsapp
from fkp.dialogue import Outgoing


def test_signature():
    body = b'{"x":1}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    whatsapp.verify_signature("secret", body, sig)
    for secret, s in (("secret", "sha256=00"), ("", sig), ("other", sig)):
        with pytest.raises(whatsapp.SignatureError):
            whatsapp.verify_signature(secret, body, s)


def test_parse_webhook_messages_buttons_media_and_statuses():
    doc = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "4917000", "profile": {"name": "Ana Popescu"}}],
        "messages": [
            {"from": "4917000", "id": "wamid.1", "timestamp": "1793000000", "type": "text", "text": {"body": "Bună"}},
            {"from": "4917000", "id": "wamid.2", "timestamp": "1793000001", "type": "interactive",
             "interactive": {"type": "button_reply", "button_reply": {"id": "consent_yes", "title": "Da"}}},
            {"from": "4917000", "id": "wamid.3", "timestamp": "1793000002", "type": "audio", "audio": {"id": "m"}},
            {"from": "4917000", "id": "wamid.4", "timestamp": "1793000003", "type": "image", "image": {"id": "i", "caption": "atestat"}},
        ],
        "statuses": [{"id": "wamid.out", "status": "delivered", "timestamp": "1793000004",
                      "pricing": {"billable": True, "category": "utility", "pricing_model": "PMP"}}],
    }}]}]}
    b = whatsapp.parse_webhook(doc)
    kinds = [(p, m.kind, m.text, m.button_id, m.profile_name) for p, m in b.messages]
    assert kinds[0] == ("4917000", "text", "Bună", "", "Ana Popescu")
    assert kinds[1][1:4] == ("button", "", "consent_yes")
    assert kinds[2][1] == "audio" and kinds[3][1:3] == ("image", "atestat")
    assert b.statuses[0].category == "utility" and b.statuses[0].billable


def test_payloads_follow_the_platform_limits():
    p = whatsapp.payload("49170", Outgoing("buttons", "Ok?", "x", [("a", "Ja"), ("b", "Nein")]))
    assert p["interactive"]["action"]["buttons"][0] == {"type": "reply", "reply": {"id": "a", "title": "Ja"}}
    with pytest.raises(ValueError):
        whatsapp.payload("49170", Outgoing("buttons", "Ok?", "x", [("a", "x" * 21)]))
    with pytest.raises(ValueError):
        whatsapp.payload("49170", Outgoing("buttons", "Ok?", "x", [("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")]))
    t = whatsapp.payload("49170", Outgoing("template", "...", "r", template={"name": "application_missing_info", "language": "pl", "params": ["A", "B"]}))
    assert t["template"]["language"] == {"code": "pl"} and [x["text"] for x in t["template"]["components"][0]["parameters"]] == ["A", "B"]


def test_every_button_title_in_every_language_fits():
    for lang, m in config.messages().items():
        for key in ("consent_yes", "consent_no", "confirm_yes", "confirm_fix", "pool_yes", "pool_no"):
            assert len(m[key]) <= whatsapp.MAX_BUTTON_TITLE, (lang, key, m[key])


def test_reminder_template_text_is_pure_utility():
    """One promotional sentence makes Meta bill a utility template as marketing."""
    promo = ["angebot", "jetzt bewerben", "bonus", "prämie", "gehalt", "offer", "apply now", "salary", "€", "!"]
    for lang, m in config.messages().items():
        assert not any(p in m["reminder"].lower() for p in promo), lang


def test_client_errors_are_classified():
    def handler(req):
        body = json.loads(req.content)
        if body["to"] == "1":
            return httpx.Response(200, json={"messages": [{"id": "wamid.ok"}]})
        if body["to"] == "2":
            return httpx.Response(429, json={"error": {"code": 4, "message": "rate"}})
        return httpx.Response(400, json={"error": {"code": 131047, "message": "Re-engagement message"}})

    c = whatsapp.CloudApiClient("123", "t", transport=httpx.MockTransport(handler))
    assert c.send("1", Outgoing("text", "hi", "x")) == "wamid.ok"
    with pytest.raises(whatsapp.SendError) as e:
        c.send("2", Outgoing("text", "hi", "x"))
    assert e.value.retryable
    with pytest.raises(whatsapp.SendError) as e:
        c.send("3", Outgoing("text", "hi", "x"))
    assert not e.value.retryable and e.value.code == whatsapp.WINDOW_CLOSED
