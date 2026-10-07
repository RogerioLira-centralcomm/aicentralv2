-- Central de alertas v2 (aditivo, idempotente; depende de add_reports_alerts_v1.sql).
-- Canal, tipo (ocorrência ou oportunidade), impacto principal, métricas/série/URLs/causas/recomendações para o painel,
-- estado "em investigação" e alertas por cliente sem site (Google Ads, Meta, relatórios).
ALTER TABLE cadu_reports_alerts ALTER COLUMN site_id DROP NOT NULL;

ALTER TABLE cadu_reports_alerts
    ADD COLUMN IF NOT EXISTS channel VARCHAR(12) NOT NULL DEFAULT 'site',
    ADD COLUMN IF NOT EXISTS kind VARCHAR(12) NOT NULL DEFAULT 'incident',
    ADD COLUMN IF NOT EXISTS impact JSONB,
    ADD COLUMN IF NOT EXISTS metrics JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS series JSONB,
    ADD COLUMN IF NOT EXISTS impacted_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS causes JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS investigating_at TIMESTAMPTZ;

ALTER TABLE cadu_reports_alerts DROP CONSTRAINT IF EXISTS cadu_reports_alerts_channel_check;
ALTER TABLE cadu_reports_alerts ADD CONSTRAINT cadu_reports_alerts_channel_check
    CHECK (channel IN ('site','journey','google_ads','meta','reports'));
ALTER TABLE cadu_reports_alerts DROP CONSTRAINT IF EXISTS cadu_reports_alerts_kind_check;
ALTER TABLE cadu_reports_alerts ADD CONSTRAINT cadu_reports_alerts_kind_check
    CHECK (kind IN ('incident','opportunity'));
ALTER TABLE cadu_reports_alerts DROP CONSTRAINT IF EXISTS cadu_reports_alerts_status_check;
ALTER TABLE cadu_reports_alerts ADD CONSTRAINT cadu_reports_alerts_status_check
    CHECK (status IN ('open','acknowledged','investigating','silenced','resolved'));

-- Listas do painel e dos detectores (Google Ads grava recomendações): sempre arrays, como a evidência.
ALTER TABLE cadu_reports_alerts DROP CONSTRAINT IF EXISTS cadu_reports_alerts_panel_arrays_check;
ALTER TABLE cadu_reports_alerts ADD CONSTRAINT cadu_reports_alerts_panel_arrays_check
    CHECK (jsonb_typeof(metrics)='array' AND jsonb_typeof(impacted_urls)='array' AND jsonb_typeof(causes)='array' AND jsonb_typeof(recommendations)='array');

-- Regras de insight já existentes são oportunidades, não incidentes.
UPDATE cadu_reports_alerts SET kind='opportunity'
 WHERE rule IN ('channel_entry_exit','device_conversion_low','campaign_weak_page') AND kind='incident';
UPDATE cadu_reports_alerts SET channel='journey' WHERE rule IN ('channel_entry_exit','campaign_weak_page') AND channel='site';

-- Um alerta vivo por assunto, inclusive os sem site (NULL não participaria de um índice único comum).
DROP INDEX IF EXISTS cadu_reports_alerts_live_unique;
CREATE UNIQUE INDEX IF NOT EXISTS cadu_reports_alerts_live_unique_v2
    ON cadu_reports_alerts (client_id, COALESCE(site_id::text, ''), rule, subject_key) WHERE status <> 'resolved';
CREATE INDEX IF NOT EXISTS cadu_reports_alerts_kind_idx
    ON cadu_reports_alerts (client_id, kind, status, last_seen_at DESC);
