-- Fonte e data das métricas públicas de cada canal, e campos editoriais próprios da ficha (aditivo, idempotente).
ALTER TABLE cadu_canais ADD COLUMN IF NOT EXISTS fontes_metricas JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE cadu_canais ADD COLUMN IF NOT EXISTS metricas_atualizadas_em TIMESTAMPTZ;
ALTER TABLE cadu_canais ADD COLUMN IF NOT EXISTS perfil_audiencia TEXT;
ALTER TABLE cadu_canais ADD COLUMN IF NOT EXISTS melhor_uso TEXT;
