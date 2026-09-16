CREATE TABLE IF NOT EXISTS cadu_connect_report_imports (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    original_name VARCHAR(200) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    image_bytes BYTEA NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    supplier VARCHAR(200) NOT NULL DEFAULT '',
    period_start DATE,
    period_end DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'received' CHECK (status IN ('received','matched','reviewed','dismissed')),
    report_id BIGINT REFERENCES cadu_connect_report_workspaces(id),
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id,client_id,sha256)
);
CREATE INDEX IF NOT EXISTS cadu_connect_report_imports_inbox_idx ON cadu_connect_report_imports(organization_id,client_id,status,created_at DESC);
