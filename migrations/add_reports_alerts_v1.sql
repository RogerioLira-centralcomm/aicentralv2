-- Reports alerts: confirmed incidents with owner, snooze and an audit trail. Additive and replayable.
CREATE TABLE IF NOT EXISTS cadu_reports_alerts (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    rule VARCHAR(40) NOT NULL,
    subject_key VARCHAR(520) NOT NULL DEFAULT '',
    severity VARCHAR(8) NOT NULL CHECK (severity IN ('high','medium','low')),
    status VARCHAR(14) NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','silenced','resolved')),
    resolution VARCHAR(10) CHECK (resolution IN ('auto','manual')),
    title VARCHAR(200) NOT NULL,
    summary TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence)='array'),
    page_path VARCHAR(500),
    occurrences INTEGER NOT NULL DEFAULT 1,
    assigned_to BIGINT,
    acknowledged_by BIGINT,
    acknowledged_at TIMESTAMPTZ,
    silenced_until TIMESTAMPTZ,
    last_notified_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
-- One live alert per subject: a repeat sighting updates it instead of creating a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS cadu_reports_alerts_live_unique
    ON cadu_reports_alerts (site_id, rule, subject_key) WHERE status <> 'resolved';
CREATE INDEX IF NOT EXISTS cadu_reports_alerts_client_idx
    ON cadu_reports_alerts (client_id, status, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_alert_events (
    id BIGSERIAL PRIMARY KEY,
    alert_id UUID NOT NULL REFERENCES cadu_reports_alerts(id) ON DELETE CASCADE,
    kind VARCHAR(24) NOT NULL,
    actor_user_id BIGINT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_reports_alert_events_alert_idx ON cadu_reports_alert_events (alert_id, created_at DESC);
