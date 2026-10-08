-- Plano final do Cadu Planner: documento gerado por IA, versionado por plano, com link público próprio.
-- Aditivo e idempotente. Depende de add_cadu_planner_plans.sql (revision vem de add_cadu_planner_cobuild.sql,
-- mas aqui é só copiada como número: sem dependência de esquema).
-- Toda geração, edição ou revisão grava uma versão nova; nada é sobrescrito.
CREATE TABLE IF NOT EXISTS cadu_planner_final_plans (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    version INTEGER NOT NULL,
    plan_revision INTEGER NOT NULL DEFAULT 0,
    source_hash VARCHAR(64) NOT NULL,
    document JSONB NOT NULL DEFAULT '{}'::jsonb,
    edited_sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    origin VARCHAR(16) NOT NULL DEFAULT 'generated',
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    instructions TEXT,
    charged_tokens INTEGER NOT NULL DEFAULT 0,
    prompt_version VARCHAR(40),
    project_source_id BIGINT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_planner_final_plans_version_uniq UNIQUE (plan_id, version),
    CONSTRAINT cadu_planner_final_plans_origin_check CHECK (origin IN ('generated', 'edited', 'revised'))
);
CREATE INDEX IF NOT EXISTS cadu_planner_final_plans_client_idx ON cadu_planner_final_plans (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_planner_final_plan_shares (
    plan_id UUID PRIMARY KEY REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    share_token VARCHAR(64) NOT NULL UNIQUE,
    share_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
