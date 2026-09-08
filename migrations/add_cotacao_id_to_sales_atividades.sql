ALTER TABLE sales_atividades
    ADD COLUMN IF NOT EXISTS cotacao_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_sales_atividades_cotacao'
    ) THEN
        ALTER TABLE sales_atividades
            ADD CONSTRAINT fk_sales_atividades_cotacao
            FOREIGN KEY (cotacao_id) REFERENCES cadu_cotacoes(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_sales_atividades_cotacao_id
    ON sales_atividades (cotacao_id)
    WHERE cotacao_id IS NOT NULL;

COMMENT ON COLUMN sales_atividades.cotacao_id IS
    'Cotação/proposta relacionada à atividade; vínculo opcional para o pipeline comercial.';
