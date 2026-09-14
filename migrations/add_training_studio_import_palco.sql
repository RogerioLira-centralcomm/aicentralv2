-- Espelho dos patches em aicentralv2/training_studio/schema.py.
-- Guarda ingestão (YouTube/página), palco 16:9 e origem da sessão.

ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS palco_json JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS importacao_id BIGINT;
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS origem VARCHAR(20) NOT NULL DEFAULT 'oficial';

CREATE TABLE IF NOT EXISTS cx_treinamento_importacoes (
    id BIGSERIAL PRIMARY KEY,
    treinamento_id INTEGER NOT NULL REFERENCES cx_treinamentos(id) ON DELETE CASCADE,
    sessao_id BIGINT REFERENCES cx_treinamento_sessoes(id) ON DELETE SET NULL,
    kind VARCHAR(20) NOT NULL DEFAULT 'page',
    url TEXT NOT NULL,
    video_id VARCHAR(20),
    titulo VARCHAR(300),
    autor VARCHAR(200),
    duracao_s INTEGER NOT NULL DEFAULT 0,
    transcript TEXT NOT NULL DEFAULT '',
    transcript_source VARCHAR(40) NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    interpretacao TEXT NOT NULL DEFAULT '',
    briefing_html TEXT NOT NULL DEFAULT '',
    texto TEXT NOT NULL DEFAULT '',
    pipeline JSONB NOT NULL DEFAULT '[]'::jsonb,
    frames JSONB NOT NULL DEFAULT '[]'::jsonb,
    costs JSONB NOT NULL DEFAULT '[]'::jsonb,
    hero_url TEXT,
    embed_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ingested',
    applied_mode VARCHAR(20),
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_importacoes_treino
    ON cx_treinamento_importacoes (treinamento_id, created_at DESC);

ALTER TABLE cx_treinamento_fontes ADD COLUMN IF NOT EXISTS importacao_id BIGINT
    REFERENCES cx_treinamento_importacoes(id) ON DELETE SET NULL;
ALTER TABLE cx_treinamento_fontes ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'page';
ALTER TABLE cx_treinamento_fontes ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE cx_treinamento_imagens ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'gerada';
ALTER TABLE cx_treinamento_imagens ADD COLUMN IF NOT EXISTS importacao_id BIGINT
    REFERENCES cx_treinamento_importacoes(id) ON DELETE SET NULL;
ALTER TABLE cx_treinamento_imagens ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE cx_treinamento_sessoes DROP CONSTRAINT IF EXISTS cx_treinamento_sessoes_importacao_id_fkey;
ALTER TABLE cx_treinamento_sessoes
    ADD CONSTRAINT cx_treinamento_sessoes_importacao_id_fkey
    FOREIGN KEY (importacao_id) REFERENCES cx_treinamento_importacoes(id) ON DELETE SET NULL;

ALTER TABLE cx_treinamento_importacoes ADD COLUMN IF NOT EXISTS texto TEXT NOT NULL DEFAULT '';
ALTER TABLE cx_treinamento_importacoes ADD COLUMN IF NOT EXISTS costs JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE cx_treinamento_importacoes ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ingested';
ALTER TABLE cx_treinamento_importacoes ADD COLUMN IF NOT EXISTS applied_mode VARCHAR(20);
ALTER TABLE cx_treinamento_importacoes ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ;

ALTER TABLE cx_treinamento_agent_mensagens ADD COLUMN IF NOT EXISTS surface VARCHAR(20);
ALTER TABLE cx_treinamento_agent_mensagens ADD COLUMN IF NOT EXISTS selection TEXT NOT NULL DEFAULT '';
ALTER TABLE cx_treinamento_agent_mensagens ADD COLUMN IF NOT EXISTS importacao_id BIGINT
    REFERENCES cx_treinamento_importacoes(id) ON DELETE SET NULL;

ALTER TABLE cx_treinamento_ai_ledger DROP CONSTRAINT IF EXISTS cx_treinamento_ai_ledger_kind_check;
ALTER TABLE cx_treinamento_ai_ledger
    ADD CONSTRAINT cx_treinamento_ai_ledger_kind_check
    CHECK (kind IN ('texto', 'pesquisa', 'imagem', 'resumo_url', 'visao_video', 'slide'));
