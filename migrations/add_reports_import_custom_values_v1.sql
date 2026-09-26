-- Flexible, channel-aware key/value metrics from multichannel report imports.
ALTER TABLE cadu_reports_import_range_metrics
  DROP CONSTRAINT IF EXISTS cadu_reports_import_range_metrics_metric_key_check;
ALTER TABLE cadu_reports_import_range_metrics
  ALTER COLUMN metric_key TYPE VARCHAR(100);
ALTER TABLE cadu_reports_import_range_metrics
  ADD COLUMN IF NOT EXISTS metric_label VARCHAR(160);
ALTER TABLE cadu_reports_import_range_metrics
  ADD COLUMN IF NOT EXISTS channel VARCHAR(64) NOT NULL DEFAULT 'paid_media';
ALTER TABLE cadu_reports_import_range_metrics
  DROP CONSTRAINT IF EXISTS cadu_reports_import_range_metrics_unit_check;
ALTER TABLE cadu_reports_import_range_metrics
  DROP CONSTRAINT IF EXISTS cadu_reports_import_range_metrics_currency_check;
ALTER TABLE cadu_reports_import_range_metrics
  ALTER COLUMN unit TYPE VARCHAR(32);
ALTER TABLE cadu_reports_import_range_metrics
  DROP CONSTRAINT IF EXISTS cadu_reports_import_range_metrics_value_numeric_check;
ALTER TABLE cadu_reports_import_range_metrics
  ADD CONSTRAINT cadu_reports_import_range_metrics_currency_check
  CHECK ((unit = 'currency' AND currency IS NOT NULL) OR
         (unit <> 'currency' AND currency IS NULL));

CREATE TABLE IF NOT EXISTS cadu_reports_import_custom_values (
    id BIGSERIAL PRIMARY KEY,
    import_row_id BIGINT NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    campaign_id BIGINT NOT NULL,
    metric_date DATE NOT NULL,
    channel VARCHAR(64) NOT NULL DEFAULT 'paid_media',
    metric_key VARCHAR(100) NOT NULL,
    metric_label VARCHAR(160) NOT NULL,
    value_numeric NUMERIC(24,6) NOT NULL,
    unit VARCHAR(32) NOT NULL DEFAULT 'count',
    currency CHAR(3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_import_custom_values_row_fk
      FOREIGN KEY (import_row_id,organization_id,client_id)
      REFERENCES cadu_reports_import_rows (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_custom_values_campaign_fk
      FOREIGN KEY (campaign_id,organization_id,client_id)
      REFERENCES cadu_reports_campaigns (id,organization_id,client_id),
    CONSTRAINT cadu_reports_import_custom_values_currency_check
      CHECK ((unit='currency' AND currency IS NOT NULL) OR (unit<>'currency' AND currency IS NULL)),
    CONSTRAINT cadu_reports_import_custom_values_row_key_unique
      UNIQUE (import_row_id,channel,metric_key)
);
ALTER TABLE cadu_reports_import_custom_values
  DROP CONSTRAINT IF EXISTS cadu_reports_import_custom_values_value_numeric_check;
CREATE INDEX IF NOT EXISTS cadu_reports_import_custom_values_lookup_idx
  ON cadu_reports_import_custom_values
  (organization_id,client_id,campaign_id,channel,metric_key,metric_date DESC);
