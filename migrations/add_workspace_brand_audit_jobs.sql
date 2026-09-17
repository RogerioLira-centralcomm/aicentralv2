-- Additive durable queue for slow Workspace brand audits.
-- A claimed job is never auto-retried: a provider request may have charged it.
CREATE TABLE IF NOT EXISTS cadu_workspace_brand_audit_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_jobs_pending
    ON cadu_workspace_brand_audit_jobs(created_at, job_id) WHERE status = 'queued';
