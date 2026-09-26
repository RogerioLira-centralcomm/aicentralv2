-- First-party monitoring for Planner sites. Tracking data stays within Cadu;
-- test sessions are stored separately and never enter conversion totals.
CREATE TABLE IF NOT EXISTS cadu_planner_sites (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    name VARCHAR(180) NOT NULL,
    entry_url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    site_type VARCHAR(32) NOT NULL,
    install_token UUID NOT NULL UNIQUE,
    consent_required BOOLEAN NOT NULL DEFAULT TRUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_checked_at TIMESTAMPTZ,
    next_check_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (site_type IN ('campaign', 'institutional', 'ecommerce', 'publisher', 'app', 'other'))
);
CREATE INDEX IF NOT EXISTS cadu_planner_sites_due_idx
    ON cadu_planner_sites (next_check_at) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS cadu_planner_sites_client_idx
    ON cadu_planner_sites (client_id, created_at DESC) WHERE active = TRUE;

CREATE TABLE IF NOT EXISTS cadu_planner_funnels (
    id UUID PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES cadu_planner_sites(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    start_path VARCHAR(500) NOT NULL DEFAULT '/',
    conversion_path VARCHAR(500) NOT NULL DEFAULT '',
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_planner_funnels_site_idx
    ON cadu_planner_funnels (site_id, active, created_at);

CREATE TABLE IF NOT EXISTS cadu_planner_site_events (
    id BIGSERIAL PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES cadu_planner_sites(id) ON DELETE CASCADE,
    funnel_id UUID REFERENCES cadu_planner_funnels(id) ON DELETE SET NULL,
    visitor_hash CHAR(64) NOT NULL,
    event_type VARCHAR(24) NOT NULL,
    path VARCHAR(500) NOT NULL,
    is_test BOOLEAN NOT NULL DEFAULT FALSE,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (event_type IN ('page_view', 'conversion', 'heartbeat'))
);
CREATE INDEX IF NOT EXISTS cadu_planner_site_events_live_idx
    ON cadu_planner_site_events (site_id, occurred_at DESC) WHERE is_test = FALSE;
CREATE INDEX IF NOT EXISTS cadu_planner_site_events_visitor_idx
    ON cadu_planner_site_events (site_id, visitor_hash, occurred_at DESC);

CREATE TABLE IF NOT EXISTS cadu_planner_site_health_checks (
    id BIGSERIAL PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES cadu_planner_sites(id) ON DELETE CASCADE,
    checked_url TEXT NOT NULL DEFAULT '/',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(24) NOT NULL,
    status_code INTEGER,
    response_ms INTEGER,
    detail VARCHAR(180) NOT NULL DEFAULT '',
    CHECK (status IN ('up', 'degraded', 'down', 'blocked'))
);
CREATE INDEX IF NOT EXISTS cadu_planner_site_health_latest_idx
    ON cadu_planner_site_health_checks (site_id, checked_at DESC);
ALTER TABLE cadu_planner_site_health_checks
    ADD COLUMN IF NOT EXISTS checked_url TEXT NOT NULL DEFAULT '/';
