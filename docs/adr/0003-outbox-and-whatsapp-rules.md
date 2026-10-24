# 0003: Postgres outbox, with WhatsApp's rules checked at send time

Status: accepted

## Context

A webhook can arrive twice; two messages from one person can arrive at once; a send can fail
after the database committed; WhatsApp refuses free-form messages outside the 24-hour window
(error 131047) and bills templates by category.

## Decision

- One transaction per inbound message: dedupe by the WhatsApp message id, an advisory lock per
  phone number, the conversation state, the stored message, events, and outbox rows for every
  reply, hand-over and event webhook, each with an idempotency key.
- Workers claim outbox rows with `FOR UPDATE SKIP LOCKED` and a 60-second lease, send outside the
  transaction, retry with exponential backoff (at most 8 attempts), and mark a row `expired`
  when the window has closed or WhatsApp answers 131047. The window is checked again at send
  time because a reply queued at minute 1,439 may leave at minute 1,441.
- Reminders are free-form inside the window and the utility template outside it, never in quiet
  hours, on Sundays or public holidays (national plus the configured state).

## Consequences

Any number of API and worker replicas. No message is sent twice and none is lost when a worker
dies; a message that can no longer be sent legally is expired, visible in the metrics.
