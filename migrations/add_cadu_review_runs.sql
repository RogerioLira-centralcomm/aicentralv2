-- Cadu Análise: uma linha por revisão (web, MCP ou API key).
-- Aditivo e idempotente. Registrado em ORDER.txt. Usado por aicentralv2/cadu_review/repository.py,
-- que não falha se a tabela ainda não existir.
-- Não guarda o arquivo nem o conteúdo das linhas do plano: só o resumo, o status de cada
-- critério e o consumo do TypeSafe. v1 não cobra (tokens_cobrados = 0).
CREATE TABLE IF NOT EXISTS cadu_review_runs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kind VARCHAR(32) NOT NULL,                 -- media_plan
    channel VARCHAR(16) NOT NULL,              -- web | mcp | api
    client_id INTEGER NOT NULL,
    user_id INTEGER,
    api_key_id TEXT,
    file_type VARCHAR(8),
    file_sha256 CHAR(64),
    line_count INTEGER,
    score SMALLINT,
    verdict VARCHAR(32),
    partial BOOLEAN NOT NULL DEFAULT FALSE,
    statuses JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {criterio: ok|atencao|erro|na}
    typesafe_model TEXT,
    typesafe_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    tokens_estimados INTEGER NOT NULL DEFAULT 0,
    tokens_cobrados INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL,               -- succeeded | failed
    error_code VARCHAR(64),
    duration_ms INTEGER,
    prompt_version VARCHAR(48)
);
CREATE INDEX IF NOT EXISTS idx_cadu_review_runs_client_created ON cadu_review_runs (client_id, created_at DESC);

-- Reverso (manual):
-- DROP TABLE IF EXISTS cadu_review_runs;
