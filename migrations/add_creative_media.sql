CREATE TABLE IF NOT EXISTS cx_media_jobs (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    user_id INTEGER,
    client_id INTEGER,
    billing_client_id INTEGER,
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

ALTER TABLE cx_media_jobs ADD COLUMN IF NOT EXISTS billing_client_id INTEGER;

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

-- Projetos do editor: documento atual para leitura rápida e histórico imutável
-- para recuperação segura em caso de edição concorrente.
CREATE TABLE IF NOT EXISTS cx_studio_projects (
    id UUID PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    document JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_studio_projects_client_updated
    ON cx_studio_projects (client_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cx_studio_project_revisions (
    project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    document JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, revision)
);

-- Histórico de criação do Cadu Studio. Os lotes mantêm a decisão criativa
-- auditável e os itens ficam ligados ao projeto para reaproveitamento no editor.
CREATE TABLE IF NOT EXISTS cx_studio_creation_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    user_id INTEGER,
    prompt TEXT NOT NULL DEFAULT '',
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    requested_count SMALLINT NOT NULL DEFAULT 1 CHECK (requested_count BETWEEN 1 AND 5),
    returned_count SMALLINT NOT NULL DEFAULT 0 CHECK (returned_count BETWEEN 0 AND 5),
    model VARCHAR(180) NOT NULL DEFAULT '',
    charged_credits INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    error_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cx_studio_creation_runs_project
    ON cx_studio_creation_runs (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_studio_creation_directions (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cx_studio_creation_runs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 5),
    title VARCHAR(120) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL,
    selected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, position)
);

CREATE INDEX IF NOT EXISTS idx_cx_studio_creation_directions_project
    ON cx_studio_creation_directions (project_id, created_at DESC);

-- Feed extensível do projeto: referência, direção, imagem ou vídeo. Ele evita
-- que o histórico fique solto quando uma direção segue para outra ferramenta.
CREATE TABLE IF NOT EXISTS cx_studio_project_items (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    direction_id UUID REFERENCES cx_studio_creation_directions(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    user_id INTEGER,
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('reference', 'direction', 'image', 'video')),
    title VARCHAR(160) NOT NULL DEFAULT '',
    asset_url TEXT NOT NULL DEFAULT '',
    source_type VARCHAR(48) NOT NULL DEFAULT 'studio',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_studio_project_items_project
    ON cx_studio_project_items (project_id, created_at DESC);

-- Toda geração de imagem recebe identidade antes de chamar o provedor. A
-- unicidade por conta torna retries seguros inclusive no modo sem projeto.
CREATE TABLE IF NOT EXISTS cx_studio_image_generations (
    id UUID PRIMARY KEY,
    request_id VARCHAR(160) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    user_id INTEGER,
    project_id UUID REFERENCES cx_studio_projects(id) ON DELETE SET NULL,
    prompt TEXT NOT NULL DEFAULT '',
    model VARCHAR(180) NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (client_id, request_id)
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_image_generations_client
    ON cx_studio_image_generations (client_id, created_at DESC);

-- O restante do ciclo de sessão vive também em uma migration incremental para
-- instalações existentes. Este include é mantido duplicado de forma explícita
-- porque ensure_schema executa somente este arquivo em instalações novas.

CREATE TABLE IF NOT EXISTS cx_studio_assets (
    id UUID PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    owner_user_id INTEGER,
    project_id UUID REFERENCES cx_studio_projects(id) ON DELETE SET NULL,
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('reference', 'image', 'video', 'document')),
    source_type VARCHAR(48) NOT NULL DEFAULT 'studio', source_id VARCHAR(180) NOT NULL DEFAULT '',
    title VARCHAR(160) NOT NULL DEFAULT '', asset_url TEXT NOT NULL DEFAULT '', storage_key TEXT NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'working'
        CHECK (status IN ('working', 'accepted', 'final', 'discarded', 'pending_delete', 'deleted')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), deleted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_assets_owner ON cx_studio_assets (client_id, owner_user_id, updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cx_studio_assets_project ON cx_studio_assets (project_id, updated_at DESC) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_studio_assets_source ON cx_studio_assets (client_id, source_type, source_id) WHERE source_id <> '' AND deleted_at IS NULL;
ALTER TABLE cx_studio_project_items ADD COLUMN IF NOT EXISTS asset_id UUID REFERENCES cx_studio_assets(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_cx_studio_project_items_asset ON cx_studio_project_items (asset_id) WHERE asset_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cx_studio_sessions (
    id UUID PRIMARY KEY, root_session_id UUID NOT NULL, parent_session_id UUID,
    project_id UUID REFERENCES cx_studio_projects(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE, user_id INTEGER NOT NULL,
    studio_type VARCHAR(24) NOT NULL CHECK (studio_type IN ('create', 'edit', 'adapt')),
    status VARCHAR(24) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'ready', 'finalizing', 'finalized', 'archived', 'failed', 'cancelled')),
    title VARCHAR(160) NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    active_asset_id UUID REFERENCES cx_studio_assets(id) ON DELETE SET NULL,
    base_asset_id UUID REFERENCES cx_studio_assets(id) ON DELETE SET NULL,
    original_prompt TEXT NOT NULL DEFAULT '', optimized_prompt TEXT NOT NULL DEFAULT '',
    prompt_language VARCHAR(16) NOT NULL DEFAULT 'pt-BR', prompt_version VARCHAR(40) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb, started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finalized_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_cx_studio_sessions_root FOREIGN KEY (root_session_id) REFERENCES cx_studio_sessions(id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_cx_studio_sessions_parent FOREIGN KEY (parent_session_id) REFERENCES cx_studio_sessions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_project ON cx_studio_sessions (client_id, project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_free ON cx_studio_sessions (client_id, user_id, updated_at DESC) WHERE project_id IS NULL AND status <> 'archived';
CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_root ON cx_studio_sessions (root_session_id, created_at);

CREATE TABLE IF NOT EXISTS cx_studio_session_assets (
    session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES cx_studio_assets(id) ON DELETE CASCADE,
    role VARCHAR(24) NOT NULL CHECK (role IN ('reference', 'base', 'attempt', 'accepted', 'final', 'discard')),
    position INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, asset_id, role)
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_session_assets_asset ON cx_studio_session_assets (asset_id, session_id);

CREATE TABLE IF NOT EXISTS cx_studio_session_events (
    id BIGSERIAL PRIMARY KEY, session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(48) NOT NULL, request_id VARCHAR(160), payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_session_events_session ON cx_studio_session_events (session_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_studio_session_events_request ON cx_studio_session_events (session_id, request_id, event_type) WHERE request_id IS NOT NULL AND request_id <> '';

CREATE TABLE IF NOT EXISTS cx_studio_finalizations (
    id UUID PRIMARY KEY, session_id UUID NOT NULL UNIQUE REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    root_session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    final_asset_id UUID NOT NULL REFERENCES cx_studio_assets(id), snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    generation_count INTEGER NOT NULL DEFAULT 0 CHECK (generation_count >= 0), edit_count INTEGER NOT NULL DEFAULT 0 CHECK (edit_count >= 0),
    format_count INTEGER NOT NULL DEFAULT 0 CHECK (format_count >= 0), handoff_count INTEGER NOT NULL DEFAULT 0 CHECK (handoff_count >= 0),
    active_seconds INTEGER NOT NULL DEFAULT 0 CHECK (active_seconds >= 0), estimated_minutes_saved INTEGER NOT NULL DEFAULT 0 CHECK (estimated_minutes_saved >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_finalizations_root ON cx_studio_finalizations (root_session_id, created_at);

CREATE TABLE IF NOT EXISTS cx_studio_delivery_outbox (
    id UUID PRIMARY KEY, root_session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    finalization_id UUID NOT NULL REFERENCES cx_studio_finalizations(id) ON DELETE CASCADE,
    recipient_email VARCHAR(320) NOT NULL, recipient_name VARCHAR(160) NOT NULL DEFAULT '',
    kind VARCHAR(40) NOT NULL DEFAULT 'first_finalization', status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0), provider_message_id VARCHAR(180) NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb, last_error TEXT NOT NULL DEFAULT '', available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (root_session_id, kind)
);
ALTER TABLE cx_studio_delivery_outbox ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_cx_studio_delivery_outbox_pending ON cx_studio_delivery_outbox (available_at, created_at) WHERE status IN ('pending', 'failed');

CREATE TABLE IF NOT EXISTS cx_studio_asset_deletions (
    id BIGSERIAL PRIMARY KEY, asset_id UUID NOT NULL UNIQUE REFERENCES cx_studio_assets(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'deleted', 'failed', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0), available_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ, last_error TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE cx_studio_asset_deletions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_cx_studio_asset_deletions_pending ON cx_studio_asset_deletions (available_at, created_at) WHERE status IN ('pending', 'failed');
