-- Link Tester: three independent reports may share one URL, never one score.
CREATE TABLE IF NOT EXISTS cadu_planner_link_test_runs (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    mode VARCHAR(16) NOT NULL,
    original_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    score SMALLINT NOT NULL,
    status_label VARCHAR(48) NOT NULL,
    result JSONB NOT NULL,
    public_token UUID UNIQUE,
    shared_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (mode IN ('destination', 'media', 'agentic')),
    CHECK (score BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS cadu_planner_link_test_runs_client_created_idx
    ON cadu_planner_link_test_runs (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS cadu_planner_link_test_runs_domain_idx
    ON cadu_planner_link_test_runs ((split_part(regexp_replace(final_url, '^https?://', ''), '/', 1)));
CREATE INDEX IF NOT EXISTS cadu_planner_link_test_runs_public_idx
    ON cadu_planner_link_test_runs (public_token) WHERE revoked_at IS NULL;

ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS public_token UUID UNIQUE;
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS shared_at TIMESTAMPTZ;
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS project_ref TEXT;
CREATE INDEX IF NOT EXISTS cadu_planner_link_test_runs_project_idx
    ON cadu_planner_link_test_runs (client_id, project_ref, created_at DESC)
    WHERE project_ref IS NOT NULL;
