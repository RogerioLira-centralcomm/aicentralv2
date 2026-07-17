-- Converte apresentacao_dados para TEXT (briefing livre).
-- Alguns ambientes tinham a coluna como JSON, o que quebrava o INSERT de texto do formulário.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cadu_cotacoes'
          AND column_name = 'apresentacao_dados'
    ) THEN
        ALTER TABLE cadu_cotacoes ADD COLUMN apresentacao_dados TEXT;
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cadu_cotacoes'
          AND column_name = 'apresentacao_dados'
          AND udt_name IN ('json', 'jsonb')
    ) THEN
        ALTER TABLE cadu_cotacoes
            ALTER COLUMN apresentacao_dados TYPE TEXT
            USING (
                CASE
                    WHEN apresentacao_dados IS NULL THEN NULL::text
                    WHEN jsonb_typeof(apresentacao_dados::jsonb) = 'string'
                        THEN apresentacao_dados::jsonb #>> '{}'
                    WHEN jsonb_typeof(apresentacao_dados::jsonb) = 'object'
                        THEN COALESCE(
                            apresentacao_dados::jsonb ->> 'texto',
                            apresentacao_dados::jsonb ->> 'resumo',
                            apresentacao_dados::jsonb::text
                        )
                    ELSE apresentacao_dados::text
                END
            );
    END IF;
END $$;

COMMENT ON COLUMN cadu_cotacoes.apresentacao_dados IS 'Resumo do briefing da campanha (texto livre)';
