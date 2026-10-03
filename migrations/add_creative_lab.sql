-- Creative Lab (/lab no host do Studio): bancada de modelos de imagem.
-- Aditiva e isolada: nenhuma tabela do Studio é alterada; nada aqui é lido pelo pipeline de produção.

CREATE TABLE IF NOT EXISTS cx_lab_files (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(48) NOT NULL UNIQUE,
    client_id BIGINT NOT NULL,
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('reference', 'output', 'thumb')),
    mime VARCHAR(40) NOT NULL,
    content BYTEA NOT NULL,
    byte_size INTEGER NOT NULL,
    width INTEGER,
    height INTEGER,
    sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cx_lab_files_sha ON cx_lab_files (client_id, kind, sha256);

-- Uma referência por imagem (sha256) por organização: o mesmo logo nunca aparece duas vezes.
CREATE TABLE IF NOT EXISTS cx_lab_references (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    brand_id BIGINT,
    role VARCHAR(16) NOT NULL,
    label VARCHAR(160) NOT NULL DEFAULT '',
    source VARCHAR(16) NOT NULL DEFAULT 'upload' CHECK (source IN ('brand_asset', 'upload', 'run_output')),
    source_ref TEXT,
    file_id BIGINT NOT NULL REFERENCES cx_lab_files(id),
    thumb_file_id BIGINT REFERENCES cx_lab_files(id),
    sha256 VARCHAR(64) NOT NULL,
    has_person BOOLEAN NOT NULL DEFAULT FALSE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, sha256)
);

CREATE TABLE IF NOT EXISTS cx_lab_experiments (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    scenario_key VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    task VARCHAR(12) NOT NULL CHECK (task IN ('generate', 'edit')),
    brand_id BIGINT,
    brand_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cx_lab_experiments_recent ON cx_lab_experiments (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_lab_runs (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES cx_lab_experiments(id) ON DELETE CASCADE,
    model_key VARCHAR(80) NOT NULL,
    provider VARCHAR(24) NOT NULL,
    provider_model_id VARCHAR(120) NOT NULL,
    profile_version INTEGER NOT NULL DEFAULT 1,
    attempt INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(16) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'skipped', 'blocked')),
    adaptation_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_prompt TEXT NOT NULL DEFAULT '',
    request_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    provider_request_id VARCHAR(160),
    latency_ms INTEGER,
    estimated_cost_usd NUMERIC(10, 5),
    actual_cost_usd NUMERIC(10, 5),
    cost_source VARCHAR(24),
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_file_id BIGINT REFERENCES cx_lab_files(id),
    thumb_file_id BIGINT REFERENCES cx_lab_files(id),
    error JSONB,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cx_lab_runs_experiment ON cx_lab_runs (experiment_id, model_key, attempt DESC);
CREATE INDEX IF NOT EXISTS cx_lab_runs_pending ON cx_lab_runs (status, created_at) WHERE status IN ('queued', 'running');

-- Observador (visão) e TypeSafe ficam separados das notas humanas.
CREATE TABLE IF NOT EXISTS cx_lab_evaluations (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES cx_lab_runs(id) ON DELETE CASCADE,
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('observer', 'typesafe')),
    model VARCHAR(120),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    primary_failure VARCHAR(40),
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,
    cost_usd NUMERIC(10, 5),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cx_lab_evaluations_run ON cx_lab_evaluations (run_id, kind, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_lab_ratings (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES cx_lab_runs(id) ON DELETE CASCADE,
    rater_id BIGINT,
    composition SMALLINT CHECK (composition BETWEEN 1 AND 5),
    product_fidelity SMALLINT CHECK (product_fidelity BETWEEN 1 AND 5),
    brand_fidelity SMALLINT CHECK (brand_fidelity BETWEEN 1 AND 5),
    text_quality SMALLINT CHECK (text_quality BETWEEN 1 AND 5),
    aesthetic SMALLINT CHECK (aesthetic BETWEEN 1 AND 5),
    verdict VARCHAR(12) CHECK (verdict IN ('approved', 'discarded')),
    notes TEXT NOT NULL DEFAULT '',
    blind BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Anotações livres sobre um modelo, um cenário, um experimento ou uma geração.
CREATE TABLE IF NOT EXISTS cx_lab_notes (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    scope VARCHAR(16) NOT NULL CHECK (scope IN ('model', 'scenario', 'experiment', 'run')),
    scope_key VARCHAR(120) NOT NULL,
    body TEXT NOT NULL,
    author_id BIGINT,
    author_name VARCHAR(160),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cx_lab_notes_scope ON cx_lab_notes (client_id, scope, scope_key, created_at DESC);

-- Ajustes sugeridos ao manifesto de um modelo; nunca aplicados sem revisão.
CREATE TABLE IF NOT EXISTS cx_lab_profile_proposals (
    id BIGSERIAL PRIMARY KEY,
    model_key VARCHAR(80) NOT NULL,
    from_version INTEGER NOT NULL,
    failure VARCHAR(40) NOT NULL,
    change JSONB NOT NULL DEFAULT '{}'::jsonb,
    rationale TEXT NOT NULL DEFAULT '',
    evidence_run_ids BIGINT[] NOT NULL DEFAULT '{}',
    status VARCHAR(16) NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by BIGINT,
    UNIQUE (model_key, from_version, failure)
);

-- v2 (2026-10-03): anatomia de peças reais (arquétipo, herói, níveis de copy, elenco, kit, assinatura).
ALTER TABLE cx_lab_references ADD COLUMN IF NOT EXISTS anatomy JSONB;
ALTER TABLE cx_lab_references ADD COLUMN IF NOT EXISTS is_benchmark BOOLEAN NOT NULL DEFAULT FALSE;
