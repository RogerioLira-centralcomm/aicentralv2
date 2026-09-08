-- Ambientes HTML/CSS para visualizar criativos em portais e CTV.
-- Migração aditiva e idempotente.

CREATE TABLE IF NOT EXISTS cx_creative_viewer_profiles (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    viewer_kind VARCHAR(20) NOT NULL,
    source_url TEXT NOT NULL,
    logo_asset_ref TEXT,
    palette JSONB NOT NULL DEFAULT '{}'::jsonb,
    shell_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    disclaimer TEXT NOT NULL DEFAULT
        'Simulação de ambiente · sem afiliação com o veículo',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_viewer_profile_kind
        CHECK (viewer_kind IN ('portal', 'tv')),
    CONSTRAINT chk_cx_viewer_profile_palette_object
        CHECK (jsonb_typeof(palette) = 'object'),
    CONSTRAINT chk_cx_viewer_profile_shell_object
        CHECK (jsonb_typeof(shell_spec) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_cx_viewer_profiles_kind
    ON cx_creative_viewer_profiles(viewer_kind, is_active);

ALTER TABLE cx_format_templates
    ADD COLUMN IF NOT EXISTS default_viewer_profile_id INTEGER
        REFERENCES cx_creative_viewer_profiles(id) ON DELETE SET NULL;

ALTER TABLE cx_public_collection_assets
    ADD COLUMN IF NOT EXISTS viewer_profile_id INTEGER
        REFERENCES cx_creative_viewer_profiles(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_cx_public_assets_viewer
    ON cx_public_collection_assets(viewer_profile_id);
