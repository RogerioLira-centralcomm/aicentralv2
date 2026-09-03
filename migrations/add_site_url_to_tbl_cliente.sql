-- Adiciona a coluna opcional `site_url` (VARCHAR) em tbl_cliente.
-- Introduzida em set/2026 para o CRM v3 permitir persistir o site do
-- cliente e derivar o logo automaticamente pelo domínio (via Clearbit).
-- Bases sem a coluna continuam funcionando normalmente — o backend
-- detecta a presença via `_has_column` em `aicentralv2/db.py`.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tbl_cliente'
          AND column_name = 'site_url'
    ) THEN
        ALTER TABLE tbl_cliente ADD COLUMN site_url VARCHAR(255);
    END IF;
END $$;
