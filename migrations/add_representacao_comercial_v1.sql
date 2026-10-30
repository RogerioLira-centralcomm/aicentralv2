ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS trilha_representacao VARCHAR(32);

ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS fluxo_proposta_representacao VARCHAR(32);

ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS proposta_representacao_pronta BOOLEAN DEFAULT FALSE;

UPDATE cadu_cotacoes
SET proposta_representacao_pronta = FALSE
WHERE proposta_representacao_pronta IS NULL;

ALTER TABLE cadu_pi
    ADD COLUMN IF NOT EXISTS numero_io VARCHAR(80);

ALTER TABLE cadu_pi
    ADD COLUMN IF NOT EXISTS comissao_prevista_estimada NUMERIC(14, 2);

ALTER TABLE cadu_pi
    ADD COLUMN IF NOT EXISTS modo_operacao VARCHAR(32) DEFAULT 'campanha';

UPDATE cadu_pi
SET modo_operacao = 'campanha'
WHERE modo_operacao IS NULL OR BTRIM(modo_operacao) = '';

UPDATE cadu_pi p
SET modo_operacao = 'representacao'
FROM cadu_cotacoes c
WHERE p.cotacao_id = c.id
  AND c.tipo_de_contrato = 'representacao_comercial';

CREATE TABLE IF NOT EXISTS cadu_pi_representacao_relatorio (
    id SERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    tipo VARCHAR(16) NOT NULL DEFAULT 'parcial',
    periodo_inicio DATE,
    periodo_fim DATE,
    arquivo_path VARCHAR(500),
    arquivo_nome VARCHAR(255),
    enviado_cliente_em TIMESTAMP,
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP),
    created_by INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pi_rep_relatorio_pi
    ON cadu_pi_representacao_relatorio(id_pi);

CREATE TABLE IF NOT EXISTS cadu_nf_comissao_representacao (
    id SERIAL PRIMARY KEY,
    id_parceiro INTEGER NOT NULL,
    competencia DATE NOT NULL,
    valor_comissao NUMERIC(14, 2) NOT NULL DEFAULT 0,
    codigo_servico VARCHAR(20) DEFAULT '17.06.01',
    vencimento DATE,
    valor_recebido NUMERIC(14, 2),
    recebido_em DATE,
    status VARCHAR(32) DEFAULT 'rascunho',
    discriminacao TEXT,
    spedy_invoice_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_nf_comissao_parceiro_competencia
    ON cadu_nf_comissao_representacao(id_parceiro, competencia);

CREATE TABLE IF NOT EXISTS cadu_nf_comissao_pi (
    id SERIAL PRIMARY KEY,
    id_nf_comissao INTEGER NOT NULL REFERENCES cadu_nf_comissao_representacao(id) ON DELETE CASCADE,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    valor_comissao_pi NUMERIC(14, 2),
    UNIQUE (id_nf_comissao, id_pi)
);

CREATE INDEX IF NOT EXISTS idx_nf_comissao_pi_nf ON cadu_nf_comissao_pi(id_nf_comissao);
CREATE INDEX IF NOT EXISTS idx_nf_comissao_pi_pi ON cadu_nf_comissao_pi(id_pi);
