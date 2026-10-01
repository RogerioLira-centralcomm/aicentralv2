-- Versões do plano: congelam o desenho para aprovação sem ligar a medição.
-- Ficam fora de cadu_reports_flow_versions, que a coleta usa para fixar sessões.
CREATE TABLE IF NOT EXISTS cadu_reports_flow_plan_versions (
    flow_id UUID NOT NULL REFERENCES cadu_reports_flow_registry(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    revision BIGINT NOT NULL,
    name VARCHAR(120) NOT NULL,
    config JSONB NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (flow_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_cadu_reports_flow_plan_versions_client
    ON cadu_reports_flow_plan_versions (client_id, flow_id, revision DESC);
