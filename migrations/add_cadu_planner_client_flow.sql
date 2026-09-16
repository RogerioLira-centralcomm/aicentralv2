-- Planner do cliente: contexto da campanha, versões imutáveis e ponte comercial.
-- Não altera nem migra sessões do SmartPlanner comercial legado.
ALTER TABLE cadu_planner_plans
    ADD COLUMN IF NOT EXISTS advertiser_name VARCHAR(180),
    ADD COLUMN IF NOT EXISTS campaign_name VARCHAR(180);

CREATE TABLE IF NOT EXISTS cadu_planner_plan_versions (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (plan_id, version_number)
);
CREATE INDEX IF NOT EXISTS cadu_planner_plan_versions_plan_idx
    ON cadu_planner_plan_versions (plan_id, version_number DESC);

CREATE TABLE IF NOT EXISTS cadu_planner_quote_requests (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE RESTRICT,
    plan_version_id UUID NOT NULL REFERENCES cadu_planner_plan_versions(id) ON DELETE RESTRICT,
    client_id BIGINT NOT NULL,
    requested_by BIGINT NOT NULL,
    scope VARCHAR(40) NOT NULL,
    message VARCHAR(2000),
    status VARCHAR(32) NOT NULL DEFAULT 'requested',
    assigned_executive_id BIGINT,
    crm_quote_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    CHECK (scope IN ('full_operation', 'media_inventory', 'specific_channels')),
    CHECK (status IN ('requested', 'in_review', 'needs_information', 'proposal_available', 'approved', 'closed'))
);
CREATE INDEX IF NOT EXISTS cadu_planner_quote_requests_client_recent_idx
    ON cadu_planner_quote_requests (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS cadu_planner_quote_requests_plan_idx
    ON cadu_planner_quote_requests (plan_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_planner_user_notifications (
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    notified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (client_id, user_id)
);
