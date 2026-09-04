-- Histórico seguro do copiloto e vínculo transacional de sequências do CRM v3.
-- Não armazena prompt bruto nem dados pessoais de contato.
CREATE TABLE IF NOT EXISTS crm_ai_interactions (
    id BIGSERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    atividade_id BIGINT NULL REFERENCES sales_atividades(id) ON DELETE SET NULL,
    executivo_id INTEGER NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    funcao VARCHAR(40) NOT NULL,
    origem VARCHAR(30) NOT NULL DEFAULT 'fallback',
    modelo VARCHAR(100) NULL,
    conteudo JSONB NOT NULL DEFAULT '{}'::jsonb,
    aplicado BOOLEAN NOT NULL DEFAULT FALSE,
    aplicado_em TIMESTAMPTZ NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crm_ai_interactions_cliente
    ON crm_ai_interactions (cliente_id, criado_em DESC);

CREATE TABLE IF NOT EXISTS crm_atividade_sequencias (
    id BIGSERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    executivo_id INTEGER NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    titulo VARCHAR(255) NOT NULL,
    origem VARCHAR(30) NOT NULL DEFAULT 'fallback',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_atividade_sequencia_itens (
    sequencia_id BIGINT NOT NULL REFERENCES crm_atividade_sequencias(id) ON DELETE CASCADE,
    atividade_id BIGINT NOT NULL REFERENCES sales_atividades(id) ON DELETE CASCADE,
    ordem SMALLINT NOT NULL,
    canal VARCHAR(30) NULL,
    PRIMARY KEY (sequencia_id, atividade_id)
);

CREATE INDEX IF NOT EXISTS idx_crm_atividade_seq_cliente
    ON crm_atividade_sequencias (cliente_id, criado_em DESC);
