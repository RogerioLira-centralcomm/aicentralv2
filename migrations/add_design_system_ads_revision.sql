-- Revisão do Design System Ads como coluna gerada do JSON canônico.
-- Idempotente. Não muda o documento; só indexa o path já gravado.

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS design_system_ads_revision integer
    GENERATED ALWAYS AS (
        COALESCE(
            CASE
                WHEN brand_profile #>> '{design_system_ads,revision}' ~ '^[0-9]+$'
                THEN (brand_profile #>> '{design_system_ads,revision}')::int
                ELSE 0
            END,
            0
        )
    ) STORED;

ALTER TABLE cx_campaigns
    ADD COLUMN IF NOT EXISTS design_system_ads_revision integer
    GENERATED ALWAYS AS (
        COALESCE(
            CASE
                WHEN creative_brief #>> '{design_system_ads,revision}' ~ '^[0-9]+$'
                THEN (creative_brief #>> '{design_system_ads,revision}')::int
                ELSE 0
            END,
            0
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_cx_clients_dsa_revision
    ON cx_clients (id, design_system_ads_revision);

CREATE INDEX IF NOT EXISTS idx_cx_campaigns_dsa_revision
    ON cx_campaigns (id, design_system_ads_revision);
