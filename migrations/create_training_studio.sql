-- Espelho do DDL em aicentralv2/training_studio/schema.py.
-- O Python cria as tabelas no primeiro acesso (IF NOT EXISTS).
-- Rodar este arquivo só antecipa isso no painel de migrations.

CREATE TABLE IF NOT EXISTS cx_treinamentos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    descricao TEXT,
    slug VARCHAR(80) UNIQUE,
    guia_estilo JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cx_treinamento_sessoes (
    id BIGSERIAL PRIMARY KEY,
    treinamento_id INTEGER NOT NULL REFERENCES cx_treinamentos(id) ON DELETE CASCADE,
    titulo VARCHAR(200) NOT NULL DEFAULT 'Sessão',
    conteudo_html TEXT NOT NULL DEFAULT '',
    -- FUTURO: slides JSONB (quebra automática do texto corrido)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_sessoes_treino
    ON cx_treinamento_sessoes (treinamento_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_fontes (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    titulo VARCHAR(300),
    resumo TEXT NOT NULL DEFAULT '',
    incluido_no_contexto BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_fontes_sessao
    ON cx_treinamento_fontes (sessao_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_imagens (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    asset_url TEXT NOT NULL,
    thumb_url TEXT,
    prompt TEXT NOT NULL DEFAULT '',
    -- FUTURO: posicao JSONB / slide_id para drag-and-drop no canvas
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_imagens_sessao
    ON cx_treinamento_imagens (sessao_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_agent_mensagens (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL DEFAULT '',
    tool_used VARCHAR(40),
    display_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_agent_msgs
    ON cx_treinamento_agent_mensagens (sessao_id, created_at, id);

CREATE TABLE IF NOT EXISTS cx_treinamento_ai_ledger (
    id BIGSERIAL PRIMARY KEY,
    treinamento_id INTEGER NOT NULL REFERENCES cx_treinamentos(id) ON DELETE CASCADE,
    sessao_id BIGINT REFERENCES cx_treinamento_sessoes(id) ON DELETE SET NULL,
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('texto', 'pesquisa', 'imagem', 'resumo_url')),
    provider VARCHAR(40) NOT NULL DEFAULT 'openrouter',
    model VARCHAR(120),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    cost_brl NUMERIC(12,2) NOT NULL DEFAULT 0,
    usd_brl_rate NUMERIC(10,4),
    usd_brl_source VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_ai_ledger_sessao
    ON cx_treinamento_ai_ledger (sessao_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_ai_ledger_treino
    ON cx_treinamento_ai_ledger (treinamento_id, created_at DESC);

ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS slug VARCHAR(80);
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS ordem INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS horario_inicio VARCHAR(5);
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS horario_fim VARCHAR(5);
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS facilitadores TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) NOT NULL DEFAULT 'bloco';
CREATE UNIQUE INDEX IF NOT EXISTS idx_cx_treinamento_sessoes_slug
    ON cx_treinamento_sessoes (treinamento_id, slug) WHERE slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS cx_treinamento_planos (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    marca VARCHAR(160) NOT NULL,
    briefing TEXT NOT NULL DEFAULT '',
    budget_brl NUMERIC(14,2) NOT NULL DEFAULT 0,
    plano JSONB NOT NULL DEFAULT '{}'::jsonb,
    analise JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- FUTURO: motor de forecast (alcance, atenção, frequência, risco)
    previsao_impacto JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_planos_sessao
    ON cx_treinamento_planos (sessao_id, created_at DESC);
