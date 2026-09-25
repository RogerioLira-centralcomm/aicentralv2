-- Follow-up for environments that already applied add_reports_operations_v1.sql.
ALTER TABLE tbl_contato_cliente ADD COLUMN IF NOT EXISTS reports_only BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS cadu_reports_user_access (
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    role VARCHAR(12) NOT NULL CHECK (role IN ('viewer','member','admin')),
    granted_by INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    PRIMARY KEY (organization_id,user_id,client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_user_access_client_idx
    ON cadu_reports_user_access (organization_id,client_id,user_id) WHERE revoked_at IS NULL;

ALTER TABLE cadu_reports_ingest_keys
    ADD COLUMN IF NOT EXISTS allowed_account_ids TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE cadu_reports_ingest_keys
    ADD COLUMN IF NOT EXISTS bound_account_id VARCHAR(20);

CREATE TABLE IF NOT EXISTS cadu_reports_flow_rate_limits (
    tag_id UUID NOT NULL REFERENCES cadu_reports_site_tags(id) ON DELETE CASCADE,
    bucket_start TIMESTAMPTZ NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 0 CHECK (event_count >= 0),
    PRIMARY KEY (tag_id,bucket_start)
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_rate_limits_time_idx
    ON cadu_reports_flow_rate_limits (bucket_start);
