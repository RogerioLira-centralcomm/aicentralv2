-- Reports V1: additive media operations schema. Apply after report workspace tables.
CREATE TABLE IF NOT EXISTS cadu_reports_accounts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    platform VARCHAR(32) NOT NULL,
    external_id VARCHAR(160) NOT NULL,
    name VARCHAR(240) NOT NULL,
    parent_account_id BIGINT REFERENCES cadu_reports_accounts(id) ON DELETE SET NULL,
    account_kind VARCHAR(20) NOT NULL DEFAULT 'advertiser',
    currency CHAR(3),
    time_zone VARCHAR(100),
    status VARCHAR(24) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_accounts_kind_check CHECK (account_kind IN ('manager', 'advertiser')),
    CONSTRAINT cadu_reports_accounts_scope_unique UNIQUE (organization_id, client_id, platform, external_id),
    CONSTRAINT cadu_reports_accounts_id_scope_unique UNIQUE (id, organization_id, client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_accounts_client_idx
    ON cadu_reports_accounts (organization_id, client_id, platform, name);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='cadu_reports_accounts_parent_scope_fk') THEN
        ALTER TABLE cadu_reports_accounts ADD CONSTRAINT cadu_reports_accounts_parent_scope_fk
            FOREIGN KEY (parent_account_id, organization_id, client_id)
            REFERENCES cadu_reports_accounts (id, organization_id, client_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS cadu_reports_campaigns (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    external_id VARCHAR(160) NOT NULL,
    name VARCHAR(240) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'unknown',
    objective VARCHAR(160),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_campaign_account_scope_fk
        FOREIGN KEY (account_id, organization_id, client_id)
        REFERENCES cadu_reports_accounts (id, organization_id, client_id),
    CONSTRAINT cadu_reports_campaign_unique UNIQUE (account_id, external_id),
    CONSTRAINT cadu_reports_campaign_id_scope_unique UNIQUE (id, organization_id, client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_campaigns_client_idx
    ON cadu_reports_campaigns (organization_id, client_id, account_id, name);

CREATE TABLE IF NOT EXISTS cadu_reports_source_runs (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    source_kind VARCHAR(32) NOT NULL,
    external_run_key VARCHAR(200),
    account_id BIGINT,
    campaign_id BIGINT,
    period_start DATE,
    period_end DATE,
    status VARCHAR(24) NOT NULL DEFAULT 'received',
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT cadu_reports_run_account_scope_fk
        FOREIGN KEY (account_id, organization_id, client_id)
        REFERENCES cadu_reports_accounts (id, organization_id, client_id),
    CONSTRAINT cadu_reports_run_campaign_scope_fk
        FOREIGN KEY (campaign_id, organization_id, client_id)
        REFERENCES cadu_reports_campaigns (id, organization_id, client_id),
    CONSTRAINT cadu_reports_run_idempotency_unique
        UNIQUE (organization_id, client_id, source_kind, external_run_key)
);
CREATE INDEX IF NOT EXISTS cadu_reports_source_runs_client_idx
    ON cadu_reports_source_runs (organization_id, client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_ingest_keys (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    label VARCHAR(120) NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    source_kind VARCHAR(32) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cadu_reports_ingest_keys_client_idx
    ON cadu_reports_ingest_keys (organization_id, client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_campaign_daily_metrics (
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    campaign_id BIGINT NOT NULL,
    metric_date DATE NOT NULL,
    source_kind VARCHAR(32) NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (campaign_id, metric_date, source_kind),
    CONSTRAINT cadu_reports_metric_campaign_scope_fk
        FOREIGN KEY (campaign_id, organization_id, client_id)
        REFERENCES cadu_reports_campaigns (id, organization_id, client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_daily_metrics_client_idx
    ON cadu_reports_campaign_daily_metrics (organization_id, client_id, metric_date DESC);

-- Existing reports become usable without a mandatory Workspace project.
ALTER TABLE cadu_connect_report_workspaces ALTER COLUMN project_ref DROP NOT NULL;
ALTER TABLE cadu_connect_report_workspaces ADD COLUMN IF NOT EXISTS account_id BIGINT;
ALTER TABLE cadu_connect_report_workspaces ADD COLUMN IF NOT EXISTS media_campaign_id BIGINT;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='cadu_reports_workspace_account_scope_fk') THEN
        ALTER TABLE cadu_connect_report_workspaces ADD CONSTRAINT cadu_reports_workspace_account_scope_fk
            FOREIGN KEY (account_id, organization_id, client_id)
            REFERENCES cadu_reports_accounts (id, organization_id, client_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='cadu_reports_workspace_campaign_scope_fk') THEN
        ALTER TABLE cadu_connect_report_workspaces ADD CONSTRAINT cadu_reports_workspace_campaign_scope_fk
            FOREIGN KEY (media_campaign_id, organization_id, client_id)
            REFERENCES cadu_reports_campaigns (id, organization_id, client_id);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS cadu_reports_workspace_account_idx
    ON cadu_connect_report_workspaces (organization_id, client_id, account_id, updated_at DESC);

-- Keep historical Link Tester records and attach them to media entities over time.
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS account_id BIGINT;
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS media_campaign_id BIGINT;
CREATE INDEX IF NOT EXISTS cadu_reports_link_runs_client_idx
    ON cadu_planner_link_test_runs (client_id, created_at DESC);

-- Bring over only reports with explicit platform IDs. Names alone are ambiguous.
INSERT INTO cadu_reports_accounts (organization_id,client_id,platform,external_id,name)
SELECT DISTINCT organization_id,client_id,
       CASE lower(trim(document->>'platform'))
           WHEN 'google ads' THEN 'google_ads'
           WHEN 'meta ads' THEN 'meta_ads'
           WHEN 'microsoft ads' THEN 'microsoft_ads'
           ELSE lower(trim(document->>'platform')) END,
       trim(document->>'external_account_id'),trim(document->>'external_account_id')
FROM cadu_connect_report_workspaces
WHERE NULLIF(trim(document->>'platform'),'') IS NOT NULL
  AND NULLIF(trim(document->>'external_account_id'),'') IS NOT NULL
  AND (lower(trim(document->>'platform')) ~ '^[a-z][a-z0-9_]{0,31}$'
       OR lower(trim(document->>'platform')) IN ('google ads','meta ads','microsoft ads'))
  AND length(trim(document->>'external_account_id')) <= 160
ON CONFLICT (organization_id,client_id,platform,external_id) DO NOTHING;

UPDATE cadu_connect_report_workspaces w
SET account_id=a.id
FROM cadu_reports_accounts a
WHERE w.account_id IS NULL AND a.organization_id=w.organization_id AND a.client_id=w.client_id
  AND a.platform=CASE lower(trim(w.document->>'platform'))
      WHEN 'google ads' THEN 'google_ads'
      WHEN 'meta ads' THEN 'meta_ads'
      WHEN 'microsoft ads' THEN 'microsoft_ads'
      ELSE lower(trim(w.document->>'platform')) END
  AND a.external_id=trim(w.document->>'external_account_id');

INSERT INTO cadu_reports_campaigns (organization_id,client_id,account_id,external_id,name)
SELECT DISTINCT ON (w.account_id, trim(w.document->>'external_campaign_id'))
       w.organization_id,w.client_id,w.account_id,trim(w.document->>'external_campaign_id'),w.campaign_name
FROM cadu_connect_report_workspaces w
WHERE w.account_id IS NOT NULL AND NULLIF(trim(w.document->>'external_campaign_id'),'') IS NOT NULL
  AND length(trim(w.document->>'external_campaign_id')) <= 160
ORDER BY w.account_id,trim(w.document->>'external_campaign_id'),w.updated_at DESC
ON CONFLICT (account_id,external_id) DO NOTHING;

UPDATE cadu_connect_report_workspaces w
SET media_campaign_id=c.id
FROM cadu_reports_campaigns c
WHERE w.media_campaign_id IS NULL AND c.account_id=w.account_id
  AND c.external_id=trim(w.document->>'external_campaign_id');

-- Funnel Flow V1: public installation key, URL steps and minimal event collection.
CREATE TABLE IF NOT EXISTS cadu_reports_site_tags (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    label VARCHAR(120) NOT NULL,
    allowed_host VARCHAR(253) NOT NULL,
    public_key VARCHAR(80) NOT NULL UNIQUE,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT cadu_reports_site_tags_id_scope_unique UNIQUE (id, organization_id, client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_site_tags_client_idx
    ON cadu_reports_site_tags (organization_id, client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_flow_steps (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    tag_id UUID NOT NULL,
    name VARCHAR(120) NOT NULL,
    path_prefix VARCHAR(500) NOT NULL,
    step_kind VARCHAR(24) NOT NULL DEFAULT 'page',
    campaign_id BIGINT,
    position INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_flow_step_kind CHECK (step_kind IN ('page', 'conversion')),
    CONSTRAINT cadu_reports_flow_step_tag_scope_fk
        FOREIGN KEY (tag_id, organization_id, client_id)
        REFERENCES cadu_reports_site_tags (id, organization_id, client_id),
    CONSTRAINT cadu_reports_flow_step_id_scope_unique UNIQUE (id, organization_id, client_id),
    CONSTRAINT cadu_reports_flow_step_campaign_scope_fk
        FOREIGN KEY (campaign_id, organization_id, client_id)
        REFERENCES cadu_reports_campaigns (id, organization_id, client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_steps_client_idx
    ON cadu_reports_flow_steps (organization_id, client_id, tag_id, position);
ALTER TABLE cadu_reports_flow_steps ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE cadu_reports_flow_steps ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS cadu_reports_flow_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    tag_id UUID NOT NULL,
    visitor_id UUID NOT NULL,
    session_id UUID NOT NULL,
    event_kind VARCHAR(24) NOT NULL,
    page_path VARCHAR(1000) NOT NULL,
    referrer_host VARCHAR(253),
    utm_source VARCHAR(160),
    utm_medium VARCHAR(160),
    utm_campaign VARCHAR(160),
    utm_id VARCHAR(160),
    click_id VARCHAR(160),
    step_id BIGINT,
    campaign_id BIGINT,
    attribution_method VARCHAR(24),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_flow_event_kind CHECK (event_kind IN ('page_view', 'heartbeat', 'conversion')),
    CONSTRAINT cadu_reports_flow_event_tag_scope_fk
        FOREIGN KEY (tag_id, organization_id, client_id)
        REFERENCES cadu_reports_site_tags (id, organization_id, client_id),
    CONSTRAINT cadu_reports_flow_event_step_scope_fk
        FOREIGN KEY (step_id, organization_id, client_id)
        REFERENCES cadu_reports_flow_steps (id, organization_id, client_id),
    CONSTRAINT cadu_reports_flow_event_campaign_scope_fk
        FOREIGN KEY (campaign_id, organization_id, client_id)
        REFERENCES cadu_reports_campaigns (id, organization_id, client_id),
    CONSTRAINT cadu_reports_flow_attribution_method_check
        CHECK (attribution_method IS NULL OR attribution_method IN ('utm_id', 'utm_campaign', 'step'))
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_client_time_idx
    ON cadu_reports_flow_events (organization_id, client_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_tag_time_idx
    ON cadu_reports_flow_events (tag_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_time_idx
    ON cadu_reports_flow_events (occurred_at);
ALTER TABLE cadu_reports_flow_events ADD COLUMN IF NOT EXISTS utm_id VARCHAR(160);
ALTER TABLE cadu_reports_flow_events ADD COLUMN IF NOT EXISTS campaign_id BIGINT;
ALTER TABLE cadu_reports_flow_events ADD COLUMN IF NOT EXISTS attribution_method VARCHAR(24);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='cadu_reports_flow_event_campaign_scope_fk') THEN
        ALTER TABLE cadu_reports_flow_events ADD CONSTRAINT cadu_reports_flow_event_campaign_scope_fk
            FOREIGN KEY (campaign_id, organization_id, client_id)
            REFERENCES cadu_reports_campaigns (id, organization_id, client_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='cadu_reports_flow_attribution_method_check') THEN
        ALTER TABLE cadu_reports_flow_events ADD CONSTRAINT cadu_reports_flow_attribution_method_check
            CHECK (attribution_method IS NULL OR attribution_method IN ('utm_id', 'utm_campaign', 'step'));
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_campaign_time_idx
    ON cadu_reports_flow_events (organization_id, client_id, campaign_id, occurred_at DESC)
    WHERE campaign_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cadu_reports_external_conversions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    source_kind VARCHAR(32) NOT NULL DEFAULT 'conversion_webhook',
    external_event_id VARCHAR(160) NOT NULL,
    visitor_id UUID,
    campaign_id BIGINT,
    attribution_method VARCHAR(24),
    conversion_kind VARCHAR(32) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    value_micros BIGINT CHECK (value_micros IS NULL OR value_micros >= 0),
    currency CHAR(3),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_external_conversion_unique
        UNIQUE (organization_id, client_id, source_kind, external_event_id),
    CONSTRAINT cadu_reports_external_conversion_campaign_scope_fk
        FOREIGN KEY (campaign_id, organization_id, client_id)
        REFERENCES cadu_reports_campaigns (id, organization_id, client_id),
    CONSTRAINT cadu_reports_external_conversion_kind_check
        CHECK (conversion_kind IN ('lead', 'qualified_lead', 'sale')),
    CONSTRAINT cadu_reports_external_conversion_attribution_check
        CHECK (attribution_method IS NULL OR attribution_method IN ('explicit_campaign', 'visitor'))
);
CREATE INDEX IF NOT EXISTS cadu_reports_external_conversions_client_time_idx
    ON cadu_reports_external_conversions (organization_id, client_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_external_conversions_time_idx
    ON cadu_reports_external_conversions (occurred_at);
