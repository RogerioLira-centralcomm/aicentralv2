CREATE TABLE IF NOT EXISTS cadu_connect_report_public_links (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL UNIQUE REFERENCES cadu_connect_report_workspaces(id) ON DELETE CASCADE,
    token VARCHAR(96) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_connect_report_public_links_token_active_idx
    ON cadu_connect_report_public_links (token) WHERE revoked_at IS NULL;
