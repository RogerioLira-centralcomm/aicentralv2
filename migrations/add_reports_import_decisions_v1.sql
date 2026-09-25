-- Immutable human decisions for source-bound import rows.
CREATE TABLE IF NOT EXISTS cadu_reports_import_decisions (
    id BIGSERIAL PRIMARY KEY,
    import_row_id BIGINT NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    before_parsed JSONB NOT NULL,
    after_parsed JSONB NOT NULL,
    note VARCHAR(1000) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_decisions_row_scope_fk
        FOREIGN KEY (import_row_id,organization_id,client_id)
        REFERENCES cadu_reports_import_rows (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_decisions_row_unique UNIQUE (import_row_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_decisions_client_idx
    ON cadu_reports_import_decisions (organization_id,client_id,created_at DESC);
