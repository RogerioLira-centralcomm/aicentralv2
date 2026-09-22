-- Durable orchestration for research, extraction and incrementally composed artifacts.
CREATE TABLE IF NOT EXISTS cadu_agent_long_jobs (
    id UUID PRIMARY KEY,
    run_id UUID REFERENCES cadu_family_chat_runs(id) ON DELETE SET NULL,
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    artifact_id UUID REFERENCES cadu_workspace_artifacts(id) ON DELETE SET NULL,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    project_ref TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('deep_research','long_document','multi_source_analysis','artifact_revision')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','waiting','paused','completed','failed','cancelled','budget_exhausted')),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    source_target INTEGER NOT NULL DEFAULT 5 CHECK (source_target BETWEEN 0 AND 40),
    max_agent_calls INTEGER NOT NULL DEFAULT 8 CHECK (max_agent_calls BETWEEN 1 AND 40),
    max_extractor_calls INTEGER NOT NULL DEFAULT 40 CHECK (max_extractor_calls BETWEEN 0 AND 80),
    token_budget INTEGER NOT NULL CHECK (token_budget > 0),
    tokens_used INTEGER NOT NULL DEFAULT 0 CHECK (tokens_used >= 0),
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    UNIQUE (client_id, user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_cadu_long_jobs_queue
    ON cadu_agent_long_jobs (status, updated_at) WHERE status IN ('queued','running','waiting');
CREATE INDEX IF NOT EXISTS idx_cadu_long_jobs_conversation
    ON cadu_agent_long_jobs (conversation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_agent_long_job_units (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES cadu_agent_long_jobs(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES cadu_agent_long_job_units(id) ON DELETE SET NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    kind TEXT NOT NULL CHECK (kind IN ('discover','extract','classify','summarize','synthesize','compose','review','render')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','waiting','completed','failed','skipped','cancelled')),
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    token_usage INTEGER NOT NULL DEFAULT 0 CHECK (token_usage >= 0),
    error_code TEXT,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    UNIQUE (job_id, position)
);
CREATE INDEX IF NOT EXISTS idx_cadu_long_units_next
    ON cadu_agent_long_job_units (job_id, status, position);

CREATE TABLE IF NOT EXISTS cadu_agent_long_job_sources (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES cadu_agent_long_jobs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'web',
    status TEXT NOT NULL DEFAULT 'discovered' CHECK (status IN ('discovered','queued','extracting','extracted','blocked','failed','discarded')),
    relevance NUMERIC(6,5),
    content_hash TEXT,
    excerpt TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    extracted_at TIMESTAMPTZ,
    UNIQUE (job_id, canonical_url)
);
CREATE INDEX IF NOT EXISTS idx_cadu_long_sources_status
    ON cadu_agent_long_job_sources (job_id, status, relevance DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS cadu_agent_long_job_fragments (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES cadu_agent_long_jobs(id) ON DELETE CASCADE,
    unit_id UUID REFERENCES cadu_agent_long_job_units(id) ON DELETE SET NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    kind TEXT NOT NULL CHECK (kind IN ('note','evidence','section','revision','final')),
    heading TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    source_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
    content_hash TEXT NOT NULL,
    supersedes_id UUID REFERENCES cadu_agent_long_job_fragments(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, ordinal),
    UNIQUE (job_id, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_cadu_long_fragments_job
    ON cadu_agent_long_job_fragments (job_id, ordinal);

CREATE TABLE IF NOT EXISTS cadu_agent_long_job_calls (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES cadu_agent_long_jobs(id) ON DELETE CASCADE,
    unit_id UUID REFERENCES cadu_agent_long_job_units(id) ON DELETE SET NULL,
    call_type TEXT NOT NULL CHECK (call_type IN ('agent','extractor','embedding','renderer')),
    provider TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('running','completed','failed','cancelled')),
    idempotency_key TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    cost_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    UNIQUE (job_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_cadu_long_calls_job
    ON cadu_agent_long_job_calls (job_id, created_at);
