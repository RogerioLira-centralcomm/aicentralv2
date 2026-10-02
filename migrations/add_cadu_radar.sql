-- Radar de Oportunidades do Cadu.
-- Sinal → Oportunidade (nota Editorial, nota Paga, nota Geo) → plano.
-- Benchmarks de mídia guardam faixas (P25/P50/P75), nunca um número único.

CREATE TABLE IF NOT EXISTS cadu_radar_runs (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    created_by BIGINT,
    brand_ref TEXT,
    project_ref TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    cost JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    lease_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS cadu_radar_runs_client_idx ON cadu_radar_runs (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_radar_signals (
    id UUID PRIMARY KEY,
    run_id UUID REFERENCES cadu_radar_runs(id) ON DELETE SET NULL,
    client_id BIGINT NOT NULL,
    headline TEXT NOT NULL,
    description TEXT,
    source TEXT,
    source_type VARCHAR(24),
    url TEXT,
    published_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entities JSONB NOT NULL DEFAULT '[]'::jsonb,
    topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    geography JSONB NOT NULL DEFAULT '[]'::jsonb,
    industry TEXT,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence NUMERIC(4,3),
    velocity NUMERIC(6,3),
    verification JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS cadu_radar_signals_client_idx ON cadu_radar_signals (client_id, detected_at DESC);

CREATE TABLE IF NOT EXISTS cadu_radar_opportunities (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    run_id UUID REFERENCES cadu_radar_runs(id) ON DELETE SET NULL,
    brand_ref TEXT,
    project_ref TEXT,
    title VARCHAR(240) NOT NULL,
    thesis TEXT,
    editorial_score SMALLINT,
    paid_score SMALLINT,
    geo_scores JSONB NOT NULL DEFAULT '[]'::jsonb,
    score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    penalties JSONB NOT NULL DEFAULT '[]'::jsonb,
    quadrant VARCHAR(16),
    status VARCHAR(16) NOT NULL DEFAULT 'nova',
    signal_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (editorial_score IS NULL OR editorial_score BETWEEN 0 AND 100),
    CHECK (paid_score IS NULL OR paid_score BETWEEN 0 AND 100),
    CHECK (quadrant IS NULL OR quadrant IN ('conteudo', 'midia', 'integrada', 'ignorar')),
    CHECK (status IN ('nova', 'salva', 'em_plano', 'descartada'))
);

CREATE INDEX IF NOT EXISTS cadu_radar_opportunities_client_idx
    ON cadu_radar_opportunities (client_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_media_benchmarks (
    id BIGSERIAL PRIMARY KEY,
    channel VARCHAR(80) NOT NULL,
    objective VARCHAR(40) NOT NULL DEFAULT 'any',
    geo_level VARCHAR(16) NOT NULL DEFAULT 'pais',
    geo VARCHAR(120) NOT NULL DEFAULT 'BR',
    metric VARCHAR(16) NOT NULL,
    p25 NUMERIC(14,4) NOT NULL,
    p50 NUMERIC(14,4) NOT NULL,
    p75 NUMERIC(14,4) NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    source VARCHAR(16) NOT NULL,
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    period VARCHAR(40),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (metric IN ('cpm', 'cpc', 'ctr', 'cpa', 'frequency')),
    CHECK (source IN ('history', 'model_estimate')),
    CHECK (p25 <= p50 AND p50 <= p75),
    UNIQUE (channel, objective, geo_level, geo, metric, source)
);
