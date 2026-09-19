CREATE TABLE IF NOT EXISTS cadu_project_resources (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    project_ref TEXT NOT NULL,
    source_system VARCHAR(40) NOT NULL,
    source_id TEXT NOT NULL,
    resource_type VARCHAR(40) NOT NULL,
    title TEXT NOT NULL,
    mime_type VARCHAR(160),
    purpose VARCHAR(40) NOT NULL DEFAULT 'project_resource',
    category VARCHAR(40) NOT NULL DEFAULT 'other',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    content_hash CHAR(64),
    locator TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by BIGINT,
    source_created_at TIMESTAMPTZ,
    source_updated_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, project_ref, source_system, source_id)
);

CREATE INDEX IF NOT EXISTS idx_cadu_project_resources_project
    ON cadu_project_resources (client_id, project_ref, category, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_project_resources_purpose
    ON cadu_project_resources (client_id, project_ref, purpose, status);
CREATE INDEX IF NOT EXISTS idx_cadu_project_resources_hash
    ON cadu_project_resources (client_id, content_hash) WHERE content_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS cadu_project_resource_events (
    id BIGSERIAL PRIMARY KEY,
    resource_id UUID NOT NULL REFERENCES cadu_project_resources(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    project_ref TEXT NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    fingerprint CHAR(64) NOT NULL,
    actor_id BIGINT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (resource_id, event_type, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_cadu_project_resource_events_project
    ON cadu_project_resource_events (client_id, project_ref, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_project_resource_jobs (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    project_ref TEXT NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    source_system VARCHAR(40),
    source_id TEXT,
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
ALTER TABLE cadu_project_resource_jobs
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS actor_id BIGINT;

DROP INDEX IF EXISTS idx_cadu_project_resource_jobs_queue;
CREATE INDEX idx_cadu_project_resource_jobs_queue
    ON cadu_project_resource_jobs (status, next_attempt_at, created_at) WHERE status IN ('queued','failed','running');

CREATE TABLE IF NOT EXISTS cadu_project_resource_relations (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    project_ref TEXT NOT NULL,
    source_resource_id UUID NOT NULL REFERENCES cadu_project_resources(id) ON DELETE CASCADE,
    target_resource_id UUID NOT NULL REFERENCES cadu_project_resources(id) ON DELETE CASCADE,
    relation_type VARCHAR(40) NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_resource_id, target_resource_id, relation_type),
    CHECK (source_resource_id <> target_resource_id)
);
CREATE INDEX IF NOT EXISTS idx_cadu_project_resource_relations_project
    ON cadu_project_resource_relations (client_id, project_ref, relation_type);
