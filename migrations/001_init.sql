-- One row per phone number and channel: a conversation is restarted, not duplicated.
CREATE TABLE conversations (
    id              text PRIMARY KEY,
    channel         text NOT NULL CHECK (channel IN ('whatsapp', 'sandbox')),
    phone           text NOT NULL,
    lang            text NOT NULL DEFAULT 'de',
    stage           text NOT NULL,
    job_id          text,
    state           jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    last_inbound_at timestamptz,
    consent_at      timestamptz,
    handed_over_at  timestamptz,
    pool_until      timestamptz,
    UNIQUE (channel, phone)
);
CREATE INDEX conversations_stage ON conversations (stage, updated_at);

-- Inbound messages are deduplicated by the channel's message id (WhatsApp retries webhooks).
CREATE TABLE messages (
    id              bigserial PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    direction       text NOT NULL CHECK (direction IN ('in', 'out')),
    channel_id      text,
    kind            text NOT NULL,
    body            text NOT NULL DEFAULT '',
    purpose         text,
    status          text,
    category        text,
    cost_usd        numeric(10, 4) NOT NULL DEFAULT 0,
    at              timestamptz NOT NULL,
    redacted        boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX messages_channel_id ON messages (direction, channel_id) WHERE channel_id IS NOT NULL;
CREATE INDEX messages_conversation ON messages (conversation_id, at);

-- Everything that leaves the system goes through here: chat messages, ATS hand-overs, webhooks.
CREATE TABLE outbox (
    id              bigserial PRIMARY KEY,
    conversation_id text REFERENCES conversations (id) ON DELETE CASCADE,
    kind            text NOT NULL CHECK (kind IN ('message', 'ats', 'webhook')),
    payload         jsonb NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'expired')),
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error      text,
    external_id     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    sent_at         timestamptz
);
CREATE INDEX outbox_due ON outbox (next_attempt_at) WHERE status = 'pending';

CREATE TABLE events (
    id              bigserial PRIMARY KEY,
    conversation_id text REFERENCES conversations (id) ON DELETE CASCADE,
    type            text NOT NULL,
    data            jsonb NOT NULL DEFAULT '{}',
    at              timestamptz NOT NULL
);
CREATE INDEX events_type ON events (type, at);

CREATE TABLE jobs (
    id         text PRIMARY KEY,
    data       jsonb NOT NULL,
    open       boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Numbers that said stop. Only a salted hash is kept, so the list holds no personal data but a
-- number on it is never messaged first again.
CREATE TABLE suppression (
    phone_hash text PRIMARY KEY,
    reason     text NOT NULL,
    at         timestamptz NOT NULL
);

-- Deletions are recorded without personal data, to show that erasure happened and when.
CREATE TABLE erasures (
    id        bigserial PRIMARY KEY,
    reason    text NOT NULL,
    at        timestamptz NOT NULL
);
