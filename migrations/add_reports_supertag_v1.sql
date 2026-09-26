-- Independent first-party Cadu Super Tag installation and batched event store.
CREATE TABLE IF NOT EXISTS cadu_reports_supertag_sites (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    public_id VARCHAR(32) NOT NULL UNIQUE,
    label VARCHAR(120) NOT NULL,
    allowed_host VARCHAR(253) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{"consent_required":true,"audience_days":90,"visibility_enabled":true}'::jsonb,
    config_version INTEGER NOT NULL DEFAULT 1,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT cadu_reports_supertag_sites_scope_unique UNIQUE (id,organization_id,client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_sites_client_idx
    ON cadu_reports_supertag_sites (organization_id,client_id,created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_supertag_events (
    id BIGSERIAL PRIMARY KEY,
    site_id UUID NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    event_id UUID NOT NULL,
    visitor_id UUID,
    session_id UUID NOT NULL,
    event_kind VARCHAR(24) NOT NULL,
    event_name VARCHAR(80),
    page_path VARCHAR(500) NOT NULL,
    referrer_host VARCHAR(253),
    attribution JSONB NOT NULL DEFAULT '{}'::jsonb,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    viewport_width SMALLINT,
    viewport_height SMALLINT,
    consent_state VARCHAR(16) NOT NULL DEFAULT 'granted',
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_supertag_events_site_scope_fk
      FOREIGN KEY (site_id,organization_id,client_id)
      REFERENCES cadu_reports_supertag_sites (id,organization_id,client_id) ON DELETE CASCADE,
    CONSTRAINT cadu_reports_supertag_events_event_kind_check
      CHECK (event_kind IN ('page_view','click','whatsapp_click','form_submit','visibility','scroll_depth','custom_event','conversion')),
    CONSTRAINT cadu_reports_supertag_events_consent_check
      CHECK (consent_state = 'granted'),
    CONSTRAINT cadu_reports_supertag_events_idempotent UNIQUE (site_id,event_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_events_site_time_idx
    ON cadu_reports_supertag_events (site_id,occurred_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_events_site_path_time_idx
    ON cadu_reports_supertag_events (site_id,page_path,occurred_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_events_site_session_time_idx
    ON cadu_reports_supertag_events (site_id,session_id,occurred_at);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_events_heatmap_idx
    ON cadu_reports_supertag_events (site_id,page_path,event_kind,occurred_at DESC)
    WHERE event_kind IN ('click','whatsapp_click','visibility','scroll_depth');

CREATE TABLE IF NOT EXISTS cadu_reports_supertag_rate_limits (
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    bucket_start TIMESTAMPTZ NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (site_id,bucket_start)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_rate_limits_time_idx
    ON cadu_reports_supertag_rate_limits (bucket_start);
