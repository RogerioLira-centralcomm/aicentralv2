-- Apply after add_cadu_family.sql and add_cadu_chat_request_hash.sql.
-- Additive only: no existing conversations, files or links are changed.
CREATE TABLE IF NOT EXISTS cadu_family_chat_jobs (
    run_id UUID PRIMARY KEY REFERENCES cadu_family_chat_runs(id),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cadu_chat_jobs_pending
    ON cadu_family_chat_jobs(created_at) WHERE claimed_at IS NULL;
CREATE TABLE IF NOT EXISTS cadu_family_chat_events (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_family_chat_runs(id),
    event JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_chat_events_replay
    ON cadu_family_chat_events(run_id, id);
