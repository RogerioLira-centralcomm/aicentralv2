-- Audited mappings for unfamiliar export headers; source rows stay immutable.
CREATE TABLE IF NOT EXISTS cadu_reports_import_column_maps (
    id BIGSERIAL PRIMARY KEY,
    import_id UUID NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    mapping JSONB NOT NULL,
    platform_hint VARCHAR(32),
    currency_hint CHAR(3),
    date_order VARCHAR(4) NOT NULL CHECK (date_order IN ('auto','dmy','mdy')),
    applied_rows INTEGER NOT NULL DEFAULT 0 CHECK (applied_rows >= 0),
    note VARCHAR(1000) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_column_maps_file_scope_fk
        FOREIGN KEY (import_id,organization_id,client_id)
        REFERENCES cadu_reports_import_files (id,organization_id,client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_column_maps_file_idx
    ON cadu_reports_import_column_maps
    (organization_id,client_id,import_id,created_at DESC);
