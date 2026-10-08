-- Planner portais: popularidade pública (ranking Tranco), porte estimado e demografia estimada por categoria.
-- Tudo estimado fica marcado como tal na ficha. Aditiva e idempotente.
ALTER TABLE cadu_planner_portals
    ADD COLUMN IF NOT EXISTS popularity_rank INTEGER CHECK (popularity_rank IS NULL OR popularity_rank > 0),
    ADD COLUMN IF NOT EXISTS popularity_source VARCHAR(40),
    ADD COLUMN IF NOT EXISTS popularity_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS traffic_tier VARCHAR(20),
    ADD COLUMN IF NOT EXISTS demographics JSONB,
    ADD COLUMN IF NOT EXISTS estimates_updated_at TIMESTAMPTZ;

DO $$ BEGIN
    ALTER TABLE cadu_planner_portals
        ADD CONSTRAINT cadu_planner_portals_traffic_tier_check
        CHECK (traffic_tier IS NULL OR traffic_tier IN ('grande', 'medio', 'pequeno', 'nicho'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
