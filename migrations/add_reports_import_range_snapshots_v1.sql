-- Confirmed interval facts remain separate from daily media metrics.
CREATE TABLE IF NOT EXISTS cadu_reports_import_range_snapshots (
    id BIGSERIAL PRIMARY KEY,
    import_id UUID NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    scope_index INTEGER NOT NULL CHECK (scope_index >= 0),
    account_id BIGINT NOT NULL,
    campaign_id BIGINT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    source_evidence JSONB NOT NULL,
    note VARCHAR(1000) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_range_snapshots_period_check CHECK (period_start < period_end),
    CONSTRAINT cadu_reports_import_range_snapshots_file_scope_fk
        FOREIGN KEY (import_id,organization_id,client_id)
        REFERENCES cadu_reports_import_files (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_range_snapshots_account_scope_fk
        FOREIGN KEY (account_id,organization_id,client_id)
        REFERENCES cadu_reports_accounts (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_range_snapshots_campaign_scope_fk
        FOREIGN KEY (campaign_id,organization_id,client_id)
        REFERENCES cadu_reports_campaigns (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_range_snapshots_id_scope_unique
        UNIQUE (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_range_snapshots_source_unique UNIQUE (import_id,scope_index)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_range_snapshots_client_period_idx
    ON cadu_reports_import_range_snapshots
    (organization_id,client_id,period_end DESC,campaign_id);

CREATE TABLE IF NOT EXISTS cadu_reports_import_range_metrics (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    metric_key VARCHAR(40) NOT NULL CHECK
        (metric_key IN ('impressions','clicks','cost','conversions','conversion_value')),
    value_numeric NUMERIC(24,6) NOT NULL CHECK (value_numeric >= 0),
    unit VARCHAR(16) NOT NULL CHECK (unit IN ('count','currency')),
    currency CHAR(3),
    CONSTRAINT cadu_reports_import_range_metrics_snapshot_scope_fk
        FOREIGN KEY (snapshot_id,organization_id,client_id)
        REFERENCES cadu_reports_import_range_snapshots (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_range_metrics_currency_check
        CHECK ((unit='currency' AND currency IS NOT NULL) OR (unit='count' AND currency IS NULL)),
    CONSTRAINT cadu_reports_import_range_metrics_unique UNIQUE (snapshot_id,metric_key)
);
