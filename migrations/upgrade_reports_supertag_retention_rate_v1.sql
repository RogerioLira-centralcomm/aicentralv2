-- Upgrade an installation that already ran add_reports_supertag_v1.sql.
ALTER TABLE cadu_reports_supertag_events
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '90 days';

CREATE INDEX IF NOT EXISTS cadu_reports_supertag_events_expiry_idx
    ON cadu_reports_supertag_events (expires_at,id);

CREATE TABLE IF NOT EXISTS cadu_reports_supertag_ip_rate_limits (
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    ip_digest CHAR(64) NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (site_id,ip_digest,bucket_start)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_ip_rate_limits_time_idx
    ON cadu_reports_supertag_ip_rate_limits (bucket_start);
