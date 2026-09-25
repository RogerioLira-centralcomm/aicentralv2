-- A conservative, read-only projection of immutable daily import observations.
-- Identical re-exports collapse to one value. Divergent values remain unresolved.
CREATE INDEX IF NOT EXISTS cadu_reports_import_observations_client_date_idx
    ON cadu_reports_import_observations
    (organization_id,client_id,metric_date DESC,campaign_id,metric_key);
CREATE OR REPLACE VIEW cadu_reports_import_metric_projection AS
SELECT organization_id,client_id,campaign_id,metric_date,metric_key,
    CASE WHEN COUNT(DISTINCT (value_numeric,COALESCE(currency,'')))=1
        THEN MAX(value_numeric) ELSE NULL END AS value_numeric,
    CASE WHEN COUNT(DISTINCT (value_numeric,COALESCE(currency,'')))=1
        THEN MAX(currency) ELSE NULL END AS currency,
    COUNT(*)::bigint AS observation_count,
    COUNT(DISTINCT (value_numeric,COALESCE(currency,'')))::bigint AS version_count
FROM cadu_reports_import_observations
GROUP BY organization_id,client_id,campaign_id,metric_date,metric_key;
