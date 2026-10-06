-- Planner portais: escopo (premium nacional / regional), UF, métricas com fonte
-- e resultado do crawler de ads.txt e sinais programáticos. Aditiva e idempotente.
ALTER TABLE cadu_planner_portals
    ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'regional',
    ADD COLUMN IF NOT EXISTS uf CHAR(2),
    ADD COLUMN IF NOT EXISTS site_title VARCHAR(180),
    ADD COLUMN IF NOT EXISTS favicon_url TEXT,
    ADD COLUMN IF NOT EXISTS monthly_visits BIGINT CHECK (monthly_visits IS NULL OR monthly_visits >= 0),
    ADD COLUMN IF NOT EXISTS avg_time_seconds INTEGER CHECK (avg_time_seconds IS NULL OR avg_time_seconds >= 0),
    ADD COLUMN IF NOT EXISTS metrics_period VARCHAR(80),
    ADD COLUMN IF NOT EXISTS metrics_source_url TEXT,
    ADD COLUMN IF NOT EXISTS metrics_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ads_txt_status VARCHAR(30),
    ADD COLUMN IF NOT EXISTS ads_txt_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ads_txt_records INTEGER,
    ADD COLUMN IF NOT EXISTS ads_txt_sellers JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS programmatic_status VARCHAR(30),
    ADD COLUMN IF NOT EXISTS programmatic_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS programmatic_checked_at TIMESTAMPTZ;

DO $$ BEGIN
    ALTER TABLE cadu_planner_portals
        ADD CONSTRAINT cadu_planner_portals_scope_check CHECK (scope IN ('nacional_premium', 'regional'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE cadu_planner_portals
        ADD CONSTRAINT cadu_planner_portals_metrics_source_check
        CHECK ((monthly_visits IS NULL AND avg_time_seconds IS NULL)
               OR (metrics_source_url IS NOT NULL AND metrics_checked_at IS NOT NULL));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS cadu_planner_portals_scope_uf_idx
    ON cadu_planner_portals (scope, uf, name) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS cadu_planner_portals_programmatic_idx
    ON cadu_planner_portals (programmatic_status, ads_txt_status) WHERE active = TRUE;
