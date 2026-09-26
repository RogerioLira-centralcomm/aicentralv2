-- Keep canonical facts at their source grain and project campaign totals from
-- the newest observation for each source dimension.
ALTER TABLE cadu_reports_import_observations
  ADD COLUMN IF NOT EXISTS dimensions JSONB NOT NULL DEFAULT '{}'::jsonb;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
      WHERE conname='cadu_reports_import_observations_dimensions_object_check') THEN
    ALTER TABLE cadu_reports_import_observations
      ADD CONSTRAINT cadu_reports_import_observations_dimensions_object_check
      CHECK (jsonb_typeof(dimensions)='object');
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS cadu_reports_import_observations_dimension_lookup_idx
  ON cadu_reports_import_observations
  (organization_id,client_id,campaign_id,metric_date,metric_key,dimensions,id DESC);

ALTER TABLE cadu_reports_import_projection_decisions
  ADD COLUMN IF NOT EXISTS dimensions JSONB NOT NULL DEFAULT '{}'::jsonb;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
      WHERE conname='cadu_reports_import_projection_decisions_dimensions_object_check') THEN
    ALTER TABLE cadu_reports_import_projection_decisions
      ADD CONSTRAINT cadu_reports_import_projection_decisions_dimensions_object_check
      CHECK (jsonb_typeof(dimensions)='object');
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS cadu_reports_import_projection_decision_dimension_idx
  ON cadu_reports_import_projection_decisions
  (organization_id,client_id,campaign_id,metric_date,metric_key,dimensions,id DESC);

UPDATE cadu_reports_import_observations o
SET dimensions=CASE
    WHEN jsonb_typeof(r.parsed->'grain_dimensions')='object'
         AND r.parsed->'grain_dimensions'<>'{}'::jsonb
      THEN r.parsed->'grain_dimensions'
    WHEN COALESCE(r.raw->>'Anúncios','')<>''
      THEN jsonb_build_object('anuncios',jsonb_build_object(
          'label','Anúncios','value',r.raw->>'Anúncios'))
    ELSE '{}'::jsonb END
FROM cadu_reports_import_rows r
WHERE r.id=o.import_row_id AND r.organization_id=o.organization_id
  AND r.client_id=o.client_id AND o.dimensions='{}'::jsonb
  AND (r.parsed ? 'grain_dimensions' OR COALESCE(r.raw->>'Anúncios','')<>'');

UPDATE cadu_reports_import_projection_decisions d
SET dimensions=o.dimensions
FROM cadu_reports_import_observations o
WHERE o.id=d.selected_observation_id AND o.organization_id=d.organization_id
  AND o.client_id=d.client_id AND o.campaign_id=d.campaign_id
  AND o.metric_date=d.metric_date AND o.metric_key=d.metric_key
  AND d.dimensions='{}'::jsonb AND o.dimensions<>'{}'::jsonb;

CREATE OR REPLACE VIEW cadu_reports_import_metric_projection AS
WITH ranked_by_dimension AS (
    SELECT id,organization_id,client_id,campaign_id,metric_date,metric_key,
        value_numeric,currency,dimensions,
        ROW_NUMBER() OVER (PARTITION BY organization_id,client_id,campaign_id,
            metric_date,metric_key,dimensions ORDER BY id DESC) AS revision_rank
    FROM cadu_reports_import_observations
), revision_counts AS (
    SELECT organization_id,client_id,campaign_id,metric_date,metric_key,dimensions,
        COUNT(DISTINCT (value_numeric,COALESCE(currency,'')))::bigint AS revision_count
    FROM cadu_reports_import_observations
    GROUP BY organization_id,client_id,campaign_id,metric_date,metric_key,dimensions
), latest_by_dimension AS (
    SELECT r.id,r.organization_id,r.client_id,r.campaign_id,r.metric_date,r.metric_key,
        r.value_numeric,r.currency,r.dimensions,c.revision_count
    FROM ranked_by_dimension r JOIN revision_counts c USING
        (organization_id,client_id,campaign_id,metric_date,metric_key,dimensions)
    WHERE r.revision_rank=1
), resolved_by_dimension AS (
    SELECT latest.organization_id,latest.client_id,latest.campaign_id,latest.metric_date,
        latest.metric_key,latest.dimensions,latest.value_numeric,latest.currency,
        latest.revision_count,latest.id AS latest_observation_id,
        CASE WHEN latest.revision_count=1 THEN latest.value_numeric
             WHEN COALESCE(decision.seen_observation_id,0)>=latest.id THEN selected.value_numeric
             ELSE NULL END AS resolved_value,
        CASE WHEN latest.revision_count=1 THEN latest.currency
             WHEN COALESCE(decision.seen_observation_id,0)>=latest.id THEN selected.currency
             ELSE NULL END AS resolved_currency,
        (latest.revision_count>1 AND COALESCE(decision.seen_observation_id,0)<latest.id) AS unresolved
    FROM latest_by_dimension latest
    LEFT JOIN LATERAL (
        SELECT selected_observation_id,seen_observation_id
        FROM cadu_reports_import_projection_decisions
        WHERE organization_id=latest.organization_id AND client_id=latest.client_id
          AND campaign_id=latest.campaign_id AND metric_date=latest.metric_date
          AND metric_key=latest.metric_key AND dimensions=latest.dimensions
        ORDER BY id DESC LIMIT 1
    ) decision ON TRUE
    LEFT JOIN cadu_reports_import_observations selected
      ON selected.id=decision.selected_observation_id
      AND selected.organization_id=latest.organization_id AND selected.client_id=latest.client_id
      AND selected.campaign_id=latest.campaign_id AND selected.metric_date=latest.metric_date
      AND selected.metric_key=latest.metric_key AND selected.dimensions=latest.dimensions
), grouped AS (
    SELECT organization_id,client_id,campaign_id,metric_date,metric_key,
        CASE WHEN BOOL_OR(unresolved) THEN NULL ELSE SUM(resolved_value) END AS value_numeric,
        CASE WHEN BOOL_OR(unresolved) OR COUNT(DISTINCT resolved_currency)>1 THEN NULL
             ELSE MAX(resolved_currency) END AS currency,
        COUNT(*)::bigint AS observation_count,
        MAX(latest_observation_id) AS latest_observation_id,
        MAX(revision_count)::bigint AS version_count
    FROM resolved_by_dimension
    GROUP BY organization_id,client_id,campaign_id,metric_date,metric_key
)
SELECT g.organization_id,g.client_id,g.campaign_id,g.metric_date,g.metric_key,
    g.value_numeric,g.currency,
    g.observation_count,g.version_count
FROM grouped g
