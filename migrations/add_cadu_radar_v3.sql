-- Radar: sinais salvos na tela de resultados (aditivo, idempotente; depende de add_cadu_radar.sql).
ALTER TABLE cadu_radar_signals ADD COLUMN IF NOT EXISTS saved_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS cadu_radar_signals_saved_idx ON cadu_radar_signals (client_id, saved_at DESC) WHERE saved_at IS NOT NULL;
