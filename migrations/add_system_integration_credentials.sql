CREATE TABLE IF NOT EXISTS system_integration_credentials (
    provider VARCHAR(50) PRIMARY KEY,
    public_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    encrypted_secret TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled', 'error')),
    last_validation_status VARCHAR(20),
    last_validation_message TEXT,
    last_validated_at TIMESTAMPTZ,
    updated_by INTEGER
        REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (provider IN ('google_calendar', 'higgsfield'))
);

CREATE INDEX IF NOT EXISTS idx_system_integration_credentials_status
    ON system_integration_credentials (status);
