# Runbook

## Signals

| Signal | Where | Normal | Look at |
|---|---|---|---|
| Outbox backlog | `SELECT status, count(*) FROM outbox GROUP BY 1` | `pending` drains within a minute | worker logs, WhatsApp/ATS status |
| Expired messages | `/api/metrics` → `window_closed` | a few per day (candidates who went quiet) | a spike means the worker was down for hours |
| Failed rows | `outbox.status = 'failed'` | zero | `last_error`; 4xx from the ATS are not retried |
| Delivery failures | `events.type = 'delivery_failed'` | rare | WhatsApp error code in `data.code` |
| Cost | `/api/metrics` → `messages` | utility templates, service beyond 1,000 a month | marketing category on a utility template means Meta recategorised it |

## Incidents

**WhatsApp webhook returns 401.** The app secret changed or the request is not from Meta. Check
`FKP_WA_APP_SECRET` against the app dashboard; nothing is processed until it matches, and Meta
retries for a while, so nothing is lost if fixed promptly.

**Outbox backlog grows.** Check the worker is running (`fkp worker`). Rows with an expired lease
come back by themselves. If the ATS answers 429, rows back off up to an hour; that is intended.

**A template is rejected or recategorised.** Utility templates must not promote anything. Keep
`application_missing_info` to the missing items and the company name; re-submit through Meta.

**A candidate asks what is stored.** `GET /api/candidates/{id}/export` (recruiter role).
**A candidate asks for deletion.** "stop" in the chat, or `DELETE /api/candidates/{id}`; the number
is kept only as a salted hash so no reminder reaches it.

**Database restore or failover.** Connections are checked before use and reconnect. Inbound
messages are deduplicated by WhatsApp id, so replaying webhooks after a restore is safe.

## Releases

1. `pytest -q` and `cd web && npm test` green; `fkp eval` unchanged or the change explained.
2. If extraction, matching or the AGG check changed: run the held-out sets and record the
   latest run; never edit a first run.
3. Apply migrations (`fkp migrate`, the Kubernetes job does it), then roll the API and workers.
