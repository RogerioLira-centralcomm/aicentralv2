CREATE TABLE IF NOT EXISTS cadu_agent_improvements (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    title VARCHAR(180) NOT NULL,
    rationale TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommendation TEXT NOT NULL,
    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
    confidence NUMERIC(5,4),
    status VARCHAR(24) NOT NULL DEFAULT 'identified',
    applied_ref VARCHAR(240),
    applied_by BIGINT,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (priority IN ('low','medium','high')),
    CHECK (status IN ('identified','in_review','applied','dismissed')),
    CHECK (status <> 'applied' OR applied_ref IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_cadu_agent_improvements_scope
    ON cadu_agent_improvements (client_id, status, created_at DESC);
