CREATE TABLE IF NOT EXISTS cadu_connect_report_ai_runs (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL REFERENCES cadu_connect_report_workspaces(id) ON DELETE CASCADE,
    source_id BIGINT NOT NULL REFERENCES cadu_connect_report_sources(id) ON DELETE CASCADE,
    created_by INTEGER NOT NULL,
    operation VARCHAR(40) NOT NULL,
    model VARCHAR(120) NOT NULL,
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL CHECK (status IN ('succeeded','failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_connect_report_ai_runs_source_idx ON cadu_connect_report_ai_runs(source_id,created_at DESC);
