CREATE TABLE IF NOT EXISTS cadu_workspace_email_events (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT REFERENCES tbl_cliente(id_cliente) ON DELETE SET NULL,
    recipient_email VARCHAR(320) NOT NULL,
    event_type VARCHAR(48) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(24) NOT NULL CHECK (status IN ('sent', 'failed')),
    provider_message_id VARCHAR(255),
    provider_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_email_events_client_created
    ON cadu_workspace_email_events (id_cliente, created_at DESC);
