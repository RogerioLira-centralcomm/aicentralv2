-- Persist bounded site-discovery work so a partial scan can continue safely.
ALTER TABLE cadu_reports_flow_discovery_runs
    ADD COLUMN IF NOT EXISTS pending_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS pending_truncated BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE cadu_reports_flow_discovery_runs
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_discovery_pending_urls_array;
ALTER TABLE cadu_reports_flow_discovery_runs
    ADD CONSTRAINT cadu_reports_flow_discovery_pending_urls_array
    CHECK (jsonb_typeof(pending_urls)='array');
