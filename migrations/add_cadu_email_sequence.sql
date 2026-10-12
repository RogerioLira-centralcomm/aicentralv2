-- Sequência de e-mails de adoção, preferências de contato e ledger único de envios.
-- Aditivo e idempotente. Depende de tbl_contato_cliente.

CREATE TABLE IF NOT EXISTS cadu_email_preferences (
    contato_id INTEGER PRIMARY KEY REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    marketing_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
    opted_out_at TIMESTAMPTZ,
    opt_out_source VARCHAR(24),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cadu_email_sequence_state (
    id BIGSERIAL PRIMARY KEY,
    contato_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    sequence_key VARCHAR(40) NOT NULL DEFAULT 'adocao_v1',
    next_step INTEGER NOT NULL DEFAULT 1,
    next_send_at TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0,
    paused_reason VARCHAR(80),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (contato_id, sequence_key)
);

CREATE INDEX IF NOT EXISTS idx_cadu_email_sequence_due
    ON cadu_email_sequence_state (next_send_at) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS cadu_email_log (
    id BIGSERIAL PRIMARY KEY,
    contato_id INTEGER,
    id_cliente BIGINT,
    recipient_email VARCHAR(320) NOT NULL,
    kind VARCHAR(16) NOT NULL DEFAULT 'sequence',
    event_type VARCHAR(80) NOT NULL,
    sequence_key VARCHAR(40),
    step INTEGER,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'sent',
    provider_message_id VARCHAR(255),
    provider_error TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    first_opened_at TIMESTAMPTZ,
    first_clicked_at TIMESTAMPTZ,
    open_count INTEGER NOT NULL DEFAULT 0,
    click_count INTEGER NOT NULL DEFAULT 0,
    last_event_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cadu_email_log_contact ON cadu_email_log (contato_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_email_log_status ON cadu_email_log (status, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_email_log_message ON cadu_email_log (provider_message_id)
    WHERE provider_message_id IS NOT NULL;
