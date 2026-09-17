CREATE TABLE IF NOT EXISTS cadu_user_onboardings (
    id BIGSERIAL PRIMARY KEY,
    contato_id INTEGER NOT NULL UNIQUE REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    perfil VARCHAR(20) NOT NULL CHECK (perfil IN ('cliente_final', 'agencia')),
    empresa VARCHAR(255) NOT NULL,
    cargo VARCHAR(160),
    telefone VARCHAR(40),
    site_url VARCHAR(500),
    objetivo TEXT,
    executivo_id INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    lead_id BIGINT REFERENCES cadu_leads(id) ON DELETE SET NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    followup_scheduled_for TIMESTAMPTZ,
    followup_sent_at TIMESTAMPTZ,
    followup_attempts INTEGER NOT NULL DEFAULT 0,
    followup_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_user_onboardings_followup_pending
    ON cadu_user_onboardings (followup_scheduled_for)
    WHERE followup_sent_at IS NULL;
