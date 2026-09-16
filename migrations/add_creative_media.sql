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
