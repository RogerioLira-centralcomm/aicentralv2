-- Versioned brand-audit state. The active identity remains in cx_clients;
-- every new audit is an immutable candidate until explicitly approved.
ALTER TABLE cadu_workspace_brand_audit_jobs
    ADD COLUMN IF NOT EXISTS analysis_mode VARCHAR(20) NOT NULL DEFAULT 'complete',
    ADD COLUMN IF NOT EXISTS base_snapshot_id BIGINT,
    ADD COLUMN IF NOT EXISTS request_reason VARCHAR(32) NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS requested_by BIGINT,
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(160);

ALTER TABLE cadu_workspace_brand_audit_runs
    ADD COLUMN IF NOT EXISTS parent_job_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS base_snapshot_id BIGINT,
    ADD COLUMN IF NOT EXISTS request_reason VARCHAR(32) NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS requested_by BIGINT,
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(128),
    ADD COLUMN IF NOT EXISTS superseded_by VARCHAR(64);

ALTER TABLE cadu_workspace_brand_profile_snapshots
    ADD COLUMN IF NOT EXISTS snapshot_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS approved_by BIGINT,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS diff JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS active_brand_audit_job_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS active_brand_snapshot_id BIGINT,
    ADD COLUMN IF NOT EXISTS audit_cadence_days INTEGER NOT NULL DEFAULT 60,
    ADD COLUMN IF NOT EXISTS last_audited_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS next_analysis_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS identity_revision INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS cadu_workspace_brand_identity_fields (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    snapshot_id BIGINT,
    field_name VARCHAR(96) NOT NULL,
    value JSONB NOT NULL DEFAULT 'null'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'needs_review',
    confidence NUMERIC(4,3),
    evidence_count INTEGER NOT NULL DEFAULT 0,
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (brand_id, snapshot_id, field_name)
);

CREATE INDEX IF NOT EXISTS cadu_workspace_brand_identity_fields_current
    ON cadu_workspace_brand_identity_fields (client_id, brand_id, field_name, last_verified_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS cadu_workspace_brand_audit_jobs_idempotency
    ON cadu_workspace_brand_audit_jobs (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_runs_pending
    ON cadu_workspace_brand_audit_runs (client_id, brand_id, status, created_at DESC);
