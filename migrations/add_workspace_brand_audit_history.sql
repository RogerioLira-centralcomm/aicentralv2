-- Histórico consultável de auditorias de marca. O pacote em cx_clients continua
-- sendo o estado atual; esta tabela mantém a trilha de cada execução.
CREATE TABLE IF NOT EXISTS cadu_workspace_brand_audit_runs (
    job_id VARCHAR(64) PRIMARY KEY,
    client_id BIGINT NOT NULL,
    brand_id BIGINT NOT NULL,
    analysis_mode VARCHAR(20) NOT NULL DEFAULT 'complete',
    status VARCHAR(24) NOT NULL DEFAULT 'queued',
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    collected_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    costs JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviews JSONB NOT NULL DEFAULT '[]'::jsonb,
    human_effort JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_runs_brand_recent
    ON cadu_workspace_brand_audit_runs (client_id, brand_id, created_at DESC);
