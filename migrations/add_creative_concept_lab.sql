-- Mesa de conceito 15s: sessão, cenas, camadas, passagens e referências.
-- Idempotente. Não substitui cx_campaigns / cx_creative_scenes do Preparar.

CREATE TABLE IF NOT EXISTS cx_concept_sessions (
    id VARCHAR(32) PRIMARY KEY,
    campaign_id INTEGER NOT NULL
        REFERENCES cx_campaigns(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL
        REFERENCES cx_clients(id) ON DELETE RESTRICT,
    format_key VARCHAR(40) NOT NULL DEFAULT 'video-linear-15',
    variant VARCHAR(1) NOT NULL DEFAULT 'A',
    intent VARCHAR(20) NOT NULL DEFAULT 'create',
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    campaign_slug VARCHAR(80),
    duration_seconds INTEGER NOT NULL DEFAULT 15,
    scene_count INTEGER NOT NULL DEFAULT 4,
    adapter VARCHAR(40),
    platform_label VARCHAR(40),
    objective VARCHAR(120),
    knobs JSONB NOT NULL DEFAULT '{}'::jsonb,
    spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    brand_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    qa JSONB NOT NULL DEFAULT '{}'::jsonb,
    quote JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    spent_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    handed_off_at TIMESTAMPTZ,
    CONSTRAINT chk_cx_concept_session_format
        CHECK (
            format_key IN (
                'video-linear-15', 'video-cta-15', 'video-qr-15',
                'ctv-video-linear-30', 'ctv-video-cta', 'ctv-video-qr'
            )
        ),
    CONSTRAINT chk_cx_concept_session_variant
        CHECK (variant IN ('A', 'B', 'C', 'D')),
    CONSTRAINT chk_cx_concept_session_intent
        CHECK (
            intent IN (
                'create', 'reconstruct', 'adapt', 'refine', 'html', 'vary'
            )
        ),
    CONSTRAINT chk_cx_concept_session_status
        CHECK (
            status IN (
                'draft', 'concept', 'review', 'ready', 'handed_off'
            )
        ),
    CONSTRAINT chk_cx_concept_session_scene_count
        CHECK (scene_count IN (4, 5)),
    CONSTRAINT chk_cx_concept_session_duration
        CHECK (duration_seconds = 15),
    CONSTRAINT chk_cx_concept_session_spent
        CHECK (spent_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cx_concept_sessions_campaign
    ON cx_concept_sessions(campaign_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_concept_sessions_client
    ON cx_concept_sessions(client_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_concept_sessions_status
    ON cx_concept_sessions(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS cx_concept_scenes (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL
        REFERENCES cx_concept_sessions(id) ON DELETE CASCADE,
    scene_key VARCHAR(16) NOT NULL,
    position INTEGER NOT NULL,
    purpose VARCHAR(40),
    role VARCHAR(40),
    headline VARCHAR(240),
    support VARCHAR(240),
    cta VARCHAR(120),
    tip VARCHAR(120),
    set_note VARCHAR(240),
    action_note VARCHAR(240),
    timecode VARCHAR(40),
    duration_seconds NUMERIC(6, 2) NOT NULL DEFAULT 3,
    image_prompt TEXT,
    html TEXT,
    render_url TEXT,
    layers JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cx_concept_scene_key UNIQUE (session_id, scene_key),
    CONSTRAINT uq_cx_concept_scene_position UNIQUE (session_id, position),
    CONSTRAINT chk_cx_concept_scene_key
        CHECK (scene_key IN (
            'scene_01', 'scene_02', 'scene_03', 'scene_04', 'scene_05'
        )),
    CONSTRAINT chk_cx_concept_scene_position
        CHECK (position BETWEEN 1 AND 5),
    CONSTRAINT chk_cx_concept_scene_status
        CHECK (status IN ('draft', 'concept', 'review', 'ready', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_cx_concept_scenes_session
    ON cx_concept_scenes(session_id, position);

CREATE TABLE IF NOT EXISTS cx_concept_layers (
    id BIGSERIAL PRIMARY KEY,
    scene_id BIGINT NOT NULL
        REFERENCES cx_concept_scenes(id) ON DELETE CASCADE,
    layer_key VARCHAR(80) NOT NULL,
    layer_type VARCHAR(40),
    x NUMERIC(8, 3),
    y NUMERIC(8, 3),
    w NUMERIC(8, 3),
    h NUMERIC(8, 3),
    z INTEGER,
    text_value TEXT,
    css_value TEXT,
    CONSTRAINT uq_cx_concept_layer_key UNIQUE (scene_id, layer_key)
);

CREATE INDEX IF NOT EXISTS idx_cx_concept_layers_scene
    ON cx_concept_layers(scene_id, z);

CREATE TABLE IF NOT EXISTS cx_concept_passes (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL
        REFERENCES cx_concept_sessions(id) ON DELETE CASCADE,
    job_id BIGINT REFERENCES cx_generation_jobs(id) ON DELETE SET NULL,
    pass_kind VARCHAR(20) NOT NULL,
    position INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    model VARCHAR(100) NOT NULL DEFAULT 'openai/gpt-5.4',
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    actual_cost_usd NUMERIC(12, 6),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_concept_pass_kind
        CHECK (
            pass_kind IN (
                'create', 'refine', 'implement', 'validate', 'patch'
            )
        ),
    CONSTRAINT chk_cx_concept_pass_status
        CHECK (status IN ('queued', 'running', 'done', 'review', 'failed')),
    CONSTRAINT chk_cx_concept_pass_position
        CHECK (position BETWEEN 1 AND 8),
    CONSTRAINT chk_cx_concept_pass_cost
        CHECK (
            estimated_cost_usd >= 0
            AND (actual_cost_usd IS NULL OR actual_cost_usd >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_cx_concept_passes_session
    ON cx_concept_passes(session_id, position);

CREATE TABLE IF NOT EXISTS cx_concept_references (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL
        REFERENCES cx_concept_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'reference',
    asset_url TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_concept_reference_role
        CHECK (role IN ('user', 'logo', 'reference')),
    CONSTRAINT chk_cx_concept_reference_position
        CHECK (position BETWEEN 1 AND 8)
);

CREATE INDEX IF NOT EXISTS idx_cx_concept_references_session
    ON cx_concept_references(session_id, position);

ALTER TABLE cx_generation_jobs
    ADD COLUMN IF NOT EXISTS concept_session_id VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_cx_generation_jobs_concept_session
    ON cx_generation_jobs(concept_session_id, created_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_generation_jobs_concept_session'
           AND conrelid = 'cx_generation_jobs'::regclass
    ) THEN
        ALTER TABLE cx_generation_jobs
            ADD CONSTRAINT fk_cx_generation_jobs_concept_session
            FOREIGN KEY (concept_session_id)
            REFERENCES cx_concept_sessions(id)
            ON DELETE SET NULL;
    END IF;
END
$$;
