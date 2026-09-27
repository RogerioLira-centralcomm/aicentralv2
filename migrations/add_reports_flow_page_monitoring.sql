ALTER TABLE cadu_reports_flow_registry
    ADD COLUMN IF NOT EXISTS monitor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS monitor_interval_minutes SMALLINT NOT NULL DEFAULT 15,
    ADD COLUMN IF NOT EXISTS monitor_status VARCHAR(16) NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS monitor_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS monitor_next_check_at TIMESTAMPTZ;

ALTER TABLE cadu_reports_flow_registry
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_monitor_interval_check;
ALTER TABLE cadu_reports_flow_registry
    ADD CONSTRAINT cadu_reports_flow_monitor_interval_check
    CHECK (monitor_interval_minutes IN (5,15,30,60));

ALTER TABLE cadu_reports_flow_registry
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_monitor_status_check;
ALTER TABLE cadu_reports_flow_registry
    ADD CONSTRAINT cadu_reports_flow_monitor_status_check
    CHECK (monitor_status IN ('unknown','checking','online','degraded','offline'));

CREATE INDEX IF NOT EXISTS cadu_reports_flow_monitor_due_idx
    ON cadu_reports_flow_registry (monitor_next_check_at)
    WHERE monitor_enabled=TRUE AND status='published';

CREATE TABLE IF NOT EXISTS cadu_reports_flow_monitor_checks (
    id BIGSERIAL PRIMARY KEY,
    flow_id UUID NOT NULL REFERENCES cadu_reports_flow_registry(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('online','degraded','offline')),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    pages JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(pages)='array'),
    CONSTRAINT cadu_reports_flow_monitor_check_payload_size
        CHECK (pg_column_size(pages) <= 65536)
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_monitor_history_idx
    ON cadu_reports_flow_monitor_checks (flow_id,checked_at DESC);
