-- Design System Ads: um sistema por marca em cx_brand_visual_systems,
-- cópia no brand_profile e DS da campanha no creative_brief.
-- Idempotente. Não cria tabela nova.

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS brand_profile JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE cx_campaigns
    ADD COLUMN IF NOT EXISTS creative_brief JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF to_regclass('public.cx_brand_visual_systems') IS NULL THEN
        RAISE EXCEPTION 'cx_brand_visual_systems ausente; rode a biblioteca de compose antes.';
    END IF;
END $$;

DELETE FROM cx_brand_visual_systems AS older
 USING cx_brand_visual_systems AS newer
 WHERE older.client_id IS NOT NULL
   AND older.client_id = newer.client_id
   AND older.id < newer.id
   AND COALESCE(older.tokens->>'framework', '') = 'design-system-ads'
   AND COALESCE(newer.tokens->>'framework', '') = 'design-system-ads';

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_brand_visual_systems_design_system_ads
    ON cx_brand_visual_systems (client_id)
    WHERE client_id IS NOT NULL
      AND tokens->>'framework' = 'design-system-ads'
      AND status <> 'archived';

CREATE INDEX IF NOT EXISTS idx_cx_brand_visual_systems_dsa_framework
    ON cx_brand_visual_systems ((tokens->>'framework'))
    WHERE tokens->>'framework' = 'design-system-ads';
