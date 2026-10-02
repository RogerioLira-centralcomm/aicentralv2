-- Reports · Google Ads: history of campaign settings, bidding targets from Google, and campaign goals set by the operator.
-- Idempotent. Daily metric tables already keep every day forever; this adds what changes over time and what the
-- team wants each campaign to achieve.

-- Bidding targets read from Google Ads (tCPA / tROAS, standalone or inside maximize strategies).
ALTER TABLE cadu_reports_gads_campaign_settings ADD COLUMN IF NOT EXISTS target_cpa_micros BIGINT CHECK (target_cpa_micros IS NULL OR target_cpa_micros >= 0);
ALTER TABLE cadu_reports_gads_campaign_settings ADD COLUMN IF NOT EXISTS target_roas NUMERIC(10,4) CHECK (target_roas IS NULL OR target_roas >= 0);

-- One row each time status, bidding, budget or targets change, so budget and strategy history can be read later.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_campaign_settings_history (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    campaign_external_id VARCHAR(20) NOT NULL,
    campaign_name VARCHAR(240) NOT NULL,
    status VARCHAR(24),
    bidding_strategy_type VARCHAR(64),
    budget_micros BIGINT,
    target_cpa_micros BIGINT,
    target_roas NUMERIC(10,4),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_settings_history_idx
    ON cadu_reports_gads_campaign_settings_history (account_id, campaign_external_id, observed_at DESC);

-- What the team wants from each campaign: budget ceilings, flight dates and the objective with its target.
CREATE TABLE IF NOT EXISTS cadu_reports_campaign_goals (
    campaign_id BIGINT PRIMARY KEY REFERENCES cadu_reports_campaigns(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    objective VARCHAR(24) CHECK (objective IS NULL OR objective IN ('leads', 'sales', 'traffic', 'awareness', 'app')),
    monthly_budget_cap NUMERIC(14,2) CHECK (monthly_budget_cap IS NULL OR monthly_budget_cap >= 0),
    total_budget_cap NUMERIC(14,2) CHECK (total_budget_cap IS NULL OR total_budget_cap >= 0),
    flight_start DATE,
    flight_end DATE,
    target_cpa NUMERIC(14,2) CHECK (target_cpa IS NULL OR target_cpa >= 0),
    target_roas NUMERIC(10,4) CHECK (target_roas IS NULL OR target_roas >= 0),
    target_conversions_month INTEGER CHECK (target_conversions_month IS NULL OR target_conversions_month >= 0),
    notes VARCHAR(1000),
    updated_by BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (flight_end IS NULL OR flight_start IS NULL OR flight_end >= flight_start)
);
CREATE INDEX IF NOT EXISTS cadu_reports_campaign_goals_client_idx ON cadu_reports_campaign_goals (client_id);
