-- Renomeia tbl_cliente.percentual → fee (Fee_ag / Fee_pr no cadastro)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tbl_cliente'
          AND column_name = 'percentual'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tbl_cliente'
          AND column_name = 'fee'
    ) THEN
        ALTER TABLE public.tbl_cliente RENAME COLUMN percentual TO fee;
    END IF;
END $$;
