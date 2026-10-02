-- Reports · Google Ads · Ações: changes approved in the Reports and applied by the "Ações" script installed in the account.
-- Idempotent. The read script (engine v2) never writes; this script only runs operations from its own closed list.

-- Limits chosen when the Ações script was generated (the same values are written into the pasted code).
ALTER TABLE cadu_reports_ingest_keys ADD COLUMN IF NOT EXISTS limits JSONB NOT NULL DEFAULT '{}'::jsonb;

-- One row per change to apply in one Google Ads account.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_actions (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL REFERENCES cadu_reports_accounts(id) ON DELETE CASCADE,
    account_external_id VARCHAR(10) NOT NULL,
    op VARCHAR(32) NOT NULL CHECK (op IN ('campaign.pause', 'campaign.enable', 'ad_group.pause', 'ad_group.enable',
        'keyword.pause', 'keyword.enable', 'keyword.add', 'keyword.set_cpc', 'negative.add', 'negative.remove', 'campaign.set_budget')),
    target JSONB NOT NULL DEFAULT '{}'::jsonb,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    expect JSONB NOT NULL DEFAULT '{}'::jsonb,
    label VARCHAR(300) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'approved' CHECK (status IN ('approved', 'sent', 'applied', 'failed', 'skipped',
        'expired', 'cancelled')),
    origin VARCHAR(80) NOT NULL DEFAULT 'manual',
    recommendation_id VARCHAR(200),
    undo_of UUID REFERENCES cadu_reports_gads_actions(id) ON DELETE SET NULL,
    created_by BIGINT NOT NULL,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    finished_at TIMESTAMPTZ,
    result JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_actions_queue_idx
    ON cadu_reports_gads_actions (account_external_id, created_at) WHERE status IN ('approved', 'sent');
CREATE INDEX IF NOT EXISTS cadu_reports_gads_actions_client_idx
    ON cadu_reports_gads_actions (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_gads_actions_recommendation_idx
    ON cadu_reports_gads_actions (client_id, recommendation_id) WHERE recommendation_id IS NOT NULL;

-- Last contact of each Ações script, per account: drives the "próxima execução" countdown on screen.
CREATE TABLE IF NOT EXISTS cadu_reports_gads_action_agents (
    client_id BIGINT NOT NULL,
    account_external_id VARCHAR(10) NOT NULL,
    key_id UUID NOT NULL,
    engine_version VARCHAR(20),
    allow_writes BOOLEAN NOT NULL DEFAULT TRUE,
    preview BOOLEAN NOT NULL DEFAULT FALSE,
    limits JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_poll_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    previous_poll_at TIMESTAMPTZ,
    PRIMARY KEY (client_id, account_external_id)
);
