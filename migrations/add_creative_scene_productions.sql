-- Plano de produção visual por cenas.
-- Mantém o modelo histórico de variações A/B e pode ser reaplicada.

CREATE TABLE IF NOT EXISTS cx_creative_productions (
    id BIGSERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL
        REFERENCES cx_campaigns(id) ON DELETE CASCADE,
    format_template_id INTEGER NOT NULL
        REFERENCES cx_format_templates(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    selected_asset_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cx_creative_production_format
        UNIQUE (campaign_id, format_template_id),
    CONSTRAINT chk_cx_creative_production_status
        CHECK (status IN ('active', 'completed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_cx_creative_productions_campaign
    ON cx_creative_productions(campaign_id, created_at);

CREATE TABLE IF NOT EXISTS cx_creative_scenes (
    id BIGSERIAL PRIMARY KEY,
    production_id BIGINT NOT NULL
        REFERENCES cx_creative_productions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    description TEXT,
    prompt TEXT,
    prompt_status VARCHAR(20) NOT NULL DEFAULT 'draft',
    status VARCHAR(20) NOT NULL DEFAULT 'blocked',
    approved_asset_id BIGINT,
    preview_asset_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cx_creative_scene_position UNIQUE (production_id, position),
    CONSTRAINT chk_cx_creative_scene_position CHECK (position BETWEEN 1 AND 4),
    CONSTRAINT chk_cx_creative_scene_status
        CHECK (
            status IN (
                'blocked', 'ready', 'generating', 'review',
                'approved', 'failed'
            )
        ),
    CONSTRAINT chk_cx_creative_scene_prompt_status
        CHECK (prompt_status IN ('draft', 'generated', 'reviewed', 'approved'))
);

CREATE INDEX IF NOT EXISTS idx_cx_creative_scenes_production
    ON cx_creative_scenes(production_id, position);

ALTER TABLE cx_generation_jobs
    ADD COLUMN IF NOT EXISTS scene_id BIGINT;

ALTER TABLE cx_generated_assets
    ADD COLUMN IF NOT EXISTS scene_id BIGINT;

ALTER TABLE cx_creative_scenes
    ADD COLUMN IF NOT EXISTS prompt_status VARCHAR(20) NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS preview_asset_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_cx_generation_jobs_scene
    ON cx_generation_jobs(scene_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cx_generated_assets_scene
    ON cx_generated_assets(scene_id, created_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'chk_cx_creative_scene_prompt_status'
           AND conrelid = 'cx_creative_scenes'::regclass
    ) THEN
        ALTER TABLE cx_creative_scenes
            ADD CONSTRAINT chk_cx_creative_scene_prompt_status
            CHECK (
                prompt_status IN ('draft', 'generated', 'reviewed', 'approved')
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_generation_jobs_scene'
           AND conrelid = 'cx_generation_jobs'::regclass
    ) THEN
        ALTER TABLE cx_generation_jobs
            ADD CONSTRAINT fk_cx_generation_jobs_scene
            FOREIGN KEY (scene_id)
            REFERENCES cx_creative_scenes(id)
            ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_generated_assets_scene'
           AND conrelid = 'cx_generated_assets'::regclass
    ) THEN
        ALTER TABLE cx_generated_assets
            ADD CONSTRAINT fk_cx_generated_assets_scene
            FOREIGN KEY (scene_id)
            REFERENCES cx_creative_scenes(id)
            ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_creative_scenes_approved_asset'
           AND conrelid = 'cx_creative_scenes'::regclass
    ) THEN
        ALTER TABLE cx_creative_scenes
            ADD CONSTRAINT fk_cx_creative_scenes_approved_asset
            FOREIGN KEY (approved_asset_id)
            REFERENCES cx_generated_assets(id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_creative_scenes_preview_asset'
           AND conrelid = 'cx_creative_scenes'::regclass
    ) THEN
        ALTER TABLE cx_creative_scenes
            ADD CONSTRAINT fk_cx_creative_scenes_preview_asset
            FOREIGN KEY (preview_asset_id)
            REFERENCES cx_generated_assets(id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_creative_productions_selected_asset'
           AND conrelid = 'cx_creative_productions'::regclass
    ) THEN
        ALTER TABLE cx_creative_productions
            ADD CONSTRAINT fk_cx_creative_productions_selected_asset
            FOREIGN KEY (selected_asset_id)
            REFERENCES cx_generated_assets(id)
            ON DELETE SET NULL;
    END IF;
END
$$;
