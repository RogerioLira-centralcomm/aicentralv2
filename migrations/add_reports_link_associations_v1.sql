-- Confirmed Link Tester associations. Historical runs remain unchanged until a user saves a decision.
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS report_workspace_id BIGINT;
ALTER TABLE cadu_planner_link_test_runs ADD COLUMN IF NOT EXISTS association_updated_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS cadu_reports_link_association_history (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_planner_link_test_runs(id),
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    previous_account_id BIGINT,
    previous_campaign_id BIGINT,
    previous_report_id BIGINT,
    account_id BIGINT,
    campaign_id BIGINT,
    report_id BIGINT,
    action VARCHAR(16) NOT NULL CHECK (
        (action='associate' AND campaign_id IS NOT NULL AND account_id IS NOT NULL)
        OR (action='clear' AND campaign_id IS NULL AND account_id IS NULL AND report_id IS NULL)
    ),
    decided_by BIGINT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_reports_link_association_history_run_idx
    ON cadu_reports_link_association_history (run_id, decided_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_link_association_history_client_idx
    ON cadu_reports_link_association_history (organization_id, client_id, decided_at DESC);
