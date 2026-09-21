-- Normalized, append-only evidence trail for Workspace brand audits.
-- cx_clients.brand_profile remains the fast active snapshot consumed by
-- Workspace and Studio; these tables preserve why that snapshot is trusted.

CREATE TABLE IF NOT EXISTS cadu_workspace_brand_audit_sources (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL REFERENCES cadu_workspace_brand_audit_runs(job_id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'official_page',
    country VARCHAR(16),
    title TEXT,
    excerpt TEXT,
    content_hash VARCHAR(128),
    relevance NUMERIC(4,3),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, url)
);

CREATE TABLE IF NOT EXISTS cadu_workspace_brand_audit_evidence (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL REFERENCES cadu_workspace_brand_audit_runs(job_id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    field_name VARCHAR(96) NOT NULL,
    claim TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'unverified',
    source_url TEXT,
    excerpt TEXT,
    confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cadu_workspace_brand_audit_agents (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL REFERENCES cadu_workspace_brand_audit_runs(job_id) ON DELETE CASCADE,
    stage VARCHAR(64) NOT NULL,
    provider VARCHAR(32),
    model VARCHAR(128),
    prompt_version VARCHAR(64) NOT NULL DEFAULT 'brand-audit-v4',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12,6),
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, stage)
);

CREATE TABLE IF NOT EXISTS cadu_workspace_brand_audit_assets (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL REFERENCES cadu_workspace_brand_audit_runs(job_id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    asset_url TEXT NOT NULL,
    asset_kind VARCHAR(32) NOT NULL DEFAULT 'reference',
    decision VARCHAR(16) NOT NULL DEFAULT 'accepted',
    ocr_text TEXT,
    relevance NUMERIC(4,3),
    source_url TEXT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, asset_url)
);

CREATE TABLE IF NOT EXISTS cadu_workspace_brand_profile_snapshots (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL REFERENCES cadu_workspace_brand_audit_runs(job_id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    decision VARCHAR(24) NOT NULL,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    field_provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id)
);

-- Campaigns are audit outputs, not permanent brand attributes. They can later
-- become projects only through an explicit user action.
CREATE TABLE IF NOT EXISTS cadu_workspace_brand_campaigns (
    id VARCHAR(64) PRIMARY KEY,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    audit_job_id VARCHAR(64) REFERENCES cadu_workspace_brand_audit_runs(job_id) ON DELETE SET NULL,
    name VARCHAR(160) NOT NULL,
    campaign_type VARCHAR(24) NOT NULL,
    objective TEXT,
    audience TEXT,
    channels JSONB NOT NULL DEFAULT '[]'::jsonb,
    rationale TEXT,
    source_url TEXT,
    confidence NUMERIC(4,3),
    status VARCHAR(24) NOT NULL DEFAULT 'opportunity',
    project_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, brand_id, name)
);

CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_sources_run_idx
    ON cadu_workspace_brand_audit_sources (client_id, brand_id, job_id);
CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_evidence_run_idx
    ON cadu_workspace_brand_audit_evidence (client_id, brand_id, job_id, field_name);
CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_assets_run_idx
    ON cadu_workspace_brand_audit_assets (client_id, brand_id, job_id);
CREATE INDEX IF NOT EXISTS cadu_workspace_brand_campaigns_brand_idx
    ON cadu_workspace_brand_campaigns (client_id, brand_id, status, updated_at DESC);
