-- Funnel event coverage and explicit MCC ownership for Reports integrations.
ALTER TABLE cadu_reports_ingest_keys
    ADD COLUMN IF NOT EXISTS manager_external_id VARCHAR(10);
ALTER TABLE cadu_reports_campaigns
    ADD COLUMN IF NOT EXISTS channel_type VARCHAR(64);

-- A client owns one reusable public loader URL; individual flows are selected by CF code.
CREATE TABLE IF NOT EXISTS cadu_reports_flow_registry (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    flow_code VARCHAR(16) NOT NULL UNIQUE,
    tag_id UUID NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','paused')),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    CONSTRAINT cadu_reports_flow_registry_tag_fk
        FOREIGN KEY (tag_id,organization_id,client_id)
        REFERENCES cadu_reports_site_tags (id,organization_id,client_id),
    CONSTRAINT cadu_reports_flow_registry_id_scope_unique UNIQUE (id,organization_id,client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_registry_client_idx
    ON cadu_reports_flow_registry (organization_id,client_id,created_at DESC);
ALTER TABLE cadu_reports_site_tags ADD COLUMN IF NOT EXISTS tag_kind VARCHAR(16) NOT NULL DEFAULT 'flow';
ALTER TABLE cadu_reports_flow_steps DROP CONSTRAINT IF EXISTS cadu_reports_flow_step_kind;
ALTER TABLE cadu_reports_flow_steps ADD CONSTRAINT cadu_reports_flow_step_kind
    CHECK (step_kind IN ('page','conversion','form','event','whatsapp'));
CREATE TABLE IF NOT EXISTS cadu_reports_flow_events_test (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    flow_id UUID NOT NULL,
    flow_code VARCHAR(16) NOT NULL,
    event_kind VARCHAR(24) NOT NULL,
    page_path VARCHAR(1000) NOT NULL,
    source_label VARCHAR(160),
    session_id UUID NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_flow_test_flow_fk
        FOREIGN KEY (flow_id,organization_id,client_id)
        REFERENCES cadu_reports_flow_registry (id,organization_id,client_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_test_idx
    ON cadu_reports_flow_events_test (organization_id,client_id,flow_id,created_at DESC);

ALTER TABLE cadu_reports_flow_events
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_event_kind;
ALTER TABLE cadu_reports_flow_events
    ADD CONSTRAINT cadu_reports_flow_event_kind
    CHECK (event_kind IN ('page_view','heartbeat','conversion','form_submit','click','whatsapp_click','custom_event'));
ALTER TABLE cadu_reports_flow_events ADD COLUMN IF NOT EXISTS event_name VARCHAR(120);

CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_kind_time_idx
    ON cadu_reports_flow_events (organization_id,client_id,event_kind,occurred_at DESC);
