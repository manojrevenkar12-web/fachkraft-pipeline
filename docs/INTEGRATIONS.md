# Integrations

## WhatsApp Business Platform (Cloud API)

| Setting | Meaning |
|---|---|
| `FKP_WA_TOKEN`, `FKP_WA_PHONE_NUMBER_ID` | sending (Graph API version in `config/settings.yaml`) |
| `FKP_WA_APP_SECRET` | verifies `X-Hub-Signature-256` on every webhook |
| `FKP_WA_VERIFY_TOKEN` | answers Meta's subscription challenge |

Subscribe the webhook `https://<api host>/webhooks/whatsapp` to `messages`. Create two templates:
`application_missing_info` (utility; parameters: company, missing items) and
`talent_pool_new_job` (marketing; only for candidates who joined the pool).

## Personio

`FKP_PERSONIO_TOKEN`, `FKP_PERSONIO_COMPANY_ID` and `FKP_PERSONIO_POSITIONS` (JSON map from our
job id to Personio's `job_position_id`). A hand-over becomes `POST /v1/recruiting/applications`
with first name, last name, email, the position, tags (`whatsapp`, `lang:xx`, `match:fit|near`)
and the summary as the message. Name and email are asked in the chat only when a job fits.

## Any ATS, n8n or Make: signed webhook

`FKP_ATS_WEBHOOK_URL` and `FKP_ATS_WEBHOOK_SECRET` for hand-overs; `FKP_EVENTS_WEBHOOK_URL` and
`FKP_EVENTS_WEBHOOK_SECRET` for events (`handover`, `human_requested`, `pooled`, `deleted`).

```http
POST /your/endpoint
Content-Type: application/json
X-FKP-Signature: sha256=<hex HMAC-SHA256 of the raw body with the secret>
Idempotency-Key: <conversation id>:<job id>:

{"type": "candidate.handover", "data": {"conversation_id": "…", "job_id": "J-LKW-LEJ", "verdict": "fit",
 "first_name": "…", "last_name": "…", "email": "…", "phone": "…", "language": "tr", "consent_at": "…",
 "profile": {"licences": {"value": ["B", "C", "CE", "code95"], "evidence": "CE und Code 95", "source": "rules"}, …},
 "checks": [{"name": "licences", "status": "pass", "detail": "CE, code95"}, …], "summary": "…", "application_date": "2026-10-26"}}
```

Verify the signature over the raw bytes before parsing, answer 2xx, and use the idempotency key to
ignore repeats: the outbox retries until it gets a 2xx (429 and 5xx back off; other 4xx stop).

`integrations/n8n/handover.json` is an n8n workflow that does exactly this and appends the
candidate to a Google Sheet; import it, set the secret in the Crypto node and pick the sheet.
