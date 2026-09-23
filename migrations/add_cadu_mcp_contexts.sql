-- Explicit application context for stateless MCP 2026-07-28 requests.
CREATE TABLE IF NOT EXISTS cadu_mcp_contexts (
    id UUID PRIMARY KEY,
    handle_hash CHAR(64) NOT NULL UNIQUE,
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    credential_type VARCHAR(24) NOT NULL DEFAULT 'internal',
    credential_id VARCHAR(160),
    client_type VARCHAR(40) NOT NULL DEFAULT 'internal',
    exposure VARCHAR(32) NOT NULL,
    conversation_id UUID,
    surface VARCHAR(40) NOT NULL DEFAULT 'conversations',
    project_ref VARCHAR(160),
    brand_ref VARCHAR(160),
    active_object JSONB,
    label VARCHAR(120),
    status VARCHAR(24) NOT NULL DEFAULT 'active',
    sequence BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
    closed_at TIMESTAMPTZ,
    CHECK (status IN ('active','closed','expired'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_mcp_contexts_scope
    ON cadu_mcp_contexts (client_id, user_id, status, last_used_at DESC);

CREATE TABLE IF NOT EXISTS cadu_mcp_context_events (
    id BIGSERIAL PRIMARY KEY,
    context_id UUID NOT NULL REFERENCES cadu_mcp_contexts(id) ON DELETE CASCADE,
    sequence BIGINT NOT NULL,
    operation_id UUID,
    tool_name VARCHAR(120) NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    terminal_state VARCHAR(24) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (context_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_cadu_mcp_context_events_recent
    ON cadu_mcp_context_events (context_id, sequence DESC);

ALTER TABLE cadu_mcp_operations
    ADD COLUMN IF NOT EXISTS context_id UUID REFERENCES cadu_mcp_contexts(id),
    ADD COLUMN IF NOT EXISTS conversation_id UUID,
    ADD COLUMN IF NOT EXISTS tool_call_id UUID,
    ADD COLUMN IF NOT EXISTS credential_id VARCHAR(160),
    ADD COLUMN IF NOT EXISTS duration_ms INTEGER,
    ADD COLUMN IF NOT EXISTS terminal_state VARCHAR(24);
