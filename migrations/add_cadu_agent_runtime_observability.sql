ALTER TABLE cadu_family_chat_runs
    ADD COLUMN IF NOT EXISTS execution_mode VARCHAR(16) NOT NULL DEFAULT 'analysis',
    ADD COLUMN IF NOT EXISTS runtime_id VARCHAR(40),
    ADD COLUMN IF NOT EXISTS provider_config_version VARCHAR(40),
    ADD COLUMN IF NOT EXISTS provider_duration_ms INTEGER,
    ADD COLUMN IF NOT EXISTS input_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS output_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS charged_credits INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS estimated_cost_usd NUMERIC(14,6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS terminal_error_code VARCHAR(80);

CREATE TABLE IF NOT EXISTS cadu_agent_turn_events (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_family_chat_runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    item_type VARCHAR(40) NOT NULL DEFAULT 'activity',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_cadu_agent_turn_events_run
    ON cadu_agent_turn_events (run_id, sequence);

CREATE TABLE IF NOT EXISTS cadu_agent_run_steps (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_family_chat_runs(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    kind VARCHAR(32) NOT NULL,
    name VARCHAR(160),
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code VARCHAR(80),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    UNIQUE (run_id, position),
    CHECK (status IN ('pending','waiting_confirmation','running','completed','failed','cancelled'))
);
CREATE INDEX IF NOT EXISTS idx_cadu_agent_run_steps_run
    ON cadu_agent_run_steps (run_id, position);

CREATE TABLE IF NOT EXISTS cadu_agent_checkpoints (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_family_chat_runs(id) ON DELETE CASCADE,
    step_id UUID REFERENCES cadu_agent_run_steps(id) ON DELETE SET NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_agent_checkpoints_run
    ON cadu_agent_checkpoints (run_id, created_at DESC);

ALTER TABLE cadu_agent_run_steps
    ADD COLUMN IF NOT EXISTS decided_by BIGINT,
    ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS decision_note TEXT;

CREATE TABLE IF NOT EXISTS cadu_agent_provider_sessions (
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    runtime_id VARCHAR(40) NOT NULL,
    provider_conversation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (conversation_id, runtime_id)
);
CREATE INDEX IF NOT EXISTS idx_cadu_agent_provider_sessions_scope
    ON cadu_agent_provider_sessions (client_id, user_id, updated_at DESC);
