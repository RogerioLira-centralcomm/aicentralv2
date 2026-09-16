CREATE TABLE IF NOT EXISTS cadu_planner_review_runs (
    id UUID PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    actor_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    scope VARCHAR(24) NOT NULL CHECK (scope IN ('briefing', 'document', 'recommendation')),
    plan_id UUID NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    document_id INTEGER NULL,
    passes SMALLINT NOT NULL DEFAULT 3 CHECK (passes = 3),
    applied_pass SMALLINT NOT NULL DEFAULT 3 CHECK (applied_pass = 3),
    charged_tokens INTEGER NOT NULL DEFAULT 0 CHECK (charged_tokens >= 0),
    review_note TEXT NULL,
    source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    applied_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((plan_id IS NOT NULL)::integer + (document_id IS NOT NULL)::integer = 1)
);

CREATE INDEX IF NOT EXISTS cadu_planner_review_runs_plan_idx
    ON cadu_planner_review_runs (plan_id, created_at DESC)
    WHERE plan_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS cadu_planner_review_runs_document_idx
    ON cadu_planner_review_runs (document_id, created_at DESC)
    WHERE document_id IS NOT NULL;
