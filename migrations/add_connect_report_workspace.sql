-- Apply through the normal deployment process; never create tables on GET.
CREATE TABLE IF NOT EXISTS cadu_connect_report_workspaces (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    project_ref TEXT NOT NULL,
    campaign_name TEXT NOT NULL,
    campaign_key TEXT NOT NULL,
    document JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_by INTEGER NOT NULL,
    updated_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, client_id, project_ref, campaign_key)
);
CREATE TABLE IF NOT EXISTS cadu_connect_report_workspace_versions (
    report_id BIGINT NOT NULL REFERENCES cadu_connect_report_workspaces(id),
    revision INTEGER NOT NULL,
    document JSONB NOT NULL,
    note TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (report_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_connect_report_workspace_client
    ON cadu_connect_report_workspaces(organization_id, client_id, updated_at DESC);
