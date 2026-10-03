-- Reports: Google Ads engine 2.2 (anúncios, desempenho por ativo, parcela de impressões, conversões por ação,
-- componentes do Índice de Qualidade). Additive and idempotent; engine 2.1 data is untouched.

-- Ads as last seen (snapshot): a snapshot that no longer contains an ad stamps removed_at, so changes stay in the history.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_ads (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    ad_external_id VARCHAR(20) NOT NULL,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    ad_group_external_id VARCHAR(20) NOT NULL,
    ad_group_name VARCHAR(240) NOT NULL,
    ad_type VARCHAR(48) NOT NULL DEFAULT 'UNKNOWN',
    status VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN',
    ad_strength VARCHAR(24),
    approval_status VARCHAR(32),
    final_url VARCHAR(2000),
    headlines JSONB NOT NULL DEFAULT '[]'::jsonb,
    descriptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    path1 VARCHAR(30),
    path2 VARCHAR(30),
    snapshot_id VARCHAR(200) NOT NULL DEFAULT '',
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    PRIMARY KEY (account_id, ad_external_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_ads_group_idx
    ON cadu_reports_gads_ads (client_id, account_id, ad_group_external_id) WHERE removed_at IS NULL;

CREATE TABLE IF NOT EXISTS cadu_reports_gads_ad_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    ad_group_external_id VARCHAR(20) NOT NULL,
    ad_external_id VARCHAR(20) NOT NULL,
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, ad_external_id, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_ad_daily_client_idx
    ON cadu_reports_gads_ad_daily (client_id, metric_date DESC);

-- Google's rating of each headline/description of a responsive search ad (snapshot).
CREATE TABLE IF NOT EXISTS cadu_reports_gads_asset_performance (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    ad_external_id VARCHAR(20) NOT NULL,
    asset_external_id VARCHAR(20) NOT NULL,
    field_type VARCHAR(24) NOT NULL,
    campaign_external_id VARCHAR(20) NOT NULL,
    ad_group_external_id VARCHAR(20) NOT NULL,
    asset_text VARCHAR(400) NOT NULL DEFAULT '',
    performance_label VARCHAR(24),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    snapshot_id VARCHAR(200) NOT NULL DEFAULT '',
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    PRIMARY KEY (account_id, ad_external_id, asset_external_id, field_type)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_asset_performance_group_idx
    ON cadu_reports_gads_asset_performance (client_id, account_id, ad_group_external_id) WHERE removed_at IS NULL;

-- Search impression share per campaign and day (ratios 0..1; Google reports no value when it is below its threshold).
CREATE TABLE IF NOT EXISTS cadu_reports_gads_impression_share_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    metric_date DATE NOT NULL,
    search_impression_share NUMERIC(7,6) CHECK (search_impression_share BETWEEN 0 AND 1),
    budget_lost NUMERIC(7,6) CHECK (budget_lost BETWEEN 0 AND 1),
    rank_lost NUMERIC(7,6) CHECK (rank_lost BETWEEN 0 AND 1),
    top_impression_share NUMERIC(7,6) CHECK (top_impression_share BETWEEN 0 AND 1),
    absolute_top_impression_share NUMERIC(7,6) CHECK (absolute_top_impression_share BETWEEN 0 AND 1),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, campaign_external_id, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_impression_share_daily_client_idx
    ON cadu_reports_gads_impression_share_daily (client_id, metric_date DESC);

-- Conversions by conversion action (lead, purchase, phone call...) per campaign and day.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_conversion_action_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    action_name VARCHAR(240) NOT NULL,
    action_hash CHAR(32) NOT NULL,
    metric_date DATE NOT NULL,
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, campaign_external_id, action_hash, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_conversion_action_daily_client_idx
    ON cadu_reports_gads_conversion_action_daily (client_id, metric_date DESC);

-- Quality Score components and the keyword's bid, observed on each run.
ALTER TABLE cadu_reports_gads_keyword_daily ADD COLUMN IF NOT EXISTS expected_ctr VARCHAR(24);
ALTER TABLE cadu_reports_gads_keyword_daily ADD COLUMN IF NOT EXISTS ad_relevance VARCHAR(24);
ALTER TABLE cadu_reports_gads_keyword_daily ADD COLUMN IF NOT EXISTS landing_page_experience VARCHAR(24);
ALTER TABLE cadu_reports_gads_keyword_daily ADD COLUMN IF NOT EXISTS cpc_bid_micros BIGINT CHECK (cpc_bid_micros >= 0);
