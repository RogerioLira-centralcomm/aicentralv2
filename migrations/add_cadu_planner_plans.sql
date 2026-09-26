-- O plano é a unidade de trabalho do novo Planner. Catálogos permanecem
-- canônicos; esta tabela guarda somente as decisões e o contexto da equipe.
CREATE TABLE IF NOT EXISTS cadu_planner_plans (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    project_ref TEXT,
    brand_ref TEXT,
    title VARCHAR(180) NOT NULL,
    objective VARCHAR(80),
    status VARCHAR(24) NOT NULL DEFAULT 'draft',
    briefing JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    CHECK (status IN ('draft', 'ready', 'archived'))
);

CREATE INDEX IF NOT EXISTS cadu_planner_plans_client_updated_idx
    ON cadu_planner_plans (client_id, updated_at DESC)
    WHERE archived_at IS NULL;

CREATE TABLE IF NOT EXISTS cadu_planner_plan_items (
    id BIGSERIAL PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    kind VARCHAR(24) NOT NULL,
    resource_id TEXT NOT NULL,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (plan_id, kind, resource_id),
    CHECK (kind IN ('audiencias', 'canais', 'formatos', 'interativos', 'places', 'portais'))
);

CREATE INDEX IF NOT EXISTS cadu_planner_plan_items_plan_idx
    ON cadu_planner_plan_items (plan_id, kind, created_at);
