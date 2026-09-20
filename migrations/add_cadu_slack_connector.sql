CREATE TABLE IF NOT EXISTS cadu_slack_connections (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    team_id VARCHAR(80) NOT NULL,
    team_name VARCHAR(255),
    encrypted_bot_token TEXT NOT NULL,
    encrypted_signing_secret TEXT NOT NULL,
    granted_scopes TEXT NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'connected'
        CHECK (status IN ('connected','revoked','error')),
    created_by BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id),
    UNIQUE (team_id)
);

CREATE TABLE IF NOT EXISTS cadu_slack_events (
    id BIGSERIAL PRIMARY KEY,
    connection_id UUID NOT NULL REFERENCES cadu_slack_connections(id) ON DELETE CASCADE,
    event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (connection_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_cadu_slack_events_received
    ON cadu_slack_events (connection_id, received_at DESC);
