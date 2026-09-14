ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS grupo_plano_id UUID;

ALTER TABLE cadu_cotacoes
    ADD COLUMN IF NOT EXISTS eh_principal BOOLEAN;

UPDATE cadu_cotacoes
SET grupo_plano_id = gen_random_uuid()
WHERE grupo_plano_id IS NULL;

UPDATE cadu_cotacoes
SET eh_principal = TRUE
WHERE eh_principal IS NULL;

ALTER TABLE cadu_cotacoes
    ALTER COLUMN grupo_plano_id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN grupo_plano_id SET NOT NULL,
    ALTER COLUMN eh_principal SET DEFAULT TRUE,
    ALTER COLUMN eh_principal SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS cadu_cotacoes_uma_principal_por_grupo
    ON cadu_cotacoes (grupo_plano_id)
    WHERE eh_principal AND deleted_at IS NULL;
