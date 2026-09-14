CREATE TABLE IF NOT EXISTS cx_media_jobs (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    user_id INTEGER,
    client_id INTEGER,
    run_id VARCHAR(80) NOT NULL DEFAULT '',
    source_version_id VARCHAR(40) NOT NULL DEFAULT '',
    source_revision INTEGER,
    plan_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    plan_hash VARCHAR(64) NOT NULL DEFAULT '',
    quote_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(40) NOT NULL DEFAULT 'queued',
    stage VARCHAR(40) NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider VARCHAR(40) NOT NULL DEFAULT 'openrouter',
    model VARCHAR(120) NOT NULL DEFAULT '',
    provider_job_id VARCHAR(120) NOT NULL DEFAULT '',
    provider_polling_url TEXT NOT NULL DEFAULT '',
    seed INTEGER,
    locked_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    error_code VARCHAR(80) NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    attempt INTEGER NOT NULL DEFAULT 0,
    version_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_media_jobs_run
    ON cx_media_jobs (run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cx_media_jobs_status
    ON cx_media_jobs (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS cx_media_assets (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    job_id BIGINT REFERENCES cx_media_jobs(id) ON DELETE SET NULL,
    kind VARCHAR(40) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'video/mp4',
    storage_key TEXT NOT NULL,
    sha256 VARCHAR(64),
    size_bytes INTEGER,
    width INTEGER,
    height INTEGER,
    duration INTEGER,
    has_audio BOOLEAN NOT NULL DEFAULT FALSE,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_media_assets_job
    ON cx_media_assets (job_id, kind);
