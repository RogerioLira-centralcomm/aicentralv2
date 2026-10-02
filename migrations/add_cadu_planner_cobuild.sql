-- Co-construção do plano de mídia com o Cadu.
-- O Cadu nunca escreve direto no plano: ele grava propostas por seção, e o
-- usuário aceita, edita ou recusa. A revisão do plano protege contra escritas
-- concorrentes (padrão expected_revision dos fluxos do Reports).

ALTER TABLE cadu_planner_plans ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cadu_planner_plans ADD COLUMN IF NOT EXISTS workbench JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE cadu_planner_plans ADD COLUMN IF NOT EXISTS source VARCHAR(24) NOT NULL DEFAULT 'manual';
ALTER TABLE cadu_planner_plans ADD COLUMN IF NOT EXISTS opportunity_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cadu_planner_plans_source_check') THEN
        ALTER TABLE cadu_planner_plans ADD CONSTRAINT cadu_planner_plans_source_check
            CHECK (source IN ('manual', 'radar', 'smart_planner'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS cadu_planner_plans_opportunity_idx
    ON cadu_planner_plans (opportunity_id) WHERE opportunity_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cadu_planner_proposals (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    section VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    rationale TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    base_revision INTEGER NOT NULL DEFAULT 0,
    model VARCHAR(120),
    cost JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_by BIGINT,
    decided_at TIMESTAMPTZ,
    CHECK (status IN ('pending', 'accepted', 'partial', 'rejected', 'superseded'))
);

CREATE INDEX IF NOT EXISTS cadu_planner_proposals_plan_idx
    ON cadu_planner_proposals (plan_id, section, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_planner_plan_events (
    id BIGSERIAL PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    role VARCHAR(8) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    body JSONB NOT NULL DEFAULT '{}'::jsonb,
    proposal_id UUID REFERENCES cadu_planner_proposals(id) ON DELETE SET NULL,
    actor_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (role IN ('user', 'cadu', 'system'))
);

CREATE INDEX IF NOT EXISTS cadu_planner_plan_events_plan_idx
    ON cadu_planner_plan_events (plan_id, created_at);

-- Ponte entre o SmartPlanner interno e o plano comum. A tabela de sessões
-- nasceu no PHP; só altera onde ela existe.
DO $$
BEGIN
    IF to_regclass('public.cadu_smart_planner_sessions') IS NOT NULL THEN
        ALTER TABLE cadu_smart_planner_sessions ADD COLUMN IF NOT EXISTS planner_plan_id UUID;
    END IF;
END $$;
