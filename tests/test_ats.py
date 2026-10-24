"""ATS adapters against a mock HTTP transport: what is sent, and which failures are retried."""

import hashlib
import hmac
import json

import httpx
import pytest

from fkp.ats import AtsError, PersonioAdapter, WebhookAdapter

PAYLOAD = {
    "conversation_id": "c1",
    "job_id": "J-LKW-LEJ",
    "verdict": "fit",
    "first_name": "Mehmet",
    "last_name": "Kaya",
    "email": "mehmet.kaya@mail.example",
    "phone": "4917000000",
    "language": "tr",
    "consent_at": "2026-10-26T09:00:00+00:00",
    "profile": {},
    "checks": [],
    "summary": "Berufskraftfahrer, CE, Code 95",
    "application_date": "2026-10-26",
}


def personio(handler):
    return PersonioAdapter("tok", "42", {"J-LKW-LEJ": 1234}, transport=httpx.MockTransport(handler))


def test_personio_application_has_the_required_fields_and_headers():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["headers"], seen["body"] = str(req.url), req.headers, json.loads(req.content)
        return httpx.Response(201, json={"data": {"id": 987}})

    assert personio(handler).send(PAYLOAD) == "987"
    assert seen["url"] == "https://api.personio.de/v1/recruiting/applications"
    assert seen["headers"]["authorization"] == "Bearer tok" and seen["headers"]["x-company-id"] == "42"
    body = seen["body"]
    assert (body["first_name"], body["last_name"], body["email"], body["job_position_id"]) == ("Mehmet", "Kaya", "mehmet.kaya@mail.example", 1234)
    assert "lang:tr" in body["tags"] and body["application_date"] == "2026-10-26"


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (422, False), (401, False)])
def test_personio_failures_are_classified(status, retryable):
    with pytest.raises(AtsError) as e:
        personio(lambda req: httpx.Response(status, text="nope")).send(PAYLOAD)
    assert e.value.retryable is retryable


def test_personio_refuses_without_email_or_position():
    with pytest.raises(AtsError) as e:
        personio(lambda req: httpx.Response(201)).send({**PAYLOAD, "email": None})
    assert not e.value.retryable
    with pytest.raises(AtsError):
        personio(lambda req: httpx.Response(201)).send({**PAYLOAD, "job_id": "J-UNKNOWN"})


def test_network_errors_are_retried():
    def boom(req):
        raise httpx.ConnectError("down")

    with pytest.raises(AtsError) as e:
        personio(boom).send(PAYLOAD)
    assert e.value.retryable


def test_webhook_is_signed_and_idempotent():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["raw"], seen["headers"] = req.content, req.headers
        return httpx.Response(204)

    key = WebhookAdapter("https://hooks.example/fkp", "s3cret", transport=httpx.MockTransport(handler)).send(PAYLOAD)
    expected = "sha256=" + hmac.new(b"s3cret", seen["raw"], hashlib.sha256).hexdigest()
    assert seen["headers"]["x-fkp-signature"] == expected
    assert seen["headers"]["idempotency-key"] == key == "c1:J-LKW-LEJ:"
    assert json.loads(seen["raw"])["type"] == "candidate.handover"
