-- Durable, retryable project source reindexing.
CREATE TABLE IF NOT EXISTS cadu_project_index_jobs (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    project_ref TEXT NOT NULL,
    source_id BIGINT NOT NULL REFERENCES cadu_ci_projeto_arquivos(id) ON DELETE CASCADE,
    operation VARCHAR(32) NOT NULL DEFAULT 'reindex',
    actor_id BIGINT,
    status VARCHAR(24) NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    next_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CHECK (status IN ('queued','running','completed','failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_project_index_jobs_active
    ON cadu_project_index_jobs (client_id, project_ref, source_id, operation)
    WHERE status IN ('queued','running');

CREATE INDEX IF NOT EXISTS idx_cadu_project_index_jobs_queue
    ON cadu_project_index_jobs (status, next_attempt_at, created_at)
    WHERE status IN ('queued','failed','running');

CREATE INDEX IF NOT EXISTS idx_cadu_project_index_jobs_source
    ON cadu_project_index_jobs (client_id, project_ref, source_id, created_at DESC);
