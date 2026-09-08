ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS tipo_comercial VARCHAR(32);

UPDATE cadu_cotacoes
SET tipo_comercial = 'midia'
WHERE tipo_comercial IS NULL OR BTRIM(tipo_comercial) = '';

ALTER TABLE cadu_cotacoes
    ALTER COLUMN tipo_comercial SET DEFAULT 'midia',
    ALTER COLUMN tipo_comercial SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cadu_cotacoes_tipo_comercial_check'
          AND conrelid = 'cadu_cotacoes'::regclass
    ) THEN
        ALTER TABLE cadu_cotacoes
            ADD CONSTRAINT cadu_cotacoes_tipo_comercial_check
            CHECK (
                tipo_comercial IN (
                    'midia',
                    'parceiros',
                    'formatos_interativos',
                    'dados'
                )
            );
    END IF;
END
$$;
