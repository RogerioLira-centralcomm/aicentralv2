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

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'editorial-still-4x5', 'Editorial still', 'layout', 'portrait_4x5',
       'editorial_still.html',
       '{"headline_font_size":{"min":14,"max":32,"step":2},"cta_gap":{"min":6,"max":16}}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'editorial-still-4x5'
       );

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'editorial-still-1x1', 'Editorial still', 'layout', 'square_1x1',
       'editorial_still.html',
       '{"headline_font_size":{"min":14,"max":32,"step":2},"cta_gap":{"min":6,"max":16}}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'editorial-still-1x1'
       );

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'product-hero-story', 'Produto herói', 'layout', 'story_9x16',
       'product_hero.html',
       '{"headline_font_size":{"min":14,"max":32,"step":2},"cta_gap":{"min":6,"max":16}}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'product-hero-story'
       );

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'ugc-face-story', 'UGC / rosto', 'layout', 'story_9x16',
       'ugc_face.html',
       '{"headline_font_size":{"min":14,"max":32,"step":2},"cta_gap":{"min":6,"max":16}}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'ugc-face-story'
       );

INSERT INTO cx_compose_templates (
    slug, name, kind, family, html_key, adjust_schema
)
SELECT 'offer-stack-1x1', 'Oferta em faixa', 'layout', 'square_1x1',
       'offer_stack.html',
       '{"headline_font_size":{"min":22,"max":32,"step":2},"photo_side":["left","right"],"cta_gap":{"min":8,"max":16}}'::jsonb
 WHERE NOT EXISTS (
           SELECT 1 FROM cx_compose_templates WHERE slug = 'offer-stack-1x1'
       );

INSERT INTO cx_compose_variations (template_id, name, params, status)
SELECT t.id, 'Papel editorial',
       '{"headline_font_size":28,"cta_gap":12,"regions":[{"tipo":"headline","x":6,"y":16,"w":24,"h":28},{"tipo":"foto_produto","x":30,"y":14,"w":42,"h":58},{"tipo":"logo","x":74,"y":16,"w":18,"h":14},{"tipo":"cta","x":8,"y":80,"w":84,"h":8},{"tipo":"legal","x":8,"y":90,"w":84,"h":6}]}'::jsonb,
       'experimental'
  FROM cx_compose_templates t
 WHERE t.slug = 'editorial-still-4x5'
   AND NOT EXISTS (
           SELECT 1 FROM cx_compose_variations v
            WHERE v.template_id = t.id AND v.name = 'Papel editorial'
       );

INSERT INTO cx_compose_variations (template_id, name, params, status)
SELECT t.id, 'Herói no poço',
       '{"headline_font_size":28,"cta_gap":12,"regions":[{"tipo":"foto_produto","x":0,"y":0,"w":100,"h":78},{"tipo":"headline","x":7,"y":72,"w":86,"h":12},{"tipo":"cta","x":20,"y":86,"w":60,"h":8}]}'::jsonb,
       'experimental'
  FROM cx_compose_templates t
 WHERE t.slug = 'product-hero-story'
   AND NOT EXISTS (
           SELECT 1 FROM cx_compose_variations v
            WHERE v.template_id = t.id AND v.name = 'Herói no poço'
       );

INSERT INTO cx_compose_variations (template_id, name, params, status)
SELECT t.id, 'Rosto + caption',
       '{"headline_font_size":26,"cta_gap":10,"regions":[{"tipo":"foto_pessoa","x":0,"y":0,"w":100,"h":100},{"tipo":"headline","x":6,"y":72,"w":70,"h":10},{"tipo":"cta","x":6,"y":84,"w":50,"h":8}]}'::jsonb,
       'experimental'
  FROM cx_compose_templates t
 WHERE t.slug = 'ugc-face-story'
   AND NOT EXISTS (
           SELECT 1 FROM cx_compose_variations v
            WHERE v.template_id = t.id AND v.name = 'Rosto + caption'
       );

INSERT INTO cx_compose_variations (template_id, name, params, status)
SELECT t.id, 'Split oferta',
       '{"headline_font_size":26,"photo_side":"right","cta_gap":12}'::jsonb,
       'experimental'
  FROM cx_compose_templates t
 WHERE t.slug = 'offer-stack-1x1'
   AND NOT EXISTS (
           SELECT 1 FROM cx_compose_variations v
            WHERE v.template_id = t.id AND v.name = 'Split oferta'
       );
