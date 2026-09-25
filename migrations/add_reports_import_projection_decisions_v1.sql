-- Explicit, immutable decisions for conflicting daily export values.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='cadu_reports_import_observations_scope_unique') THEN
        ALTER TABLE cadu_reports_import_observations ADD CONSTRAINT
            cadu_reports_import_observations_scope_unique
            UNIQUE (id,organization_id,client_id,campaign_id,metric_date,metric_key);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS cadu_reports_import_projection_decisions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    campaign_id BIGINT NOT NULL,
    metric_date DATE NOT NULL,
    metric_key VARCHAR(40) NOT NULL,
    selected_observation_id BIGINT NOT NULL,
    seen_observation_id BIGINT NOT NULL,
    note VARCHAR(1000) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_projection_decisions_selected_scope_fk
        FOREIGN KEY (selected_observation_id,organization_id,client_id,campaign_id,metric_date,metric_key)
        REFERENCES cadu_reports_import_observations
            (id,organization_id,client_id,campaign_id,metric_date,metric_key),
    CONSTRAINT cadu_reports_import_projection_decisions_campaign_scope_fk
        FOREIGN KEY (campaign_id,organization_id,client_id)
        REFERENCES cadu_reports_campaigns (id,organization_id,client_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_import_projection_decisions_key_idx
    ON cadu_reports_import_projection_decisions
    (organization_id,client_id,campaign_id,metric_date,metric_key,id DESC);

CREATE OR REPLACE VIEW cadu_reports_import_metric_projection AS
WITH grouped AS (
    SELECT organization_id,client_id,campaign_id,metric_date,metric_key,
        MAX(value_numeric) AS unanimous_value,
        MAX(currency) AS unanimous_currency,
        COUNT(*)::bigint AS observation_count,
        COUNT(DISTINCT (value_numeric,COALESCE(currency,'')))::bigint AS version_count,
        MAX(id) AS latest_observation_id
    FROM cadu_reports_import_observations
    GROUP BY organization_id,client_id,campaign_id,metric_date,metric_key
), latest_decision AS (
    SELECT DISTINCT ON (organization_id,client_id,campaign_id,metric_date,metric_key)
        organization_id,client_id,campaign_id,metric_date,metric_key,
        selected_observation_id,seen_observation_id
    FROM cadu_reports_import_projection_decisions
    ORDER BY organization_id,client_id,campaign_id,metric_date,metric_key,id DESC
)
SELECT g.organization_id,g.client_id,g.campaign_id,g.metric_date,g.metric_key,
    CASE WHEN g.version_count=1 THEN g.unanimous_value
         WHEN d.seen_observation_id>=g.latest_observation_id THEN chosen.value_numeric
         ELSE NULL END AS value_numeric,
    CASE WHEN g.version_count=1 THEN g.unanimous_currency
         WHEN d.seen_observation_id>=g.latest_observation_id THEN chosen.currency
         ELSE NULL END AS currency,
    g.observation_count,g.version_count
FROM grouped g
LEFT JOIN latest_decision d ON d.organization_id=g.organization_id AND d.client_id=g.client_id
    AND d.campaign_id=g.campaign_id AND d.metric_date=g.metric_date AND d.metric_key=g.metric_key
LEFT JOIN cadu_reports_import_observations chosen
    ON chosen.id=d.selected_observation_id AND chosen.organization_id=g.organization_id
    AND chosen.client_id=g.client_id AND chosen.campaign_id=g.campaign_id
    AND chosen.metric_date=g.metric_date AND chosen.metric_key=g.metric_key;
