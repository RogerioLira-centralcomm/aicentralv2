BEGIN;

CREATE TABLE IF NOT EXISTS public.studio_creative_analyses (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    brand_ref VARCHAR(160),
    project_ref VARCHAR(160),
    status VARCHAR(24) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'complete', 'partial', 'failed')),
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    original_name VARCHAR(255) NOT NULL,
    media_type VARCHAR(16) NOT NULL CHECK (media_type IN ('image', 'video')),
    mime_type VARCHAR(100) NOT NULL,
    format VARCHAR(20),
    source_asset_id VARCHAR(80),
    thumbnail_url TEXT,
    score_geral SMALLINT CHECK (score_geral BETWEEN 0 AND 100),
    creative_type VARCHAR(80),
    funnel VARCHAR(40),
    context_text TEXT,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code VARCHAR(80),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_studio_creative_analyses_client_created
    ON public.studio_creative_analyses (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_studio_creative_analyses_user_created
    ON public.studio_creative_analyses (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_studio_creative_analyses_project
    ON public.studio_creative_analyses (client_id, project_ref, created_at DESC)
    WHERE project_ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.studio_creative_analysis_assets (
    id BIGSERIAL PRIMARY KEY,
    analysis_id BIGINT NOT NULL REFERENCES public.studio_creative_analyses(id) ON DELETE CASCADE,
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('source', 'thumbnail', 'frame', 'audio')),
    position SMALLINT,
    storage_key TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    sha256 CHAR(64),
    size_bytes BIGINT,
    width INTEGER,
    height INTEGER,
    duration_seconds NUMERIC(12,3),
    frame_time_seconds NUMERIC(12,3),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (analysis_id, kind, position)
);

CREATE INDEX IF NOT EXISTS idx_studio_creative_analysis_assets_analysis
    ON public.studio_creative_analysis_assets (analysis_id, kind, position);

CREATE TABLE IF NOT EXISTS public.studio_creative_analysis_runs (
    id BIGSERIAL PRIMARY KEY,
    analysis_id BIGINT NOT NULL REFERENCES public.studio_creative_analyses(id) ON DELETE CASCADE,
    stage VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL CHECK (status IN ('queued', 'running', 'complete', 'failed')),
    attempt INTEGER NOT NULL DEFAULT 1,
    provider VARCHAR(80),
    model VARCHAR(160),
    tokens_input INTEGER,
    tokens_output INTEGER,
    duration_ms INTEGER,
    error_code VARCHAR(80),
    error_message TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_studio_creative_analysis_runs_analysis
    ON public.studio_creative_analysis_runs (analysis_id, created_at);

CREATE TABLE IF NOT EXISTS public.studio_creative_analysis_shares (
    id BIGSERIAL PRIMARY KEY,
    analysis_id BIGINT NOT NULL REFERENCES public.studio_creative_analyses(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_creative_analysis_active_share
    ON public.studio_creative_analysis_shares (analysis_id)
    WHERE active = TRUE AND revoked_at IS NULL;

COMMIT;
