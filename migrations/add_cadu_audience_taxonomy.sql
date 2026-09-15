-- Taxonomia V2 de audiências CADU.
-- Migração aditiva: não remove nem altera categoria_id/subcategoria_id legados.

CREATE TABLE IF NOT EXISTS cadu_taxonomy_markets (
    slug VARCHAR(80) PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    ordem_exibicao INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO cadu_taxonomy_markets (slug, nome, ordem_exibicao) VALUES
    ('imobiliario-construcao', 'Imobiliário & Construção', 10),
    ('financas-seguros', 'Finanças & Seguros', 20),
    ('varejo-consumo', 'Varejo & Consumo', 30),
    ('servicos-consumidor', 'Serviços ao Consumidor', 40),
    ('b2b-enterprise-industria', 'B2B, Enterprise & Indústria', 50),
    ('automotivo-mobilidade-logistica', 'Automotivo, Mobilidade & Logística', 60),
    ('agronegocio', 'Agronegócio', 70),
    ('saude-bem-estar-beleza', 'Saúde, Bem-estar & Beleza', 80),
    ('educacao-carreira', 'Educação & Carreira', 90),
    ('entretenimento-conteudo-esportes', 'Entretenimento, Conteúdo & Esportes', 100)
ON CONFLICT (slug) DO UPDATE SET
    nome = EXCLUDED.nome,
    ordem_exibicao = EXCLUDED.ordem_exibicao,
    updated_at = NOW();

CREATE TABLE IF NOT EXISTS cadu_audience_taxonomy (
    audience_id INTEGER PRIMARY KEY
        REFERENCES cadu_audiencias(id) ON DELETE CASCADE,
    catalog_role VARCHAR(50) NOT NULL DEFAULT 'conceito de audiência',
    market_scope VARCHAR(20) NOT NULL DEFAULT 'vertical',
    primary_market_slug VARCHAR(80)
        REFERENCES cadu_taxonomy_markets(slug) ON DELETE SET NULL,
    primary_submarket VARCHAR(160),
    b2b_b2c_orientation VARCHAR(30) NOT NULL DEFAULT 'Transversal/indefinido',
    signal_types TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    funnel_stages TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    classification_confidence VARCHAR(20) NOT NULL DEFAULT 'média',
    migration_action VARCHAR(80) NOT NULL DEFAULT 'revisão editorial obrigatória',
    curation_status VARCHAR(30) NOT NULL DEFAULT 'draft',
    canonical_name VARCHAR(300),
    canonical_key VARCHAR(300),
    taxonomy_version VARCHAR(50) NOT NULL DEFAULT 'v2',
    classification_source VARCHAR(100) NOT NULL DEFAULT 'manual',
    classification_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    data_quality_status VARCHAR(30) NOT NULL DEFAULT 'unverified',
    data_origin VARCHAR(80),
    source_reference TEXT,
    source_observed_at TIMESTAMPTZ,
    data_valid_until TIMESTAMPTZ,
    methodology_note TEXT,
    is_estimated BOOLEAN,
    available_channels TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    geographic_scope TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    activation_restrictions TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (market_scope IN ('vertical', 'transversal')),
    CHECK (catalog_role IN (
        'conceito de audiência',
        'contexto/afinidade de conteúdo',
        'perfil transversal',
        'tática de ativação',
        'formato/inventário',
        'inválido/quarentena'
    )),
    CHECK (classification_confidence IN ('alta', 'média', 'baixa')),
    CHECK (curation_status IN ('draft', 'reviewed', 'approved', 'quarantined')),
    CHECK (data_quality_status IN ('unverified', 'estimated', 'verified', 'expired')),
    CHECK (
        (market_scope = 'transversal' AND primary_market_slug IS NULL)
        OR market_scope = 'vertical'
    )
);

ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS classification_metadata JSONB NOT NULL DEFAULT '{}'::JSONB;
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS data_quality_status VARCHAR(30) NOT NULL DEFAULT 'unverified';
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS data_origin VARCHAR(80);
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS source_reference TEXT;
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS source_observed_at TIMESTAMPTZ;
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS data_valid_until TIMESTAMPTZ;
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS methodology_note TEXT;
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS is_estimated BOOLEAN;
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS available_channels TEXT[] NOT NULL DEFAULT '{}'::TEXT[];
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS geographic_scope TEXT[] NOT NULL DEFAULT '{}'::TEXT[];
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS activation_restrictions TEXT[] NOT NULL DEFAULT '{}'::TEXT[];
ALTER TABLE cadu_audience_taxonomy
    ADD COLUMN IF NOT EXISTS canonical_name VARCHAR(300);

CREATE TABLE IF NOT EXISTS cadu_audience_measurements (
    id BIGSERIAL PRIMARY KEY,
    audience_id INTEGER NOT NULL
        REFERENCES cadu_audiencias(id) ON DELETE CASCADE,
    metric_code VARCHAR(80) NOT NULL,
    value_numeric NUMERIC(20, 6),
    value_text TEXT,
    unit VARCHAR(40) NOT NULL DEFAULT '',
    channel VARCHAR(80),
    geography VARCHAR(160),
    period_start DATE,
    period_end DATE,
    source_reference TEXT,
    methodology_note TEXT,
    quality_status VARCHAR(30) NOT NULL DEFAULT 'unverified',
    observed_at TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (quality_status IN ('unverified', 'estimated', 'verified', 'expired')),
    CHECK (value_numeric IS NOT NULL OR value_text IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_cadu_audience_measurements_lookup
    ON cadu_audience_measurements (audience_id, metric_code, channel, period_end DESC);

CREATE TABLE IF NOT EXISTS cadu_audience_market_relations (
    audience_id INTEGER NOT NULL
        REFERENCES cadu_audiencias(id) ON DELETE CASCADE,
    market_slug VARCHAR(80) NOT NULL
        REFERENCES cadu_taxonomy_markets(slug) ON DELETE CASCADE,
    relation_type VARCHAR(20) NOT NULL DEFAULT 'related',
    source VARCHAR(100) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (audience_id, market_slug, relation_type),
    CHECK (relation_type IN ('primary', 'related'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_audience_taxonomy_market
    ON cadu_audience_taxonomy (primary_market_slug, catalog_role, curation_status);
CREATE INDEX IF NOT EXISTS idx_cadu_audience_taxonomy_scope
    ON cadu_audience_taxonomy (market_scope, b2b_b2c_orientation);
CREATE INDEX IF NOT EXISTS idx_cadu_audience_taxonomy_signals
    ON cadu_audience_taxonomy USING GIN (signal_types);
CREATE INDEX IF NOT EXISTS idx_cadu_audience_taxonomy_funnel
    ON cadu_audience_taxonomy USING GIN (funnel_stages);
CREATE INDEX IF NOT EXISTS idx_cadu_audience_market_relations_market
    ON cadu_audience_market_relations (market_slug, relation_type, audience_id);
