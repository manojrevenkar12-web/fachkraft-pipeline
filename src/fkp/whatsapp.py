"""The WhatsApp Business Platform (Cloud API): webhooks in, messages out, and its rules.

Rules the sender enforces, not just documents:

* Free-form messages only within 24 hours of the candidate's last message. After that only an
  approved template, and only for what it was approved for: reminders are a *utility* template
  with nothing promotional in it (one promotional sentence makes Meta reclassify it as marketing,
  at 2.5 times the price in Germany).
* Interactive reply buttons: at most 3, titles at most 20 characters.
* Webhooks are authenticated by the X-Hub-Signature-256 HMAC of the raw body with the app secret,
  and deduplicated by message id, because Meta retries deliveries.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from .dialogue import Inbound, Outgoing

MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20
RETRYABLE = {429, 500, 502, 503, 504}
WINDOW_CLOSED = 131047  # "Re-engagement message": more than 24 hours since the user replied


class SignatureError(ValueError):
    pass


class SendError(Exception):
    def __init__(self, message: str, retryable: bool, code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


def verify_signature(app_secret: str, body: bytes, header: str) -> None:
    if not app_secret:
        raise SignatureError("no app secret configured")
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, header or ""):
        raise SignatureError("signature mismatch")


@dataclass
class Status:
    message_id: str
    status: str  # sent, delivered, read, failed
    at: datetime
    category: str | None = None
    billable: bool | None = None
    error_code: int | None = None


@dataclass
class WebhookBatch:
    messages: list[tuple[str, Inbound]] = field(default_factory=list)  # (phone, message)
    statuses: list[Status] = field(default_factory=list)


def parse_webhook(doc: dict[str, Any]) -> WebhookBatch:
    out = WebhookBatch()
    for entry in doc.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                at = datetime.fromtimestamp(int(m.get("timestamp", "0")), UTC)
                typ = m.get("type", "text")
                phone = m.get("from", "")
                msg = Inbound(id=m["id"], at=at, kind="text", profile_name=names.get(phone, ""))
                if typ == "text":
                    msg.text = (m.get("text") or {}).get("body", "")
                elif typ == "interactive":
                    inter = m.get("interactive") or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    msg.kind, msg.button_id = "button", reply.get("id", "")
                    msg.text = reply.get("title", "") if not msg.button_id else ""
                elif typ == "button":  # quick reply on a template
                    b = m.get("button") or {}
                    msg.kind, msg.button_id, msg.text = "button", b.get("payload", ""), b.get("text", "")
                elif typ in ("audio", "voice"):
                    msg.kind = "audio"
                elif typ in ("image", "document", "video"):
                    msg.kind = "document" if typ == "document" else "image"
                    msg.text = (m.get(typ) or {}).get("caption", "")
                else:
                    msg.kind = "unsupported"
                out.messages.append((phone, msg))
            for s in value.get("statuses", []):
                pricing = s.get("pricing") or {}
                errors = s.get("errors") or [{}]
                out.statuses.append(
                    Status(
                        message_id=s.get("id", ""),
                        status=s.get("status", ""),
                        at=datetime.fromtimestamp(int(s.get("timestamp", "0")), UTC),
                        category=pricing.get("category"),
                        billable=pricing.get("billable"),
                        error_code=errors[0].get("code") if s.get("status") == "failed" else None,
                    )
                )
    return out


def payload(to: str, out: Outgoing) -> dict[str, Any]:
    """The Graph API request body for one outgoing message."""
    base: dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if out.kind == "template":
        t = out.template or {}
        return {
            **base,
            "type": "template",
            "template": {
                "name": t["name"],
                "language": {"code": t.get("language", "de")},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in t.get("params", [])]}],
            },
        }
    if out.kind == "buttons":
        if len(out.buttons) > MAX_BUTTONS:
            raise ValueError("WhatsApp allows at most 3 reply buttons")
        for _, title in out.buttons:
            if len(title) > MAX_BUTTON_TITLE:
                raise ValueError(f"button title longer than {MAX_BUTTON_TITLE} characters: {title!r}")
        return {
            **base,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": out.body[:1024]},
                "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": t}} for i, t in out.buttons]},
            },
        }
    return {**base, "type": "text", "text": {"body": out.body[:4096], "preview_url": False}}


class CloudApiClient:
    def __init__(
        self,
        phone_number_id: str,
        token: str,
        graph_version: str = "v21.0",
        base_url: str = "https://graph.facebook.com",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.url = f"{base_url}/{graph_version}/{phone_number_id}/messages"
        self.client = httpx.Client(timeout=timeout, transport=transport, headers={"Authorization": f"Bearer {token}"})

    def send(self, to: str, out: Outgoing) -> str:
        try:
            r = self.client.post(self.url, json=payload(to, out))
        except httpx.HTTPError as e:
            raise SendError(f"network: {e}", retryable=True) from e
        if r.status_code == 200:
            return str(r.json()["messages"][0]["id"])
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        code = err.get("code")
        raise SendError(f"{r.status_code} {err.get('message', r.text[:200])}", retryable=r.status_code in RETRYABLE, code=code)


class SandboxClient:
    """The demo and test channel: records what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def send(self, to: str, out: Outgoing) -> str:
        body = payload(to, out)
        self.sent.append((to, body))
        return f"sandbox.{uuid.uuid4().hex}"
