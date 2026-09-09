-- Modelagem de Criativos com variações A/B.
-- Idempotente e compatível com o executor de migrations do CentralX.

CREATE TABLE IF NOT EXISTS cx_format_categories (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS cx_channels (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    channel_type VARCHAR(30),
    device_mockup VARCHAR(50),
    screen_context_template TEXT,
    logo_asset_ref TEXT,
    partner_primary_color VARCHAR(20),
    partner_secondary_color VARCHAR(20),
    brand_guidelines JSONB NOT NULL DEFAULT '{}'::jsonb,
    reference_assets JSONB NOT NULL DEFAULT '[]'::jsonb,
    category_id INTEGER REFERENCES cx_format_categories(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cx_channels_category
    ON cx_channels(category_id);

CREATE TABLE IF NOT EXISTS cx_format_templates (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(60) NOT NULL UNIQUE,
    name_pt VARCHAR(100) NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    channel_id INTEGER REFERENCES cx_channels(id) ON DELETE RESTRICT,
    mechanic VARCHAR(50),
    media_type VARCHAR(10) NOT NULL,
    engine VARCHAR(20) NOT NULL,
    aspect_ratio VARCHAR(10),
    default_size VARCHAR(20),
    safe_area JSONB NOT NULL DEFAULT '{}'::jsonb,
    responsive_rules TEXT,
    background_guidance TEXT,
    foreground_guidance TEXT,
    max_reference_variants INTEGER NOT NULL DEFAULT 4,
    layers JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    optional_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    forbidden_elements JSONB NOT NULL DEFAULT '[]'::jsonb,
    use_cases_by_market JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'formato_aberto',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_cx_format_media_type
        CHECK (media_type IN ('image', 'video')),
    CONSTRAINT chk_cx_format_engine
        CHECK (
            (media_type = 'image' AND engine = 'gpt_image_2')
            OR (media_type = 'video' AND engine = 'higgsfield')
        ),
    CONSTRAINT chk_cx_format_reference_limit
        CHECK (max_reference_variants BETWEEN 1 AND 4)
);

CREATE INDEX IF NOT EXISTS idx_cx_format_templates_channel
    ON cx_format_templates(channel_id);
CREATE INDEX IF NOT EXISTS idx_cx_format_templates_active
    ON cx_format_templates(is_active);

CREATE TABLE IF NOT EXISTS cx_clients (
    id SERIAL PRIMARY KEY,
    crm_client_id INTEGER,
    name VARCHAR(150) NOT NULL,
    sector VARCHAR(80),
    tone_of_voice TEXT,
    logo_url TEXT,
    logo_upload_path TEXT,
    primary_color VARCHAR(20),
    secondary_color VARCHAR(20),
    website_url TEXT,
    brand_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    analysis_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    price_policy VARCHAR(30) NOT NULL DEFAULT 'hide_price',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_cx_clients_crm_client
        FOREIGN KEY (crm_client_id)
        REFERENCES tbl_cliente(id_cliente)
        ON DELETE SET NULL,
    CONSTRAINT chk_cx_client_price_policy
        CHECK (price_policy IN ('hide_price', 'show_price'))
);

CREATE INDEX IF NOT EXISTS idx_cx_clients_created_at
    ON cx_clients(created_at DESC);

CREATE TABLE IF NOT EXISTS cx_campaigns (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL
        REFERENCES cx_clients(id) ON DELETE RESTRICT,
    name VARCHAR(200) NOT NULL,
    objective VARCHAR(120),
    campaign_text TEXT,
    cta_text TEXT,
    show_price BOOLEAN NOT NULL DEFAULT FALSE,
    budget_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    reserved_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    spent_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_campaign_status
        CHECK (status IN ('draft', 'active', 'paused', 'closed')),
    CONSTRAINT chk_cx_campaign_budget
        CHECK (
            budget_usd >= 0 AND reserved_usd >= 0 AND spent_usd >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_cx_campaigns_client
    ON cx_campaigns(client_id);
CREATE INDEX IF NOT EXISTS idx_cx_campaigns_created_at
    ON cx_campaigns(created_at DESC);

CREATE TABLE IF NOT EXISTS cx_campaign_variations (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL
        REFERENCES cx_campaigns(id) ON DELETE CASCADE,
    label VARCHAR(5) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_campaign_variation_label UNIQUE (campaign_id, label),
    CONSTRAINT chk_cx_variation_label
        CHECK (label IN ('A', 'B', 'C', 'D'))
);

CREATE INDEX IF NOT EXISTS idx_cx_campaign_variations_campaign
    ON cx_campaign_variations(campaign_id);

CREATE TABLE IF NOT EXISTS cx_variation_steps (
    id SERIAL PRIMARY KEY,
    variation_id INTEGER NOT NULL
        REFERENCES cx_campaign_variations(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    format_template_id INTEGER NOT NULL
        REFERENCES cx_format_templates(id) ON DELETE RESTRICT,
    mockup VARCHAR(20) NOT NULL,
    scene_description TEXT,
    rendered_prompt TEXT,
    prompt_status VARCHAR(20) NOT NULL DEFAULT 'draft',
    script_text TEXT,
    script_status VARCHAR(20) NOT NULL DEFAULT 'draft',
    engine VARCHAR(20) NOT NULL,
    asset_url TEXT,
    asset_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_variation_step_position UNIQUE (variation_id, position),
    CONSTRAINT chk_cx_step_position CHECK (position > 0),
    CONSTRAINT chk_cx_step_mockup
        CHECK (mockup IN ('portal', 'tv', 'celular', 'tablet')),
    CONSTRAINT chk_cx_step_engine
        CHECK (engine IN ('gpt_image_2', 'higgsfield')),
    CONSTRAINT chk_cx_step_asset_status
        CHECK (
            asset_status IN (
                'pending', 'generating', 'done', 'failed',
                'approved', 'rejected'
            )
        ),
    CONSTRAINT chk_cx_step_prompt_status
        CHECK (prompt_status IN ('draft', 'generated', 'reviewed', 'approved')),
    CONSTRAINT chk_cx_step_script_status
        CHECK (script_status IN ('draft', 'generated', 'reviewed', 'approved'))
);

CREATE INDEX IF NOT EXISTS idx_cx_variation_steps_variation
    ON cx_variation_steps(variation_id, position);
CREATE INDEX IF NOT EXISTS idx_cx_variation_steps_format
    ON cx_variation_steps(format_template_id);

CREATE TABLE IF NOT EXISTS cx_generation_jobs (
    id BIGSERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL
        REFERENCES cx_campaigns(id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES cx_variation_steps(id) ON DELETE CASCADE,
    format_template_id INTEGER
        REFERENCES cx_format_templates(id) ON DELETE RESTRICT,
    job_type VARCHAR(30) NOT NULL,
    provider VARCHAR(30) NOT NULL,
    model VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    prompt TEXT,
    script_text TEXT,
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    actual_cost_usd NUMERIC(12, 6),
    error_message TEXT,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_generation_job_type
        CHECK (
            job_type IN (
                'prompt', 'script', 'image', 'mockup',
                'video_payload', 'display_motion_payload'
            )
        ),
    CONSTRAINT chk_cx_generation_provider
        CHECK (provider IN ('openrouter', 'higgsfield')),
    CONSTRAINT chk_cx_generation_status
        CHECK (
            status IN (
                'queued', 'generating', 'review', 'approved', 'done',
                'failed', 'ready_for_higgsfield'
            )
        ),
    CONSTRAINT chk_cx_generation_cost
        CHECK (
            estimated_cost_usd >= 0
            AND (actual_cost_usd IS NULL OR actual_cost_usd >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_cx_generation_jobs_campaign
    ON cx_generation_jobs(campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_generation_jobs_step
    ON cx_generation_jobs(step_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_generation_references (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL
        REFERENCES cx_generation_jobs(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    asset_path TEXT NOT NULL,
    original_name VARCHAR(255),
    mime_type VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cx_generation_reference_position UNIQUE (job_id, position),
    CONSTRAINT chk_cx_generation_reference_position CHECK (position BETWEEN 1 AND 2)
);

CREATE TABLE IF NOT EXISTS cx_generated_assets (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL
        REFERENCES cx_generation_jobs(id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES cx_variation_steps(id) ON DELETE CASCADE,
    asset_type VARCHAR(20) NOT NULL,
    asset_url TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,
    title VARCHAR(200),
    caption TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'done',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_generated_asset_type
        CHECK (asset_type IN ('image', 'video', 'mockup')),
    CONSTRAINT chk_cx_generated_asset_status
        CHECK (status IN ('done', 'approved', 'rejected')),
    CONSTRAINT chk_cx_generated_asset_position CHECK (position > 0)
);

CREATE INDEX IF NOT EXISTS idx_cx_generated_assets_step
    ON cx_generated_assets(step_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_generated_assets_job_position
    ON cx_generated_assets(job_id, position);

CREATE TABLE IF NOT EXISTS cx_format_references (
    id BIGSERIAL PRIMARY KEY,
    format_template_id INTEGER NOT NULL
        REFERENCES cx_format_templates(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    reference_type VARCHAR(20) NOT NULL DEFAULT 'full_mockup',
    prompt TEXT,
    asset_url TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'approved',
    source_job_id BIGINT
        REFERENCES cx_generation_jobs(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cx_format_reference_slot UNIQUE (format_template_id, slot),
    CONSTRAINT chk_cx_format_reference_slot CHECK (slot BETWEEN 1 AND 4),
    CONSTRAINT chk_cx_format_reference_type
        CHECK (reference_type IN ('background', 'full_mockup')),
    CONSTRAINT chk_cx_format_reference_status
        CHECK (status IN ('draft', 'approved', 'archived'))
);

CREATE TABLE IF NOT EXISTS cx_video_input_assets (
    job_id BIGINT NOT NULL
        REFERENCES cx_generation_jobs(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    asset_id BIGINT NOT NULL
        REFERENCES cx_generated_assets(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, position),
    CONSTRAINT uq_cx_video_input_asset UNIQUE (job_id, asset_id),
    CONSTRAINT chk_cx_video_input_position CHECK (position BETWEEN 1 AND 4)
);

CREATE TABLE IF NOT EXISTS cx_generation_cost_ledger (
    id BIGSERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL
        REFERENCES cx_campaigns(id) ON DELETE CASCADE,
    job_id BIGINT NOT NULL
        REFERENCES cx_generation_jobs(id) ON DELETE CASCADE,
    entry_type VARCHAR(20) NOT NULL,
    amount_usd NUMERIC(12, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_cost_entry_type
        CHECK (entry_type IN ('reservation', 'charge', 'release')),
    CONSTRAINT chk_cx_cost_amount CHECK (amount_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cx_generation_cost_campaign
    ON cx_generation_cost_ledger(campaign_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_public_creative_collections (
    id BIGSERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL
        REFERENCES cx_campaigns(id) ON DELETE CASCADE,
    token VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT chk_cx_public_collection_state
        CHECK (
            (is_active = TRUE AND revoked_at IS NULL)
            OR is_active = FALSE
        )
);

CREATE INDEX IF NOT EXISTS idx_cx_public_collection_campaign
    ON cx_public_creative_collections(campaign_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_public_collection_assets (
    collection_id BIGINT NOT NULL
        REFERENCES cx_public_creative_collections(id) ON DELETE CASCADE,
    asset_id BIGINT NOT NULL
        REFERENCES cx_generated_assets(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (collection_id, asset_id),
    CONSTRAINT uq_cx_public_collection_position UNIQUE (collection_id, position),
    CONSTRAINT chk_cx_public_asset_position CHECK (position > 0)
);

-- Compatibilidade caso uma versão anterior da migration já tenha sido aplicada.
ALTER TABLE cx_channels
    ADD COLUMN IF NOT EXISTS partner_primary_color VARCHAR(20),
    ADD COLUMN IF NOT EXISTS partner_secondary_color VARCHAR(20),
    ADD COLUMN IF NOT EXISTS brand_guidelines JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS reference_assets JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE cx_format_templates
    ADD COLUMN IF NOT EXISTS safe_area JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS responsive_rules TEXT,
    ADD COLUMN IF NOT EXISTS background_guidance TEXT,
    ADD COLUMN IF NOT EXISTS foreground_guidance TEXT,
    ADD COLUMN IF NOT EXISTS max_reference_variants INTEGER NOT NULL DEFAULT 4;

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS crm_client_id INTEGER,
    ADD COLUMN IF NOT EXISTS primary_color VARCHAR(20),
    ADD COLUMN IF NOT EXISTS secondary_color VARCHAR(20),
    ADD COLUMN IF NOT EXISTS website_url TEXT,
    ADD COLUMN IF NOT EXISTS brand_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS analysis_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint constraint_row
          JOIN pg_attribute column_row
            ON column_row.attrelid = constraint_row.conrelid
           AND column_row.attnum = ANY(constraint_row.conkey)
         WHERE constraint_row.conrelid = 'cx_clients'::regclass
           AND constraint_row.confrelid = 'tbl_cliente'::regclass
           AND constraint_row.contype = 'f'
           AND column_row.attname = 'crm_client_id'
    ) THEN
        ALTER TABLE cx_clients
            ADD CONSTRAINT fk_cx_clients_crm_client
            FOREIGN KEY (crm_client_id)
            REFERENCES tbl_cliente(id_cliente)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client
    ON cx_clients(crm_client_id)
    WHERE crm_client_id IS NOT NULL;

ALTER TABLE cx_campaigns
    ADD COLUMN IF NOT EXISTS budget_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reserved_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS spent_usd NUMERIC(12, 6) NOT NULL DEFAULT 0;

ALTER TABLE cx_variation_steps
    ADD COLUMN IF NOT EXISTS prompt_status VARCHAR(20) NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS script_text TEXT,
    ADD COLUMN IF NOT EXISTS script_status VARCHAR(20) NOT NULL DEFAULT 'draft';

ALTER TABLE cx_generated_assets
    ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS title VARCHAR(200),
    ADD COLUMN IF NOT EXISTS caption TEXT;
