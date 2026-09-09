CREATE TABLE IF NOT EXISTS cadu_cotacao_itens_especificos (
    id BIGSERIAL PRIMARY KEY,
    cotacao_id INTEGER NOT NULL
        REFERENCES cadu_cotacoes(id) ON DELETE CASCADE,
    tipo_comercial VARCHAR(32) NOT NULL
        CHECK (tipo_comercial IN ('parceiros', 'formatos_interativos', 'dados')),
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    quantidade NUMERIC(14, 2) NOT NULL DEFAULT 1 CHECK (quantidade > 0),
    valor_unitario NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (valor_unitario >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ordem INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cotacao_itens_especificos_ordem
    ON cadu_cotacao_itens_especificos (cotacao_id, ordem, id);
