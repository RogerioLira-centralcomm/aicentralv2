-- Custo de mídia orçado e preço unitário da cotação por campanha PI
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cadu_pi_campanha'
          AND column_name = 'custo_midia_orcado'
    ) THEN
        ALTER TABLE cadu_pi_campanha ADD COLUMN custo_midia_orcado VARCHAR(30);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cadu_pi_campanha'
          AND column_name = 'preco_unitario_orcado'
    ) THEN
        ALTER TABLE cadu_pi_campanha ADD COLUMN preco_unitario_orcado VARCHAR(30);
    END IF;
END $$;
