-- Reports: Google Ads engine v2. Additive; the v1 campaign metrics tables stay untouched.
-- Every table is scoped by client_id and keyed by the advertiser account row plus Google external IDs,
-- so detail datasets never depend on a campaign row existing first.

-- Ad groups, daily.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_ad_group_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    ad_group_external_id VARCHAR(20) NOT NULL,
    ad_group_name VARCHAR(240) NOT NULL,
    ad_group_status VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN',
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, ad_group_external_id, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_ad_group_daily_client_idx
    ON cadu_reports_gads_ad_group_daily (client_id, metric_date DESC);

-- Positive keywords, daily, with the Quality Score observed on that run.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_keyword_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    ad_group_external_id VARCHAR(20) NOT NULL,
    ad_group_name VARCHAR(240) NOT NULL,
    criterion_external_id VARCHAR(20) NOT NULL,
    keyword_text VARCHAR(240) NOT NULL,
    match_type VARCHAR(16) NOT NULL,
    keyword_status VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN',
    quality_score SMALLINT CHECK (quality_score BETWEEN 1 AND 10),
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, ad_group_external_id, criterion_external_id, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_keyword_daily_client_idx
    ON cadu_reports_gads_keyword_daily (client_id, metric_date DESC);

-- Search terms that actually triggered ads, daily. The term hash keeps the key short and indexable.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_search_term_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    ad_group_external_id VARCHAR(20) NOT NULL,
    ad_group_name VARCHAR(240) NOT NULL,
    search_term VARCHAR(800) NOT NULL,
    term_hash CHAR(32) NOT NULL,
    term_status VARCHAR(24) NOT NULL DEFAULT 'NONE',
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, ad_group_external_id, term_hash, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_search_term_daily_client_idx
    ON cadu_reports_gads_search_term_daily (client_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_search_term_daily_term_idx
    ON cadu_reports_gads_search_term_daily (account_id, term_hash);

-- Campaign performance by device, daily.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_device_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    device VARCHAR(24) NOT NULL,
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, campaign_external_id, device, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_device_daily_client_idx
    ON cadu_reports_gads_device_daily (client_id, metric_date DESC);

-- Campaign configuration snapshot: budget, bidding strategy and serving state as last seen.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_campaign_settings (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN',
    serving_status VARCHAR(40),
    channel_type VARCHAR(64),
    bidding_strategy_type VARCHAR(64),
    budget_micros BIGINT CHECK (budget_micros >= 0),
    budget_shared BOOLEAN,
    snapshot_id VARCHAR(200) NOT NULL DEFAULT '',
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    PRIMARY KEY (account_id, campaign_external_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_campaign_settings_client_idx
    ON cadu_reports_gads_campaign_settings (client_id, account_id);

-- Negative keywords at campaign, ad group and shared-list level. Snapshot semantics: a full
-- snapshot that no longer contains a row stamps removed_at, so the history of changes is kept.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_negative_keywords (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    level VARCHAR(12) NOT NULL CHECK (level IN ('campaign', 'ad_group', 'shared_list')),
    fingerprint CHAR(40) NOT NULL,
    campaign_external_id VARCHAR(20),
    campaign_name VARCHAR(240),
    ad_group_external_id VARCHAR(20),
    ad_group_name VARCHAR(240),
    shared_set_external_id VARCHAR(20),
    shared_set_name VARCHAR(240),
    attached_campaign_ids TEXT[] NOT NULL DEFAULT '{}',
    keyword_text VARCHAR(240) NOT NULL,
    match_type VARCHAR(16) NOT NULL,
    snapshot_id VARCHAR(200) NOT NULL,
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    CONSTRAINT cadu_reports_gads_negative_unique UNIQUE (account_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_negative_client_idx
    ON cadu_reports_gads_negative_keywords (client_id, account_id) WHERE removed_at IS NULL;

-- Landing pages the ads send traffic to, daily. page_host/page_path are the join keys to Super Tag pages
-- (allowed_host + page_path); the full final URL is kept so campaign UTMs stay auditable.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_landing_page_daily (
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    final_url VARCHAR(2000) NOT NULL,
    url_hash CHAR(32) NOT NULL,
    page_host VARCHAR(253) NOT NULL,
    page_path VARCHAR(500) NOT NULL,
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    cost_micros BIGINT NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    conversions NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    conversion_value_micros BIGINT NOT NULL DEFAULT 0 CHECK (conversion_value_micros >= 0),
    last_run_id UUID REFERENCES cadu_reports_source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, campaign_external_id, url_hash, metric_date)
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_landing_page_daily_page_idx
    ON cadu_reports_gads_landing_page_daily (client_id, page_host, page_path, metric_date DESC);
