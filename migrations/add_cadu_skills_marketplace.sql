-- Fundação do Cadu Skills: publicação, personalização, compartilhamento e créditos.
-- Idempotente e sem ativar execuções de modelo.

CREATE TABLE IF NOT EXISTS cadu_skill_definitions (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(180) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    category VARCHAR(100) NOT NULL DEFAULT 'Produtividade',
    owner_type VARCHAR(24) NOT NULL DEFAULT 'centralx',
    visibility VARCHAR(24) NOT NULL DEFAULT 'public',
    status VARCHAR(24) NOT NULL DEFAULT 'draft',
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_skill_visibility_ck CHECK (visibility IN ('public', 'agency', 'private')),
    CONSTRAINT cadu_skill_status_ck CHECK (status IN ('draft', 'published', 'archived'))
);

CREATE TABLE IF NOT EXISTS cadu_skill_versions (
    id BIGSERIAL PRIMARY KEY,
    skill_id BIGINT NOT NULL REFERENCES cadu_skill_definitions(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    instructions TEXT NOT NULL,
    model VARCHAR(100) NOT NULL DEFAULT 'openai/gpt-4o-mini',
    credit_cost INTEGER NOT NULL DEFAULT 1,
    input_limit INTEGER NOT NULL DEFAULT 4000,
    output_limit INTEGER NOT NULL DEFAULT 1400,
    published_at TIMESTAMPTZ,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (skill_id, version),
    CONSTRAINT cadu_skill_credit_cost_ck CHECK (credit_cost > 0),
    CONSTRAINT cadu_skill_limits_ck CHECK (input_limit > 0 AND output_limit > 0)
);

CREATE TABLE IF NOT EXISTS cadu_skill_customizations (
    id BIGSERIAL PRIMARY KEY,
    skill_version_id BIGINT NOT NULL REFERENCES cadu_skill_versions(id),
    client_id BIGINT NOT NULL,
    brand_id BIGINT,
    project_id BIGINT,
    name VARCHAR(180) NOT NULL,
    context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'draft',
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_skill_custom_status_ck CHECK (status IN ('draft', 'published', 'archived'))
);

CREATE TABLE IF NOT EXISTS cadu_skill_shares (
    id BIGSERIAL PRIMARY KEY,
    customization_id BIGINT NOT NULL REFERENCES cadu_skill_customizations(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    permission VARCHAR(12) NOT NULL DEFAULT 'view',
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_skill_share_permission_ck CHECK (permission IN ('view', 'run'))
);

CREATE TABLE IF NOT EXISTS cadu_skill_runs (
    id BIGSERIAL PRIMARY KEY,
    customization_id BIGINT REFERENCES cadu_skill_customizations(id),
    skill_version_id BIGINT NOT NULL REFERENCES cadu_skill_versions(id),
    client_plan_id BIGINT NOT NULL REFERENCES cadu_client_plans(id),
    user_id BIGINT NOT NULL,
    model VARCHAR(100) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'reserved',
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB,
    provider_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT cadu_skill_run_status_ck CHECK (status IN ('reserved', 'running', 'succeeded', 'failed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS cadu_credit_ledger (
    id BIGSERIAL PRIMARY KEY,
    client_plan_id BIGINT NOT NULL REFERENCES cadu_client_plans(id),
    run_id BIGINT REFERENCES cadu_skill_runs(id),
    kind VARCHAR(24) NOT NULL,
    amount INTEGER NOT NULL,
    idempotency_key VARCHAR(180) NOT NULL UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_credit_ledger_kind_ck CHECK (kind IN ('monthly_grant', 'reserve', 'capture', 'release', 'refund', 'adjustment')),
    CONSTRAINT cadu_credit_ledger_amount_ck CHECK (amount <> 0)
);

CREATE INDEX IF NOT EXISTS idx_cadu_skill_versions_published ON cadu_skill_versions(skill_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_skill_custom_client ON cadu_skill_customizations(client_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_skill_runs_plan ON cadu_skill_runs(client_plan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_credit_ledger_plan ON cadu_credit_ledger(client_plan_id, created_at DESC);

INSERT INTO cadu_skill_definitions (slug, name, summary, category, visibility, status)
VALUES (
    'cadu-media-planning',
    'Planejamento de mídia Cadu',
    'Transforma briefing, contexto de marca e canais disponíveis em um plano de mídia defendível.',
    'Planejamento de mídia',
    'public',
    'published'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    summary = EXCLUDED.summary,
    category = EXCLUDED.category,
    updated_at = NOW();
