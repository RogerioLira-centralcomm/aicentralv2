-- Registro dos envios de teste de conversão (limite diário por fluxo). A análise por HTML não grava nada.
CREATE TABLE IF NOT EXISTS cadu_reports_flow_probe_runs (
    id BIGSERIAL PRIMARY KEY,
    flow_id UUID NOT NULL REFERENCES cadu_reports_flow_registry(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('submit')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_reports_flow_probe_runs_flow_day
    ON cadu_reports_flow_probe_runs (flow_id, created_at DESC);
