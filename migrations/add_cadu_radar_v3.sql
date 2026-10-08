-- Radar: sinais salvos na tela de resultados (aditivo, idempotente; depende de add_cadu_radar.sql e add_cadu_planner_cobuild.sql).
ALTER TABLE cadu_radar_signals ADD COLUMN IF NOT EXISTS saved_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS cadu_radar_signals_saved_idx ON cadu_radar_signals (client_id, saved_at DESC) WHERE saved_at IS NOT NULL;

-- Plano que nasceu de uma notícia (sinal) do Radar; o plano guarda o vínculo, como já faz com a oportunidade.
ALTER TABLE cadu_planner_plans ADD COLUMN IF NOT EXISTS signal_id UUID;
CREATE INDEX IF NOT EXISTS cadu_planner_plans_signal_idx ON cadu_planner_plans (signal_id) WHERE signal_id IS NOT NULL;
