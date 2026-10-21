CREATE TABLE IF NOT EXISTS cadu_cotacao_destinatario (
    id BIGSERIAL PRIMARY KEY,
    id_cotacao INTEGER NOT NULL REFERENCES cadu_cotacoes(id) ON DELETE CASCADE,
    id_contato_cliente INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    papel VARCHAR(20) NOT NULL CHECK (papel IN ('agencia', 'cliente_final', 'parceiro')),
    padrao BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    CONSTRAINT uq_cotacao_contato_operacional UNIQUE (id_cotacao, id_contato_cliente)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cotacao_destinatario_padrao_papel
    ON cadu_cotacao_destinatario(id_cotacao, papel) WHERE padrao;
CREATE INDEX IF NOT EXISTS idx_cotacao_destinatario_cotacao
    ON cadu_cotacao_destinatario(id_cotacao);

CREATE TABLE IF NOT EXISTS cadu_cotacao_email_log (
    id BIGSERIAL PRIMARY KEY,
    id_cotacao INTEGER NOT NULL REFERENCES cadu_cotacoes(id) ON DELETE CASCADE,
    tipo VARCHAR(60) NOT NULL,
    assunto TEXT NOT NULL,
    destinatario_nome TEXT,
    destinatario_email TEXT NOT NULL,
    html TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'enviando', 'sucesso', 'erro')),
    brevo_message_id TEXT,
    erro TEXT,
    criado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    enviado_em TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP)
);
CREATE INDEX IF NOT EXISTS idx_cotacao_email_log_cotacao_created
    ON cadu_cotacao_email_log(id_cotacao, created_at DESC);
