-- Planner portais: formatos de anúncio observados na home renderizada, editorias do menu e data da leitura.
-- Aditiva e idempotente.
ALTER TABLE cadu_planner_portals
    ADD COLUMN IF NOT EXISTS ad_formats JSONB,
    ADD COLUMN IF NOT EXISTS site_sections JSONB,
    ADD COLUMN IF NOT EXISTS signals_checked_at TIMESTAMPTZ;
