-- Biblioteca viva do Estúdio: sistema visual, template HTML e variações.

CREATE TABLE IF NOT EXISTS cx_brand_visual_systems (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES cx_clients(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    tokens JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'approved',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_brand_visual_system_status
        CHECK (status IN ('draft', 'approved', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_cx_brand_visual_systems_client
    ON cx_brand_visual_systems (client_id, status);

CREATE TABLE IF NOT EXISTS cx_compose_templates (
    id BIGSERIAL PRIMARY KEY,
    visual_system_id BIGINT REFERENCES cx_brand_visual_systems(id)
        ON DELETE SET NULL,
    format_template_id INTEGER REFERENCES cx_format_templates(id)
        ON DELETE SET NULL,
    slug VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    family VARCHAR(40) NOT NULL,
    html_key VARCHAR(120) NOT NULL,
    adjust_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_compose_template_kind
        CHECK (kind IN ('layout', 'script'))
);

CREATE INDEX IF NOT EXISTS idx_cx_compose_templates_family
    ON cx_compose_templates (family, kind);

CREATE TABLE IF NOT EXISTS cx_compose_variations (
    id BIGSERIAL PRIMARY KEY,
    template_id BIGINT NOT NULL
        REFERENCES cx_compose_templates(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'experimental',
    approve_count INTEGER NOT NULL DEFAULT 0,
    reject_count INTEGER NOT NULL DEFAULT 0,
    preview_asset_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_compose_variation_status
        CHECK (status IN ('experimental', 'approved', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_cx_compose_variations_template
    ON cx_compose_variations (template_id, status, approve_count DESC);

CREATE TABLE IF NOT EXISTS cx_compose_feedback (
    id BIGSERIAL PRIMARY KEY,
    variation_id BIGINT NOT NULL
        REFERENCES cx_compose_variations(id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES cx_campaigns(id) ON DELETE SET NULL,
    asset_id BIGINT REFERENCES cx_generated_assets(id) ON DELETE SET NULL,
    verdict VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_compose_feedback_verdict
        CHECK (verdict IN ('approved', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_cx_compose_feedback_variation
    ON cx_compose_feedback (variation_id, created_at DESC);

INSERT INTO cx_brand_visual_systems (client_id, name, tokens, status)
SELECT NULL, 'Sistema demo',
       '{"palette":["#1E4D4F","#E50914"],"fonts":{"display":null,"body":null},"spacing":{"unit":8,"cta_gap_max":16}}'::jsonb,
       'approved'
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_brand_visual_systems WHERE name = 'Sistema demo'
       );

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'square-feed-v1', 'Feed quadrado', 'layout', 'square_1x1',
       'square_1x1.html',
       '{"headline_font_size":{"min":22,"max":32,"step":2},"photo_side":["left","right"],"cta_gap":{"min":8,"max":16}}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'square-feed-v1'
       );

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'netflix-script-v1', 'Roteiro Netflix 16:9', 'script', 'sequence_16x9',
       'sequence_16x9.html',
       '{"scenography":["line","change"],"cast_count":[1,2],"copy_on_last_only":[true,false]}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'netflix-script-v1'
       );

INSERT INTO cx_compose_variations (template_id, name, params, status)
SELECT t.id, 'Foto à direita',
       '{"headline_font_size":26,"photo_side":"right","cta_gap":12}'::jsonb,
       'experimental'
  FROM cx_compose_templates t
 WHERE t.slug = 'square-feed-v1'
   AND NOT EXISTS (
           SELECT 1 FROM cx_compose_variations v
            WHERE v.template_id = t.id AND v.name = 'Foto à direita'
       );

INSERT INTO cx_compose_variations (template_id, name, params, status)
SELECT t.id, 'Gancho → Fechamento',
       '{"scenography":"line","cast_count":1,"copy_on_last_only":true}'::jsonb,
       'experimental'
  FROM cx_compose_templates t
 WHERE t.slug = 'netflix-script-v1'
   AND NOT EXISTS (
           SELECT 1 FROM cx_compose_variations v
            WHERE v.template_id = t.id AND v.name = 'Gancho → Fechamento'
       );
