-- Modelos de fluxo do time: um plano limpo (sem endereços, prazos, verba ou aprovações)
-- que outros fluxos do mesmo cliente usam como ponto de partida.
CREATE TABLE IF NOT EXISTS cadu_reports_flow_templates (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sector VARCHAR(40) NOT NULL DEFAULT '',
    config JSONB NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_reports_flow_templates_client
    ON cadu_reports_flow_templates (client_id, created_at DESC);
