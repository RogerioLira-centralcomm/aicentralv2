-- Source-first import inbox. Raw material and normalized observations remain separate.
CREATE TABLE IF NOT EXISTS cadu_reports_import_files (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    original_name VARCHAR(200) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_kind VARCHAR(12) NOT NULL CHECK (file_kind IN ('csv','xlsx','image')),
    raw_bytes BYTEA NOT NULL,
    status VARCHAR(24) NOT NULL CHECK (status IN ('received','parsed','awaiting_extraction','needs_review')),
    platform_hint VARCHAR(32),
    row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    applied_count INTEGER NOT NULL DEFAULT 0 CHECK (applied_count >= 0),
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_files_scope_unique UNIQUE (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_files_hash_unique UNIQUE (organization_id,client_id,sha256)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_files_client_idx
    ON cadu_reports_import_files (organization_id,client_id,created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_import_rows (
    id BIGSERIAL PRIMARY KEY,
    import_id UUID NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    sheet_name VARCHAR(100) NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw JSONB NOT NULL,
    parsed JSONB NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('applied','needs_review')),
    reason TEXT,
    account_id BIGINT,
    campaign_id BIGINT,
    metric_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_rows_id_scope_unique UNIQUE (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_rows_file_scope_fk
        FOREIGN KEY (import_id,organization_id,client_id)
        REFERENCES cadu_reports_import_files (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_rows_account_scope_fk
        FOREIGN KEY (account_id,organization_id,client_id)
        REFERENCES cadu_reports_accounts (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_rows_campaign_scope_fk
        FOREIGN KEY (campaign_id,organization_id,client_id)
        REFERENCES cadu_reports_campaigns (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_rows_source_unique UNIQUE (import_id,sheet_name,source_row)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_rows_client_idx
    ON cadu_reports_import_rows (organization_id,client_id,status,created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_import_observations (
    id BIGSERIAL PRIMARY KEY,
    import_row_id BIGINT NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    campaign_id BIGINT NOT NULL,
    metric_date DATE NOT NULL,
    metric_key VARCHAR(40) NOT NULL,
    value_numeric NUMERIC(24,6) NOT NULL CHECK (value_numeric >= 0),
    unit VARCHAR(16) NOT NULL CHECK (unit IN ('count','currency')),
    currency CHAR(3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_observations_row_scope_fk
        FOREIGN KEY (import_row_id,organization_id,client_id)
        REFERENCES cadu_reports_import_rows (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_observations_campaign_scope_fk
        FOREIGN KEY (campaign_id,organization_id,client_id)
        REFERENCES cadu_reports_campaigns (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_observations_metric_check
        CHECK (metric_key IN ('impressions','clicks','cost','conversions','conversion_value')),
    CONSTRAINT cadu_reports_import_observations_currency_check
        CHECK ((unit='currency' AND currency IS NOT NULL) OR (unit='count' AND currency IS NULL)),
    CONSTRAINT cadu_reports_import_observations_row_metric_unique
        UNIQUE (import_row_id,metric_key)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_observations_campaign_date_idx
    ON cadu_reports_import_observations (organization_id,client_id,campaign_id,metric_date DESC);
