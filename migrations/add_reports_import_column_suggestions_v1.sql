-- TypeSafe header suggestions are review-only and cached per import file.
CREATE TABLE IF NOT EXISTS cadu_reports_import_column_suggestions (
    id BIGSERIAL PRIMARY KEY,
    import_id UUID NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    result JSONB NOT NULL,
    model VARCHAR(120) NOT NULL,
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_column_suggestions_file_scope_fk
        FOREIGN KEY (import_id,organization_id,client_id)
        REFERENCES cadu_reports_import_files (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_column_suggestions_one_per_file UNIQUE (import_id)
);
