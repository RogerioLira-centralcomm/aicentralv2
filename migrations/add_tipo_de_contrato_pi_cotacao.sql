ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS tipo_de_contrato VARCHAR(32);

UPDATE cadu_cotacoes
SET tipo_de_contrato = 'operacao_propria'
WHERE tipo_de_contrato IS NULL OR BTRIM(tipo_de_contrato) = '';

ALTER TABLE cadu_cotacoes
    ALTER COLUMN tipo_de_contrato SET DEFAULT 'operacao_propria',
    ALTER COLUMN tipo_de_contrato SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cadu_cotacoes_tipo_de_contrato_check'
          AND conrelid = 'cadu_cotacoes'::regclass
    ) THEN
        ALTER TABLE cadu_cotacoes
            ADD CONSTRAINT cadu_cotacoes_tipo_de_contrato_check
            CHECK (
                tipo_de_contrato IN (
                    'operacao_propria',
                    'representacao_comercial'
                )
            );
    END IF;
END
$$;

ALTER TABLE cadu_pi
    ADD COLUMN IF NOT EXISTS tipo_de_contrato VARCHAR(32);

UPDATE cadu_pi
SET tipo_de_contrato = 'operacao_propria'
WHERE tipo_de_contrato IS NULL OR BTRIM(tipo_de_contrato) = '';

ALTER TABLE cadu_pi
    ALTER COLUMN tipo_de_contrato SET DEFAULT 'operacao_propria',
    ALTER COLUMN tipo_de_contrato SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cadu_pi_tipo_de_contrato_check'
          AND conrelid = 'cadu_pi'::regclass
    ) THEN
        ALTER TABLE cadu_pi
            ADD CONSTRAINT cadu_pi_tipo_de_contrato_check
            CHECK (
                tipo_de_contrato IN (
                    'operacao_propria',
                    'representacao_comercial'
                )
            );
    END IF;
END
$$;
