"""Handing a qualified candidate over to the ATS.

Two adapters: Personio's recruiting API (`POST /v1/recruiting/applications`, which needs first
name, last name, email and a job position id) and a signed JSON webhook for anything else, n8n and
Make included. The hand-over carries the profile with the evidence behind each value, the match
checks and the consent time; never health information or the raw chat.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import httpx

from . import config
from .dialogue import Conversation

RETRYABLE = {408, 429, 500, 502, 503, 504}


class AtsError(Exception):
    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def handover_payload(conv: Conversation, job_id: str, verdict: str, summary: str) -> dict[str, Any]:
    name = (conv.profile["full_name"].value if "full_name" in conv.profile else conv.wa_name).strip()
    first, _, last = name.partition(" ")
    match = next((m for m in conv.matches if m["job_id"] == job_id), None)
    return {
        "conversation_id": conv.id,
        "job_id": job_id,
        "verdict": verdict,
        "first_name": first or "-",
        "last_name": last or "-",
        "email": conv.profile["email"].value if "email" in conv.profile else None,
        "phone": conv.phone,
        "language": conv.lang,
        "consent_at": conv.consent_at,
        "profile": {
            k: {"value": v.value, "evidence": v.evidence, "source": v.source} for k, v in conv.profile.items() if k not in ("email", "full_name")
        },
        "checks": match["checks"] if match else [],
        "summary": summary,
        "application_date": date.fromisoformat(conv.handed_over_at[:10]).isoformat() if conv.handed_over_at else None,
    }


class Adapter(Protocol):
    name: str

    def send(self, p: dict[str, Any]) -> str: ...


@dataclass
class PersonioAdapter:
    token: str
    company_id: str
    positions: dict[str, int]  # our job id -> Personio job_position_id
    base_url: str = "https://api.personio.de"
    transport: httpx.BaseTransport | None = None
    name: str = "personio"

    def send(self, p: dict[str, Any]) -> str:
        if not p.get("email"):
            raise AtsError("Personio needs an email address", retryable=False)
        if p["job_id"] not in self.positions:
            raise AtsError(f"no Personio position for job {p['job_id']}", retryable=False)
        body = {
            "first_name": p["first_name"],
            "last_name": p["last_name"],
            "email": p["email"],
            "job_position_id": self.positions[p["job_id"]],
            "message": p["summary"][:5000],
            "tags": ["whatsapp", f"lang:{p['language']}", f"match:{p['verdict']}"],
        }
        if p.get("application_date"):
            body["application_date"] = p["application_date"]
        headers = {"Authorization": f"Bearer {self.token}", "X-Company-ID": self.company_id, "Accept": "application/json"}
        try:
            with httpx.Client(transport=self.transport, timeout=15) as client:
                r = client.post(f"{self.base_url}/v1/recruiting/applications", json=body, headers=headers)
        except httpx.HTTPError as e:
            raise AtsError(f"network: {e}", retryable=True) from e
        if r.status_code in (200, 201):
            data = r.json() if r.content else {}
            return str((data.get("data") or {}).get("id") or data.get("id") or "created")
        raise AtsError(f"Personio {r.status_code}: {r.text[:200]}", retryable=r.status_code in RETRYABLE)


@dataclass
class WebhookAdapter:
    url: str
    secret: str
    transport: httpx.BaseTransport | None = None
    name: str = "webhook"

    def send(self, p: dict[str, Any]) -> str:
        raw = json.dumps({"type": "candidate.handover", "data": p}, ensure_ascii=False, sort_keys=True).encode()
        sig = "sha256=" + hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()
        key = f"{p.get('conversation_id')}:{p.get('job_id') or p.get('event')}:{p.get('at', '')}"
        try:
            with httpx.Client(transport=self.transport, timeout=15) as client:
                r = client.post(self.url, content=raw, headers={"Content-Type": "application/json", "X-FKP-Signature": sig, "Idempotency-Key": key})
        except httpx.HTTPError as e:
            raise AtsError(f"network: {e}", retryable=True) from e
        if 200 <= r.status_code < 300:
            return key
        raise AtsError(f"webhook {r.status_code}", retryable=r.status_code in RETRYABLE or r.status_code >= 500)


def required_fields(adapter: Adapter) -> list[str]:
    return ["full_name", "email"] if adapter.name == "personio" else list(config.settings()["conversation"]["fields_for_handover"])
